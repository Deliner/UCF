(
    "Input Partition Coverage analyzer — every input equivalence class should "
    'be exercised.\n\n@implements("actions/analyze-input-partitions")\n'
)

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.models.base import FieldDef
from ucf.models.usecase import UseCaseSpec, invariant_reference
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding, FindingCategory, FindingSeverity


@dataclass
class InputPartition:
    name: str
    description: str


@dataclass
class PartitionCoverage:
    action_name: str
    field_name: str
    partition: InputPartition
    covered_by: list[str] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        return len(self.covered_by) > 0


def derive_partitions(field_name: str, field_def: FieldDef) -> list[InputPartition]:
    """Derive equivalence partitions from a FieldDef's type and constraints."""
    partitions: list[InputPartition] = []

    partitions.append(
        InputPartition(
            name="valid_present",
            description=f"{field_name} provided with a valid value",
        )
    )

    if not field_def.required:
        partitions.append(
            InputPartition(
                name="absent",
                description=f"{field_name} not provided (null/missing)",
            )
        )

    ftype = field_def.type.value if field_def.type else "string"

    if ftype == "string":
        partitions.append(
            InputPartition(
                name="empty_string",
                description=f"{field_name} is an empty string",
            )
        )

    if ftype in ("integer", "number"):
        if field_def.min is not None:
            partitions.append(
                InputPartition(
                    name="below_min",
                    description=f"{field_name} < {field_def.min}",
                )
            )
        if field_def.max is not None:
            partitions.append(
                InputPartition(
                    name="above_max",
                    description=f"{field_name} > {field_def.max}",
                )
            )

    if field_def.enum:
        for val in field_def.enum:
            partitions.append(
                InputPartition(
                    name=f"enum_{val}",
                    description=f"{field_name} == {val!r}",
                )
            )
        partitions.append(
            InputPartition(
                name="invalid_enum",
                description=f"{field_name} is not one of {field_def.enum}",
            )
        )

    if ftype == "array":
        partitions.append(
            InputPartition(
                name="empty_array",
                description=f"{field_name} is an empty array",
            )
        )

    if ftype == "boolean":
        partitions.append(
            InputPartition(
                name="true",
                description=f"{field_name} == true",
            )
        )
        partitions.append(
            InputPartition(
                name="false",
                description=f"{field_name} == false",
            )
        )

    return partitions


