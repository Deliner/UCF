"""Concrete inputs for the generated inspect-spec-detail-web scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


@pytest.fixture
def inputs() -> dict[str, object]:
    return {
        "specs_dir": SPECS_DIR,
        "kind": "action",
        "name": "validate-spec",
        "spec_ref": "actions/validate-spec",
        "tab_name": "relationships",
        "related_ref": "usecase/validate-spec-directory",
    }
