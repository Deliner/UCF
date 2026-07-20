"""Explicit inputs for generate-negative-test-code scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucf.parser.loader import SpecLoader


@pytest.fixture
def inputs(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> dict[str, object]:
    specs_dir = tmp_path / "specs"
    actions_dir = specs_dir / "actions"
    usecases_dir = specs_dir / "use-cases"
    actions_dir.mkdir(parents=True)
    usecases_dir.mkdir()

    (actions_dir / "create-order.yaml").write_text(
        """\
kind: action
metadata:
  name: create-order
input:
  user_id:
    type: string
  cart_id:
    type: string
output:
  order_id:
    type: string
errors:
  - status: 400
    code: invalid-cart
    condition: cart is empty or does not exist
  - status: 409
    code: duplicate-order
    condition: order already exists for this cart
""",
        encoding="utf-8",
    )
    (actions_dir / "get-cart.yaml").write_text(
        """\
kind: action
metadata:
  name: get-cart
input:
  cart_id:
    type: string
output:
  items:
    type: array
""",
        encoding="utf-8",
    )
    (usecases_dir / "place-order.yaml").write_text(
        """\
kind: usecase
metadata:
  name: place-order
steps:
  - id: get-cart
    use: actions/get-cart
    input:
      cart_id: $inputs.cart_id
  - id: create
    use: actions/create-order
    input:
      user_id: $inputs.user_id
      cart_id: $inputs.cart_id
    output:
      order_id: order_id
postconditions:
  - order is created
""",
        encoding="utf-8",
    )
    (usecases_dir / "get-cart-flow.yaml").write_text(
        """\
kind: usecase
metadata:
  name: get-cart-flow
steps:
  - id: get
    use: actions/get-cart
    input:
      cart_id: $inputs.cart_id
postconditions:
  - cart is retrieved
""",
        encoding="utf-8",
    )

    usecase_name = (
        "get-cart-flow"
        if request.node.cls is not None
        and request.node.cls.__name__ == "TestAltNoErrorsDefined"
        else "place-order"
    )
    loader = SpecLoader(specs_dir)
    target_usecase = loader.load_file(usecases_dir / f"{usecase_name}.yaml")

    return {
        "specs_dir": specs_dir,
        "target_usecase": target_usecase,
        "interface_class": "PlaceOrderInterface",
        "usecase_name": usecase_name,
    }
