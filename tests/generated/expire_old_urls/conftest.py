"""Executable inputs for the expire-old-urls generated tests."""

import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    return {"days_threshold": 15}
