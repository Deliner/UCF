"""Concrete inputs for deterministic short-link visit scenarios."""

import pytest

from .impl import SHORT_CODE


@pytest.fixture
def inputs() -> dict[str, object]:
    return {"short_code": SHORT_CODE}
