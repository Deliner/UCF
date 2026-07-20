from __future__ import annotations

from enum import StrEnum


class ChangeGovernanceErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DECISION_SET_MISMATCH = "decision_set_mismatch"
    DERIVED_CLASS_MISMATCH = "derived_class_mismatch"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    DUPLICATE_JSON_MEMBER = "duplicate_json_member"
    INCOMPLETE_ASSESSMENT = "incomplete_assessment"
    INVALID_JSON = "invalid_json"
    INVALID_STRUCTURE = "invalid_structure"
    NON_CANONICAL_ORDER = "non_canonical_order"
    PROCEDURE_MISMATCH = "procedure_mismatch"
    SUMMARY_MISMATCH = "summary_mismatch"
    UNRESOLVED_ASSESSMENT = "unresolved_assessment"


class ChangeGovernanceValidationError(ValueError):
    def __init__(
        self,
        code: ChangeGovernanceErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")
