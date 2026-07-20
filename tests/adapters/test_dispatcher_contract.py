from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from ucf.adapter_protocol import (
    ADAPTER_PROTOCOL_VERSION,
    MAX_PENDING_REQUESTS,
    AdapterDispatcher,
    AdapterPayload,
    AdapterRequestCancelled,
    CancelNotification,
    CancelParams,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    ErrorResponse,
    InitializeParams,
    InitializeResult,
    Method,
    OperationKind,
    OperationParams,
    OperationResult,
    ProtocolCode,
    Request,
    RequestContext,
    SessionState,
    ShutdownParams,
    ShutdownResult,
    SuccessResponse,
)
from ucf.ir.models import NullValue, Producer, StringValue

INVENTORY = "org.ucf.adapter.inventory"
DISCOVERY = "org.ucf.adapter.discovery"
MAPPING = "org.ucf.adapter.mapping"
GENERATION = "org.ucf.adapter.generation"
VERIFICATION = "org.ucf.adapter.verification"
ALL_CAPABILITIES = (
    INVENTORY,
    DISCOVERY,
    MAPPING,
    GENERATION,
    VERIFICATION,
)


def _producer(name: str) -> Producer:
    return Producer(kind="producer", name=name, version="1.0.0")


def _capability_request(
    name: str,
    *,
    minimum_version: str = "1.0.0",
    required: bool = True,
) -> CapabilityRequest:
    return CapabilityRequest(
        kind="capability_request",
        name=name,
        minimum_version=minimum_version,
        required=required,
    )


def _offered(*names: str, version: str = "1.0.0"):
    return tuple(
        CapabilitySelection(kind="capability", name=name, version=version)
        for name in names
    )


def _initialize(
    capabilities: tuple[CapabilityRequest, ...],
    *,
    version: str = ADAPTER_PROTOCOL_VERSION,
    request_id: str = "initialize-1",
) -> Request:
    return Request(
        jsonrpc="2.0",
        id=request_id,
        method=Method.INITIALIZE,
        params=InitializeParams(
            kind="initialize_request",
            protocol_version=version,
            client=_producer("org.ucf.core"),
            capabilities=capabilities,
        ),
    )


def _operation(method: Method, request_id: str) -> Request:
    request_kind = {
        Method.INVENTORY: OperationKind.INVENTORY_REQUEST,
        Method.DISCOVER: OperationKind.DISCOVER_REQUEST,
        Method.MAP: OperationKind.MAP_REQUEST,
        Method.GENERATE: OperationKind.GENERATE_REQUEST,
        Method.VERIFY: OperationKind.VERIFY_REQUEST,
    }[method]
    return Request(
        jsonrpc="2.0",
        id=request_id,
        method=method,
        params=OperationParams(
            kind=request_kind,
            payload=AdapterPayload(
                kind="adapter_payload",
                schema_uri="urn:ucf:adapter:reference",
                schema_version="1.0.0",
                value=NullValue(kind="null"),
            ),
        ),
    )


def _shutdown(request_id: str = "shutdown-1") -> Request:
    return Request(
        jsonrpc="2.0",
        id=request_id,
        method=Method.SHUTDOWN,
        params=ShutdownParams(kind="shutdown_request"),
    )


def _cancel(request_id: str) -> CancelNotification:
    return CancelNotification(
        jsonrpc="2.0",
        method=Method.CANCEL,
        params=CancelParams(kind="cancel_request", request_id=request_id),
    )


def _dispatcher(
    handler: Callable[
        [Method, AdapterPayload, RequestContext],
        Awaitable[AdapterPayload],
    ],
    *,
    offered: tuple[CapabilitySelection, ...] | None = None,
    max_pending: int = MAX_PENDING_REQUESTS,
    max_requests: int | None = None,
) -> AdapterDispatcher:
    kwargs = {}
    if max_requests is not None:
        kwargs["max_requests"] = max_requests
    return AdapterDispatcher(
        adapter=_producer("org.ucf.reference-adapter"),
        offered_capabilities=offered or _offered(*ALL_CAPABILITIES),
        handler=handler,
        max_pending=max_pending,
        **kwargs,
    )


async def _echo_handler(
    method: Method,
    payload: AdapterPayload,
    context: RequestContext,
) -> AdapterPayload:
    return payload


def _error_code(response: ErrorResponse) -> ProtocolCode:
    return response.error.data.ucf_code


