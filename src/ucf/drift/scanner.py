"""Source code scanner — finds @implements markers in Python files.

@implements("actions/scan-source-directory")
@implements("components/scanned-codebase")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_IMPLEMENTS_RE = re.compile(
    r"""@implements\(\s*["']([^"']+)["']\s*\)""",
)

_COMMENT_IMPLEMENTS_RE = re.compile(
    r"""#\s*@implements\(\s*["']([^"']+)["']\s*\)""",
)


@dataclass(frozen=True)
class ImplementationEntry:
    file_path: str
    spec_ref: str
    line_number: int


@dataclass
class ScanResult:
    implementations: list[ImplementationEntry] = field(default_factory=list)
    scanned_count: int = 0
    marker_count: int = 0


class SourceScanner:
    """Scans source files for @implements("spec-ref") markers."""

    def __init__(
        self,
        source_dir: Path,
        patterns: list[str] | None = None,
    ) -> None:
        self.source_dir = source_dir.resolve()
        self.patterns = patterns or ["**/*.py"]

    def scan(self) -> ScanResult:
        result = ScanResult()

        for pattern in self.patterns:
            for file_path in sorted(self.source_dir.rglob(pattern)):
                if not file_path.is_file():
                    continue
                result.scanned_count += 1
                entries = self._scan_file(file_path)
                result.implementations.extend(entries)
                result.marker_count += len(entries)

        return result

    def _scan_file(self, path: Path) -> list[ImplementationEntry]:
        entries: list[ImplementationEntry] = []
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return entries

        rel_path = str(path.relative_to(self.source_dir))

        for line_no, line in enumerate(text.splitlines(), start=1):
            comment_match = _COMMENT_IMPLEMENTS_RE.search(line)
            if comment_match:
                entries.append(ImplementationEntry(
                    file_path=rel_path,
                    spec_ref=comment_match.group(1),
                    line_number=line_no,
                ))
                continue
            for m in _IMPLEMENTS_RE.finditer(line):
                entries.append(ImplementationEntry(
                    file_path=rel_path,
                    spec_ref=m.group(1),
                    line_number=line_no,
                ))

        return entries
