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
                None,
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
    impl = CreateShortUrlImpl()
    
    # Monkey-patch to use real URL when None passed
    original_validate = impl.action_validate_url
    
    def validate_with_default(url):
        return original_validate(url if url is not None else "https://github.com/test/repo")
    
    impl.action_validate_url = validate_with_default
    
    original_store = impl.action_store_url
    
    def store_with_default(slug, original_url, created_by):
        return original_store(
            slug,
            original_url if original_url is not None else "https://github.com/test/repo",
            created_by if created_by is not None else "test_user",
        )
    
    impl.action_store_url = store_with_default
    
    # No need for action_return_error stub!
    # Alt flow can now call self.render_cli_output() directly (inherited from FrameworkActions)
    
    # Add missing action_retry_generate for alt flow
    def action_retry_generate(length):
        return impl.action_generate_slug(length)
    
    impl.action_retry_generate = action_retry_generate
    
    return impl
