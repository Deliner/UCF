from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from ucf.ir.errors import IRErrorCode, IRValidationError

if TYPE_CHECKING:
    from ucf.ir.models import BehaviorIR

CURRENT_IR_VERSION = "1.0.0"
SEMANTIC_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
MIN_SAFE_INTEGER = -9_007_199_254_740_991
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_JSON_NESTING = 128


class _DuplicateMemberError(ValueError):
    pass


class _NonFiniteNumberError(ValueError):
    pass


class _NonCanonicalIntegerError(ValueError):
    pass


class _UnsafeIntegerError(ValueError):
    pass


def _unique_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateMemberError(key)
        result[key] = value
    return result


def _reject_non_finite(token: str) -> None:
    raise _NonFiniteNumberError(token)


def _parse_integer(token: str) -> int:
    if token == "-0":
        raise _NonCanonicalIntegerError(token)
    digits = token.removeprefix("-")
    if len(digits) > 16:
        raise _UnsafeIntegerError
    value = int(token)
    if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        raise _UnsafeIntegerError
    return value


def _decode_text(payload: str | bytes) -> str:
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise IRValidationError(
                IRErrorCode.INVALID_JSON,
                "document is not valid UTF-8",
            ) from error
    elif isinstance(payload, str):
        text = payload
    else:
        raise TypeError("IR JSON payload must be str or bytes")

    if text.startswith("\ufeff"):
        raise IRValidationError(
            IRErrorCode.INVALID_JSON,
            "UTF-8 BOM is not permitted",
        )
    return text


def _validate_number_profile(value: Any) -> None:
    pending = [(value, "$", 0)]
    while pending:
        current, location, depth = pending.pop()
        if depth > MAX_JSON_NESTING:
            raise IRValidationError(
                IRErrorCode.INVALID_STRUCTURE,
                (
                    "document exceeds the maximum JSON nesting depth "
                    f"of {MAX_JSON_NESTING}"
                ),
                location=location,
            )
        if isinstance(current, dict):
            for key, nested in reversed(current.items()):
                pending.append((nested, f"{location}.{key}", depth + 1))
            continue
        if isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                pending.append(
                    (current[index], f"{location}[{index}]", depth + 1)
                )
            continue
        if (
            isinstance(current, bool)
            or current is None
            or isinstance(current, (int, str))
        ):
            continue
        if isinstance(current, float):
            raise IRValidationError(
                IRErrorCode.INVALID_VALUE,
                "JSON fractional numbers are not part of the IR v1 value profile",
                location=location,
            )


def decode_strict_json_object(payload: str | bytes) -> dict[str, Any]:
    """Decode the shared cross-runtime JSON profile without document semantics."""

    text = _decode_text(payload)
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_non_finite,
            parse_int=_parse_integer,
        )
    except _DuplicateMemberError as error:
        raise IRValidationError(
            IRErrorCode.DUPLICATE_JSON_MEMBER,
            f"duplicate object member {error.args[0]!r}",
        ) from error
    except _NonFiniteNumberError as error:
        raise IRValidationError(
            IRErrorCode.INVALID_VALUE,
            f"non-finite JSON number {error.args[0]!r} is not permitted",
        ) from error
    except _NonCanonicalIntegerError as error:
        raise IRValidationError(
            IRErrorCode.INVALID_VALUE,
            f"non-canonical JSON integer {error.args[0]!r} is not permitted",
        ) from error
    except _UnsafeIntegerError as error:
        raise IRValidationError(
            IRErrorCode.INVALID_VALUE,
            "JSON integer is outside the cross-runtime exact range",
        ) from error
    except RecursionError as error:
        raise IRValidationError(
            IRErrorCode.INVALID_STRUCTURE,
            (
                "document exceeds the maximum JSON nesting depth "
                f"of {MAX_JSON_NESTING}"
            ),
        ) from error
    except json.JSONDecodeError as error:
        raise IRValidationError(
            IRErrorCode.INVALID_JSON,
            error.msg,
            location=f"line {error.lineno}, column {error.colno}",
        ) from error

    if not isinstance(decoded, dict):
        raise IRValidationError(
            IRErrorCode.INVALID_STRUCTURE,
            "document root must be an object",
        )

    _validate_number_profile(decoded)
    return decoded


