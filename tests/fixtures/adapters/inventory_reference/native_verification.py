from __future__ import annotations

import hashlib
import os
import platform
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .implementation_evidence import (
    ENVIRONMENT_IDENTITY_URI,
    PRODUCER,
    VERIFICATION_ADAPTER_PROCEDURE_URI,
    VERSION,
    canonical_json,
)

CHECK_PATH = "tests/behavior_checks.py"
CHECK_SHA256 = "45402e8f23021b3e3ac798f198eb38c1cc816b83435ccbe8c0e5e802c19aaebf"
SOURCE_PATHS = (
    "src/legacy_quote/__init__.py",
    "src/legacy_quote/service.py",
    CHECK_PATH,
)
SUCCESS_STDOUT = b"3 native behavior checks passed\n"
SNAPSHOT_PREFIX = "ucf-python-native-"

type NativeOutcome = Literal["passed", "failed", "error"]


class NativeVerificationError(RuntimeError):
    def __init__(self, code: Literal["operation_failed"], message: str) -> None:
        super().__init__(message)
        self.code = code


class NativeVerificationCancelled(NativeVerificationError):
    def __init__(self) -> None:
        super().__init__("operation_failed", "native verification was cancelled")


@dataclass(frozen=True)
class NativeVerificationLimits:
    execution_timeout: float
    termination_grace: float
    cleanup_timeout: float
    max_output_bytes: int
    max_source_file_bytes: int
    max_snapshot_bytes: int
    max_interpreter_bytes: int

    def __post_init__(self) -> None:
        if (
            self.execution_timeout <= 0
            or self.termination_grace < 0
            or self.cleanup_timeout <= self.termination_grace
            or self.max_output_bytes <= 0
            or self.max_source_file_bytes <= 0
            or self.max_snapshot_bytes < self.max_source_file_bytes
            or self.max_interpreter_bytes <= 0
        ):
            raise ValueError("native verification limits are invalid")


DEFAULT_LIMITS = NativeVerificationLimits(
    execution_timeout=5.0,
    termination_grace=1.0,
    cleanup_timeout=2.0,
    max_output_bytes=65_536,
    max_source_file_bytes=1_048_576,
    max_snapshot_bytes=4_194_304,
    max_interpreter_bytes=67_108_864,
)


@dataclass(frozen=True)
class NativeVerificationResult:
    outcome: NativeOutcome


@dataclass(frozen=True)
class _Artifact:
    path: str
    payload: bytes
    digest: str


@dataclass(frozen=True)
class _ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    overflow: bool


def build_execution_environment(
    root_path: str | Path,
    inventory: object,
    *,
    limits: NativeVerificationLimits = DEFAULT_LIMITS,
) -> dict[str, object]:
    root = _root_directory(root_path)
    inventory_value = _inventory(inventory)
    artifacts = _load_artifacts(root, inventory_value, limits)
    interpreter, interpreter_size, interpreter_digest = _interpreter(limits)
    receipt = _execution_receipt(
        artifacts,
        interpreter=interpreter,
        interpreter_size=interpreter_size,
        interpreter_digest=interpreter_digest,
    )
    return {
        "kind": "execution_environment",
        "identity_uri": ENVIRONMENT_IDENTITY_URI,
        "revision": {
            "kind": "digest",
            "algorithm": "sha-256",
            "value": hashlib.sha256(canonical_json(receipt)).hexdigest(),
        },
    }


