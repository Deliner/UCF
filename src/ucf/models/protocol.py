"""Protocol primitive — an abstract interface with multiple implementations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ucf.models.base import FieldDef, Metadata, Ref, ResourceWrite


class ProtocolSpec(BaseModel):
    kind: Literal["protocol"] = "protocol"
    metadata: Metadata
    input: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    output: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    writes: list[ResourceWrite] = Field(default_factory=list)
    guarantees: list[str] = Field(default_factory=list)
    implementations: list[Ref] = Field(default_factory=list)