def test_initialize_selects_only_requested_compatible_capabilities():
    async def scenario():
        dispatcher = _dispatcher(
            _echo_handler,
            offered=_offered(INVENTORY, DISCOVERY, version="1.2.0"),
        )
        response = await dispatcher.dispatch(
            _initialize(
                (
                    _capability_request(INVENTORY, minimum_version="1.1.0"),
                    _capability_request(
                        GENERATION,
                        required=False,
                    ),
                )
            )
        )

        assert isinstance(response, SuccessResponse)
        assert isinstance(response.result, InitializeResult)
        assert response.id == "initialize-1"
        assert [
            (item.name, item.version) for item in response.result.capabilities
        ] == [(INVENTORY, "1.2.0")]
        assert dispatcher.state is SessionState.READY
        assert dispatcher.negotiated_capabilities == {INVENTORY: "1.2.0"}

    asyncio.run(scenario())


def test_capability_negotiation_compares_unbounded_decimal_versions_without_int():
    async def scenario():
        very_large_major = "9" * 5_000
        dispatcher = _dispatcher(
            _echo_handler,
            offered=_offered(
                INVENTORY,
                version=f"{very_large_major}.0.0",
            ),
        )

        response = await dispatcher.dispatch(
            _initialize(
                (
                    _capability_request(
                        INVENTORY,
                        minimum_version="1.0.0",
                    ),
                )
            )
        )

        assert isinstance(response, SuccessResponse)
        assert response.result.capabilities[0].version == (
            f"{very_large_major}.0.0"
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("message", "code"),
    [
        (
            _initialize(
                (_capability_request(INVENTORY),),
                version="1.0.1",
            ),
            ProtocolCode.INCOMPATIBLE_VERSION,
        ),
        (
            _initialize(
                (
                    _capability_request(INVENTORY),
                    _capability_request(INVENTORY),
                )
            ),
            ProtocolCode.DUPLICATE_CAPABILITY,
        ),
        (
            _initialize((_capability_request("org.example.missing"),)),
            ProtocolCode.UNSUPPORTED_CAPABILITY,
        ),
        (
            _initialize(
                (
                    _capability_request(
                        INVENTORY,
                        minimum_version="2.0.0",
                    ),
                )
            ),
            ProtocolCode.UNSUPPORTED_CAPABILITY,
        ),
    ],
)
def test_failed_negotiation_is_explicit_and_does_not_partially_initialize(
    message: Request,
    code: ProtocolCode,
):
    async def scenario():
        dispatcher = _dispatcher(
            _echo_handler,
            offered=_offered(INVENTORY, version="1.2.0"),
        )

        response = await dispatcher.dispatch(message)

        assert isinstance(response, ErrorResponse)
        assert response.error.data.category is ErrorCategory.PROTOCOL_FAILURE
        assert _error_code(response) is code
        assert dispatcher.state is SessionState.NEW
        assert dispatcher.negotiated_capabilities == {}

    asyncio.run(scenario())


def test_every_operation_family_runs_only_through_its_negotiated_capability():
    async def scenario():
        calls: list[Method] = []

        async def recording_handler(method, payload, context):
            calls.append(method)
            return payload

        dispatcher = _dispatcher(recording_handler)
        initialized = await dispatcher.dispatch(
            _initialize(tuple(_capability_request(name) for name in ALL_CAPABILITIES))
        )
        assert isinstance(initialized, SuccessResponse)

        for index, method in enumerate(
            (
                Method.INVENTORY,
                Method.DISCOVER,
                Method.MAP,
                Method.GENERATE,
                Method.VERIFY,
            ),
            start=1,
        ):
            response = await dispatcher.dispatch(
                _operation(method, f"operation-{index}")
            )
            assert isinstance(response, SuccessResponse)
            assert isinstance(response.result, OperationResult)
            assert response.result.kind.value == (
                f"{method.value.removeprefix('ucf.')}_result"
            )

        assert calls == [
            Method.INVENTORY,
            Method.DISCOVER,
            Method.MAP,
            Method.GENERATE,
            Method.VERIFY,
        ]

    asyncio.run(scenario())


def test_unnegotiated_operation_fails_before_handler_semantics():
    async def scenario():
        called = False

        async def forbidden_handler(method, payload, context):
            nonlocal called
            called = True
            return payload

        dispatcher = _dispatcher(forbidden_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )

        response = await dispatcher.dispatch(
            _operation(Method.VERIFY, "verify-1")
        )

        assert isinstance(response, ErrorResponse)
        assert _error_code(response) is ProtocolCode.CAPABILITY_NOT_NEGOTIATED
        assert called is False

    asyncio.run(scenario())


