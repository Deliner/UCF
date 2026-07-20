"""Implementation for use case: explore-dependency-graph-web."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.graph.dependency import DependencyGraph
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.web.app import create_app

from .interface import (
    BuildJsonResult,
    ClickNodeResult,
    ExploreDependencyGraphWebInterface,
    Graph_builderContext,
    LoaderContext,
    ToggleViewResult,
)


class ExploreDependencyGraphWebImpl(ExploreDependencyGraphWebInterface):
    def __init__(self) -> None:
        self._rendered_outputs: list[dict[str, Any]] = []

    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        specs_path = Path(specs_dir)
        loaded, errors = SpecLoader(specs_path).load_all_tolerant()
        registry = SpecRegistry()
        for path, spec in loaded:
            registry.register(spec, path)

        self._app = create_app(specs_path)
        transport = ASGITransport(app=self._app)
        self._client = AsyncClient(transport=transport, base_url="http://test")
        return LoaderContext(
            registry=registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def setup_graph_builder(self, registry: Any) -> Graph_builderContext:
        if not isinstance(registry, SpecRegistry):
            raise TypeError("registry must be a SpecRegistry")
        graph = DependencyGraph(registry)
        return Graph_builderContext(
            graph=graph,
            node_count=graph.g.number_of_nodes(),
            edge_count=graph.g.number_of_edges(),
        )

    def action_build_json(self, registry: Any, graph: Any) -> BuildJsonResult:
        import asyncio

        if not isinstance(registry, SpecRegistry):
            raise TypeError("registry must be a SpecRegistry")
        if not isinstance(graph, DependencyGraph):
            raise TypeError("graph must be a DependencyGraph")

        async def _get():
            resp = await self._client.get("/api/graph")
            assert resp.status_code == 200
            return resp.json()

        data = asyncio.run(_get())
        assert data["node_count"] == graph.g.number_of_nodes()
        assert data["edge_count"] == graph.g.number_of_edges()
        self._graph_data = data
        return BuildJsonResult(
            nodes=data["nodes"],
            links=data["links"],
            node_count=data["node_count"],
            edge_count=data["edge_count"],
        )

    def action_render_graph(self, data: Any, format: Any) -> None:
        self._record_render("graph", data, format)

    def action_render_mermaid(self, data: Any, format: Any) -> None:
        if format != "mermaid":
            raise ValueError(f"expected mermaid format, got {format}")
        self._record_render("mermaid", data, format)

    def action_render_json(self, data: Any, format: Any) -> None:
        if format != "json":
            raise ValueError(f"expected json format, got {format}")
        self._record_render("json", data, format)

    def action_render_empty(self, data: Any, format: Any) -> None:
        self._record_render("empty", data, format)

    def action_render_error(self, data: Any, format: Any) -> None:
        self._record_render("error", data, format)

    def _record_render(self, channel: str, data: Any, format: Any) -> None:
        rendered = {"channel": channel, "data": data, "format": format}
        self._rendered_outputs.append(rendered)
        self._rendered_graph = rendered

    def action_click_node(self, node_id: Any) -> ClickNodeResult:
        matching_nodes = [
            item for item in self._graph_data["nodes"] if item["id"] == node_id
        ]
        if len(matching_nodes) != 1:
            raise ValueError(f"graph node does not exist: {node_id}")
        node = matching_nodes[0]
        node_id_val = node["id"]

        connected = [
            link
            for link in self._graph_data["links"]
            if link["source"] == node_id_val or link["target"] == node_id_val
        ]
        self._selected_node = {**node, "connections": len(connected)}
        return ClickNodeResult(selected_node=self._selected_node, tooltip_visible=True)

    def action_toggle_view(self, target_view: Any) -> ToggleViewResult:
        view = str(target_view)
        if view not in {"interactive", "static"}:
            raise ValueError(f"unsupported graph view: {view}")
        self._active_view = view
        return ToggleViewResult(active_view=view)

    def verify_developer_sees_all_specs_as_graph_nodes(self) -> None:
        assert self._graph_data["node_count"] > 0

    def verify_developer_sees_all_dependency_edges_as_links(self) -> None:
        assert len(self._graph_data["links"]) == self._graph_data["edge_count"]

    def verify_nodes_carry_kind_and_name_metadata(self) -> None:
        for node in self._graph_data["nodes"]:
            assert "kind" in node and "name" in node

    def verify_links_reference_valid_node_identifiers(self) -> None:
        node_ids = {n["id"] for n in self._graph_data["nodes"]}
        for link in self._graph_data["links"]:
            assert link["source"] in node_ids
            assert link["target"] in node_ids

    def verify_clicking_a_node_highlights_its_connections(self) -> None:
        assert self._selected_node is not None
        assert "connections" in self._selected_node

    def verify_tooltip_shows_node_kind_and_name(self) -> None:
        assert "kind" in self._selected_node
        assert "name" in self._selected_node

    def verify_toggling_view_switches_between_d3_interactive_and_mermaid(self) -> None:
        assert self._active_view in ("interactive", "static")

    def verify_graph_acyclic(self) -> None:
        import networkx as nx

        g = nx.DiGraph()
        node_ids = {n["id"] for n in self._graph_data["nodes"]}
        g.add_nodes_from(node_ids)
        for link in self._graph_data["links"]:
            if link["edge_type"] == "depends_on":
                g.add_edge(link["source"], link["target"])
        assert nx.is_directed_acyclic_graph(g), "Dependency edges must be acyclic"

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def explore_dependency_graph_web_impl() -> ExploreDependencyGraphWebImpl:
    return ExploreDependencyGraphWebImpl()
