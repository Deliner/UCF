"""Test fixtures for redirect-to-original use case."""

import pytest

from .impl import RedirectToOriginalImpl


@pytest.fixture
def redirect_to_original_impl_with_data():
    """Create impl with pre-populated data."""
    impl = RedirectToOriginalImpl()

    # Pre-populate a URL for testing
    impl.service.store_url(
        slug="test123",
        original_url="https://example.com/original",
        created_by="test_user",
    )

    # Monkey-patch to use test slug if None passed
    original_lookup = impl.action_lookup_url

    def lookup_with_default(slug):
        if slug is None:
            slug = "test123"
        return original_lookup(slug)

    impl.action_lookup_url = lookup_with_default

    original_increment = impl.action_increment_clicks

    def increment_with_default(slug):
        if slug is None:
            slug = "test123"
        return original_increment(slug)

    impl.action_increment_clicks = increment_with_default

    # Add missing action_return_404 for alt flow
    def action_return_404(data, format):
        impl._alt_flow_404_data = data

    impl.action_return_404 = action_return_404

    return impl