def run_native_verification(
    root_path: str | Path,
    inventory: object,
    *,
    expected_total_cents: int,
    cancel_event: threading.Event | None = None,
    limits: NativeVerificationLimits = DEFAULT_LIMITS,
) -> NativeVerificationResult:
    if (
        type(expected_total_cents) is not int
        or not 0 <= expected_total_cents <= 9_007_199_254_740_991
    ):
        raise NativeVerificationError(
            "operation_failed",
            "native verification expected output is invalid",
        )
    cancellation = threading.Event() if cancel_event is None else cancel_event
    if cancellation.is_set():
        raise NativeVerificationCancelled
    root = _root_directory(root_path)
    inventory_value = _inventory(inventory)
    artifacts = _load_artifacts(root, inventory_value, limits)
    interpreter, _, _ = _interpreter(limits)
    try:
        snapshot = Path(tempfile.mkdtemp(prefix=SNAPSHOT_PREFIX))
    except OSError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification snapshot could not be created",
        ) from error
    try:
        try:
            _write_snapshot(snapshot, artifacts)
        except OSError as error:
            raise NativeVerificationError(
                "operation_failed",
                "native verification snapshot could not be populated",
            ) from error
        result = _execute_native_check(
            snapshot,
            interpreter,
            cancellation,
            limits,
        )
        if cancellation.is_set():
            raise NativeVerificationCancelled
        current = _load_artifacts(root, inventory_value, limits)
        if current != artifacts:
            raise NativeVerificationError(
                "operation_failed",
                "native verification source changed during execution",
            )
        if (
            result.timed_out
            or result.overflow
            or result.returncode != 0
            or result.stderr != b""
            or result.stdout != SUCCESS_STDOUT
        ):
            return NativeVerificationResult(outcome="error")
        return NativeVerificationResult(
            outcome=("passed" if expected_total_cents == 2500 else "failed")
        )
    finally:
        try:
            shutil.rmtree(snapshot)
        except OSError as error:
            raise NativeVerificationError(
                "operation_failed",
                "native verification snapshot cleanup failed",
            ) from error


def _execution_receipt(
    artifacts: tuple[_Artifact, ...],
    *,
    interpreter: Path,
    interpreter_size: int,
    interpreter_digest: str,
) -> dict[str, object]:
    version = sys.version_info
    return {
        "kind": "python_native_execution_receipt",
        "receipt_version": VERSION,
        "producer": PRODUCER,
        "procedure_uri": VERIFICATION_ADAPTER_PROCEDURE_URI,
        "runtime": {
            "kind": "python_runtime_coordinates",
            "implementation": sys.implementation.name,
            "version": f"{version.major}.{version.minor}.{version.micro}",
            "cache_tag": sys.implementation.cache_tag,
            "platform": sys.platform,
            "machine": platform.machine(),
            "executable": {
                "kind": "executable_identity",
                "logical_name": "python",
                "resolved_name": interpreter.name,
                "size_bytes": interpreter_size,
                "content_digest": _digest(interpreter_digest),
            },
        },
        "argv": [
            "python",
            "-P",
            "-B",
            "-S",
            CHECK_PATH,
        ],
        "environment": [
            ["PYTHONHASHSEED", "0"],
            ["PYTHONIOENCODING", "utf-8"],
            ["PYTHONPATH", "src"],
            ["PYTHONUTF8", "1"],
        ],
        "artifacts": [
            {
                "kind": "execution_artifact",
                "path": artifact.path,
                "size_bytes": len(artifact.payload),
                "content_digest": _digest(artifact.digest),
            }
            for artifact in artifacts
        ],
    }


def _execute_native_check(
    snapshot: Path,
    interpreter: Path,
    cancellation: threading.Event,
    limits: NativeVerificationLimits,
) -> _ProcessResult:
    command = (
        str(interpreter),
        "-P",
        "-B",
        "-S",
        CHECK_PATH,
    )
    environment = {
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(snapshot / "src"),
        "PYTHONUTF8": "1",
    }
    try:
        process = subprocess.Popen(
            command,
            cwd=snapshot,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification process could not start",
        ) from error
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_descriptor = process.stdout.fileno()
    stderr_descriptor = process.stderr.fileno()
    selector = selectors.DefaultSelector()
    buffers = {
        stdout_descriptor: bytearray(),
        stderr_descriptor: bytearray(),
    }
    streams = {
        stdout_descriptor: process.stdout,
        stderr_descriptor: process.stderr,
    }
    for descriptor, stream in streams.items():
        os.set_blocking(descriptor, False)
        selector.register(stream, selectors.EVENT_READ, descriptor)
    deadline = time.monotonic() + limits.execution_timeout
    timed_out = False
    overflow = False
    cancelled = False
    try:
        while selector.get_map() or process.poll() is None:
            if cancellation.is_set():
                cancelled = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(timeout=min(remaining, 0.025)):
                descriptor = key.data
                try:
                    chunk = os.read(descriptor, 8192)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer = buffers[descriptor]
                available = limits.max_output_bytes + 1 - len(buffer)
                if available > 0:
                    buffer.extend(chunk[:available])
                if len(buffer) > limits.max_output_bytes or len(chunk) > available:
                    overflow = True
                    break
            if overflow:
                break
        if cancelled or timed_out or overflow or process.poll() is None:
            _terminate_process_group(process, limits)
        else:
            _kill_remaining_process_group(process.pid, limits.cleanup_timeout)
        _drain_available(selector, buffers, limits.max_output_bytes)
        returncode = process.wait(timeout=limits.cleanup_timeout)
    except subprocess.TimeoutExpired as error:
        _terminate_process_group(process, limits)
        raise NativeVerificationError(
            "operation_failed",
            "native verification process cleanup timed out",
        ) from error
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if cancelled:
        raise NativeVerificationCancelled
    return _ProcessResult(
        returncode=returncode,
        stdout=bytes(buffers[stdout_descriptor])[: limits.max_output_bytes],
        stderr=bytes(buffers[stderr_descriptor])[: limits.max_output_bytes],
        timed_out=timed_out,
        overflow=overflow,
    )


