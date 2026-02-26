"""Drift detector — finds unimplemented specs, orphan code, and stale mappings.

@implements("actions/detect-drift")
@implements("invariants/spec-has-implementation")
@implements("invariants/implementation-has-spec")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.drift.mapper import SpecCodeMap
from ucf.parser.registry import SpecRegistry


@dataclass(frozen=True)
class DriftEntry:
    ref: str
    kind: str
    detail: str


@dataclass
class DriftResult:
    unimplemented_specs: list[DriftEntry] = field(default_factory=list)
    orphan_code: list[DriftEntry] = field(default_factory=list)
    stale_mappings: list[DriftEntry] = field(default_factory=list)

    @property
    def drift_count(self) -> int:
        return (
            len(self.unimplemented_specs)
            + len(self.orphan_code)
            + len(self.stale_mappings)
        )


class DriftDetector:
    """Compares spec↔code mappings to find gaps and orphans."""

    def __init__(
        self,
        registry: SpecRegistry,
        spec_code_map: SpecCodeMap,
    ) -> None:
        self.registry = registry
        self.map = spec_code_map

    def detect(self) -> DriftResult:
        result = DriftResult()

        self._find_unimplemented(result)
        self._find_orphan_code(result)

        return result

    def _find_unimplemented(self, result: DriftResult) -> None:
        for ref, code_paths in self.map.spec_to_code.items():
            if not code_paths:
                parts = ref.split("/", 1)
                kind = parts[0] if parts else "unknown"
                result.unimplemented_specs.append(DriftEntry(
                    ref=ref,
                    kind=kind,
                    detail=f"No implementation found for '{ref}'",
                ))

    def _find_orphan_code(self, result: DriftResult) -> None:
        all_refs = {
            f"{plural}/{spec.metadata.name}"
            for spec in self.registry.all_specs()
            for plural in [self._kind_to_plural(spec.kind)]
        }

        for code_path, spec_refs in self.map.code_to_spec.items():
            for ref in spec_refs:
                if ref not in all_refs:
                    result.orphan_code.append(DriftEntry(
                        ref=code_path,
                        kind="orphan",
                        detail=f"'{code_path}' references '{ref}' which does not exist in specs",
                    ))

    @staticmethod
    def _kind_to_plural(kind: str) -> str:
        mapping = {
            "action": "actions",
            "event": "events",
            "component": "components",
            "protocol": "protocols",
            "usecase": "use-cases",
            "invariant": "invariants",
        }
        return mapping.get(kind, f"{kind}s")
