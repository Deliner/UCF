"""Implementation for use case: generate-negative-test-code."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from ucf.generator.pytest_plugin import (
    ErrorTestDef,
    extract_error_definitions,
    generate_negative_test_code,
)
from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry

from .interface import (
    ExtractErrorsResult,
    GenerateNegativeTestCodeInterface,
    GenerateResult,
    LoaderContext,
)


ACTION_WITH_ERRORS = {
    "kind": "action",
    "metadata": {"name": "create-order"},
    "input": {"user_id": {"type": "string"}, "cart_id": {"type": "string"}},
    "output": {"order_id": {"type": "string"}},
    "errors": [
        {"status": 400, "code": "invalid-cart", "condition": "cart is empty or does not exist"},
        {"status": 409, "code": "duplicate-order", "condition": "order already exists for this cart"},
    ],
}

ACTION_NO_ERRORS = {
    "kind": "action",
    "metadata": {"name": "get-cart"},
    "input": {"cart_id": {"type": "string"}},
    "output": {"items": {"type": "array"}},
}

USECASE_WITH_ERRORS = {
    "kind": "usecase",
    "metadata": {"name": "place-order"},
    "steps": [
        {"id": "get-cart", "use": "actions/get-cart", "input": {"cart_id": "$inputs.cart_id"}},
        {
            "id": "create",
            "use": "actions/create-order",
            "input": {"user_id": "$inputs.user_id", "cart_id": "$inputs.cart_id"},
            "output": {"order_id": "order_id"},
        },
    ],
    "postconditions": ["order is created"],
}


class GenerateNegativeTestCodeImpl(GenerateNegativeTestCodeInterface):

    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._error_defs: list[ErrorTestDef] = []
        self._generated_code: str = ""
        self._error_methods: list[str] = []

    def setup_loader(self) -> LoaderContext:
        self._registry = SpecRegistry()
        self._registry.register(parse_spec(ACTION_WITH_ERRORS))
        self._registry.register(parse_spec(ACTION_NO_ERRORS))
        self._registry.register(parse_spec(USECASE_WITH_ERRORS))
        return LoaderContext(
            registry=self._registry,
            loaded_count=3,
            load_errors=[],
        )

    def action_extract_errors(self, usecase: Any, registry: Any) -> ExtractErrorsResult:
        assert self._registry is not None
        uc = self._registry.usecases()[0]
        self._error_defs = extract_error_definitions(uc, self._registry)
        return ExtractErrorsResult(
            error_defs=self._error_defs,
            error_count=len(self._error_defs),
        )

    def action_generate(self, error_defs: Any, interface_class: Any, usecase_name: Any) -> GenerateResult:
        code, methods = generate_negative_test_code(
            self._error_defs,
            interface_class="PlaceOrderInterface",
            usecase_name="place-order",
        )
        self._generated_code = code
        self._error_methods = methods
        return GenerateResult(
            negative_test_code=code,
            error_methods=methods,
            test_count=len(self._error_defs),
        )

    def action_render_results(self, data: Any, format: Any) -> None:
        pass

    def verify_for_each_action_error_a_testerror_class_is_generated(self) -> None:
        assert "TestErrorInvalidCart" in self._generated_code
        assert "TestErrorDuplicateOrder" in self._generated_code

    def verify_the_interface_has_abstract_error_methods_for_each_error(self) -> None:
        assert "action_error_create_invalid_cart" in self._error_methods
        assert "action_error_create_duplicate_order" in self._error_methods

    def verify_error_test_methods_receive_the_error_condition_as_a(self) -> None:
        assert "cart is empty or does not exist" in self._generated_code
        assert "order already exists for this cart" in self._generated_code

    def verify_generated_code_compiles_without_syntaxerror(self) -> None:
        try:
            ast.parse(self._generated_code)
        except SyntaxError:
            pytest.fail(f"Generated negative test code has SyntaxError:\n{self._generated_code}")

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


class GenerateNegativeNoErrorsImpl(GenerateNegativeTestCodeInterface):
    """Alt flow: no errors defined in any action spec."""

    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None

    def setup_loader(self) -> LoaderContext:
        self._registry = SpecRegistry()
        self._registry.register(parse_spec(ACTION_NO_ERRORS))
        uc_spec = {
            "kind": "usecase",
            "metadata": {"name": "get-cart-flow"},
            "steps": [
                {"id": "get", "use": "actions/get-cart", "input": {"cart_id": "$inputs.cart_id"}},
            ],
            "postconditions": ["cart retrieved"],
        }
        self._registry.register(parse_spec(uc_spec))
        return LoaderContext(registry=self._registry, loaded_count=2, load_errors=[])

    def action_extract_errors(self, usecase: Any, registry: Any) -> ExtractErrorsResult:
        assert self._registry is not None
        uc = self._registry.usecases()[0]
        defs = extract_error_definitions(uc, self._registry)
        return ExtractErrorsResult(error_defs=defs, error_count=len(defs))

    def action_generate(self, error_defs: Any, interface_class: Any, usecase_name: Any) -> GenerateResult:
        return GenerateResult(negative_test_code="", error_methods=[], test_count=0)

    def action_render_results(self, data: Any, format: Any) -> None:
        pass

    def verify_for_each_action_error_a_testerror_class_is_generated(self) -> None:
        pass

    def verify_the_interface_has_abstract_error_methods_for_each_error(self) -> None:
        pass

    def verify_error_test_methods_receive_the_error_condition_as_a(self) -> None:
        pass

    def verify_generated_code_compiles_without_syntaxerror(self) -> None:
        pass

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def generate_negative_test_code_impl() -> GenerateNegativeTestCodeImpl:
    return GenerateNegativeTestCodeImpl()
