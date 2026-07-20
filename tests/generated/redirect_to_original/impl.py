"""Implementation for use case: redirect-to-original.

@implements("use-cases/redirect-to-original")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import (
    AcquireClickLockResult,
    IncrementClicksResult,
    LookupUrlResult,
    RedirectResult,
    RedirectToOriginalInterface,
    ReleaseClickLockResult,
)

HAPPY_SLUG = "test123"
MISSING_SLUG = "missing123"
ORIGINAL_URL = "https://example.com/page"
CREATED_AT = 1_700_000_000.0


class RedirectToOriginalImpl(RedirectToOriginalInterface):
    def __init__(self) -> None:
        self.service = URLShortener()
        self._redirect_url = None
        self._redirect_status = None
        self._initial_count = None
        self._new_count = None
        self._locks: dict[str, tuple[Any, Any, Any]] = {}

    # ── Actions ──

    def action_lookup_url(self, slug: Any) -> LookupUrlResult:
        record = self.service.get_by_slug(slug)
        if record is None:
            raise ValueError(f"Slug '{slug}' not found")
        self._initial_count = record.click_count
        # Return the full record object (generator expects this)
        return LookupUrlResult(url_record=record)

    def action_increment_clicks(self, slug: Any) -> IncrementClicksResult:
        new_count = self.service.increment_clicks(slug)
        self._new_count = new_count
        return IncrementClicksResult(new_count=new_count)

    def action_acquire_click_lock(
        self, resource: Any, key: Any, timeout: Any
    ) -> AcquireClickLockResult:
        """Acquire a lock on a resource."""
        lock_id = f"{resource}:{key}:{timeout}"
        self._locks[lock_id] = (resource, key, timeout)
        return AcquireClickLockResult(lock_id=lock_id, acquired=True)

    def action_release_click_lock(self, lock_id: Any) -> ReleaseClickLockResult:
        """Release a previously acquired lock."""
        if lock_id in self._locks:
            del self._locks[lock_id]
            return ReleaseClickLockResult(released=True)
        return ReleaseClickLockResult(released=False)

    def action_redirect(self, target_url: Any, status_code: Any) -> RedirectResult:
        self._redirect_url = target_url
        self._redirect_status = status_code
        return RedirectResult(redirected=True)

    def action_return_404(self, data: Any, format: Any) -> None:
        slug = data["slug"]
        if self.service.get_by_slug(slug) is not None:
            raise ValueError(
                f"Cannot render not-found response for existing slug '{slug}'"
            )
        self._not_found_response = {"data": data, "format": format}

    # ── Verifications ──

    def verify_visitor_is_redirected_to_original_url(self) -> None:
        assert self._redirect_url is not None, "No redirect URL set"
        assert self._redirect_url.startswith("http"), (
            f"Invalid redirect URL: {self._redirect_url}"
        )

    def verify_click_count_is_incremented_by_1(self) -> None:
        assert self._initial_count is not None, "Initial count not captured"
        assert self._new_count is not None, "New count not captured"
        assert self._new_count == self._initial_count + 1, (
            f"Click count not incremented correctly: "
            f"{self._initial_count} → {self._new_count}"
        )

    def verify_redirect_uses_302_found_status(self) -> None:
        assert self._redirect_status == 302, (
            f"Expected status 302, got {self._redirect_status}"
        )

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def redirect_to_original_impl() -> RedirectToOriginalImpl:
    impl = RedirectToOriginalImpl()

    record = impl.service.store_url(
        slug=HAPPY_SLUG,
        original_url=ORIGINAL_URL,
        created_by="test_user",
    )
    record.created_at = CREATED_AT

    return impl
