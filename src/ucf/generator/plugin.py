"""Generator plugin protocol and engine.

@implements("actions/generate-tests")
@implements("invariants/generated-files-idempotent")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry

_SAFE_NAME_RE = re.compile(r"[^a-z0-9_]")


def _safe_module_name(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", name.lower().replace("-", "_"))


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: str
    overwrite: bool = True


@runtime_checkable
class GeneratorPlugin(Protocol):
    name: str
    language: str

    def generate_interface(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile: ...

    def generate_orchestrator(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile: ...

    def generate_impl_stub(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile: ...


@dataclass
class GenerationResult:
    usecase_name: str
    files_written: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)


class GeneratorEngine:
    """Loads specs, iterates use cases, delegates to plugin, writes files."""

    def __init__(
        self,
        registry: SpecRegistry,
        plugin: GeneratorPlugin,
        output_dir: Path,
    ) -> None:
        self.registry = registry
        self.plugin = plugin
        self.output_dir = output_dir

    def generate_all(self) -> list[GenerationResult]:
        results = []
        for uc in self.registry.usecases():
            result = self.generate_usecase(uc)
            results.append(result)
        return results

    def generate_usecase(self, uc: UseCaseSpec) -> GenerationResult:
        result = GenerationResult(usecase_name=uc.metadata.name)
        safe_name = _safe_module_name(uc.metadata.name)
        uc_dir = self.output_dir / safe_name
        uc_dir.mkdir(parents=True, exist_ok=True)

        init_file = uc_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

        generated_files = [
            self.plugin.generate_interface(uc, self.registry),
            self.plugin.generate_orchestrator(uc, self.registry),
            self.plugin.generate_impl_stub(uc, self.registry),
        ]

        written_paths: list[Path] = []
        try:
            for gf in generated_files:
                target = (uc_dir / gf.path).resolve()
                uc_dir_resolved = uc_dir.resolve()
                if not str(target).startswith(str(uc_dir_resolved) + "/"):
                    raise ValueError(
                        f"Generated path escapes output directory: {gf.path}"
                    )
                if target.exists() and not gf.overwrite:
                    result.files_skipped.append(str(target))
                    continue
                target.write_text(gf.content, encoding="utf-8")
                written_paths.append(target)
                result.files_written.append(str(target))
        except Exception:
            for p in written_paths:
                p.unlink(missing_ok=True)
            raise

        return result
