"""Concrete inputs for the generated redirect-to-original scenarios."""

from __future__ import annotations

import pytest

from .impl import HAPPY_SLUG, MISSING_SLUG

SLUG_BY_TEST = {
    "test_redirect_to_original_completes_successfully": HAPPY_SLUG,
    "test_slug_not_found": MISSING_SLUG,
}


@pytest.fixture
def inputs(request: pytest.FixtureRequest) -> dict[str, object]:
    return {"slug": SLUG_BY_TEST[request.node.name]}
