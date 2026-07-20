"""Unit tests for GeneratorEngine and PytestPlugin."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ucf.generator.plugin import (
    GeneratedFile,
    GeneratorEngine,
    UnsupportedFeatureError,
    _safe_module_name,
)
from ucf.generator.pytest_plugin import PytestPlugin
from ucf.models.spec import parse_spec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]


ACTION_FOO = {
    "kind": "action",
    "metadata": {"name": "do-foo"},
    "input": {"x": {"type": "string"}},
    "output": {"y": {"type": "string"}},
}

USECASE_SIMPLE = {
    "kind": "usecase",
    "metadata": {"name": "simple-flow"},
    "steps": [
        {
            "id": "s1",
            "use": "actions/do-foo",
            "input": {"x": "$inputs.x"},
            "output": {"y": "y"},
        },
    ],
    "postconditions": ["y is produced"],
}


def _registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_FOO))
    r.register(parse_spec(USECASE_SIMPLE))
    return r


def _retry_registry(*, include_supported_usecase: bool = False) -> SpecRegistry:
    retry_usecase = {
        "kind": "usecase",
        "metadata": {"name": "retry-flow"},
        "steps": [
            {
                "id": "attempt",
                "use": "actions/do-foo",
                "retry": {
                    "max_attempts": 3,
                    "on_error": "temporary-failure",
                },
            }
        ],
    }
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    if include_supported_usecase:
        registry.register(parse_spec(USECASE_SIMPLE))
    registry.register(parse_spec(retry_usecase))
    return registry


class TestSafeModuleName:
    def test_kebab(self):
        assert _safe_module_name("my-flow") == "my_flow"

    def test_special_chars(self):
        assert _safe_module_name("bad/chars!") == "bad_chars_"

    def test_uppercase(self):
        assert _safe_module_name("MyFlow") == "myflow"


class TestPytestPlugin:
    def test_generate_interface(self):
        plugin = PytestPlugin()
        reg = _registry()
        uc = reg.usecases()[0]
        result = plugin.generate_interface(uc, reg)
        assert isinstance(result, GeneratedFile)
        assert result.path == "interface.py"
        assert result.overwrite is True
        assert "class SimpleFlowInterface(ABC, FrameworkActions):" in result.content
        assert "action_s1" in result.content

    def test_generate_orchestrator(self):
        plugin = PytestPlugin()
        reg = _registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        assert result.path == "test_orchestrator.py"
        assert result.overwrite is True
        assert "class TestHappyPath" in result.content
        assert "import pytest" in result.content

    def test_generate_impl_stub(self):
        plugin = PytestPlugin()
        reg = _registry()
        uc = reg.usecases()[0]
        result = plugin.generate_impl_stub(uc, reg)
        assert result.path == "impl.py"
        assert result.overwrite is False
        assert "NotImplementedError" in result.content
        assert "SimpleFlowImpl" in result.content

    def test_interface_has_dataclasses(self):
        plugin = PytestPlugin()
        reg = _registry()
        uc = reg.usecases()[0]
        result = plugin.generate_interface(uc, reg)
        assert "@dataclass(frozen=True)" in result.content


RENDER_ACTION = {
    "kind": "action",
    "metadata": {"name": "render-cli-output"},
    "input": {
        "data": {"type": "object"},
        "format": {"type": "string"},
    },
    "output": {},
}

VALIDATE_ACTION = {
    "kind": "action",
    "metadata": {"name": "validate-input"},
    "input": {"registry": {"type": "object"}},
    "output": {
        "issues": {"type": "array"},
        "count": {"type": "integer"},
    },
}

SHOW_ERROR_ACTION = {
    "kind": "action",
    "metadata": {"name": "show-error"},
    "input": {"message": {"type": "string"}},
    "output": {},
}

LOADED_REGISTRY_COMPONENT = {
    "kind": "component",
    "metadata": {"name": "loaded-registry"},
    "parameters": {
        "specs_dir": {"type": "string", "required": True},
    },
    "provides": {
        "registry": {"type": "object"},
    },
}

FIRST_COMPONENT = {
    "kind": "component",
    "metadata": {"name": "first-component"},
    "provides": {"value": {"type": "string"}},
}

SECOND_COMPONENT = {
    "kind": "component",
    "metadata": {"name": "second-component"},
    "parameters": {"source": {"type": "string", "required": True}},
    "provides": {"result": {"type": "string"}},
}

USECASE_NESTED_DICT = {
    "kind": "usecase",
    "metadata": {"name": "nested-dict-flow"},
    "steps": [
        {
            "id": "validate",
            "use": "actions/validate-input",
            "input": {"registry": "$inputs.registry"},
            "output": {"issues": "issues", "count": "count"},
        },
        {
            "id": "render",
            "use": "actions/render-cli-output",
            "input": {
                "data": {
                    "issues": "$steps.validate.issues",
                    "count": "$steps.validate.count",
                },
                "format": "table",
            },
        },
    ],
    "postconditions": ["output is rendered"],
}

USECASE_ALT_FLOW = {
    "kind": "usecase",
    "metadata": {"name": "alt-flow-scoping"},
    "steps": [
        {
            "id": "validate",
            "use": "actions/validate-input",
            "input": {"registry": "$inputs.registry"},
            "output": {"issues": "issues", "count": "count"},
        },
        {
            "id": "render",
            "use": "actions/render-cli-output",
            "input": {
                "data": {"issues": "$steps.validate.issues"},
                "format": "table",
            },
        },
    ],
    "postconditions": ["validation completes"],
    "alternative_flows": [
        {
            "name": "validation-fails",
            "trigger": "issues found",
            "steps": [
                {
                    "id": "render-errors",
                    "use": "actions/render-cli-output",
                    "input": {
                        "data": {"issues": "$steps.validate.issues"},
                        "format": "table",
                    },
                },
            ],
        },
    ],
}

USECASE_MULTI_DEP_ALT_FLOW = {
    "kind": "usecase",
    "metadata": {"name": "multi-dependency-alt-flow"},
    "steps": [
        {
            "id": "alpha",
            "use": "actions/do-foo",
            "input": {"x": "alpha"},
            "output": {"y": "alpha_value"},
        },
        {
            "id": "beta",
            "use": "actions/do-foo",
            "input": {"x": "beta"},
            "output": {"y": "beta_value"},
        },
    ],
    "postconditions": ["both values are produced"],
    "alternative_flows": [
        {
            "name": "render-values",
            "trigger": "diagnostics requested",
            "steps": [
                {
                    "id": "render-values",
                    "use": "actions/render-cli-output",
                    "input": {
                        "data": {
                            "alpha": "$steps.alpha.alpha_value",
                            "beta": "$steps.beta.beta_value",
                        },
                        "format": "table",
                    },
                },
            ],
        },
    ],
}

USECASE_EXPLICIT_DEP_ALT_FLOW = {
    "kind": "usecase",
    "metadata": {"name": "explicit-dependency-alt-flow"},
    "steps": [
        {
            "id": "alpha",
            "use": "actions/do-foo",
            "input": {"x": "alpha"},
            "output": {"y": "alpha_value"},
        },
        {
            "id": "beta",
            "use": "actions/do-foo",
            "depends_on": ["alpha"],
            "input": {"x": "beta"},
            "output": {"y": "beta_value"},
        },
    ],
    "postconditions": ["beta is produced after alpha"],
    "alternative_flows": [
        {
            "name": "render-beta",
            "trigger": "diagnostics requested",
            "steps": [
                {
                    "id": "render-beta",
                    "use": "actions/render-cli-output",
                    "input": {
                        "data": {"beta": "$steps.beta.beta_value"},
                        "format": "table",
                    },
                },
            ],
        },
    ],
}

USECASE_NORMALIZED_STEP_COLLISION = {
    "kind": "usecase",
    "metadata": {"name": "normalized-step-collision"},
    "steps": [
        {
            "id": "foo-bar",
            "use": "actions/do-foo",
            "input": {"x": "first"},
            "output": {"y": "first_value"},
        },
        {
            "id": "foo_bar",
            "use": "actions/do-foo",
            "input": {"x": "second"},
            "output": {"y": "second_value"},
        },
    ],
    "postconditions": ["both steps execute"],
}

USECASE_LONG_POSTCOND = {
    "kind": "usecase",
    "metadata": {"name": "long-postcond-flow"},
    "steps": [
        {
            "id": "s1",
            "use": "actions/do-foo",
            "input": {"x": "$inputs.x"},
            "output": {"y": "y"},
        },
    ],
    "postconditions": [
        "the generated interface file compiles without SyntaxError",
        (
            "all verify method names are readable and not truncated "
            "mid-word by the generator"
        ),
    ],
}


def _nested_dict_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(RENDER_ACTION))
    r.register(parse_spec(VALIDATE_ACTION))
    r.register(parse_spec(USECASE_NESTED_DICT))
    return r


def _alt_flow_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(RENDER_ACTION))
    r.register(parse_spec(VALIDATE_ACTION))
    r.register(parse_spec(USECASE_ALT_FLOW))
    return r


def _alt_only_action_registry() -> SpecRegistry:
    usecase = {
        **USECASE_SIMPLE,
        "metadata": {"name": "alt-only-action"},
        "alternative_flows": [
            {
                "name": "invalid-input",
                "trigger": "input is invalid",
                "steps": [
                    {
                        "id": "show-error",
                        "use": "actions/show-error",
                        "input": {"message": "invalid input"},
                    },
                ],
            },
        ],
    }
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    registry.register(parse_spec(SHOW_ERROR_ACTION))
    registry.register(parse_spec(usecase))
    return registry


def _multi_dependency_alt_registry() -> SpecRegistry:
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    registry.register(parse_spec(RENDER_ACTION))
    registry.register(parse_spec(USECASE_MULTI_DEP_ALT_FLOW))
    return registry


def _component_parameter_registry() -> SpecRegistry:
    usecase = {
        **USECASE_SIMPLE,
        "metadata": {"name": "component-parameter"},
        "requires": [
            {
                "$ref": "components/loaded-registry",
                "as": "loader",
                "params": {"specs_dir": "$inputs.specs_dir"},
            },
        ],
    }
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    registry.register(parse_spec(LOADED_REGISTRY_COMPONENT))
    registry.register(parse_spec(usecase))
    return registry


def _reverse_component_dependency_registry() -> SpecRegistry:
    usecase = {
        **USECASE_SIMPLE,
        "metadata": {"name": "component-dependency-order"},
        "requires": [
            {
                "$ref": "components/second-component",
                "as": "second",
                "params": {"source": "$first.value"},
            },
            {
                "$ref": "components/first-component",
                "as": "first",
                "params": {},
            },
        ],
    }
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    registry.register(parse_spec(FIRST_COMPONENT))
    registry.register(parse_spec(SECOND_COMPONENT))
    registry.register(parse_spec(usecase))
    return registry


def _explicit_dependency_alt_registry() -> SpecRegistry:
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    registry.register(parse_spec(RENDER_ACTION))
    registry.register(parse_spec(USECASE_EXPLICIT_DEP_ALT_FLOW))
    return registry


def _normalized_step_collision_registry() -> SpecRegistry:
    registry = SpecRegistry()
    registry.register(parse_spec(ACTION_FOO))
    registry.register(parse_spec(USECASE_NORMALIZED_STEP_COLLISION))
    return registry


def _long_postcond_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_FOO))
    r.register(parse_spec(USECASE_LONG_POSTCOND))
    return r


class TestNestedDictHandling:
    def test_dict_input_produces_keyword_arg(self):
        plugin = PytestPlugin()
        reg = _nested_dict_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        assert "data={" in result.content

    def test_dict_input_not_expanded_flat(self):
        plugin = PytestPlugin()
        reg = _nested_dict_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        lines = [
            line for line in result.content.splitlines() if "action_render" in line
        ]
        assert len(lines) >= 1
        assert "validate.issues, validate.count" not in lines[0]


class TestMethodNameTruncation:
    def test_names_not_cut_mid_word(self):
        plugin = PytestPlugin()
        reg = _long_postcond_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_interface(uc, reg)
        for line in result.content.splitlines():
            if "def verify_" in line:
                name = line.strip().split("(")[0].replace("def ", "")
                assert not name.endswith("_"), f"Name ends with underscore: {name}"
                last_word = name.split("_")[-1]
                assert len(last_word) >= 2, f"Last word too short (truncated?): {name}"

    def test_long_name_preserved_fully_or_at_word_boundary(self):
        from ucf.generator.pytest_plugin import _truncate_name

        raw = "the generated interface file compiles without SyntaxError"
        result = _truncate_name(raw)
        assert not result.endswith("_")
        assert "syntaxerror" in result


class TestAltFlowScoping:
    def test_alt_flow_replays_prerequisites(self):
        plugin = PytestPlugin()
        reg = _alt_flow_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        alt_section = result.content.split("TestAlt")[1]
        assert "action_validate" in alt_section, "Alt flow should replay validate step"

    def test_alt_flow_defines_before_use(self):
        import ast

        plugin = PytestPlugin()
        reg = _alt_flow_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        tree = ast.parse(result.content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Alt" in node.name:
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        defined: set[str] = set()
                        for stmt in ast.walk(method):
                            if isinstance(stmt, ast.Assign):
                                for t in stmt.targets:
                                    if isinstance(t, ast.Name):
                                        defined.add(t.id)
                            if isinstance(stmt, ast.Attribute) and isinstance(
                                stmt.value, ast.Name
                            ):
                                var = stmt.value.id
                                if (
                                    var not in ("self", "uc", "inputs")
                                    and var not in defined
                                ):
                                    pytest.fail(f"Alt flow uses undefined '{var}'")

    def test_alt_only_action_is_part_of_interface_and_impl_contract(self):
        plugin = PytestPlugin()
        registry = _alt_only_action_registry()
        usecase = registry.usecases()[0]

        interface = plugin.generate_interface(usecase, registry)
        impl = plugin.generate_impl_stub(usecase, registry)

        assert "def action_show_error(" in interface.content
        assert "def action_show_error(" in impl.content

    def test_repeated_action_ref_keeps_each_step_signature(self):
        plugin = PytestPlugin()
        registry = _alt_flow_registry()
        usecase = registry.usecases()[0]

        interface = plugin.generate_interface(usecase, registry)
        orchestrator = plugin.generate_orchestrator(usecase, registry)

        assert "def action_render_errors(" in interface.content
        alt_section = orchestrator.content.split("class TestAlt", 1)[1]
        assert "uc.action_render_errors(" in alt_section

    def test_prerequisite_order_is_stable_across_hash_seeds(self):
        script = (
            "from tests.unit.test_generator import "
            "_multi_dependency_alt_registry\n"
            "from ucf.generator.pytest_plugin import PytestPlugin\n"
            "registry = _multi_dependency_alt_registry()\n"
            "usecase = registry.usecases()[0]\n"
            "print(PytestPlugin().generate_orchestrator("
            "usecase, registry).content)\n"
        )
        outputs = set()
        for seed in range(1, 21):
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=PROJECT_ROOT,
                env={**os.environ, "PYTHONHASHSEED": str(seed)},
                check=True,
                capture_output=True,
                text=True,
            )
            outputs.add(result.stdout)

        assert len(outputs) == 1

    def test_alt_prerequisite_closure_includes_explicit_dependencies(self):
        plugin = PytestPlugin()
        registry = _explicit_dependency_alt_registry()
        usecase = registry.usecases()[0]

        orchestrator = plugin.generate_orchestrator(usecase, registry)
        alt_section = orchestrator.content.split("class TestAlt", 1)[1]

        assert alt_section.index("uc.action_alpha(") < alt_section.index(
            "uc.action_beta("
        )

    def test_normalized_step_name_collision_fails_explicitly(self):
        plugin = PytestPlugin()
        registry = _normalized_step_collision_registry()
        usecase = registry.usecases()[0]

        with pytest.raises(ValueError, match="normalize to the same Python name"):
            plugin.generate_interface(usecase, registry)


class TestComponentParameters:
    def test_required_component_parameters_are_explicitly_forwarded(self):
        plugin = PytestPlugin()
        registry = _component_parameter_registry()
        usecase = registry.usecases()[0]

        interface = plugin.generate_interface(usecase, registry)
        orchestrator = plugin.generate_orchestrator(usecase, registry)

        assert "specs_dir: Any," in interface.content
        assert "uc.setup_loader(" in orchestrator.content
        assert "specs_dir=inputs['specs_dir']," in orchestrator.content

    def test_component_setups_follow_binding_dependencies_not_yaml_order(self):
        plugin = PytestPlugin()
        registry = _reverse_component_dependency_registry()
        usecase = registry.usecases()[0]

        orchestrator = plugin.generate_orchestrator(usecase, registry)

        assert orchestrator.content.index(
            "uc.setup_first("
        ) < orchestrator.content.index("uc.setup_second(")


class TestGeneratorEngine:
    def test_pytest_generation_rejects_unimplemented_retry_semantics(self):
        registry = _retry_registry()
        usecase = registry.usecases()[0]

        with pytest.raises(
            ValueError,
            match=r"pytest.*retry-flow.*steps\.attempt\.retry",
        ):
            PytestPlugin().generate_orchestrator(usecase, registry)

    def test_generate_all_preflights_unsupported_features_before_writing(
        self, tmp_path
    ):
        output_dir = tmp_path / "generated"
        engine = GeneratorEngine(
            _retry_registry(include_supported_usecase=True),
            PytestPlugin(),
            output_dir,
        )

        with pytest.raises(ValueError, match="retry"):
            engine.generate_all()

        assert not output_dir.exists()

    def test_generate_all(self, tmp_path):
        reg = _registry()
        plugin = PytestPlugin()
        engine = GeneratorEngine(reg, plugin, tmp_path)
        results = engine.generate_all()
        assert len(results) == 1
        r = results[0]
        assert r.usecase_name == "simple-flow"
        assert len(r.files_written) == 3

        uc_dir = tmp_path / "simple_flow"
        assert (uc_dir / "interface.py").exists()
        assert (uc_dir / "test_orchestrator.py").exists()
        assert (uc_dir / "impl.py").exists()
        assert (uc_dir / "__init__.py").exists()

    def test_impl_not_overwritten(self, tmp_path):
        reg = _registry()
        plugin = PytestPlugin()
        engine = GeneratorEngine(reg, plugin, tmp_path)

        engine.generate_all()

        sentinel = "# DO NOT TOUCH"
        impl_path = tmp_path / "simple_flow" / "impl.py"
        impl_path.write_text(sentinel, encoding="utf-8")

        results = engine.generate_all()
        assert impl_path.read_text() == sentinel
        assert any("impl.py" in f for f in results[0].files_skipped)

    def test_encoding_utf8(self, tmp_path):
        reg = _registry()
        plugin = PytestPlugin()
        engine = GeneratorEngine(reg, plugin, tmp_path)
        engine.generate_all()
        content = (tmp_path / "simple_flow" / "interface.py").read_text(
            encoding="utf-8"
        )
        assert "interface" in content.lower()

    def test_generate_specific_usecase(self, tmp_path):
        reg = _registry()
        plugin = PytestPlugin()
        engine = GeneratorEngine(reg, plugin, tmp_path)
        uc = reg.usecases()[0]
        result = engine.generate_usecase(uc)
        assert result.usecase_name == "simple-flow"
        assert len(result.files_written) == 3

    def test_fresh_generated_package_collects(self, tmp_path):
        output_dir = tmp_path / "generated"
        engine = GeneratorEngine(_registry(), PytestPlugin(), output_dir)
        engine.generate_all()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "--no-cov",
                str(output_dir),
            ],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_generated_package_executes_with_explicit_input_fixture(self, tmp_path):
        output_dir = tmp_path / "generated"
        engine = GeneratorEngine(_registry(), PytestPlugin(), output_dir)
        engine.generate_all()

        usecase_dir = output_dir / "simple_flow"
        (usecase_dir / "impl.py").write_text(
            """\
