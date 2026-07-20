"""Executable inputs for the browse-spec-catalog generated tests."""

from pathlib import Path

import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    return {
        "specs_dir": Path(__file__).resolve().parents[3] / "specs",
        "kind_filter": "action",
        "search_query": "validate",
    }
