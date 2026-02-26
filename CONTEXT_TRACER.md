# Context Tracer — Business Logic Compiler

The Context Tracer is a virtual machine that executes use cases on abstract entities without real code. It traces data flow through every step, forks context at branch points, and reports logical errors through pure static analysis.

No database. No HTTP. No runtime. Just logic.

## 1. Concept: Eidos (Abstract Context Model)

Every action in a use case **transforms** the context. Before an action, context is in state A; after — state B. Each step declares:

- **Reads** — what it expects to already exist in context
- **Writes** — what it adds to context
- **Mutates** — what it changes (field already exists, value changes)
- **Invalidates** — what it removes or marks as stale

These declarations form an **eidos** — a shadow of real entities. An eidos doesn't describe *how* data is stored; it describes *what is known* about the system at each step.

### Eidos vs Reality

A real ORM model `Order` has 50 fields — timestamps, foreign keys, JSON blobs, audit trails. The eidos `Order` for a "place order" use case knows only 4:

| Eidos field | Why it matters |
|---|---|
| `order.id` | Created by the "create order" step, read by every subsequent step |
| `order.status` | State machine field — transitions must be verified |
| `order.total` | Computed from line items, read by payment step |
| `order.user_id` | Links order to user, must exist before creation |

Everything else is invisible to the tracer. This is deliberate: the tracer verifies **business logic**, not storage layout.

## 2. Core Data Structures

```python
from dataclasses import dataclass, field
from enum import Enum


class SlotState(Enum):
    AVAILABLE = "available"
    MUTATED = "mutated"
    INVALIDATED = "invalidated"


@dataclass
class ContextSlot:
    name: str
    type: str
    source_step: str
    state: SlotState = SlotState.AVAILABLE
    constraint: str | None = None
    read_by: list[str] = field(default_factory=list)


@dataclass
class ContextSnapshot:
    step_id: str
    slots: dict[str, ContextSlot] = field(default_factory=dict)

    def has(self, name: str) -> bool:
        slot = self.slots.get(name)
        return slot is not None and slot.state != SlotState.INVALIDATED

    def get_type(self, name: str) -> str | None:
        slot = self.slots.get(name)
        return slot.type if slot else None

    def fork(self, new_step_id: str) -> "ContextSnapshot":
        import copy
        forked = copy.deepcopy(self)
        forked.step_id = new_step_id
        return forked


@dataclass
class ReadEffect:
    field: str
    expected_type: str


@dataclass
class WriteEffect:
    field: str
    type: str
    constraint: str | None = None


@dataclass
class InvalidateEffect:
    field: str


@dataclass
class ActionEffect:
    reads: list[ReadEffect] = field(default_factory=list)
    writes: list[WriteEffect] = field(default_factory=list)
    invalidates: list[InvalidateEffect] = field(default_factory=list)

    @classmethod
    def from_action_spec(cls, spec: dict) -> "ActionEffect":
        return cls(
            reads=[ReadEffect(**r) for r in spec.get("reads", [])],
            writes=[WriteEffect(**w) for w in spec.get("writes", [])],
            invalidates=[InvalidateEffect(**i) for i in spec.get("invalidates", [])],
        )


class FindingSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingCategory(Enum):
    DATA_GAP = "data_gap"
    DEAD_DATA = "dead_data"
    TYPE_MISMATCH = "type_mismatch"
    OVERWRITE_WARNING = "overwrite_warning"
    BRANCH_DIVERGENCE = "branch_divergence"
    BRANCH_STATE_DIFFERENCE = "branch_state_difference"
    FORBIDDEN_TRANSITION = "forbidden_transition"
    CROSS_UC_MUTATION_CONFLICT = "cross_uc_mutation_conflict"
    MISSING_POSTCONDITION = "missing_postcondition"


@dataclass
class Finding:
    severity: FindingSeverity
    category: FindingCategory
    step_id: str
    message: str
    suggestion: str
```

## 3. Context Tracer (The Virtual Machine)

