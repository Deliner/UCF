"""Implementation for use case: test-conditional-flow.

Fill in the method bodies below. This file is never overwritten by `ucf generate`.
"""

from __future__ import annotations

from typing import Any

import pytest

from .interface import TestConditionalFlowInterface, StepAResult


class TestConditionalFlowImpl(TestConditionalFlowInterface):

    # ── State Setup ──

    # ── Actions ──

    def action_step_a(self, threshold: Any) -> StepAResult:
        """Return value = threshold. For dogfooding: threshold=11 triggers step-b, skips step-c."""
        t = threshold if threshold is not None else 11
        return StepAResult(value=int(t))

    def action_step_b(self, value: Any) -> None:
        """Executed when step_a.value > 10."""
        pass

    def action_step_c(self, value: Any) -> None:
        """Executed when step_a.value <= 10 (skip_if when > 10)."""
        pass

    # ── Verifications ──

    def verify_conditional_execution_works(self) -> None:
        """Verify conditional execution completed."""
        pass


@pytest.fixture
def test_conditional_flow_impl() -> TestConditionalFlowImpl:
    return TestConditionalFlowImpl()
