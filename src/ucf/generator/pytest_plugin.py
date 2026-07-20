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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ucf.generator.plugin import GeneratedFile, UnsupportedFeatureError
from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec, StepDef
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec, invariant_reference
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
    when_expr: str | None = None
    skip_if_expr: str | None = None
    capture_result: bool = True

    @property
    def args_str(self) -> str:
        return ", ".join(self.args)

    def render_call(self, indent: int) -> str:
        prefix = " " * indent
        assignment = f"{self.var} = " if self.capture_result else ""
        if not self.args:
            return f"{prefix}{assignment}uc.{self.method}()"

        lines = [f"{prefix}{assignment}uc.{self.method}("]
        argument_prefix = prefix + " " * 4
        for argument in self.args:
            argument_lines = argument.splitlines()
            lines.append(argument_prefix + argument_lines[0])
            lines.extend(argument_prefix + line for line in argument_lines[1:])
            lines[-1] += ","
        lines.append(f"{prefix})")
        return "\n".join(lines)


@dataclass
class AltFlowTest:
    class_name: str
    test_name: str
    setup_steps: list[StepCall] = field(default_factory=list)
    action_steps: list[StepCall] = field(default_factory=list)
    uses_inputs: bool = False


def _step_calls_use_inputs(steps: list[StepCall]) -> bool:
    pattern = re.compile(r"\binputs(?:\.|\[)")
    for step in steps:
        expressions = [
            *step.args,
            step.when_expr or "",
            step.skip_if_expr or "",
        ]
        if any(pattern.search(expression) for expression in expressions):
            return True
    return False


def _step_calls_reference_variable(
    steps: list[StepCall],
    variable: str,
) -> bool:
    pattern = re.compile(rf"\b{re.escape(variable)}(?:\.|\b)")
    for step in steps:
        expressions = [
            *step.args,
            step.when_expr or "",
            step.skip_if_expr or "",
        ]
        if any(pattern.search(expression) for expression in expressions):
            return True
    return False


def _setup_steps_for_flow(
    setup_steps: list[StepCall],
    action_steps: list[StepCall],
) -> list[StepCall]:
    return [
        replace(
            step,
            capture_result=_step_calls_reference_variable(
                [*setup_steps[index + 1 :], *action_steps],
                step.var,
            ),
        )
        for index, step in enumerate(setup_steps)
    ]


def _extract_type_from_field(field_def: Any) -> str:
    if isinstance(field_def, dict):
        raw = field_def.get("type", "object")
    elif hasattr(field_def, "type"):
        raw = (
            field_def.type.value
            if hasattr(field_def.type, "value")
            else str(field_def.type)
        )
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


def _translate_expression(expr: str) -> str:
    """Translates YAML bindings in expressions to Python variables.

    Uses _resolve_binding for $steps, $requires, and $inputs.
    """
    pattern = r"\$[a-zA-Z0-9_\-\.]+"

    def replacer(match: re.Match[str]) -> str:
        return _resolve_binding(match.group(0))

    return re.sub(pattern, replacer, expr)


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
        indexes = "".join(f"[{part!r}]" for part in parts[1:])
        return f"inputs{indexes}"
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


def _build_dict_literal(
    values: dict[str, Any],
    indent_level: int = 0,
) -> str:
    """Build a Python dict literal from a spec input dict with $ references."""
    lines = ["{"]
    item_prefix = " " * (4 * (indent_level + 1))
    for key, value in values.items():
        if isinstance(value, str) and value.startswith("$"):
            lines.append(f"{item_prefix}{key!r}: {_resolve_binding(value)},")
        elif isinstance(value, dict):
            nested = _build_dict_literal(value, indent_level + 1).splitlines()
            lines.append(f"{item_prefix}{key!r}: {nested[0]}")
            lines.extend(nested[1:])
            lines[-1] += ","
        elif isinstance(value, str) and (
            len(item_prefix) + len(repr(key)) + len(repr(value)) + 4 > 88
        ):
            lines.append(f"{item_prefix}{key!r}: (")
            for chunk in _split_string_literal(value):
                lines.append(f"{item_prefix}    {chunk!r}")
            lines.append(f"{item_prefix}),")
        else:
            lines.append(f"{item_prefix}{key!r}: {value!r},")
    lines.append(" " * (4 * indent_level) + "}")
    return "\n".join(lines)


