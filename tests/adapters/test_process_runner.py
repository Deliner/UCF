from __future__ import annotations

import asyncio
import math
import os
import sys
from pathlib import Path

import pytest

from ucf.adapter_protocol import (
    MAX_RETAINED_STDERR_BYTES,
    AdapterPayload,
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    ProcessState,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.ir.models import BooleanValue, NullValue, StringValue

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ADAPTER = ROOT / "tests" / "fixtures" / "adapters" / "reference_adapter.py"
FAULT_ADAPTER = ROOT / "tests" / "fixtures" / "adapters" / "fault_adapter.py"
CAPABILITIES = {
    Method.INVENTORY: "org.ucf.adapter.inventory",
    Method.DISCOVER: "org.ucf.adapter.discovery",
    Method.MAP: "org.ucf.adapter.mapping",
    Method.GENERATE: "org.ucf.adapter.generation",
    Method.VERIFY: "org.ucf.adapter.verification",
}
FAST_TIMEOUTS = ProcessTimeouts(
    initialize=1.0,
    operation=1.0,
    write=1.0,
    cancellation=0.2,
    shutdown=0.5,
    terminate=0.2,
    kill=0.5,
)


@pytest.mark.parametrize("invalid", [0.0, -1.0, math.inf, -math.inf, math.nan])
def test_process_timeouts_must_be_finite_positive_numbers(invalid: float):
    with pytest.raises(ValueError):
        ProcessTimeouts(operation=invalid)


def test_invalid_environment_name_is_rejected_before_process_start():
    with pytest.raises(ValueError):
        AdapterProcess(
            command=(sys.executable, "-c", "raise SystemExit(0)"),
            cwd=ROOT,
            requested_capabilities=(),
            environment={"INVALID=NAME": "value"},
        )


def _capability(
    name: str,
    *,
    required: bool = True,
) -> CapabilityRequest:
    return CapabilityRequest(
        kind="capability_request",
        name=name,
        minimum_version="1.0.0",
        required=required,
    )


def _payload(
    suffix: str = "echo",
    *,
    value=None,
) -> AdapterPayload:
    return AdapterPayload(
        kind="adapter_payload",
        schema_uri=f"urn:ucf:adapter:reference:{suffix}",
        schema_version="1.0.0",
        value=value or NullValue(kind="null"),
    )


def _process(
    *capabilities: str,
    command: tuple[str, ...] | None = None,
    timeouts: ProcessTimeouts = FAST_TIMEOUTS,
    environment: dict[str, str] | None = None,
    retain_stderr_tail: bool = True,
) -> AdapterProcess:
    return AdapterProcess(
        command=command
        or (
            sys.executable,
            str(REFERENCE_ADAPTER),
        ),
        cwd=ROOT,
        requested_capabilities=tuple(
            _capability(name) for name in capabilities
        ),
        timeouts=timeouts,
        environment=environment,
        retain_stderr_tail=retain_stderr_tail,
    )


def test_reference_adapter_crosses_a_real_process_for_every_operation_family():
    async def scenario():
        adapter = _process(*CAPABILITIES.values())
        initialized = await adapter.start()

        assert adapter.pid != os.getpid()
        assert initialized.adapter.name == "org.ucf.reference-adapter"
        assert adapter.state is ProcessState.READY
        assert adapter.negotiated_capabilities == {
            name: "1.0.0" for name in sorted(CAPABILITIES.values())
        }

        for method in CAPABILITIES:
            sent = _payload(
                value=StringValue(kind="string", value=method.value)
            )
            received = await adapter.call(method, sent)
            assert received == sent

        child_pid = adapter.pid
        await adapter.close()

        assert adapter.state is ProcessState.CLOSED
        assert adapter.returncode == 0
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)

    asyncio.run(scenario())


def test_cancelling_start_reaps_the_child_and_leaves_close_idempotent():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "block-before-initialize-response",
            ),
        )
        start = asyncio.create_task(adapter.start())
        for _ in range(100):
            if adapter.state is ProcessState.STARTING:
                try:
                    child_pid = adapter.pid
                except RuntimeError:
                    pass
                else:
                    break
            await asyncio.sleep(0.005)
        else:
            pytest.fail("adapter child did not enter starting state")

        start.cancel()
        with pytest.raises(asyncio.CancelledError):
            await start

        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        await adapter.close()

    asyncio.run(scenario())


