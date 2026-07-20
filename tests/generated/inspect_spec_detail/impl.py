"""Implementation for use case: inspect-spec-detail."""

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
    InspectSpecDetailInterface,
    LoaderContext,
)


class InspectSpecDetailImpl(InspectSpecDetailInterface):
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
            loaded_count=registry.total,
            load_errors=errors,
        )

    def setup_graph_builder(self, registry: Any) -> Graph_builderContext:
        graph = DependencyGraph(registry)
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
            spec=data,
            raw_yaml=data["raw_yaml"],
            impl_status=data["impl_status"],
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

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def inspect_spec_detail_impl() -> InspectSpecDetailImpl:
    return InspectSpecDetailImpl()
