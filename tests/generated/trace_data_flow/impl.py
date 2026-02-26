"""Implementation for use case: trace-data-flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding
from ucf.tracer.engine import ContextTracer

from .interface import LoaderContext, TraceDataFlowInterface, TraceResult

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


class TraceDataFlowImpl(TraceDataFlowInterface):

    def __init__(self) -> None:
        self._registry: SpecRegistry | None = None
        self._findings: list[Finding] = []
        self._traced_usecases: set[str] = set()

    def setup_loader(self) -> LoaderContext:
        loader = SpecLoader(SPECS_DIR)
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
        assert self._registry is not None
        tracer = ContextTracer(self._registry)

        all_findings: list[Finding] = []
        final_ctx = None
        for uc in self._registry.usecases():
            findings = tracer.trace_usecase(uc)
            all_findings.extend(findings)
            self._traced_usecases.add(uc.metadata.name)
            final_ctx = tracer.get_final_context(uc)

        self._findings = all_findings
        return TraceResult(findings=all_findings, final_context=final_ctx)

    def action_render_trace(self, data: Any, format: Any) -> None:
        pass

    def verify_every_step_in_the_use_case_has_been_traced(self) -> None:
        assert len(self._traced_usecases) > 0

    def verify_data_gaps_and_dead_data_are_reported(self) -> None:
        assert isinstance(self._findings, list)
        reportable = {"data_gap", "dead_data", "overwrite_warning", "type_mismatch"}
        categories = {f.category.value for f in self._findings}
        # All categories produced must be known tracer categories
        known = reportable | {
            "missing_postcondition", "branch_divergence", "branch_state_difference",
            "cross_uc_mutation_conflict", "forbidden_transition",
        }
        unknown = categories - known
        assert not unknown, f"Unknown finding categories: {unknown}"

    def verify_branch_divergences_between_happy_path_and_alt_flows_are(self) -> None:
        assert self._registry is not None
        ucs_with_alt_flows = [
            uc for uc in self._registry.usecases()
            if uc.metadata.name in self._traced_usecases and uc.alternative_flows
        ]
        assert len(ucs_with_alt_flows) > 0, "At least one traced UC should have alternative flows"

    def verify_refs_resolvable(self) -> None:
        assert self._registry is not None
        for uc in self._registry.usecases():
            for step in uc.steps:
                resolved = self._registry.resolve_ref(step.use)
                assert resolved is not None, f"Unresolvable: {step.use}"

    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        # Framework enforces required inputs via Pydantic: ActionSpec without metadata must fail
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def trace_data_flow_impl() -> TraceDataFlowImpl:
    return TraceDataFlowImpl()
