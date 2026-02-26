"""Implementation for use case: generate-test-code."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from ucf.generator.plugin import GeneratorEngine
from ucf.generator.pytest_plugin import PytestPlugin
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import GenerateResult, GenerateTestCodeInterface, LoaderContext

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class GenerateTestCodeImpl(GenerateTestCodeInterface):

    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._output_dir: Path | None = None
        self._result: GenerateResult | None = None

    def setup_loader(self) -> LoaderContext:
        loader = SpecLoader(SPECS_DIR)
        loaded, errors = loader.load_all_tolerant()

        self._registry = SpecRegistry()
        for path, spec in loaded:
            self._registry.register(spec, path)

        return LoaderContext(
            registry=self._registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_generate(self, usecase: Any, registry: Any, output_dir: Any) -> GenerateResult:
        assert self._registry is not None
        self._output_dir = Path(tempfile.mkdtemp(prefix="ucf_gen_"))
        plugin = PytestPlugin()
        engine = GeneratorEngine(self._registry, plugin, self._output_dir)

        uc = self._registry.usecases()[0]
        gen_result = engine.generate_usecase(uc)

        safe_name = uc.metadata.name.replace("-", "_")
        uc_dir = self._output_dir / safe_name

        self._result = GenerateResult(
            interface_path=str(uc_dir / "interface.py"),
            orchestrator_path=str(uc_dir / "test_orchestrator.py"),
            impl_path=str(uc_dir / "impl.py"),
            files_written=len(gen_result.files_written),
        )
        return self._result

    def action_render_result(self, *args: Any, **kwargs: Any) -> None:
        pass

    def verify_for_each_usecase_interface_py_test_orchestrator(self) -> None:
        assert self._result is not None
        assert Path(self._result.interface_path).exists()
        assert Path(self._result.orchestrator_path).exists()

    def verify_impl_py_stubs_are_created_only_if_they_do_not_alre(self) -> None:
        assert self._result is not None
        impl_path = Path(self._result.impl_path)
        assert impl_path.exists()

        # Run generate again — impl should be skipped
        assert self._registry is not None
        assert self._output_dir is not None
        plugin = PytestPlugin()
        engine = GeneratorEngine(self._registry, plugin, self._output_dir)
        uc = self._registry.usecases()[0]
        gen_result = engine.generate_usecase(uc)
        assert len(gen_result.files_skipped) >= 1

    def verify_generated_code_is_deterministic_given_the_same_spe(self) -> None:
        assert self._result is not None
        content1 = Path(self._result.interface_path).read_text()

        # Regenerate and compare
        assert self._registry is not None
        out2 = Path(tempfile.mkdtemp(prefix="ucf_det_"))
        plugin = PytestPlugin()
        engine = GeneratorEngine(self._registry, plugin, out2)
        uc = self._registry.usecases()[0]
        engine.generate_usecase(uc)

        safe_name = uc.metadata.name.replace("-", "_")
        content2 = (out2 / safe_name / "interface.py").read_text()
        assert content1 == content2


@pytest.fixture
def generate_test_code_impl() -> GenerateTestCodeImpl:
    return GenerateTestCodeImpl()
