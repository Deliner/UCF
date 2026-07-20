"""Implementation for use case: generate-test-code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.generator.plugin import GeneratorEngine
from ucf.generator.pytest_plugin import PytestPlugin
from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import GenerateResult, GenerateTestCodeInterface, LoaderContext


class GenerateTestCodeImpl(GenerateTestCodeInterface):
    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._target_usecase: UseCaseSpec | None = None
        self._output_dir: Path | None = None
        self._result: GenerateResult | None = None
        self._rendered_result: tuple[Any, Any] | None = None

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

    def action_generate(
        self, usecase: Any, registry: Any, output_dir: Any
    ) -> GenerateResult:
        assert isinstance(usecase, UseCaseSpec)
        assert isinstance(registry, SpecRegistry)

        self._target_usecase = usecase
        self._registry = registry
        self._output_dir = Path(output_dir)
        plugin = PytestPlugin()
        engine = GeneratorEngine(registry, plugin, self._output_dir)

        gen_result = engine.generate_usecase(usecase)
        generated_paths = {
            Path(path).name: Path(path) for path in gen_result.files_written
        }

        expected_names = {"interface.py", "test_orchestrator.py", "impl.py"}
        assert expected_names <= generated_paths.keys()

        self._result = GenerateResult(
            interface_path=str(generated_paths["interface.py"]),
            orchestrator_path=str(generated_paths["test_orchestrator.py"]),
            impl_path=str(generated_paths["impl.py"]),
            files_written=len(gen_result.files_written),
        )
        return self._result

    def action_render_result(self, data: Any, format: Any) -> None:
        self._rendered_result = (data, format)

    def verify_for_each_usecase_interface_py_test_orchestrator_py_are(self) -> None:
        assert self._result is not None
        assert Path(self._result.interface_path).exists()
        assert Path(self._result.orchestrator_path).exists()

    def verify_impl_py_stubs_are_created_only_if_they_do_not_already_exist(
        self,
    ) -> None:
        assert self._result is not None
        impl_path = Path(self._result.impl_path)
        assert impl_path.exists()

        # Run generate again — impl should be skipped
        assert self._registry is not None
        assert self._output_dir is not None
        assert self._target_usecase is not None
        plugin = PytestPlugin()
        engine = GeneratorEngine(self._registry, plugin, self._output_dir)
        content_before = impl_path.read_text(encoding="utf-8")
        gen_result = engine.generate_usecase(self._target_usecase)
        assert str(impl_path) in gen_result.files_skipped
        assert impl_path.read_text(encoding="utf-8") == content_before

    def verify_generated_code_is_deterministic_given_the_same_spec_input(self) -> None:
        assert self._result is not None
        assert self._registry is not None
        assert self._target_usecase is not None
        assert self._output_dir is not None

        first_paths = {
            "interface.py": Path(self._result.interface_path),
            "test_orchestrator.py": Path(self._result.orchestrator_path),
            "impl.py": Path(self._result.impl_path),
        }
        first_contents = {
            name: path.read_text(encoding="utf-8")
            for name, path in first_paths.items()
        }

        out2 = self._output_dir.parent / f"{self._output_dir.name}-determinism"
        assert not out2.exists()
        plugin = PytestPlugin()
        engine = GeneratorEngine(self._registry, plugin, out2)
        gen_result = engine.generate_usecase(self._target_usecase)
        second_paths = {
            Path(path).name: Path(path) for path in gen_result.files_written
        }

        assert first_contents == {
            name: second_paths[name].read_text(encoding="utf-8")
            for name in first_contents
        }

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def generate_test_code_impl() -> GenerateTestCodeImpl:
    return GenerateTestCodeImpl()
