"""Concrete inputs for validating generated conditional-flow tests."""

from pathlib import Path

import pytest

from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader


@pytest.fixture
def inputs(
    request: pytest.FixtureRequest,
    specs_dir: Path,
    tmp_path: Path,
) -> dict[str, object]:
    target = SpecLoader(specs_dir).load_file(
        specs_dir / "use-cases" / "test-conditional-flow.yaml"
    )
    assert isinstance(target, UseCaseSpec)
    output_dir = tmp_path / "generated"
    if request.node.name == "test_validation_failures":
        target_dir = output_dir / "test_conditional_flow"
        target_dir.mkdir(parents=True)
        (target_dir / "impl.py").write_text(
            "def invalid_python(:\n",
            encoding="utf-8",
        )
    return {
        "specs_dir": str(specs_dir),
        "target_usecase": target,
        "output_dir": str(output_dir),
    }
