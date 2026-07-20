"""UseCase primitive — a complete user scenario, the central unit of UCF."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from ucf.models.base import Metadata, Ref, SpecModel
from ucf.models.component import StepDef
from ucf.models.invariant import InvariantSpec

InvariantBinding = Ref | InvariantSpec


def invariant_reference(binding: InvariantBinding) -> str:
    """Return the canonical registry reference for an invariant binding."""

    if isinstance(binding, Ref):
        return binding.ref
    return f"invariants/{binding.metadata.name}"


class ComponentRequirement(SpecModel):
    ref: str = Field(alias="$ref")
    as_: str = Field(alias="as")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class AlternativeFlow(SpecModel):
    name: str
    trigger: str
    handles_error: str | None = None
    steps: list[StepDef] = Field(default_factory=list)


class ConcurrencyDef(SpecModel):
    conflict: str
    strategy: str
    description: str | None = None


class UseCaseSpec(SpecModel):
    kind: Literal["usecase"] = "usecase"
    metadata: Metadata
    extends: str | None = None
    trigger: str | None = None
    input_from_event: dict[str, str] = Field(default_factory=dict)
    requires: list[ComponentRequirement] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    assumed_preconditions: list[str] = Field(default_factory=list)
    steps: list[StepDef] = Field(default_factory=list)
    alternative_flows: list[AlternativeFlow] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    terminal: bool = False
    invariants: list[InvariantBinding] = Field(default_factory=list)
    concurrency: list[ConcurrencyDef] = Field(default_factory=list)