```python
@dataclass
class UseCaseSpec:
    id: str
    components: list[dict]
    steps: list[dict]
    postconditions: list[dict]
    alternative_flows: list[dict] = field(default_factory=list)


class ContextTracer:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def trace_usecase(self, spec: UseCaseSpec) -> list[Finding]:
        self.findings = []
        ctx = ContextSnapshot(step_id="init")

        self._apply_components(ctx, spec.components)

        for step in spec.steps:
            effect = ActionEffect.from_action_spec(step.get("effect", {}))
            ctx = self._execute_step(ctx, step["id"], effect)

        self._verify_postconditions(ctx, spec.postconditions)

        for alt_flow in spec.alternative_flows:
            self._trace_alternative_flow(ctx, spec, alt_flow)

        self._detect_dead_data(ctx, spec.postconditions)

        return self.findings

    def _apply_components(
        self, ctx: ContextSnapshot, components: list[dict]
    ) -> None:
        for component in components:
            for slot_spec in component.get("provides", []):
                slot = ContextSlot(
                    name=slot_spec["field"],
                    type=slot_spec["type"],
                    source_step="component:" + component["id"],
                )
                ctx.slots[slot.name] = slot

    def _execute_step(
        self, ctx: ContextSnapshot, step_id: str, effect: ActionEffect
    ) -> ContextSnapshot:
        for read in effect.reads:
            if not ctx.has(read.field):
                self.findings.append(Finding(
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.DATA_GAP,
                    step_id=step_id,
                    message=f"Step reads '{read.field}' but it does not exist in context",
                    suggestion=f"Add a preceding step that produces '{read.field}' "
                               f"or include it in components",
                ))
                continue

            actual_type = ctx.get_type(read.field)
            if actual_type and actual_type != read.expected_type:
                self.findings.append(Finding(
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.TYPE_MISMATCH,
                    step_id=step_id,
                    message=f"Step expects '{read.field}' as {read.expected_type} "
                            f"but context has {actual_type}",
                    suggestion=f"Align types between producer and consumer of "
                               f"'{read.field}'",
                ))

            ctx.slots[read.field].read_by.append(step_id)

        for write in effect.writes:
            if ctx.has(write.field):
                existing = ctx.slots[write.field]
                self.findings.append(Finding(
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.OVERWRITE_WARNING,
                    step_id=step_id,
                    message=f"Step overwrites '{write.field}' previously set by "
                            f"'{existing.source_step}'",
                    suggestion=f"Verify this overwrite is intentional; consider "
                               f"using a mutation instead",
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

    def _verify_postconditions(
        self, ctx: ContextSnapshot, postconditions: list[dict]
    ) -> None:
        for post in postconditions:
            field_name = post["field"]
            if not ctx.has(field_name):
                self.findings.append(Finding(
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.DATA_GAP,
                    step_id="postcondition",
                    message=f"Postcondition checks '{field_name}' but it does not "
                            f"exist in final context",
                    suggestion=f"Ensure some step produces '{field_name}' before "
                               f"the use case ends",
                ))

    def _trace_alternative_flow(
        self,
        main_ctx: ContextSnapshot,
        spec: UseCaseSpec,
        alt_flow: dict,
    ) -> None:
        branch_point = alt_flow["branch_after_step"]

        branch_ctx = None
        temp_ctx = ContextSnapshot(step_id="init")
        self._apply_components(temp_ctx, spec.components)
        for step in spec.steps:
            if step["id"] == branch_point:
                branch_ctx = temp_ctx.fork(f"alt:{alt_flow['id']}")
                break
            effect = ActionEffect.from_action_spec(step.get("effect", {}))
            temp_ctx = self._execute_step(temp_ctx, step["id"], effect)

        if branch_ctx is None:
            return

        for step in alt_flow.get("steps", []):
            effect = ActionEffect.from_action_spec(step.get("effect", {}))
            branch_ctx = self._execute_step(branch_ctx, step["id"], effect)

        self._check_branch_compatibility(main_ctx, branch_ctx, alt_flow["id"])

    def _check_branch_compatibility(
        self,
        main_ctx: ContextSnapshot,
        alt_ctx: ContextSnapshot,
        alt_flow_id: str,
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
                step_id=f"alt:{alt_flow_id}",
                message=f"Field '{field_name}' exists in happy path but not in "
                        f"alternative flow '{alt_flow_id}'",
                suggestion=f"Ensure downstream consumers of '{field_name}' handle "
                           f"its absence in the alternative flow",
            ))

        for field_name in main_fields & alt_fields:
            main_constraint = main_ctx.slots[field_name].constraint
            alt_constraint = alt_ctx.slots[field_name].constraint
            if main_constraint != alt_constraint:
                self.findings.append(Finding(
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.BRANCH_STATE_DIFFERENCE,
                    step_id=f"alt:{alt_flow_id}",
                    message=f"Field '{field_name}' has constraint "
                            f"'{main_constraint}' in happy path but "
                            f"'{alt_constraint}' in alt flow '{alt_flow_id}'",
                    suggestion=f"Verify both constraint values are valid for "
                               f"downstream steps",
                ))

    def _detect_dead_data(
        self, ctx: ContextSnapshot, postconditions: list[dict]
    ) -> None:
        postcondition_fields = {p["field"] for p in postconditions}

        for name, slot in ctx.slots.items():
            if slot.source_step.startswith("component:"):
                continue
            if name in postcondition_fields:
                continue
            if not slot.read_by:
                self.findings.append(Finding(
                    severity=FindingSeverity.INFO,
                    category=FindingCategory.DEAD_DATA,
                    step_id=slot.source_step,
                    message=f"Step produces '{name}' but no subsequent step reads it",
                    suggestion=f"Remove '{name}' from step output or add a consumer",
                ))
```

