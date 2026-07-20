from __future__ import annotations

import asyncio
from pathlib import Path

from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    OperationKind,
    OperationParams,
    ProcessTimeouts,
    ProtocolCode,
    Request,
    encode_frame,
)
from ucf.generation.errors import GenerationClientError
from ucf.generation.models import GenerationRequest, GenerationResult
from ucf.generation.validation import (
    validate_generation_request,
    validate_generation_result,
)
from ucf.generation.wire import (
    generation_request_to_payload,
    generation_result_from_payload,
)


async def generate_with_adapter(
    *,
    command: tuple[str, ...],
    cwd: Path,
    request: GenerationRequest,
    timeouts: ProcessTimeouts | None = None,
    operation_timeout: float | None = None,
) -> GenerationResult:
    validate_generation_request(request)
    payload = generation_request_to_payload(request)
    _preflight_request(payload)
    adapter = AdapterProcess(
        command=command,
        cwd=cwd,
        requested_capabilities=(
            CapabilityRequest(
                kind="capability_request",
                name=request.capability.name,
                minimum_version=request.capability.version,
                required=True,
            ),
            CapabilityRequest(
                kind="capability_request",
                name=request.profile_capability.name,
                minimum_version=request.profile_capability.version,
                required=True,
            ),
        ),
        timeouts=timeouts,
        retain_stderr_tail=False,
    )
    result: GenerationResult | None = None
    operation_failure: tuple[ErrorCategory, ProtocolCode] | None = None
    cleanup_failure: tuple[ErrorCategory, ProtocolCode] | None = None
    cancelled = False
    try:
        initialized = await adapter.start()
        raw_result = await adapter.call(
            Method.GENERATE,
            payload,
            timeout=operation_timeout,
        )
        try:
            result = generation_result_from_payload(raw_result)
            validate_generation_result(
                result,
                request=request,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
        except (TypeError, ValueError):
            operation_failure = (
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.INVALID_ADAPTER_OUTPUT,
            )
    except AdapterProtocolError as error:
        operation_failure = (error.category, error.code)
    except asyncio.CancelledError:
        cancelled = True
    finally:
        try:
            await adapter.close()
        except AdapterProtocolError as error:
            cleanup_failure = (error.category, error.code)

    if cancelled:
        raise asyncio.CancelledError
    failure = cleanup_failure
    if failure is None and adapter.stderr_total_bytes:
        failure = (
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
        )
    if failure is None:
        failure = operation_failure
    if failure is not None:
        raise GenerationClientError(*failure)
    assert result is not None
    return result


def _preflight_request(payload) -> None:
    encode_frame(
        Request(
            jsonrpc="2.0",
            id="x" * 64,
            method=Method.GENERATE,
            params=OperationParams(
                kind=OperationKind.GENERATE_REQUEST,
                payload=payload,
            ),
        )
    )
