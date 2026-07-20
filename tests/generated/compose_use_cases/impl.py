"""Implementation for use case: compose-use-cases.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.composition import CompositionError, resolve_extends
from ucf.models.base import Metadata
from ucf.models.component import StepDef
from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import ComposeUseCasesInterface, LoaderContext, ResolveResult


def _make_uc(
    name: str,
    steps: list[dict[str, Any]] | None = None,
    postconditions: list[str] | None = None,
    extends: str | None = None,
    invariants: list[dict[str, str]] | None = None,
) -> UseCaseSpec:
    return UseCaseSpec(
        metadata=Metadata(name=name, version="0.1.0"),
        extends=extends,
        steps=[StepDef(**s) for s in (steps or [])],
        postconditions=postconditions or [],
        invariants=[{"$ref": r["$ref"]} for r in (invariants or [])],
    )


class ComposeUseCasesImpl(ComposeUseCasesInterface):
    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        loaded, errors = SpecLoader(Path(specs_dir)).load_all_tolerant()
        registry = SpecRegistry()
        for path, spec in loaded:
            registry.register(spec, path)

        children = [usecase for usecase in registry.usecases() if usecase.extends]
        if len(children) != 1:
            raise ValueError(
                "composition fixture must contain exactly one child use case"
            )

        child = children[0]
        parent_ref = child.extends.replace("$ref:", "")
        parent = registry.resolve_ref(parent_ref)
        if not isinstance(parent, UseCaseSpec):
            raise ValueError(f"composition parent does not resolve: {parent_ref}")

        self._registry = registry
        self._child = child
        self._parent = parent

        return LoaderContext(
            registry=registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_resolve(self, usecase: Any, registry: Any) -> ResolveResult:
        if not isinstance(usecase, UseCaseSpec):
            raise TypeError("usecase must be a UseCaseSpec")
        if not isinstance(registry, SpecRegistry):
            raise TypeError("registry must be a SpecRegistry")

        self._child = usecase
        self._registry = registry
        flattened, chain, parent_ids = resolve_extends(usecase, registry)
        self._flattened = flattened
        self._chain = chain
        self._parent_ids = parent_ids
        return ResolveResult(
            flattened=flattened,
            extends_chain=chain,
            parent_step_ids=parent_ids,
        )

    def verify_flattened_uc_has_parent_steps_followed_by_child_steps(self) -> None:
        step_ids = [s.id for s in self._flattened.steps]
        assert step_ids == ["p-step1", "p-step2", "c-step1"]

    def verify_parent_postconditions_are_preserved_in_the_result(self) -> None:
        assert "data is loaded" in self._flattened.postconditions
        assert "result is computed" in self._flattened.postconditions
        assert "view is rendered" in self._flattened.postconditions

    def verify_extends_chain_is_acyclic(self) -> None:
        assert len(self._chain) == len(set(self._chain))

        registry = SpecRegistry()
        a = _make_uc(
            "a",
            extends="$ref:use-cases/b",
            steps=[{"id": "a1", "use": "x", "input": {}}],
        )
        b = _make_uc(
            "b",
            extends="$ref:use-cases/a",
            steps=[{"id": "b1", "use": "x", "input": {}}],
        )
        registry.register(a)
        registry.register(b)
        with pytest.raises(CompositionError, match="CIRCULAR_EXTENDS"):
            resolve_extends(a, registry)

    def verify_no_step_id_appears_in_both_parent_and_child(self) -> None:
        parent_ids = set(self._parent_ids)
        child_ids = {s.id for s in self._child.steps}
        assert not parent_ids & child_ids

        registry = SpecRegistry()
        p = _make_uc("p", steps=[{"id": "clash", "use": "x", "input": {}}])
        c = _make_uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "clash", "use": "y", "input": {}}],
        )
        registry.register(p)
        registry.register(c)
        with pytest.raises(CompositionError, match="STEP_ID_CLASH"):
            resolve_extends(c, registry)

    def verify_no_circular_extends(self) -> None:
        assert len(self._chain) == len(set(self._chain))

    def verify_extends_no_step_id_clash(self) -> None:
        parent_ids = {s.id for s in self._parent.steps}
        child_ids = {s.id for s in self._child.steps}
        assert not parent_ids & child_ids

    def action_render_parent_error(self, data: Any, format: Any) -> None:
        self._exercise_composition_error("PARENT_NOT_FOUND", data, format)

    def action_render_cycle_error(self, data: Any, format: Any) -> None:
        self._exercise_composition_error("CIRCULAR_EXTENDS", data, format)

    def action_render_clash_error(self, data: Any, format: Any) -> None:
        self._exercise_composition_error("STEP_ID_CLASH", data, format)

    def _exercise_composition_error(
        self,
        error_code: str,
        data: Any,
        format: Any,
    ) -> None:
        expected_messages = {
            "PARENT_NOT_FOUND": "parent use case not found",
            "CIRCULAR_EXTENDS": "circular extends chain detected",
            "STEP_ID_CLASH": "step ID conflict between parent and child",
        }
        if data["message"] != expected_messages[error_code]:
            raise ValueError(
                f"message does not describe {error_code}: {data['message']}"
            )

        registry = SpecRegistry()
        if error_code == "PARENT_NOT_FOUND":
            child = _make_uc(
                "c",
                extends="$ref:use-cases/missing",
                steps=[{"id": "c1", "use": "x", "input": {}}],
            )
            registry.register(child)
        elif error_code == "CIRCULAR_EXTENDS":
            child = _make_uc(
                "a",
                extends="$ref:use-cases/b",
                steps=[{"id": "a1", "use": "x", "input": {}}],
            )
            parent = _make_uc(
                "b",
                extends="$ref:use-cases/a",
                steps=[{"id": "b1", "use": "y", "input": {}}],
            )
            registry.register(child)
            registry.register(parent)
        elif error_code == "STEP_ID_CLASH":
            parent = _make_uc(
                "p",
                steps=[{"id": "clash", "use": "x", "input": {}}],
            )
            child = _make_uc(
                "c",
                extends="$ref:use-cases/p",
                steps=[{"id": "clash", "use": "y", "input": {}}],
            )
            registry.register(parent)
            registry.register(child)
        else:
            raise ValueError(f"unsupported composition error: {error_code}")

        with pytest.raises(CompositionError, match=error_code):
            resolve_extends(child, registry)
        self._rendered_error = {
            "error_code": error_code,
            "data": data,
            "format": format,
        }

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError

        from ucf.models.action import ActionSpec

        # Pydantic rejects an ActionSpec without required metadata.
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def compose_use_cases_impl() -> ComposeUseCasesImpl:
    return ComposeUseCasesImpl()