def test_lifecycle_rejects_operations_before_initialize_and_initialize_twice():
    async def scenario():
        dispatcher = _dispatcher(_echo_handler)

        premature = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "inventory-before-init")
        )
        assert isinstance(premature, ErrorResponse)
        assert _error_code(premature) is ProtocolCode.INVALID_LIFECYCLE

        first = await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )
        assert isinstance(first, SuccessResponse)
        duplicate = await dispatcher.dispatch(
            _initialize(
                (_capability_request(INVENTORY),),
                request_id="initialize-2",
            )
        )
        assert isinstance(duplicate, ErrorResponse)
        assert _error_code(duplicate) is ProtocolCode.INVALID_LIFECYCLE

    asyncio.run(scenario())


def test_two_requests_can_finish_out_of_order_without_losing_correlation():
    async def scenario():
        gates = {
            "first": asyncio.Event(),
            "second": asyncio.Event(),
        }

        async def ordered_handler(method, payload, context):
            await gates[context.request_id].wait()
            return AdapterPayload(
                kind="adapter_payload",
                schema_uri="urn:ucf:adapter:reference",
                schema_version="1.0.0",
                value=StringValue(kind="string", value=context.request_id),
            )

        dispatcher = _dispatcher(ordered_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )
        first = asyncio.create_task(
            dispatcher.dispatch(_operation(Method.INVENTORY, "first"))
        )
        second = asyncio.create_task(
            dispatcher.dispatch(_operation(Method.INVENTORY, "second"))
        )
        await asyncio.sleep(0)

        gates["second"].set()
        second_response = await second
        assert isinstance(second_response, SuccessResponse)
        assert second_response.id == "second"
        gates["first"].set()
        first_response = await first
        assert isinstance(first_response, SuccessResponse)
        assert first_response.id == "first"

    asyncio.run(scenario())


def test_cancel_targets_only_the_exact_active_request_and_has_no_response():
    async def scenario():
        started = asyncio.Event()

        async def cancellable_handler(method, payload, context):
            started.set()
            await context.cancelled.wait()
            raise AdapterRequestCancelled

        dispatcher = _dispatcher(cancellable_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )
        blocked = asyncio.create_task(
            dispatcher.dispatch(_operation(Method.INVENTORY, "blocked"))
        )
        await started.wait()

        assert await dispatcher.dispatch(_cancel("unknown")) is None
        assert blocked.done() is False
        assert await dispatcher.dispatch(_cancel("blocked")) is None
        response = await asyncio.wait_for(blocked, timeout=1)

        assert isinstance(response, ErrorResponse)
        assert response.id == "blocked"
        assert response.error.data.category is ErrorCategory.CANCELLED
        assert _error_code(response) is ProtocolCode.REQUEST_CANCELLED

    asyncio.run(scenario())


def test_duplicate_active_id_and_pending_bound_are_rejected():
    async def scenario():
        release = asyncio.Event()

        async def blocked_handler(method, payload, context):
            await release.wait()
            return payload

        dispatcher = _dispatcher(blocked_handler, max_pending=2)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )
        first = asyncio.create_task(
            dispatcher.dispatch(_operation(Method.INVENTORY, "first"))
        )
        second = asyncio.create_task(
            dispatcher.dispatch(_operation(Method.INVENTORY, "second"))
        )
        await asyncio.sleep(0)

        duplicate = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "first")
        )
        overflow = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "third")
        )
        assert isinstance(duplicate, ErrorResponse)
        assert _error_code(duplicate) is ProtocolCode.DUPLICATE_REQUEST_ID
        assert isinstance(overflow, ErrorResponse)
        assert _error_code(overflow) is ProtocolCode.TOO_MANY_PENDING

        release.set()
        await asyncio.gather(first, second)

    asyncio.run(scenario())


def test_request_ids_cannot_be_reused_after_their_response_completed():
    async def scenario():
        dispatcher = _dispatcher(_echo_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )

        completed = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "completed")
        )
        reused = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "completed")
        )
        reused_initialize_id = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "initialize-1")
        )

        assert isinstance(completed, SuccessResponse)
        assert isinstance(reused, ErrorResponse)
        assert _error_code(reused) is ProtocolCode.DUPLICATE_REQUEST_ID
        assert isinstance(reused_initialize_id, ErrorResponse)
        assert (
            _error_code(reused_initialize_id)
            is ProtocolCode.DUPLICATE_REQUEST_ID
        )

    asyncio.run(scenario())


