"""YAML spec loader with $ref resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ucf.models.spec import AnySpec, SpecParseError, parse_spec


class RefResolutionError(Exception):
    def __init__(self, ref: str, source: str, reason: str) -> None:
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

        for yaml_path in sorted(self.base_dir.rglob(pattern)):
            try:
                spec = self.load_file(yaml_path)
                results.append((yaml_path, spec))
            except (SpecParseError, RefResolutionError) as exc:
                errors.append(
                    SpecParseError(str(exc), path=str(yaml_path))
                )

        if errors:
            msg_parts = [f"  - {e.path}: {e}" for e in errors]
            raise SpecParseError(
                f"Failed to load {len(errors)} spec(s):\n" + "\n".join(msg_parts)
            )

        return results

    def load_all_tolerant(self, pattern: str = "**/*.yaml") -> tuple[
        list[tuple[Path, AnySpec]], list[SpecParseError]
    ]:
        """Load all specs, returning both successes and errors."""
        results: list[tuple[Path, AnySpec]] = []
        errors: list[SpecParseError] = []

        for yaml_path in sorted(self.base_dir.rglob(pattern)):
            try:
                spec = self.load_file(yaml_path)
                results.append((yaml_path, spec))
            except (SpecParseError, RefResolutionError, yaml.YAMLError) as exc:
                errors.append(SpecParseError(str(exc), path=str(yaml_path)))

        return results, errors

    def _read_yaml(self, path: Path) -> dict:
        resolved = path.resolve()
        if resolved in self._file_cache:
            return self._file_cache[resolved]

        if not resolved.exists():
            raise SpecParseError(f"File not found: {path}", path=str(path))

        with open(resolved) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise SpecParseError(
                f"Expected YAML mapping, got {type(data).__name__}",
                path=str(path),
            )

        self._file_cache[resolved] = data
        return data

    def _resolve_refs(self, data: Any, source: Path, depth: int) -> Any:
        if depth > self.MAX_REF_DEPTH:
            raise RefResolutionError(
                "<nested>", str(source),
                f"Maximum $ref depth ({self.MAX_REF_DEPTH}) exceeded",
            )

        if isinstance(data, dict):
            if "$ref" in data and len(data) == 1:
                return self._load_ref(data["$ref"], source, depth)
            return {k: self._resolve_refs(v, source, depth) for k, v in data.items()}

        if isinstance(data, list):
            return [self._resolve_refs(item, source, depth) for item in data]

        return data

    def _load_ref(self, ref: str, source: Path, depth: int) -> Any:
        ref_path = self._resolve_ref_path(ref, source)

        if not ref_path.exists():
            raise RefResolutionError(ref, str(source), f"File not found: {ref_path}")

        raw = self._read_yaml(ref_path)
        return self._resolve_refs(raw, ref_path, depth + 1)

    def _resolve_ref_path(self, ref: str, source: Path) -> Path:
        if ref.endswith(".yaml") or ref.endswith(".yml"):
            candidate = source.parent / ref
        else:
            candidate = self.base_dir / f"{ref}.yaml"
            if not candidate.exists():
                candidate = source.parent / f"{ref}.yaml"

        return candidate.resolve()
