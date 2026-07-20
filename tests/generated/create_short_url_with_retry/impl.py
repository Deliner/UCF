"""Implementation for use case: create-short-url-with-retry.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

import random
import string
from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import (
    CheckExistsResult,
    CreateShortUrlWithRetryInterface,
    GenerateSlugResult,
    StoreUrlResult,
    ValidateUrlResult,
)


class CreateShortUrlWithRetryImpl(CreateShortUrlWithRetryInterface):
    def __init__(self) -> None:
        self.service = URLShortener()
        self._random = random.Random(0)
        self._generated_slug: str | None = None
        self._stored_url = None
        self._rendered_error: dict[str, Any] | None = None

    # ── Actions ──

    def action_validate_url(self, url: Any) -> ValidateUrlResult:
        is_valid, error_message = self.service.validate_url(url)
        return ValidateUrlResult(
            is_valid=is_valid,
            error_message=error_message or "",
        )

    def action_generate_slug(self, length: Any) -> GenerateSlugResult:
        slug_length = int(length)
        if not 4 <= slug_length <= 20:
            raise ValueError("length must be between 4 and 20")

        alphabet = string.ascii_letters + string.digits
        for _attempt in range(5):
            slug = "".join(self._random.choices(alphabet, k=slug_length))
            if not self.service.slug_exists(slug):
                self._generated_slug = slug
                return GenerateSlugResult(slug=slug)
        raise ValueError("MAX_RETRIES_EXCEEDED")

    def action_check_exists(self, slug: Any) -> CheckExistsResult:
        return CheckExistsResult(exists=self.service.slug_exists(str(slug)))

    def action_store_url(
        self, slug: Any, original_url: Any, created_by: Any
    ) -> StoreUrlResult:
        record = self.service.store_url(
            str(slug),
            str(original_url),
            str(created_by),
        )
        self._stored_url = record
        return StoreUrlResult(
            url_id=record.id,
            short_url=self.service.get_full_short_url(record.slug),
        )

    def action_return_error(self, data: Any, format: Any) -> None:
        self._rendered_error = dict(data)
        self.render_cli_output(data, str(format))

    def action_max_retries_exceeded_return_error(
        self,
        error_code: Any,
        message: Any,
        context: Any,
    ) -> None:
        self._rendered_error = {
            "error_code": str(error_code),
            "message": str(message),
            "context": dict(context),
        }
        self.render_error_response(
            str(error_code),
            str(message),
            dict(context),
        )

    # ── Verifications ──

    def verify_short_url_is_created_and_stored(self) -> None:
        assert self._stored_url is not None
        assert self.service.get_by_slug(self._stored_url.slug) == self._stored_url

    def verify_short_url_uses_generated_slug(self) -> None:
        assert self._stored_url is not None
        assert self._stored_url.slug == self._generated_slug

    def verify_slug_is_unique_in_database(self) -> None:
        assert self._stored_url is not None
        with pytest.raises(ValueError, match="already exists"):
            self.service.store_url(
                self._stored_url.slug,
                "https://example.com/duplicate",
                "duplicate-check",
            )

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def create_short_url_with_retry_impl() -> CreateShortUrlWithRetryImpl:
    return CreateShortUrlWithRetryImpl()
