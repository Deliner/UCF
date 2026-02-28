"""Tests for tracer CLI output (conditional step display)."""

from __future__ import annotations

from ucf.models.component import StepDef
from ucf.tracer.display import format_step_label


def test_format_step_label_unconditional():
    """Unconditional step has no [?] prefix."""
    step = StepDef(id="create", use="actions/create-order")
    assert format_step_label(step) == "create"


def test_format_step_label_when():
    """Step with when shows [?] prefix and condition."""
    step = StepDef(
        id="confirm",
        use="actions/confirm-order",
        when="$inputs.amount > 100",
    )
    label = format_step_label(step)
    assert label.startswith("[?] ")
    assert "confirm" in label
    assert "(when: $inputs.amount > 100)" in label


def test_format_step_label_skip_if():
    """Step with skip_if shows [?] prefix and condition."""
    step = StepDef(
        id="optional",
        use="actions/optional-step",
        skip_if="$inputs.skip_optional",
    )
    label = format_step_label(step)
    assert label.startswith("[?] ")
    assert "optional" in label
    assert "(skip_if: $inputs.skip_optional)" in label
