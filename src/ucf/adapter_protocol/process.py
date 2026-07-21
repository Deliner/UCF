from __future__ import annotations

import asyncio
import math
import os
import signal
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from ucf import __version__
from ucf.adapter_protocol.codec import (
    decode_response_frame,
    encode_frame,
)
from ucf.adapter_protocol.errors import (
    AdapterProtocolError,
    ErrorCategory,
    ProtocolCode,
)
from ucf.adapter_protocol.models import (
    ADAPTER_PROTOCOL_VERSION,
    MAX_FRAME_BYTES,
    MAX_PENDING_REQUESTS,
    MAX_REQUESTS_PER_SESSION,
    MAX_RETAINED_STDERR_BYTES,
    CancelNotification,
    CancelParams,
    CapabilityRequest,
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
    ShutdownParams,
    ShutdownResult,
    SuccessResponse,
)
from ucf.adapter_protocol.versioning import version_at_least
from ucf.ir.codec import MAX_SAFE_INTEGER
from ucf.ir.models import Producer

_METHOD_CAPABILITY = {
    Method.INVENTORY: "org.ucf.adapter.inventory",
    Method.DISCOVER: "org.ucf.adapter.discovery",
    Method.MAP: "org.ucf.adapter.mapping",
    Method.GENERATE: "org.ucf.adapter.generation",
    Method.VERIFY: "org.ucf.adapter.verification",
}
_METHOD_REQUEST_KIND = {
    Method.INVENTORY: OperationKind.INVENTORY_REQUEST,
    Method.DISCOVER: OperationKind.DISCOVER_REQUEST,
    Method.MAP: OperationKind.MAP_REQUEST,
    Method.GENERATE: OperationKind.GENERATE_REQUEST,
    Method.VERIFY: OperationKind.VERIFY_REQUEST,
}
_METHOD_RESULT_KIND = {
    Method.INVENTORY: OperationKind.INVENTORY_RESULT,
    Method.DISCOVER: OperationKind.DISCOVER_RESULT,
    Method.MAP: OperationKind.MAP_RESULT,
    Method.GENERATE: OperationKind.GENERATE_RESULT,
    Method.VERIFY: OperationKind.VERIFY_RESULT,
}
_PEER_ERROR_CATEGORIES = {
    ErrorCategory.PROTOCOL_FAILURE,
    ErrorCategory.ADAPTER_FAILURE,
    ErrorCategory.CANCELLED,
}
_MINIMAL_ENV_ALLOWLIST = (
    "PATH",
    "LANG",
    "LC_ALL",
    "SYSTEMROOT",
    "WINDIR",
    "TMPDIR",
    "TEMP",
    "TMP",
)


class ProcessState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass(frozen=True)
class ProcessTimeouts:
    initialize: float = 5.0
    operation: float = 30.0
    write: float = 5.0
    cancellation: float = 1.0
    shutdown: float = 2.0
    terminate: float = 1.0
    kill: float = 1.0

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            _validate_timeout(value, name=f"{name} timeout")


@dataclass(frozen=True)
class _Pending:
    method: Method
    future: asyncio.Future[ServerMessage]
    cancel_requested: bool = False


class AdapterCall:
    def __init__(
        self,
        owner: AdapterProcess,
        request_id: str,
        method: Method,
        future: asyncio.Future[ServerMessage],
    ) -> None:
        self._owner = owner
        self.request_id = request_id
        self._method = method
        self._future = future

    async def result(self, timeout: float | None = None) -> Payload:
        return await self._owner._await_operation(
            self.request_id,
            self._method,
            self._future,
            timeout if timeout is not None else self._owner.timeouts.operation,
        )

    async def cancel(self) -> Payload:
        return await self._owner._cancel_call(
            self.request_id,
            self._method,
            self._future,
        )


