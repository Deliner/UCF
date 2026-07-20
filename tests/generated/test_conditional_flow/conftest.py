"""Test fixtures for test-conditional-flow use case."""

import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    """Select the branch where step-b runs and step-c is skipped."""
    return {"threshold": 11}
