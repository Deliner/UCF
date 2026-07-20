"""Generates skeleton UCF specs from scanned Python code.

@implements("actions/generate-skeleton-specs")
@implements("use-cases/scaffold-specs-from-code")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ucf.scaffold.scanner import ClassInfo, FunctionInfo, ParamInfo

_PYTHON_TO_UCF_TYPE = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "void",
}


def _to_kebab(name: str) -> str:
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s1)
    return s2.replace("_", "-").lower()


def _map_type(annotation: str) -> str:
    base = annotation.split("[")[0].strip()
    return _PYTHON_TO_UCF_TYPE.get(base, "object")


def _param_to_field(param: ParamInfo) -> dict:
    field_def: dict = {"type": _map_type(param.annotation)}
    if param.default is not None:
        field_def["required"] = False
    else:
        field_def["required"] = True
    return field_def


@dataclass
class SpecGenResult:
    action_specs: list[str] = field(default_factory=list)
    component_specs: list[str] = field(default_factory=list)
    specs_written: int = 0


class SkeletonSpecGenerator:
    """Generates UCF YAML spec skeletons from scanned Python code."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def generate(
        self,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
    ) -> SpecGenResult:
        result = SpecGenResult()

        actions_dir = self.output_dir / "actions"
        actions_dir.mkdir(parents=True, exist_ok=True)

        components_dir = self.output_dir / "components"
        components_dir.mkdir(parents=True, exist_ok=True)

        for func in functions:
            path = self._generate_action_spec(func, actions_dir)
            if path:
                result.action_specs.append(str(path))
                result.specs_written += 1

        for cls in classes:
            path = self._generate_component_spec(cls, components_dir)
            if path:
                result.component_specs.append(str(path))
                result.specs_written += 1

        return result

    def _generate_action_spec(
        self,
        func: FunctionInfo,
        out_dir: Path,
    ) -> Path | None:
        kebab = _to_kebab(func.name)
        target = out_dir / f"{kebab}.yaml"

        if target.exists():
            return None

        input_fields = {}
        for param in func.params:
            input_fields[param.name] = _param_to_field(param)

        output_fields = {}
        if func.return_type and func.return_type not in ("None", "Any"):
            output_fields["result"] = {"type": _map_type(func.return_type)}

        spec: dict = {
            "kind": "action",
            "metadata": {
                "name": kebab,
                "version": "0.1.0",
                "owner": "your-team",
            },
        }

        if input_fields:
            spec["input"] = input_fields
        else:
            spec["input"] = {}

        if output_fields:
            spec["output"] = output_fields
        else:
            spec["output"] = {}

        spec["preconditions"] = []
        spec["postconditions"] = []

        if func.docstring:
            spec["metadata"]["description"] = func.docstring.split("\n")[0]

        target.write_text(
            yaml.dump(
                spec, default_flow_style=False, sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        return target

    def _generate_component_spec(
        self,
        cls: ClassInfo,
        out_dir: Path,
    ) -> Path | None:
        if not cls.methods:
            return None

        kebab = _to_kebab(cls.name)
        target = out_dir / f"{kebab}.yaml"

        if target.exists():
            return None

        provides: dict = {}
        for method in cls.methods:
            if method.name == "__init__":
                continue
            provides[method.name] = {
                "type": _map_type(method.return_type),
                "description": method.docstring.split("\n")[0]
                if method.docstring
                else f"Result of {method.name}",
            }

        if not provides:
            return None

        spec: dict = {
            "kind": "component",
            "metadata": {
                "name": kebab,
                "version": "0.1.0",
                "owner": "your-team",
            },
            "provides": provides,
        }

        if cls.docstring:
            spec["metadata"]["description"] = cls.docstring.split("\n")[0]

        target.write_text(
            yaml.dump(
                spec, default_flow_style=False, sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        return target
