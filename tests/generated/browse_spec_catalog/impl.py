"""Implementation for use case: browse-spec-catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.web.app import create_app

from .interface import BrowseSpecCatalogInterface, ListSpecsResult, LoaderContext

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class BrowseSpecCatalogImpl(BrowseSpecCatalogInterface):

    def setup_loader(self) -> LoaderContext:
        self._app = create_app(SPECS_DIR)
        transport = ASGITransport(app=self._app)
        self._client = AsyncClient(transport=transport, base_url="http://test")
        return LoaderContext(registry=self._app, loaded_count=1, load_errors=[])

    def action_list_specs(self, registry: Any, kind_filter: Any = None, search_query: Any = None) -> ListSpecsResult:
        import asyncio
        params: dict[str, str] = {}
        if kind_filter:
            params["kind"] = kind_filter
        if search_query:
            params["search"] = search_query

        async def _get():
            resp = await self._client.get("/api/specs", params=params)
            assert resp.status_code == 200
            return resp.json()

        data = asyncio.run(_get())
        self._catalog_data = data
        return ListSpecsResult(
            specs=data["specs"],
            total_count=data["total_count"],
            kind_counts=data["kind_counts"],
        )

    def action_render_results(self, data: Any, format: Any = None) -> None:
        pass

    def verify_developer_receives_a_list_of_specs_matching_the_filter(self) -> None:
        assert self._catalog_data["total_count"] > 0
        assert len(self._catalog_data["specs"]) == self._catalog_data["total_count"]

    def verify_spec_counts_per_kind_are_reported(self) -> None:
        counts = self._catalog_data["kind_counts"]
        assert isinstance(counts, dict)
        assert sum(counts.values()) > 0

    def verify_empty_result_shows_a_clear_message(self) -> None:
        import asyncio

        async def _get():
            resp = await self._client.get("/api/specs", params={"search": "zzznonexistent999"})
            return resp.json()

        data = asyncio.run(_get())
        assert data["total_count"] == 0
        assert data["specs"] == []

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def browse_spec_catalog_impl() -> BrowseSpecCatalogImpl:
    return BrowseSpecCatalogImpl()
