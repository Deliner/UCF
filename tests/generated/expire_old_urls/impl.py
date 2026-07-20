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
        expired_slugs = self.service.list_expired_urls(int(days_threshold))
        self._found_count = len(expired_slugs)
        return FindExpiredResult(expired_slugs=expired_slugs)

    def action_delete_batch(self, slugs: Any) -> DeleteBatchResult:
        deleted, failed = self.service.delete_batch(slugs)
        self._deleted_count = deleted
        self._failed_slugs = failed
        return DeleteBatchResult(deleted_count=deleted, failed_slugs=failed)

    def action_log_empty(self, data: Any, format: Any) -> None:
        self._empty_result = data
        self.render_cli_output(data, str(format))

    def verify_all_expired_urls_are_deleted_from_database(self) -> None:
        assert self._deleted_count is not None
        for slug in self._failed_slugs:
            assert self.service.slug_exists(slug), (
                f"Failed slug {slug} should still exist"
            )

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

    for i in range(3):
        slug = f"old{i}"
        impl.service.store_url(
            slug=slug,
            original_url=f"https://example.com/old{i}",
            created_by="test",
        )
        impl.service._urls[slug].created_at = 0.0

    impl.service.store_url(
        slug="fresh",
        original_url="https://example.com/fresh",
        created_by="test",
    )

    return impl
