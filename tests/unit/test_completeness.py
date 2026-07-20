"""Unit tests for the spec completeness analysis module."""

from __future__ import annotations

from ucf.models.action import ActionSpec, HttpBinding, Platform
from ucf.models.base import (
    ErrorDef,
    FieldDef,
    FieldType,
    Metadata,
    ResourceWrite,
)
from ucf.models.component import StepDef
from ucf.models.invariant import AppliesTo, InvariantSpec, InvariantType
from ucf.models.usecase import AlternativeFlow, ConcurrencyDef, UseCaseSpec
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import FindingCategory


def _action(
    name: str,
    errors: list[dict] | None = None,
    inputs: dict | None = None,
    platform: Platform | None = None,
    writes: list[dict] | None = None,
    reads: list[dict] | None = None,
) -> ActionSpec:
    return ActionSpec(
        metadata=Metadata(name=name, version="0.1.0"),
        errors=[ErrorDef(**e) for e in (errors or [])],
        input={k: FieldDef(**v) for k, v in (inputs or {}).items()},
        platform=platform,
        writes=[ResourceWrite(**w) for w in (writes or [])],
        reads=[
            {"resource": r["resource"], "fields": r.get("fields", [])}
            for r in (reads or [])
        ],
    )


def _uc(
    name: str,
    steps: list[dict] | None = None,
    alt_flows: list[dict] | None = None,
    preconditions: list[str] | None = None,
    postconditions: list[str] | None = None,
    invariants: list[dict] | None = None,
    concurrency: list[dict] | None = None,
) -> UseCaseSpec:
    alts = []
    for af in alt_flows or []:
        alts.append(
            AlternativeFlow(
                name=af["name"],
                trigger=af["trigger"],
                handles_error=af.get("handles_error"),
                steps=[StepDef(**s) for s in af.get("steps", [])],
            )
        )
    return UseCaseSpec(
        metadata=Metadata(name=name, version="0.1.0"),
        steps=[StepDef(**s) for s in (steps or [])],
        alternative_flows=alts,
        preconditions=preconditions or [],
        postconditions=postconditions or [],
        invariants=[{"$ref": r["$ref"]} for r in (invariants or [])],
        concurrency=[ConcurrencyDef(**c) for c in (concurrency or [])],
    )


def _invariant(
    name: str,
    rule: str = "some rule",
    inv_type: InvariantType = InvariantType.RELATIONSHIP,
    applies_to: list[dict] | None = None,
) -> InvariantSpec:
    return InvariantSpec(
        metadata=Metadata(name=name, version="0.1.0"),
        type=inv_type,
        rule=rule,
        applies_to=[AppliesTo(**a) for a in (applies_to or [])],
    )


# ── Error Reachability ────────────────────────────────────────


class TestErrorReachability:
    def test_covered_by_handles_error(self):
        from ucf.completeness.error_reachability import ErrorReachabilityAnalyzer

        reg = SpecRegistry()
        action = _action(
            "get-item",
            errors=[
                {
                    "status": 404,
                    "code": "ITEM_NOT_FOUND",
                    "condition": "item does not exist",
                },
            ],
        )
        uc = _uc(
            "fetch-item",
            steps=[
                {"id": "s1", "use": "actions/get-item", "input": {}},
            ],
            alt_flows=[
                {
                    "name": "not-found",
                    "trigger": "item missing",
                    "handles_error": "ITEM_NOT_FOUND",
                },
            ],
        )
        reg.register(action)
        reg.register(uc)

        covs, findings = ErrorReachabilityAnalyzer(reg).analyze()
        assert len(covs) == 1
        assert covs[0].is_covered
        assert len(findings) == 0

    def test_covered_by_name_match(self):
        from ucf.completeness.error_reachability import ErrorReachabilityAnalyzer

        reg = SpecRegistry()
        action = _action(
            "get-item",
            errors=[
                {
                    "status": 404,
                    "code": "ITEM_NOT_FOUND",
                    "condition": "item does not exist",
                },
            ],
        )
        uc = _uc(
            "fetch-item",
            steps=[
                {"id": "s1", "use": "actions/get-item", "input": {}},
            ],
            alt_flows=[
                {"name": "item-not-found", "trigger": "the item was not found"},
            ],
        )
        reg.register(action)
        reg.register(uc)

        covs, findings = ErrorReachabilityAnalyzer(reg).analyze()
        assert covs[0].is_covered

    def test_uncovered_error_produces_finding(self):
        from ucf.completeness.error_reachability import ErrorReachabilityAnalyzer

        reg = SpecRegistry()
        action = _action(
            "get-item",
            errors=[
                {
                    "status": 404,
                    "code": "ITEM_NOT_FOUND",
                    "condition": "item does not exist",
                },
            ],
        )
        uc = _uc(
            "fetch-item",
            steps=[
                {"id": "s1", "use": "actions/get-item", "input": {}},
            ],
        )
        reg.register(action)
        reg.register(uc)

        covs, findings = ErrorReachabilityAnalyzer(reg).analyze()
        assert not covs[0].is_covered
        assert len(findings) == 1
        assert findings[0].category == FindingCategory.UNCOVERED_ERROR

    def test_action_not_in_any_uc(self):
        from ucf.completeness.error_reachability import ErrorReachabilityAnalyzer

        reg = SpecRegistry()
        action = _action(
            "orphan-action",
            errors=[
                {"status": 500, "code": "INTERNAL", "condition": "unexpected"},
            ],
        )
        reg.register(action)

        covs, findings = ErrorReachabilityAnalyzer(reg).analyze()
        assert len(covs) == 1
        assert not covs[0].is_covered
        assert len(findings) == 1

    def test_no_errors_produces_no_coverages(self):
        from ucf.completeness.error_reachability import ErrorReachabilityAnalyzer

        reg = SpecRegistry()
        action = _action("simple-action")
        reg.register(action)

        covs, findings = ErrorReachabilityAnalyzer(reg).analyze()
        assert len(covs) == 0
        assert len(findings) == 0


