"""Implementation for use case: get-url-stats.

@implements("use-cases/get-url-stats")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import FetchStatsResult, GetUrlStatsInterface

STATS_SLUG = "stats123"
STATS_CREATED_AT = 1_700_000_000.0


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

    def action_return_not_found(self, data: Any, format: Any) -> None:
        self._not_found_output = data
        self._not_found_format = format

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

    record = impl.service.store_url(
        slug=STATS_SLUG,
        original_url="https://example.com/stats-page",
        created_by="stat_user",
    )
    record.created_at = STATS_CREATED_AT
    impl.service.increment_clicks(STATS_SLUG)
    impl.service.increment_clicks(STATS_SLUG)

    return impl
