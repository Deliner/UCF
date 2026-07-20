"""Protocol primitive — an abstract interface with multiple implementations."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ucf.models.base import FieldDef, Metadata, Ref, ResourceWrite, SpecModel
from ucf.models.component import ComponentSpec

ImplementationBinding = Ref | ComponentSpec


def implementation_reference(binding: ImplementationBinding) -> str:
    """Return the canonical registry reference for a protocol implementation."""

    if isinstance(binding, Ref):
        return binding.ref
    return f"components/{binding.metadata.name}"


class ProtocolSpec(SpecModel):
    kind: Literal["protocol"] = "protocol"
    metadata: Metadata
    input: dict[str, FieldDef] = Field(default_factory=dict)
    output: dict[str, FieldDef] = Field(default_factory=dict)
    writes: list[ResourceWrite] = Field(default_factory=list)
    guarantees: list[str] = Field(default_factory=list)
    implementations: list[ImplementationBinding] = Field(default_factory=list)
