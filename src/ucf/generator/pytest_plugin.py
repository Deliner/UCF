"""Pytest generator plugin — transforms use case specs into test code.

@implements("actions/generate-tests")
@implements("actions/validate-generated-code")
@implements("actions/extract-error-definitions")
@implements("actions/generate-negative-tests")
@implements("use-cases/generate-test-code")
@implements("use-cases/validate-generated-tests")
@implements("use-cases/generate-negative-test-code")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ucf.generator.plugin import GeneratedFile
from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _to_snake(name: str) -> str:
    return name.replace("-", "_")


def _to_pascal(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("-"))


@dataclass
class FieldInfo:
    name: str
    type: str = "Any"


@dataclass
class DataclassInfo:
    class_name: str
    fields: list[FieldInfo] = field(default_factory=list)


@dataclass
class MethodInfo:
    name: str
    params: list[FieldInfo] = field(default_factory=list)
    return_type: str = "Any"

    @property
    def params_str(self) -> str:
        if not self.params:
            return ""
        parts = [f"{p.name}: {p.type}" for p in self.params]
        return ", " + ", ".join(parts)


@dataclass
class StepCall:
    var: str
    method: str
    args: list[str] = field(default_factory=list)

    @property
    def args_str(self) -> str:
        return ", ".join(self.args)


@dataclass
class AltFlowTest:
    class_name: str
    test_name: str
    setup_steps: list[StepCall] = field(default_factory=list)
    action_steps: list[StepCall] = field(default_factory=list)


def _extract_type_from_field(field_def: Any) -> str:
    if isinstance(field_def, dict):
        raw = field_def.get("type", "object")
    elif hasattr(field_def, "type"):
        raw = field_def.type.value if hasattr(field_def.type, "value") else str(field_def.type)
    else:
        raw = "Any"

    type_map = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list[Any]",
        "object": "Any",
    }
    return type_map.get(raw, "Any")


def _resolve_binding(val: str) -> str:
    """Convert a $ expression to a Python variable reference.
    
    Supports nested field access:
    - $steps.lookup-url.url_record.original_url → lookup_url.url_record.original_url
    - $requires.loader.registry.specs → loader.registry.specs
    """
    if not val.startswith("$"):
        return repr(val)
    parts = val[1:].split(".")
    if parts[0] == "inputs" and len(parts) >= 2:
        return "None"
    if parts[0] == "steps" and len(parts) >= 3:
        # parts[1] = step_id, parts[2:] = nested field access
        step_var = _to_snake(parts[1])
        fields = ".".join(_to_snake(p) for p in parts[2:])
        return f"{step_var}.{fields}"
    if parts[0] == "requires" and len(parts) >= 3:
        # parts[1] = component alias, parts[2:] = nested field access
        alias = _to_snake(parts[1])
        fields = ".".join(_to_snake(p) for p in parts[2:])
        return f"{alias}.{fields}"
    if parts[0] == "requires" and len(parts) == 2:
        return _to_snake(parts[1])
    if len(parts) >= 2:
        return f"{_to_snake(parts[0])}.{_to_snake(parts[1])}"
    return _to_snake(val)


def _build_dict_literal(d: dict[str, Any]) -> str:
    """Build a Python dict literal from a spec input dict with $ references."""
    pairs = []
    for k, v in d.items():
        if isinstance(v, str) and v.startswith("$"):
            pairs.append(f"{repr(k)}: {_resolve_binding(v)}")
        elif isinstance(v, dict):
            pairs.append(f"{repr(k)}: {_build_dict_literal(v)}")
        else:
            pairs.append(f"{repr(k)}: {repr(v)}")
    return "{" + ", ".join(pairs) + "}"


def _build_step_args(input_dict: dict[str, Any]) -> list[str]:
    """Build argument list from a step's input dict.
    
    Always generates keyword arguments to avoid syntax errors when mixing
    literals and bindings.
    """
    args = []
    for fname, binding in input_dict.items():
        if isinstance(binding, dict):
            args.append(f"{_to_snake(fname)}={_build_dict_literal(binding)}")
        elif isinstance(binding, str) and binding.startswith("$"):
            # Always use keyword argument, even for bindings (fixes Bottle Neck #10)
            args.append(f"{_to_snake(fname)}={_resolve_binding(binding)}")
        else:
            args.append(f"{_to_snake(fname)}={repr(binding)}")
    return args


def _truncate_name(raw: str, max_len: int = 60) -> str:
    """Truncate a snake_case method name at a word boundary."""
    safe = re.sub(r"[^a-z0-9_]", "_", raw.lower().strip())
    safe = re.sub(r"_+", "_", safe).strip("_")
    if len(safe) <= max_len:
        return safe
    truncated = safe[:max_len]
    last_sep = truncated.rfind("_")
    if last_sep > max_len // 2:
        truncated = truncated[:last_sep]
    return truncated


def _collect_step_refs(input_dict: dict[str, Any]) -> set[str]:
    """Extract all $steps.X references from a step's input bindings."""
    refs: set[str] = set()
    for v in input_dict.values():
        if isinstance(v, str) and v.startswith("$steps."):
            parts = v[1:].split(".")
            if len(parts) >= 2:
                refs.add(parts[1])
        elif isinstance(v, dict):
            for inner_v in v.values():
                if isinstance(inner_v, str) and inner_v.startswith("$steps."):
                    parts = inner_v[1:].split(".")
                    if len(parts) >= 2:
                        refs.add(parts[1])
    return refs


