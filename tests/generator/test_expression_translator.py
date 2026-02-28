"""Tests for _translate_expression helper."""

from __future__ import annotations

from ucf.generator.pytest_plugin import _translate_expression


def test_translate_expression():
    assert _translate_expression("$inputs.amount > 100") == "inputs.get('amount') > 100"
    assert _translate_expression("$steps.check-fraud.score == 5") == "check_fraud.score == 5"
    assert _translate_expression("$inputs.type == 'A' and $steps.foo.bar") == "inputs.get('type') == 'A' and foo.bar"
