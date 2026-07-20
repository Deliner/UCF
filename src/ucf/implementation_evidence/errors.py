from __future__ import annotations

from enum import StrEnum


class ImplementationEvidenceErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CAPABILITY_MISMATCH = "capability_mismatch"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    ENVIRONMENT_IDENTITY_MISMATCH = "environment_identity_mismatch"
    EVIDENCE_NOT_PASSED = "evidence_not_passed"
    INCOMPLETE_BINDING = "incomplete_binding"
    INVALID_STRUCTURE = "invalid_structure"
    NON_CANONICAL_ORDER = "non_canonical_order"
    PROCEDURE_MISMATCH = "procedure_mismatch"
    PRODUCER_IDENTITY_MISMATCH = "producer_identity_mismatch"
    REQUEST_IDENTITY_MISMATCH = "request_identity_mismatch"
    RESULT_STATUS_MISMATCH = "result_status_mismatch"
    SOURCE_IDENTITY_MISMATCH = "source_identity_mismatch"
    SOURCE_NOT_CANDIDATE_EVIDENCE = "source_not_candidate_evidence"
    TARGET_NOT_MAPPED = "target_not_mapped"
    TARGET_NOT_MATERIALIZED = "target_not_materialized"
    UNKNOWN_PORT = "unknown_port"
    VALUE_KIND_MISMATCH = "value_kind_mismatch"
    WRONG_TARGET_KIND = "wrong_target_kind"


class ImplementationEvidenceValidationError(ValueError):
    def __init__(
        self,
        code: ImplementationEvidenceErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")
