from __future__ import annotations

from enum import StrEnum


class EvidenceStatusErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    CURRENT_CONTEXT_INCOMPLETE = "current_context_incomplete"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    INVALID_STRUCTURE = "invalid_structure"
    NON_CANONICAL_ORDER = "non_canonical_order"


class EvidenceStatusValidationError(ValueError):
    def __init__(
        self,
        code: EvidenceStatusErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")
