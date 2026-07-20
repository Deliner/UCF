"""Implementation for use case: scaffold-specs-from-code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from ucf.scaffold.generator import SkeletonSpecGenerator, SpecGenResult
from ucf.scaffold.scanner import ASTScanner, ASTScanResult

from .interface import (
    GenerateResult,
    ScaffoldSpecsFromCodeInterface,
    ScanDefaultsResult,
    ScanResult,
)


class ScaffoldSpecsFromCodeImpl(ScaffoldSpecsFromCodeInterface):
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self._scan: ASTScanResult | None = None
        self._gen: SpecGenResult | None = None
        self._output_dir = tmp_path / "specs_out"
        self._setup_source()

    def _setup_source(self) -> None:
        src = self.tmp_path / "src"
        src.mkdir(exist_ok=True)

        (src / "orders.py").write_text(
            "def create_order(item: str, quantity: int) -> str:\n"
            '    """Create a new order for the given item."""\n'
            '    return "order-1"\n'
            "\n"
            "def _internal_helper():\n"
            "    pass\n"
            "\n"
            "def cancel_order(order_id: str) -> bool:\n"
            '    """Cancel an existing order."""\n'
            "    return True\n",
            encoding="utf-8",
        )

        (src / "payments.py").write_text(
            "class PaymentProcessor:\n"
            '    """Handles payment processing."""\n'
            "\n"
            "    def __init__(self, api_key: str) -> None:\n"
            "        self.api_key = api_key\n"
            "\n"
            "    def charge(self, amount: float, currency: str) -> dict:\n"
            '        """Charge a payment method."""\n'
            '        return {"id": "txn-1"}\n'
            "\n"
            "    def refund(self, transaction_id: str) -> bool:\n"
            '        """Refund a previous transaction."""\n'
            "        return True\n"
            "\n"
            "    def _validate(self) -> None:\n"
            "        pass\n",
            encoding="utf-8",
        )

        self._source_dir = src

    def action_scan(self, source_dir: Any, patterns: Any) -> ScanResult:
        source_path = Path(source_dir)
        selected_patterns = list(patterns) if patterns else ["**/*.py"]
        scanner = ASTScanner(source_path, selected_patterns)
        self._source_dir = source_path
        self._scan = scanner.scan()
        return ScanResult(
            functions=self._scan.functions,
            classes=self._scan.classes,
            scanned_count=self._scan.scanned_count,
        )

    def action_generate(
        self, functions: Any, classes: Any, output_dir: Any
    ) -> GenerateResult:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        gen = SkeletonSpecGenerator(self._output_dir)
        self._gen = gen.generate(functions, classes)
        return GenerateResult(
            action_specs=self._gen.action_specs,
            component_specs=self._gen.component_specs,
            specs_written=self._gen.specs_written,
        )

    def action_render_results(self, data: Any, format: Any) -> None:
        assert format == "tree"
        assert isinstance(data, dict)
        if "message" in data:
            assert data == {
                "message": "no Python code found in source directory",
                "scanned_count": 0,
            }
        else:
            assert data["scanned_count"] >= 2
            assert data["specs_written"] >= 3

    def action_scan_defaults(self, source_dir: Any) -> ScanDefaultsResult:
        scan = self.action_scan(source_dir, ["**/*.py"])
        return ScanDefaultsResult(
            functions=scan.functions,
            classes=scan.classes,
            scanned_count=scan.scanned_count,
        )

    def action_render_empty(self, data: Any, format: Any) -> None:
        self.action_render_results(data, format)

    def verify_every_public_function_in_the_source_directory_has_a(self) -> None:
        assert self._scan is not None
        assert self._gen is not None
        public_funcs = {f.name for f in self._scan.functions}
        generated_actions = set()
        for path_str in self._gen.action_specs:
            name = Path(path_str).stem
            generated_actions.add(name)

        for func_name in public_funcs:
            kebab = func_name.replace("_", "-")
            assert kebab in generated_actions, (
                f"Function '{func_name}' has no action spec (expected '{kebab}')"
            )

    def verify_every_class_with_public_methods_has_a_corresponding(self) -> None:
        from ucf.scaffold.generator import _to_kebab

        assert self._scan is not None
        assert self._gen is not None
        for cls in self._scan.classes:
            public_methods = [m for m in cls.methods if m.name != "__init__"]
            if public_methods:
                generated_names = {Path(p).stem for p in self._gen.component_specs}
                expected = _to_kebab(cls.name)
                assert expected in generated_names, (
                    f"Class '{cls.name}' has no component spec (expected '{expected}')"
                )

    def verify_generated_specs_are_valid_yaml_that_passes_ucf_validate(self) -> None:
        assert self._gen is not None
        all_paths = self._gen.action_specs + self._gen.component_specs
        for path_str in all_paths:
            path = Path(path_str)
            assert path.exists(), f"Spec not written: {path}"
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            assert isinstance(data, dict), f"Not a YAML dict: {path}"
            assert "kind" in data, f"Missing 'kind': {path}"
            assert "metadata" in data, f"Missing 'metadata': {path}"
            assert data["metadata"].get("name"), f"Missing 'metadata.name': {path}"

    def verify_existing_specs_are_never_overwritten(self) -> None:
        assert self._gen is not None
        sentinel_dir = self._output_dir / "actions"
        sentinel_dir.mkdir(parents=True, exist_ok=True)
        sentinel = sentinel_dir / "create-order.yaml"
        sentinel.write_text("# sentinel — do not overwrite", encoding="utf-8")

        gen2 = SkeletonSpecGenerator(self._output_dir)
        assert self._scan is not None
        gen2.generate(self._scan.functions, self._scan.classes)
        assert sentinel.read_text() == "# sentinel — do not overwrite"

    def verify_output_reports_the_number_of_files_scanned_and_specs(self) -> None:
        assert self._scan is not None
        assert self._gen is not None
        assert self._scan.scanned_count >= 2
        assert self._gen.specs_written >= 3

    def verify_required_inputs_validated(self) -> None:
        assert self._source_dir.is_dir()
        assert self._output_dir.is_dir()


class ScaffoldEmptyImpl(ScaffoldSpecsFromCodeInterface):
    """Variant with an empty source directory — alt flow."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self._source_dir = tmp_path / "empty_src"
        self._source_dir.mkdir()
        self._scan: ASTScanResult | None = None
        self._gen: SpecGenResult | None = None
        self._output_dir = tmp_path / "empty_specs_out"

    def action_scan(self, source_dir: Any, patterns: Any) -> ScanResult:
        source_path = Path(source_dir)
        selected_patterns = list(patterns) if patterns else ["**/*.py"]
        scanner = ASTScanner(source_path, selected_patterns)
        self._source_dir = source_path
        self._scan = scanner.scan()
        return ScanResult(
            functions=self._scan.functions,
            classes=self._scan.classes,
            scanned_count=self._scan.scanned_count,
        )

    def action_generate(
        self, functions: Any, classes: Any, output_dir: Any
    ) -> GenerateResult:
        self._output_dir = Path(output_dir)
        self._gen = SkeletonSpecGenerator(self._output_dir).generate(
            functions,
            classes,
        )
        return GenerateResult(
            action_specs=self._gen.action_specs,
            component_specs=self._gen.component_specs,
            specs_written=self._gen.specs_written,
        )

    def action_render_results(self, data: Any, format: Any) -> None:
        assert format == "tree"
        assert data == {
            "message": "no Python code found in source directory",
            "scanned_count": 0,
        }

    def action_scan_defaults(self, source_dir: Any) -> ScanDefaultsResult:
        scan = self.action_scan(source_dir, ["**/*.py"])
        return ScanDefaultsResult(
            functions=scan.functions,
            classes=scan.classes,
            scanned_count=scan.scanned_count,
        )

    def action_render_empty(self, data: Any, format: Any) -> None:
        self.action_render_results(data, format)

    def verify_every_public_function_in_the_source_directory_has_a(self) -> None:
        assert self._scan is not None
        assert len(self._scan.functions) == 0

    def verify_every_class_with_public_methods_has_a_corresponding(self) -> None:
        assert self._scan is not None
        assert len(self._scan.classes) == 0

    def verify_generated_specs_are_valid_yaml_that_passes_ucf_validate(self) -> None:
        assert self._gen is not None
        assert self._gen.action_specs == []
        assert self._gen.component_specs == []

    def verify_existing_specs_are_never_overwritten(self) -> None:
        sentinel_dir = self._output_dir / "actions"
        sentinel_dir.mkdir(parents=True, exist_ok=True)
        sentinel = sentinel_dir / "sentinel.yaml"
        sentinel.write_text("existing: true\n", encoding="utf-8")
        assert self._scan is not None
        SkeletonSpecGenerator(self._output_dir).generate(
            self._scan.functions,
            self._scan.classes,
        )
        assert sentinel.read_text(encoding="utf-8") == "existing: true\n"

    def verify_output_reports_the_number_of_files_scanned_and_specs(self) -> None:
        assert self._scan is not None
        assert self._scan.scanned_count == 0

    def verify_required_inputs_validated(self) -> None:
        assert self._source_dir.is_dir()


@pytest.fixture
def scaffold_specs_from_code_impl(tmp_path: Path) -> ScaffoldSpecsFromCodeImpl:
    return ScaffoldSpecsFromCodeImpl(tmp_path)
