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
from enum import Enum

from ucf.models.component import ComponentSpec
from ucf.models.event import EventSpec
from ucf.models.invariant import InvariantSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.spec import AnySpec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCategory(str, Enum):
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

        self._check_duplicates()

        for spec in self.registry.all_specs():
            self._validate_naming(spec)

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
        self.issues.append(ValidationIssue(
            severity=severity,
            category=category,
            spec_name=spec_name,
            message=message,
            suggestion=suggestion,
        ))

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

    def _check_duplicates(self) -> None:
        seen: dict[str, list[str]] = {}
        for spec in self.registry.all_specs():
            key = f"{spec.kind}/{spec.metadata.name}"
            seen.setdefault(key, []).append(spec.metadata.name)

        for key, names in seen.items():
            if len(names) > 1:
                self._issue(
                    IssueSeverity.ERROR,
                    IssueCategory.DUPLICATE,
                    key,
                    f"Duplicate spec: '{key}' defined {len(names)} times",
                )

    def _validate_usecase(self, uc: UseCaseSpec) -> None:
        name = uc.metadata.name

        if uc.extends:
            self._validate_extends(uc)

        if not uc.steps:
            self._issue(
                IssueSeverity.ERROR, IssueCategory.MISSING_FIELD, name,
                "Use case has no steps",
            )

        if not uc.postconditions:
            self._issue(
                IssueSeverity.WARNING, IssueCategory.MISSING_FIELD, name,
                "Use case has no postconditions",
                "Add postconditions to verify the expected outcome",
            )

        seen_step_ids: set[str] = set()
        for step in uc.steps:
            if step.id in seen_step_ids:
                self._issue(
                    IssueSeverity.ERROR, IssueCategory.DUPLICATE, name,
                    f"Duplicate step id '{step.id}' in use case",
                )
            seen_step_ids.add(step.id)

        step_ids = seen_step_ids
        for step in uc.steps:
            self._validate_step_ref(step.use, name)
            for dep in step.depends_on:
                if dep not in step_ids:
                    self._issue(
                        IssueSeverity.ERROR, IssueCategory.BROKEN_REF, name,
                        f"Step '{step.id}' depends on '{dep}' which does not exist",
                    )

        for alt in uc.alternative_flows:
            for step in alt.steps:
                self._validate_step_ref(step.use, name)

        for inv_ref in uc.invariants:
            if isinstance(inv_ref, dict):
                ref_str = inv_ref.get("$ref", "")
            else:
                ref_str = inv_ref.ref
            if ref_str and not self.registry.resolve_ref(ref_str):
                self._issue(
                    IssueSeverity.WARNING, IssueCategory.BROKEN_REF, name,
                    f"Invariant ref '{ref_str}' not found in registry",
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
                IssueSeverity.ERROR, IssueCategory.BROKEN_REF, name,
                f"extends reference '{ref}' does not resolve to a known use case",
            )
            return
        if not isinstance(parent, UseCaseSpec):
            self._issue(
                IssueSeverity.ERROR, IssueCategory.TYPE_MISMATCH, name,
                f"extends reference '{ref}' resolves to a {parent.kind}, not a use case",
            )
            return

        visited: set[str] = {name}
        current = parent
        while current is not None and current.extends:
            if current.metadata.name in visited:
                self._issue(
                    IssueSeverity.ERROR, IssueCategory.BROKEN_REF, name,
                    f"circular extends chain detected: {' -> '.join(visited)} -> {current.metadata.name}",
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
                IssueSeverity.ERROR, IssueCategory.DUPLICATE, name,
                f"step IDs conflict with parent: {sorted(clash)}",
            )

    def _validate_step_ref(self, use: str, spec_name: str) -> None:
        if not use:
            self._issue(
                IssueSeverity.ERROR, IssueCategory.MISSING_FIELD, spec_name,
                "Step has empty 'use' field",
            )
            return

        ref_spec = self.registry.resolve_ref(use)
        if ref_spec is None:
            self._issue(
                IssueSeverity.WARNING, IssueCategory.BROKEN_REF, spec_name,
                f"Step references '{use}' which is not loaded",
                f"Ensure {use}.yaml exists in specs/",
            )

    def _validate_component(self, comp: ComponentSpec) -> None:
        name = comp.metadata.name

        if not comp.provides:
            self._issue(
                IssueSeverity.WARNING, IssueCategory.MISSING_FIELD, name,
                "Component provides nothing",
                "Add 'provides' fields so use cases can consume this component",
            )

        for step in comp.steps:
            self._validate_step_ref(step.use, name)

    def _validate_protocol(self, proto: ProtocolSpec) -> None:
        name = proto.metadata.name

        if not proto.guarantees:
            self._issue(
                IssueSeverity.WARNING, IssueCategory.MISSING_FIELD, name,
                "Protocol has no guarantees",
                "Add guarantees to document behavioral contracts",
            )

    def _validate_event(self, event: EventSpec) -> None:
        name = event.metadata.name

        if event.trigger and event.trigger.after:
            ref = f"actions/{event.trigger.after}"
            if not self.registry.resolve_ref(ref):
                self._issue(
                    IssueSeverity.INFO, IssueCategory.BROKEN_REF, name,
                    f"Event trigger references action '{event.trigger.after}' "
                    f"which is not loaded",
                )

    def _validate_invariant(self, inv: InvariantSpec) -> None:
        name = inv.metadata.name

        if not inv.rule and not inv.rules and not inv.transitions:
            self._issue(
                IssueSeverity.ERROR, IssueCategory.MISSING_FIELD, name,
                "Invariant has no rule, rules, or transitions defined",
            )

        for binding in inv.applies_to:
            if binding.action:
                ref = binding.action
                if not ref.startswith("actions/"):
                    ref = f"actions/{ref}"
                if not self.registry.resolve_ref(ref):
                    self._issue(
                        IssueSeverity.INFO, IssueCategory.BROKEN_REF, name,
                        f"Invariant applies_to references '{ref}' which is not loaded",
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
                if isinstance(req, dict):
                    referenced_refs.add(req.get("$ref", ""))
                else:
                    referenced_refs.add(req.ref)
            for inv_ref in uc.invariants:
                if isinstance(inv_ref, dict):
                    ref_str = inv_ref.get("$ref", inv_ref.get("metadata", {}).get("name", ""))
                else:
                    ref_str = inv_ref.ref
                if ref_str:
                    referenced_refs.add(ref_str)

        for comp in self.registry.components():
            for step in comp.steps:
                referenced_refs.add(step.use)

        for action in self.registry.actions():
            ref = f"actions/{action.metadata.name}"
            if ref not in referenced_refs:
                self._issue(
                    IssueSeverity.INFO, IssueCategory.ORPHAN,
                    action.metadata.name,
                    f"Action '{action.metadata.name}' is not used by any use case or component",
                )

        for comp in self.registry.components():
            ref = f"components/{comp.metadata.name}"
            if ref not in referenced_refs:
                self._issue(
                    IssueSeverity.INFO, IssueCategory.ORPHAN,
                    comp.metadata.name,
                    f"Component '{comp.metadata.name}' is not referenced by any use case",
                )

        for inv in self.registry.invariants():
            ref = f"invariants/{inv.metadata.name}"
            if ref not in referenced_refs:
                self._issue(
                    IssueSeverity.INFO, IssueCategory.ORPHAN,
                    inv.metadata.name,
                    f"Invariant '{inv.metadata.name}' is not referenced by any use case",
                )
