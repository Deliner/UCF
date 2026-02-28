"""Test fixtures for create-short-url use case."""

import pytest

from .impl import CreateShortUrlImpl


@pytest.fixture
def real_inputs():
    """Provide real test inputs."""
    return {
        "original_url": "https://github.com/example/repo",
        "custom_slug": None,
        "created_by": "test_user",
    }


@pytest.fixture
def create_short_url_impl_with_inputs(real_inputs):
    """Create impl with monkey-patched methods to use real inputs."""
    impl = CreateShortUrlImpl()
    
    # Store inputs for use in actions
    impl._test_inputs = real_inputs
    
    # Monkey-patch to return proper errors for alt flow
    original_validate = impl.action_validate_url
    
    def validate_with_context(url):
        # Use real input if None passed (from orchestrator)
        if url is None:
            url = real_inputs["original_url"]
        return original_validate(url)
    
    impl.action_validate_url = validate_with_context
    
    # Monkey-patch store to use real inputs
    original_store = impl.action_store_url
    
    def store_with_context(slug, original_url, created_by):
        if original_url is None:
            original_url = real_inputs["original_url"]
        if created_by is None:
            created_by = real_inputs["created_by"]
        return original_store(slug, original_url, created_by)
    
    impl.action_store_url = store_with_context
    
    # Add missing action_return_error for alt flow
    def action_return_error(data, format):
        # Just a stub for alt flow test
        impl._alt_flow_error = data
    
    impl.action_return_error = action_return_error
    
    return impl
