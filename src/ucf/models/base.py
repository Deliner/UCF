"""Shared types used across all spec primitives."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class MutationType(str, Enum):
    CREATE = "create"
    SET = "set"
    INCREMENT = "increment"
    DECREMENT = "decrement"
    APPEND = "append"
    DELETE = "delete"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class Metadata(BaseModel):
    name: str
    version: str | None = None
    owner: str | None = None
    actor: str | None = None
    tags: list[str] = Field(default_factory=list)
    severity: Severity | None = None


class FieldDef(BaseModel):
    type: FieldType
    required: bool = False
    format: str | None = None
    min: float | None = None
    max: float | None = None
    enum: list[Any] | None = None
    description: str | None = None


class ErrorDef(BaseModel):
    status: str | int
    code: str
    condition: str


class ResourceRead(BaseModel):
    resource: str
    fields: list[str] = Field(default_factory=list)


class ResourceWrite(BaseModel):
    resource: str
    mutation: MutationType
    by: str | None = None


class EmitRef(BaseModel):
    event: str


class Ref(BaseModel):
    """A $ref to another spec file."""

    ref: str = Field(alias="$ref")

    model_config = {"populate_by_name": True}
