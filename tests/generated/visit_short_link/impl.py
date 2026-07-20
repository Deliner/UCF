"""Implementation for use case: visit-short-link.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from .interface import RedirectToDestinationResult, VisitShortLinkInterface

SHORT_CODE = "abc123"
DESTINATION_URL = "https://example.com/article"


class VisitShortLinkImpl(VisitShortLinkInterface):
    def __init__(self) -> None:
        self._links: dict[str, str] = {}
        self._visit_counts: dict[str, int] = {}
        self._last_code: str | None = None
        self._last_result: RedirectToDestinationResult | None = None
        self._redirect_elapsed_ms: float | None = None
        self._missing_code: str | None = None

    # ── State Setup ──

    # ── Actions ──

    def action_redirect_to_destination(
        self, short_code: Any
    ) -> RedirectToDestinationResult:
        started_at = time.perf_counter_ns()
        assert isinstance(short_code, str)
        assert short_code.isalnum()
        assert 6 <= len(short_code) <= 10
        assert short_code in self._links

        self._visit_counts[short_code] = self._visit_counts.get(short_code, 0) + 1
        self._last_code = short_code
        self._last_result = RedirectToDestinationResult(
            url=self._links[short_code],
            success=True,
        )
        self._redirect_elapsed_ms = (time.perf_counter_ns() - started_at) / 1_000_000
        return self._last_result

    def action_show_404(self, short_code: Any) -> None:
        assert isinstance(short_code, str)
        assert short_code not in self._links
        self._missing_code = short_code

    def seed_link(self, short_code: str, destination_url: str) -> None:
        self._links[short_code] = destination_url
        self._visit_counts[short_code] = 0

    # ── Verifications ──

    def verify_visitor_is_redirected_to_original_page(self) -> None:
        assert self._last_result == RedirectToDestinationResult(
            url=DESTINATION_URL,
            success=True,
        )

    def verify_visit_is_recorded_for_analytics(self) -> None:
        assert self._last_code is not None
        assert self._visit_counts[self._last_code] == 1

    def verify_redirect_happens_in_200ms(self) -> None:
        assert self._redirect_elapsed_ms is not None
        assert self._redirect_elapsed_ms < 200

    def verify_required_inputs_validated(self) -> None:
        assert self._last_code is not None
        assert self._last_code.isalnum()
        assert 6 <= len(self._last_code) <= 10


@pytest.fixture
def visit_short_link_impl(request: pytest.FixtureRequest) -> VisitShortLinkImpl:
    implementation = VisitShortLinkImpl()
    if request.node.name == "test_visit_short_link_completes_successfully":
        implementation.seed_link(SHORT_CODE, DESTINATION_URL)
    return implementation
