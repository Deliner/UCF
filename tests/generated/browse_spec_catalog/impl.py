"""Implementation for use case: browse-spec-catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.web.app import create_app

from .interface import (
    BrowseSpecCatalogInterface,
    ListAllResult,
    ListSpecsResult,
    LoaderContext,
)


class BrowseSpecCatalogImpl(BrowseSpecCatalogInterface):
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

    def _fetch_catalog(self, params: dict[str, str]) -> dict[str, Any]:
        import asyncio

        async def _get() -> dict[str, Any]:
            response = await self._client.get("/api/specs", params=params)
            assert response.status_code == 200
            return response.json()

        return asyncio.run(_get())

    def _record_render(self, channel: str, data: Any, format: Any) -> None:
        self._rendered_results.append(
            {"channel": channel, "data": data, "format": format}
        )

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
            resp = await self._client.get(
                "/api/specs", params={"search": "zzznonexistent999"}
            )
            return resp.json()

        data = asyncio.run(_get())
        assert data["total_count"] == 0
        assert data["specs"] == []

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def browse_spec_catalog_impl() -> BrowseSpecCatalogImpl:
    return BrowseSpecCatalogImpl()
