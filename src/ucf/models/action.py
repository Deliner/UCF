"""Action primitive — an atomic operation abstracted from the platform."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ucf.models.base import (
    EmitRef,
    ErrorDef,
    FieldDef,
    FieldType,
    Metadata,
    ResourceRead,
    ResourceWrite,
)


class HttpBinding(BaseModel):
    method: str
    path: str


class GrpcBinding(BaseModel):
    service: str
    method: str
    proto: str | None = None


class GraphqlBinding(BaseModel):
    operation: str
    name: str


class UiStep(BaseModel):
    click: str | None = None
    fill: str | None = None
    value: str | None = None
    assert_condition: str | None = Field(None, alias="assert")

    model_config = {"populate_by_name": True}


class UiBinding(BaseModel):
    steps: list[UiStep]


class CliBinding(BaseModel):
    command: str
    exit_code: int = 0


class KafkaBinding(BaseModel):
    topic: str


class Platform(BaseModel):
    http: HttpBinding | None = None
    grpc: GrpcBinding | None = None
    graphql: GraphqlBinding | None = None
    ui: UiBinding | None = None
    cli: CliBinding | None = None
    kafka: KafkaBinding | None = None


class ActionSpec(BaseModel):
    kind: Literal["action"] = "action"
    metadata: Metadata
    platform: Platform | None = None
    input: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    output: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    errors: list[ErrorDef] = Field(default_factory=list)
    reads: list[ResourceRead] = Field(default_factory=list)
    writes: list[ResourceWrite] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    emits: list[EmitRef] = Field(default_factory=list)

    @field_validator("input", "output", mode="before")
    @classmethod
    def _prefer_fielddef(cls, v: Any) -> Any:
        """Try to parse dict values as FieldDef before falling through to raw dict."""
        if not isinstance(v, dict):
            return v
        result: dict[str, Any] = {}
        for key, val in v.items():
            if isinstance(val, FieldDef):
                result[key] = val
            elif isinstance(val, dict) and "type" in val:
                type_val = val["type"]
                if isinstance(type_val, str):
                    try:
                        FieldType(type_val)
                        result[key] = FieldDef(**val)
                        continue
                    except (ValueError, ValidationError):
                        pass
                result[key] = val
            else:
                result[key] = val
        return result
