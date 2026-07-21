"""Discriminated union of all spec types + factory function.

@implements("actions/parse-spec")
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

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


def _find_internal_field_name(
    raw: object,
    validated: object,
    path: tuple[str | int, ...] = (),
) -> tuple[tuple[str | int, ...], str] | None:
    """Find a Python field name used instead of its public wire alias."""
    if isinstance(validated, BaseModel) and isinstance(raw, dict):
        for field_name, field in type(validated).model_fields.items():
            alias = field.alias if isinstance(field.alias, str) else field_name
            if alias != field_name and field_name in raw:
                return (*path, field_name), alias

            if alias not in raw:
                continue
            invalid = _find_internal_field_name(
                raw[alias],
                getattr(validated, field_name),
                (*path, alias),
            )
            if invalid is not None:
                return invalid
        return None

    if isinstance(validated, (list, tuple)) and isinstance(raw, list):
        for index, (raw_item, validated_item) in enumerate(zip(raw, validated)):
            invalid = _find_internal_field_name(
                raw_item,
                validated_item,
                (*path, index),
            )
            if invalid is not None:
                return invalid
        return None

    if isinstance(validated, dict) and isinstance(raw, dict):
        for key, validated_item in validated.items():
            if key not in raw:
                continue
            invalid = _find_internal_field_name(
                raw[key],
                validated_item,
                (*path, key),
            )
            if invalid is not None:
                return invalid
    return None


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

    normalized_data: dict[str, Any] = json.loads(json_data)
    try:
        model = model_cls.model_validate_json(json_data, strict=True)
    except ValidationError as exc:
        raise SpecParseError(
            f"Validation error in '{kind}' spec: {exc}",
            path=source_path,
        ) from exc

    invalid = _find_internal_field_name(normalized_data, model)
    if invalid is not None:
        input_path, public_alias = invalid
        field_name = str(input_path[-1])
        dotted_path = ".".join(str(part) for part in input_path)
        raise SpecParseError(
            f"Validation error in '{kind}' spec: internal field name "
            f"'{field_name}' at '{dotted_path}' is not allowed; use public "
            f"alias '{public_alias}'",
            path=source_path,
        )
    return model
