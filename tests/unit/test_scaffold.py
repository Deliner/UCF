"""Unit tests for scaffold scanner and generator."""

from __future__ import annotations

from pathlib import Path

import yaml

from ucf.scaffold.generator import SkeletonSpecGenerator, _to_kebab
from ucf.scaffold.scanner import ASTScanner, ClassInfo, FunctionInfo


class TestToKebab:
    def test_snake_case(self):
        assert _to_kebab("create_order") == "create-order"

    def test_camel_case(self):
        assert _to_kebab("CreateOrder") == "create-order"

    def test_already_kebab(self):
        assert _to_kebab("create-order") == "create-order"

    def test_mixed(self):
        assert _to_kebab("PaymentProcessor") == "payment-processor"

    def test_acronym(self):
        assert _to_kebab("HTMLParser") == "html-parser"


class TestASTScanner:
    def test_finds_public_functions(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "def hello(name: str) -> str:\n"
            '    """Greet someone."""\n'
            "    return f'hi {name}'\n"
            "\n"
            "def _private():\n"
            "    pass\n",
            encoding="utf-8",
        )
        scanner = ASTScanner(src)
        result = scanner.scan()
        assert result.scanned_count == 1
        assert len(result.functions) == 1
        assert result.functions[0].name == "hello"
        assert result.functions[0].return_type == "str"
        assert len(result.functions[0].params) == 1
        assert result.functions[0].params[0].name == "name"

    def test_excludes_private_functions(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "def _hidden():\n    pass\ndef __dunder():\n    pass\n",
            encoding="utf-8",
        )
        scanner = ASTScanner(src)
        result = scanner.scan()
        assert len(result.functions) == 0

    def test_finds_classes_with_methods(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "svc.py").write_text(
            "class OrderService:\n"
            '    """Manages orders."""\n'
            "\n"
            "    def __init__(self, db: str) -> None:\n"
            "        self.db = db\n"
            "\n"
            "    def create(self, item: str) -> dict:\n"
            '        """Create an order."""\n'
            "        return {}\n"
            "\n"
            "    def _internal(self) -> None:\n"
            "        pass\n",
            encoding="utf-8",
        )
        scanner = ASTScanner(src)
        result = scanner.scan()
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "OrderService"
        assert cls.docstring == "Manages orders."
        public_methods = [m for m in cls.methods if m.name != "__init__"]
        assert len(public_methods) == 1
        assert public_methods[0].name == "create"

    def test_handles_syntax_errors(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        (src / "good.py").write_text("def ok() -> None:\n    pass\n", encoding="utf-8")
        scanner = ASTScanner(src)
        result = scanner.scan()
        assert result.scanned_count == 2
        assert len(result.functions) == 1
        assert result.functions[0].name == "ok"

    def test_extracts_docstring(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            'def greet():\n    """Say hello to the world."""\n    pass\n',
            encoding="utf-8",
        )
        scanner = ASTScanner(src)
        result = scanner.scan()
        assert result.functions[0].docstring == "Say hello to the world."

    def test_custom_patterns(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            "def found() -> None:\n    pass\n", encoding="utf-8"
        )
        (src / "script.txt").write_text(
            "def not_found() -> None:\n    pass\n", encoding="utf-8"
        )
        scanner = ASTScanner(src, patterns=["*.py"])
        result = scanner.scan()
        assert len(result.functions) == 1
        assert result.functions[0].name == "found"

    def test_empty_directory(self, tmp_path: Path):
        src = tmp_path / "empty"
        src.mkdir()
        scanner = ASTScanner(src)
        result = scanner.scan()
        assert result.scanned_count == 0
        assert len(result.functions) == 0
        assert len(result.classes) == 0


class TestSkeletonSpecGenerator:
    def test_generates_action_from_function(self, tmp_path: Path):
        gen = SkeletonSpecGenerator(tmp_path)
        funcs = [
            FunctionInfo(
                name="create_order",
                params=[],
                return_type="str",
                docstring="Create a new order.",
                file_path="orders.py",
                line=1,
            )
        ]
        result = gen.generate(funcs, [])
        assert result.specs_written == 1
        assert len(result.action_specs) == 1

        spec_path = Path(result.action_specs[0])
        data = yaml.safe_load(spec_path.read_text())
        assert data["kind"] == "action"
        assert data["metadata"]["name"] == "create-order"

    def test_generates_component_from_class(self, tmp_path: Path):
        from ucf.scaffold.scanner import MethodInfo as ScannerMethodInfo

        gen = SkeletonSpecGenerator(tmp_path)
        classes = [
            ClassInfo(
                name="PaymentProcessor",
                methods=[
                    ScannerMethodInfo(name="charge", return_type="dict"),
                    ScannerMethodInfo(name="refund", return_type="bool"),
                ],
                docstring="Handles payments.",
                file_path="payments.py",
                line=1,
            )
        ]
        result = gen.generate([], classes)
        assert result.specs_written == 1
        assert len(result.component_specs) == 1

        spec_path = Path(result.component_specs[0])
        data = yaml.safe_load(spec_path.read_text())
        assert data["kind"] == "component"
        assert "charge" in data["provides"]
        assert "refund" in data["provides"]

    def test_does_not_overwrite_existing(self, tmp_path: Path):
        actions_dir = tmp_path / "actions"
        actions_dir.mkdir(parents=True)
        existing = actions_dir / "create-order.yaml"
        existing.write_text("# original", encoding="utf-8")

        gen = SkeletonSpecGenerator(tmp_path)
        funcs = [FunctionInfo(name="create_order")]
        result = gen.generate(funcs, [])
        assert result.specs_written == 0
        assert existing.read_text() == "# original"

    def test_maps_python_types_to_ucf(self, tmp_path: Path):
        from ucf.scaffold.scanner import ParamInfo

        gen = SkeletonSpecGenerator(tmp_path)
        funcs = [
            FunctionInfo(
                name="process",
                params=[
                    ParamInfo(name="name", annotation="str"),
                    ParamInfo(name="count", annotation="int"),
                    ParamInfo(name="active", annotation="bool"),
                    ParamInfo(name="items", annotation="list"),
                ],
                return_type="dict",
            )
        ]
        result = gen.generate(funcs, [])
        spec_path = Path(result.action_specs[0])
        data = yaml.safe_load(spec_path.read_text())
        assert data["input"]["name"]["type"] == "string"
        assert data["input"]["count"]["type"] == "integer"
        assert data["input"]["active"]["type"] == "boolean"
        assert data["input"]["items"]["type"] == "array"
        assert data["output"]["result"]["type"] == "object"

    def test_skips_class_without_public_methods(self, tmp_path: Path):
        gen = SkeletonSpecGenerator(tmp_path)
        classes = [
            ClassInfo(
                name="Empty",
                methods=[],
                file_path="empty.py",
                line=1,
            )
        ]
        result = gen.generate([], classes)
        assert result.specs_written == 0
        assert len(result.component_specs) == 0
