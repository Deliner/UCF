from __future__ import annotations

import json
from collections.abc import Callable

from ucf.adapter_protocol import (
    AdapterPayload,
    ir_value_to_json_profile,
    json_profile_to_ir_value,
)
from ucf.implementation_evidence.codec import (
    parse_execution_verification_request_json,
    parse_execution_verification_result_json,
    parse_implementation_mapping_request_json,
    parse_implementation_mapping_result_json,
)
from ucf.implementation_evidence.models import (
    EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationMappingRequest,
    ImplementationMappingResult,
)


def implementation_mapping_request_to_payload(
    request: ImplementationMappingRequest,
) -> AdapterPayload:
    return _to_payload(request, IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI)


def implementation_mapping_request_from_payload(
    payload: AdapterPayload,
) -> ImplementationMappingRequest:
    return _from_payload(
        payload,
        schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
        parser=parse_implementation_mapping_request_json,
    )


def implementation_mapping_result_to_payload(
    result: ImplementationMappingResult,
) -> AdapterPayload:
    return _to_payload(result, IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI)


def implementation_mapping_result_from_payload(
    payload: AdapterPayload,
) -> ImplementationMappingResult:
    return _from_payload(
        payload,
        schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
        parser=parse_implementation_mapping_result_json,
    )


def execution_verification_request_to_payload(
    request: ExecutionVerificationRequest,
) -> AdapterPayload:
    return _to_payload(request, EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI)


def execution_verification_request_from_payload(
    payload: AdapterPayload,
) -> ExecutionVerificationRequest:
    return _from_payload(
        payload,
        schema_uri=EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
        parser=parse_execution_verification_request_json,
    )


def execution_verification_result_to_payload(
    result: ExecutionVerificationResult,
) -> AdapterPayload:
    return _to_payload(result, EXECUTION_VERIFICATION_RESULT_SCHEMA_URI)


def execution_verification_result_from_payload(
    payload: AdapterPayload,
) -> ExecutionVerificationResult:
    return _from_payload(
        payload,
        schema_uri=EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
        parser=parse_execution_verification_result_json,
    )


def _to_payload(document, schema_uri: str) -> AdapterPayload:
    return AdapterPayload(
        kind="adapter_payload",
        schema_uri=schema_uri,
        schema_version=IMPLEMENTATION_EVIDENCE_VERSION,
        value=json_profile_to_ir_value(
            document.model_dump(mode="json")
        ),
    )


def _from_payload(payload, *, schema_uri: str, parser: Callable):
    if not isinstance(payload, AdapterPayload):
        raise ValueError(
            "implementation evidence payload must be an adapter payload"
        )
    if (
        payload.schema_uri != schema_uri
        or payload.schema_version != IMPLEMENTATION_EVIDENCE_VERSION
    ):
        raise ValueError(
            "implementation evidence payload coordinates are incompatible"
        )
    decoded = ir_value_to_json_profile(payload.value)
    if not isinstance(decoded, dict):
        raise ValueError(
            "implementation evidence payload root must be a record"
        )
    encoded = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return parser(encoded)
