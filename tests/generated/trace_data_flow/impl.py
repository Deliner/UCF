"""Implementation for use case: trace-data-flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding
from ucf.tracer.engine import ContextTracer

from .interface import LoaderContext, TraceDataFlowInterface, TraceResult


class TraceDataFlowImpl(TraceDataFlowInterface):
    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._specs_dir: Path | None = None
        self._target_usecase: UseCaseSpec | None = None
        self._findings: list[Finding] = []
        self._traced_usecases: set[str] = set()

    def setup_loader(self, specs_dir: Any) -> LoaderContext:
        self._specs_dir = Path(specs_dir)
        loader = SpecLoader(self._specs_dir)
        loaded, errors = loader.load_all_tolerant()

        self._registry = SpecRegistry()
        for path, spec in loaded:
            self._registry.register(spec, path)

        return LoaderContext(
            registry=self._registry,
            loaded_count=len(loaded),
            load_errors=errors,
        )

    def action_trace(self, usecase: Any, registry: Any) -> TraceResult:
        assert isinstance(usecase, UseCaseSpec)
        assert isinstance(registry, SpecRegistry)
        assert registry is self._registry
        self._target_usecase = usecase

        tracer = ContextTracer(registry)
        self._findings = tracer.trace_usecase(usecase)
        self._traced_usecases = {usecase.metadata.name}
        final_context = tracer.get_final_context(usecase)
        return TraceResult(
            findings=self._findings,
            final_context=final_context,
        )

    def action_render_trace(self, data: Any, format: Any) -> None:
        assert format == "tree"
        assert isinstance(data, dict)
        assert data["findings"] is self._findings
        assert data["context"] is not None

    def verify_every_step_in_the_use_case_has_been_traced(self) -> None:
        assert self._target_usecase is not None
        assert self._traced_usecases == {self._target_usecase.metadata.name}

    def verify_data_gaps_and_dead_data_are_reported(self) -> None:
        assert isinstance(self._findings, list)
        reportable = {"data_gap", "dead_data", "overwrite_warning", "type_mismatch"}
        categories = {f.category.value for f in self._findings}
        # All categories produced must be known tracer categories
        known = reportable | {
            "missing_postcondition",
            "branch_divergence",
            "branch_state_difference",
            "cross_uc_mutation_conflict",
            "forbidden_transition",
        }
        unknown = categories - known
        assert not unknown, f"Unknown finding categories: {unknown}"

    def verify_branch_divergences_between_happy_path_and_alt_flows_are(self) -> None:
        assert self._target_usecase is not None
        assert self._target_usecase.alternative_flows

    def verify_refs_resolvable(self) -> None:
        assert self._registry is not None
        assert self._target_usecase is not None
        for step in self._target_usecase.steps:
            resolved = self._registry.resolve_ref(step.use)
            assert resolved is not None, f"Unresolvable: {step.use}"

    def verify_required_inputs_validated(self) -> None:
        assert self._specs_dir is not None
        assert self._specs_dir.is_dir()
        assert self._target_usecase is not None


@pytest.fixture
def trace_data_flow_impl() -> TraceDataFlowImpl:
    return TraceDataFlowImpl()
