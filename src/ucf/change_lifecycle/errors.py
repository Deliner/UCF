from __future__ import annotations

from enum import StrEnum


class ChangeLifecycleErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    CYCLIC_DEPENDENCY = "cyclic_dependency"
    DESTINATION_CONFLICT = "destination_conflict"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    DUPLICATE_JSON_MEMBER = "duplicate_json_member"
    EVIDENCE_CONTEXT_INVALID = "evidence_context_invalid"
    EVIDENCE_NOT_PASSED = "evidence_not_passed"
    INCOMPLETE_COVERAGE = "incomplete_coverage"
    INCOMPLETE_DELTA = "incomplete_delta"
    INCOMPLETE_TASKS = "incomplete_tasks"
    INVALID_JSON = "invalid_json"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_TRANSITION = "invalid_transition"
    NON_CANONICAL_ORDER = "non_canonical_order"
    PUBLISH_FAILED = "publish_failed"
    SOURCE_CHANGED = "source_changed"
    UNSAFE_FILESYSTEM = "unsafe_filesystem"
    UNSUPPORTED_EVIDENCE_PROFILE = "unsupported_evidence_profile"
    UNSUPPORTED_OPENSPEC_PROFILE = "unsupported_openspec_profile"
    WRONG_TARGET_KIND = "wrong_target_kind"


class ChangeLifecycleValidationError(ValueError):
    def __init__(
        self,
        code: ChangeLifecycleErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")
