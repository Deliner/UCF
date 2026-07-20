"""Executable inputs for the detect-spec-code-drift generated tests."""

from pathlib import Path

import pytest

CREATE_ORDER_SPEC = """\
kind: action
metadata:
  name: create-order
input:
  item: {type: string}
output:
  order_id: {type: string}
"""

CONFIRM_ORDER_SPEC = """\
kind: action
metadata:
  name: confirm-order
input:
  order_id: {type: string}
output:
  confirmed: {type: boolean}
"""

CREATE_ORDER_SOURCE = """\
# @implements("actions/create-order")
def create_order(item: str) -> str:
    return "order-1"
"""


@pytest.fixture
def inputs(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> dict[str, object]:
    specs_dir = tmp_path / "specs"
    actions_dir = specs_dir / "actions"
    actions_dir.mkdir(parents=True)
    (actions_dir / "create-order.yaml").write_text(
        CREATE_ORDER_SPEC,
        encoding="utf-8",
    )
    if request.node.cls.__name__ != "TestAltNoDriftFound":
        (actions_dir / "confirm-order.yaml").write_text(
            CONFIRM_ORDER_SPEC,
            encoding="utf-8",
        )

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "create_order.py").write_text(
        CREATE_ORDER_SOURCE,
        encoding="utf-8",
    )

    return {
        "specs_dir": specs_dir,
        "source_dir": source_dir,
        "convention": "specs/{kind}/{name}.yaml -> src/{kind}/{name}.py",
    }
