"""Concrete inputs for the generated get-url-stats scenarios."""

from __future__ import annotations

import pytest

from .impl import STATS_SLUG


@pytest.fixture
def inputs() -> dict[str, object]:
    return {"slug": STATS_SLUG}
