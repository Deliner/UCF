"""Executable inputs for the create-short-url-with-retry generated tests."""

import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    return {
        "original_url": "https://github.com/example/repo",
        "created_by": "test_user",
    }
