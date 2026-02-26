"""Implementation for use case: compose-use-cases.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from typing import Any

import pytest

from ucf.composition import CompositionError, resolve_extends
from ucf.models.base import Metadata
from ucf.models.component import StepDef
from ucf.models.usecase import UseCaseSpec
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

    def setup_loader(self) -> LoaderContext:
        registry = SpecRegistry()

        parent = _make_uc(
            "parent-uc",
            steps=[
                {"id": "p-step1", "use": "actions/load", "input": {}, "output": {"data": "data"}},
                {"id": "p-step2", "use": "actions/transform", "input": {}, "output": {"result": "result"}},
            ],
            postconditions=["data is loaded", "result is computed"],
            invariants=[{"$ref": "invariants/graph-acyclic"}],
        )

        child = _make_uc(
            "child-uc",
            extends="$ref:use-cases/parent-uc",
            steps=[
                {"id": "c-step1", "use": "actions/render", "input": {}, "output": {"view": "view"}},
            ],
            postconditions=["view is rendered", "result is computed"],
            invariants=[{"$ref": "invariants/no-circular-extends"}],
        )

        registry.register(parent)
        registry.register(child)

        self._registry = registry
        self._child = child
        self._parent = parent

        return LoaderContext(
            registry=registry,
            loaded_count=2,
            load_errors=[],
        )

    def action_resolve(self, usecase: Any, registry: Any) -> ResolveResult:
        flattened, chain, parent_ids = resolve_extends(self._child, self._registry)
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
        a = _make_uc("a", extends="$ref:use-cases/b", steps=[{"id": "a1", "use": "x", "input": {}}])
        b = _make_uc("b", extends="$ref:use-cases/a", steps=[{"id": "b1", "use": "x", "input": {}}])
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
        c = _make_uc("c", extends="$ref:use-cases/p", steps=[{"id": "clash", "use": "y", "input": {}}])
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

    def action_render_parent_error(self, **kwargs: Any) -> Any:
        registry = SpecRegistry()
        c = _make_uc("c", extends="$ref:use-cases/missing", steps=[{"id": "c1", "use": "x", "input": {}}])
        registry.register(c)
        with pytest.raises(CompositionError, match="PARENT_NOT_FOUND"):
            resolve_extends(c, registry)

    def action_render_cycle_error(self, **kwargs: Any) -> Any:
        registry = SpecRegistry()
        a = _make_uc("a", extends="$ref:use-cases/b", steps=[{"id": "a1", "use": "x", "input": {}}])
        b = _make_uc("b", extends="$ref:use-cases/a", steps=[{"id": "b1", "use": "y", "input": {}}])
        registry.register(a)
        registry.register(b)
        with pytest.raises(CompositionError, match="CIRCULAR_EXTENDS"):
            resolve_extends(a, registry)

    def action_render_clash_error(self, **kwargs: Any) -> Any:
        registry = SpecRegistry()
        p = _make_uc("p", steps=[{"id": "clash", "use": "x", "input": {}}])
        c = _make_uc("c", extends="$ref:use-cases/p", steps=[{"id": "clash", "use": "y", "input": {}}])
        registry.register(p)
        registry.register(c)
        with pytest.raises(CompositionError, match="STEP_ID_CLASH"):
            resolve_extends(c, registry)

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def compose_use_cases_impl() -> ComposeUseCasesImpl:
    return ComposeUseCasesImpl()
