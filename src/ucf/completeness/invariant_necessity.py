"""Invariant Necessity analyzer — every invariant should be testable by some UC.

@implements("actions/analyze-invariant-necessity")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.models.invariant import InvariantSpec
from ucf.models.usecase import UseCaseSpec, invariant_reference
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding, FindingCategory, FindingSeverity


@dataclass
class InvariantCoverage:
    invariant_name: str
    applies_to_actions: list[str] = field(default_factory=list)
    exercised_by_ucs: list[str] = field(default_factory=list)

    @property
    def is_testable(self) -> bool:
        return len(self.exercised_by_ucs) > 0


class InvariantNecessityAnalyzer:
    (
        "For each invariant, check that at least one UC exercises the "
        "constrained actions."
    )

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> tuple[list[InvariantCoverage], list[Finding]]:
        coverages: list[InvariantCoverage] = []
        findings: list[Finding] = []

        action_to_ucs = self._build_action_uc_map()

        for inv in self.registry.invariants():
            cov = InvariantCoverage(invariant_name=inv.metadata.name)

            bound_actions = self._get_bound_actions(inv)
            cov.applies_to_actions = bound_actions

            exercising_ucs: set[str] = set()
            for action_ref in bound_actions:
                for uc in action_to_ucs.get(action_ref, []):
                    exercising_ucs.add(uc.metadata.name)

            if not exercising_ucs:
                exercising_ucs = self._find_ucs_referencing_invariant(inv)

            cov.exercised_by_ucs = sorted(exercising_ucs)
            coverages.append(cov)

            if not cov.is_testable:
                findings.append(
                    Finding(
                        severity=FindingSeverity.INFO,
                        category=FindingCategory.UNTESTABLE_INVARIANT,
                        step_id=f"invariants/{inv.metadata.name}",
                        message=(
                            f"Invariant '{inv.metadata.name}' "
                            f"(rule: {inv.rule or 'composite'}) "
                            f"is not exercised by any use case"
                        ),
                        suggestion=(
                            "Either the invariant is unnecessary, or there's a missing "
                            "use case that could violate it"
                        ),
                    )
                )

        return coverages, findings

    def _build_action_uc_map(self) -> dict[str, list[UseCaseSpec]]:
        result: dict[str, list[UseCaseSpec]] = {}
        for uc in self.registry.usecases():
            for step in uc.steps:
                result.setdefault(step.use, []).append(uc)
        return result

    @staticmethod
    def _get_bound_actions(inv: InvariantSpec) -> list[str]:
        actions: list[str] = []
        for binding in inv.applies_to:
            if binding.action:
                ref = binding.action
                if not ref.startswith("actions/"):
                    ref = f"actions/{ref}"
                actions.append(ref)
        return actions

    def _find_ucs_referencing_invariant(self, inv: InvariantSpec) -> set[str]:
        (
            "Check if any UC directly references this invariant "
            "(by $ref or resolved name)."
        )
        inv_ref = f"invariants/{inv.metadata.name}"
        result: set[str] = set()
        for uc in self.registry.usecases():
            for inv_ref_item in uc.invariants:
                if invariant_reference(inv_ref_item) == inv_ref:
                    result.add(uc.metadata.name)
        return result