class InputPartitionAnalyzer:
    """For each action input field, derive partitions and check UC coverage."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> tuple[list[PartitionCoverage], list[Finding]]:
        coverages: list[PartitionCoverage] = []
        findings: list[Finding] = []

        action_to_ucs = self._build_action_uc_map()

        for action in self.registry.actions():
            if not action.input:
                continue

            action_ref = f"actions/{action.metadata.name}"
            consuming_ucs = action_to_ucs.get(action_ref, [])

            for fname, fdef in action.input.items():
                if not isinstance(fdef, FieldDef):
                    continue

                partitions = derive_partitions(fname, fdef)
                for part in partitions:
                    cov = PartitionCoverage(
                        action_name=action.metadata.name,
                        field_name=fname,
                        partition=part,
                    )

                    for uc in consuming_ucs:
                        if self._partition_covered(uc, action_ref, fname, part):
                            cov.covered_by.append(uc.metadata.name)

                    coverages.append(cov)

                    if not cov.is_covered:
                        findings.append(
                            Finding(
                                severity=FindingSeverity.INFO,
                                category=FindingCategory.UNCOVERED_INPUT_PARTITION,
                                step_id=f"actions/{action.metadata.name}",
                                message=(
                                    f"Input '{fname}' partition '{part.name}' "
                                    f"({part.description}) "
                                    f"is not covered by any use case"
                                ),
                                suggestion=(
                                    "Add an alternative_flow or test case that "
                                    "exercises "
                                    f"'{fname}' in the '{part.name}' partition"
                                ),
                            )
                        )

        return coverages, findings

    def _build_action_uc_map(self) -> dict[str, list[UseCaseSpec]]:
        comp_actions: dict[str, set[str]] = {}
        for comp in self.registry.components():
            actions: set[str] = set()
            for step in comp.steps:
                actions.add(step.use)
            comp_actions[f"components/{comp.metadata.name}"] = actions

        result: dict[str, list[UseCaseSpec]] = {}
        for uc in self.registry.usecases():
            for step in uc.steps:
                result.setdefault(step.use, []).append(uc)
            for req in uc.requires:
                ref = req.ref if hasattr(req, "ref") else req.get("$ref", "")
                for action_ref in comp_actions.get(ref, set()):
                    result.setdefault(action_ref, []).append(uc)
        return result

    def _partition_covered(
        self,
        uc: UseCaseSpec,
        action_ref: str,
        field_name: str,
        partition: InputPartition,
    ) -> bool:
        """Check if a UC exercises a given partition through its steps or alt flows."""
        uses_action = self._uc_uses_action(uc, action_ref)

        all_steps = list(uc.steps)
        for alt in uc.alternative_flows:
            all_steps.extend(alt.steps)

        if partition.name == "valid_present":
            if uses_action:
                for step in all_steps:
                    if step.use == action_ref and field_name in step.input:
                        return True
                if self._action_in_component(uc, action_ref):
                    return True

        if partition.name == "absent":
            for step in all_steps:
                if step.use == action_ref and field_name not in step.input:
                    return True
            if self._action_in_component(uc, action_ref):
                return True

        if partition.name in ("empty_string", "empty_array", "invalid_enum"):
            if self._uc_has_input_validation_invariant(uc, action_ref):
                return True

        for alt in uc.alternative_flows:
            trigger_lower = alt.trigger.lower()
            field_lower = field_name.lower().replace("_", " ")

            if partition.name == "empty_string":
                if "empty" in trigger_lower and (
                    field_lower in trigger_lower or field_name in trigger_lower
                ):
                    return True
                if alt.handles_error and "empty" in alt.handles_error.lower():
                    return True
                if alt.handles_error and alt.handles_error == "VALIDATION_ERROR":
                    return True
            if partition.name == "empty_array":
                if ("empty" in trigger_lower or "no " in trigger_lower) and (
                    field_lower in trigger_lower or field_name in trigger_lower
                ):
                    return True
                if alt.handles_error and alt.handles_error == "VALIDATION_ERROR":
                    return True
            if partition.name == "below_min" and (
                "below" in trigger_lower
                or "minimum" in trigger_lower
                or "negative" in trigger_lower
            ):
                return True
            if partition.name == "above_max" and (
                "above" in trigger_lower
                or "maximum" in trigger_lower
                or "exceeds" in trigger_lower
            ):
                return True
            if partition.name == "invalid_enum" and (
                "invalid" in trigger_lower or "unrecognized" in trigger_lower
            ):
                return True
            if partition.name.startswith("enum_"):
                val = partition.name[5:]
                for step in alt.steps:
                    if step.use == action_ref:
                        step_val = step.input.get(field_name)
                        if isinstance(step_val, str) and step_val == val:
                            return True
                if val.lower() in trigger_lower:
                    return True
            if partition.name in ("true", "false") and partition.name in trigger_lower:
                return True

        return False

    def _uc_has_input_validation_invariant(
        self, uc: UseCaseSpec, action_ref: str
    ) -> bool:
        (
            "Check if this UC references the required-inputs-validated invariant "
            "that covers this action."
        )
        for inv_item in uc.invariants:
            ref = invariant_reference(inv_item)
            if ref == "invariants/required-inputs-validated":
                inv_spec = self.registry.resolve_ref(
                    "invariants/required-inputs-validated"
                )
                if inv_spec and hasattr(inv_spec, "applies_to"):
                    for binding in inv_spec.applies_to:
                        a_ref = binding.action or ""
                        if not a_ref.startswith("actions/"):
                            a_ref = f"actions/{a_ref}"
                        if a_ref == action_ref:
                            return True
        return False

    def _action_in_component(self, uc: UseCaseSpec, action_ref: str) -> bool:
        """Check if action is used by a component required by this UC."""
        for req in uc.requires:
            ref = req.ref if hasattr(req, "ref") else req.get("$ref", "")
            comp = self.registry.resolve_ref(ref)
            if comp and hasattr(comp, "steps"):
                for step in comp.steps:
                    if step.use == action_ref:
                        return True
        return False

    def _uc_uses_action(self, uc: UseCaseSpec, action_ref: str) -> bool:
        for step in uc.steps:
            if step.use == action_ref:
                return True
        return self._action_in_component(uc, action_ref)