class PytestPlugin:
    name = "pytest"
    language = "python"

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @staticmethod
    def _resolve_composition(spec: UseCaseSpec, registry: SpecRegistry) -> UseCaseSpec:
        if spec.extends is None:
            return spec
        from ucf.composition import resolve_extends
        flattened, _chain, _parent_ids = resolve_extends(spec, registry)
        return flattened

    def generate_interface(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile:
        spec = self._resolve_composition(spec, registry)
        ctx = self._build_context(spec, registry)
        template = self._env.get_template("interface.py.j2")
        content = template.render(**ctx)
        return GeneratedFile(path="interface.py", content=content, overwrite=True)

    def generate_orchestrator(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile:
        spec = self._resolve_composition(spec, registry)
        ctx = self._build_context(spec, registry)
        orch_ctx = self._build_orchestrator_context(spec, registry, ctx)
        template = self._env.get_template("orchestrator.py.j2")
        content = template.render(**orch_ctx)
        return GeneratedFile(path="test_orchestrator.py", content=content, overwrite=True)

    def generate_impl_stub(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile:
        spec = self._resolve_composition(spec, registry)
        ctx = self._build_context(spec, registry)
        ctx["impl_class"] = _to_pascal(spec.metadata.name) + "Impl"
        template = self._env.get_template("impl_stub.py.j2")
        content = template.render(**ctx)
        return GeneratedFile(path="impl.py", content=content, overwrite=False)

    def _build_context(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> dict[str, Any]:
        uc_name = spec.metadata.name
        interface_class = _to_pascal(uc_name) + "Interface"

        dataclasses: list[DataclassInfo] = []
        setup_methods: list[MethodInfo] = []
        action_methods: list[MethodInfo] = []
        verify_methods: list[MethodInfo] = []

        for req in spec.requires:
            if isinstance(req, dict):
                ref = req.get("$ref", "")
                alias = req.get("as", "")
            else:
                ref = req.ref
                alias = req.as_

            comp = registry.resolve_ref(ref)
            if isinstance(comp, ComponentSpec):
                dc_name = _to_pascal(alias or comp.metadata.name) + "Context"
                fields = []
                for fname, fdef in comp.provides.items():
                    fields.append(FieldInfo(
                        name=_to_snake(fname),
                        type=_extract_type_from_field(fdef),
                    ))
                dataclasses.append(DataclassInfo(class_name=dc_name, fields=fields))
                setup_methods.append(MethodInfo(
                    name=f"setup_{_to_snake(alias or comp.metadata.name)}",
                    return_type=dc_name,
                ))

        for step in spec.steps:
            action_ref = step.use
            action_spec = registry.resolve_ref(action_ref)

            params: list[FieldInfo] = []
            return_fields: list[FieldInfo] = []

            for fname, binding in step.input.items():
                params.append(FieldInfo(name=_to_snake(fname), type="Any"))

            if step.output:
                for fname, binding in step.output.items():
                    out_name = binding if isinstance(binding, str) else fname
                    out_type = "Any"

                    if isinstance(action_spec, (ActionSpec, ProtocolSpec)):
                        for afield_name, afield_def in action_spec.output.items():
                            if afield_name == out_name or afield_name == fname:
                                out_type = _extract_type_from_field(afield_def)
                                break

                    return_fields.append(FieldInfo(
                        name=_to_snake(out_name),
                        type=out_type,
                    ))

            ret_type: str
            if return_fields:
                dc_name = _to_pascal(step.id) + "Result"
                dataclasses.append(DataclassInfo(class_name=dc_name, fields=return_fields))
                ret_type = dc_name
            else:
                ret_type = "None"

            action_methods.append(MethodInfo(
                name=f"action_{_to_snake(step.id)}",
                params=params,
                return_type=ret_type,
            ))

        for i, post in enumerate(spec.postconditions):
            safe = _truncate_name(post)
            verify_methods.append(MethodInfo(
                name=f"verify_{safe}",
            ))

        for inv_ref in spec.invariants:
            inv_name = ""
            if isinstance(inv_ref, dict):
                if "$ref" in inv_ref:
                    raw = inv_ref["$ref"]
                    inv_name = raw.split("/")[-1] if "/" in raw else raw
                elif "metadata" in inv_ref and isinstance(inv_ref["metadata"], dict):
                    inv_name = inv_ref["metadata"].get("name", "")
                elif "name" in inv_ref:
                    inv_name = inv_ref["name"]
            else:
                inv_name = inv_ref.ref.split("/")[-1] if "/" in inv_ref.ref else inv_ref.ref

            if inv_name:
                verify_methods.append(MethodInfo(
                    name=f"verify_{_to_snake(inv_name)}",
                ))

        return {
            "usecase_name": uc_name,
            "interface_class": interface_class,
            "dataclasses": dataclasses,
            "setup_methods": setup_methods,
            "action_methods": action_methods,
            "verify_methods": verify_methods,
        }

    def _build_orchestrator_context(
        self, spec: UseCaseSpec, registry: SpecRegistry, ctx: dict,
    ) -> dict[str, Any]:
        orch = dict(ctx)
        orch["fixture_name"] = _to_snake(spec.metadata.name) + "_impl"
        orch["test_name"] = _to_snake(spec.metadata.name)

        setup_steps: list[StepCall] = []
        for method in ctx["setup_methods"]:
            var_name = method.name.replace("setup_", "")
            setup_steps.append(StepCall(var=var_name, method=method.name))

        action_steps: list[StepCall] = []
        for i, step in enumerate(spec.steps):
            method = ctx["action_methods"][i]
            var = _to_snake(step.id)

            args = _build_step_args(step.input)

            action_steps.append(StepCall(
                var=var, method=method.name, args=args,
            ))

        verify_steps: list[StepCall] = []
        for method in ctx["verify_methods"]:
            verify_steps.append(StepCall(var="_", method=method.name))

        # Map step IDs and action refs to method names for alt flow reuse.
        # Step ID is unique; action ref may repeat (last occurrence wins for action key).
        action_ref_to_method: dict[str, str] = {}
        step_id_to_method: dict[str, str] = {}
        for i, step in enumerate(spec.steps):
            action_ref_to_method[step.use] = ctx["action_methods"][i].name
            step_id_to_method[step.id] = ctx["action_methods"][i].name

        main_step_index: dict[str, int] = {}
        main_step_deps: dict[str, set[str]] = {}
        for i, step in enumerate(spec.steps):
            main_step_index[step.id] = i
            main_step_deps[step.id] = _collect_step_refs(step.input)

        def _transitive_deps(step_ids: set[str]) -> list[str]:
            """Topologically sorted list of all transitive step dependencies."""
            visited: set[str] = set()
            order: list[str] = []

            def _visit(sid: str) -> None:
                if sid in visited or sid not in main_step_index:
                    return
                visited.add(sid)
                for dep in main_step_deps.get(sid, set()):
                    _visit(dep)
                order.append(sid)

            for sid in step_ids:
                _visit(sid)
            return order

        alt_flow_tests: list[AltFlowTest] = []
        for alt in spec.alternative_flows:
            alt_class = _to_pascal(alt.name)

            needed_steps: set[str] = set()
            for step in alt.steps:
                needed_steps |= _collect_step_refs(step.input)

            ordered_prereqs = _transitive_deps(needed_steps)

            prereq_steps: list[StepCall] = []
            for step_id in ordered_prereqs:
                idx = main_step_index[step_id]
                main_step = spec.steps[idx]
                prereq_var = _to_snake(main_step.id)
                prereq_method = step_id_to_method.get(
                    main_step.id,
                    action_ref_to_method.get(main_step.use, f"action_{_to_snake(main_step.id)}"),
                )
                prereq_args = _build_step_args(main_step.input)
                prereq_steps.append(StepCall(
                    var=prereq_var, method=prereq_method, args=prereq_args,
                ))

            alt_action_steps: list[StepCall] = []
            for step in alt.steps:
                step_var = _to_snake(step.id)
                method_name = action_ref_to_method.get(
                    step.use, f"action_{_to_snake(step.id)}"
                )
                step_args = _build_step_args(step.input)

                alt_action_steps.append(StepCall(
                    var=step_var, method=method_name, args=step_args,
                ))

            alt_flow_tests.append(AltFlowTest(
                class_name=alt_class,
                test_name=_to_snake(alt.name),
                setup_steps=list(setup_steps),
                action_steps=prereq_steps + alt_action_steps,
            ))

        orch["setup_steps"] = setup_steps
        orch["action_steps"] = action_steps
        orch["verify_steps"] = verify_steps
        orch["alt_flow_tests"] = alt_flow_tests

        return orch


@dataclass
class ErrorTestDef:
    step_id: str
    action_name: str
    error_code: str
    condition: str
    status: str | int


def extract_error_definitions(
    spec: UseCaseSpec, registry: SpecRegistry,
) -> list[ErrorTestDef]:
    """Extract error definitions from action specs referenced by use case steps."""
    results: list[ErrorTestDef] = []
    for step in spec.steps:
        action = registry.resolve_ref(step.use)
        if isinstance(action, ActionSpec) and action.errors:
            for err in action.errors:
                results.append(ErrorTestDef(
                    step_id=step.id,
                    action_name=action.metadata.name,
                    error_code=err.code,
                    condition=err.condition,
                    status=err.status,
                ))
    return results


def generate_negative_test_code(
    error_defs: list[ErrorTestDef],
    interface_class: str,
    usecase_name: str,
) -> tuple[str, list[str]]:
    """Generate Python test code for error/negative paths.

    Returns (test_code, list_of_error_method_names).
    """
    lines: list[str] = []
    method_names: list[str] = []

    lines.append('"""Negative tests for error paths."""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import pytest")
    lines.append("")

    for err in error_defs:
        safe_code = _to_snake(err.error_code)
        safe_step = _to_snake(err.step_id)
        method_name = f"action_error_{safe_step}_{safe_code}"
        method_names.append(method_name)

        class_name = f"TestError{_to_pascal(err.error_code)}"
        lines.append("")
        lines.append(f"class {class_name}:")
        lines.append(f'    """Error: {err.condition}"""')
        lines.append("")
        lines.append(f"    def test_{safe_step}_raises_{safe_code}(self, uc):")
        lines.append(f'        """Condition: {err.condition}"""')
        lines.append(f"        error = uc.{method_name}()")
        lines.append(f"        assert error is not None")
        lines.append(f"        assert error.get('code') == {repr(err.error_code)}")
        lines.append("")

    return "\n".join(lines), method_names