def test_cancelling_close_fails_pending_and_reaps_before_reraising():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "ignore-cancel-and-term",
            ),
        )
        await adapter.start()
        blocked = await adapter.begin(Method.INVENTORY, _payload())
        child_pid = adapter.pid
        close = asyncio.create_task(adapter.close())
        for _ in range(100):
            if adapter.state is ProcessState.STOPPING:
                break
            await asyncio.sleep(0.005)
        else:
            pytest.fail("adapter did not enter stopping state")

        close.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close

        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        with pytest.raises(AdapterProtocolError) as pending_error:
            await blocked.result()
        assert pending_error.value.code is ProtocolCode.PROCESS_EXITED
        await adapter.close()

    asyncio.run(scenario())


def test_cancelling_one_shot_call_does_not_abandon_its_pending_request():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "ignore-cancel-and-term",
            ),
        )
        await adapter.start()
        child_pid = adapter.pid
        operation = asyncio.create_task(
            adapter.call(Method.INVENTORY, _payload())
        )
        await asyncio.sleep(0.02)

        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation

        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        await adapter.close()

    asyncio.run(scenario())


def test_one_shot_call_validates_timeout_before_sending_a_request():
    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()

        with pytest.raises(ValueError):
            await adapter.call(
                Method.INVENTORY,
                _payload(),
                timeout=math.nan,
            )

        assert await adapter.call(Method.INVENTORY, _payload()) == _payload()
        await adapter.close()

    asyncio.run(scenario())


def test_unnegotiated_operation_fails_locally_before_adapter_semantics():
    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.call(Method.VERIFY, _payload())

        assert captured.value.category is ErrorCategory.PROTOCOL_FAILURE
        assert (
            captured.value.code is ProtocolCode.CAPABILITY_NOT_NEGOTIATED
        )
        await adapter.close()

    asyncio.run(scenario())


def test_missing_required_capability_fails_initialization_and_reaps_child():
    async def scenario():
        adapter = _process("org.example.unsupported")

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.start()

        assert captured.value.code is ProtocolCode.UNSUPPORTED_CAPABILITY
        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None

    asyncio.run(scenario())


def test_cancel_reaches_only_the_original_in_flight_request():
    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()
        blocked = await adapter.begin(
            Method.INVENTORY,
            _payload("block"),
        )
        echo = await adapter.call(Method.INVENTORY, _payload())
        assert echo == _payload()

        with pytest.raises(AdapterProtocolError) as captured:
            await blocked.cancel()

        assert captured.value.category is ErrorCategory.CANCELLED
        assert captured.value.code is ProtocolCode.REQUEST_CANCELLED
        assert captured.value.request_id == blocked.request_id

        later = await adapter.call(Method.INVENTORY, _payload())
        assert later == _payload()
        await adapter.close()

    asyncio.run(scenario())


def test_reader_correlates_out_of_order_responses():
    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()
        slow = await adapter.begin(
            Method.INVENTORY,
            _payload(
                "delay",
                value=StringValue(kind="string", value="0.05"),
            ),
        )
        fast = await adapter.begin(Method.INVENTORY, _payload())

        assert await fast.result() == _payload()
        assert await slow.result() == _payload(
            "delay",
            value=StringValue(kind="string", value="0.05"),
        )
        await adapter.close()

    asyncio.run(scenario())


def test_stderr_is_drained_concurrently_bounded_and_never_becomes_a_result():
    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()

        response = await adapter.call(
            Method.INVENTORY,
            _payload("stderr-flood"),
        )

        assert response == _payload("stderr-flood")
        await adapter.close()
        assert adapter.stderr_total_bytes >= 1_048_576
        assert len(adapter.stderr_tail) == MAX_RETAINED_STDERR_BYTES

    asyncio.run(scenario())


def test_stderr_tail_retention_can_be_disabled_without_stopping_drain():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            retain_stderr_tail=False,
        )
        await adapter.start()

        response = await adapter.call(
            Method.INVENTORY,
            _payload("stderr-flood"),
        )

        assert response == _payload("stderr-flood")
        await adapter.close()
        assert adapter.stderr_total_bytes >= 1_048_576
        assert adapter.stderr_tail == b""

    asyncio.run(scenario())