def _drain_available(
    selector: selectors.BaseSelector,
    buffers: dict[int, bytearray],
    limit: int,
) -> None:
    while selector.get_map():
        events = selector.select(timeout=0)
        if not events:
            return
        for key, _ in events:
            descriptor = key.data
            try:
                chunk = os.read(descriptor, 8192)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            available = max(0, limit + 1 - len(buffers[descriptor]))
            buffers[descriptor].extend(chunk[:available])


def _terminate_process_group(
    process: subprocess.Popen[bytes],
    limits: NativeVerificationLimits,
) -> None:
    _signal_process_group(process.pid, signal.SIGTERM)
    graceful_deadline = time.monotonic() + limits.termination_grace
    while process.poll() is None and time.monotonic() < graceful_deadline:
        threading.Event().wait(0.01)
    _signal_process_group(process.pid, signal.SIGKILL)
    try:
        process.wait(
            timeout=max(
                0.01,
                limits.cleanup_timeout - limits.termination_grace,
            )
        )
    except subprocess.TimeoutExpired as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification process could not be reaped",
        ) from error
    _wait_for_process_group_exit(process.pid, limits.cleanup_timeout)


def _kill_remaining_process_group(process_id: int, timeout: float) -> None:
    _signal_process_group(process_id, signal.SIGKILL)
    _wait_for_process_group_exit(process_id, timeout)


def _signal_process_group(process_id: int, signal_number: signal.Signals) -> None:
    try:
        os.killpg(process_id, signal_number)
    except ProcessLookupError:
        return
    except PermissionError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification process group is not owned",
        ) from error


