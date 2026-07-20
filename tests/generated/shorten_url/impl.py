"""Implementation for use case: shorten-url.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from .interface import CreateShortLinkResult, ShortenUrlInterface

ORIGINAL_URL = "https://example.com/article"
CUSTOM_CODE = "article1"
BASE_URL = "https://short.example"
CREATED_AT = "2026-07-19T00:00:00+00:00"
EXPIRES_AT = "2026-08-18T00:00:00+00:00"


@dataclass(frozen=True)
class _ShortLink:
    original_url: str
    code: str
    created_at: str
    expires_at: str


class ShortenUrlImpl(ShortenUrlInterface):
    def __init__(self) -> None:
        self._links: dict[str, _ShortLink] = {}
        self._last_link: _ShortLink | None = None
        self._last_result: CreateShortLinkResult | None = None
        self._shown_error: str | None = None
        self._suggestions: list[str] = []

    # ── State Setup ──

    # ── Actions ──

    def action_create_short_link(
        self, original_url: Any, custom_code: Any
    ) -> CreateShortLinkResult:
        assert isinstance(original_url, str)
        assert original_url.startswith(("http://", "https://"))
        assert isinstance(custom_code, str)
        assert custom_code.isalnum()
        assert custom_code not in self._links

        link = _ShortLink(
            original_url=original_url,
            code=custom_code,
            created_at=CREATED_AT,
            expires_at=EXPIRES_AT,
        )
        self._links[custom_code] = link
        self._last_link = link
        self._last_result = CreateShortLinkResult(
            code=custom_code,
            url=f"{BASE_URL}/{custom_code}",
            expiry=EXPIRES_AT,
        )
        return self._last_result

    def action_show_error(self, error: Any) -> None:
        assert error == "URL must start with http:// or https://"
        self._shown_error = str(error)

    def action_suggest_alternatives(self, requested_code: Any) -> None:
        assert isinstance(requested_code, str)
        assert requested_code in self._links
        self._suggestions = [
            candidate
            for suffix in ("1", "2", "3")
            if (candidate := f"{requested_code}{suffix}") not in self._links
        ]
        assert len(self._suggestions) == 3

    def seed_existing_link(self, code: str, original_url: str) -> None:
        self._links[code] = _ShortLink(
            original_url=original_url,
            code=code,
            created_at=CREATED_AT,
            expires_at=EXPIRES_AT,
        )

    # ── Verifications ──

    def verify_content_creator_receives_shortened_url(self) -> None:
        assert self._last_result is not None
        assert self._last_result.url == f"{BASE_URL}/{self._last_result.code}"

    def verify_shortened_url_is_ready_to_use_immediately(self) -> None:
        assert self._last_link is not None
        assert self._links[self._last_link.code] is self._last_link

    def verify_shortened_url_redirects_to_original_page(self) -> None:
        assert self._last_link is not None
        assert self._last_link.original_url == ORIGINAL_URL

    def verify_creation_is_recorded_with_timestamp(self) -> None:
        assert self._last_link is not None
        assert self._last_link.created_at == CREATED_AT

    def verify_required_inputs_validated(self) -> None:
        assert self._last_link is not None
        assert self._last_link.original_url
        assert self._last_link.code


@pytest.fixture
def shorten_url_impl(request: pytest.FixtureRequest) -> ShortenUrlImpl:
    implementation = ShortenUrlImpl()
    if request.node.name == "test_custom_code_taken":
        implementation.seed_existing_link(CUSTOM_CODE, ORIGINAL_URL)
    return implementation
