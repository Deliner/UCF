"""Shared types used across all spec primitives."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpecModel(BaseModel):
    """Strict base for every modeled specification object."""

    model_config = ConfigDict(extra="forbid")


class FieldType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class MutationType(StrEnum):
    CREATE = "create"
    SET = "set"
    INCREMENT = "increment"
    DECREMENT = "decrement"
    APPEND = "append"
    DELETE = "delete"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class Metadata(SpecModel):
    name: str
    version: str | None = None
    owner: str | None = None
    actor: str | None = None
    tags: list[str] = Field(default_factory=list)
    severity: Severity | None = None
    description: str | None = None


class FieldDef(SpecModel):
    type: FieldType
    required: bool = False
    format: str | None = None
    min: float | None = None
    max: float | None = None
    enum: list[Any] | None = None
    description: str | None = None


class ErrorDef(SpecModel):
    status: str | int
    code: str
    condition: str
    description: str | None = None


class ResourceRead(SpecModel):
    resource: str
    fields: list[str] = Field(default_factory=list)


class ResourceWrite(SpecModel):
    resource: str
    mutation: MutationType
    by: str | None = None
    fields: list[str] = Field(default_factory=list)


class EmitRef(SpecModel):
    event: str


class Ref(SpecModel):
    """A $ref to another spec file."""

    ref: str = Field(alias="$ref")

    model_config = ConfigDict(populate_by_name=True)
