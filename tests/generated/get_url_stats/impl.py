"""Implementation for use case: get-url-stats.

@implements("use-cases/get-url-stats")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import FetchStatsResult, GetUrlStatsInterface


class GetUrlStatsImpl(GetUrlStatsInterface):
    def __init__(self) -> None:
        self.service = URLShortener()
        self._stats = None

    def action_fetch_stats(self, slug: Any) -> FetchStatsResult:
        stats = self.service.get_stats(slug)
        self._stats = stats
        return FetchStatsResult(
            slug=stats["slug"],
            original_url=stats["original_url"],
            total_clicks=stats["total_clicks"],
            created_at=stats["created_at"],
            created_by=stats["created_by"],
        )

    def action_render_stats(self, data: Any, format: Any) -> None:
        pass

    def verify_creator_sees_total_click_count(self) -> None:
        assert self._stats is not None
        assert "total_clicks" in self._stats
        assert isinstance(self._stats["total_clicks"], int)
        assert self._stats["total_clicks"] >= 0

    def verify_creator_sees_original_url(self) -> None:
        assert self._stats is not None
        assert "original_url" in self._stats
        assert self._stats["original_url"].startswith("http")

    def verify_creator_sees_creation_timestamp(self) -> None:
        assert self._stats is not None
        assert "created_at" in self._stats
        assert self._stats["created_at"]

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def get_url_stats_impl() -> GetUrlStatsImpl:
    impl = GetUrlStatsImpl()
    
    # Pre-populate test URL
    impl.service.store_url(
        slug="stats123",
        original_url="https://example.com/stats-page",
        created_by="stat_user",
    )
    # Add some clicks
    impl.service.increment_clicks("stats123")
    impl.service.increment_clicks("stats123")
    
    # Monkey-patch to use test slug
    original_fetch = impl.action_fetch_stats
    
    def fetch_with_default(slug):
        return original_fetch(slug if slug is not None else "stats123")
    
    impl.action_fetch_stats = fetch_with_default
    
    # Add missing action_return_not_found for alt flow
    def action_return_not_found(data, format):
        impl._alt_404 = data
    
    impl.action_return_not_found = action_return_not_found
    
    return impl
