from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from ucf.adapter_protocol.errors import (
    AdapterProtocolError,
    ErrorCategory,
    ProtocolCode,
    json_rpc_error_code,
)
from ucf.adapter_protocol.models import (
    MAX_FRAME_BYTES,
    CancelNotification,
    ClientMessage,
    ErrorResponse,
    Method,
    Request,
    ServerMessage,
    SuccessResponse,
)
from ucf.ir import IRErrorCode, IRValidationError, decode_strict_json_object

_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def encode_frame(message: Any) -> bytes:
    try:
        dumped = message.model_dump(mode="json")
        frame = (
            json.dumps(
                dumped,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (AttributeError, TypeError, ValueError) as error:
        raise TypeError("protocol messages must be validated models") from error
    if len(frame) > MAX_FRAME_BYTES:
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.FRAME_TOO_LARGE,
            f"encoded frame exceeds {MAX_FRAME_BYTES} bytes",
        )
    return frame


def _recover_request_id(decoded: dict[str, Any]) -> str | None:
    value = decoded.get("id")
    if isinstance(value, str) and _REQUEST_ID.fullmatch(value):
        return value
    return None


def _decode_frame_object(frame: bytes) -> dict[str, Any]:
    if not isinstance(frame, bytes):
        raise TypeError("protocol frame must be bytes")
    if len(frame) > MAX_FRAME_BYTES:
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.FRAME_TOO_LARGE,
            f"frame exceeds {MAX_FRAME_BYTES} bytes",
        )
    if not frame.endswith(b"\n"):
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.TRUNCATED_FRAME,
            "frame is not terminated by LF",
        )
    if b"\n" in frame[:-1]:
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.INVALID_MESSAGE,
            "frame contains an interior LF delimiter",
        )
    if frame == b"\n":
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.INVALID_MESSAGE,
            "empty protocol frame",
        )
    try:
        return decode_strict_json_object(frame[:-1])
    except IRValidationError as error:
        code = (
            ProtocolCode.INVALID_MESSAGE
            if error.code is IRErrorCode.INVALID_STRUCTURE
            and error.message == "document root must be an object"
            else ProtocolCode.PARSE_ERROR
        )
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            code,
            error.message,
        ) from error


def _validate_from_json(model: type[Any], decoded: dict[str, Any]) -> Any:
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)


def decode_request_frame(frame: bytes) -> ClientMessage:
    decoded = _decode_frame_object(frame)
    request_id = _recover_request_id(decoded)
    method_value = decoded.get("method")
    if not isinstance(method_value, str):
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.INVALID_MESSAGE,
            "request method must be a known string",
            request_id=request_id,
        )
    try:
        method = Method(method_value)
    except ValueError as error:
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.METHOD_NOT_FOUND,
            f"unknown method {method_value!r}",
            request_id=request_id,
        ) from error

    is_notification = "id" not in decoded
    expected_fields = (
        {"jsonrpc", "method", "params"}
        if is_notification
        else {"jsonrpc", "id", "method", "params"}
    )
    if set(decoded) != expected_fields:
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.INVALID_MESSAGE,
            "request envelope fields are not exact",
            request_id=request_id,
        )
    if decoded.get("jsonrpc") != "2.0" or not isinstance(
        decoded.get("params"), dict
    ):
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.INVALID_MESSAGE,
            "invalid JSON-RPC marker or params",
            request_id=request_id,
        )
    if is_notification:
        if method is not Method.CANCEL:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.INVALID_MESSAGE,
                "only ucf.cancel may be a notification",
            )
        model: type[Request] | type[CancelNotification] = CancelNotification
    else:
        if method is Method.CANCEL or request_id is None:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.INVALID_MESSAGE,
                "request id must be a bounded ASCII string",
                request_id=request_id,
            )
        model = Request
    try:
        return _validate_from_json(model, decoded)
    except ValidationError as error:
        raise AdapterProtocolError(
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.INVALID_PARAMS,
            error.errors(include_url=False)[0]["msg"],
            request_id=request_id,
        ) from error


def decode_response_frame(frame: bytes) -> ServerMessage:
    decoded = _decode_frame_object(frame)
    has_result = "result" in decoded
    has_error = "error" in decoded
    if has_result == has_error:
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            "response must contain exactly one of result or error",
        )
    expected_fields = (
        {"jsonrpc", "id", "result"}
        if has_result
        else {"jsonrpc", "id", "error"}
    )
    if set(decoded) != expected_fields or decoded.get("jsonrpc") != "2.0":
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            "response envelope fields are not exact",
        )
    request_id = _recover_request_id(decoded)
    if has_result and request_id is None:
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            "success response id must be a bounded ASCII string",
        )
    if not has_result and decoded.get("id") is not None and request_id is None:
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            "error response id must be null or a bounded ASCII string",
        )
    model: type[SuccessResponse] | type[ErrorResponse] = (
        SuccessResponse if has_result else ErrorResponse
    )
    try:
        response = _validate_from_json(model, decoded)
    except ValidationError as error:
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            error.errors(include_url=False)[0]["msg"],
            request_id=request_id,
        ) from error
    if isinstance(response, ErrorResponse) and response.error.code != (
        json_rpc_error_code(response.error.data.ucf_code)
    ):
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            "JSON-RPC error code does not match error.data.ucf_code",
            request_id=request_id,
        )
    return response
