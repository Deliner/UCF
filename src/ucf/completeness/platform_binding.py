"""Platform Binding Completeness — HTTP/UI contracts imply required scenarios.

@implements("actions/analyze-platform-completeness")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.models.action import ActionSpec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding, FindingCategory, FindingSeverity


@dataclass
class PlatformScenario:
    action_name: str
    scenario: str
    description: str
    covered_by: list[str] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        return len(self.covered_by) > 0


class PlatformBindingAnalyzer:
    """For actions with platform bindings, check that implied scenarios are covered."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> tuple[list[PlatformScenario], list[Finding]]:
        scenarios: list[PlatformScenario] = []
        findings: list[Finding] = []

        action_to_ucs = self._build_action_uc_map()

        for action in self.registry.actions():
            if not action.platform:
                continue

            action_ref = f"actions/{action.metadata.name}"
            consuming_ucs = action_to_ucs.get(action_ref, [])

            if action.platform.http:
                http_scenarios = self._derive_http_scenarios(action)
                for scenario in http_scenarios:
                    for uc in consuming_ucs:
                        if self._scenario_covered(uc, scenario):
                            scenario.covered_by.append(uc.metadata.name)
                    scenarios.append(scenario)

            if action.platform.ui:
                ui_scenarios = self._derive_ui_scenarios(action)
                for scenario in ui_scenarios:
                    for uc in consuming_ucs:
                        if self._scenario_covered(uc, scenario):
                            scenario.covered_by.append(uc.metadata.name)
                    scenarios.append(scenario)

        for s in scenarios:
            if not s.is_covered:
                findings.append(Finding(
                    severity=FindingSeverity.INFO,
                    category=FindingCategory.UNCOVERED_HTTP_SCENARIO,
                    step_id=f"actions/{s.action_name}",
                    message=(
                        f"Platform scenario '{s.scenario}' ({s.description}) "
                        f"is not covered by any use case"
                    ),
                    suggestion=(
                        f"Add a use case or alternative flow that exercises "
                        f"the '{s.scenario}' scenario for this action"
                    ),
                ))

        return scenarios, findings

    def _build_action_uc_map(self) -> dict[str, list[UseCaseSpec]]:
        result: dict[str, list[UseCaseSpec]] = {}
        for uc in self.registry.usecases():
            for step in uc.steps:
                result.setdefault(step.use, []).append(uc)
        return result

    def _derive_http_scenarios(self, action: ActionSpec) -> list[PlatformScenario]:
        name = action.metadata.name
        scenarios = [
            PlatformScenario(
                action_name=name,
                scenario="http_success",
                description=f"HTTP {action.platform.http.method} {action.platform.http.path} returns 2xx",
            ),
        ]

        for error in action.errors:
            scenarios.append(PlatformScenario(
                action_name=name,
                scenario=f"http_error_{error.status}",
                description=f"HTTP returns {error.status} ({error.code})",
            ))

        if action.reads:
            scenarios.append(PlatformScenario(
                action_name=name,
                scenario="http_resource_not_found",
                description="Referenced resource does not exist",
            ))

        return scenarios

    def _derive_ui_scenarios(self, action: ActionSpec) -> list[PlatformScenario]:
        name = action.metadata.name
        scenarios = [
            PlatformScenario(
                action_name=name,
                scenario="ui_happy_path",
                description="UI interaction completes successfully",
            ),
        ]
        return scenarios

    def _scenario_covered(self, uc: UseCaseSpec, scenario: PlatformScenario) -> bool:
        action_ref = f"actions/{scenario.action_name}"

        if scenario.scenario in ("http_success", "ui_happy_path"):
            for step in uc.steps:
                if step.use == action_ref:
                    return True

        if scenario.scenario.startswith("http_error_"):
            status = scenario.scenario.replace("http_error_", "")
            error_codes = self._error_codes_for_status(scenario.action_name, status)
            for alt in uc.alternative_flows:
                trigger_lower = alt.trigger.lower()
                if status in trigger_lower:
                    return True
                if alt.handles_error and alt.handles_error in error_codes:
                    return True
                if "not found" in trigger_lower or "not exist" in trigger_lower:
                    if status == "404":
                        return True

        if scenario.scenario == "http_resource_not_found":
            for alt in uc.alternative_flows:
                trigger_lower = alt.trigger.lower()
                if "not found" in trigger_lower or "not exist" in trigger_lower:
                    return True
                if alt.handles_error:
                    error_codes = self._error_codes_for_status(scenario.action_name, "404")
                    if alt.handles_error in error_codes:
                        return True

        return False

    def _error_codes_for_status(self, action_name: str, status: str) -> set[str]:
        """Get error codes for a given HTTP status from the action spec."""
        action = self.registry.resolve_ref(f"actions/{action_name}")
        if not isinstance(action, ActionSpec):
            return set()
        return {e.code for e in action.errors if str(e.status) == status}
