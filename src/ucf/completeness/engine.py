"""Completeness Engine — orchestrates all completeness analyzers.

@implements("actions/check-spec-completeness")
@implements("use-cases/check-spec-completeness")
@implements("invariants/every-error-has-alt-flow")
@implements("invariants/every-input-partition-covered")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.completeness.error_reachability import ErrorCoverage, ErrorReachabilityAnalyzer
from ucf.completeness.input_partitions import InputPartitionAnalyzer, PartitionCoverage
from ucf.completeness.invariant_necessity import (
    InvariantCoverage,
    InvariantNecessityAnalyzer,
)
from ucf.completeness.platform_binding import PlatformBindingAnalyzer, PlatformScenario
from ucf.completeness.resource_conflicts import (
    ResourceConflict,
    ResourceConflictAnalyzer,
)
from ucf.completeness.state_coverage import StateCoverageAnalyzer, StateGraph
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding


@dataclass
class CompletenessReport:
    error_coverages: list[ErrorCoverage] = field(default_factory=list)
    partition_coverages: list[PartitionCoverage] = field(default_factory=list)
    state_graph: StateGraph | None = None
    platform_scenarios: list[PlatformScenario] = field(default_factory=list)
    invariant_coverages: list[InvariantCoverage] = field(default_factory=list)
    resource_conflicts: list[ResourceConflict] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def gap_count(self) -> int:
        return len(self.findings)

    @property
    def errors_covered(self) -> int:
        return sum(1 for e in self.error_coverages if e.is_covered)

    @property
    def errors_total(self) -> int:
        return len(self.error_coverages)

    @property
    def partitions_covered(self) -> int:
        return sum(1 for p in self.partition_coverages if p.is_covered)

    @property
    def partitions_total(self) -> int:
        return len(self.partition_coverages)

    @property
    def scenarios_covered(self) -> int:
        return sum(1 for s in self.platform_scenarios if s.is_covered)

    @property
    def scenarios_total(self) -> int:
        return len(self.platform_scenarios)

    @property
    def invariants_testable(self) -> int:
        return sum(1 for i in self.invariant_coverages if i.is_testable)

    @property
    def invariants_total(self) -> int:
        return len(self.invariant_coverages)


class CompletenessEngine:
    """Runs all completeness analyzers and produces a unified report."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> CompletenessReport:
        report = CompletenessReport()

        error_covs, error_findings = ErrorReachabilityAnalyzer(self.registry).analyze()
        report.error_coverages = error_covs
        report.findings.extend(error_findings)

        part_covs, part_findings = InputPartitionAnalyzer(self.registry).analyze()
        report.partition_coverages = part_covs
        report.findings.extend(part_findings)

        state_graph, state_findings = StateCoverageAnalyzer(self.registry).analyze()
        report.state_graph = state_graph
        report.findings.extend(state_findings)

        plat_scenarios, plat_findings = PlatformBindingAnalyzer(self.registry).analyze()
        report.platform_scenarios = plat_scenarios
        report.findings.extend(plat_findings)

        inv_covs, inv_findings = InvariantNecessityAnalyzer(self.registry).analyze()
        report.invariant_coverages = inv_covs
        report.findings.extend(inv_findings)

        res_conflicts, res_findings = ResourceConflictAnalyzer(self.registry).analyze()
        report.resource_conflicts = res_conflicts
        report.findings.extend(res_findings)

        return report