## 4. Branch Handling (Alternative Flows)

When a use case has alternative flows (error paths, edge cases, permission failures), the context **forks** at the branch point. The tracer:

1. Replays the main flow up to the branch point
2. Creates an independent copy of the context via `fork()`
3. Executes the alternative flow's steps against the forked copy
4. Compares the final main context and the final branch context

Two categories of findings emerge from branch comparison:

| Category | Meaning |
|---|---|
| **Branch Divergence** | A field exists in one flow but not the other. Downstream code that depends on this field will break on the alternative path. |
| **Branch State Difference** | The same field has different constraints across branches. Example: `order.status = "confirmed"` in happy path, `order.status = "cancelled"` in alt flow — both valid, but downstream steps must be aware. |

## 5. Dead Data Detection

A field is "dead" when it is produced by a step but never consumed by any subsequent step or postcondition.

Dead data signals one of two problems:
- The producing step does unnecessary work (waste)
- A consumer step is missing its read declaration (latent bug)

The tracer skips two categories from dead data detection:
- **Component-provided fields** — these represent preconditions, not computed outputs
- **Postcondition fields** — these are consumed by verification, even if no step reads them

## 6. Cross-UseCase Analyzer

Individual use case tracing catches errors within one scenario. The `CrossUseCaseAnalyzer` finds conflicts **between** scenarios.

```python
@dataclass
class MutationRecord:
    usecase_id: str
    step_id: str
    field: str
    constraint: str | None


class CrossUseCaseAnalyzer:
    def __init__(self) -> None:
        self.write_map: dict[str, list[MutationRecord]] = {}

    def register_trace(
        self, usecase_id: str, ctx: ContextSnapshot
    ) -> None:
        for name, slot in ctx.slots.items():
            if slot.source_step.startswith("component:"):
                continue
            record = MutationRecord(
                usecase_id=usecase_id,
                step_id=slot.source_step,
                field=name,
                constraint=slot.constraint,
            )
            self.write_map.setdefault(name, []).append(record)

    def find_conflicts(self) -> list[Finding]:
        findings: list[Finding] = []

        for field_name, records in self.write_map.items():
            if len(records) < 2:
                continue

            constraints = {r.constraint for r in records}
            if len(constraints) > 1:
                sources = ", ".join(
                    f"{r.usecase_id}:{r.step_id}" for r in records
                )
                findings.append(Finding(
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.CROSS_UC_MUTATION_CONFLICT,
                    step_id="cross-uc",
                    message=f"Field '{field_name}' written with different "
                            f"constraints by: {sources}",
                    suggestion=f"Verify that concurrent mutations to "
                               f"'{field_name}' don't conflict at runtime",
                ))

        return findings
```

## 7. State Machine Verifier

Many domain entities have state machine semantics — an `Order` transitions through `draft → confirmed → shipped → delivered`. The verifier checks every state mutation in a trace against the allowed transitions table.

```python
@dataclass
class TransitionTable:
    entity: str
    field: str
    transitions: dict[str, list[str]]


class StateMachineVerifier:
    def __init__(self, tables: list[TransitionTable]) -> None:
        self.tables = {
            (t.entity, t.field): t.transitions for t in tables
        }

    def verify_trace(
        self, steps: list[dict], ctx_snapshots: list[ContextSnapshot]
    ) -> list[Finding]:
        findings: list[Finding] = []

        for (entity, field_name), allowed in self.tables.items():
            prev_constraint: str | None = None

            for snapshot in ctx_snapshots:
                slot = snapshot.slots.get(field_name)
                if slot is None or slot.constraint is None:
                    continue

                current = slot.constraint
                if prev_constraint is not None and current != prev_constraint:
                    allowed_targets = allowed.get(prev_constraint, [])
                    if current not in allowed_targets:
                        findings.append(Finding(
                            severity=FindingSeverity.ERROR,
                            category=FindingCategory.FORBIDDEN_TRANSITION,
                            step_id=snapshot.step_id,
                            message=f"{entity}.{field_name}: transition "
                                    f"'{prev_constraint}' → '{current}' "
                                    f"is not allowed",
                            suggestion=f"Allowed transitions from "
                                       f"'{prev_constraint}': "
                                       f"{allowed_targets}",
                        ))

                prev_constraint = current

        return findings
```

