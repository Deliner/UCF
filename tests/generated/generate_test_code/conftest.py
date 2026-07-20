"""Explicit inputs for the generate-test-code scenario."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucf.parser.loader import SpecLoader

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, object]:
    specs_dir = REPOSITORY_ROOT / "specs"
    loader = SpecLoader(specs_dir)
    target_usecase = loader.load_file(
        specs_dir / "use-cases" / "generate-test-code.yaml"
    )

    return {
        "specs_dir": specs_dir,
        "target_usecase": target_usecase,
        "output_dir": tmp_path / "generated",
    }
