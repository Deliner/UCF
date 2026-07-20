"""Executable inputs for the compose-use-cases generated tests."""

from pathlib import Path

import pytest

from ucf.parser.loader import SpecLoader

PARENT_SPEC = """\
kind: usecase
metadata:
  name: parent-uc
  version: 0.1.0
steps:
  - id: p-step1
    use: actions/load
    input: {}
    output: {data: data}
  - id: p-step2
    use: actions/transform
    input: {}
    output: {result: result}
postconditions:
  - data is loaded
  - result is computed
"""

CHILD_SPEC = """\
kind: usecase
metadata:
  name: child-uc
  version: 0.1.0
extends: $ref:use-cases/parent-uc
steps:
  - id: c-step1
    use: actions/render
    input: {}
    output: {view: view}
postconditions:
  - view is rendered
  - result is computed
"""


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, object]:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "parent.yaml").write_text(PARENT_SPEC, encoding="utf-8")
    child_path = specs_dir / "child.yaml"
    child_path.write_text(CHILD_SPEC, encoding="utf-8")
    child = SpecLoader(specs_dir).load_file(child_path)
    return {"specs_dir": specs_dir, "usecase": child}
