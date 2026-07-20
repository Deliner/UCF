"""Unit tests for DependencyGraph."""

from __future__ import annotations

from ucf.graph.dependency import DependencyGraph
from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry

ACTION_A = {
    "kind": "action",
    "metadata": {"name": "action-a"},
    "writes": [{"resource": "orders", "mutation": "create"}],
}

ACTION_B = {
    "kind": "action",
    "metadata": {"name": "action-b"},
    "writes": [{"resource": "orders", "mutation": "set", "by": "status"}],
}

UC_X = {
    "kind": "usecase",
    "metadata": {"name": "flow-x"},
    "steps": [
        {"id": "s1", "use": "actions/action-a", "input": {}, "output": {"id": "id"}},
    ],
    "postconditions": ["done"],
}

UC_Y = {
    "kind": "usecase",
    "metadata": {"name": "flow-y"},
    "steps": [
        {"id": "s1", "use": "actions/action-b", "input": {}, "output": {"ok": "ok"}},
    ],
    "postconditions": ["done"],
}


def _registry() -> SpecRegistry:
    r = SpecRegistry()
    for d in [ACTION_A, ACTION_B, UC_X, UC_Y]:
        r.register(parse_spec(d))
    return r


class TestDependencyGraph:
    def test_build_graph(self):
        reg = _registry()
        g = DependencyGraph(reg)
        assert g.g.number_of_nodes() > 0
        assert g.g.number_of_edges() > 0

    def test_node_ids(self):
        reg = _registry()
        g = DependencyGraph(reg)
        nodes = list(g.g.nodes)
        assert "action/action-a" in nodes
        assert "usecase/flow-x" in nodes

    def test_find_impact(self):
        reg = _registry()
        g = DependencyGraph(reg)
        result = g.impact("action/action-a")
        assert result.target == "action/action-a"

    def test_write_conflicts_between_usecases(self):
        reg = _registry()
        g = DependencyGraph(reg)
        conflicts = g.find_write_conflicts()
        resources = {c[2] for c in conflicts}
        assert "orders" in resources

    def test_mermaid_output(self):
        reg = _registry()
        g = DependencyGraph(reg)
        mermaid = g.to_mermaid()
        assert mermaid.startswith("graph TD")

    def test_empty_registry(self):
        reg = SpecRegistry()
        g = DependencyGraph(reg)
        assert g.g.number_of_nodes() == 0

    def test_alt_flow_writes_included(self):
        uc_with_alt = {
            "kind": "usecase",
            "metadata": {"name": "alt-flow"},
            "steps": [
                {"id": "s1", "use": "actions/action-a", "input": {}, "output": {}},
            ],
            "alternative_flows": [
                {
                    "name": "fallback",
                    "trigger": "error",
                    "steps": [
                        {
                            "id": "s2",
                            "use": "actions/action-b",
                            "input": {},
                            "output": {},
                        },
                    ],
                },
            ],
            "postconditions": ["done"],
        }
        reg = SpecRegistry()
        for d in [ACTION_A, ACTION_B, uc_with_alt]:
            reg.register(parse_spec(d))
        g = DependencyGraph(reg)
        conflicts = g.find_write_conflicts()
        resources = {c[2] for c in conflicts}
        assert "orders" in resources
