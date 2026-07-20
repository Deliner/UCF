from __future__ import annotations

from collections.abc import Mapping, Sequence

from ucf.ir.models import (
    BooleanValue,
    IntegerValue,
    IRValue,
    ListValue,
    NullValue,
    RecordEntry,
    RecordValue,
    StringValue,
)
from ucf.ir.validation import validate_ir_value

MAX_PROFILE_VALUE_DEPTH = 128


def json_profile_to_ir_value(value: object) -> IRValue:
    encoded = _encode_value(value, depth=0)
    validate_ir_value(encoded)
    return encoded


def ir_value_to_json_profile(value: IRValue) -> object:
    validate_ir_value(value)
    return _decode_value(value, depth=0)


def _encode_value(value: object, *, depth: int) -> IRValue:
    _check_depth(depth)
    if value is None:
        return NullValue(kind="null")
    if isinstance(value, bool):
        return BooleanValue(kind="boolean", value=value)
    if isinstance(value, str):
        return StringValue(kind="string", value=value)
    if isinstance(value, int):
        return IntegerValue(kind="integer", value=value)
    if isinstance(value, Mapping):
        if any(not isinstance(name, str) for name in value):
            raise ValueError("profile object names must be strings")
        return RecordValue(
            kind="record",
            entries=tuple(
                RecordEntry(
                    kind="record_entry",
                    name=name,
                    value=_encode_value(item, depth=depth + 1),
                )
                for name, item in sorted(value.items())
            ),
        )
    if isinstance(value, Sequence) and not isinstance(
        value,
        (bytes, bytearray),
    ):
        return ListValue(
            kind="list",
            items=tuple(
                _encode_value(item, depth=depth + 1)
                for item in value
            ),
        )
    raise ValueError("profile document contains an unsupported value")


def _decode_value(value: IRValue, *, depth: int) -> object:
    _check_depth(depth)
    if isinstance(value, NullValue):
        return None
    if isinstance(value, (BooleanValue, StringValue, IntegerValue)):
        return value.value
    if isinstance(value, ListValue):
        return [
            _decode_value(item, depth=depth + 1)
            for item in value.items
        ]
    if isinstance(value, RecordValue):
        names = tuple(entry.name for entry in value.entries)
        if len(names) != len(set(names)):
            raise ValueError("profile wire record has duplicate names")
        if names != tuple(sorted(names)):
            raise ValueError("profile wire record names must be sorted")
        return {
            entry.name: _decode_value(
                entry.value,
                depth=depth + 1,
            )
            for entry in value.entries
        }
    raise ValueError("profile wire value kind is unsupported")


def _check_depth(depth: int) -> None:
    if depth > MAX_PROFILE_VALUE_DEPTH:
        raise ValueError("profile wire value exceeds the nesting limit")
