"""Tests for use case model (StepDef conditional fields)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ucf.models.component import StepDef


def test_step_def_supports_when():
    step = StepDef(id="test", use="mock", when="$inputs.x > 0")
    assert step.when == "$inputs.x > 0"


def test_step_def_supports_skip_if():
    step = StepDef(id="test", use="mock", skip_if="$inputs.y == False")
    assert step.skip_if == "$inputs.y == False"


def test_step_def_mutually_exclusive_conditions():
    with pytest.raises(ValidationError, match="Cannot specify both 'when' and 'skip_if'"):
        StepDef(id="test", use="mock", when="True", skip_if="False")
