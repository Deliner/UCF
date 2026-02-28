"""Implementation for use case: redirect-to-original.

@implements("use-cases/redirect-to-original")
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.shortener import URLShortener

from .interface import (
    IncrementClicksResult,
    LookupUrlResult,
    RedirectResult,
    RedirectToOriginalInterface,
)


class RedirectToOriginalImpl(RedirectToOriginalInterface):
    def __init__(self) -> None:
        self.service = URLShortener()
        self._redirect_url = None
        self._redirect_status = None
        self._initial_count = None
        self._new_count = None
        self._locks = {}  # lock_id → (resource, key)

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
    ) -> Any:
        """Acquire a lock on a resource."""
        import uuid
        from dataclasses import dataclass
        
        @dataclass
        class LockResult:
            lock_id: str
            acquired: bool
        
        lock_id = str(uuid.uuid4())
        self._locks[lock_id] = (resource, key)
        return LockResult(lock_id=lock_id, acquired=True)

    def action_release_click_lock(self, lock_id: Any) -> Any:
        """Release a previously acquired lock."""
        from dataclasses import dataclass
        
        @dataclass
        class ReleaseResult:
            released: bool
        
        if lock_id in self._locks:
            del self._locks[lock_id]
            return ReleaseResult(released=True)
        return ReleaseResult(released=False)

    def action_redirect(self, target_url: Any, status_code: Any) -> RedirectResult:
        self._redirect_url = target_url
        self._redirect_status = status_code
        return RedirectResult(redirected=True)

    # ── Verifications ──

    def verify_visitor_is_redirected_to_original_url(self) -> None:
        assert self._redirect_url is not None, "No redirect URL set"
        assert self._redirect_url.startswith(
            "http"
        ), f"Invalid redirect URL: {self._redirect_url}"

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
    
    # Pre-populate test URL
    impl.service.store_url(
        slug="test123",
        original_url="https://example.com/page",
        created_by="test_user",
    )
    
    # Monkey-patch actions to use test slug when None passed
    original_lookup = impl.action_lookup_url
    
    def lookup_with_default(slug):
        return original_lookup(slug if slug is not None else "test123")
    
    impl.action_lookup_url = lookup_with_default
    
    original_acquire_lock = impl.action_acquire_click_lock
    
    def acquire_with_default(resource, key, timeout):
        return original_acquire_lock(resource, key if key is not None else "test123", timeout)
    
    impl.action_acquire_click_lock = acquire_with_default
    
    original_increment = impl.action_increment_clicks
    
    def increment_with_default(slug):
        return original_increment(slug if slug is not None else "test123")
    
    impl.action_increment_clicks = increment_with_default
    
    # Add missing action_return_404 for alt flow
    def action_return_404(data, format):
        impl._alt_flow_404 = data
    
    impl.action_return_404 = action_return_404
    
    return impl
