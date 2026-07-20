"""Executable inputs for the explore-dependency-graph-web generated tests."""

from pathlib import Path

import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    return {
        "specs_dir": Path(__file__).resolve().parents[3] / "specs",
        "target_node_id": "action/acquire-lock",
        "target_view": "static",
    }
