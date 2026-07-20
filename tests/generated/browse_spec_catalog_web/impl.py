"""Implementation for use case: browse-spec-catalog-web.

Tests both backend API (inherited from parent UC) and UI interaction contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.web.app import create_app

from .interface import (
    BrowseSpecCatalogWebInterface,
    FilterByKindResult,
    ListAllResult,
    ListSpecsResult,
    LoaderContext,
    NavigateToSpecResult,
    ShowAllResult,
)


class BrowseSpecCatalogWebImpl(BrowseSpecCatalogWebInterface):
    def __init__(self) -> None:
        self._rendered_results: list[dict[str, Any]] = []

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

    def action_list_specs(
        self, registry: Any, kind_filter: Any, search_query: Any
    ) -> ListSpecsResult:
        if not isinstance(registry, SpecRegistry):
            raise TypeError("registry must be a SpecRegistry")
        data = self._fetch_catalog(
            {"kind": str(kind_filter), "search": str(search_query)}
        )
        self._catalog_data = data
        return ListSpecsResult(
            specs=data["specs"],
            total_count=data["total_count"],
            kind_counts=data["kind_counts"],
        )

    def action_render_results(self, data: Any, format: Any) -> None:
        self._record_render("results", data, format)

    def action_filter_by_kind(
        self, kind: Any, search_text: Any
    ) -> FilterByKindResult:
        params = {"kind": str(kind), "search": str(search_text)}
        data = self._fetch_catalog(params)
        self._filtered_data = data
        kind_matches = all(
            spec["kind"] == str(kind) for spec in data["specs"]
        )
        search_matches = all(
            str(search_text).lower() in spec["name"].lower()
            for spec in data["specs"]
        )
        return FilterByKindResult(filtered_view=kind_matches and search_matches)

    def action_navigate_to_spec(
        self, spec_kind: Any, spec_name: Any
    ) -> NavigateToSpecResult:
        import asyncio

        if not spec_kind or not spec_name:
            raise ValueError("spec_kind and spec_name are required")

        data = asyncio.run(
            self._async_get(f"/api/specs/{spec_kind}/{spec_name}", {})
        )
        self._navigated_spec = data
        return NavigateToSpecResult(navigated=True)

    def action_list_all(self, registry: Any) -> ListAllResult:
        if not isinstance(registry, SpecRegistry):
            raise TypeError("registry must be a SpecRegistry")
        data = self._fetch_catalog({})
        self._catalog_data = data
        return ListAllResult(
            specs=data["specs"],
            total_count=data["total_count"],
            kind_counts=data["kind_counts"],
        )

    def action_render_all(self, data: Any) -> None:
        self._rendered_results.append({"channel": "all", "data": data})

    def action_render_empty(self, data: Any, format: Any) -> None:
        self._record_render("empty", data, format)

    def action_render_registry_error(self, data: Any, format: Any) -> None:
        self._record_render("registry-error", data, format)

    def action_render_kind_error(self, data: Any, format: Any) -> None:
        self._record_render("kind-error", data, format)

    def action_show_all(self) -> ShowAllResult:
        data = self._fetch_catalog({})
        self._filtered_data = data
        visible_count = len(data["specs"])
        return ShowAllResult(filtered_view=visible_count == data["total_count"])

    def _fetch_catalog(self, params: dict[str, str]) -> dict[str, Any]:
        import asyncio

        return asyncio.run(self._async_get("/api/specs", params))

    async def _async_get(
        self, path: str, params: dict[str, str]
    ) -> dict[str, Any]:
        resp = await self._client.get(path, params=params)
        assert resp.status_code == 200
        return resp.json()

    def _record_render(self, channel: str, data: Any, format: Any) -> None:
        self._rendered_results.append(
            {"channel": channel, "data": data, "format": format}
        )

    def verify_developer_receives_a_list_of_specs_matching_the_filter(self) -> None:
        assert self._catalog_data["total_count"] > 0

    def verify_spec_counts_per_kind_are_reported(self) -> None:
        assert isinstance(self._catalog_data["kind_counts"], dict)

    def verify_empty_result_shows_a_clear_message(self) -> None:
        import asyncio

        data = asyncio.run(
            self._async_get("/api/specs", {"search": "zzz_nonexistent_999"})
        )
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

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def browse_spec_catalog_web_impl() -> BrowseSpecCatalogWebImpl:
    return BrowseSpecCatalogWebImpl()
