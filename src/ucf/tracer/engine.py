"""Context Tracer — virtual machine that executes use cases on abstract entities.

@implements("actions/trace-usecase")
"""

from __future__ import annotations

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import (
    ActionEffect,
    ContextSlot,
    ContextSnapshot,
    Finding,
    FindingCategory,
    FindingSeverity,
    ReadEffect,
    SlotState,
    WriteEffect,
)


class ContextTracer:
    """Traces data flow through a use case without executing real code."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry
        self.findings: list[Finding] = []

    def trace_usecase(self, uc: UseCaseSpec) -> list[Finding]:
        self.findings = []

        uc = self._resolve_composition(uc)

        ctx = ContextSnapshot(step_id="init")

        self._apply_requires(ctx, uc)

        for step in uc.steps:
            effect = self._build_effect(step)
            ctx = self._execute_step(ctx, step.id, effect)

        self._verify_postconditions(ctx, uc)

        alt_reads: set[str] = set()
        for alt_flow in uc.alternative_flows:
            self._trace_alternative_flow(ctx, uc, alt_flow, alt_reads)

        self._detect_dead_data(ctx, uc, alt_reads)

        return self.findings

    def _resolve_composition(self, uc: UseCaseSpec) -> UseCaseSpec:
        """If UC has extends, flatten it before tracing."""
        if uc.extends is None:
            return uc
        from ucf.composition import resolve_extends
        flattened, _chain, _parent_ids = resolve_extends(uc, self.registry)
        return flattened

    def get_final_context(self, uc: UseCaseSpec) -> ContextSnapshot:
        """Build the final context snapshot after executing all steps."""
        uc = self._resolve_composition(uc)
        ctx = ContextSnapshot(step_id="init")
        self._apply_requires(ctx, uc)
        for step in uc.steps:
            effect = self._build_effect(step)
            ctx = self._execute_step(ctx, step.id, effect, record=False)
        return ctx

    def _apply_requires(self, ctx: ContextSnapshot, uc: UseCaseSpec) -> None:
        for req in uc.requires:
            if isinstance(req, dict):
                ref = req.get("$ref", "")
                alias = req.get("as", "")
            else:
                ref = req.ref
                alias = req.as_

            comp = self.registry.resolve_ref(ref)
            if comp is None or not isinstance(comp, ComponentSpec):
                continue

            source = f"component:{alias or comp.metadata.name}"
            for field_name, field_def in comp.provides.items():
                ftype = ""
                if isinstance(field_def, dict):
                    ftype = field_def.get("type", "")
                else:
                    ftype = field_def.type.value if field_def.type else ""

                ctx.slots[field_name] = ContextSlot(
                    name=field_name,
                    type=ftype,
                    source_step=source,
                )

    def _build_effect(self, step) -> ActionEffect:
        """Build an ActionEffect from a step, enriched by the referenced action spec."""
        writes: list[WriteEffect] = []
        reads: list[str] = []

        for field_name, binding in step.output.items():
            out_name = binding if isinstance(binding, str) else field_name
            writes.append(WriteEffect(field=out_name))

        for field_name, binding in step.input.items():
            self._collect_reads(binding, reads)

        action_ref = step.use
        action_spec = self.registry.resolve_ref(action_ref)

        read_effects: list[ReadEffect] = []
        for r in reads:
            expected = ""
            if isinstance(action_spec, ActionSpec):
                field_def = action_spec.input.get(r)
                if field_def is not None:
                    if isinstance(field_def, dict):
                        expected = field_def.get("type", "")
                    elif hasattr(field_def, "type") and field_def.type:
                        expected = field_def.type.value
            read_effects.append(ReadEffect(field=r, expected_type=expected))

        return ActionEffect(reads=read_effects, writes=writes)

    @staticmethod
    def _collect_reads(value, reads: list[str]) -> None:
        """Recursively extract $steps.X.field references from nested values."""
        if isinstance(value, str):
            if value.startswith("$steps."):
                parts = value.split(".")
                if len(parts) >= 3:
                    reads.append(parts[2])
        elif isinstance(value, dict):
            for v in value.values():
                ContextTracer._collect_reads(v, reads)
        elif isinstance(value, list):
            for item in value:
                ContextTracer._collect_reads(item, reads)

    def _execute_step(
        self, ctx: ContextSnapshot, step_id: str, effect: ActionEffect,
        *, record: bool = True,
    ) -> ContextSnapshot:
        for read in effect.reads:
            if not ctx.has(read.field):
                if record:
                    self.findings.append(Finding(
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.DATA_GAP,
                        step_id=step_id,
                        message=f"Step reads '{read.field}' but it does not exist in context",
                        suggestion=f"Add a preceding step that produces '{read.field}' or include it in components",
                    ))
                continue

            actual_type = ctx.get_type(read.field)
            if read.expected_type and actual_type and actual_type != read.expected_type:
                if record:
                    self.findings.append(Finding(
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.TYPE_MISMATCH,
                        step_id=step_id,
                        message=f"Step expects '{read.field}' as {read.expected_type} but context has {actual_type}",
                        suggestion=f"Align types between producer and consumer of '{read.field}'",
                    ))

            if read.field in ctx.slots:
                ctx.slots[read.field].read_by.append(step_id)

        for write in effect.writes:
            if ctx.has(write.field):
                existing = ctx.slots[write.field]
                if record:
                    self.findings.append(Finding(
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.OVERWRITE_WARNING,
                        step_id=step_id,
                        message=f"Step overwrites '{write.field}' previously set by '{existing.source_step}'",
                        suggestion="Verify this overwrite is intentional; consider using a mutation instead",
                    ))

            ctx.slots[write.field] = ContextSlot(
                name=write.field,
                type=write.type,
                source_step=step_id,
                state=SlotState.AVAILABLE,
                constraint=write.constraint,
            )

        for inv in effect.invalidates:
            if inv.field in ctx.slots:
                ctx.slots[inv.field].state = SlotState.INVALIDATED

        ctx.step_id = step_id
        return ctx

    def _verify_postconditions(self, ctx: ContextSnapshot, uc: UseCaseSpec) -> None:
        # Postconditions are free-text; we check that at least
        # the steps produced some outputs to verify against.
        if uc.postconditions and not ctx.slots:
            self.findings.append(Finding(
                severity=FindingSeverity.WARNING,
                category=FindingCategory.MISSING_POSTCONDITION,
                step_id="postcondition",
                message="Use case has postconditions but no data was produced by steps",
                suggestion="Ensure steps produce outputs that can be verified",
            ))

    def _trace_alternative_flow(
        self, main_ctx: ContextSnapshot, uc: UseCaseSpec, alt_flow,
        alt_reads: set[str] | None = None,
    ) -> None:
        branch_ctx = ContextSnapshot(step_id="init")
        self._apply_requires(branch_ctx, uc)

        for step in uc.steps:
            effect = self._build_effect(step)
            branch_ctx = self._execute_step(branch_ctx, step.id, effect, record=False)

        branch_ctx = branch_ctx.fork(f"alt:{alt_flow.name}")

        for step in alt_flow.steps:
            effect = self._build_effect(step)
            if alt_reads is not None:
                for r in effect.reads:
                    alt_reads.add(r.field)
            branch_ctx = self._execute_step(branch_ctx, step.id, effect)

        self._check_branch_compatibility(main_ctx, branch_ctx, alt_flow.name)

    def _check_branch_compatibility(
        self,
        main_ctx: ContextSnapshot,
        alt_ctx: ContextSnapshot,
        alt_flow_name: str,
    ) -> None:
        main_fields = {
            k for k, v in main_ctx.slots.items()
            if v.state != SlotState.INVALIDATED
        }
        alt_fields = {
            k for k, v in alt_ctx.slots.items()
            if v.state != SlotState.INVALIDATED
        }

        for field_name in main_fields - alt_fields:
            self.findings.append(Finding(
                severity=FindingSeverity.WARNING,
                category=FindingCategory.BRANCH_DIVERGENCE,
                step_id=f"alt:{alt_flow_name}",
                message=f"Field '{field_name}' exists in happy path but not in alt flow '{alt_flow_name}'",
                suggestion=f"Ensure downstream consumers handle absence of '{field_name}' in the alt flow",
            ))

        for field_name in main_fields & alt_fields:
            main_c = main_ctx.slots[field_name].constraint
            alt_c = alt_ctx.slots[field_name].constraint
            if main_c != alt_c and (main_c is not None or alt_c is not None):
                self.findings.append(Finding(
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.BRANCH_STATE_DIFFERENCE,
                    step_id=f"alt:{alt_flow_name}",
                    message=f"Field '{field_name}' has different constraints: "
                            f"'{main_c}' (happy) vs '{alt_c}' (alt flow)",
                    suggestion="Verify both constraint values are valid for downstream steps",
                ))

    def _detect_dead_data(
        self, ctx: ContextSnapshot, uc: UseCaseSpec,
        alt_reads: set[str] | None = None,
    ) -> None:
        for name, slot in ctx.slots.items():
            if slot.source_step.startswith("component:"):
                continue
            if alt_reads and name in alt_reads:
                continue
            if not slot.read_by:
                self.findings.append(Finding(
                    severity=FindingSeverity.INFO,
                    category=FindingCategory.DEAD_DATA,
                    step_id=slot.source_step,
                    message=f"Step produces '{name}' but no subsequent step reads it",
                    suggestion=f"Remove '{name}' from step output or add a consumer",
                ))


class CrossUseCaseAnalyzer:
    """Finds mutation conflicts between use cases."""

    def __init__(self) -> None:
        self.write_map: dict[str, list[tuple[str, str, str | None]]] = {}

    def register_trace(self, usecase_id: str, ctx: ContextSnapshot) -> None:
        for name, slot in ctx.slots.items():
            if slot.source_step.startswith("component:"):
                continue
            key = name
            self.write_map.setdefault(key, []).append(
                (usecase_id, slot.source_step, slot.constraint)
            )

    def find_conflicts(self) -> list[Finding]:
        findings: list[Finding] = []
        for field_name, records in self.write_map.items():
            if len(records) < 2:
                continue

            uc_ids = {r[0] for r in records}
            if len(uc_ids) < 2:
                continue

            constraints = {r[2] for r in records}
            if len(constraints) > 1:
                sources = ", ".join(f"{r[0]}:{r[1]}" for r in records)
                findings.append(Finding(
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.CROSS_UC_MUTATION_CONFLICT,
                    step_id="cross-uc",
                    message=f"Field '{field_name}' written with different constraints by: {sources}",
                    suggestion=f"Verify that concurrent mutations to '{field_name}' don't conflict at runtime",
                ))
        return findings


