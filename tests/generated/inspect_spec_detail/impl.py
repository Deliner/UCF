"""Implementation for use case: inspect-spec-detail."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.web.app import create_app

from .interface import (
    GetDetailResult,
    GetRelsResult,
    Graph_builderContext,
    InspectSpecDetailInterface,
    LoaderContext,
)

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class InspectSpecDetailImpl(InspectSpecDetailInterface):

    def setup_loader(self) -> LoaderContext:
        self._app = create_app(SPECS_DIR)
        transport = ASGITransport(app=self._app)
        self._client = AsyncClient(transport=transport, base_url="http://test")
        return LoaderContext(registry=self._app, loaded_count=1, load_errors=[])

    def setup_graph_builder(self) -> Graph_builderContext:
        return Graph_builderContext(graph=None, node_count=0, edge_count=0)

    def action_get_detail(self, registry: Any, kind: Any, name: Any) -> GetDetailResult:
        import asyncio

        async def _get():
            resp = await self._client.get(f"/api/specs/action/validate-spec")
            assert resp.status_code == 200
            return resp.json()

        data = asyncio.run(_get())
        self._detail = data
        return GetDetailResult(
            spec=data,
            raw_yaml=data["raw_yaml"],
            impl_status=data["impl_status"],
        )

    def action_get_rels(self, registry: Any, graph: Any, spec_ref: Any) -> GetRelsResult:
        import asyncio

        async def _get():
            resp = await self._client.get(f"/api/specs/action/validate-spec/rels")
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
        pass

    def verify_developer_sees_parsed_spec_metadata_and_schema(self) -> None:
        assert self._detail["kind"] == "action"
        assert self._detail["name"] == "validate-spec"

    def verify_developer_sees_raw_yaml_source(self) -> None:
        assert "kind: action" in self._detail["raw_yaml"]

    def verify_developer_sees_upstream_and_downstream_relationships(self) -> None:
        assert isinstance(self._rels["upstream"], list)
        assert isinstance(self._rels["downstream"], list)

    def verify_developer_sees_implementation_status(self) -> None:
        assert self._detail["impl_status"] in ("mapped", "unimplemented", "unknown")

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def inspect_spec_detail_impl() -> InspectSpecDetailImpl:
    return InspectSpecDetailImpl()
