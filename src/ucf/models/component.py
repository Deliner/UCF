"""Component primitive — a reusable block of steps (function analog)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ucf.models.base import FieldDef, Metadata


class StepDef(BaseModel):
    id: str
    use: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, str] = Field(default_factory=dict)
    when: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    postcondition: str | None = None


class ComponentSpec(BaseModel):
    kind: Literal["component"] = "component"
    metadata: Metadata
    parameters: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    provides: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    steps: list[StepDef] = Field(default_factory=list)