@pytest.mark.parametrize("invalid", [0, 1, "false", None])
def test_stderr_tail_retention_flag_requires_bool(invalid):
    with pytest.raises(ValueError):
        AdapterProcess(
            command=(sys.executable, "-c", "raise SystemExit(0)"),
            cwd=ROOT,
            requested_capabilities=(),
            retain_stderr_tail=invalid,
        )


def test_child_receives_explicit_cwd_but_not_ambient_secret(monkeypatch):
    monkeypatch.setenv("UCF_ADAPTER_SENTINEL_SECRET", "must-not-cross")

    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()

        response = await adapter.call(
            Method.INVENTORY,
            _payload("environment"),
        )

        assert isinstance(response.value, BooleanValue)
        assert response.value.value is False
        cwd_response = await adapter.call(
            Method.INVENTORY,
            _payload("cwd"),
        )
        assert isinstance(cwd_response.value, StringValue)
        assert cwd_response.value.value == str(ROOT)
        await adapter.close()

    asyncio.run(scenario())


def test_child_receives_no_implicit_language_runtime_environment():
    async def scenario():
        adapter = _process(CAPABILITIES[Method.INVENTORY])
        await adapter.start()
        try:
            response = await adapter.call(
                Method.INVENTORY,
                _payload("python-runtime-environment"),
            )

            assert isinstance(response.value, BooleanValue)
            assert response.value.value is False
        finally:
            await adapter.close()

    asyncio.run(scenario())


def test_child_receives_explicit_language_runtime_environment():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            environment={"PYTHONUTF8": "1"},
        )
        await adapter.start()
        try:
            response = await adapter.call(
                Method.INVENTORY,
                _payload("python-runtime-environment"),
            )

            assert isinstance(response.value, BooleanValue)
            assert response.value.value is True
        finally:
            await adapter.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("stdout-noise", ProtocolCode.INVALID_ADAPTER_OUTPUT),
        ("partial-eof", ProtocolCode.TRUNCATED_FRAME),
        ("exit-nonzero", ProtocolCode.PROCESS_EXITED),
        ("unknown-response-id", ProtocolCode.CORRELATION_FAILURE),
        ("duplicate-init-response", ProtocolCode.CORRELATION_FAILURE),
        ("forged-process-error", ProtocolCode.INVALID_ADAPTER_OUTPUT),
        ("unrequested-capability", ProtocolCode.INVALID_ADAPTER_OUTPUT),
    ],
)
def test_faulty_process_output_fails_all_waiters_and_is_reaped(
    mode: str,
    expected: ProtocolCode,
):
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(sys.executable, str(FAULT_ADAPTER), mode),
        )

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.start()

        assert captured.value.code is expected
        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None

    asyncio.run(scenario())


def test_result_kind_must_match_the_exact_originating_method():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "wrong-operation-result",
            ),
        )
        await adapter.start()

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.call(Method.INVENTORY, _payload())

        assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT
        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None

    asyncio.run(scenario())


def test_operation_timeout_cancels_then_kills_an_uncooperative_process():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "ignore-cancel-and-term",
            ),
            timeouts=ProcessTimeouts(
                initialize=1.0,
                operation=0.05,
                write=0.5,
                cancellation=0.05,
                shutdown=0.1,
                terminate=0.05,
                kill=0.5,
            ),
        )
        await adapter.start()
        child_pid = adapter.pid

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.call(Method.INVENTORY, _payload())

        assert captured.value.category is ErrorCategory.TIMEOUT
        assert captured.value.code is ProtocolCode.OPERATION_TIMEOUT
        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode",
    ["unsolicited-initialize-cancel", "unsolicited-operation-cancel"],
)
def test_peer_cannot_claim_cancellation_the_client_did_not_request(mode: str):
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(sys.executable, str(FAULT_ADAPTER), mode),
        )

        with pytest.raises(AdapterProtocolError) as captured:
            if mode == "unsolicited-initialize-cancel":
                await adapter.start()
            else:
                await adapter.start()
                await adapter.call(Method.INVENTORY, _payload())

        assert captured.value.category is ErrorCategory.PROCESS_FAILURE
        assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT
        assert adapter.state is ProcessState.FAILED

    asyncio.run(scenario())


