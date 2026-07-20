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
from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import (
    ExtractErrorsResult,
    GenerateNegativeTestCodeInterface,
    GenerateResult,
    LoaderContext,
)


class GenerateNegativeTestCodeImpl(GenerateNegativeTestCodeInterface):
    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._error_defs: list[ErrorTestDef] = []
        self._generated_code: str = ""
        self._error_methods: list[str] = []
        self._rendered_results: tuple[Any, Any] | None = None

    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        loader = SpecLoader(Path(specs_dir))
        loaded, errors = loader.load_all_tolerant()

        self._registry = SpecRegistry()
        for path, spec in loaded:
            self._registry.register(spec, path)

        return LoaderContext(
            registry=self._registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_extract_errors(self, usecase: Any, registry: Any) -> ExtractErrorsResult:
        assert isinstance(usecase, UseCaseSpec)
        assert isinstance(registry, SpecRegistry)
        self._error_defs = extract_error_definitions(usecase, registry)
        return ExtractErrorsResult(
            error_defs=self._error_defs,
            error_count=len(self._error_defs),
        )

    def action_generate(
        self, error_defs: Any, interface_class: Any, usecase_name: Any
    ) -> GenerateResult:
        assert isinstance(error_defs, list)
        assert all(isinstance(error_def, ErrorTestDef) for error_def in error_defs)
        assert isinstance(interface_class, str) and interface_class
        assert isinstance(usecase_name, str) and usecase_name

        self._error_defs = error_defs
        code, methods = generate_negative_test_code(
            error_defs,
            interface_class=interface_class,
            usecase_name=usecase_name,
        )
        self._generated_code = code
        self._error_methods = methods
        return GenerateResult(
            negative_test_code=code,
            error_methods=methods,
            test_count=len(self._error_defs),
        )

    def action_render_results(self, data: Any, format: Any) -> None:
        self._rendered_results = (data, format)

    def action_render_empty(self, data: Any, format: Any) -> None:
        if self._error_defs:
            raise ValueError(
                "empty result cannot be rendered when errors were extracted"
            )
        self._rendered_results = (data, format)

    def verify_for_each_action_error_a_testerror_class_is_generated(self) -> None:
        for error_def in self._error_defs:
            class_suffix = "".join(
                word.capitalize() for word in error_def.error_code.split("-")
            )
            assert f"class TestError{class_suffix}:" in self._generated_code

    def verify_the_interface_has_abstract_error_methods_for_each_error(self) -> None:
        expected_methods = [
            "action_error_"
            f"{error_def.step_id.replace('-', '_')}_"
            f"{error_def.error_code.replace('-', '_')}"
            for error_def in self._error_defs
        ]
        assert self._error_methods == expected_methods

    def verify_error_test_methods_receive_the_error_condition_as_a(self) -> None:
        for error_def in self._error_defs:
            assert f'"""Condition: {error_def.condition}"""' in self._generated_code

    def verify_generated_code_compiles_without_syntaxerror(self) -> None:
        ast.parse(self._generated_code)

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def generate_negative_test_code_impl() -> GenerateNegativeTestCodeImpl:
    return GenerateNegativeTestCodeImpl()