def decode_ir_json(payload: str | bytes) -> dict[str, Any]:
    decoded = decode_strict_json_object(payload)
    version = decoded.get("ir_version")
    if not isinstance(version, str) or SEMANTIC_VERSION.fullmatch(version) is None:
        raise IRValidationError(
            IRErrorCode.MALFORMED_VERSION,
            "ir_version must be normalized major.minor.patch",
            location="$.ir_version",
        )
    if version != CURRENT_IR_VERSION:
        raise IRValidationError(
            IRErrorCode.UNSUPPORTED_VERSION,
            f"unsupported IR version {version!r}; expected {CURRENT_IR_VERSION!r}",
            location="$.ir_version",
        )
    return decoded


def _format_location(location: tuple[str | int, ...]) -> str:
    formatted = "$"
    for segment in location:
        if isinstance(segment, int):
            formatted += f"[{segment}]"
        else:
            formatted += f".{segment}"
    return formatted


def _model_error_code(error: ValidationError) -> IRErrorCode:
    errors = error.errors()
    error_types = {item["type"] for item in errors}
    if "extra_forbidden" in error_types:
        return IRErrorCode.UNKNOWN_FIELD
    if "value_error" in error_types:
        return IRErrorCode.INVALID_VALUE
    if error_types & {"greater_than_equal", "less_than_equal"}:
        return IRErrorCode.INVALID_VALUE
    for item in errors:
        if item["type"] == "string_pattern_mismatch" and any(
            segment in {"decimal", "timestamp"} for segment in item["loc"]
        ):
            return IRErrorCode.INVALID_VALUE
    return IRErrorCode.INVALID_STRUCTURE


def parse_ir_json(payload: str | bytes) -> BehaviorIR:
    from ucf.ir.models import BehaviorIR

    decoded = decode_ir_json(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    try:
        document = BehaviorIR.model_validate_json(normalized)
    except ValidationError as error:
        first_error = error.errors(include_url=False)[0]
        location = _format_location(first_error["loc"])
        message = first_error["msg"]
        raise IRValidationError(
            _model_error_code(error),
            message,
            location=location,
        ) from error
    from ucf.ir.validation import validate_ir_semantics

    validate_ir_semantics(document)
    return document


_REFERENCE_SET_FIELDS = {
    "applies_to",
    "bindings",
    "effects",
    "invariants",
    "observations",
    "requires",
    "roots",
    "subjects",
}
_PORT_SET_FIELDS = {"input_ports", "output_ports"}


def _canonicalize(value: Any, *, owner_kind: str | None = None, field: str = "") -> Any:
    if isinstance(value, dict):
        kind = value.get("kind")
        return {
            key: _canonicalize(nested, owner_kind=kind, field=key)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        items = [
            _canonicalize(item, owner_kind=owner_kind, field=field)
            for item in value
        ]
        if field == "entities":
            return sorted(items, key=lambda item: (item["kind"], item["id"]))
        if field in _PORT_SET_FIELDS:
            return sorted(items, key=lambda item: item["name"])
        if field == "entries" and owner_kind == "record":
            return sorted(items, key=lambda item: item["name"])
        if field in _REFERENCE_SET_FIELDS:
            return sorted(
                items,
                key=lambda item: (item["target_kind"], item["target_id"]),
            )
        return items
    return value


def canonical_ir_json(document: BehaviorIR) -> str:
    dumped = document.model_dump(mode="json")
    canonical = _canonicalize(dumped)
    return (
        json.dumps(
            canonical,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
