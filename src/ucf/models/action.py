"""Action primitive — an atomic operation abstracted from the platform."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from ucf.models.base import (
    EmitRef,
    ErrorDef,
    FieldDef,
    Metadata,
    ResourceRead,
    ResourceWrite,
    SpecModel,
)


class HttpBinding(SpecModel):
    method: str
    path: str


class GrpcBinding(SpecModel):
    service: str
    method: str
    proto: str | None = None


class GraphqlBinding(SpecModel):
    operation: str
    name: str


class UiStep(SpecModel):
    click: str | None = None
    fill: str | None = None
    value: str | None = None
    assert_condition: str | None = Field(None, alias="assert")

    model_config = ConfigDict(populate_by_name=True)


class UiBinding(SpecModel):
    steps: list[UiStep]


class CliBinding(SpecModel):
    command: str
    exit_code: int = 0


class KafkaBinding(SpecModel):
    topic: str


class Platform(SpecModel):
    http: HttpBinding | None = None
    grpc: GrpcBinding | None = None
    graphql: GraphqlBinding | None = None
    ui: UiBinding | None = None
    cli: CliBinding | None = None
    kafka: KafkaBinding | None = None


class ActionSpec(SpecModel):
    kind: Literal["action"] = "action"
    metadata: Metadata
    platform: Platform | None = None
    input: dict[str, FieldDef] = Field(default_factory=dict)
    output: dict[str, FieldDef] = Field(default_factory=dict)
    errors: list[ErrorDef] = Field(default_factory=list)
    reads: list[ResourceRead] = Field(default_factory=list)
    writes: list[ResourceWrite] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    emits: list[EmitRef] = Field(default_factory=list)