# ── Input Partition Coverage ──────────────────────────────────


class TestInputPartitions:
    def test_derive_string_partitions(self):
        from ucf.completeness.input_partitions import derive_partitions

        fd = FieldDef(type=FieldType.STRING, required=True)
        parts = derive_partitions("name", fd)
        names = [p.name for p in parts]
        assert "valid_present" in names
        assert "empty_string" in names
        assert "absent" not in names

    def test_derive_optional_partition(self):
        from ucf.completeness.input_partitions import derive_partitions

        fd = FieldDef(type=FieldType.STRING, required=False)
        parts = derive_partitions("filter", fd)
        names = [p.name for p in parts]
        assert "absent" in names

    def test_derive_integer_range_partitions(self):
        from ucf.completeness.input_partitions import derive_partitions

        fd = FieldDef(type=FieldType.INTEGER, required=True, min=1, max=100)
        parts = derive_partitions("count", fd)
        names = [p.name for p in parts]
        assert "below_min" in names
        assert "above_max" in names

    def test_derive_enum_partitions(self):
        from ucf.completeness.input_partitions import derive_partitions

        fd = FieldDef(type=FieldType.STRING, required=True, enum=["a", "b", "c"])
        parts = derive_partitions("kind", fd)
        names = [p.name for p in parts]
        assert "enum_a" in names
        assert "enum_b" in names
        assert "enum_c" in names
        assert "invalid_enum" in names

    def test_derive_boolean_partitions(self):
        from ucf.completeness.input_partitions import derive_partitions

        fd = FieldDef(type=FieldType.BOOLEAN, required=True)
        parts = derive_partitions("active", fd)
        names = [p.name for p in parts]
        assert "true" in names
        assert "false" in names

    def test_valid_present_covered_by_step_input(self):
        from ucf.completeness.input_partitions import InputPartitionAnalyzer

        reg = SpecRegistry()
        action = _action(
            "search", inputs={"query": {"type": "string", "required": True}}
        )
        uc = _uc(
            "do-search",
            steps=[
                {"id": "s1", "use": "actions/search", "input": {"query": "test"}},
            ],
        )
        reg.register(action)
        reg.register(uc)

        covs, findings = InputPartitionAnalyzer(reg).analyze()
        valid_present = [c for c in covs if c.partition.name == "valid_present"]
        assert len(valid_present) == 1
        assert valid_present[0].is_covered

    def test_uncovered_partition_produces_finding(self):
        from ucf.completeness.input_partitions import InputPartitionAnalyzer

        reg = SpecRegistry()
        action = _action(
            "search", inputs={"query": {"type": "string", "required": True}}
        )
        reg.register(action)

        covs, findings = InputPartitionAnalyzer(reg).analyze()
        uncovered = [
            f
            for f in findings
            if f.category == FindingCategory.UNCOVERED_INPUT_PARTITION
        ]
        assert len(uncovered) > 0


# ── State Coverage ────────────────────────────────────────────


