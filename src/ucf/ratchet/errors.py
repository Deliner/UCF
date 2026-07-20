from __future__ import annotations

from enum import StrEnum


class RatchetErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    ILLEGAL_WEAKENING = "illegal_weakening"
    INCOMPLETE_COVERAGE = "incomplete_coverage"
    NON_CANONICAL_ORDER = "non_canonical_order"
    SUMMARY_MISMATCH = "summary_mismatch"
    WRONG_TARGET_KIND = "wrong_target_kind"


class RatchetValidationError(ValueError):
    def __init__(
        self,
        code: RatchetErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")
