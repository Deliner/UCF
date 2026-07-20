"""Discriminated union of all spec types + factory function.

@implements("actions/parse-spec")
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.event import EventSpec
from ucf.models.invariant import InvariantSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec

AnySpec = (
    ActionSpec | EventSpec | ComponentSpec | ProtocolSpec | UseCaseSpec | InvariantSpec
)

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
    if not isinstance(data, dict):
        raise SpecParseError(
            f"Expected a YAML mapping, got {type(data).__name__}",
            path=source_path,
        )
    kind = data.get("kind")
    if kind is None:
        raise SpecParseError("Missing 'kind' field", path=source_path)

    model_cls = _KIND_MAP.get(kind)
    if model_cls is None:
        valid = ", ".join(sorted(_KIND_MAP))
        raise SpecParseError(
            f"Unknown kind '{kind}'. Valid kinds: {valid}",
            path=source_path,
        )

    try:
        json_data = json.dumps(data, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SpecParseError(
            f"Spec contains a non-JSON value: {exc}",
            path=source_path,
        ) from exc

    try:
        return model_cls.model_validate_json(
            json_data,
            strict=True,
            by_alias=True,
            by_name=False,
        )
    except ValidationError as exc:
        raise SpecParseError(
            f"Validation error in '{kind}' spec: {exc}",
            path=source_path,
        ) from exc