class TestStateCoverage:
    def test_initial_to_state(self):
        from ucf.completeness.state_coverage import StateCoverageAnalyzer

        reg = SpecRegistry()
        uc = _uc(
            "setup",
            steps=[
                {"id": "s1", "use": "actions/init", "input": {}},
            ],
            postconditions=["system initialized"],
        )
        reg.register(uc)

        graph, findings = StateCoverageAnalyzer(reg).analyze()
        assert len(graph.states) >= 2
        assert len(graph.transitions) >= 1

    def test_unreachable_state(self):
        from ucf.completeness.state_coverage import StateCoverageAnalyzer

        reg = SpecRegistry()
        uc = _uc(
            "needs-setup",
            steps=[
                {"id": "s1", "use": "actions/run", "input": {}},
            ],
            preconditions=["admin logged in"],
            postconditions=["report generated"],
        )
        reg.register(uc)

        graph, findings = StateCoverageAnalyzer(reg).analyze()
        orphan_findings = [
            f for f in findings if f.category == FindingCategory.UNREACHABLE_STATE
        ]
        assert len(orphan_findings) >= 1

    def test_connected_states_no_unreachable(self):
        from ucf.completeness.state_coverage import StateCoverageAnalyzer

        reg = SpecRegistry()
        uc1 = _uc(
            "step-one",
            steps=[
                {"id": "s1", "use": "actions/a", "input": {}},
            ],
            postconditions=["step one complete"],
        )
        uc2 = _uc(
            "step-two",
            steps=[
                {"id": "s2", "use": "actions/b", "input": {}},
            ],
            preconditions=["step one complete"],
            postconditions=["step two complete"],
        )
        reg.register(uc1)
        reg.register(uc2)

        graph, findings = StateCoverageAnalyzer(reg).analyze()
        unreachable = [
            f for f in findings if f.category == FindingCategory.UNREACHABLE_STATE
        ]
        assert len(unreachable) == 0

    def test_dead_end_state(self):
        from ucf.completeness.state_coverage import StateCoverageAnalyzer

        reg = SpecRegistry()
        uc = _uc(
            "terminal",
            steps=[
                {"id": "s1", "use": "actions/done", "input": {}},
            ],
            postconditions=["all done"],
        )
        reg.register(uc)

        graph, findings = StateCoverageAnalyzer(reg).analyze()
        dead_ends = [
            f for f in findings if f.category == FindingCategory.DEAD_END_STATE
        ]
        assert len(dead_ends) >= 1


# ── Platform Binding Completeness ─────────────────────────────


class TestPlatformBinding:
    def test_http_success_covered(self):
        from ucf.completeness.platform_binding import PlatformBindingAnalyzer

        reg = SpecRegistry()
        action = _action(
            "get-items",
            platform=Platform(
                http=HttpBinding(method="GET", path="/items"),
            ),
        )
        uc = _uc(
            "browse",
            steps=[
                {"id": "s1", "use": "actions/get-items", "input": {}},
            ],
        )
        reg.register(action)
        reg.register(uc)

        scenarios, findings = PlatformBindingAnalyzer(reg).analyze()
        http_success = [s for s in scenarios if s.scenario == "http_success"]
        assert len(http_success) == 1
        assert http_success[0].is_covered

    def test_http_error_uncovered(self):
        from ucf.completeness.platform_binding import PlatformBindingAnalyzer

        reg = SpecRegistry()
        action = _action(
            "get-items",
            platform=Platform(
                http=HttpBinding(method="GET", path="/items"),
            ),
            errors=[
                {"status": 404, "code": "NOT_FOUND", "condition": "resource missing"},
            ],
        )
        uc = _uc(
            "browse",
            steps=[
                {"id": "s1", "use": "actions/get-items", "input": {}},
            ],
        )
        reg.register(action)
        reg.register(uc)

        scenarios, findings = PlatformBindingAnalyzer(reg).analyze()
        error_scenarios = [s for s in scenarios if s.scenario == "http_error_404"]
        assert len(error_scenarios) == 1
        assert not error_scenarios[0].is_covered

    def test_no_platform_no_scenarios(self):
        from ucf.completeness.platform_binding import PlatformBindingAnalyzer

        reg = SpecRegistry()
        action = _action("compute")
        reg.register(action)

        scenarios, findings = PlatformBindingAnalyzer(reg).analyze()
        assert len(scenarios) == 0


# ── Invariant Necessity ───────────────────────────────────────


