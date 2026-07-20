"""Concrete inputs for deterministic URL-shortening scenarios."""

import pytest

from .impl import CUSTOM_CODE, ORIGINAL_URL


@pytest.fixture
def inputs() -> dict[str, object]:
    return {
        "original_url": ORIGINAL_URL,
        "custom_code": CUSTOM_CODE,
    }
