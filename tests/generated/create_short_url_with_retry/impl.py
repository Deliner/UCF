"""Implementation for use case: create-short-url-with-retry.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from typing import Any

from .interface import CreateShortUrlWithRetryInterface, ValidateUrlResult, GenerateSlugResult, CheckExistsResult, StoreUrlResult

class CreateShortUrlWithRetryImpl(CreateShortUrlWithRetryInterface):

    # ── State Setup ──

    # ── Actions ──

    def action_validate_url(self, url: Any) -> ValidateUrlResult:
        raise NotImplementedError("Fill in: action_validate_url")

    def action_generate_slug(self, length: Any) -> GenerateSlugResult:
        raise NotImplementedError("Fill in: action_generate_slug")

    def action_check_exists(self, slug: Any) -> CheckExistsResult:
        raise NotImplementedError("Fill in: action_check_exists")

    def action_store_url(self, slug: Any, original_url: Any, created_by: Any) -> StoreUrlResult:
        raise NotImplementedError("Fill in: action_store_url")

    # ── Verifications ──

    def verify_short_url_is_created_and_stored(self) -> None:
        raise NotImplementedError("Fill in: verify_short_url_is_created_and_stored")

    def verify_short_url_uses_generated_slug(self) -> None:
        raise NotImplementedError("Fill in: verify_short_url_uses_generated_slug")

    def verify_slug_is_unique_in_database(self) -> None:
        raise NotImplementedError("Fill in: verify_slug_is_unique_in_database")

    def verify_required_inputs_validated(self) -> None:
        raise NotImplementedError("Fill in: verify_required_inputs_validated")
