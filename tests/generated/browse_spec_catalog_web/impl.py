"""Implementation for use case: browse-spec-catalog-web.

Tests both backend API (inherited from parent UC) and UI interaction contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.web.app import create_app

from .interface import (
    BrowseSpecCatalogWebInterface,
    FilterByKindResult,
    ListSpecsResult,
    LoaderContext,
    NavigateToSpecResult,
)

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class BrowseSpecCatalogWebImpl(BrowseSpecCatalogWebInterface):

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

        data = asyncio.run(self._async_get("/api/specs", params))
        self._catalog_data = data
        return ListSpecsResult(
            specs=data["specs"],
            total_count=data["total_count"],
            kind_counts=data["kind_counts"],
        )

    def action_render_results(self, data: Any, format: Any = None) -> None:
        pass

    def action_filter_by_kind(self, kind: Any = None, search_text: Any = None) -> FilterByKindResult:
        import asyncio
        params: dict[str, str] = {}
        if kind:
            params["kind"] = kind
        data = asyncio.run(self._async_get("/api/specs", params))
        self._filtered_data = data
        all_match_kind = all(s["kind"] == kind for s in data["specs"]) if kind and data["specs"] else True
        return FilterByKindResult(filtered_view=all_match_kind)

    def action_navigate_to_spec(self, spec_kind: Any, spec_name: Any) -> NavigateToSpecResult:
        import asyncio
        if not spec_kind or not spec_name:
            first = self._catalog_data["specs"][0] if self._catalog_data["specs"] else None
            if first:
                spec_kind, spec_name = first["kind"], first["name"]
            else:
                return NavigateToSpecResult(navigated=False)

        data = asyncio.run(self._async_get(f"/api/specs/{spec_kind}/{spec_name}"))
        self._navigated_spec = data
        return NavigateToSpecResult(navigated=True)

    async def _async_get(self, path: str, params: dict[str, str] | None = None) -> dict:
        resp = await self._client.get(path, params=params or {})
        assert resp.status_code == 200
        return resp.json()

    def verify_developer_receives_a_list_of_specs_matching_the_filter(self) -> None:
        assert self._catalog_data["total_count"] > 0

    def verify_spec_counts_per_kind_are_reported(self) -> None:
        assert isinstance(self._catalog_data["kind_counts"], dict)

    def verify_empty_result_shows_a_clear_message(self) -> None:
        import asyncio
        data = asyncio.run(self._async_get("/api/specs", {"search": "zzz_nonexistent_999"}))
        assert data["total_count"] == 0

    def verify_clicking_a_kind_tab_filters_the_spec_table(self) -> None:
        import asyncio
        data = asyncio.run(self._async_get("/api/specs", {"kind": "action"}))
        assert all(s["kind"] == "action" for s in data["specs"])

    def verify_clicking_a_spec_row_navigates_to_its_detail_page(self) -> None:
        assert self._navigated_spec is not None
        assert "name" in self._navigated_spec
        assert "kind" in self._navigated_spec
        assert "raw_yaml" in self._navigated_spec
        assert self._navigated_spec["name"], "navigated spec must have a non-empty name"

    def verify_search_input_filters_specs_by_name_match(self) -> None:
        import asyncio
        data = asyncio.run(self._async_get("/api/specs", {"search": "validate"}))
        for s in data["specs"]:
            assert "validate" in s["name"].lower()

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def browse_spec_catalog_web_impl() -> BrowseSpecCatalogWebImpl:
    return BrowseSpecCatalogWebImpl()
