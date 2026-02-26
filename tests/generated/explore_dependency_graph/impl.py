"""Implementation for use case: explore-dependency-graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.web.app import create_app

from .interface import (
    BuildJsonResult,
    ExploreDependencyGraphInterface,
    Graph_builderContext,
    LoaderContext,
)

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class ExploreDependencyGraphImpl(ExploreDependencyGraphInterface):

    def setup_loader(self) -> LoaderContext:
        self._app = create_app(SPECS_DIR)
        transport = ASGITransport(app=self._app)
        self._client = AsyncClient(transport=transport, base_url="http://test")
        return LoaderContext(registry=self._app, loaded_count=1, load_errors=[])

    def setup_graph_builder(self) -> Graph_builderContext:
        return Graph_builderContext(graph=None, node_count=0, edge_count=0)

    def action_build_json(self, registry: Any, graph: Any) -> BuildJsonResult:
        import asyncio

        async def _get():
            resp = await self._client.get("/api/graph")
            assert resp.status_code == 200
            return resp.json()

        data = asyncio.run(_get())
        self._graph_data = data
        return BuildJsonResult(
            nodes=data["nodes"],
            links=data["links"],
            node_count=data["node_count"],
            edge_count=data["edge_count"],
        )

    def action_render_graph(self, data: Any, format: Any) -> None:
        pass

    def verify_developer_sees_all_specs_as_graph_nodes(self) -> None:
        assert self._graph_data["node_count"] > 0
        assert len(self._graph_data["nodes"]) == self._graph_data["node_count"]

    def verify_developer_sees_all_dependency_edges_as_links(self) -> None:
        assert len(self._graph_data["links"]) == self._graph_data["edge_count"]

    def verify_nodes_carry_kind_and_name_metadata(self) -> None:
        for node in self._graph_data["nodes"]:
            assert "kind" in node
            assert "name" in node
            assert node["kind"] in ("action", "usecase", "component", "event", "protocol", "invariant")

    def verify_links_reference_valid_node_identifiers(self) -> None:
        node_ids = {n["id"] for n in self._graph_data["nodes"]}
        for link in self._graph_data["links"]:
            assert link["source"] in node_ids, f"source {link['source']} not in nodes"
            assert link["target"] in node_ids, f"target {link['target']} not in nodes"

    def verify_graph_acyclic(self) -> None:
        import networkx as nx

        g = nx.DiGraph()
        node_ids = {n["id"] for n in self._graph_data["nodes"]}
        g.add_nodes_from(node_ids)
        for link in self._graph_data["links"]:
            g.add_edge(link["source"], link["target"])
        assert nx.is_directed_acyclic_graph(g), "Dependency graph must be acyclic"

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def explore_dependency_graph_impl() -> ExploreDependencyGraphImpl:
    return ExploreDependencyGraphImpl()