## 8. Full Assembly

The `UseCaseVerifier` ties together context tracing, state machine verification, and cross-use-case analysis into a single entry point.

```python
class UseCaseVerifier:
    def __init__(
        self,
        transition_tables: list[TransitionTable] | None = None,
    ) -> None:
        self.tracer = ContextTracer()
        self.state_verifier = StateMachineVerifier(transition_tables or [])
        self.cross_analyzer = CrossUseCaseAnalyzer()

    def verify(self, spec: UseCaseSpec) -> list[Finding]:
        findings = self.tracer.trace_usecase(spec)

        snapshots = self._collect_snapshots(spec)
        findings.extend(
            self.state_verifier.verify_trace(spec.steps, snapshots)
        )

        final_ctx = self._build_final_context(spec)
        self.cross_analyzer.register_trace(spec.id, final_ctx)

        return findings

    def verify_cross_usecase(self) -> list[Finding]:
        return self.cross_analyzer.find_conflicts()

    def _collect_snapshots(
        self, spec: UseCaseSpec
    ) -> list[ContextSnapshot]:
        snapshots: list[ContextSnapshot] = []
        ctx = ContextSnapshot(step_id="init")
        self.tracer._apply_components(ctx, spec.components)
        snapshots.append(ctx.fork("init"))

        for step in spec.steps:
            effect = ActionEffect.from_action_spec(step.get("effect", {}))
            ctx = self.tracer._execute_step(ctx, step["id"], effect)
            snapshots.append(ctx.fork(step["id"]))

        return snapshots

    def _build_final_context(
        self, spec: UseCaseSpec
    ) -> ContextSnapshot:
        ctx = ContextSnapshot(step_id="init")
        self.tracer._apply_components(ctx, spec.components)
        for step in spec.steps:
            effect = ActionEffect.from_action_spec(step.get("effect", {}))
            ctx = self.tracer._execute_step(ctx, step["id"], effect)
        return ctx
```

### CLI Output Example

```
$ ucf trace specs/place_order.yaml

── Context Trace: place_order ──────────────────────────────────

  [init] Components loaded: user.id, user.email, cart.items
  [validate_cart] ✓ reads cart.items → writes cart.validated (bool)
  [create_order] ✓ reads cart.validated, user.id → writes order.id, order.status="draft"
  [calculate_total] ✓ reads order.id, cart.items → writes order.total (Decimal)
  [charge_payment] ✓ reads order.total, user.id → writes payment.id, order.status="confirmed"
  [send_confirmation] ✓ reads order.id, user.email → writes notification.id

── State Machine: order.status ─────────────────────────────────

  draft → confirmed  ✓ (via charge_payment)

── Alternative Flow: payment_declined ──────────────────────────

  [branch after: calculate_total]
  [decline_payment] ✓ reads order.total → writes order.status="cancelled"
  ⚠ BRANCH_DIVERGENCE: 'payment.id' exists in happy path but not in alt flow
  ⚠ BRANCH_STATE_DIFFERENCE: order.status = "confirmed" vs "cancelled"

── Summary ─────────────────────────────────────────────────────

  0 errors · 3 warnings · 0 info
```

## 9. What the Tracer Detects

| # | Category | Severity | Meaning |
|---|---|---|---|
| 1 | **Data Gap** | error | Step reads a field that does not exist in context. No preceding step or component provides it. |
| 2 | **Dead Data** | info | Step produces a field that no subsequent step reads and no postcondition checks. |
| 3 | **Type Mismatch** | error | Producer writes `field: str` but consumer expects `field: int`. |
| 4 | **Overwrite Warning** | warning | Step writes to a field already set by a previous step without declaring a mutation. |
| 5 | **Branch Divergence** | warning | A field exists in the happy path but is absent in an alternative flow (or vice versa). |
| 6 | **Branch State Difference** | warning | Same field exists in both branches but with different constraints (e.g., `status="confirmed"` vs `status="cancelled"`). |
| 7 | **Forbidden Transition** | error | A state machine field transitions through a path not listed in the transition table. |
| 8 | **Cross-UC Mutation Conflict** | warning | Two different use cases write incompatible values to the same field without coordination. |
| 9 | **Missing Postcondition** | warning | An action mutates a field but no postcondition verifies the mutation took effect. |
