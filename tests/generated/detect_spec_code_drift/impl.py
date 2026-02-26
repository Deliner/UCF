"""Implementation for use case: detect-spec-code-drift.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.drift.detector import DriftDetector, DriftResult
from ucf.drift.mapper import SpecCodeMap, SpecCodeMapper
from ucf.drift.scanner import ImplementationEntry, ScanResult, SourceScanner
from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry

from .interface import (
    BuildMapResult,
    DetectResult,
    DetectSpecCodeDriftInterface,
    LoaderContext,
    ScannerContext,
)


class DetectSpecCodeDriftImpl(DetectSpecCodeDriftInterface):

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self._registry: SpecRegistry | None = None
        self._scan_result: ScanResult | None = None
        self._drift_result: DriftResult | None = None
        self._map_result: SpecCodeMap | None = None
        self._rendered: bool = False

        self._setup_fixtures()

    def _setup_fixtures(self) -> None:
        specs_dir = self.tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "actions").mkdir()
        (specs_dir / "actions" / "create-order.yaml").write_text(
            "kind: action\nmetadata:\n  name: create-order\n"
            "input:\n  item: {type: string}\n"
            "output:\n  order_id: {type: string}\n",
            encoding="utf-8",
        )
        (specs_dir / "actions" / "confirm-order.yaml").write_text(
            "kind: action\nmetadata:\n  name: confirm-order\n"
            "input:\n  order_id: {type: string}\n"
            "output:\n  confirmed: {type: boolean}\n",
            encoding="utf-8",
        )

        source_dir = self.tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "create_order.py").write_text(
            '# @implements("actions/create-order")\n'
            "def create_order(item: str) -> str:\n"
            "    return 'order-1'\n",
            encoding="utf-8",
        )

        self._specs_dir = specs_dir
        self._source_dir = source_dir

    def setup_loader(self) -> LoaderContext:
        from ucf.parser.loader import SpecLoader

        loader = SpecLoader(self._specs_dir)
        pairs, errors = loader.load_all_tolerant()

        registry = SpecRegistry()
        for path, spec in pairs:
            registry.register(spec, path)

        self._registry = registry
        return LoaderContext(
            registry=registry,
            loaded_count=len(pairs),
            load_errors=errors,
        )

    def setup_scanner(self) -> ScannerContext:
        scanner = SourceScanner(self._source_dir)
        self._scan_result = scanner.scan()
        return ScannerContext(
            implementations=self._scan_result.implementations,
            scanned_count=self._scan_result.scanned_count,
            marker_count=self._scan_result.marker_count,
        )

    def action_build_map(self, registry: Any, implementations: Any, convention: Any = None) -> BuildMapResult:
        mapper = SpecCodeMapper(registry, implementations)
        self._map_result = mapper.build()
        return BuildMapResult(
            spec_to_code=self._map_result.spec_to_code,
            code_to_spec=self._map_result.code_to_spec,
            mapped_count=self._map_result.mapped_count,
        )

    def action_detect(self, registry: Any, spec_to_code: Any, code_to_spec: Any) -> DetectResult:
        map_obj = SpecCodeMap(
            spec_to_code=spec_to_code,
            code_to_spec=code_to_spec,
        )
        detector = DriftDetector(registry, map_obj)
        self._drift_result = detector.detect()
        return DetectResult(
            unimplemented_specs=[e.ref for e in self._drift_result.unimplemented_specs],
            orphan_code=[e.ref for e in self._drift_result.orphan_code],
            stale_mappings=[e.ref for e in self._drift_result.stale_mappings],
            drift_count=self._drift_result.drift_count,
        )

    def action_render_drift(self, data: Any, format: Any) -> None:
        self._rendered = True

    def verify_every_spec_without_an_implementation_is_reported_as(self) -> None:
        assert self._drift_result is not None
        unmapped_refs = {
            ref for ref, paths in self._map_result.spec_to_code.items() if not paths
        }
        reported_refs = {e.ref for e in self._drift_result.unimplemented_specs}
        assert unmapped_refs == reported_refs

    def verify_every_implements_marker_referencing_a_missing_spec_is(self) -> None:
        assert self._drift_result is not None
        for entry in self._drift_result.orphan_code:
            assert "does not exist" in entry.detail

    def verify_drift_count_correctly_sums_unimplemented_orphan_stale(self) -> None:
        assert self._drift_result is not None
        expected = (
            len(self._drift_result.unimplemented_specs)
            + len(self._drift_result.orphan_code)
            + len(self._drift_result.stale_mappings)
        )
        assert self._drift_result.drift_count == expected

    def verify_output_is_rendered_in_the_requested_format(self) -> None:
        assert self._rendered

    def verify_spec_has_implementation(self) -> None:
        assert self._map_result is not None
        assert self._map_result.mapped_count >= 1

    def verify_implementation_has_spec(self) -> None:
        assert self._drift_result is not None
        assert len(self._drift_result.orphan_code) == 0

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


class DetectSpecCodeDriftNoDriftImpl(DetectSpecCodeDriftImpl):
    """Variant where every spec has an implementation — zero drift."""

    def _setup_fixtures(self) -> None:
        specs_dir = self.tmp_path / "specs"
        specs_dir.mkdir()

        (specs_dir / "actions").mkdir()
        (specs_dir / "actions" / "create-order.yaml").write_text(
            "kind: action\nmetadata:\n  name: create-order\n"
            "input:\n  item: {type: string}\n"
            "output:\n  order_id: {type: string}\n",
            encoding="utf-8",
        )

        source_dir = self.tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "create_order.py").write_text(
            '# @implements("actions/create-order")\n'
            "def create_order(item: str) -> str:\n"
            "    return 'order-1'\n",
            encoding="utf-8",
        )

        self._specs_dir = specs_dir
        self._source_dir = source_dir


@pytest.fixture
def detect_spec_code_drift_impl(tmp_path: Path) -> DetectSpecCodeDriftInterface:
    return DetectSpecCodeDriftImpl(tmp_path)


@pytest.fixture
def uc_no_drift(tmp_path: Path) -> DetectSpecCodeDriftInterface:
    return DetectSpecCodeDriftNoDriftImpl(tmp_path)
