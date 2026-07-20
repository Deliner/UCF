"""Unit tests for the drift module (scanner, mapper, detector)."""

from __future__ import annotations

from ucf.drift.detector import DriftDetector
from ucf.drift.mapper import SpecCodeMap, SpecCodeMapper
from ucf.drift.scanner import ImplementationEntry, SourceScanner
from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry


def _action(name: str = "my-action"):
    return parse_spec({"kind": "action", "metadata": {"name": name}})


def _registry(*names: str) -> SpecRegistry:
    r = SpecRegistry()
    for n in names:
        r.register(_action(n))
    return r


class TestSourceScanner:
    def test_finds_decorator_marker(self, tmp_path):
        (tmp_path / "handler.py").write_text(
            '@implements("actions/create-order")\ndef create_order(): pass\n',
            encoding="utf-8",
        )
        scanner = SourceScanner(tmp_path)
        result = scanner.scan()
        assert result.scanned_count == 1
        assert result.marker_count == 1
        assert result.implementations[0].spec_ref == "actions/create-order"
        assert result.implementations[0].line_number == 1

    def test_finds_comment_marker(self, tmp_path):
        (tmp_path / "service.py").write_text(
            '# @implements("actions/validate-spec")\nclass Validator: pass\n',
            encoding="utf-8",
        )
        scanner = SourceScanner(tmp_path)
        result = scanner.scan()
        assert result.marker_count == 1
        assert result.implementations[0].spec_ref == "actions/validate-spec"

    def test_multiple_markers_in_one_file(self, tmp_path):
        (tmp_path / "multi.py").write_text(
            '@implements("actions/a")\n'
            "def a(): pass\n\n"
            '@implements("actions/b")\n'
            "def b(): pass\n",
            encoding="utf-8",
        )
        scanner = SourceScanner(tmp_path)
        result = scanner.scan()
        assert result.marker_count == 2
        refs = {e.spec_ref for e in result.implementations}
        assert refs == {"actions/a", "actions/b"}

    def test_no_markers(self, tmp_path):
        (tmp_path / "clean.py").write_text("def clean(): pass\n", encoding="utf-8")
        scanner = SourceScanner(tmp_path)
        result = scanner.scan()
        assert result.scanned_count == 1
        assert result.marker_count == 0

    def test_custom_pattern(self, tmp_path):
        (tmp_path / "lib.js").write_text(
            '// @implements("actions/foo")\n',
            encoding="utf-8",
        )
        (tmp_path / "lib.py").write_text("pass\n", encoding="utf-8")
        scanner = SourceScanner(tmp_path, patterns=["**/*.js"])
        result = scanner.scan()
        assert result.scanned_count == 1

    def test_relative_paths(self, tmp_path):
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "handler.py").write_text(
            '@implements("actions/x")\ndef x(): pass\n',
            encoding="utf-8",
        )
        scanner = SourceScanner(tmp_path)
        result = scanner.scan()
        assert result.implementations[0].file_path == "pkg/handler.py"


class TestSpecCodeMapper:
    def test_maps_marker_to_spec(self):
        reg = _registry("create-order")
        impls = [ImplementationEntry("handler.py", "actions/create-order", 1)]
        mapper = SpecCodeMapper(reg, impls)
        result = mapper.build()
        assert result.mapped_count == 1
        assert "handler.py" in result.spec_to_code["actions/create-order"]

    def test_maps_by_name_only(self):
        reg = _registry("validate-spec")
        impls = [ImplementationEntry("v.py", "validate-spec", 5)]
        mapper = SpecCodeMapper(reg, impls)
        result = mapper.build()
        assert result.mapped_count == 1

    def test_unmapped_spec(self):
        reg = _registry("create-order", "delete-order")
        impls = [ImplementationEntry("handler.py", "actions/create-order", 1)]
        mapper = SpecCodeMapper(reg, impls)
        result = mapper.build()
        assert result.mapped_count == 1
        assert result.spec_to_code["actions/delete-order"] == []

    def test_bidirectional(self):
        reg = _registry("x")
        impls = [ImplementationEntry("x.py", "actions/x", 1)]
        mapper = SpecCodeMapper(reg, impls)
        result = mapper.build()
        assert "x.py" in result.code_to_spec
        assert "actions/x" in result.code_to_spec["x.py"]

    def test_no_implementations(self):
        reg = _registry("a", "b")
        mapper = SpecCodeMapper(reg, [])
        result = mapper.build()
        assert result.mapped_count == 0
        assert len(result.spec_to_code) == 2


class TestDriftDetector:
    def test_finds_unimplemented(self):
        reg = _registry("create-order", "delete-order")
        spec_map = SpecCodeMap(
            spec_to_code={
                "actions/create-order": ["handler.py"],
                "actions/delete-order": [],
            },
            code_to_spec={"handler.py": ["actions/create-order"]},
        )
        detector = DriftDetector(reg, spec_map)
        result = detector.detect()
        assert len(result.unimplemented_specs) == 1
        assert result.unimplemented_specs[0].ref == "actions/delete-order"

    def test_finds_orphan_code(self):
        reg = _registry("create-order")
        spec_map = SpecCodeMap(
            spec_to_code={"actions/create-order": ["handler.py"]},
            code_to_spec={
                "handler.py": ["actions/create-order"],
                "old.py": ["actions/removed-action"],
            },
        )
        detector = DriftDetector(reg, spec_map)
        result = detector.detect()
        assert len(result.orphan_code) == 1
        assert "old.py" in result.orphan_code[0].ref

    def test_drift_count_sums(self):
        reg = _registry("a")
        spec_map = SpecCodeMap(
            spec_to_code={"actions/a": []},
            code_to_spec={"orphan.py": ["actions/gone"]},
        )
        detector = DriftDetector(reg, spec_map)
        result = detector.detect()
        assert result.drift_count == 2

    def test_no_drift(self):
        reg = _registry("x")
        spec_map = SpecCodeMap(
            spec_to_code={"actions/x": ["x.py"]},
            code_to_spec={"x.py": ["actions/x"]},
        )
        detector = DriftDetector(reg, spec_map)
        result = detector.detect()
        assert result.drift_count == 0
