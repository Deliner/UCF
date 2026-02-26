"""Unit tests for expression parsing and resolution."""

from __future__ import annotations

import pytest

from ucf.expressions.resolver import (
    ExpressionContext,
    ExpressionNamespace,
    ResolvedExpression,
    extract_expressions,
    parse_expression,
    validate_expressions_in_value,
)


class TestParseExpression:
    def test_steps_ref(self):
        r = parse_expression("$steps.create-order.order_id")
        assert r is not None
        assert r.namespace == ExpressionNamespace.STEPS
        assert r.step_id == "create-order"
        assert r.field == "order_id"

    def test_inputs_ref(self):
        r = parse_expression("$inputs.quantity")
        assert r is not None
        assert r.namespace == ExpressionNamespace.INPUTS
        assert r.root == "quantity"

    def test_component_alias(self):
        r = parse_expression("$auth.user_id")
        assert r is not None
        assert r.namespace == "auth"
        assert r.field == "user_id"

    def test_event_ref(self):
        r = parse_expression("$event.message_id")
        assert r is not None
        assert r.namespace == ExpressionNamespace.EVENT

    def test_generated_ref(self):
        r = parse_expression("$generated.uuid")
        assert r is not None
        assert r.namespace == ExpressionNamespace.GENERATED

    def test_invalid_expr(self):
        assert parse_expression("not-an-expression") is None
        assert parse_expression("") is None

    def test_bare_namespace(self):
        r = parse_expression("$inputs")
        assert r is not None
        assert r.path == []
        assert r.root == ""

    def test_trailing_garbage_rejected(self):
        assert parse_expression("$inputs.x THIS IS GARBAGE") is None


class TestExtractExpressions:
    def test_multi(self):
        text = "$steps.a.x and $inputs.y"
        results = extract_expressions(text)
        assert len(results) == 2

    def test_no_expressions(self):
        assert extract_expressions("just plain text") == []


class TestExpressionContext:
    def test_can_resolve_inputs(self):
        ctx = ExpressionContext()
        ctx.add_namespace("inputs", {"quantity", "price"})
        expr = parse_expression("$inputs.quantity")
        assert ctx.can_resolve(expr)

    def test_cannot_resolve_missing(self):
        ctx = ExpressionContext()
        ctx.add_namespace("inputs", {"x"})
        expr = parse_expression("$inputs.missing_field")
        assert not ctx.can_resolve(expr)

    def test_component_alias_resolution(self):
        ctx = ExpressionContext()
        ctx.add_component("auth", {"user_id", "token"})
        expr = parse_expression("$auth.user_id")
        assert ctx.can_resolve(expr)

    def test_component_alias_missing_field(self):
        ctx = ExpressionContext()
        ctx.add_component("auth", {"user_id"})
        expr = parse_expression("$auth.missing")
        assert not ctx.can_resolve(expr)

    def test_step_outputs(self):
        ctx = ExpressionContext()
        ctx.add_step_outputs("create-order", {"order_id", "total"})
        expr = parse_expression("$steps.create-order.order_id")
        assert ctx.can_resolve(expr)

    def test_generated_always_resolves(self):
        ctx = ExpressionContext()
        expr = parse_expression("$generated.uuid")
        assert ctx.can_resolve(expr)

    def test_context_always_resolves(self):
        ctx = ExpressionContext()
        expr = parse_expression("$context.timestamp")
        assert ctx.can_resolve(expr)

    def test_old_always_resolves(self):
        ctx = ExpressionContext()
        expr = parse_expression("$old.status")
        assert ctx.can_resolve(expr)

    def test_unknown_namespace_fails(self):
        ctx = ExpressionContext()
        expr = parse_expression("$nonexistent.field")
        assert not ctx.can_resolve(expr)


class TestValidateExpressionsInValue:
    def test_valid_string(self):
        ctx = ExpressionContext()
        ctx.add_namespace("inputs", {"x"})
        errors = validate_expressions_in_value("$inputs.x", ctx, "test")
        assert errors == []

    def test_invalid_string(self):
        ctx = ExpressionContext()
        errors = validate_expressions_in_value("$missing.field", ctx, "test")
        assert len(errors) == 1

    def test_nested_dict(self):
        ctx = ExpressionContext()
        ctx.add_namespace("inputs", {"a"})
        errors = validate_expressions_in_value(
            {"key": "$inputs.a", "bad": "$missing.b"}, ctx, "test",
        )
        assert len(errors) == 1

    def test_list(self):
        ctx = ExpressionContext()
        errors = validate_expressions_in_value(
            ["$unknown.x", "plain text"], ctx, "test",
        )
        assert len(errors) == 1