def test_one_timeout_fails_every_other_pending_request_without_a_second_wait():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "ignore-cancel-and-term",
            ),
            timeouts=ProcessTimeouts(
                initialize=1.0,
                operation=1.0,
                write=0.5,
                cancellation=0.05,
                shutdown=0.1,
                terminate=0.05,
                kill=0.5,
            ),
        )
        await adapter.start()
        first = await adapter.begin(Method.INVENTORY, _payload())
        second = await adapter.begin(Method.INVENTORY, _payload())
        second_result = asyncio.create_task(second.result(timeout=1.0))

        with pytest.raises(AdapterProtocolError) as first_error:
            await first.result(timeout=0.05)
        assert first_error.value.code is ProtocolCode.OPERATION_TIMEOUT

        with pytest.raises(AdapterProtocolError) as second_error:
            await asyncio.wait_for(second_result, timeout=0.2)
        assert second_error.value.category is ErrorCategory.PROCESS_FAILURE
        assert second_error.value.code is ProtocolCode.PROCESS_EXITED

    asyncio.run(scenario())


def test_write_timeout_fails_the_session_and_reaps_a_peer_that_stops_reading():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "stop-reading-after-init",
            ),
            timeouts=ProcessTimeouts(
                initialize=1.0,
                operation=1.0,
                write=0.05,
                cancellation=0.05,
                shutdown=0.1,
                terminate=0.05,
                kill=0.5,
            ),
        )
        await adapter.start()
        oversized_for_pipe = _payload(
            value=StringValue(kind="string", value="x" * 900_000)
        )

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.begin(Method.INVENTORY, oversized_for_pipe)

        assert captured.value.category is ErrorCategory.TIMEOUT
        assert captured.value.code is ProtocolCode.WRITE_TIMEOUT
        assert adapter.state is ProcessState.FAILED
        assert adapter.returncode is not None

    asyncio.run(scenario())


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_timeout_kills_a_grandchild_that_inherits_the_adapter_process_group():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "grandchild-holds-pipes",
            ),
            timeouts=ProcessTimeouts(
                initialize=1.0,
                operation=0.05,
                write=0.5,
                cancellation=0.05,
                shutdown=0.1,
                terminate=0.05,
                kill=0.5,
            ),
        )
        await adapter.start()

        with pytest.raises(AdapterProtocolError) as captured:
            await adapter.call(Method.INVENTORY, _payload())
        assert captured.value.code is ProtocolCode.OPERATION_TIMEOUT

        diagnostic = adapter.stderr_tail.decode("ascii")
        marker = next(
            line
            for line in diagnostic.splitlines()
            if line.startswith("grandchild_pid=")
        )
        grandchild_pid = int(marker.partition("=")[2])
        for _ in range(50):
            try:
                os.kill(grandchild_pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("adapter grandchild survived process-group teardown")

    asyncio.run(scenario())


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_teardown_kills_inherited_grandchild_after_adapter_leader_exits():
    async def scenario():
        adapter = _process(
            CAPABILITIES[Method.INVENTORY],
            command=(
                sys.executable,
                str(FAULT_ADAPTER),
                "leader-exits-grandchild-holds-pipes",
            ),
            timeouts=ProcessTimeouts(
                initialize=1.0,
                operation=0.1,
                write=0.2,
                cancellation=0.05,
                shutdown=0.1,
                terminate=0.05,
                kill=0.5,
            ),
        )
        await adapter.start()
        await asyncio.sleep(0.05)

        with pytest.raises(AdapterProtocolError):
            await adapter.call(Method.INVENTORY, _payload())

        diagnostic = adapter.stderr_tail.decode("ascii")
        marker = next(
            line
            for line in diagnostic.splitlines()
            if line.startswith("grandchild_pid=")
        )
        grandchild_pid = int(marker.partition("=")[2])
        for _ in range(50):
            try:
                os.kill(grandchild_pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)
        else:
            os.kill(grandchild_pid, 9)
            pytest.fail(
                "adapter grandchild survived teardown after leader exit"
            )

    asyncio.run(scenario())
