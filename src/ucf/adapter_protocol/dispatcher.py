from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from ucf.adapter_protocol.errors import (
    ErrorCategory,
    ProtocolCode,
    json_rpc_error_code,
)
from ucf.adapter_protocol.models import (
    ADAPTER_PROTOCOL_VERSION,
    MAX_PENDING_REQUESTS,
    MAX_REQUESTS_PER_SESSION,
    AdapterPayload,
    CancelNotification,
    CapabilitySelection,
    ClientMessage,
    ErrorData,
    ErrorObject,
    ErrorResponse,
    InitializeParams,
    InitializeResult,
    Method,
    OperationKind,
    OperationParams,
    OperationResult,
    Payload,
    Request,
    ServerMessage,
    ShutdownResult,
    SuccessResponse,
)
from ucf.adapter_protocol.versioning import version_at_least
from ucf.ir.models import BehaviorIR, Producer
from ucf.ir.trust_models import TrustIR


class SessionState(StrEnum):
    NEW = "new"
    READY = "ready"
    CLOSED = "closed"


class AdapterRequestCancelled(Exception):
    """Cooperative terminal outcome requested through ucf.cancel."""


class CancellationSignal:
    """Read-only handler view of a dispatcher-owned cancellation event."""

    __slots__ = ("__event",)

    def __init__(self, event: asyncio.Event) -> None:
        self.__event = event

    def is_set(self) -> bool:
        return self.__event.is_set()

    async def wait(self) -> None:
        await self.__event.wait()


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    cancelled: CancellationSignal


@dataclass(frozen=True)
class _ActiveRequest:
    context: RequestContext
    cancelled: asyncio.Event


type AdapterHandler = Callable[
    [Method, Payload, RequestContext],
    Awaitable[Payload],
]

_METHOD_CAPABILITY = {
    Method.INVENTORY: "org.ucf.adapter.inventory",
    Method.DISCOVER: "org.ucf.adapter.discovery",
    Method.MAP: "org.ucf.adapter.mapping",
    Method.GENERATE: "org.ucf.adapter.generation",
    Method.VERIFY: "org.ucf.adapter.verification",
}
_METHOD_RESULT_KIND = {
    Method.INVENTORY: OperationKind.INVENTORY_RESULT,
    Method.DISCOVER: OperationKind.DISCOVER_RESULT,
    Method.MAP: OperationKind.MAP_RESULT,
    Method.GENERATE: OperationKind.GENERATE_RESULT,
    Method.VERIFY: OperationKind.VERIFY_RESULT,
}
_PAYLOAD_TYPES = (BehaviorIR, TrustIR, AdapterPayload)


def error_response(
    request_id: str | None,
    category: ErrorCategory,
    code: ProtocolCode,
    message: str,
) -> ErrorResponse:
    return ErrorResponse(
        jsonrpc="2.0",
        id=request_id,
        error=ErrorObject(
            code=json_rpc_error_code(code),
            message=message,
            data=ErrorData(category=category, ucf_code=code),
        ),
    )


