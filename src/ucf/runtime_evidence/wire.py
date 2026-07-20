from __future__ import annotations

import json

from ucf.adapter_protocol import (
    AdapterPayload,
    ir_value_to_json_profile,
    json_profile_to_ir_value,
)
from ucf.runtime_evidence.codec import (
    parse_runtime_evidence_request_json,
    parse_runtime_evidence_result_json,
)
from ucf.runtime_evidence.models import (
    RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
    RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEvidenceImportRequest,
    RuntimeEvidenceResult,
)


def runtime_evidence_request_to_payload(
    request: RuntimeEvidenceImportRequest,
) -> AdapterPayload:
    return _to_payload(request, RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI)


def runtime_evidence_request_from_payload(
    payload: AdapterPayload,
) -> RuntimeEvidenceImportRequest:
    decoded = _from_payload(
        payload,
        schema_uri=RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
    )
    return parse_runtime_evidence_request_json(decoded)


def runtime_evidence_result_to_payload(
    result: RuntimeEvidenceResult,
) -> AdapterPayload:
    return _to_payload(result, RUNTIME_EVIDENCE_RESULT_SCHEMA_URI)


def runtime_evidence_result_from_payload(
    payload: AdapterPayload,
) -> RuntimeEvidenceResult:
    decoded = _from_payload(
        payload,
        schema_uri=RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
    )
    return parse_runtime_evidence_result_json(decoded)


def _to_payload(document, schema_uri: str) -> AdapterPayload:
    return AdapterPayload(
        kind="adapter_payload",
        schema_uri=schema_uri,
        schema_version=RUNTIME_EVIDENCE_VERSION,
        value=json_profile_to_ir_value(
            document.model_dump(mode="json")
        ),
    )


def _from_payload(
    payload,
    *,
    schema_uri: str,
) -> bytes:
    if not isinstance(payload, AdapterPayload):
        raise ValueError(
            "runtime evidence payload must be an adapter payload"
        )
    if (
        payload.schema_uri != schema_uri
        or payload.schema_version != RUNTIME_EVIDENCE_VERSION
    ):
        raise ValueError(
            "runtime evidence payload coordinates are incompatible"
        )
    decoded = ir_value_to_json_profile(payload.value)
    if not isinstance(decoded, dict):
        raise ValueError("runtime evidence payload root must be a record")
    return json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
