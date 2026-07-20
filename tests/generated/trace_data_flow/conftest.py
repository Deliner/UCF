"""Concrete inputs for tracing one use case with a branch."""

from pathlib import Path

import pytest

from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader


@pytest.fixture
def inputs(specs_dir: Path) -> dict[str, object]:
    target = SpecLoader(specs_dir).load_file(
        specs_dir / "use-cases" / "shorten-url.yaml"
    )
    assert isinstance(target, UseCaseSpec)
    return {
        "specs_dir": str(specs_dir),
        "target_usecase": target,
    }
