from __future__ import annotations

import hashlib
import json

from ucf.implementation_evidence.models import (
    ExecutionEnvironment,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationEvidenceProfileDocument,
    ImplementationMappingRequest,
    ImplementationMappingResult,
)
from ucf.ir import decode_strict_json_object
from ucf.ir.models import Digest


def canonical_implementation_evidence_json(
    document: ImplementationEvidenceProfileDocument,
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


def parse_implementation_mapping_request_json(
    payload: str | bytes,
) -> ImplementationMappingRequest:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return ImplementationMappingRequest.model_validate_json(normalized)


def parse_implementation_mapping_result_json(
    payload: str | bytes,
) -> ImplementationMappingResult:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    result = ImplementationMappingResult.model_validate_json(normalized)
    from ucf.implementation_evidence.validation import (
        validate_implementation_mapping_result_structure,
    )

    validate_implementation_mapping_result_structure(result)
    return result


def parse_execution_verification_request_json(
    payload: str | bytes,
) -> ExecutionVerificationRequest:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return ExecutionVerificationRequest.model_validate_json(normalized)


def canonical_implementation_evidence_digest(
    document: ImplementationEvidenceProfileDocument,
) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_implementation_evidence_json(document)
        ).hexdigest(),
    )


def canonical_execution_environment_digest(
    environment: ExecutionEnvironment,
) -> Digest:
    encoded = (
        json.dumps(
            environment.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(encoded).hexdigest(),
    )


def parse_execution_verification_result_json(
    payload: str | bytes,
) -> ExecutionVerificationResult:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    result = ExecutionVerificationResult.model_validate_json(normalized)
    from ucf.implementation_evidence.validation import (
        validate_execution_verification_result_structure,
    )

    validate_execution_verification_result_structure(result)
    return result
