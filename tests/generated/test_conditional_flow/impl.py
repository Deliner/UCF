"""Implementation for use case: test-conditional-flow.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from typing import Any

import pytest

from .interface import StepAResult, TestConditionalFlowInterface


class TestConditionalFlowImpl(TestConditionalFlowInterface):
    def __init__(self) -> None:
        self._step_value: int | None = None
        self._executed_steps: set[str] = set()

    # ── State Setup ──

    # ── Actions ──

    def action_step_a(self, threshold: Any) -> StepAResult:
        """Return the explicit threshold used by the conditional expressions."""
        self._step_value = int(threshold)
        return StepAResult(value=self._step_value)

    def action_step_b(self, value: Any) -> None:
        """Executed when step_a.value > 10."""
        assert int(value) > 10
        self._executed_steps.add("step-b")

    def action_step_c(self, value: Any) -> None:
        """Executed when step_a.value <= 10 (skip_if when > 10)."""
        assert int(value) <= 10
        self._executed_steps.add("step-c")

    # ── Verifications ──

    def verify_conditional_execution_works(self) -> None:
        assert self._step_value is not None
        expected = {"step-b"} if self._step_value > 10 else {"step-c"}
        assert self._executed_steps == expected


@pytest.fixture
def test_conditional_flow_impl() -> TestConditionalFlowImpl:
    return TestConditionalFlowImpl()
