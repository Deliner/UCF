from __future__ import annotations

import hashlib
import json

from pydantic import TypeAdapter

from ucf.ir import decode_strict_json_object
from ucf.ir.models import Digest
from ucf.runtime_evidence.models import (
    RuntimeEnvironment,
    RuntimeEvidenceImportRequest,
    RuntimeEvidencePolicy,
    RuntimeEvidenceProfileDocument,
    RuntimeEvidenceResult,
)

_RESULT_ADAPTER = TypeAdapter(RuntimeEvidenceResult)


def canonical_runtime_evidence_json(
    document: RuntimeEvidenceProfileDocument,
) -> bytes:
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


def parse_runtime_evidence_policy_json(
    payload: str | bytes,
) -> RuntimeEvidencePolicy:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return RuntimeEvidencePolicy.model_validate_json(normalized)


def parse_runtime_environment_json(
    payload: str | bytes,
) -> RuntimeEnvironment:
    return _parse_runtime_evidence_json(payload, RuntimeEnvironment)


def parse_runtime_evidence_request_json(
    payload: str | bytes,
) -> RuntimeEvidenceImportRequest:
    return _parse_runtime_evidence_json(
        payload,
        RuntimeEvidenceImportRequest,
    )


def parse_runtime_evidence_result_json(
    payload: str | bytes,
) -> RuntimeEvidenceResult:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    result = _RESULT_ADAPTER.validate_json(normalized)
    from ucf.runtime_evidence.validation import (
        validate_runtime_evidence_result_structure,
    )

    validate_runtime_evidence_result_structure(result)
    return result


def canonical_runtime_evidence_digest(
    document: RuntimeEvidenceProfileDocument,
) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_runtime_evidence_json(document)
        ).hexdigest(),
    )


def _parse_runtime_evidence_json(payload, model):
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)