class TestInvariantNecessity:
    def test_invariant_with_exercising_uc(self):
        from ucf.completeness.invariant_necessity import InvariantNecessityAnalyzer

        reg = SpecRegistry()
        inv = _invariant("no-dupes", applies_to=[{"action": "actions/create-item"}])
        action = _action("create-item")
        uc = _uc(
            "add-item",
            steps=[
                {"id": "s1", "use": "actions/create-item", "input": {}},
            ],
        )
        reg.register(inv)
        reg.register(action)
        reg.register(uc)

        covs, findings = InvariantNecessityAnalyzer(reg).analyze()
        assert covs[0].is_testable
        assert len(findings) == 0

    def test_invariant_without_exercising_uc(self):
        from ucf.completeness.invariant_necessity import InvariantNecessityAnalyzer

        reg = SpecRegistry()
        inv = _invariant("no-dupes", applies_to=[{"action": "actions/delete-item"}])
        reg.register(inv)

        covs, findings = InvariantNecessityAnalyzer(reg).analyze()
        assert not covs[0].is_testable
        assert len(findings) == 1
        assert findings[0].category == FindingCategory.UNTESTABLE_INVARIANT

    def test_invariant_referenced_directly_by_uc(self):
        from ucf.completeness.invariant_necessity import InvariantNecessityAnalyzer

        reg = SpecRegistry()
        inv = _invariant("my-rule")
        uc = _uc(
            "some-uc",
            steps=[
                {"id": "s1", "use": "actions/x", "input": {}},
            ],
            invariants=[{"$ref": "invariants/my-rule"}],
        )
        reg.register(inv)
        reg.register(uc)

        covs, findings = InvariantNecessityAnalyzer(reg).analyze()
        assert covs[0].is_testable


# ── Resource Conflict Coverage ────────────────────────────────


class TestResourceConflicts:
    def test_shared_resource_unguarded(self):
        from ucf.completeness.resource_conflicts import ResourceConflictAnalyzer

        reg = SpecRegistry()
        a1 = _action("writer-a", writes=[{"resource": "orders", "mutation": "create"}])
        a2 = _action(
            "writer-b",
            writes=[{"resource": "orders", "mutation": "set", "by": "status"}],
        )
        reg.register(a1)
        reg.register(a2)

        conflicts, findings = ResourceConflictAnalyzer(reg).analyze()
        assert len(conflicts) == 1
        assert not conflicts[0].is_guarded
        assert findings[0].category == FindingCategory.UNGUARDED_RESOURCE_CONFLICT

    def test_shared_resource_with_invariant(self):
        from ucf.completeness.resource_conflicts import ResourceConflictAnalyzer

        reg = SpecRegistry()
        a1 = _action("writer-a", writes=[{"resource": "orders", "mutation": "create"}])
        a2 = _action(
            "writer-b",
            writes=[{"resource": "orders", "mutation": "set", "by": "status"}],
        )
        inv = _invariant("order-guard", applies_to=[{"resource": "orders"}])
        reg.register(a1)
        reg.register(a2)
        reg.register(inv)

        conflicts, findings = ResourceConflictAnalyzer(reg).analyze()
        assert conflicts[0].is_guarded
        assert len(findings) == 0

    def test_shared_resource_with_concurrency_policy(self):
        from ucf.completeness.resource_conflicts import ResourceConflictAnalyzer

        reg = SpecRegistry()
        a1 = _action("writer-a", writes=[{"resource": "orders", "mutation": "create"}])
        a2 = _action(
            "writer-b",
            writes=[{"resource": "orders", "mutation": "set", "by": "status"}],
        )
        uc = _uc(
            "process-order",
            concurrency=[
                {"conflict": "orders", "strategy": "optimistic-lock"},
            ],
        )
        reg.register(a1)
        reg.register(a2)
        reg.register(uc)

        conflicts, findings = ResourceConflictAnalyzer(reg).analyze()
        assert conflicts[0].is_guarded

    def test_single_writer_no_conflict(self):
        from ucf.completeness.resource_conflicts import ResourceConflictAnalyzer

        reg = SpecRegistry()
        a1 = _action("sole-writer", writes=[{"resource": "logs", "mutation": "append"}])
        reg.register(a1)

        conflicts, findings = ResourceConflictAnalyzer(reg).analyze()
        assert len(conflicts) == 0


# ── Completeness Engine ───────────────────────────────────────


class TestCompletenessEngine:
    def test_full_analysis(self):
        from ucf.completeness.engine import CompletenessEngine

        reg = SpecRegistry()
        action = _action(
            "get-item",
            errors=[
                {"status": 404, "code": "NOT_FOUND", "condition": "item missing"},
            ],
            inputs={"id": {"type": "string", "required": True}},
        )
        uc = _uc(
            "fetch",
            steps=[
                {"id": "s1", "use": "actions/get-item", "input": {"id": "123"}},
            ],
            postconditions=["item retrieved"],
        )
        reg.register(action)
        reg.register(uc)

        engine = CompletenessEngine(reg)
        report = engine.analyze()

        assert report.errors_total >= 1
        assert report.partitions_total >= 1
        assert report.state_graph is not None
        assert report.gap_count >= 0

    def test_empty_registry(self):
        from ucf.completeness.engine import CompletenessEngine

        reg = SpecRegistry()
        engine = CompletenessEngine(reg)
        report = engine.analyze()

        assert report.gap_count == 0
        assert report.errors_total == 0
        assert report.partitions_total == 0