def _split_string_literal(value: str, width: int = 56) -> list[str]:
    chunks: list[str] = []
    remaining = value
    while len(remaining) > width:
        split_at = remaining.rfind(" ", 0, width + 1)
        if split_at <= 0:
            split_at = width
        else:
            split_at += 1
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    chunks.append(remaining)
    return chunks


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


def _step_when_skip(step: StepDef) -> tuple[str | None, str | None]:
    """Extract when/skip_if expressions for a step, translated to Python."""
    when_expr = _translate_expression(step.when) if step.when else None
    skip_if_expr = _translate_expression(step.skip_if) if step.skip_if else None
    return (when_expr, skip_if_expr)


def _collect_step_refs(value: Any) -> set[str]:
    """Extract all referenced step IDs from nested bindings or expressions."""
    refs: set[str] = set()
    if isinstance(value, dict):
        for nested_value in value.values():
            refs.update(_collect_step_refs(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            refs.update(_collect_step_refs(nested_value))
    elif isinstance(value, str):
        refs.update(re.findall(r"\$steps\.([a-zA-Z0-9_-]+)", value))
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

    def validate_spec(
        self,
        spec: UseCaseSpec,
        registry: SpecRegistry,
    ) -> None:
        resolved = self._resolve_composition(spec, registry)
        unsupported = [
            f"steps.{step.id}.retry"
            for step in resolved.steps
            if step.retry is not None
        ]
        for flow in resolved.alternative_flows:
            unsupported.extend(
                f"alternative_flows.{flow.name}.steps.{step.id}.retry"
                for step in flow.steps
                if step.retry is not None
            )
        if unsupported:
            raise UnsupportedFeatureError(
                self.name,
                spec.metadata.name,
                unsupported,
            )

    @staticmethod
    def _resolve_composition(spec: UseCaseSpec, registry: SpecRegistry) -> UseCaseSpec:
        if spec.extends is None:
            return spec
        from ucf.composition import resolve_extends

        flattened, _chain, _parent_ids = resolve_extends(spec, registry)
        return flattened

    def generate_interface(
        self,
        spec: UseCaseSpec,
        registry: SpecRegistry,
    ) -> GeneratedFile:
        self.validate_spec(spec, registry)
        spec = self._resolve_composition(spec, registry)
        ctx = self._build_context(spec, registry)
        template = self._env.get_template("interface.py.j2")
        content = template.render(**ctx)
        return GeneratedFile(path="interface.py", content=content, overwrite=True)

    def generate_orchestrator(
        self,
        spec: UseCaseSpec,
        registry: SpecRegistry,
    ) -> GeneratedFile:
        self.validate_spec(spec, registry)
        spec = self._resolve_composition(spec, registry)
        ctx = self._build_context(spec, registry)
        orch_ctx = self._build_orchestrator_context(spec, registry, ctx)
        template = self._env.get_template("orchestrator.py.j2")
        content = template.render(**orch_ctx)
        return GeneratedFile(
            path="test_orchestrator.py", content=content, overwrite=True
        )

    def generate_impl_stub(
        self,
        spec: UseCaseSpec,
        registry: SpecRegistry,
    ) -> GeneratedFile:
        self.validate_spec(spec, registry)
        spec = self._resolve_composition(spec, registry)
        ctx = self._build_context(spec, registry)
        ctx["impl_class"] = _to_pascal(spec.metadata.name) + "Impl"
        ctx["fixture_name"] = _to_snake(spec.metadata.name) + "_impl"
        template = self._env.get_template("impl_stub.py.j2")
        content = template.render(**ctx)
        return GeneratedFile(path="impl.py", content=content, overwrite=False)

    def _build_context(
        self,
        spec: UseCaseSpec,
        registry: SpecRegistry,
    ) -> dict[str, Any]:
        self._validate_python_step_names(spec)
        uc_name = spec.metadata.name
        interface_class = _to_pascal(uc_name) + "Interface"

        dataclasses: list[DataclassInfo] = []
        setup_methods: list[MethodInfo] = []
        setup_method_args: list[list[str]] = []
        action_methods: list[MethodInfo] = []
        main_action_method_names: list[str] = []
        alt_action_method_names: list[list[str]] = []
        verify_methods: list[MethodInfo] = []

        requirements: list[dict[str, Any]] = []
        for index, req in enumerate(spec.requires):
            if isinstance(req, dict):
                ref = req.get("$ref", "")
                alias = req.get("as", "")
                params = req.get("params", {})
            else:
                ref = req.ref
                alias = req.as_
                params = req.params

            comp = registry.resolve_ref(ref)
            if isinstance(comp, ComponentSpec):
                requirements.append(
                    {
                        "index": index,
                        "alias": alias or comp.metadata.name,
                        "component": comp,
                        "params": params,
                    }
                )

        for requirement in self._order_requirements(requirements):
            alias = requirement["alias"]
            comp = requirement["component"]
            params = requirement["params"]
            dc_name = _to_pascal(alias) + "Context"
            fields = []
            for fname, fdef in comp.provides.items():
                fields.append(
                    FieldInfo(
                        name=_to_snake(fname),
                        type=_extract_type_from_field(fdef),
                    )
                )
            dataclasses.append(DataclassInfo(class_name=dc_name, fields=fields))
            setup_methods.append(
                MethodInfo(
                    name=f"setup_{_to_snake(alias)}",
                    params=[FieldInfo(name=_to_snake(name)) for name in params],
                    return_type=dc_name,
                )
            )
            setup_method_args.append(_build_step_args(params))

        used_action_method_names: set[str] = set()

        def build_action_method(
            step: StepDef,
            method_name: str,
        ) -> MethodInfo:
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

                    return_fields.append(
                        FieldInfo(
                            name=_to_snake(out_name),
                            type=out_type,
                        )
                    )

            ret_type: str
            if return_fields:
                result_stem = method_name.removeprefix("action_")
                dc_name = (
                    "".join(part.capitalize() for part in result_stem.split("_"))
                    + "Result"
                )
                dataclasses.append(
                    DataclassInfo(class_name=dc_name, fields=return_fields)
                )
                ret_type = dc_name
            else:
                ret_type = "None"

            return MethodInfo(
                name=method_name,
                params=params,
                return_type=ret_type,
            )

        for step in spec.steps:
            method_name = f"action_{_to_snake(step.id)}"
            action_methods.append(build_action_method(step, method_name))
            used_action_method_names.add(method_name)
            main_action_method_names.append(method_name)

        for alternative_flow in spec.alternative_flows:
            flow_method_names: list[str] = []
            for step in alternative_flow.steps:
                method_name = f"action_{_to_snake(step.id)}"
                if method_name in used_action_method_names:
                    method_name = (
                        f"action_{_to_snake(alternative_flow.name)}_"
                        f"{_to_snake(step.id)}"
                    )
                unique_name = method_name
                suffix = 2
                while unique_name in used_action_method_names:
                    unique_name = f"{method_name}_{suffix}"
                    suffix += 1

                action_methods.append(build_action_method(step, unique_name))
                used_action_method_names.add(unique_name)
                flow_method_names.append(unique_name)
            alt_action_method_names.append(flow_method_names)

        for i, post in enumerate(spec.postconditions):
            safe = _truncate_name(post)
            verify_methods.append(
                MethodInfo(
                    name=f"verify_{safe}",
                )
            )

        for inv_ref in spec.invariants:
            raw_reference = invariant_reference(inv_ref)
            inv_name = raw_reference.rsplit("/", 1)[-1]

            if inv_name:
                verify_methods.append(
                    MethodInfo(
                        name=f"verify_{_to_snake(inv_name)}",
                    )
                )

        return {
            "usecase_name": uc_name,
            "interface_class": interface_class,
            "interface_imports": sorted(
                [interface_class, *(dc.class_name for dc in dataclasses)]
            ),
            "dataclasses": dataclasses,
            "setup_methods": setup_methods,
            "setup_method_args": setup_method_args,
            "action_methods": action_methods,
            "main_action_method_names": main_action_method_names,
            "alt_action_method_names": alt_action_method_names,
            "verify_methods": verify_methods,
            "uses_any": any(
                field.type == "Any"
                for dataclass_info in dataclasses
                for field in dataclass_info.fields
            )
            or any(
                parameter.type == "Any"
                for method in [*setup_methods, *action_methods, *verify_methods]
                for parameter in method.params
            ),
        }

    @staticmethod
    def _validate_python_step_names(spec: UseCaseSpec) -> None:
        flows = [("happy path", spec.steps)]
        flows.extend(
            (f"alternative flow '{flow.name}'", flow.steps)
            for flow in spec.alternative_flows
        )
        for flow_name, steps in flows:
            seen: dict[str, str] = {}
            for step in steps:
                normalized = _to_snake(step.id)
                previous = seen.get(normalized)
                if previous is not None:
                    raise ValueError(
                        f"Step IDs '{previous}' and '{step.id}' in {flow_name} "
                        "normalize to the same Python name"
                    )
                seen[normalized] = step.id

    @staticmethod
    def _order_requirements(
        requirements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_alias: dict[str, dict[str, Any]] = {}
        for requirement in requirements:
            alias = requirement["alias"]
            normalized = _to_snake(alias)
            if normalized in by_alias:
                previous = by_alias[normalized]["alias"]
                raise ValueError(
                    f"Component aliases '{previous}' and '{alias}' normalize "
                    "to the same Python name"
                )
            by_alias[normalized] = requirement

        def dependency_aliases(value: Any) -> set[str]:
            aliases: set[str] = set()
            if isinstance(value, dict):
                for nested in value.values():
                    aliases.update(dependency_aliases(nested))
            elif isinstance(value, list):
                for nested in value:
                    aliases.update(dependency_aliases(nested))
            elif isinstance(value, str) and value.startswith("$"):
                parts = value[1:].split(".")
                if parts[0] == "requires" and len(parts) >= 2:
                    aliases.add(_to_snake(parts[1]))
                elif parts:
                    aliases.add(_to_snake(parts[0]))
            return aliases

        dependencies = {
            alias: dependency_aliases(requirement["params"]) & by_alias.keys()
            for alias, requirement in by_alias.items()
        }
        state: dict[str, str] = {}
        ordered: list[dict[str, Any]] = []

        def visit(alias: str, chain: tuple[str, ...] = ()) -> None:
            if state.get(alias) == "done":
                return
            if state.get(alias) == "visiting":
                cycle = " -> ".join((*chain, alias))
                raise ValueError(f"Circular component requirement bindings: {cycle}")

            state[alias] = "visiting"
            dependency_order = sorted(
                dependencies[alias],
                key=lambda item: by_alias[item]["index"],
            )
            for dependency in dependency_order:
                visit(dependency, (*chain, alias))
            state[alias] = "done"
            ordered.append(by_alias[alias])

        for alias in sorted(
            by_alias,
            key=lambda item: by_alias[item]["index"],
        ):
            visit(alias)
        return ordered

    def _build_orchestrator_context(
        self,
        spec: UseCaseSpec,
        registry: SpecRegistry,
        ctx: dict,
    ) -> dict[str, Any]:
        orch = dict(ctx)
        orch["fixture_name"] = _to_snake(spec.metadata.name) + "_impl"
        orch["test_name"] = _to_snake(spec.metadata.name)

        # setup_steps and verify_steps are never conditional (no when/skip_if).
        setup_steps: list[StepCall] = []
        for method, args in zip(
            ctx["setup_methods"],
            ctx["setup_method_args"],
            strict=True,
        ):
            var_name = method.name.replace("setup_", "")
            setup_steps.append(
                StepCall(
                    var=var_name,
                    method=method.name,
                    args=args,
                )
            )

        action_steps: list[StepCall] = []
        referenced_step_ids: set[str] = set()
        for referenced_step in spec.steps:
            referenced_step_ids.update(_collect_step_refs(referenced_step.input))
            referenced_step_ids.update(_collect_step_refs(referenced_step.when))
            referenced_step_ids.update(_collect_step_refs(referenced_step.skip_if))
        for alternative_flow in spec.alternative_flows:
            for referenced_step in alternative_flow.steps:
                referenced_step_ids.update(_collect_step_refs(referenced_step.input))
                referenced_step_ids.update(_collect_step_refs(referenced_step.when))
                referenced_step_ids.update(_collect_step_refs(referenced_step.skip_if))

        for i, step in enumerate(spec.steps):
            method = ctx["action_methods"][i]
            var = _to_snake(step.id)

            args = _build_step_args(step.input)
            when_expr, skip_if_expr = _step_when_skip(step)

            action_steps.append(
                StepCall(
                    var=var,
                    method=method.name,
                    args=args,
                    when_expr=when_expr,
                    skip_if_expr=skip_if_expr,
                    capture_result=step.id in referenced_step_ids,
                )
            )

        verify_steps: list[StepCall] = []
        for method in ctx["verify_methods"]:
            verify_steps.append(StepCall(var="_", method=method.name))

        step_id_to_method: dict[str, str] = {}
        for i, step in enumerate(spec.steps):
            step_id_to_method[step.id] = ctx["main_action_method_names"][i]

        main_step_index: dict[str, int] = {}
        main_step_deps: dict[str, set[str]] = {}
        for i, step in enumerate(spec.steps):
            main_step_index[step.id] = i
            main_step_deps[step.id] = (
                _collect_step_refs(step.input)
                | _collect_step_refs(step.when)
                | _collect_step_refs(step.skip_if)
                | set(step.depends_on)
            )

        def _transitive_deps(step_ids: set[str]) -> list[str]:
            """Topologically sorted list of all transitive step dependencies."""
            visited: set[str] = set()
            order: list[str] = []

            def _visit(sid: str) -> None:
                if sid in visited or sid not in main_step_index:
                    return
                visited.add(sid)
                for dep in sorted(
                    main_step_deps.get(sid, set()),
                    key=lambda item: main_step_index.get(item, len(main_step_index)),
                ):
                    _visit(dep)
                order.append(sid)

            for sid in sorted(
                step_ids,
                key=lambda item: main_step_index.get(item, len(main_step_index)),
            ):
                _visit(sid)
            return order

        alt_flow_tests: list[AltFlowTest] = []
        for alt_index, alt in enumerate(spec.alternative_flows):
            alt_class = _to_pascal(alt.name)

            needed_steps: set[str] = set()
            for step in alt.steps:
                needed_steps |= _collect_step_refs(step.input)
                needed_steps |= _collect_step_refs(step.when)
                needed_steps |= _collect_step_refs(step.skip_if)
                needed_steps |= set(step.depends_on)

            ordered_prereqs = _transitive_deps(needed_steps)

            prereq_steps: list[StepCall] = []
            for step_id in ordered_prereqs:
                idx = main_step_index[step_id]
                main_step = spec.steps[idx]
                prereq_var = _to_snake(main_step.id)
                prereq_method = step_id_to_method[main_step.id]
                prereq_args = _build_step_args(main_step.input)
                prereq_when, prereq_skip_if = _step_when_skip(main_step)
                prereq_steps.append(
                    StepCall(
                        var=prereq_var,
                        method=prereq_method,
                        args=prereq_args,
                        when_expr=prereq_when,
                        skip_if_expr=prereq_skip_if,
                        capture_result=main_step.id in referenced_step_ids,
                    )
                )

            alt_action_steps: list[StepCall] = []
            for step_index, step in enumerate(alt.steps):
                step_var = _to_snake(step.id)
                method_name = ctx["alt_action_method_names"][alt_index][step_index]
                step_args = _build_step_args(step.input)
                alt_when, alt_skip_if = _step_when_skip(step)

                alt_action_steps.append(
                    StepCall(
                        var=step_var,
                        method=method_name,
                        args=step_args,
                        when_expr=alt_when,
                        skip_if_expr=alt_skip_if,
                        capture_result=step.id in referenced_step_ids,
                    )
                )

            alt_action_calls = prereq_steps + alt_action_steps
            alt_setup_steps = _setup_steps_for_flow(
                setup_steps,
                alt_action_calls,
            )
            alt_flow_tests.append(
                AltFlowTest(
                    class_name=alt_class,
                    test_name=_to_snake(alt.name),
                    setup_steps=alt_setup_steps,
                    action_steps=alt_action_calls,
                    uses_inputs=_step_calls_use_inputs(
                        alt_setup_steps + alt_action_calls
                    ),
                )
            )

        happy_setup_steps = _setup_steps_for_flow(
            setup_steps,
            action_steps,
        )
        orch["setup_steps"] = happy_setup_steps
        orch["action_steps"] = action_steps
        orch["happy_uses_inputs"] = _step_calls_use_inputs(
            happy_setup_steps + action_steps
        )
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
    spec: UseCaseSpec,
    registry: SpecRegistry,
) -> list[ErrorTestDef]:
    """Extract error definitions from action specs referenced by use case steps."""
    results: list[ErrorTestDef] = []
    for step in spec.steps:
        action = registry.resolve_ref(step.use)
        if isinstance(action, ActionSpec) and action.errors:
            for err in action.errors:
                results.append(
                    ErrorTestDef(
                        step_id=step.id,
                        action_name=action.metadata.name,
                        error_code=err.code,
                        condition=err.condition,
                        status=err.status,
                    )
                )
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
        lines.append("        assert error is not None")
        lines.append(f"        assert error.get('code') == {repr(err.error_code)}")
        lines.append("")

    return "\n".join(lines), method_names
