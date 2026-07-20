"""Expression resolver for UCF $ expressions.

Parses and resolves expressions like $steps.create-order.order_id,
$auth.user_id, $event.message_id, $inputs.quantity, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class ExpressionNamespace(StrEnum):
    INPUTS = "inputs"
    STEPS = "steps"
    EVENT = "event"
    CONTEXT = "context"
    PARAMETERS = "parameters"
    OLD = "old"
    GENERATED = "generated"


@dataclass(frozen=True)
class ResolvedExpression:
    raw: str
    namespace: ExpressionNamespace | str
    path: list[str]

    @property
    def root(self) -> str:
        return self.path[0] if self.path else ""

    @property
    def field(self) -> str:
        return self.path[-1] if self.path else ""

    @property
    def step_id(self) -> str | None:
        """For $steps.X.field, returns X."""
        if self.namespace == ExpressionNamespace.STEPS and len(self.path) >= 2:
            return self.path[0]
        return None


_EXPR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_\-]*)(?:\.([a-zA-Z0-9_.\-]+))?")


_FULL_EXPR_RE = re.compile(r"^\$([a-zA-Z_][a-zA-Z0-9_\-]*)(?:\.([a-zA-Z0-9_.\-]+))?$")


def parse_expression(expr: str) -> ResolvedExpression | None:
    """Parse a single $ expression. Returns None if not a valid expression."""
    m = _FULL_EXPR_RE.match(expr.strip())
    if not m:
        return None

    namespace_str = m.group(1)
    rest = m.group(2) or ""
    path = [p for p in rest.split(".") if p]

    try:
        ns = ExpressionNamespace(namespace_str)
    except ValueError:
        ns = namespace_str  # type: ignore[assignment]

    return ResolvedExpression(raw=expr.strip(), namespace=ns, path=path)


def extract_expressions(text: str) -> list[ResolvedExpression]:
    """Extract all $ expressions from a string."""
    results: list[ResolvedExpression] = []
    for m in _EXPR_RE.finditer(text):
        full = m.group(0)
        parsed = parse_expression(full)
        if parsed is not None:
            results.append(parsed)
    return results


@dataclass
class ExpressionContext:
    """Tracks available data for expression validation."""

    available: dict[str, set[str]] = field(default_factory=dict)

    def add_namespace(self, ns: str, fields: set[str]) -> None:
        self.available.setdefault(ns, set()).update(fields)

    def add_step_outputs(self, step_id: str, fields: set[str]) -> None:
        self.available.setdefault("steps", set())
        for f in fields:
            self.available["steps"].add(f"{step_id}.{f}")

    def add_component(self, alias: str, fields: set[str]) -> None:
        for f in fields:
            self.available.setdefault(alias, set()).add(f)

    def can_resolve(self, expr: ResolvedExpression) -> bool:
        ns = expr.namespace if isinstance(expr.namespace, str) else expr.namespace.value

        if ns in ("generated", "context", "old"):
            return True

        if ns not in self.available:
            component_aliases = {
                alias
                for alias in self.available
                if alias not in {n.value for n in ExpressionNamespace}
            }
            if ns in component_aliases:
                fields = self.available.get(ns, set())
                if not expr.path:
                    return True
                return self._match_path(expr.path, fields)
            return False

        fields = self.available.get(ns, set())
        if not expr.path:
            return True

        return self._match_path(expr.path, fields)

    @staticmethod
    def _match_path(path: list[str], fields: set[str]) -> bool:
        full_path = ".".join(path)
        if full_path in fields:
            return True
        for i in range(len(path), 0, -1):
            partial = ".".join(path[:i])
            if partial in fields:
                return True
        return False


@dataclass
class ExpressionError:
    expression: str
    location: str
    message: str


def validate_expressions_in_value(
    value: str | dict | list,
    ctx: ExpressionContext,
    location: str,
) -> list[ExpressionError]:
    """Validate all $ expressions found in a value."""
    errors: list[ExpressionError] = []

    if isinstance(value, str):
        for expr in extract_expressions(value):
            if not ctx.can_resolve(expr):
                errors.append(
                    ExpressionError(
                        expression=expr.raw,
                        location=location,
                        message=f"Cannot resolve '{expr.raw}': "
                        f"namespace '{expr.namespace}' not available",
                    )
                )
    elif isinstance(value, dict):
        for k, v in value.items():
            errors.extend(validate_expressions_in_value(v, ctx, f"{location}.{k}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            errors.extend(validate_expressions_in_value(item, ctx, f"{location}[{i}]"))

    return errors
