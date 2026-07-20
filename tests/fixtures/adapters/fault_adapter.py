from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
import time

from ucf.adapter_protocol import (
    AdapterDispatcher,
    CapabilitySelection,
    ErrorCategory,
    ErrorData,
    ErrorObject,
    ErrorResponse,
    InitializeResult,
    OperationKind,
    OperationResult,
    ProtocolCode,
    RequestContext,
    SuccessResponse,
    decode_request_frame,
    encode_frame,
    run_stdio_server,
)
from ucf.ir.models import Producer

_INVENTORY_CAPABILITY = "org.ucf.adapter.inventory"
_MODES = frozenset(
    {
        "stdout-noise",
        "partial-eof",
        "exit-nonzero",
        "unknown-response-id",
        "ignore-cancel-and-term",
        "stop-reading-after-init",
        "duplicate-init-response",
        "forged-process-error",
        "unrequested-capability",
        "wrong-operation-result",
        "grandchild-holds-pipes",
        "leader-exits-grandchild-holds-pipes",
        "unsolicited-initialize-cancel",
        "unsolicited-operation-cancel",
        "block-before-initialize-response",
    }
)


def _read_initialization_request():
    return decode_request_frame(sys.stdin.buffer.readline())


def _write_stdout(payload: bytes) -> None:
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _initialize_response(
    request_id: str,
    capability: str = _INVENTORY_CAPABILITY,
) -> bytes:
    return encode_frame(
        SuccessResponse(
            jsonrpc="2.0",
            id=request_id,
            result=InitializeResult(
                kind="initialize_result",
                protocol_version="1.0.0",
                adapter=Producer(
                    kind="producer",
                    name="org.ucf.fault-adapter",
                    version="1.0.0",
                ),
                capabilities=(
                    CapabilitySelection(
                        kind="capability",
                        name=capability,
                        version="1.0.0",
                    ),
                ),
            ),
        )
    )


def _unknown_response() -> bytes:
    return _initialize_response("never-requested")


def _forged_process_error(request_id: str) -> bytes:
    return (
        '{"error":{"code":-32000,"data":{"category":"process_failure",'
        '"ucf_code":"process_exited"},"message":"forged local process '
        f'outcome"}},"id":"{request_id}","jsonrpc":"2.0"}}\n'
    ).encode()


def _cancelled_error(request_id: str) -> bytes:
    return encode_frame(
        ErrorResponse(
            jsonrpc="2.0",
            id=request_id,
            error=ErrorObject(
                code=-32000,
                message="request cancelled",
                data=ErrorData(
                    category=ErrorCategory.CANCELLED,
                    ucf_code=ProtocolCode.REQUEST_CANCELLED,
                ),
            ),
        )
    )


def _spawn_pipe_holding_grandchild() -> subprocess.Popen:
    grandchild = subprocess.Popen(
        (
            sys.executable,
            "-c",
            (
                "import signal,time;"
                "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                "time.sleep(3600)"
            ),
        ),
        stdin=subprocess.DEVNULL,
    )
    print(f"grandchild_pid={grandchild.pid}", file=sys.stderr, flush=True)
    return grandchild


async def _ignore_request(method, payload, context: RequestContext):
    del method, payload, context
    await asyncio.Event().wait()
    raise AssertionError("unreachable")


def _uncooperative_dispatcher() -> AdapterDispatcher:
    return AdapterDispatcher(
        adapter=Producer(
            kind="producer",
            name="org.ucf.fault-adapter",
            version="1.0.0",
        ),
        offered_capabilities=(
            CapabilitySelection(
                kind="capability",
                name=_INVENTORY_CAPABILITY,
                version="1.0.0",
            ),
        ),
        handler=_ignore_request,
    )


def main(mode: str) -> int:
    if mode in {"ignore-cancel-and-term", "grandchild-holds-pipes"}:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if mode == "grandchild-holds-pipes":
            _spawn_pipe_holding_grandchild()
        return run_stdio_server(_uncooperative_dispatcher())

    initialization = _read_initialization_request()
    if mode == "block-before-initialize-response":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(3600)
    if mode == "unsolicited-initialize-cancel":
        _write_stdout(_cancelled_error(initialization.id))
        return 0
    if mode == "stop-reading-after-init":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        _write_stdout(_initialize_response(initialization.id))
        while True:
            time.sleep(3600)
    if mode == "duplicate-init-response":
        response = _initialize_response(initialization.id)
        _write_stdout(response + response)
        return 0
    if mode == "forged-process-error":
        _write_stdout(_forged_process_error(initialization.id))
        return 0
    if mode == "unrequested-capability":
        _write_stdout(
            _initialize_response(
                initialization.id,
                capability="org.example.unrequested",
            )
        )
        return 0
    if mode == "wrong-operation-result":
        _write_stdout(_initialize_response(initialization.id))
        operation = decode_request_frame(sys.stdin.buffer.readline())
        _write_stdout(
            encode_frame(
                SuccessResponse(
                    jsonrpc="2.0",
                    id=operation.id,
                    result=OperationResult(
                        kind=OperationKind.VERIFY_RESULT,
                        payload=operation.params.payload,
                    ),
                )
            )
        )
        return 0
    if mode == "unsolicited-operation-cancel":
        _write_stdout(_initialize_response(initialization.id))
        operation = decode_request_frame(sys.stdin.buffer.readline())
        _write_stdout(_cancelled_error(operation.id))
        return 0
    if mode == "leader-exits-grandchild-holds-pipes":
        _write_stdout(_initialize_response(initialization.id))
        _spawn_pipe_holding_grandchild()
        return 17
    if mode == "stdout-noise":
        _write_stdout(b"adapter log on protocol stdout\n")
        return 0
    if mode == "partial-eof":
        _write_stdout(b'{"id":"partial","jsonrpc":"2.0"')
        return 0
    if mode == "exit-nonzero":
        return 17
    if mode == "unknown-response-id":
        _write_stdout(_unknown_response())
        return 0
    raise ValueError(f"unsupported fault mode: {mode}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in _MODES:
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
