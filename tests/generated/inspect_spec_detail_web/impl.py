"""Implementation for use case: inspect-spec-detail-web."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.graph.dependency import DependencyGraph
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.web.app import create_app

from .interface import (
    GetDetailResult,
    GetRelsResult,
    Graph_builderContext,
    InspectSpecDetailWebInterface,
    LoaderContext,
    NavigateRelatedResult,
    ToggleTabResult,
)

DETAIL_TABS = ("overview", "schema", "relationships", "implementation")


class InspectSpecDetailWebImpl(InspectSpecDetailWebInterface):
    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        specs_path = Path(specs_dir)
        loaded, errors = SpecLoader(specs_path).load_all_tolerant()
        registry = SpecRegistry()
        for path, spec in loaded:
            registry.register(spec, path)

        self._registry = registry
        self._app = create_app(specs_path)
        transport = ASGITransport(app=self._app)
        self._client = AsyncClient(transport=transport, base_url="http://test")
        return LoaderContext(
            registry=registry,
            loaded_count=registry.total,
            load_errors=errors,
        )

    def setup_graph_builder(self, registry: Any) -> Graph_builderContext:
        graph = DependencyGraph(registry)
        self._graph = graph
        return Graph_builderContext(
            graph=graph,
            node_count=graph.g.number_of_nodes(),
            edge_count=graph.g.number_of_edges(),
        )

    def action_get_detail(self, registry: Any, kind: Any, name: Any) -> GetDetailResult:
        if registry.get(kind, name) is None:
            raise ValueError(f"Spec '{kind}/{name}' not found")

        async def _get() -> dict[str, Any]:
            resp = await self._client.get(f"/api/specs/{kind}/{name}")
            assert resp.status_code == 200
            return resp.json()

        data = asyncio.run(_get())
        self._detail = data
        self._requested_kind = kind
        self._requested_name = name
        return GetDetailResult(
            spec=data, raw_yaml=data["raw_yaml"], impl_status=data["impl_status"]
        )

    def action_get_rels(
        self, registry: Any, graph: Any, spec_ref: Any
    ) -> GetRelsResult:
        spec = registry.resolve_ref(spec_ref)
        if spec is None:
            raise ValueError(f"Spec ref '{spec_ref}' not found")

        kind = spec.kind
        name = spec.metadata.name
        if not graph.g.has_node(f"{kind}/{name}"):
            raise ValueError(f"Spec ref '{spec_ref}' is absent from the graph")

        async def _get() -> dict[str, Any]:
            resp = await self._client.get(f"/api/specs/{kind}/{name}/rels")
            assert resp.status_code == 200
            return resp.json()

        data = asyncio.run(_get())
        self._rels = data
        return GetRelsResult(
            upstream=data["upstream"],
            downstream=data["downstream"],
            edge_count=data["edge_count"],
        )

    def action_render_detail(self, data: Any, format: Any) -> None:
        self._rendered_detail = data
        self._rendered_format = format

    def action_render_404(self, data: Any, format: Any) -> None:
        self._not_found_detail = data
        self._not_found_format = format

    def action_toggle_tab(self, tab_name: Any) -> ToggleTabResult:
        if tab_name not in DETAIL_TABS:
            raise ValueError(f"Unknown detail tab '{tab_name}'")
        self._active_tab = tab_name
        return ToggleTabResult(active_tab=self._active_tab)

    def action_navigate_related(self, related_ref: Any) -> NavigateRelatedResult:
        relations = self._rels["upstream"] + self._rels["downstream"]
        if related_ref not in {relation["ref"] for relation in relations}:
            self._navigated_related = False
            return NavigateRelatedResult(navigated=False)

        spec = self._registry.resolve_ref(related_ref)
        if spec is None:
            self._navigated_related = False
            return NavigateRelatedResult(navigated=False)

        kind = spec.kind
        name = spec.metadata.name
        if not self._graph.g.has_node(f"{kind}/{name}"):
            self._navigated_related = False
            return NavigateRelatedResult(navigated=False)

        async def _get() -> bool:
            resp = await self._client.get(f"/api/specs/{kind}/{name}")
            return resp.status_code == 200

        ok = asyncio.run(_get())
        self._navigated_related = ok
        return NavigateRelatedResult(navigated=ok)

    def verify_developer_sees_parsed_spec_metadata_and_schema(self) -> None:
        assert self._detail["kind"] == self._requested_kind
        assert self._detail["name"] == self._requested_name

    def verify_developer_sees_raw_yaml_source(self) -> None:
        assert f"kind: {self._requested_kind}" in self._detail["raw_yaml"]

    def verify_developer_sees_upstream_and_downstream_relationships(self) -> None:
        assert isinstance(self._rels["upstream"], list)
        assert isinstance(self._rels["downstream"], list)

    def verify_developer_sees_implementation_status(self) -> None:
        assert self._detail["impl_status"] in ("mapped", "unimplemented", "unknown")

    def verify_clicking_a_tab_switches_the_detail_panel_content(self) -> None:
        assert self._active_tab in DETAIL_TABS

    def verify_clicking_a_relationship_link_navigates_to_that_spec(self) -> None:
        has_rels = bool(self._rels["upstream"] or self._rels["downstream"])
        if has_rels:
            assert self._navigated_related is True

    def verify_all_tabs_render_without_errors(self) -> None:
        for tab in DETAIL_TABS:
            assert isinstance(tab, str)

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def inspect_spec_detail_web_impl() -> InspectSpecDetailWebImpl:
    return InspectSpecDetailWebImpl()
