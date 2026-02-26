"""Event primitive — an asynchronous fact that already happened."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ucf.models.base import FieldDef, Metadata


class EventTrigger(BaseModel):
    after: str


class DeliveryChannel(BaseModel):
    channel: str
    condition: str | None = None


class EventSpec(BaseModel):
    kind: Literal["event"] = "event"
    metadata: Metadata
    trigger: EventTrigger | None = None
    payload: dict[str, FieldDef | dict[str, Any]] = Field(default_factory=dict)
    delivery: list[DeliveryChannel] = Field(default_factory=list)
