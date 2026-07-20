from __future__ import annotations

import json
from collections.abc import Callable

from ucf.adapter_protocol import (
    AdapterPayload,
    ir_value_to_json_profile,
    json_profile_to_ir_value,
)
from ucf.generation.codec import (
    parse_generation_request_json,
    parse_generation_result_json,
)
from ucf.generation.models import (
    GENERATION_PROFILE_VERSION,
    GENERATION_REQUEST_SCHEMA_URI,
    GENERATION_RESULT_SCHEMA_URI,
    GenerationRequest,
    GenerationResult,
)


def generation_request_to_payload(
    request: GenerationRequest,
) -> AdapterPayload:
    return _to_payload(
        request,
        GENERATION_REQUEST_SCHEMA_URI,
        expected_type=GenerationRequest,
    )


def generation_request_from_payload(
    payload: AdapterPayload,
) -> GenerationRequest:
    return _from_payload(
        payload,
        schema_uri=GENERATION_REQUEST_SCHEMA_URI,
        parser=parse_generation_request_json,
    )


def generation_result_to_payload(
    result: GenerationResult,
) -> AdapterPayload:
    return _to_payload(
        result,
        GENERATION_RESULT_SCHEMA_URI,
        expected_type=GenerationResult,
    )


def generation_result_from_payload(
    payload: AdapterPayload,
) -> GenerationResult:
    return _from_payload(
        payload,
        schema_uri=GENERATION_RESULT_SCHEMA_URI,
        parser=parse_generation_result_json,
    )


def _to_payload(
    document: GenerationRequest | GenerationResult,
    schema_uri: str,
    *,
    expected_type: type[GenerationRequest] | type[GenerationResult],
) -> AdapterPayload:
    if expected_type is GenerationRequest:
        if type(document) is not GenerationRequest:
            raise TypeError(
                "generation payload requires an exact generation request"
            )
        from ucf.generation.validation import validate_generation_request

        validate_generation_request(document)
    elif expected_type is GenerationResult:
        if type(document) is not GenerationResult:
            raise TypeError(
                "generation payload requires an exact generation result"
            )
        from ucf.generation.validation import (
            validate_generation_result_structure,
        )

        validate_generation_result_structure(document)
    else:
        raise TypeError("generation payload encoder type is unsupported")
    return AdapterPayload(
        kind="adapter_payload",
        schema_uri=schema_uri,
        schema_version=GENERATION_PROFILE_VERSION,
        value=json_profile_to_ir_value(
            document.model_dump(mode="json")
        ),
    )


def _from_payload(
    payload: object,
    *,
    schema_uri: str,
    parser: Callable,
):
    if not isinstance(payload, AdapterPayload):
        raise ValueError("generation wire value must be an adapter payload")
    if (
        payload.schema_uri != schema_uri
        or payload.schema_version != GENERATION_PROFILE_VERSION
    ):
        raise ValueError("generation payload coordinates are incompatible")
    decoded = ir_value_to_json_profile(payload.value)
    if not isinstance(decoded, dict):
        raise ValueError("generation payload root must be a record")
    return parser(
        json.dumps(
            decoded,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
