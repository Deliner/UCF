from __future__ import annotations

from enum import StrEnum


class RatchetErrorCode(StrEnum):
    AMBIGUOUS_COVERAGE_IDENTITY = "ambiguous_coverage_identity"
    BROKEN_REFERENCE = "broken_reference"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    ILLEGAL_WEAKENING = "illegal_weakening"
    INCOMPLETE_COMPARISON_DOMAIN = "incomplete_comparison_domain"
    INCOMPLETE_COVERAGE = "incomplete_coverage"
    INCOMPLETE_RULE_COVERAGE = "incomplete_rule_coverage"
    MIGRATION_SOURCE_MISMATCH = "migration_source_mismatch"
    NON_CANONICAL_ORDER = "non_canonical_order"
    NON_COMPARABLE_COVERAGE_DOMAIN = "non_comparable_coverage_domain"
    RATCHET_DOWNGRADE_FORBIDDEN = "ratchet_downgrade_forbidden"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    SUMMARY_MISMATCH = "summary_mismatch"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNSUPPORTED_EVIDENCE_KIND = "unsupported_evidence_kind"
    UNSUPPORTED_RATCHET_VERSION = "unsupported_ratchet_version"
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
