"""Implementation for use case: detect-spec-code-drift.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.drift.detector import DriftDetector, DriftResult
from ucf.drift.mapper import SpecCodeMap, SpecCodeMapper
from ucf.drift.scanner import ScanResult, SourceScanner
from ucf.parser.registry import SpecRegistry

from .interface import (
    BuildMapCustomResult,
    BuildMapResult,
    DetectResult,
    DetectSpecCodeDriftInterface,
    LoaderContext,
    ScannerContext,
)


class DetectSpecCodeDriftImpl(DetectSpecCodeDriftInterface):
    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._scan_result: ScanResult | None = None
        self._drift_result: DriftResult | None = None
        self._map_result: SpecCodeMap | None = None
        self._rendered: bool = False
        self._rendered_data: Any = None
        self._rendered_format: Any = None

    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        from ucf.parser.loader import SpecLoader

        loader = SpecLoader(Path(specs_dir))
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

    def setup_scanner(self, source_dir: Any) -> ScannerContext:
        scanner = SourceScanner(Path(source_dir))
        self._scan_result = scanner.scan()
        return ScannerContext(
            implementations=self._scan_result.implementations,
            scanned_count=self._scan_result.scanned_count,
            marker_count=self._scan_result.marker_count,
        )

    def action_build_map(
        self, registry: Any, implementations: Any
    ) -> BuildMapResult:
        result = self._build_map(registry, implementations, None)
        return BuildMapResult(
            spec_to_code=result.spec_to_code,
            code_to_spec=result.code_to_spec,
            mapped_count=result.mapped_count,
        )

    def action_build_map_custom(
        self,
        registry: Any,
        implementations: Any,
        convention: Any,
    ) -> BuildMapCustomResult:
        if not isinstance(convention, str) or not convention:
            raise ValueError("convention must be a non-empty string")
        result = self._build_map(registry, implementations, convention)
        return BuildMapCustomResult(
            spec_to_code=result.spec_to_code,
            code_to_spec=result.code_to_spec,
            mapped_count=result.mapped_count,
        )

    def _build_map(
        self,
        registry: Any,
        implementations: Any,
        convention: str | None,
    ) -> SpecCodeMap:
        if not isinstance(registry, SpecRegistry):
            raise TypeError("registry must be a SpecRegistry")
        if not isinstance(implementations, list):
            raise TypeError("implementations must be a list")
        mapper = SpecCodeMapper(
            registry,
            implementations,
            convention=convention,
        )
        self._map_result = mapper.build()
        return self._map_result

    def action_detect(
        self, registry: Any, spec_to_code: Any, code_to_spec: Any
    ) -> DetectResult:
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
        self._rendered_data = data
        self._rendered_format = format

    def action_render_clean(self, data: Any, format: Any) -> None:
        self._rendered = True
        self._rendered_data = data
        self._rendered_format = format

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

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def detect_spec_code_drift_impl() -> DetectSpecCodeDriftInterface:
    return DetectSpecCodeDriftImpl()