def test_session_request_limit_bounds_lifetime_id_retention_and_reserves_shutdown():
    async def scenario():
        calls = 0

        async def counting_handler(method, payload, context):
            nonlocal calls
            calls += 1
            return payload

        dispatcher = _dispatcher(
            counting_handler,
            max_requests=3,
        )
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )
        accepted = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "accepted")
        )
        first_rejected = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "over-limit-1")
        )
        second_rejected = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "over-limit-2")
        )
        duplicate = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "accepted")
        )
        shutdown = await dispatcher.dispatch(_shutdown())

        assert isinstance(accepted, SuccessResponse)
        assert isinstance(first_rejected, ErrorResponse)
        assert first_rejected.error.data.ucf_code.value == (
            "session_request_limit"
        )
        assert isinstance(second_rejected, ErrorResponse)
        assert second_rejected.error.data.ucf_code.value == (
            "session_request_limit"
        )
        assert isinstance(duplicate, ErrorResponse)
        assert _error_code(duplicate) is ProtocolCode.DUPLICATE_REQUEST_ID
        assert isinstance(shutdown, SuccessResponse)
        assert calls == 1

    asyncio.run(scenario())


def test_handler_cannot_claim_cancellation_without_a_matching_notification():
    async def scenario():
        async def falsely_cancelled_handler(method, payload, context):
            raise AdapterRequestCancelled

        dispatcher = _dispatcher(falsely_cancelled_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )

        response = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "not-cancelled")
        )

        assert isinstance(response, ErrorResponse)
        assert response.error.data.category is ErrorCategory.ADAPTER_FAILURE
        assert _error_code(response) is ProtocolCode.OPERATION_FAILED

    asyncio.run(scenario())


def test_handler_cannot_mutate_the_client_owned_cancellation_signal():
    async def scenario():
        async def falsely_cancelled_handler(method, payload, context):
            context.cancelled.set()
            raise AdapterRequestCancelled

        dispatcher = _dispatcher(falsely_cancelled_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )

        response = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "self-cancelled")
        )

        assert isinstance(response, ErrorResponse)
        assert response.error.data.category is ErrorCategory.ADAPTER_FAILURE
        assert _error_code(response) is ProtocolCode.OPERATION_FAILED

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("max_pending", "max_requests"),
    [(True, 3), (1.5, 3), (1, True), (1, 2.5)],
)
def test_dispatcher_resource_bounds_require_exact_integers(
    max_pending,
    max_requests,
):
    with pytest.raises(ValueError):
        _dispatcher(
            _echo_handler,
            max_pending=max_pending,
            max_requests=max_requests,
        )


def test_shutdown_acknowledges_only_after_pending_requests_are_empty():
    async def scenario():
        release = asyncio.Event()

        async def blocked_handler(method, payload, context):
            await release.wait()
            return payload

        dispatcher = _dispatcher(blocked_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )
        pending = asyncio.create_task(
            dispatcher.dispatch(_operation(Method.INVENTORY, "pending"))
        )
        await asyncio.sleep(0)

        rejected = await dispatcher.dispatch(_shutdown("too-early"))
        assert isinstance(rejected, ErrorResponse)
        assert _error_code(rejected) is ProtocolCode.INVALID_LIFECYCLE

        release.set()
        await pending
        accepted = await dispatcher.dispatch(_shutdown())
        assert isinstance(accepted, SuccessResponse)
        assert isinstance(accepted.result, ShutdownResult)
        assert dispatcher.state is SessionState.CLOSED

        after = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "after-shutdown")
        )
        assert isinstance(after, ErrorResponse)
        assert _error_code(after) is ProtocolCode.INVALID_LIFECYCLE

    asyncio.run(scenario())


def test_handler_exception_is_a_generic_adapter_failure_without_traceback():
    async def scenario():
        async def failing_handler(method, payload, context):
            raise RuntimeError("secret implementation detail")

        dispatcher = _dispatcher(failing_handler)
        await dispatcher.dispatch(
            _initialize((_capability_request(INVENTORY),))
        )

        response = await dispatcher.dispatch(
            _operation(Method.INVENTORY, "failure")
        )

        assert isinstance(response, ErrorResponse)
        assert response.error.data.category is ErrorCategory.ADAPTER_FAILURE
        assert _error_code(response) is ProtocolCode.OPERATION_FAILED
        assert "secret" not in response.error.message

    asyncio.run(scenario())
