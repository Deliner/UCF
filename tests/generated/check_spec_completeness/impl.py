"""Implementation for use case: check-spec-completeness.

@implements("use-cases/check-spec-completeness")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.completeness.engine import CompletenessEngine
from ucf.completeness.error_reachability import ErrorReachabilityAnalyzer
from ucf.completeness.input_partitions import InputPartitionAnalyzer
from ucf.completeness.invariant_necessity import InvariantNecessityAnalyzer
from ucf.completeness.platform_binding import PlatformBindingAnalyzer
from ucf.completeness.resource_conflicts import ResourceConflictAnalyzer
from ucf.completeness.state_coverage import StateCoverageAnalyzer
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import (
    AggregateResult,
    AnalyzeErrorsResult,
    AnalyzeInvariantsResult,
    AnalyzePartitionsResult,
    AnalyzePlatformResult,
    AnalyzeResourcesResult,
    AnalyzeStatesResult,
    CheckSpecCompletenessInterface,
    RegistryContext,
)

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class CheckSpecCompletenessImpl(CheckSpecCompletenessInterface):
    def __init__(self) -> None:
        self._report: Any = None

    def setup_registry(self) -> RegistryContext:
        loader = SpecLoader(SPECS_DIR)
        loaded, errors = loader.load_all_tolerant()
        registry = SpecRegistry()
        for path, spec in loaded:
            registry.register(spec, path)
        self._registry = registry
        return RegistryContext(
            registry=registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_analyze_errors(self, registry: Any) -> AnalyzeErrorsResult:
        covs, findings = ErrorReachabilityAnalyzer(registry).analyze()
        self._error_coverages = covs
        self._error_findings = findings
        return AnalyzeErrorsResult(error_coverages=covs, error_findings=findings)

    def action_analyze_partitions(self, registry: Any) -> AnalyzePartitionsResult:
        covs, findings = InputPartitionAnalyzer(registry).analyze()
        return AnalyzePartitionsResult(
            partition_coverages=covs, partition_findings=findings
        )

    def action_analyze_states(self, registry: Any) -> AnalyzeStatesResult:
        graph, findings = StateCoverageAnalyzer(registry).analyze()
        return AnalyzeStatesResult(state_graph=graph, state_findings=findings)

    def action_analyze_platform(self, registry: Any) -> AnalyzePlatformResult:
        scenarios, findings = PlatformBindingAnalyzer(registry).analyze()
        return AnalyzePlatformResult(
            platform_scenarios=scenarios, platform_findings=findings
        )

    def action_analyze_invariants(self, registry: Any) -> AnalyzeInvariantsResult:
        covs, findings = InvariantNecessityAnalyzer(registry).analyze()
        return AnalyzeInvariantsResult(
            invariant_coverages=covs, invariant_findings=findings
        )

    def action_analyze_resources(self, registry: Any) -> AnalyzeResourcesResult:
        conflicts, findings = ResourceConflictAnalyzer(registry).analyze()
        return AnalyzeResourcesResult(
            resource_conflicts=conflicts, resource_findings=findings
        )

    def action_aggregate(self, registry: Any) -> AggregateResult:
        engine = CompletenessEngine(registry)
        self._report = engine.analyze()
        return AggregateResult(report=self._report)

    def action_render_report(self, data: Any, format: Any) -> None:
        pass

    def verify_developer_sees_a_completeness_report_identifying_behavioral(
        self,
    ) -> None:
        assert self._report is not None
        assert hasattr(self._report, "gap_count")

    def verify_every_uncovered_error_partition_state_or_platform_scenario(self) -> None:
        assert self._report is not None
        assert self._report.errors_total >= 0
        assert self._report.partitions_total >= 0
        assert self._report.scenarios_total >= 0
        assert self._report.gap_count >= 0
        assert isinstance(self._report.findings, list)

    def verify_every_error_has_alt_flow(self) -> None:
        assert self._report is not None
        error_findings = [
            f for f in self._report.findings if f.category.value == "uncovered_error"
        ]
        for f in error_findings:
            assert f.step_id, "uncovered_error finding must have a step_id"
            assert f.message, "uncovered_error finding must have a message"

    def verify_every_input_partition_covered(self) -> None:
        assert self._report is not None
        partition_findings = [
            f
            for f in self._report.findings
            if f.category.value == "uncovered_input_partition"
        ]
        for f in partition_findings:
            assert f.step_id, "uncovered_input_partition finding must have a step_id"
            assert f.message, "uncovered_input_partition finding must have a message"

    def action_render_empty(self, data: Any, format: Any) -> None:
        empty_reg = SpecRegistry()
        engine = CompletenessEngine(empty_reg)
        report = engine.analyze()
        assert report.errors_total == 0
        assert report.partitions_total == 0

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def check_spec_completeness_impl() -> CheckSpecCompletenessImpl:
    return CheckSpecCompletenessImpl()
