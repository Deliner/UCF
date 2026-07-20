"""Tests for use case model (StepDef conditional fields).

Covers when/skip_if expressions, mutual exclusivity, empty-string rejection,
and default behavior when neither condition is specified.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ucf.models.component import StepDef


def test_step_def_default_no_conditions():
    """Step with neither when nor skip_if runs unconditionally (default behavior)."""
    step = StepDef(id="test", use="mock")
    assert step.when is None
    assert step.skip_if is None


def test_step_def_supports_when():
    step = StepDef(id="test", use="mock", when="$inputs.x > 0")
    assert step.when == "$inputs.x > 0"


def test_step_def_supports_skip_if():
    step = StepDef(id="test", use="mock", skip_if="$inputs.y == False")
    assert step.skip_if == "$inputs.y == False"


def test_step_def_mutually_exclusive_conditions():
    with pytest.raises(
        ValidationError, match="Cannot specify both 'when' and 'skip_if'"
    ):
        StepDef(id="test", use="mock", when="True", skip_if="False")


def test_step_def_rejects_empty_when():
    with pytest.raises(
        ValidationError, match="Expression cannot be empty or whitespace-only"
    ):
        StepDef(id="test", use="mock", when="")


def test_step_def_rejects_whitespace_only_when():
    with pytest.raises(
        ValidationError, match="Expression cannot be empty or whitespace-only"
    ):
        StepDef(id="test", use="mock", when="   \t  ")


def test_step_def_rejects_empty_skip_if():
    with pytest.raises(
        ValidationError, match="Expression cannot be empty or whitespace-only"
    ):
        StepDef(id="test", use="mock", skip_if="")


def test_step_def_rejects_whitespace_only_skip_if():
    with pytest.raises(
        ValidationError, match="Expression cannot be empty or whitespace-only"
    ):
        StepDef(id="test", use="mock", skip_if="  ")
