"""Error Reachability analyzer — every action error must be handled by some UC alt flow.

@implements("actions/analyze-error-reachability")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding, FindingCategory, FindingSeverity


@dataclass
class ErrorCoverage:
    action_name: str
    error_code: str
    error_condition: str
    covered_by: list[str] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        return len(self.covered_by) > 0


class ErrorReachabilityAnalyzer:
    """For each action error, check that at least one UC alternative_flow handles it."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> tuple[list[ErrorCoverage], list[Finding]]:
        coverages: list[ErrorCoverage] = []
        findings: list[Finding] = []

        action_to_ucs = self._build_action_uc_map()

        for action in self.registry.actions():
            if not action.errors:
                continue

            action_ref = f"actions/{action.metadata.name}"
            consuming_ucs = action_to_ucs.get(action_ref, [])

            for error in action.errors:
                cov = ErrorCoverage(
                    action_name=action.metadata.name,
                    error_code=error.code,
                    error_condition=error.condition,
                )

                for uc in consuming_ucs:
                    for alt in uc.alternative_flows:
                        if self._alt_handles_error(alt, error.code, error.condition):
                            cov.covered_by.append(
                                f"{uc.metadata.name}:{alt.name}"
                            )

                coverages.append(cov)

                if not cov.is_covered:
                    findings.append(Finding(
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.UNCOVERED_ERROR,
                        step_id=f"actions/{action.metadata.name}",
                        message=(
                            f"Error '{error.code}' (condition: {error.condition}) "
                            f"is not handled by any use case alternative flow"
                        ),
                        suggestion=(
                            f"Add an alternative_flow with handles_error: {error.code} "
                            f"to a use case that references this action"
                        ),
                    ))

        return coverages, findings

    def _build_action_uc_map(self) -> dict[str, list[UseCaseSpec]]:
        """Map action refs to all use cases that reference them (directly or via components)."""
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

    @staticmethod
    def _alt_handles_error(alt, error_code: str, error_condition: str) -> bool:
        if alt.handles_error and alt.handles_error == error_code:
            return True

        code_lower = error_code.lower().replace("_", "-")
        if code_lower in alt.name.lower():
            return True
        if code_lower in alt.trigger.lower():
            return True

        condition_words = set(error_condition.lower().split())
        trigger_words = set(alt.trigger.lower().split())
        if len(condition_words) >= 3 and len(condition_words & trigger_words) >= len(condition_words) * 0.6:
            return True

        return False