def _wait_for_process_group_exit(process_id: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.killpg(process_id, 0)
        except ProcessLookupError:
            return
        except PermissionError as error:
            raise NativeVerificationError(
                "operation_failed",
                "native verification process group ownership was lost",
            ) from error
        if time.monotonic() >= deadline:
            raise NativeVerificationError(
                "operation_failed",
                "native verification process group cleanup timed out",
            )
        threading.Event().wait(0.01)


def _write_snapshot(
    snapshot: Path,
    artifacts: tuple[_Artifact, ...],
) -> None:
    for artifact in artifacts:
        destination = snapshot / artifact.path
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o400,
        )
        try:
            view = memoryview(artifact.payload)
            written = 0
            while written < len(view):
                written += os.write(descriptor, view[written:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _load_artifacts(
    root: Path,
    inventory: dict[str, object],
    limits: NativeVerificationLimits,
) -> tuple[_Artifact, ...]:
    expected = _repository_files(inventory)
    artifacts = []
    total = 0
    for path in SOURCE_PATHS:
        payload = _read_beneath(root, path, limits.max_source_file_bytes)
        digest = hashlib.sha256(payload).hexdigest()
        record = expected.get(path)
        if (
            record is None
            or record.get("entry_kind") != "file"
            or record.get("size_bytes") != len(payload)
            or record.get("content_digest") != _digest(digest)
        ):
            raise NativeVerificationError(
                "operation_failed",
                "native verification source differs from inventory",
            )
        if path == CHECK_PATH and digest != CHECK_SHA256:
            raise NativeVerificationError(
                "operation_failed",
                "native verification check procedure is incompatible",
            )
        total += len(payload)
        if total > limits.max_snapshot_bytes:
            raise NativeVerificationError(
                "operation_failed",
                "native verification snapshot exceeds the byte limit",
            )
        artifacts.append(_Artifact(path=path, payload=payload, digest=digest))
    return tuple(artifacts)


def _repository_files(
    inventory: dict[str, object],
) -> dict[str, dict[str, object]]:
    records = inventory.get("records")
    if type(records) is not list:
        raise NativeVerificationError(
            "operation_failed",
            "native verification inventory records are unavailable",
        )
    result: dict[str, dict[str, object]] = {}
    for record in records:
        if type(record) is not dict or record.get("kind") != "repository_entry":
            continue
        path = record.get("path")
        if type(path) is not str or path in result:
            raise NativeVerificationError(
                "operation_failed",
                "native verification inventory paths are invalid",
            )
        result[path] = record
    return result


def _read_beneath(root: Path, relative_path: str, limit: int) -> bytes:
    components = relative_path.split("/")
    if not components or any(component in {"", ".", ".."} for component in components):
        raise NativeVerificationError(
            "operation_failed",
            "native verification source path is invalid",
        )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        current = os.open(root, directory_flags)
        try:
            for component in components[:-1]:
                child = os.open(component, directory_flags, dir_fd=current)
                os.close(current)
                current = child
            descriptor = os.open(components[-1], file_flags, dir_fd=current)
        finally:
            os.close(current)
    except OSError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification source layout is unavailable",
        ) from error
    try:
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
                raise NativeVerificationError(
                    "operation_failed",
                    "native verification source file is unsupported",
                )
            chunks: list[bytes] = []
            retained = 0
            while True:
                chunk = os.read(
                    descriptor,
                    min(65_536, limit + 1 - retained),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                retained += len(chunk)
                if retained > limit:
                    raise NativeVerificationError(
                        "operation_failed",
                        "native verification source file exceeds the byte limit",
                    )
            return b"".join(chunks)
        except OSError as error:
            raise NativeVerificationError(
                "operation_failed",
                "native verification source file cannot be read",
            ) from error
    finally:
        os.close(descriptor)


def _interpreter(
    limits: NativeVerificationLimits,
) -> tuple[Path, int, str]:
    if sys.implementation.name != "cpython" or sys.platform != "linux":
        raise NativeVerificationError(
            "operation_failed",
            "native verification runtime is unsupported",
        )
    requested = Path(sys.executable)
    try:
        interpreter = requested.resolve(strict=True)
        metadata = interpreter.stat()
    except OSError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification interpreter is unavailable",
        ) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size > limits.max_interpreter_bytes
    ):
        raise NativeVerificationError(
            "operation_failed",
            "native verification interpreter is unsupported",
        )
    digest = hashlib.sha256()
    size = 0
    try:
        with interpreter.open("rb") as stream:
            while chunk := stream.read(65_536):
                size += len(chunk)
                if size > limits.max_interpreter_bytes:
                    raise NativeVerificationError(
                        "operation_failed",
                        "native verification interpreter exceeds the byte limit",
                    )
                digest.update(chunk)
    except OSError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification interpreter cannot be read",
        ) from error
    if size != metadata.st_size:
        raise NativeVerificationError(
            "operation_failed",
            "native verification interpreter changed while reading",
        )
    return interpreter, size, digest.hexdigest()


def _root_directory(root_path: str | Path) -> Path:
    requested = Path(root_path)
    absolute = Path(os.path.abspath(requested))
    try:
        resolved = requested.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise NativeVerificationError(
            "operation_failed",
            "native verification root is unavailable",
        ) from error
    if absolute != resolved or not stat.S_ISDIR(metadata.st_mode):
        raise NativeVerificationError(
            "operation_failed",
            "native verification root must not contain symlinks",
        )
    return resolved


def _inventory(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise NativeVerificationError(
            "operation_failed",
            "native verification inventory is invalid",
        )
    if (
        value.get("kind") != "inventory_snapshot"
        or value.get("inventory_version") != VERSION
        or type(value.get("subject_uri")) is not str
        or not _valid_digest(value.get("source_revision"))
    ):
        raise NativeVerificationError(
            "operation_failed",
            "native verification inventory coordinates are incompatible",
        )
    return value


def _digest(value: str) -> dict[str, object]:
    return {"kind": "digest", "algorithm": "sha-256", "value": value}


def _valid_digest(value: object) -> bool:
    return (
        type(value) is dict
        and set(value) == {"kind", "algorithm", "value"}
        and value["kind"] == "digest"
        and value["algorithm"] == "sha-256"
        and type(value["value"]) is str
        and len(value["value"]) == 64
        and all(character in "0123456789abcdef" for character in value["value"])
    )
