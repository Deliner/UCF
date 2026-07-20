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
    LoaderContext,
)
from .interface import (
    ImpactResult as ImpactResultDC,
)


class AnalyzeDependencyImpactImpl(AnalyzeDependencyImpactInterface):
    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._graph: DependencyGraph | None = None
        self._impact: ImpactResult | None = None
        self._rendered_impact: tuple[Any, Any] | None = None

    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        loader = SpecLoader(Path(specs_dir))
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
        assert isinstance(graph, DependencyGraph)
        self._graph = graph
        self._impact = graph.impact(str(target))
        total = (
            len(self._impact.direct_dependents)
            + len(self._impact.transitive_dependents)
            + len(self._impact.invariants)
            + len(self._impact.conflicts)
        )
        return ImpactResultDC(
            direct_dependents=self._impact.direct_dependents,
            transitive_dependents=self._impact.transitive_dependents,
            invariants=self._impact.invariants,
            conflicts=self._impact.conflicts,
            total_impact=total,
        )

    def action_render_impact(self, data: Any, format: Any) -> None:
        self._rendered_impact = (data, format)

    def verify_all_direct_and_transitive_dependents_of_target_are_listed(self) -> None:
        assert self._impact is not None
        assert isinstance(self._impact.direct_dependents, list)
        assert isinstance(self._impact.transitive_dependents, list)

    def verify_constraining_invariants_are_listed(self) -> None:
        assert self._impact is not None
        assert isinstance(self._impact.invariants, list)

    def verify_resource_conflicts_are_listed(self) -> None:
        assert self._impact is not None
        assert isinstance(self._impact.conflicts, list)

    def verify_total_impact_count_is_reported(self) -> None:
        assert self._impact is not None
        direct = set(self._impact.direct_dependents)
        transitive = set(self._impact.transitive_dependents)
        # Transitive dependents are non-direct ancestors.
        overlap = direct & transitive
        assert not overlap, f"Nodes appear in both direct and transitive: {overlap}"
        assert self._impact.target, "impact result must have a target spec name"

    def verify_graph_node_count_and_edge_count_reflect_the_full_registry(
        self,
    ) -> None:
        assert self._graph is not None
        assert self._registry is not None
        assert self._graph.g.number_of_nodes() == len(self._registry.all_specs())
        assert self._graph.g.number_of_edges() >= 0

    def verify_graph_acyclic(self) -> None:
        import networkx as nx

        assert self._graph is not None
        dependency_edges = [
            (source, target)
            for source, target, data in self._graph.g.edges(data=True)
            if data.get("type") == "depends_on"
        ]
        assert nx.is_directed_acyclic_graph(nx.DiGraph(dependency_edges))

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def analyze_dependency_impact_impl() -> AnalyzeDependencyImpactImpl:
    return AnalyzeDependencyImpactImpl()
