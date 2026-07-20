"""Compatibility checks for language-neutral string enum values."""

from __future__ import annotations

from enum import StrEnum

import pytest

from ucf.expressions.resolver import ExpressionNamespace
from ucf.graph.dependency import EdgeType
from ucf.models.base import FieldType, MutationType, Severity
from ucf.models.invariant import InvariantType
from ucf.tracer.context import FindingCategory, FindingSeverity, SlotState
from ucf.validator.core import IssueCategory, IssueSeverity

STRING_ENUMS: tuple[type[StrEnum], ...] = (
    ExpressionNamespace,
    EdgeType,
    FieldType,
    MutationType,
    Severity,
    InvariantType,
    SlotState,
    FindingSeverity,
    FindingCategory,
    IssueSeverity,
    IssueCategory,
)


@pytest.mark.parametrize("enum_type", STRING_ENUMS, ids=lambda enum: enum.__name__)
def test_string_enum_renders_its_language_neutral_value(
    enum_type: type[StrEnum],
) -> None:
    for member in enum_type:
        assert str(member) == member.value
