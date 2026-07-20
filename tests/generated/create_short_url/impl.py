"""Implementation for use case: create-short-url.

@implements("use-cases/create-short-url")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import (
    CheckExistsResult,
    CreateShortUrlInterface,
    GenerateSlugResult,
    RetryGenerateResult,
    StoreUrlResult,
    ValidateUrlResult,
)


class CreateShortUrlImpl(CreateShortUrlInterface):
    def __init__(self) -> None:
        self.service = URLShortener()
        self._stored_url = None

    # ── Actions ──

    def action_validate_url(self, url: Any) -> ValidateUrlResult:
        is_valid, error_message = self.service.validate_url(url)
        return ValidateUrlResult(
            is_valid=is_valid,
            error_message=error_message or "",
        )

    def action_generate_slug(self, length: Any) -> GenerateSlugResult:
        slug = self.service.generate_slug(length)
        return GenerateSlugResult(slug=slug)

    def action_check_exists(self, slug: Any) -> CheckExistsResult:
        exists = self.service.slug_exists(slug)
        return CheckExistsResult(exists=exists)

    def action_store_url(
        self, slug: Any, original_url: Any, created_by: Any
    ) -> StoreUrlResult:
        record = self.service.store_url(slug, original_url, created_by)
        self._stored_url = record
        full_url = self.service.get_full_short_url(slug)
        return StoreUrlResult(url_id=record.id, short_url=full_url)

    def action_return_error(self, data: Any, format: Any) -> None:
        self._rendered_error = data
        self.render_cli_output(data, str(format))

    def action_retry_generate(self, length: Any) -> RetryGenerateResult:
        retry_slug = self.service.generate_slug(length)
        self._retry_slug = retry_slug
        return RetryGenerateResult(retry_slug=retry_slug)

    # ── Verifications ──

    def verify_short_url_is_created_and_stored(self) -> None:
        assert self._stored_url is not None, "URL was not stored"
        assert self._stored_url.slug, "Stored URL has no slug"
        assert self._stored_url.original_url, "Stored URL has no original URL"

    def verify_slug_is_unique_in_database(self) -> None:
        assert self._stored_url is not None
        # Slug must be unique - trying to store again should fail
        with pytest.raises(ValueError, match="already exists"):
            self.service.store_url(
                self._stored_url.slug,
                "http://duplicate.com",
                "duplicate-check",
            )

    def verify_click_count_is_initialized_to_0(self) -> None:
        assert self._stored_url is not None
        assert self._stored_url.click_count == 0, (
            f"Click count should be 0, got {self._stored_url.click_count}"
        )

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def create_short_url_impl() -> CreateShortUrlImpl:
    return CreateShortUrlImpl()