class AdapterProcess:
    """Bounded JSON-RPC client for one separately launched adapter process."""

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        requested_capabilities: tuple[CapabilityRequest, ...],
        timeouts: ProcessTimeouts | None = None,
        environment: Mapping[str, str] | None = None,
        client: Producer | None = None,
        retain_stderr_tail: bool = True,
    ) -> None:
        if not command or any(
            not isinstance(part, str) or not part or "\0" in part
            for part in command
        ):
            raise ValueError("adapter command must contain nonempty argv strings")
        if not isinstance(cwd, Path):
            raise ValueError("adapter cwd must be a pathlib.Path")
        if type(retain_stderr_tail) is not bool:
            raise ValueError("retain_stderr_tail must be a bool")
        resolved_cwd = cwd.resolve()
        if not resolved_cwd.is_dir():
            raise ValueError("adapter cwd must be an existing directory")
        names = [item.name for item in requested_capabilities]
        if len(names) != len(set(names)):
            raise ValueError("requested capability names must be unique")
        self.command = command
        self.cwd = resolved_cwd
        self.requested_capabilities = requested_capabilities
        self.timeouts = timeouts or ProcessTimeouts()
        self._environment = dict(environment or {})
        if any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not key
            or "=" in key
            or "\0" in key
            or "\0" in value
            for key, value in self._environment.items()
        ):
            raise ValueError("adapter environment contains an invalid entry")
        self._client = client or Producer(
            kind="producer",
            name="org.ucf.core",
            version=__version__,
        )
        self._retain_stderr_tail = retain_stderr_tail
        self._state = ProcessState.NEW
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[str, _Pending] = {}
        self._pending_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._termination_lock = asyncio.Lock()
        self._request_sequence = 0
        self._negotiated: dict[str, str] = {}
        self._stdout_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_total_bytes = 0
        self._stderr_tail = bytearray()
        self._fatal_error: AdapterProtocolError | None = None

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def pid(self) -> int:
        if self._process is None:
            raise RuntimeError("adapter process has not started")
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return None if self._process is None else self._process.returncode

    @property
    def negotiated_capabilities(self) -> dict[str, str]:
        return dict(self._negotiated)

    @property
    def stderr_total_bytes(self) -> int:
        return self._stderr_total_bytes

    @property
    def stderr_tail(self) -> bytes:
        return bytes(self._stderr_tail)

    async def start(self) -> InitializeResult:
        if self._state is not ProcessState.NEW:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.INVALID_LIFECYCLE,
                "adapter process can be started exactly once",
            )
        self._state = ProcessState.STARTING
        env = {
            key: os.environ[key]
            for key in _MINIMAL_ENV_ALLOWLIST
            if key in os.environ
        }
        env.update(self._environment)
        kwargs: dict[str, object] = {}
        if os.name == "posix":
            kwargs["start_new_session"] = True
        spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.cwd),
                env=env,
                limit=65_536,
                **kwargs,
            )
        )
        try:
            self._process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            try:
                self._process = await spawn
            except (OSError, ValueError):
                self._process = None
            self._state = ProcessState.FAILED
            await self._terminate()
            raise
        except (OSError, ValueError) as error:
            self._state = ProcessState.FAILED
            raise AdapterProtocolError(
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.START_FAILED,
                "adapter process could not be started",
            ) from error

        self._stderr_task = asyncio.create_task(self._drain_stderr())
        self._stdout_task = asyncio.create_task(self._read_stdout())
        future: asyncio.Future[ServerMessage] | None = None
        try:
            _, future = await self._send_request(
                Method.INITIALIZE,
                InitializeParams(
                    kind="initialize_request",
                    protocol_version=ADAPTER_PROTOCOL_VERSION,
                    client=self._client,
                    capabilities=self.requested_capabilities,
                ),
            )
            response = await self._wait_for_response(
                future,
                self.timeouts.initialize,
                ProtocolCode.INITIALIZE_TIMEOUT,
            )
            result = self._unwrap_initialize(response)
            self._state = ProcessState.READY
            return result
        except asyncio.CancelledError:
            if future is not None:
                await self._drop_future(future)
            await self._abort_session(_session_ended_error())
            raise
        except AdapterProtocolError:
            self._state = ProcessState.FAILED
            await self._terminate()
            raise

    async def begin(
        self,
        method: Method,
        payload: Payload,
    ) -> AdapterCall:
        if self._state is not ProcessState.READY:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.INVALID_LIFECYCLE,
                "adapter operation requires a ready process",
            )
        capability = _METHOD_CAPABILITY.get(method)
        if capability is None:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.METHOD_NOT_FOUND,
                "method is not an adapter operation",
            )
        if capability not in self._negotiated:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.CAPABILITY_NOT_NEGOTIATED,
                "operation capability was not negotiated",
            )
        request_id, future = await self._send_request(
            method,
            OperationParams(
                kind=_METHOD_REQUEST_KIND[method],
                payload=payload,
            ),
        )
        return AdapterCall(self, request_id, method, future)

    async def call(
        self,
        method: Method,
        payload: Payload,
        *,
        timeout: float | None = None,
    ) -> Payload:
        if timeout is not None:
            _validate_timeout(timeout, name="operation timeout")
        call = await self.begin(method, payload)
        return await call.result(timeout)

    async def close(self) -> None:
        if self._state is ProcessState.CLOSED:
            return
        if self._state is ProcessState.NEW:
            self._state = ProcessState.CLOSED
            return
        if self._state is ProcessState.FAILED:
            await self._terminate()
            return
        if self._state is not ProcessState.READY:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.INVALID_LIFECYCLE,
                "adapter process cannot close from its current state",
            )
        self._state = ProcessState.STOPPING
        future: asyncio.Future[ServerMessage] | None = None
        try:
            if self._pending:
                await self._cancel_pending_for_close()
            _, future = await self._send_request(
                Method.SHUTDOWN,
                ShutdownParams(kind="shutdown_request"),
            )
            response = await self._wait_for_response(
                future,
                self.timeouts.shutdown,
                ProtocolCode.SHUTDOWN_TIMEOUT,
            )
            if (
                not isinstance(response, SuccessResponse)
                or not isinstance(response.result, ShutdownResult)
            ):
                self._raise_peer_response(response)
            process = self._require_process()
            if process.stdin is not None:
                process.stdin.close()
            try:
                returncode = await asyncio.wait_for(
                    process.wait(),
                    timeout=self.timeouts.shutdown,
                )
            except TimeoutError as error:
                self._state = ProcessState.FAILED
                await self._terminate()
                raise AdapterProtocolError(
                    ErrorCategory.TIMEOUT,
                    ProtocolCode.SHUTDOWN_TIMEOUT,
                    "adapter did not exit after shutdown",
                ) from error
            if returncode != 0:
                self._state = ProcessState.FAILED
                await self._finish_io_tasks()
                raise AdapterProtocolError(
                    ErrorCategory.PROCESS_FAILURE,
                    ProtocolCode.PROCESS_EXITED,
                    "adapter exited nonzero after shutdown",
                )
            await self._finish_io_tasks()
            self._state = ProcessState.CLOSED
        except asyncio.CancelledError:
            if future is not None:
                await self._drop_future(future)
            await self._abort_session(_session_ended_error())
            raise
        except AdapterProtocolError:
            self._state = ProcessState.FAILED
            await self._terminate()
            raise

    async def _send_request(
        self,
        method: Method,
        params: InitializeParams | OperationParams | ShutdownParams,
    ) -> tuple[str, asyncio.Future[ServerMessage]]:
        async with self._pending_lock:
            if len(self._pending) >= MAX_PENDING_REQUESTS:
                raise AdapterProtocolError(
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.TOO_MANY_PENDING,
                    "pending request limit reached",
                )
            if self._request_sequence >= MAX_REQUESTS_PER_SESSION or (
                self._request_sequence == MAX_REQUESTS_PER_SESSION - 1
                and method is not Method.SHUTDOWN
            ):
                raise AdapterProtocolError(
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.SESSION_REQUEST_LIMIT,
                    "adapter session request limit reached",
                )
            self._request_sequence += 1
            request_id = f"request-{self._request_sequence}"
            future = asyncio.get_running_loop().create_future()
            future.add_done_callback(_retrieve_future_exception)
            self._pending[request_id] = _Pending(method=method, future=future)
        request = Request(
            jsonrpc="2.0",
            id=request_id,
            method=method,
            params=params,
        )
        try:
            await self._write(encode_frame(request))
        except asyncio.CancelledError:
            await self._drop_pending(request_id)
            await self._abort_session(_session_ended_error())
            raise
        except AdapterProtocolError:
            await self._drop_pending(request_id)
            self._state = ProcessState.FAILED
            await self._fail_pending(_session_ended_error())
            await self._terminate()
            raise
        return request_id, future

    async def _write(self, frame: bytes) -> None:
        process = self._require_process()
        if process.stdin is None or process.stdin.is_closing():
            raise AdapterProtocolError(
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.IO_FAILURE,
                "adapter stdin is unavailable",
            )
        try:
            async with self._write_lock:
                process.stdin.write(frame)
                await asyncio.wait_for(
                    process.stdin.drain(),
                    timeout=self.timeouts.write,
                )
        except TimeoutError as error:
            raise AdapterProtocolError(
                ErrorCategory.TIMEOUT,
                ProtocolCode.WRITE_TIMEOUT,
                "adapter stdin write timed out",
            ) from error
        except (BrokenPipeError, ConnectionError, OSError) as error:
            raise AdapterProtocolError(
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.IO_FAILURE,
                "adapter stdin write failed",
            ) from error

    async def _write_cancel(self, request_id: str) -> None:
        async with self._pending_lock:
            pending = self._pending.get(request_id)
            if pending is None:
                return
            self._pending[request_id] = replace(
                pending,
                cancel_requested=True,
            )
        try:
            await self._write(
                encode_frame(
                    CancelNotification(
                        jsonrpc="2.0",
                        method=Method.CANCEL,
                        params=CancelParams(
                            kind="cancel_request",
                            request_id=request_id,
                        ),
                    )
                )
            )
        except AdapterProtocolError:
            self._state = ProcessState.FAILED
            await self._fail_pending(_session_ended_error())
            await self._terminate()
            raise

    async def _await_operation(
        self,
        request_id: str,
        method: Method,
        future: asyncio.Future[ServerMessage],
        timeout: float,
    ) -> Payload:
        _validate_timeout(timeout, name="operation timeout")
        try:
            response = await asyncio.wait_for(
                asyncio.shield(future),
                timeout=timeout,
            )
        except TimeoutError as error:
            await self._write_cancel(request_id)
            try:
                await asyncio.wait_for(
                    asyncio.shield(future),
                    timeout=self.timeouts.cancellation,
                )
            except TimeoutError:
                await self._drop_pending(request_id)
                self._state = ProcessState.FAILED
                await self._fail_pending(_session_ended_error())
                await self._terminate()
            raise AdapterProtocolError(
                ErrorCategory.TIMEOUT,
                ProtocolCode.OPERATION_TIMEOUT,
                "adapter operation timed out",
                request_id=request_id,
            ) from error
        except asyncio.CancelledError:
            await self._settle_externally_cancelled_operation(
                request_id,
                future,
            )
            raise
        await self._raise_if_fatal()
        return self._unwrap_operation(response, method, request_id)

    async def _cancel_call(
        self,
        request_id: str,
        method: Method,
        future: asyncio.Future[ServerMessage],
    ) -> Payload:
        if future.done():
            return self._unwrap_operation(future.result(), method, request_id)
        await self._write_cancel(request_id)
        try:
            response = await asyncio.wait_for(
                asyncio.shield(future),
                timeout=self.timeouts.cancellation,
            )
        except TimeoutError as error:
            await self._drop_pending(request_id)
            self._state = ProcessState.FAILED
            await self._fail_pending(_session_ended_error())
            await self._terminate()
            raise AdapterProtocolError(
                ErrorCategory.TIMEOUT,
                ProtocolCode.CANCEL_TIMEOUT,
                "adapter did not complete a cancelled request",
                request_id=request_id,
            ) from error
        except asyncio.CancelledError:
            await self._settle_externally_cancelled_operation(
                request_id,
                future,
            )
            raise
        await self._raise_if_fatal()
        return self._unwrap_operation(response, method, request_id)

    async def _wait_for_response(
        self,
        future: asyncio.Future[ServerMessage],
        timeout: float,
        timeout_code: ProtocolCode,
    ) -> ServerMessage:
        try:
            response = await asyncio.wait_for(
                asyncio.shield(future),
                timeout=timeout,
            )
        except TimeoutError as error:
            await self._drop_future(future)
            self._state = ProcessState.FAILED
            await self._fail_pending(_session_ended_error())
            await self._terminate()
            raise AdapterProtocolError(
                ErrorCategory.TIMEOUT,
                timeout_code,
                "adapter response timed out",
            ) from error
        await self._raise_if_fatal()
        return response

    def _unwrap_initialize(self, response: ServerMessage) -> InitializeResult:
        if not isinstance(response, SuccessResponse) or not isinstance(
            response.result, InitializeResult
        ):
            self._raise_peer_response(response)
        result = response.result
        requested = {item.name: item for item in self.requested_capabilities}
        selected = {item.name: item.version for item in result.capabilities}
        invalid_selection = any(
            name not in requested
            or not version_at_least(version, requested[name].minimum_version)
            for name, version in selected.items()
        )
        missing_required = any(
            requirement.required and requirement.name not in selected
            for requirement in self.requested_capabilities
        )
        if invalid_selection or missing_required:
            raise AdapterProtocolError(
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.INVALID_ADAPTER_OUTPUT,
                "adapter returned an invalid capability selection",
            )
        self._negotiated = selected
        return result

    def _unwrap_operation(
        self,
        response: ServerMessage,
        method: Method,
        request_id: str,
    ) -> Payload:
        if not isinstance(response, SuccessResponse) or not isinstance(
            response.result, OperationResult
        ):
            self._raise_peer_response(response)
        if response.result.kind is not _METHOD_RESULT_KIND[method]:
            raise AdapterProtocolError(
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.INVALID_ADAPTER_OUTPUT,
                "adapter returned a result for a different method",
                request_id=request_id,
            )
        return response.result.payload

    @staticmethod
    def _raise_peer_response(response: ServerMessage) -> None:
        if isinstance(response, ErrorResponse):
            raise AdapterProtocolError(
                response.error.data.category,
                response.error.data.ucf_code,
                response.error.message,
                request_id=response.id,
            )
        raise AdapterProtocolError(
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
            "adapter returned an unexpected result",
            request_id=response.id,
        )

    async def _read_stdout(self) -> None:
        process = self._require_process()
        assert process.stdout is not None
        buffered = bytearray()
        try:
            while True:
                chunk = await process.stdout.read(65_536)
                if not chunk:
                    if buffered:
                        raise AdapterProtocolError(
                            ErrorCategory.PROTOCOL_FAILURE,
                            ProtocolCode.TRUNCATED_FRAME,
                            "adapter stdout ended with a partial frame",
                        )
                    async with self._pending_lock:
                        clean_stop = (
                            self._state is ProcessState.STOPPING
                            and not self._pending
                        )
                    if clean_stop:
                        return
                    code = await self._classify_eof()
                    raise AdapterProtocolError(
                        ErrorCategory.PROCESS_FAILURE,
                        code,
                        "adapter stdout closed unexpectedly",
                    )
                buffered.extend(chunk)
                while True:
                    newline = buffered.find(b"\n")
                    if newline < 0:
                        break
                    frame = bytes(buffered[: newline + 1])
                    del buffered[: newline + 1]
                    if len(frame) > MAX_FRAME_BYTES:
                        raise AdapterProtocolError(
                            ErrorCategory.PROTOCOL_FAILURE,
                            ProtocolCode.FRAME_TOO_LARGE,
                            "adapter stdout frame exceeds the limit",
                        )
                    try:
                        response = decode_response_frame(frame)
                    except AdapterProtocolError as error:
                        if error.code in {
                            ProtocolCode.FRAME_TOO_LARGE,
                            ProtocolCode.TRUNCATED_FRAME,
                        }:
                            raise
                        raise AdapterProtocolError(
                            ErrorCategory.PROCESS_FAILURE,
                            ProtocolCode.INVALID_ADAPTER_OUTPUT,
                            "adapter stdout is not a valid response",
                        ) from error
                    await self._correlate(response)
                if len(buffered) > MAX_FRAME_BYTES:
                    raise AdapterProtocolError(
                        ErrorCategory.PROTOCOL_FAILURE,
                        ProtocolCode.FRAME_TOO_LARGE,
                        "adapter stdout frame exceeds the limit",
                    )
        except asyncio.CancelledError:
            raise
        except AdapterProtocolError as error:
            await self._fail_from_reader(error)
        except (ConnectionError, OSError) as error:
            await self._fail_from_reader(
                AdapterProtocolError(
                    ErrorCategory.PROCESS_FAILURE,
                    ProtocolCode.IO_FAILURE,
                    "adapter stdout read failed",
                )
            )
            raise error

    async def _correlate(self, response: ServerMessage) -> None:
        request_id = response.id
        if request_id is None:
            raise AdapterProtocolError(
                ErrorCategory.PROTOCOL_FAILURE,
                ProtocolCode.CORRELATION_FAILURE,
                "adapter response has no correlatable request id",
            )
        async with self._pending_lock:
            pending = self._pending.get(request_id)
            if pending is None:
                raise AdapterProtocolError(
                    ErrorCategory.PROTOCOL_FAILURE,
                    ProtocolCode.CORRELATION_FAILURE,
                    "adapter response id was never pending",
                    request_id=request_id,
                )
            self._validate_response_for_pending(response, pending)
            self._pending.pop(request_id)
        if not pending.future.done():
            pending.future.set_result(response)

    def _validate_response_for_pending(
        self,
        response: ServerMessage,
        pending: _Pending,
    ) -> None:
        if isinstance(response, ErrorResponse):
            if response.error.data.category not in _PEER_ERROR_CATEGORIES:
                raise AdapterProtocolError(
                    ErrorCategory.PROCESS_FAILURE,
                    ProtocolCode.INVALID_ADAPTER_OUTPUT,
                    "adapter forged a local-only error category",
                )
            if (
                response.error.data.category is ErrorCategory.CANCELLED
                and not pending.cancel_requested
            ):
                raise AdapterProtocolError(
                    ErrorCategory.PROCESS_FAILURE,
                    ProtocolCode.INVALID_ADAPTER_OUTPUT,
                    "adapter claimed cancellation the client did not request",
                )
            return
        if pending.method is Method.INITIALIZE:
            valid = isinstance(response.result, InitializeResult)
        elif pending.method is Method.SHUTDOWN:
            valid = isinstance(response.result, ShutdownResult)
        else:
            valid = (
                isinstance(response.result, OperationResult)
                and response.result.kind is _METHOD_RESULT_KIND[pending.method]
            )
        if not valid:
            raise AdapterProtocolError(
                ErrorCategory.PROCESS_FAILURE,
                ProtocolCode.INVALID_ADAPTER_OUTPUT,
                "adapter result does not match its request method",
            )

    async def _drain_stderr(self) -> None:
        process = self._require_process()
        assert process.stderr is not None
        while True:
            chunk = await process.stderr.read(8192)
            if not chunk:
                return
            self._stderr_total_bytes = min(
                MAX_SAFE_INTEGER,
                self._stderr_total_bytes + len(chunk),
            )
            if self._retain_stderr_tail:
                self._stderr_tail.extend(chunk)
                overflow = (
                    len(self._stderr_tail) - MAX_RETAINED_STDERR_BYTES
                )
                if overflow > 0:
                    del self._stderr_tail[:overflow]

    async def _classify_eof(self) -> ProtocolCode:
        process = self._require_process()
        if process.returncode is None:
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=min(0.05, self.timeouts.terminate),
                )
            except TimeoutError:
                return ProtocolCode.UNEXPECTED_EOF
        if process.returncode not in {None, 0}:
            return ProtocolCode.PROCESS_EXITED
        return ProtocolCode.UNEXPECTED_EOF

    async def _fail_from_reader(self, error: AdapterProtocolError) -> None:
        if self._fatal_error is None:
            self._fatal_error = error
        if self._state in {ProcessState.CLOSED, ProcessState.FAILED}:
            return
        self._state = ProcessState.FAILED
        await self._terminate()
        await self._fail_pending(error)

    async def _raise_if_fatal(self) -> None:
        await asyncio.sleep(0)
        if self._fatal_error is not None:
            raise self._fatal_error

    async def _fail_pending(self, error: AdapterProtocolError) -> None:
        async with self._pending_lock:
            pending = tuple(self._pending.values())
            self._pending.clear()
        for item in pending:
            if not item.future.done():
                item.future.set_exception(error)

    async def _abort_session(self, error: AdapterProtocolError) -> None:
        self._state = ProcessState.FAILED
        await self._fail_pending(error)
        await self._terminate()

    async def _settle_externally_cancelled_operation(
        self,
        request_id: str,
        future: asyncio.Future[ServerMessage],
    ) -> None:
        try:
            await self._write_cancel(request_id)
            await asyncio.wait_for(
                asyncio.shield(future),
                timeout=self.timeouts.cancellation,
            )
        except TimeoutError:
            await self._drop_pending(request_id)
            await self._abort_session(_session_ended_error())
        except AdapterProtocolError:
            return

    async def _drop_pending(self, request_id: str) -> None:
        async with self._pending_lock:
            pending = self._pending.pop(request_id, None)
        if pending is not None and not pending.future.done():
            pending.future.cancel()

    async def _drop_future(
        self,
        future: asyncio.Future[ServerMessage],
    ) -> None:
        async with self._pending_lock:
            request_id = next(
                (
                    identity
                    for identity, pending in self._pending.items()
                    if pending.future is future
                ),
                None,
            )
        if request_id is not None:
            await self._drop_pending(request_id)

    async def _cancel_pending_for_close(self) -> None:
        async with self._pending_lock:
            pending = tuple(self._pending.items())
        for request_id, item in pending:
            if item.method in _METHOD_CAPABILITY:
                await self._write_cancel(request_id)
        if not pending:
            return
        _, unfinished = await asyncio.wait(
            [item.future for _, item in pending],
            timeout=self.timeouts.cancellation,
        )
        if unfinished:
            await self._abort_session(_session_ended_error())
            raise AdapterProtocolError(
                ErrorCategory.TIMEOUT,
                ProtocolCode.CANCEL_TIMEOUT,
                "pending requests did not stop before shutdown",
            )

    async def _terminate(self) -> None:
        async with self._termination_lock:
            process = self._process
            if process is None:
                return
            if process.stdin is not None and not process.stdin.is_closing():
                process.stdin.close()
            if os.name == "posix":
                self._signal_process_group(signal.SIGTERM)
            elif process.returncode is None:
                self._signal_process_group(signal.SIGTERM)
            direct_child_timed_out = False
            if process.returncode is None:
                try:
                    await asyncio.wait_for(
                        process.wait(),
                        timeout=self.timeouts.terminate,
                    )
                except TimeoutError:
                    direct_child_timed_out = True
            if os.name == "posix" and not direct_child_timed_out:
                await self._wait_for_process_group_exit(
                    self.timeouts.terminate
                )
            if direct_child_timed_out or (
                os.name == "posix" and self._process_group_exists()
            ):
                self._signal_process_group(signal.SIGKILL)
            if process.returncode is None:
                try:
                    await asyncio.wait_for(
                        process.wait(),
                        timeout=self.timeouts.kill,
                    )
                except TimeoutError as error:
                    await self._fail_pending(
                        AdapterProtocolError(
                            ErrorCategory.PROCESS_FAILURE,
                            ProtocolCode.TERMINATION_FAILED,
                            "adapter direct child could not be reaped",
                        )
                    )
                    raise AdapterProtocolError(
                        ErrorCategory.PROCESS_FAILURE,
                        ProtocolCode.TERMINATION_FAILED,
                        "adapter direct child could not be reaped",
                    ) from error
            await self._finish_io_tasks()

    async def _wait_for_process_group_exit(self, timeout: float) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while self._process_group_exists():
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(0.01, remaining))

    def _process_group_exists(self) -> bool:
        if os.name != "posix":
            return False
        process = self._require_process()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return False
        return True

    def _signal_process_group(self, sig: signal.Signals) -> None:
        process = self._require_process()
        try:
            if os.name == "posix":
                os.killpg(process.pid, sig)
            elif sig is signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
        except ProcessLookupError:
            pass

    async def _finish_io_tasks(self) -> None:
        current = asyncio.current_task()
        tasks = tuple(
            task
            for task in (self._stdout_task, self._stderr_task)
            if task is not None and task is not current
        )
        if not tasks:
            return
        done, pending = await asyncio.wait(tasks, timeout=self.timeouts.kill)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if not task.cancelled():
                task.exception()

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise RuntimeError("adapter process is not available")
        return self._process
def _session_ended_error() -> AdapterProtocolError:
    return AdapterProtocolError(
        ErrorCategory.PROCESS_FAILURE,
        ProtocolCode.PROCESS_EXITED,
        "adapter session ended because another request failed",
    )


def _validate_timeout(value: float, *, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a finite positive number")


def _retrieve_future_exception(
    future: asyncio.Future[ServerMessage],
) -> None:
    if not future.cancelled():
        future.exception()
