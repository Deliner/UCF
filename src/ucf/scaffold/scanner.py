"""AST-based Python source scanner for scaffold spec generation.

@implements("actions/scan-python-ast")
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParamInfo:
    name: str
    annotation: str = "Any"
    default: str | None = None


@dataclass
class FunctionInfo:
    name: str
    params: list[ParamInfo] = field(default_factory=list)
    return_type: str = "None"
    docstring: str = ""
    file_path: str = ""
    line: int = 0


@dataclass
class MethodInfo:
    name: str
    params: list[ParamInfo] = field(default_factory=list)
    return_type: str = "None"
    docstring: str = ""


@dataclass
class ClassInfo:
    name: str
    methods: list[MethodInfo] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    docstring: str = ""
    file_path: str = ""
    line: int = 0


@dataclass
class ASTScanResult:
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    scanned_count: int = 0


def _annotation_to_str(node: ast.expr | None) -> str:
    if node is None:
        return "Any"
    return ast.unparse(node)


def _extract_params(args: ast.arguments) -> list[ParamInfo]:
    params: list[ParamInfo] = []
    defaults_offset = len(args.args) - len(args.defaults)

    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue
        default_idx = i - defaults_offset
        default = None
        if default_idx >= 0 and default_idx < len(args.defaults):
            default = ast.unparse(args.defaults[default_idx])
        params.append(
            ParamInfo(
                name=arg.arg,
                annotation=_annotation_to_str(arg.annotation),
                default=default,
            )
        )
    return params


def _is_public(name: str) -> bool:
    return not name.startswith("_") or name == "__init__"


class ASTScanner:
    """Scans Python source files and extracts public functions and classes."""

    def __init__(
        self,
        source_dir: Path,
        patterns: list[str] | None = None,
    ) -> None:
        self.source_dir = source_dir
        self.patterns = patterns or ["**/*.py"]

    def scan(self) -> ASTScanResult:
        result = ASTScanResult()
        files = self._collect_files()
        result.scanned_count = len(files)

        for file_path in files:
            self._scan_file(file_path, result)

        return result

    def _collect_files(self) -> list[Path]:
        files: list[Path] = []
        for pattern in self.patterns:
            files.extend(sorted(self.source_dir.glob(pattern)))
        seen: set[Path] = set()
        unique: list[Path] = []
        for f in files:
            resolved = f.resolve()
            if resolved not in seen and f.is_file():
                seen.add(resolved)
                unique.append(f)
        return unique

    def _scan_file(self, file_path: Path, result: ASTScanResult) -> None:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return

        rel = str(file_path.relative_to(self.source_dir))

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if _is_public(node.name):
                    result.functions.append(self._extract_function(node, rel))
            elif isinstance(node, ast.ClassDef):
                if _is_public(node.name):
                    result.classes.append(self._extract_class(node, rel))

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        rel_path: str,
    ) -> FunctionInfo:
        return FunctionInfo(
            name=node.name,
            params=_extract_params(node.args),
            return_type=_annotation_to_str(node.returns),
            docstring=ast.get_docstring(node) or "",
            file_path=rel_path,
            line=node.lineno,
        )

    def _extract_class(self, node: ast.ClassDef, rel_path: str) -> ClassInfo:
        methods: list[MethodInfo] = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                if _is_public(item.name):
                    methods.append(
                        MethodInfo(
                            name=item.name,
                            params=_extract_params(item.args),
                            return_type=_annotation_to_str(item.returns),
                            docstring=ast.get_docstring(item) or "",
                        )
                    )

        bases = [ast.unparse(b) for b in node.bases]

        return ClassInfo(
            name=node.name,
            methods=methods,
            bases=bases,
            docstring=ast.get_docstring(node) or "",
            file_path=rel_path,
            line=node.lineno,
        )