from typing import Any

import pytest

from .interface import S1Result, SimpleFlowInterface


class SimpleFlowImpl(SimpleFlowInterface):
    def __init__(self) -> None:
        self.value: str | None = None

    def action_s1(self, x: Any) -> S1Result:
        self.value = str(x)
        return S1Result(y=self.value)

    def verify_y_is_produced(self) -> None:
        assert self.value == "fixture value"


@pytest.fixture
def simple_flow_impl() -> SimpleFlowImpl:
    return SimpleFlowImpl()
""",
            encoding="utf-8",
        )
        (usecase_dir / "conftest.py").write_text(
            """\
import pytest


@pytest.fixture
def inputs() -> dict[str, object]:
    return {"x": "fixture value"}
""",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-cov",
                str(output_dir),
            ],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_fresh_generated_sources_pass_ruff(self, tmp_path):
        output_dir = tmp_path / "generated"
        engine = GeneratorEngine(_registry(), PytestPlugin(), output_dir)
        engine.generate_all()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--config",
                str(PROJECT_ROOT / "pyproject.toml"),
                str(output_dir),
            ],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_complex_generated_sources_pass_ruff(self, tmp_path):
        output_dir = tmp_path / "generated"
        engine = GeneratorEngine(
            _nested_dict_registry(),
            PytestPlugin(),
            output_dir,
        )
        engine.generate_all()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--config",
                str(PROJECT_ROOT / "pyproject.toml"),
                str(output_dir),
            ],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_repository_generated_sources_pass_ruff(self, tmp_path):
        specs_dir = PROJECT_ROOT / "specs"
        loaded, _errors = SpecLoader(specs_dir).load_all_tolerant()
        registry = SpecRegistry()
        for _path, spec in loaded:
            registry.register(spec)

        output_dir = tmp_path / "generated"
        plugin = PytestPlugin()
        engine = GeneratorEngine(registry, plugin, output_dir)
        unsupported: list[tuple[str, tuple[str, ...]]] = []
        for usecase in registry.usecases():
            try:
                engine.generate_usecase(usecase)
            except UnsupportedFeatureError as exc:
                unsupported.append((usecase.metadata.name, exc.features))

        assert unsupported == [
            ("create-short-url-with-retry", ("steps.generate-slug.retry",))
        ]

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--config",
                str(PROJECT_ROOT / "pyproject.toml"),
                str(output_dir),
            ],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr

    def test_repository_orchestrator_calls_match_generated_interfaces(self):
        specs_dir = PROJECT_ROOT / "specs"
        loaded, _errors = SpecLoader(specs_dir).load_all_tolerant()
        registry = SpecRegistry()
        for _path, spec in loaded:
            registry.register(spec)

        plugin = PytestPlugin()
        mismatches: list[str] = []
        unsupported: list[tuple[str, tuple[str, ...]]] = []
        for usecase in registry.usecases():
            try:
                plugin.validate_spec(usecase, registry)
            except UnsupportedFeatureError as exc:
                unsupported.append((usecase.metadata.name, exc.features))
                continue
            interface = ast.parse(
                plugin.generate_interface(usecase, registry).content
            )
            orchestrator = ast.parse(
                plugin.generate_orchestrator(usecase, registry).content
            )
            method_params = {
                node.name: {
                    argument.arg
                    for argument in node.args.args
                    if argument.arg != "self"
                }
                for node in ast.walk(interface)
                if isinstance(node, ast.FunctionDef)
            }

            for node in ast.walk(orchestrator):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "uc"
                ):
                    continue
                method_name = node.func.attr
                expected = method_params.get(method_name)
                provided = {
                    keyword.arg
                    for keyword in node.keywords
                    if keyword.arg is not None
                }
                if expected is None or provided != expected or node.args:
                    mismatches.append(
                        f"{usecase.metadata.name}:{method_name} "
                        f"expected={expected} provided={provided} "
                        f"positional={len(node.args)}"
                    )

        assert mismatches == []
        assert unsupported == [
            ("create-short-url-with-retry", ("steps.generate-slug.retry",))
        ]


ACTION_WITH_ERRORS = {
    "kind": "action",
    "metadata": {"name": "submit-payment"},
    "input": {"amount": {"type": "integer"}},
    "output": {"txn_id": {"type": "string"}},
    "errors": [
        {
            "status": 400,
            "code": "invalid-amount",
            "condition": "amount is zero or negative",
        },
        {
            "status": 402,
            "code": "insufficient-funds",
            "condition": "account balance too low",
        },
    ],
}

USECASE_FOR_ERRORS = {
    "kind": "usecase",
    "metadata": {"name": "pay-flow"},
    "steps": [
        {
            "id": "pay",
            "use": "actions/submit-payment",
            "input": {"amount": "$inputs.amount"},
            "output": {"txn_id": "txn_id"},
        },
    ],
    "postconditions": ["payment processed"],
}


def _error_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_WITH_ERRORS))
    r.register(parse_spec(USECASE_FOR_ERRORS))
    return r


class TestExtractErrorDefinitions:
    def test_finds_errors_from_action_specs(self):
        from ucf.generator.pytest_plugin import extract_error_definitions

        reg = _error_registry()
        uc = reg.usecases()[0]
        defs = extract_error_definitions(uc, reg)
        assert len(defs) == 2
        codes = {d.error_code for d in defs}
        assert "invalid-amount" in codes
        assert "insufficient-funds" in codes

    def test_no_errors_for_clean_action(self):
        from ucf.generator.pytest_plugin import extract_error_definitions

        reg = _registry()
        uc = reg.usecases()[0]
        defs = extract_error_definitions(uc, reg)
        assert len(defs) == 0

    def test_error_includes_step_id(self):
        from ucf.generator.pytest_plugin import extract_error_definitions

        reg = _error_registry()
        uc = reg.usecases()[0]
        defs = extract_error_definitions(uc, reg)
        assert all(d.step_id == "pay" for d in defs)


USECASE_WITH_WHEN = {
    "kind": "usecase",
    "metadata": {"name": "conditional-flow"},
    "steps": [
        {
            "id": "step-a",
            "use": "actions/do-foo",
            "input": {"x": "$inputs.x"},
            "output": {"y": "value"},
        },
        {
            "id": "step-b",
            "use": "actions/do-foo",
            "when": "$steps.step-a.value > 10",
            "input": {"x": "conditional"},
            "output": {"y": "y"},
        },
    ],
    "postconditions": ["flow completes"],
}

USECASE_WITH_SKIP_IF = {
    "kind": "usecase",
    "metadata": {"name": "skip-if-flow"},
    "steps": [
        {
            "id": "check",
            "use": "actions/do-foo",
            "input": {"x": "a"},
            "output": {"y": "y"},
        },
        {
            "id": "maybe",
            "use": "actions/do-foo",
            "skip_if": "$steps.check.done",
            "input": {"x": "b"},
            "output": {"y": "y"},
        },
    ],
    "postconditions": ["done"],
}


def _when_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_FOO))
    r.register(parse_spec(USECASE_WITH_WHEN))
    return r


def _skip_if_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_FOO))
    r.register(parse_spec(USECASE_WITH_SKIP_IF))
    return r


class TestConditionalStepGeneration:
    """Tests for when/skip_if code generation in orchestrator."""

    def test_orchestrator_generates_if_else_for_when(self):
        """Generated test_orchestrator.py contains if/else block for step with when."""
        plugin = PytestPlugin()
        reg = _when_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        content = result.content
        # step-b has when: $steps.step-a.value > 10 -> step_a.value > 10
        assert "if step_a.value > 10:" in content
        assert "uc.action_step_b(" in content
        assert "step_b = uc.action_step_b(" not in content

    def test_orchestrator_with_when_produces_valid_python(self):
        """Generated code with when/skip_if parses as valid Python."""
        import ast

        plugin = PytestPlugin()
        reg = _when_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        ast.parse(result.content)

    def test_orchestrator_generates_if_else_for_skip_if(self):
        """The orchestrator uses an if-not branch for a step with skip_if."""
        plugin = PytestPlugin()
        reg = _skip_if_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        content = result.content
        assert "if not (check.done):" in content
        assert "uc.action_maybe(" in content
        assert "maybe = uc.action_maybe(" not in content


class TestGenerateNegativeTestCode:
    def test_produces_valid_python(self):
        import ast

        from ucf.generator.pytest_plugin import (
            ErrorTestDef,
            generate_negative_test_code,
        )

        defs = [
            ErrorTestDef("pay", "submit-payment", "invalid-amount", "amount <= 0", 400),
        ]
        code, methods = generate_negative_test_code(
            defs, "PayFlowInterface", "pay-flow"
        )
        ast.parse(code)

    def test_generates_test_class_per_error(self):
        from ucf.generator.pytest_plugin import (
            ErrorTestDef,
            generate_negative_test_code,
        )

        defs = [
            ErrorTestDef("pay", "submit-payment", "invalid-amount", "amount <= 0", 400),
            ErrorTestDef(
                "pay", "submit-payment", "insufficient-funds", "balance too low", 402
            ),
        ]
        code, methods = generate_negative_test_code(
            defs, "PayFlowInterface", "pay-flow"
        )
        assert "TestErrorInvalidAmount" in code
        assert "TestErrorInsufficientFunds" in code
        assert len(methods) == 2

    def test_includes_condition_in_docstring(self):
        from ucf.generator.pytest_plugin import (
            ErrorTestDef,
            generate_negative_test_code,
        )

        defs = [
            ErrorTestDef(
                "pay", "submit-payment", "bad-input", "input is malformed", 400
            ),
        ]
        code, _ = generate_negative_test_code(defs, "X", "y")
        assert "input is malformed" in code
