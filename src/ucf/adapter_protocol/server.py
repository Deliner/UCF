from __future__ import annotations

import asyncio
import os
import sys
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from ucf.adapter_protocol.codec import decode_request_frame, encode_frame
from ucf.adapter_protocol.dispatcher import AdapterDispatcher, error_response
from ucf.adapter_protocol.errors import AdapterProtocolError
from ucf.adapter_protocol.models import (
    MAX_FRAME_BYTES,
    CancelNotification,
    Method,
    Request,
    ServerMessage,
)


@dataclass(frozen=True)
class _InputItem:
    frame: bytes | None
    error: OSError | ValueError | None
    acknowledged: threading.Event


class _StdinReader:
    """One daemon thread owns blocking stdin reads and bounded handoff."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        buffer: Any,
    ) -> None:
        self._loop = loop
        self._buffer = buffer
        try:
            self._fd: int | None = buffer.fileno()
        except (AttributeError, OSError, ValueError):
            self._fd = None
        self._queue: asyncio.Queue[_InputItem] = asyncio.Queue()
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="ucf-adapter-stdin",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()

    async def read(self) -> bytes:
        item = await self._queue.get()
        item.acknowledged.set()
        if item.error is not None:
            raise item.error
        assert item.frame is not None
        return item.frame

    def _run(self) -> None:
        if self._fd is not None:
            self._run_fd()
            return
        self._run_buffer()

    def _run_buffer(self) -> None:
        while not self._stopped.is_set():
            try:
                frame = self._buffer.readline(MAX_FRAME_BYTES + 1)
            except (OSError, ValueError) as error:
                self._publish(_InputItem(None, error, threading.Event()))
                return
            if not self._publish(
                _InputItem(frame, None, threading.Event())
            ):
                return
            if not frame:
                return

    def _run_fd(self) -> None:
        assert self._fd is not None
        buffered = bytearray()
        while not self._stopped.is_set():
            newline = buffered.find(b"\n")
            if newline >= 0:
                frame = bytes(buffered[: newline + 1])
                del buffered[: newline + 1]
                if not self._publish(
                    _InputItem(frame, None, threading.Event())
                ):
                    return
                continue
            if len(buffered) > MAX_FRAME_BYTES:
                self._publish(
                    _InputItem(
                        bytes(buffered[: MAX_FRAME_BYTES + 1]),
                        None,
                        threading.Event(),
                    )
                )
                return
            try:
                chunk = os.read(self._fd, 65_536)
            except OSError as error:
                if not self._stopped.is_set():
                    self._publish(
                        _InputItem(None, error, threading.Event())
                    )
                return
            if self._stopped.is_set():
                return
            if not chunk:
                self._publish(
                    _InputItem(bytes(buffered), None, threading.Event())
                )
                return
            buffered.extend(chunk)

    def _publish(self, item: _InputItem) -> bool:
        try:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait,
                item,
            )
        except RuntimeError:
            return False
        while not item.acknowledged.wait(0.05):
            if self._stopped.is_set():
                return False
        return True


async def _serve_stdio(dispatcher: AdapterDispatcher) -> int:
    write_lock = asyncio.Lock()
    active: set[asyncio.Task[None]] = set()
    fatal_task = asyncio.Event()
    input_reader = _StdinReader(
        asyncio.get_running_loop(),
        sys.stdin.buffer,
    )
    input_reader.start()

    def operation_done(task: asyncio.Task[None]) -> None:
        active.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            fatal_task.set()

    async def write(message: ServerMessage) -> None:
        frame = encode_frame(message)

        def write_blocking() -> None:
            sys.stdout.buffer.write(frame)
            sys.stdout.buffer.flush()

        async with write_lock:
            write_blocking()

    async def dispatch_operation(request: Request) -> None:
        response = await dispatcher.dispatch(request)
        if response is not None:
            await write(response)

    try:
        while True:
            read_task = asyncio.create_task(input_reader.read())
            failure_task = asyncio.create_task(fatal_task.wait())
            await asyncio.wait(
                (read_task, failure_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if fatal_task.is_set():
                read_task.cancel()
                await asyncio.gather(read_task, return_exceptions=True)
                for task in active:
                    task.cancel()
                if active:
                    await asyncio.gather(*active, return_exceptions=True)
                return 4
            failure_task.cancel()
            await asyncio.gather(failure_task, return_exceptions=True)
            frame = read_task.result()
            if not frame:
                for task in active:
                    task.cancel()
                if active:
                    await asyncio.gather(*active, return_exceptions=True)
                return 3
            try:
                message = decode_request_frame(frame)
            except AdapterProtocolError as error:
                await write(
                    error_response(
                        error.request_id,
                        error.category,
                        error.code,
                        "invalid adapter protocol request",
                    )
                )
                return 2

            if isinstance(message, CancelNotification):
                await dispatcher.dispatch(message)
                continue
            if message.method is Method.INITIALIZE:
                response = await dispatcher.dispatch(message)
                assert response is not None
                await write(response)
                continue
            if message.method is Method.SHUTDOWN:
                response = await dispatcher.dispatch(message)
                assert response is not None
                await write(response)
                if dispatcher.state.value == "closed":
                    if active:
                        await asyncio.gather(*active)
                    return 0
                continue

            task = asyncio.create_task(dispatch_operation(message))
            active.add(task)
            task.add_done_callback(operation_done)
            await asyncio.sleep(0)
    finally:
        input_reader.stop()


def run_stdio_server(dispatcher: AdapterDispatcher) -> int:
    """Run one protocol dispatcher on stdin/stdout until shutdown or failure."""

    try:
        exit_code = asyncio.run(_serve_stdio(dispatcher))
    except (BrokenPipeError, ConnectionError):
        exit_code = 4
    if exit_code == 4:
        _redirect_stdout_to_null()
    return exit_code


def _redirect_stdout_to_null() -> None:
    try:
        stdout_fd = sys.stdout.fileno()
        null_fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null_fd, stdout_fd)
        finally:
            os.close(null_fd)
    except (AttributeError, OSError, ValueError):
        pass
    with suppress(BrokenPipeError):
        sys.stdout.flush()
