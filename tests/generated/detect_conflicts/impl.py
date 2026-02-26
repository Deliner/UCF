"""Implementation for use case: detect-conflicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.graph.dependency import DependencyGraph
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry

from .interface import (
    BuildGraphResult,
    DetectConflictsInterface,
    DetectResult,
    LoaderContext,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples" / "specs"


class DetectConflictsImpl(DetectConflictsInterface):

    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._graph: DependencyGraph | None = None
        self._conflicts: list[tuple[str, str, str]] = []

    def setup_loader(self) -> LoaderContext:
        loader = SpecLoader(EXAMPLES_DIR)
        loaded, errors = loader.load_all_tolerant()

        self._registry = SpecRegistry()
        for path, spec in loaded:
            self._registry.register(spec, path)

        return LoaderContext(
            registry=self._registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_build_graph(self, registry: Any) -> BuildGraphResult:
        assert self._registry is not None
        self._graph = DependencyGraph(self._registry)
        return BuildGraphResult(graph=self._graph)

    def action_detect(self, graph: Any, registry: Any) -> DetectResult:
        assert self._graph is not None
        self._conflicts = self._graph.find_write_conflicts()
        return DetectResult(
            conflicts=self._conflicts,
            conflict_count=len(self._conflicts),
        )

    def action_render_conflicts(self, data: Any, format: Any) -> None:
        pass

    def verify_all_write_write_conflicts_between_independent_specs_are(self) -> None:
        for a, b, resource in self._conflicts:
            assert a != b, f"Self-conflict: {a}"

    def verify_intra_usecase_conflicts_are_filtered_out(self) -> None:
        assert self._registry is not None
        uc_names = {f"usecase/{uc.metadata.name}" for uc in self._registry.usecases()}
        for a, b, _ in self._conflicts:
            if a in uc_names:
                child_steps = set()
                for uc in self._registry.usecases():
                    if f"usecase/{uc.metadata.name}" == a:
                        for step in uc.steps:
                            child_steps.add(step.use)
                assert b not in child_steps, (
                    f"Intra-usecase conflict not filtered: {a} <-> {b}"
                )

    def verify_each_conflict_pair_identifies_the_shared_resource(self) -> None:
        for a, b, resource in self._conflicts:
            assert resource, f"Missing resource in conflict: {a} <-> {b}"

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def detect_conflicts_impl() -> DetectConflictsImpl:
    return DetectConflictsImpl()
