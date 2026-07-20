"""Invariant primitive — a business rule that can never be violated."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field

from ucf.models.base import Metadata, SpecModel


class InvariantType(StrEnum):
    DATA = "data"
    RELATIONSHIP = "relationship"
    AGGREGATE = "aggregate"
    STATE_MACHINE = "state-machine"
    TEMPORAL = "temporal"
    UNIQUENESS = "uniqueness"
    COMPOSITE = "composite"


class TransitionDef(SpecModel):
    """State machine transitions map: state -> list of allowed next states."""


class ForbiddenTransition(SpecModel):
    from_state: str = Field(alias="from")
    to: str
    reason: str

    model_config = ConfigDict(populate_by_name=True)


class AppliesTo(SpecModel):
    resource: str | None = None
    action: str | None = None
    usecase: str | None = None


class InvariantSpec(SpecModel):
    kind: Literal["invariant"] = "invariant"
    metadata: Metadata
    type: InvariantType
    rule: str | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list)
    entity: str | None = None
    field: str | None = None
    condition: str | None = None
    states: list[str] = Field(default_factory=list)
    transitions: dict[str, list[str]] = Field(default_factory=dict)
    forbidden: list[ForbiddenTransition] = Field(default_factory=list)
    applies_to: list[AppliesTo] = Field(default_factory=list)
    unique_fields: list[str] = Field(default_factory=list)
    scope: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    before: dict[str, str] = Field(default_factory=dict)
    after: dict[str, str] = Field(default_factory=dict)
    join: str | None = None
    composed_of: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)
    instances: list[dict[str, Any]] = Field(default_factory=list)
