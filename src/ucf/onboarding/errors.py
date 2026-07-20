from __future__ import annotations

from enum import StrEnum


class OnboardingErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    INVALID_DECISION = "invalid_decision"
    INVALID_PROPOSAL = "invalid_proposal"
    ILLEGAL_PROMOTION = "illegal_promotion"
    NON_CANONICAL_ORDER = "non_canonical_order"
    STALE_DECISION = "stale_decision"
    SUMMARY_MISMATCH = "summary_mismatch"
    UNREACHABLE_ENTITY = "unreachable_entity"
    WRONG_TARGET_KIND = "wrong_target_kind"


class OnboardingValidationError(ValueError):
    def __init__(
        self,
        code: OnboardingErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")
