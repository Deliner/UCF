from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ucf.ir.codec import (
    SEMANTIC_VERSION,
    _canonicalize,
    _format_location,
    _model_error_code,
    decode_strict_json_object,
)
from ucf.ir.errors import IRErrorCode, IRValidationError
from ucf.ir.trust_models import CURRENT_TRUST_IR_VERSION, TrustIR


def decode_trust_ir_json(payload: str | bytes) -> dict[str, Any]:
    decoded = decode_strict_json_object(payload)
    version = decoded.get("trust_ir_version")
    if not isinstance(version, str) or SEMANTIC_VERSION.fullmatch(version) is None:
        raise IRValidationError(
            IRErrorCode.MALFORMED_VERSION,
            "trust_ir_version must be normalized major.minor.patch",
            location="$.trust_ir_version",
        )
    if version != CURRENT_TRUST_IR_VERSION:
        raise IRValidationError(
            IRErrorCode.UNSUPPORTED_VERSION,
            (
                f"unsupported trust IR version {version!r}; "
                f"expected {CURRENT_TRUST_IR_VERSION!r}"
            ),
            location="$.trust_ir_version",
        )
    return decoded


def parse_trust_ir_json(payload: str | bytes) -> TrustIR:
    decoded = decode_trust_ir_json(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    try:
        document = TrustIR.model_validate_json(normalized)
    except ValidationError as error:
        first_error = error.errors(include_url=False)[0]
        code = _model_error_code(error)
        if any("confidence" in item["loc"] for item in error.errors()):
            code = IRErrorCode.INVALID_VALUE
        raise IRValidationError(
            code,
            first_error["msg"],
            location=_format_location(first_error["loc"]),
        ) from error
    from ucf.ir.trust_validation import validate_trust_semantics

    validate_trust_semantics(document)
    return document


def canonical_trust_ir_json(document: TrustIR) -> str:
    dumped = document.model_dump(mode="json")
    dumped["records"] = sorted(
        dumped["records"],
        key=lambda record: (record["kind"], record["id"]),
    )
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
