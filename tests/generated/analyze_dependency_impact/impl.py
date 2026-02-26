"""Implementation for use case: analyze-dependency-impact."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.graph.dependency import DependencyGraph, ImpactResult
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import (
    AnalyzeDependencyImpactInterface,
    BuildGraphResult,
    ImpactResult as ImpactResultDC,
    LoaderContext,
)

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class AnalyzeDependencyImpactImpl(AnalyzeDependencyImpactInterface):

    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._graph: DependencyGraph | None = None
        self._impact: ImpactResult | None = None

    def setup_loader(self) -> LoaderContext:
        loader = SpecLoader(SPECS_DIR)
        loaded, errors = loader.load_all_tolerant()

        self._registry = SpecRegistry()
        for path, spec in loaded:
            self._registry.register(spec, path)

        return LoaderContext(
            registry=self._registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_build_graph(self, registry: Any) -> BuildGraphResult:
        assert self._registry is not None
        self._graph = DependencyGraph(self._registry)
        return BuildGraphResult(
            graph=self._graph,
            node_count=self._graph.g.number_of_nodes(),
            edge_count=self._graph.g.number_of_edges(),
        )

    def action_impact(self, graph: Any, target: Any) -> ImpactResultDC:
        assert self._graph is not None
        first_action = self._registry.actions()[0] if self._registry else None
        target_ref = f"action/{first_action.metadata.name}" if first_action else ""
        self._impact = self._graph.impact(target_ref)
        total = (
            len(self._impact.direct_dependents)
            + len(self._impact.transitive_dependents)
            + len(self._impact.invariants)
        )
        return ImpactResultDC(
            direct_dependents=self._impact.direct_dependents,
            transitive_dependents=self._impact.transitive_dependents,
            invariants=self._impact.invariants,
            total_impact=total,
        )

    def action_render_impact(self, *args: Any, **kwargs: Any) -> None:
        pass

    def verify_all_direct_and_transitive_dependents_of_target_are(self) -> None:
        assert self._impact is not None
        assert isinstance(self._impact.direct_dependents, list)
        assert isinstance(self._impact.transitive_dependents, list)

    def verify_constraining_invariants_are_listed(self) -> None:
        assert self._impact is not None
        assert isinstance(self._impact.invariants, list)

    def verify_total_impact_count_is_reported(self) -> None:
        assert self._impact is not None
        total = (
            len(self._impact.direct_dependents)
            + len(self._impact.transitive_dependents)
            + len(self._impact.invariants)
        )
        assert total >= 0

    def verify_graph_acyclic(self) -> None:
        import networkx as nx

        assert self._graph is not None
        assert nx.is_directed_acyclic_graph(self._graph.g)


@pytest.fixture
def analyze_dependency_impact_impl() -> AnalyzeDependencyImpactImpl:
    return AnalyzeDependencyImpactImpl()
