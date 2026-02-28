"""Unit tests for GeneratorEngine and PytestPlugin."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucf.generator.plugin import GeneratedFile, GenerationResult, GeneratorEngine, _safe_module_name
from ucf.generator.pytest_plugin import PytestPlugin
from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry


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
        {"id": "s1", "use": "actions/do-foo", "input": {"x": "$inputs.x"}, "output": {"y": "y"}},
    ],
    "postconditions": ["y is produced"],
}


def _registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_FOO))
    r.register(parse_spec(USECASE_SIMPLE))
    return r


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
        assert "class SimpleFlowInterface(ABC)" in result.content
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

USECASE_LONG_POSTCOND = {
    "kind": "usecase",
    "metadata": {"name": "long-postcond-flow"},
    "steps": [
        {"id": "s1", "use": "actions/do-foo", "input": {"x": "$inputs.x"}, "output": {"y": "y"}},
    ],
    "postconditions": [
        "the generated interface file compiles without SyntaxError",
        "all verify method names are readable and not truncated mid-word by the generator",
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
        lines = [l for l in result.content.splitlines() if "action_render" in l]
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
                            if isinstance(stmt, ast.Attribute) and isinstance(stmt.value, ast.Name):
                                var = stmt.value.id
                                if var not in ("self", "uc") and var not in defined:
                                    pytest.fail(
                                        f"Alt flow uses undefined '{var}'"
                                    )


class TestGeneratorEngine:
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
        content = (tmp_path / "simple_flow" / "interface.py").read_text(encoding="utf-8")
        assert "interface" in content.lower()

    def test_generate_specific_usecase(self, tmp_path):
        reg = _registry()
        plugin = PytestPlugin()
        engine = GeneratorEngine(reg, plugin, tmp_path)
        uc = reg.usecases()[0]
        result = engine.generate_usecase(uc)
        assert result.usecase_name == "simple-flow"
        assert len(result.files_written) == 3


ACTION_WITH_ERRORS = {
    "kind": "action",
    "metadata": {"name": "submit-payment"},
    "input": {"amount": {"type": "integer"}},
    "output": {"txn_id": {"type": "string"}},
    "errors": [
        {"status": 400, "code": "invalid-amount", "condition": "amount is zero or negative"},
        {"status": 402, "code": "insufficient-funds", "condition": "account balance too low"},
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


def _when_registry() -> SpecRegistry:
    r = SpecRegistry()
    r.register(parse_spec(ACTION_FOO))
    r.register(parse_spec(USECASE_WITH_WHEN))
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
        assert "step_b = uc.action_step_b(" in content
        assert "else:" in content
        assert "step_b = None" in content

    def test_orchestrator_with_when_produces_valid_python(self):
        """Generated code with when/skip_if parses as valid Python."""
        import ast

        plugin = PytestPlugin()
        reg = _when_registry()
        uc = reg.usecases()[0]
        result = plugin.generate_orchestrator(uc, reg)
        ast.parse(result.content)

    def test_orchestrator_generates_if_else_for_skip_if(self):
        """Generated test_orchestrator.py contains if not (...) for step with skip_if."""
        usecase_skip_if = {
            "kind": "usecase",
            "metadata": {"name": "skip-if-flow"},
            "steps": [
                {"id": "check", "use": "actions/do-foo", "input": {"x": "a"}, "output": {"y": "y"}},
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
        r = SpecRegistry()
        r.register(parse_spec(ACTION_FOO))
        r.register(parse_spec(usecase_skip_if))
        plugin = PytestPlugin()
        uc = r.usecases()[0]
        result = plugin.generate_orchestrator(uc, r)
        content = result.content
        assert "if not (check.done):" in content
        assert "maybe = uc.action_maybe(" in content
        assert "maybe = None" in content


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
        code, methods = generate_negative_test_code(defs, "PayFlowInterface", "pay-flow")
        ast.parse(code)

    def test_generates_test_class_per_error(self):
        from ucf.generator.pytest_plugin import (
            ErrorTestDef,
            generate_negative_test_code,
        )

        defs = [
            ErrorTestDef("pay", "submit-payment", "invalid-amount", "amount <= 0", 400),
            ErrorTestDef("pay", "submit-payment", "insufficient-funds", "balance too low", 402),
        ]
        code, methods = generate_negative_test_code(defs, "PayFlowInterface", "pay-flow")
        assert "TestErrorInvalidAmount" in code
        assert "TestErrorInsufficientFunds" in code
        assert len(methods) == 2

    def test_includes_condition_in_docstring(self):
        from ucf.generator.pytest_plugin import (
            ErrorTestDef,
            generate_negative_test_code,
        )

        defs = [
            ErrorTestDef("pay", "submit-payment", "bad-input", "input is malformed", 400),
        ]
        code, _ = generate_negative_test_code(defs, "X", "y")
        assert "input is malformed" in code
