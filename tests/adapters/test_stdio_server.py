from __future__ import annotations

import asyncio
import gc
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ucf.adapter_protocol import (
    AdapterPayload,
    CapabilityRequest,
    CapabilitySelection,
    InitializeParams,
    InitializeResult,
    Method,
    OperationKind,
    OperationParams,
    OperationResult,
    Request,
    ShutdownResult,
    SuccessResponse,
    encode_frame,
)
from ucf.adapter_protocol.server import _serve_stdio
from ucf.ir.models import NullValue, Producer

CAPABILITY = "org.ucf.adapter.inventory"
PAYLOAD = AdapterPayload(
    kind="adapter_payload",
    schema_uri="urn:ucf:adapter:test:server-write",
    schema_version="1.0.0",
    value=NullValue(kind="null"),
)


class _DelayedEofBuffer:
    def __init__(self, frames: list[bytes]) -> None:
        self.frames = frames
        self.closed = False

    def readline(self, _limit: int) -> bytes:
        if self.frames:
            return self.frames.pop(0)
        time.sleep(0.1)
        return b""

    def close(self) -> None:
        self.closed = True


class _Stdin:
    def __init__(self, frames: list[bytes]) -> None:
        self.buffer = _DelayedEofBuffer(frames)


class _FailingOutputBuffer:
    def __init__(self) -> None:
        self.writes = 0

    def write(self, _frame: bytes) -> None:
        self.writes += 1
        if self.writes >= 2:
            raise BrokenPipeError("operation response write failed")

    def flush(self) -> None:
        return None


class _Stdout:
    def __init__(self) -> None:
        self.buffer = _FailingOutputBuffer()


@dataclass
class _State:
    value: str = "ready"


class _Dispatcher:
    def __init__(self) -> None:
        self.state = _State()

    async def dispatch(self, message):
        if message.method is Method.INITIALIZE:
            return SuccessResponse(
                jsonrpc="2.0",
                id=message.id,
                result=InitializeResult(
                    kind="initialize_result",
                    protocol_version="1.0.0",
                    adapter=Producer(
                        kind="producer",
                        name="org.ucf.test-adapter",
                        version="1.0.0",
                    ),
                    capabilities=(
                        CapabilitySelection(
                            kind="capability",
                            name=CAPABILITY,
                            version="1.0.0",
                        ),
                    ),
                ),
            )
        if message.method is Method.SHUTDOWN:
            self.state.value = "closed"
            return SuccessResponse(
                jsonrpc="2.0",
                id=message.id,
                result=ShutdownResult(kind="shutdown_result"),
            )
        return SuccessResponse(
            jsonrpc="2.0",
            id=message.id,
            result=OperationResult(
                kind=OperationKind.INVENTORY_RESULT,
                payload=message.params.payload,
            ),
        )


def _frames() -> list[bytes]:
    initialize = Request(
        jsonrpc="2.0",
        id="initialize",
        method=Method.INITIALIZE,
        params=InitializeParams(
            kind="initialize_request",
            protocol_version="1.0.0",
            client=Producer(
                kind="producer",
                name="org.ucf.test-client",
                version="1.0.0",
            ),
            capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name=CAPABILITY,
                    minimum_version="1.0.0",
                    required=True,
                ),
            ),
        ),
    )
    operation = Request(
        jsonrpc="2.0",
        id="operation",
        method=Method.INVENTORY,
        params=OperationParams(
            kind=OperationKind.INVENTORY_REQUEST,
            payload=PAYLOAD,
        ),
    )
    return [encode_frame(initialize), encode_frame(operation)]


def test_background_response_write_failure_is_retrieved_and_stops_server(
    monkeypatch,
):
    async def scenario():
        fake_stdin = _Stdin(_frames())
        fake_stdout = _Stdout()
        contexts = []
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(
            lambda _loop, context: contexts.append(context)
        )
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        monkeypatch.setattr(sys, "stdout", fake_stdout)
        try:
            returncode = await _serve_stdio(_Dispatcher())
            await asyncio.sleep(0)
            gc.collect()
            await asyncio.sleep(0)
        finally:
            loop.set_exception_handler(previous_handler)

        assert returncode == 4
        assert contexts == []

    asyncio.run(scenario())


def test_broken_operation_output_exits_with_open_real_stdin_pipe():
    process = subprocess.Popen(
        (
            sys.executable,
            str(
                Path(__file__).resolve().parents[1]
                / "fixtures"
                / "adapters"
                / "reference_adapter.py"
            ),
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    try:
        process.stdin.write(_frames()[0])
        process.stdin.flush()
        assert process.stdout.readline()
        process.stdout.close()
        process.stdin.write(_frames()[1])
        process.stdin.flush()

        assert process.wait(timeout=2) == 4
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        process.stdin.close()
