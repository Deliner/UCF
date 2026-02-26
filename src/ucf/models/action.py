"""Action primitive — an atomic operation abstracted from the platform."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ucf.models.base import EmitRef, ErrorDef, FieldDef, Metadata, ResourceRead, ResourceWrite


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
