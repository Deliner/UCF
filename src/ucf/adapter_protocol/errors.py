from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    PROTOCOL_FAILURE = "protocol_failure"
    ADAPTER_FAILURE = "adapter_failure"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PROCESS_FAILURE = "process_failure"


class ProtocolCode(StrEnum):
    PARSE_ERROR = "parse_error"
    INVALID_MESSAGE = "invalid_message"
    INVALID_PARAMS = "invalid_params"
    METHOD_NOT_FOUND = "method_not_found"
    FRAME_TOO_LARGE = "frame_too_large"
    TRUNCATED_FRAME = "truncated_frame"
    INCOMPATIBLE_VERSION = "incompatible_version"
    INVALID_LIFECYCLE = "invalid_lifecycle"
    DUPLICATE_REQUEST_ID = "duplicate_request_id"
    TOO_MANY_PENDING = "too_many_pending"
    SESSION_REQUEST_LIMIT = "session_request_limit"
    DUPLICATE_CAPABILITY = "duplicate_capability"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    CAPABILITY_NOT_NEGOTIATED = "capability_not_negotiated"
    CORRELATION_FAILURE = "correlation_failure"
    REQUEST_CANCELLED = "request_cancelled"
    OPERATION_FAILED = "operation_failed"
    INTERNAL_ERROR = "internal_error"
    INITIALIZE_TIMEOUT = "initialize_timeout"
    OPERATION_TIMEOUT = "operation_timeout"
    WRITE_TIMEOUT = "write_timeout"
    CANCEL_TIMEOUT = "cancel_timeout"
    SHUTDOWN_TIMEOUT = "shutdown_timeout"
    START_FAILED = "start_failed"
    UNEXPECTED_EOF = "unexpected_eof"
    PROCESS_EXITED = "process_exited"
    IO_FAILURE = "io_failure"
    TERMINATION_FAILED = "termination_failed"
    INVALID_ADAPTER_OUTPUT = "invalid_adapter_output"


_ERROR_CATEGORIES_BY_CODE = {
    ProtocolCode.PARSE_ERROR: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.INVALID_MESSAGE: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.INVALID_PARAMS: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.METHOD_NOT_FOUND: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.FRAME_TOO_LARGE: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.TRUNCATED_FRAME: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.INCOMPATIBLE_VERSION: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.INVALID_LIFECYCLE: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.DUPLICATE_REQUEST_ID: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.TOO_MANY_PENDING: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.SESSION_REQUEST_LIMIT: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.DUPLICATE_CAPABILITY: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.UNSUPPORTED_CAPABILITY: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.CAPABILITY_NOT_NEGOTIATED: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.CORRELATION_FAILURE: ErrorCategory.PROTOCOL_FAILURE,
    ProtocolCode.REQUEST_CANCELLED: ErrorCategory.CANCELLED,
    ProtocolCode.OPERATION_FAILED: ErrorCategory.ADAPTER_FAILURE,
    ProtocolCode.INTERNAL_ERROR: ErrorCategory.ADAPTER_FAILURE,
    ProtocolCode.INITIALIZE_TIMEOUT: ErrorCategory.TIMEOUT,
    ProtocolCode.OPERATION_TIMEOUT: ErrorCategory.TIMEOUT,
    ProtocolCode.WRITE_TIMEOUT: ErrorCategory.TIMEOUT,
    ProtocolCode.CANCEL_TIMEOUT: ErrorCategory.TIMEOUT,
    ProtocolCode.SHUTDOWN_TIMEOUT: ErrorCategory.TIMEOUT,
    ProtocolCode.START_FAILED: ErrorCategory.PROCESS_FAILURE,
    ProtocolCode.UNEXPECTED_EOF: ErrorCategory.PROCESS_FAILURE,
    ProtocolCode.PROCESS_EXITED: ErrorCategory.PROCESS_FAILURE,
    ProtocolCode.IO_FAILURE: ErrorCategory.PROCESS_FAILURE,
    ProtocolCode.TERMINATION_FAILED: ErrorCategory.PROCESS_FAILURE,
    ProtocolCode.INVALID_ADAPTER_OUTPUT: ErrorCategory.PROCESS_FAILURE,
}


def error_category_for_code(code: ProtocolCode) -> ErrorCategory:
    """Return the only valid stable category for a symbolic error code."""

    return _ERROR_CATEGORIES_BY_CODE[code]


class AdapterProtocolError(RuntimeError):
    """Stable failure raised at the adapter protocol or process boundary."""

    def __init__(
        self,
        category: ErrorCategory,
        code: ProtocolCode,
        message: str,
        *,
        request_id: str | None = None,
    ) -> None:
        if category is not error_category_for_code(code):
            raise ValueError(
                "error category does not match the symbolic error code"
            )
        self.category = category
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"{category.value}/{code.value}: {message}")


def json_rpc_error_code(code: ProtocolCode) -> int:
    return {
        ProtocolCode.PARSE_ERROR: -32700,
        ProtocolCode.INVALID_MESSAGE: -32600,
        ProtocolCode.METHOD_NOT_FOUND: -32601,
        ProtocolCode.INVALID_PARAMS: -32602,
        ProtocolCode.INTERNAL_ERROR: -32603,
    }.get(code, -32000)
