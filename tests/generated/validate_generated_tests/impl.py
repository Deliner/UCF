"""Implementation for use case: validate-generated-tests."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest

from ucf.generator.plugin import GeneratorEngine
from ucf.generator.pytest_plugin import PytestPlugin
from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import (
    GenerateResult,
    LoaderContext,
    ValidateGeneratedTestsInterface,
    ValidateResult,
)


class ValidateGeneratedTestsImpl(ValidateGeneratedTestsInterface):
    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._specs_dir: Path | None = None
        self._target_usecase: UseCaseSpec | None = None
        self._output_dir: Path | None = None
        self._interface_code: str = ""
        self._orchestrator_code: str = ""
        self._impl_code: str = ""
        self._issues: list[str] = []

    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        self._specs_dir = Path(specs_dir)
        loader = SpecLoader(self._specs_dir)
        loaded, errors = loader.load_all_tolerant()

        self._registry = SpecRegistry()
        for path, spec in loaded:
            self._registry.register(spec, path)

        return LoaderContext(
            registry=self._registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_generate(
        self, usecase: Any, registry: Any, output_dir: Any
    ) -> GenerateResult:
        assert isinstance(usecase, UseCaseSpec)
        assert isinstance(registry, SpecRegistry)
        assert registry is self._registry
        self._target_usecase = usecase
        self._output_dir = Path(output_dir)

        plugin = PytestPlugin()
        engine = GeneratorEngine(registry, plugin, self._output_dir)
        result = engine.generate_usecase(usecase)

        safe = usecase.metadata.name.replace("-", "_")
        uc_dir = self._output_dir / safe

        self._interface_code = (uc_dir / "interface.py").read_text(encoding="utf-8")
        self._orchestrator_code = (uc_dir / "test_orchestrator.py").read_text(
            encoding="utf-8"
        )
        self._impl_code = (uc_dir / "impl.py").read_text(encoding="utf-8")

        return GenerateResult(
            interface_path=str(uc_dir / "interface.py"),
            orchestrator_path=str(uc_dir / "test_orchestrator.py"),
            impl_path=str(uc_dir / "impl.py"),
            files_written=len(result.files_written),
        )

    def action_validate(
        self, interface_code: Any, orchestrator_code: Any, impl_code: Any
    ) -> ValidateResult:
        self._interface_code = Path(interface_code).read_text(encoding="utf-8")
        self._orchestrator_code = Path(orchestrator_code).read_text(encoding="utf-8")
        self._impl_code = Path(impl_code).read_text(encoding="utf-8")
        issues: list[str] = []

        for label, code in [
            ("interface.py", self._interface_code),
            ("test_orchestrator.py", self._orchestrator_code),
            ("impl.py", self._impl_code),
        ]:
            try:
                ast.parse(code)
            except SyntaxError as e:
                issues.append(f"{label}: SyntaxError at line {e.lineno}: {e.msg}")

        self._check_undefined_vars(self._orchestrator_code, issues)
        self._check_dict_inputs(self._orchestrator_code, issues)
        self._check_truncated_names(self._interface_code, issues)

        self._issues = issues
        return ValidateResult(
            is_valid=len(issues) == 0,
            issues=issues,
            issue_count=len(issues),
        )

    def _check_undefined_vars(self, code: str, issues: list[str]) -> None:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("TestAlt"):
                defined: set[str] = set()
                for stmt in node.body:
                    if isinstance(stmt, ast.FunctionDef):
                        for inner in ast.walk(stmt):
                            if isinstance(inner, ast.Assign):
                                for t in inner.targets:
                                    if isinstance(t, ast.Name):
                                        defined.add(t.id)
                            if isinstance(inner, ast.Attribute) and isinstance(
                                inner.value, ast.Name
                            ):
                                if (
                                    inner.value.id not in defined
                                    and inner.value.id not in ("self", "uc")
                                ):
                                    issues.append(
                                        f"Alt flow {node.name}: "
                                        f"references undefined '{inner.value.id}'"
                                    )

    def _check_dict_inputs(self, code: str, issues: list[str]) -> None:
        for match in re.finditer(r"uc\.\w+\(([^)]+)\)", code):
            args_str = match.group(1)
            if "data=" not in args_str and args_str.count(",") > 3:
                if "$" not in args_str:
                    issues.append(
                        f"Possible nested-dict expansion: {match.group(0)[:60]}..."
                    )

    def _check_truncated_names(self, code: str, issues: list[str]) -> None:
        for match in re.finditer(r"def (verify_\w+)\(", code):
            name = match.group(1)
            if name.endswith("_") or (len(name) > 50 and not name[-1].isalpha()):
                issues.append(f"Truncated method name: {name}")

    def action_render_results(self, data: Any, format: Any) -> None:
        assert format == "table"
        assert isinstance(data, dict)
        assert data["is_valid"] is True
        assert data["issues"] == []
        assert data["issue_count"] == 0

    def action_render_failures(self, data: Any, format: Any) -> None:
        assert format == "table"
        assert isinstance(data, dict)
        assert data["issues"]
        assert data["issue_count"] > 0

    def verify_generated_interface_py_compiles_without_syntaxerror(self) -> None:
        try:
            ast.parse(self._interface_code)
        except SyntaxError:
            pytest.fail("interface.py has SyntaxError")

    def verify_generated_test_orchestrator_py_compiles_without_syntaxerror(
        self,
    ) -> None:
        try:
            ast.parse(self._orchestrator_code)
        except SyntaxError:
            pytest.fail("test_orchestrator.py has SyntaxError")

    def verify_orchestrator_does_not_reference_undefined_variables(self) -> None:
        issues: list[str] = []
        self._check_undefined_vars(self._orchestrator_code, issues)
        assert not issues, f"Undefined variable references: {issues}"

    def verify_nested_dict_inputs_are_passed_as_single_dict_arguments(self) -> None:
        issues: list[str] = []
        self._check_dict_inputs(self._orchestrator_code, issues)
        assert not issues, f"Dict expansion issues: {issues}"

    def verify_verify_method_names_are_readable_and_not_truncated_mid_word(
        self,
    ) -> None:
        issues: list[str] = []
        self._check_truncated_names(self._interface_code, issues)
        assert not issues, f"Truncated names: {issues}"

    def verify_required_inputs_validated(self) -> None:
        assert self._specs_dir is not None
        assert self._specs_dir.is_dir()
        assert self._target_usecase is not None
        assert self._output_dir is not None
        assert self._output_dir.is_dir()


@pytest.fixture
def validate_generated_tests_impl() -> ValidateGeneratedTestsImpl:
    return ValidateGeneratedTestsImpl()
