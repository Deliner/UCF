"""YAML spec loader with $ref resolution.

@implements("actions/load-yaml-file")
@implements("actions/resolve-refs")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ucf.models.spec import AnySpec, SpecParseError, parse_spec

_LOGICAL_REF_KINDS = {
    "action": "action",
    "actions": "action",
    "event": "event",
    "events": "event",
    "component": "component",
    "components": "component",
    "protocol": "protocol",
    "protocols": "protocol",
    "usecase": "usecase",
    "use-cases": "usecase",
    "invariant": "invariant",
    "invariants": "invariant",
}
_LOGICAL_REF_DIRECTORIES = {
    "action": "actions",
    "actions": "actions",
    "event": "events",
    "events": "events",
    "component": "components",
    "components": "components",
    "protocol": "protocols",
    "protocols": "protocols",
    "usecase": "use-cases",
    "use-cases": "use-cases",
    "invariant": "invariants",
    "invariants": "invariants",
}


class RefResolutionError(Exception):
    def __init__(self, ref: object, source: str, reason: str) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f"Cannot resolve '$ref: {ref}' in {source}: {reason}")


class SpecLoader:
    """Loads YAML spec files and resolves $ref references."""

    MAX_REF_DEPTH = 3

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._file_cache: dict[Path, dict] = {}

    def load_file(self, path: Path) -> AnySpec:
        raw = self._read_yaml(path)
        resolved = self._resolve_refs(raw, path, depth=0)
        return parse_spec(resolved, source_path=str(path))

    def load_all(self, pattern: str = "**/*.yaml") -> list[tuple[Path, AnySpec]]:
        results: list[tuple[Path, AnySpec]] = []
        errors: list[SpecParseError] = []

        for yaml_path in self._spec_paths(pattern):
            try:
                spec = self.load_file(yaml_path)
                results.append((yaml_path, spec))
            except (SpecParseError, RefResolutionError, yaml.YAMLError) as exc:
                errors.append(SpecParseError(str(exc), path=str(yaml_path)))

        if errors:
            msg_parts = [f"  - {e.path}: {e}" for e in errors]
            raise SpecParseError(
                f"Failed to load {len(errors)} spec(s):\n" + "\n".join(msg_parts)
            )

        return results

    def load_all_tolerant(
        self, pattern: str = "**/*.yaml"
    ) -> tuple[list[tuple[Path, AnySpec]], list[SpecParseError]]:
        """Load all specs, returning both successes and errors."""
        results: list[tuple[Path, AnySpec]] = []
        errors: list[SpecParseError] = []

        for yaml_path in self._spec_paths(pattern):
            try:
                spec = self.load_file(yaml_path)
                results.append((yaml_path, spec))
            except (SpecParseError, RefResolutionError, yaml.YAMLError) as exc:
                errors.append(SpecParseError(str(exc), path=str(yaml_path)))

        return results, errors

    def _spec_paths(self, pattern: str) -> list[Path]:
        paths = set(self.base_dir.rglob(pattern))
        if pattern == "**/*.yaml":
            paths.update(self.base_dir.rglob("**/*.yml"))
        return sorted(paths)

    def _read_yaml(self, path: Path) -> dict:
        resolved = path.resolve()
        if resolved in self._file_cache:
            return self._file_cache[resolved]

        if not resolved.exists():
            raise SpecParseError(f"File not found: {path}", path=str(path))

        with open(resolved, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise SpecParseError(
                f"Expected YAML mapping, got {type(data).__name__}",
                path=str(path),
            )

        self._file_cache[resolved] = data
        return data

    def _resolve_refs(self, data: Any, source: Path, depth: int) -> Any:
        if depth >= self.MAX_REF_DEPTH:
            raise RefResolutionError(
                "<nested>",
                str(source),
                f"Maximum $ref depth ({self.MAX_REF_DEPTH}) exceeded",
            )

        if isinstance(data, dict):
            if "$ref" in data and len(data) == 1:
                return self._load_ref(data["$ref"], source, depth)
            return {k: self._resolve_refs(v, source, depth) for k, v in data.items()}

        if isinstance(data, list):
            return [self._resolve_refs(item, source, depth) for item in data]

        return data

    def _load_ref(self, ref: object, source: Path, depth: int) -> Any:
        if not isinstance(ref, str):
            raise RefResolutionError(
                ref,
                str(source),
                f"$ref must be a string, got {type(ref).__name__}",
            )
        ref_path = self._resolve_ref_path(ref, source)

        if not ref_path.exists():
            raise RefResolutionError(ref, str(source), f"File not found: {ref_path}")

        raw = self._read_yaml(ref_path)
        self._validate_logical_ref_identity(ref, raw, source)
        return self._resolve_refs(raw, ref_path, depth + 1)

    def _validate_logical_ref_identity(
        self,
        ref: str,
        raw: dict,
        source: Path,
    ) -> None:
        if ref.endswith((".yaml", ".yml")):
            return

        parts = ref.split("/")
        if len(parts) != 2:
            return
        expected_kind = _LOGICAL_REF_KINDS.get(parts[0])
        if expected_kind is None:
            return

        metadata = raw.get("metadata")
        actual_kind = raw.get("kind")
        actual_name = metadata.get("name") if isinstance(metadata, dict) else None
        if actual_kind == expected_kind and actual_name == parts[1]:
            return

        raise RefResolutionError(
            ref,
            str(source),
            "Logical identity mismatch: "
            f"expected {expected_kind}/{parts[1]}, "
            f"loaded {actual_kind}/{actual_name}",
        )

    def _resolve_ref_path(self, ref: str, source: Path) -> Path:
        if ref.endswith(".yaml") or ref.endswith(".yml"):
            candidate = source.parent / ref
        else:
            parts = ref.split("/")
            if len(parts) == 2 and parts[0] in _LOGICAL_REF_DIRECTORIES:
                ref = f"{_LOGICAL_REF_DIRECTORIES[parts[0]]}/{parts[1]}"
            candidates = [
                self.base_dir / f"{ref}.yaml",
                source.parent / f"{ref}.yaml",
                self.base_dir / f"{ref}.yml",
                source.parent / f"{ref}.yml",
            ]
            candidate = next(
                (path for path in candidates if path.exists()),
                candidates[0],
            )

        resolved = candidate.resolve()
        base_resolved = self.base_dir.resolve()
        if (
            not str(resolved).startswith(str(base_resolved) + "/")
            and resolved != base_resolved
        ):
            raise RefResolutionError(
                ref,
                str(source),
                f"$ref resolves outside base directory: {resolved}",
            )
        return resolved
