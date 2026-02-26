"""Pytest generator plugin — transforms use case specs into test code."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry
from ucf.generator.plugin import GeneratedFile


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
    """Convert a $ expression to a Python variable reference."""
    if not val.startswith("$"):
        return repr(val)
    parts = val.lstrip("$").split(".")
    if parts[0] == "inputs" and len(parts) >= 2:
        return "None"
    if parts[0] == "steps" and len(parts) >= 3:
        return f"{_to_snake(parts[1])}.{_to_snake(parts[2])}"
    if len(parts) >= 2:
        return f"{_to_snake(parts[0])}.{_to_snake(parts[1])}"
    return _to_snake(val)


def _build_step_args(input_dict: dict[str, Any]) -> list[str]:
    """Build argument list from a step's input dict."""
    args = []
    for fname, binding in input_dict.items():
        if isinstance(binding, dict):
            # Nested dict — pass individual $ refs extracted from it
            inner_args = []
            for k, v in binding.items():
                if isinstance(v, str) and v.startswith("$"):
                    inner_args.append(_resolve_binding(v))
            if inner_args:
                args.extend(inner_args)
            else:
                args.append(f"{_to_snake(fname)}=...")
        elif isinstance(binding, str) and binding.startswith("$"):
            args.append(_resolve_binding(binding))
        else:
            args.append(f"{_to_snake(fname)}={repr(binding)}")
    return args


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

    def generate_interface(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile:
        ctx = self._build_context(spec, registry)
        template = self._env.get_template("interface.py.j2")
        content = template.render(**ctx)
        return GeneratedFile(path="interface.py", content=content, overwrite=True)

    def generate_orchestrator(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile:
        ctx = self._build_context(spec, registry)
        orch_ctx = self._build_orchestrator_context(spec, registry, ctx)
        template = self._env.get_template("orchestrator.py.j2")
        content = template.render(**orch_ctx)
        return GeneratedFile(path="test_orchestrator.py", content=content, overwrite=True)

    def generate_impl_stub(
        self, spec: UseCaseSpec, registry: SpecRegistry,
    ) -> GeneratedFile:
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
            safe = re.sub(r"[^a-z0-9_]", "_", post.lower().strip()[:50])
            safe = re.sub(r"_+", "_", safe).strip("_")
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

        # Map action refs to method names for alt flow reuse
        action_ref_to_method: dict[str, str] = {}
        for i, step in enumerate(spec.steps):
            action_ref_to_method[step.use] = ctx["action_methods"][i].name

        alt_flow_tests: list[AltFlowTest] = []
        for alt in spec.alternative_flows:
            alt_class = _to_pascal(alt.name)
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
                action_steps=alt_action_steps,
            ))

        orch["setup_steps"] = setup_steps
        orch["action_steps"] = action_steps
        orch["verify_steps"] = verify_steps
        orch["alt_flow_tests"] = alt_flow_tests

        return orch
