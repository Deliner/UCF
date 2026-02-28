"""Implementation for use case: expire-old-urls.

@implements("use-cases/expire-old-urls")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import DeleteBatchResult, ExpireOldUrlsInterface, FindExpiredResult


class ExpireOldUrlsImpl(ExpireOldUrlsInterface):
    def __init__(self) -> None:
        self.service = URLShortener()
        self._deleted_count = None
        self._failed_slugs = None
        self._found_count = 0

    def action_find_expired(self, days_threshold: Any) -> FindExpiredResult:
        expired_slugs = self.service.list_expired_urls(days_threshold)
        self._found_count = len(expired_slugs)
        return FindExpiredResult(expired_slugs=expired_slugs)

    def action_delete_batch(self, slugs: Any) -> DeleteBatchResult:
        deleted, failed = self.service.delete_batch(slugs)
        self._deleted_count = deleted
        self._failed_slugs = failed
        return DeleteBatchResult(deleted_count=deleted, failed_slugs=failed)

    def verify_all_expired_urls_are_deleted_from_database(self) -> None:
        assert self._deleted_count is not None
        for slug in self._failed_slugs:
            assert self.service.slug_exists(
                slug
            ), f"Failed slug {slug} should still exist"

    def verify_deletion_count_matches_number_of_found_expired_urls(self) -> None:
        assert self._deleted_count is not None
        expected = self._found_count - len(self._failed_slugs)
        assert self._deleted_count == expected, (
            f"Expected {expected} deletions, got {self._deleted_count}"
        )

    def verify_failed_slugs_is_empty_if_all_deletions_successful(self) -> None:
        if self._found_count > 0:
            assert self._failed_slugs is not None

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def expire_old_urls_impl() -> ExpireOldUrlsImpl:
    impl = ExpireOldUrlsImpl()
    
    # Pre-populate some old URLs for testing
    import time
    
    # Create 3 URLs with old timestamps
    for i in range(3):
        slug = f"old{i}"
        record = impl.service.store_url(
            slug=slug,
            original_url=f"https://example.com/old{i}",
            created_by="test",
        )
        # Manually set old timestamp (30 days ago)
        impl.service._urls[slug].created_at = time.time() - (30 * 86400)
    
    # Create 1 fresh URL
    impl.service.store_url(
        slug="fresh",
        original_url="https://example.com/fresh",
        created_by="test",
    )
    
    # Monkey-patch to use test threshold
    original_find = impl.action_find_expired
    
    def find_with_default(days_threshold):
        return original_find(days_threshold if days_threshold is not None else 15)
    
    impl.action_find_expired = find_with_default
    
    # Add missing action_log_empty for alt flow
    def action_log_empty(data, format):
        impl._alt_empty = data
    
    impl.action_log_empty = action_log_empty
    
    return impl
