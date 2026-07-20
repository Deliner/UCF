"""Concrete inputs for the scaffold-specs-from-code scenarios."""

from pathlib import Path

import pytest


@pytest.fixture
def inputs(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> dict[str, object]:
    source_dir = (
        tmp_path / "empty_src"
        if request.node.name == "test_no_code_found"
        else tmp_path / "src"
    )
    source_dir.mkdir(exist_ok=True)
    return {
        "source_dir": str(source_dir),
        "patterns": ["**/*.py"],
        "output_dir": str(tmp_path / "specs_out"),
    }
