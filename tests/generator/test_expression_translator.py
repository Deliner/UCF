"""Tests for _translate_expression helper."""

from __future__ import annotations

from ucf.generator.pytest_plugin import _translate_expression


def test_translate_expression():
    assert _translate_expression("$inputs.amount > 100") == "inputs.get('amount') > 100"
    assert _translate_expression("$steps.check-fraud.score == 5") == "check_fraud.score == 5"
    assert _translate_expression("$inputs.type == 'A' and $steps.foo.bar") == "inputs.get('type') == 'A' and foo.bar"


def test_translate_expression_empty_string():
    """Empty string passes through unchanged."""
    assert _translate_expression("") == ""


def test_translate_expression_no_bindings():
    """Expressions with no bindings pass through unchanged."""
    assert _translate_expression("1 + 1") == "1 + 1"
    assert _translate_expression("True and False") == "True and False"
    assert _translate_expression("x == 42") == "x == 42"


def test_translate_expression_requires_binding():
    """$requires bindings are resolved via _resolve_binding."""
    assert _translate_expression("$requires.database.connection") == "database.connection"
    assert _translate_expression("$requires.loader.registry.specs") == "loader.registry.specs"
