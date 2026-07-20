from __future__ import annotations

from enum import StrEnum

from ucf.adapter_protocol import ErrorCategory, ProtocolCode


class GenerationErrorCode(StrEnum):
    BROKEN_REFERENCE = "broken_reference"
    CAPABILITY_MISMATCH = "capability_mismatch"
    CONTENT_IDENTITY_MISMATCH = "content_identity_mismatch"
    DOCUMENT_IDENTITY_MISMATCH = "document_identity_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"
    FRAME_BUDGET_EXCEEDED = "frame_budget_exceeded"
    INCOMPLETE_PORT_VALUES = "incomplete_port_values"
    INVALID_STRUCTURE = "invalid_structure"
    NON_CANONICAL_ORDER = "non_canonical_order"
    PROCEDURE_MISMATCH = "procedure_mismatch"
    PRODUCER_IDENTITY_MISMATCH = "producer_identity_mismatch"
    REQUEST_IDENTITY_MISMATCH = "request_identity_mismatch"
    VALUE_KIND_MISMATCH = "value_kind_mismatch"
    WRONG_TARGET_KIND = "wrong_target_kind"


class GenerationValidationError(ValueError):
    def __init__(
        self,
        code: GenerationErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")


class GenerationPublicationErrorCode(StrEnum):
    COMMITTED_CLEANUP_FAILED = "committed_cleanup_failed"
    COMMITTED_DURABILITY_UNKNOWN = "committed_durability_unknown"
    DESTINATION_CONFLICT = "destination_conflict"
    INVALID_PRIOR_TREE = "invalid_prior_tree"
    PUBLISH_FAILED = "publish_failed"
    UNSAFE_FILESYSTEM = "unsafe_filesystem"
    UNSUPPORTED_PLATFORM = "unsupported_platform"


class GenerationPublicationError(ValueError):
    def __init__(
        self,
        code: GenerationPublicationErrorCode,
        message: str,
        *,
        location: str,
    ) -> None:
        self.code = code
        self.location = location
        super().__init__(f"{code.value} at {location}: {message}")


class GenerationClientError(RuntimeError):
    def __init__(
        self,
        category: ErrorCategory,
        code: ProtocolCode,
    ) -> None:
        self.category = category
        self.code = code
        super().__init__(f"{category.value}/{code.value}")
