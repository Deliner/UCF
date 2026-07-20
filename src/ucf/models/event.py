"""Event primitive — an asynchronous fact that already happened."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ucf.models.base import FieldDef, Metadata, SpecModel


class EventTrigger(SpecModel):
    after: str


class DeliveryChannel(SpecModel):
    channel: str
    condition: str | None = None


class EventSpec(SpecModel):
    kind: Literal["event"] = "event"
    metadata: Metadata
    trigger: EventTrigger | None = None
    payload: dict[str, FieldDef] = Field(default_factory=dict)
    delivery: list[DeliveryChannel] = Field(default_factory=list)