class AdapterDispatcher:
    """Transport-independent adapter lifecycle and capability dispatcher."""

    def __init__(
        self,
        *,
        adapter: Producer,
        offered_capabilities: tuple[CapabilitySelection, ...],
        handler: AdapterHandler,
        max_pending: int = MAX_PENDING_REQUESTS,
        max_requests: int = MAX_REQUESTS_PER_SESSION,
    ) -> None:
        if (
            isinstance(max_pending, bool)
            or not isinstance(max_pending, int)
            or not 1 <= max_pending <= MAX_PENDING_REQUESTS
        ):
            raise ValueError(
                f"max_pending must be between 1 and {MAX_PENDING_REQUESTS}"
            )
        if (
            isinstance(max_requests, bool)
            or not isinstance(max_requests, int)
            or not 2 <= max_requests <= MAX_REQUESTS_PER_SESSION
        ):
            raise ValueError(
                "max_requests must be between 2 and "
                f"{MAX_REQUESTS_PER_SESSION}"
            )
        offered = {item.name: item.version for item in offered_capabilities}
        if len(offered) != len(offered_capabilities):
            raise ValueError("offered capabilities must have unique names")
        self._adapter = adapter
        self._offered = offered
        self._handler = handler
        self._max_pending = max_pending
        self._max_requests = max_requests
        self._state = SessionState.NEW
        self._negotiated: dict[str, str] = {}
        self._active: dict[str, _ActiveRequest] = {}
        self._seen_request_ids: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def negotiated_capabilities(self) -> dict[str, str]:
        return dict(self._negotiated)

    async def dispatch(self, message: ClientMessage) -> ServerMessage | None:
        if isinstance(message, CancelNotification):
            await self._cancel(message)
            return None
        async with self._lock:
            if message.id in self._seen_request_ids:
                return error_response(
                    message.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.DUPLICATE_REQUEST_ID,
                    "request id was already used in this session",
                )
            if len(self._seen_request_ids) >= self._max_requests or (
                len(self._seen_request_ids) == self._max_requests - 1
                and message.method is not Method.SHUTDOWN
            ):
                return error_response(
                    message.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.SESSION_REQUEST_LIMIT,
                    "adapter session request limit reached",
                )
            self._seen_request_ids.add(message.id)
        if message.method is Method.INITIALIZE:
            return await self._initialize(message)
        if message.method is Method.SHUTDOWN:
            return await self._shutdown(message)
        return await self._operate(message)

    async def _initialize(self, request: Request) -> ServerMessage:
        assert isinstance(request.params, InitializeParams)
        async with self._lock:
            if self._state is not SessionState.NEW:
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.INVALID_LIFECYCLE,
                    "initialize is legal only in the new state",
                )
            if request.params.protocol_version != ADAPTER_PROTOCOL_VERSION:
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.INCOMPATIBLE_VERSION,
                    "adapter protocol version is not supported",
                )
            names = [item.name for item in request.params.capabilities]
            if len(names) != len(set(names)):
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.DUPLICATE_CAPABILITY,
                    "requested capability names must be unique",
                )
            selected: list[CapabilitySelection] = []
            for requirement in request.params.capabilities:
                version = self._offered.get(requirement.name)
                supported = version is not None and version_at_least(
                    version, requirement.minimum_version
                )
                if not supported:
                    if requirement.required:
                        return error_response(
                            request.id,
                            ErrorCategory.PROTOCOL_FAILURE,
                            ProtocolCode.UNSUPPORTED_CAPABILITY,
                            "a required capability is unavailable",
                        )
                    continue
                selected.append(
                    CapabilitySelection(
                        kind="capability",
                        name=requirement.name,
                        version=version,
                    )
                )
            selected.sort(key=lambda item: item.name)
            self._negotiated = {
                item.name: item.version for item in selected
            }
            self._state = SessionState.READY
            return SuccessResponse(
                jsonrpc="2.0",
                id=request.id,
                result=InitializeResult(
                    kind="initialize_result",
                    protocol_version=ADAPTER_PROTOCOL_VERSION,
                    adapter=self._adapter,
                    capabilities=tuple(selected),
                ),
            )

    async def _operate(self, request: Request) -> ServerMessage:
        assert isinstance(request.params, OperationParams)
        async with self._lock:
            if self._state is not SessionState.READY:
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.INVALID_LIFECYCLE,
                    "operations are legal only in the ready state",
                )
            capability = _METHOD_CAPABILITY[request.method]
            if capability not in self._negotiated:
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.CAPABILITY_NOT_NEGOTIATED,
                    "operation capability was not negotiated",
                )
            if len(self._active) >= self._max_pending:
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.TOO_MANY_PENDING,
                    "pending request limit reached",
                )
            cancelled = asyncio.Event()
            context = RequestContext(
                request_id=request.id,
                cancelled=CancellationSignal(cancelled),
            )
            active = _ActiveRequest(
                context=context,
                cancelled=cancelled,
            )
            self._active[request.id] = active
        try:
            payload = await self._handler(
                request.method,
                request.params.payload,
                active.context,
            )
            if not isinstance(payload, _PAYLOAD_TYPES):
                return error_response(
                    request.id,
                    ErrorCategory.ADAPTER_FAILURE,
                    ProtocolCode.OPERATION_FAILED,
                    "adapter returned an invalid payload",
                )
            return SuccessResponse(
                jsonrpc="2.0",
                id=request.id,
                result=OperationResult(
                    kind=_METHOD_RESULT_KIND[request.method],
                    payload=payload,
                ),
            )
        except AdapterRequestCancelled:
            if not active.cancelled.is_set():
                return error_response(
                    request.id,
                    ErrorCategory.ADAPTER_FAILURE,
                    ProtocolCode.OPERATION_FAILED,
                    "adapter operation failed",
                )
            return error_response(
                request.id,
                ErrorCategory.CANCELLED,
                ProtocolCode.REQUEST_CANCELLED,
                "adapter request was cancelled",
            )
        except Exception:
            return error_response(
                request.id,
                ErrorCategory.ADAPTER_FAILURE,
                ProtocolCode.OPERATION_FAILED,
                "adapter operation failed",
            )
        finally:
            async with self._lock:
                self._active.pop(request.id, None)

    async def _cancel(self, notification: CancelNotification) -> None:
        async with self._lock:
            active = self._active.get(notification.params.request_id)
            if active is not None:
                active.cancelled.set()

    async def _shutdown(self, request: Request) -> ServerMessage:
        async with self._lock:
            if self._state is not SessionState.READY or self._active:
                return error_response(
                    request.id,
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.INVALID_LIFECYCLE,
                    "shutdown requires ready state with no pending requests",
                )
            self._state = SessionState.CLOSED
            return SuccessResponse(
                jsonrpc="2.0",
                id=request.id,
                result=ShutdownResult(kind="shutdown_result"),
            )
