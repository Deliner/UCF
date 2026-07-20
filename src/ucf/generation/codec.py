from __future__ import annotations

import hashlib
import json

from ucf.generation.models import (
    GenerationDocument,
    GenerationRequest,
    GenerationResult,
)
from ucf.ir import decode_strict_json_object
from ucf.ir.models import Digest


def canonical_generation_json(document: GenerationDocument) -> bytes:
    _validate_outbound_document(document)
    return (
        json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def canonical_generation_digest(
    document: GenerationDocument,
) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_generation_json(document)
        ).hexdigest(),
    )


def parse_generation_request_json(
    payload: str | bytes,
) -> GenerationRequest:
    decoded = decode_strict_json_object(payload)
    request = GenerationRequest.model_validate_json(
        json.dumps(
            decoded,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    )
    from ucf.generation.validation import validate_generation_request

    validate_generation_request(request)
    return request


def parse_generation_result_json(
    payload: str | bytes,
) -> GenerationResult:
    decoded = decode_strict_json_object(payload)
    result = GenerationResult.model_validate_json(
        json.dumps(
            decoded,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    )
    from ucf.generation.validation import (
        validate_generation_result_structure,
    )

    validate_generation_result_structure(result)
    return result


def _validate_outbound_document(document: GenerationDocument) -> None:
    from ucf.generation.validation import (
        validate_generation_request,
        validate_generation_result_structure,
    )

    if type(document) is GenerationRequest:
        validate_generation_request(document)
    elif type(document) is GenerationResult:
        validate_generation_result_structure(document)
    else:
        raise TypeError(
            "generation JSON requires an exact request or result model"
        )
