(
    "Spec-to-code mapper — builds bidirectional mappings between specs and "
    'implementations.\n\n@implements("actions/build-spec-code-map")\n'
)

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ucf.drift.scanner import ImplementationEntry
from ucf.parser.registry import SpecRegistry

_KIND_PLURALS = {
    "action": "actions",
    "event": "events",
    "component": "components",
    "protocol": "protocols",
    "usecase": "use-cases",
    "invariant": "invariants",
}

_SPEC_REF_RE = re.compile(
    r"^(?:(?:actions|events|components|protocols|use-cases|invariants)/)?(.+)$"
)


@dataclass
class SpecCodeMap:
    spec_to_code: dict[str, list[str]] = field(default_factory=dict)
    code_to_spec: dict[str, list[str]] = field(default_factory=dict)
    mapped_count: int = 0


class SpecCodeMapper:
    """Builds bidirectional spec↔code mappings from markers and conventions."""

    def __init__(
        self,
        registry: SpecRegistry,
        implementations: list[ImplementationEntry],
        convention: str | None = None,
    ) -> None:
        self.registry = registry
        self.implementations = implementations
        self.convention = convention

    def build(self) -> SpecCodeMap:
        result = SpecCodeMap()

        all_refs = self._all_spec_refs()
        for ref in all_refs:
            result.spec_to_code[ref] = []

        for entry in self.implementations:
            matched_ref = self._match_to_spec(entry.spec_ref, all_refs)
            if matched_ref:
                result.spec_to_code.setdefault(matched_ref, []).append(entry.file_path)
                result.code_to_spec.setdefault(entry.file_path, []).append(matched_ref)

        if self.convention:
            self._apply_convention(result, all_refs)

        result.mapped_count = sum(1 for paths in result.spec_to_code.values() if paths)

        return result

    def _all_spec_refs(self) -> set[str]:
        refs: set[str] = set()
        for spec in self.registry.all_specs():
            kind = spec.kind
            plural = _KIND_PLURALS.get(kind, f"{kind}s")
            refs.add(f"{plural}/{spec.metadata.name}")
        return refs

    def _match_to_spec(self, marker_ref: str, all_refs: set[str]) -> str | None:
        if marker_ref in all_refs:
            return marker_ref

        for ref in all_refs:
            ref_name = ref.split("/", 1)[-1]
            if marker_ref == ref_name:
                return ref

        marker_name = _SPEC_REF_RE.match(marker_ref)
        if marker_name:
            name = marker_name.group(1)
            for ref in all_refs:
                if ref.endswith(f"/{name}"):
                    return ref

        return None

    def _apply_convention(self, result: SpecCodeMap, all_refs: set[str]) -> None:
        """Apply path-convention matching for unmapped specs."""
        for ref in all_refs:
            if result.spec_to_code.get(ref):
                continue

            parts = ref.split("/", 1)
            if len(parts) != 2:
                continue

            kind_plural, name = parts
            snake_name = name.replace("-", "_")

            candidates = [
                f"src/ucf/{kind_plural[:-1]}/{snake_name}.py",
                f"src/{kind_plural}/{snake_name}.py",
                f"{kind_plural}/{snake_name}.py",
            ]

            for candidate in candidates:
                if candidate in result.code_to_spec:
                    continue
                full_path = Path(candidate)
                if full_path.exists():
                    result.spec_to_code[ref].append(candidate)
                    result.code_to_spec.setdefault(candidate, []).append(ref)
