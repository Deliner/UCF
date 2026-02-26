"""Structural and semantic validation of UCF specs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from ucf.models.action import ActionSpec
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

        step_ids = {s.id for s in uc.steps}
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

    def _validate_step_ref(self, use: str, spec_name: str) -> None:
        if not use:
            return

        ref_spec = self.registry.resolve_ref(use)
        if ref_spec is None:
            parts = use.split("/")
            if len(parts) == 2:
                kind_hint, action_name = parts
                if kind_hint in ("actions", "protocols"):
                    self._issue(
                        IssueSeverity.INFO, IssueCategory.BROKEN_REF, spec_name,
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
                    ref = f"actions/{ref.split('/')[-1]}"
                # Soft check — action might not be loaded

    def _check_orphans(self) -> None:
        referenced_actions: set[str] = set()

        for uc in self.registry.usecases():
            for step in uc.steps:
                referenced_actions.add(step.use)
            for alt in uc.alternative_flows:
                for step in alt.steps:
                    referenced_actions.add(step.use)

        for comp in self.registry.components():
            for step in comp.steps:
                referenced_actions.add(step.use)

        for action in self.registry.actions():
            ref = f"actions/{action.metadata.name}"
            if ref not in referenced_actions:
                self._issue(
                    IssueSeverity.INFO, IssueCategory.ORPHAN,
                    action.metadata.name,
                    f"Action '{action.metadata.name}' is not used by any use case or component",
                )
