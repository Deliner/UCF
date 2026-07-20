from __future__ import annotations

from enum import StrEnum


class IRErrorCode(StrEnum):
    INVALID_JSON = "invalid_json"
    DUPLICATE_JSON_MEMBER = "duplicate_json_member"
    MALFORMED_VERSION = "malformed_version"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNKNOWN_FIELD = "unknown_field"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_VALUE = "invalid_value"
    DUPLICATE_IDENTITY = "duplicate_identity"
    DUPLICATE_PORT = "duplicate_port"
    DUPLICATE_REFERENCE = "duplicate_reference"
    DUPLICATE_CAPABILITY = "duplicate_capability"
    BROKEN_REFERENCE = "broken_reference"
    WRONG_TARGET_KIND = "wrong_target_kind"
    UNKNOWN_PORT = "unknown_port"
    INVALID_BINDING = "invalid_binding"
    MISSING_CAPABILITY_REQUIREMENT = "missing_capability_requirement"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    MAPPING_BASIS_MISMATCH = "mapping_basis_mismatch"
    MISSING_CLAIM_BASIS = "missing_claim_basis"
    CANDIDATE_IS_NOT_EVIDENCE = "candidate_is_not_evidence"
    CLAIM_BASIS_MISMATCH = "claim_basis_mismatch"
    EVIDENCE_NOT_PASSED = "evidence_not_passed"
    STALE_EVIDENCE = "stale_evidence"
    CIRCULAR_CLAIM_BASIS = "circular_claim_basis"
    VERIFIED_UNAVAILABLE = "verified_unavailable"


class IRValidationError(ValueError):
    def __init__(
        self,
        code: IRErrorCode,
        message: str,
        *,
        location: str = "$",
    ) -> None:
        self.code = code
        self.location = location
        self.message = message
        super().__init__(f"{code.value} at {location}: {message}")
