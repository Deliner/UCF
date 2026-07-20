from __future__ import annotations

from enum import StrEnum

from ucf.adapter_protocol import ErrorCategory, ProtocolCode


class RuntimeEvidenceErrorCode(StrEnum):
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    ENVIRONMENT_IDENTITY_MISMATCH = "environment_identity_mismatch"
    BROKEN_REFERENCE = "broken_reference"
    WRONG_TARGET_KIND = "wrong_target_kind"
    ASSERTION_MISMATCH = "assertion_mismatch"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    NON_CANONICAL_ORDER = "non_canonical_order"
    SUMMARY_MISMATCH = "summary_mismatch"
    REQUEST_IDENTITY_MISMATCH = "request_identity_mismatch"
    PRODUCER_IDENTITY_MISMATCH = "producer_identity_mismatch"
    CAPABILITY_MISMATCH = "capability_mismatch"
    SOURCE_IDENTITY_MISMATCH = "source_identity_mismatch"
    RESULT_STATUS_MISMATCH = "result_status_mismatch"


class RuntimeEvidenceValidationError(ValueError):
    def __init__(
        self,
        code: RuntimeEvidenceErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{location}: {code.value}: {message}")


class RuntimeEvidenceClientError(RuntimeError):
    def __init__(
        self,
        category: ErrorCategory,
        code: ProtocolCode,
    ) -> None:
        self.category = category
        self.code = code
        super().__init__(f"{category.value}/{code.value}")
