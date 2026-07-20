"""Structural and semantic validation of UCF specs.

@implements("actions/validate-spec")
@implements("invariants/spec-names-unique")
@implements("invariants/refs-resolvable")
@implements("invariants/kind-determines-schema")
@implements("invariants/no-circular-refs")
@implements("invariants/graph-acyclic")
@implements("invariants/no-circular-extends")
@implements("invariants/extends-no-step-id-clash")
@implements("invariants/required-inputs-validated")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.event import EventSpec
from ucf.models.invariant import InvariantSpec
from ucf.models.protocol import ProtocolSpec, implementation_reference
from ucf.models.spec import AnySpec
from ucf.models.usecase import UseCaseSpec, invariant_reference
from ucf.parser.registry import SpecRegistry


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCategory(StrEnum):
    BROKEN_REF = "broken_ref"
    MISSING_FIELD = "missing_field"
    NAMING = "naming"
    DUPLICATE = "duplicate"
    ORPHAN = "orphan"
    UNUSED = "unused"
    STEP_ORDER = "step_order"
    TYPE_MISMATCH = "type_mismatch"
    INVARIANT_BINDING = "invariant_binding"
    COMPLETENESS = "completeness"


@dataclass(frozen=True)
class ValidationIssue:
    severity: IssueSeverity
    category: IssueCategory
    spec_name: str
    message: str
    suggestion: str = ""


KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class SpecValidator:
    """Validates a set of specs for structural and semantic correctness."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry
        self.issues: list[ValidationIssue] = []

    def validate_all(self) -> list[ValidationIssue]:
        self.issues = []

        for spec in self.registry.all_specs():
            self._validate_naming(spec)

        for action in self.registry.actions():
            self._validate_action(action)

        for uc in self.registry.usecases():
            self._validate_usecase(uc)

        for comp in self.registry.components():
            self._validate_component(comp)

        for proto in self.registry.protocols():
            self._validate_protocol(proto)

        for event in self.registry.events():
            self._validate_event(event)

        for inv in self.registry.invariants():
            self._validate_invariant(inv)

        self._check_orphans()

        return self.issues

    def _issue(
        self,
        severity: IssueSeverity,
        category: IssueCategory,
        spec_name: str,
        message: str,
        suggestion: str = "",
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                category=category,
                spec_name=spec_name,
                message=message,
                suggestion=suggestion,
            )
        )

    def _validate_naming(self, spec: AnySpec) -> None:
        name = spec.metadata.name
        if not name:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.MISSING_FIELD,
                "<unnamed>",
                "Spec has an empty name",
                "Add a non-empty 'name' field to metadata",
            )
            return
        if not KEBAB_RE.match(name):
            self._issue(
                IssueSeverity.WARNING,
                IssueCategory.NAMING,
                name,
                f"Name '{name}' is not kebab-case",
                "Use lowercase letters and hyphens: my-action-name",
            )

    def _validate_usecase(self, uc: UseCaseSpec) -> None:
        name = uc.metadata.name

        if uc.extends:
            self._validate_extends(uc)

        if uc.trigger and uc.trigger.startswith(("event/", "events/")):
            self._validate_identity_ref(
                uc.trigger,
                name,
                "trigger",
                (EventSpec,),
            )

        if not uc.steps:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.MISSING_FIELD,
                name,
                "Use case has no steps",
            )

        if not uc.postconditions:
            self._issue(
                IssueSeverity.WARNING,
                IssueCategory.MISSING_FIELD,
                name,
                "Use case has no postconditions",
                "Add postconditions to verify the expected outcome",
            )

        seen_step_ids: set[str] = set()
        for step in uc.steps:
            if step.id in seen_step_ids:
                self._issue(
                    IssueSeverity.ERROR,
                    IssueCategory.DUPLICATE,
                    name,
                    f"Duplicate step id '{step.id}' in use case",
                )
            seen_step_ids.add(step.id)

        step_ids = seen_step_ids
        for step in uc.steps:
            self._validate_step_ref(step.use, name)
            for dep in step.depends_on:
                if dep not in step_ids:
                    self._issue(
                        IssueSeverity.ERROR,
                        IssueCategory.BROKEN_REF,
                        name,
                        f"Step '{step.id}' depends on '{dep}' which does not exist",
                    )

        for requirement in uc.requires:
            self._validate_identity_ref(
                requirement.ref,
                name,
                "requires",
                (ComponentSpec,),
            )

        for alt in uc.alternative_flows:
            flow_step_ids = step_ids | {step.id for step in alt.steps}
            for step in alt.steps:
                self._validate_step_ref(step.use, name)
                for dep in step.depends_on:
                    if dep not in flow_step_ids:
                        self._issue(
                            IssueSeverity.ERROR,
                            IssueCategory.BROKEN_REF,
                            name,
                            f"Step '{step.id}' in alternative flow '{alt.name}' "
                            f"depends on '{dep}' which does not exist",
                        )

        for invariant in uc.invariants:
            self._validate_identity_ref(
                invariant_reference(invariant),
                name,
                "invariant",
                (InvariantSpec,),
            )

    def _validate_extends(self, uc: UseCaseSpec) -> None:
        name = uc.metadata.name
        ref = uc.extends
        if not ref:
            return
        parent_ref = ref.replace("$ref:", "")
        parent = self.registry.resolve_ref(parent_ref)
        if parent is None:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.BROKEN_REF,
                name,
                f"extends reference '{ref}' does not resolve to a known use case",
            )
            return
        if not isinstance(parent, UseCaseSpec):
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.TYPE_MISMATCH,
                name,
                f"extends reference '{ref}' resolves to a {parent.kind}, "
                "not a use case",
            )
            return

        visited: set[str] = {name}
        current = parent
        while current is not None and current.extends:
            if current.metadata.name in visited:
                self._issue(
                    IssueSeverity.ERROR,
                    IssueCategory.BROKEN_REF,
                    name,
                    "circular extends chain detected: "
                    f"{' -> '.join(visited)} -> {current.metadata.name}",
                )
                return
            visited.add(current.metadata.name)
            next_ref = current.extends.replace("$ref:", "")
            resolved = self.registry.resolve_ref(next_ref)
            current = resolved if isinstance(resolved, UseCaseSpec) else None

        parent_step_ids = {s.id for s in parent.steps}
        child_step_ids = {s.id for s in uc.steps}
        clash = parent_step_ids & child_step_ids
        if clash:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.DUPLICATE,
                name,
                f"step IDs conflict with parent: {sorted(clash)}",
            )

    def _validate_step_ref(self, use: str, spec_name: str) -> None:
        if not use:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.MISSING_FIELD,
                spec_name,
                "Step has empty 'use' field",
            )
            return

        self._validate_identity_ref(
            use,
            spec_name,
            "step",
            (ActionSpec, ProtocolSpec),
        )

    def _validate_identity_ref(
        self,
        ref: str,
        spec_name: str,
        relationship: str,
        expected_types: tuple[type, ...],
    ) -> AnySpec | None:
        resolved = self.registry.resolve_ref(ref)
        if resolved is None:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.BROKEN_REF,
                spec_name,
                f"{relationship} reference '{ref}' is not loaded",
                f"Ensure {ref}.yaml exists in specs/",
            )
            return None
        if not isinstance(resolved, expected_types):
            expected = " or ".join(
                model.__name__.removesuffix("Spec") for model in expected_types
            )
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.TYPE_MISMATCH,
                spec_name,
                f"{relationship} reference '{ref}' resolves to kind "
                f"'{resolved.kind}', expected {expected}",
            )
            return None
        return resolved

    @staticmethod
    def _with_default_prefix(ref: str, prefix: str) -> str:
        return ref if "/" in ref else f"{prefix}/{ref}"

    def _validate_action(self, action: ActionSpec) -> None:
        for emitted in action.emits:
            self._validate_identity_ref(
                self._with_default_prefix(emitted.event, "events"),
                action.metadata.name,
                "emits",
                (EventSpec,),
            )

    def _validate_component(self, comp: ComponentSpec) -> None:
        name = comp.metadata.name

        if not comp.provides:
            self._issue(
                IssueSeverity.WARNING,
                IssueCategory.MISSING_FIELD,
                name,
                "Component provides nothing",
                "Add 'provides' fields so use cases can consume this component",
            )

        step_ids = {step.id for step in comp.steps}
        for step in comp.steps:
            self._validate_step_ref(step.use, name)
            for dep in step.depends_on:
                if dep not in step_ids:
                    self._issue(
                        IssueSeverity.ERROR,
                        IssueCategory.BROKEN_REF,
                        name,
                        f"Step '{step.id}' in component '{name}' depends on "
                        f"'{dep}' which does not exist",
                    )

    def _validate_protocol(self, proto: ProtocolSpec) -> None:
        name = proto.metadata.name

        if not proto.guarantees:
            self._issue(
                IssueSeverity.WARNING,
                IssueCategory.MISSING_FIELD,
                name,
                "Protocol has no guarantees",
                "Add guarantees to document behavioral contracts",
            )

        for implementation in proto.implementations:
            self._validate_identity_ref(
                implementation_reference(implementation),
                name,
                "implementation",
                (ComponentSpec,),
            )

    def _validate_event(self, event: EventSpec) -> None:
        name = event.metadata.name

        if event.trigger and event.trigger.after:
            self._validate_identity_ref(
                self._with_default_prefix(event.trigger.after, "actions"),
                name,
                "trigger",
                (ActionSpec,),
            )

    def _validate_invariant(self, inv: InvariantSpec) -> None:
        name = inv.metadata.name

        if not inv.rule and not inv.rules and not inv.transitions:
            self._issue(
                IssueSeverity.ERROR,
                IssueCategory.MISSING_FIELD,
                name,
                "Invariant has no rule, rules, or transitions defined",
            )

        for binding in inv.applies_to:
            if binding.action:
                self._validate_identity_ref(
                    self._with_default_prefix(binding.action, "actions"),
                    name,
                    "applies_to.action",
                    (ActionSpec,),
                )
            if binding.usecase:
                self._validate_identity_ref(
                    self._with_default_prefix(binding.usecase, "use-cases"),
                    name,
                    "applies_to.usecase",
                    (UseCaseSpec,),
                )

    def _check_orphans(self) -> None:
        referenced_refs: set[str] = set()

        for uc in self.registry.usecases():
            for step in uc.steps:
                referenced_refs.add(step.use)
            for alt in uc.alternative_flows:
                for step in alt.steps:
                    referenced_refs.add(step.use)
            for req in uc.requires:
                referenced_refs.add(req.ref)
            for inv_ref in uc.invariants:
                ref_str = invariant_reference(inv_ref)
                if ref_str:
                    referenced_refs.add(ref_str)

        for comp in self.registry.components():
            for step in comp.steps:
                referenced_refs.add(step.use)

        for action in self.registry.actions():
            ref = f"actions/{action.metadata.name}"
            if ref not in referenced_refs:
                self._issue(
                    IssueSeverity.INFO,
                    IssueCategory.ORPHAN,
                    action.metadata.name,
                    f"Action '{action.metadata.name}' is not used by any use "
                    "case or component",
                )

        for comp in self.registry.components():
            ref = f"components/{comp.metadata.name}"
            if ref not in referenced_refs:
                self._issue(
                    IssueSeverity.INFO,
                    IssueCategory.ORPHAN,
                    comp.metadata.name,
                    f"Component '{comp.metadata.name}' is not referenced by "
                    "any use case",
                )

        for inv in self.registry.invariants():
            ref = f"invariants/{inv.metadata.name}"
            if ref not in referenced_refs:
                self._issue(
                    IssueSeverity.INFO,
                    IssueCategory.ORPHAN,
                    inv.metadata.name,
                    f"Invariant '{inv.metadata.name}' is not referenced by "
                    "any use case",
                )
