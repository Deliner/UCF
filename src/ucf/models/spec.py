"""Discriminated union of all spec types + factory function."""

from __future__ import annotations

from typing import Annotated

from pydantic import TypeAdapter, ValidationError

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.event import EventSpec
from ucf.models.invariant import InvariantSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec

AnySpec = ActionSpec | EventSpec | ComponentSpec | ProtocolSpec | UseCaseSpec | InvariantSpec

_KIND_MAP: dict[str, type[AnySpec]] = {
    "action": ActionSpec,
    "event": EventSpec,
    "component": ComponentSpec,
    "protocol": ProtocolSpec,
    "usecase": UseCaseSpec,
    "invariant": InvariantSpec,
}


class SpecParseError(Exception):
    def __init__(self, message: str, path: str | None = None) -> None:
        self.path = path
        super().__init__(message)


def parse_spec(data: dict, *, source_path: str | None = None) -> AnySpec:
    """Parse a raw dict into the appropriate spec model based on `kind`."""
    kind = data.get("kind")
    if kind is None:
        raise SpecParseError(f"Missing 'kind' field", path=source_path)

    model_cls = _KIND_MAP.get(kind)
    if model_cls is None:
        valid = ", ".join(sorted(_KIND_MAP))
        raise SpecParseError(
            f"Unknown kind '{kind}'. Valid kinds: {valid}",
            path=source_path,
        )

    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise SpecParseError(
            f"Validation error in '{kind}' spec: {exc}",
            path=source_path,
        ) from exc
