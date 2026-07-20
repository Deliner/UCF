from __future__ import annotations

import asyncio
import hashlib
import os
import stat
from dataclasses import dataclass
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
from ucf.ir.models import BehaviorIR, Digest
from ucf.runtime_evidence.errors import (
    RuntimeEvidenceClientError,
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceValidationError,
)
from ucf.runtime_evidence.models import (
    RUNTIME_EVIDENCE_CAPABILITY,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEnvironment,
    RuntimeEvidenceImportRequest,
    RuntimeEvidenceResult,
)
from ucf.runtime_evidence.validation import (
    validate_runtime_evidence_request,
    validate_runtime_evidence_result,
)
from ucf.runtime_evidence.wire import (
    runtime_evidence_request_to_payload,
    runtime_evidence_result_from_payload,
)

VERIFICATION_CAPABILITY = "org.ucf.adapter.verification"
MAX_RUNTIME_RECORDING_BYTES = 16_777_216


@dataclass(frozen=True)
class _RecordingFingerprint:
    device: int
    inode: int
    size: int
    modified_ns: int
    digest: Digest


def runtime_recording_digest(path: Path) -> Digest:
    """Hash one bounded non-symlink recording without retaining its bytes."""
    return _fingerprint_recording(path).digest


async def import_runtime_evidence(
    *,
    command: tuple[str, ...],
    cwd: Path,
    recording_path: Path,
    request: RuntimeEvidenceImportRequest,
    behavior: BehaviorIR,
    environment: RuntimeEnvironment,
    timeouts: ProcessTimeouts | None = None,
    operation_timeout: float | None = None,
) -> RuntimeEvidenceResult:
    validate_runtime_evidence_request(
        request,
        behavior=behavior,
        environment=environment,
    )
    initial_source = _fingerprint_recording(recording_path)
    if initial_source.digest != request.source.source_revision:
        raise RuntimeEvidenceValidationError(
            RuntimeEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "runtime recording differs from request source revision",
            location="$.source.source_revision",
        )
    payload = runtime_evidence_request_to_payload(request)
    _preflight_request(payload)
    adapter = AdapterProcess(
        command=command,
        cwd=cwd,
        requested_capabilities=(
            CapabilityRequest(
                kind="capability_request",
                name=VERIFICATION_CAPABILITY,
                minimum_version=RUNTIME_EVIDENCE_VERSION,
                required=True,
            ),
            CapabilityRequest(
                kind="capability_request",
                name=RUNTIME_EVIDENCE_CAPABILITY,
                minimum_version=RUNTIME_EVIDENCE_VERSION,
                required=True,
            ),
        ),
        timeouts=timeouts,
        retain_stderr_tail=False,
    )
    result: RuntimeEvidenceResult | None = None
    operation_failure: tuple[ErrorCategory, ProtocolCode] | None = None
    cleanup_failure: tuple[ErrorCategory, ProtocolCode] | None = None
    cancelled = False
    try:
        initialized = await adapter.start()
        raw_result = await adapter.call(
            Method.VERIFY,
            payload,
            timeout=operation_timeout,
        )
        try:
            result = runtime_evidence_result_from_payload(raw_result)
            validate_runtime_evidence_result(
                result,
                request=request,
                behavior=behavior,
                environment=environment,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
                source_revision=initial_source.digest,
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

    source_changed = False
    try:
        source_changed = _fingerprint_recording(
            recording_path
        ) != initial_source
    except (OSError, ValueError):
        source_changed = True

    failure = cleanup_failure
    if failure is None and adapter.stderr_total_bytes:
        failure = (
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
        )
    if failure is None and source_changed:
        failure = (
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
        )
    if failure is None:
        failure = operation_failure
    if failure is not None:
        raise RuntimeEvidenceClientError(*failure)
    assert result is not None
    return result


def _preflight_request(payload) -> None:
    encode_frame(
        Request(
            jsonrpc="2.0",
            id="x" * 64,
            method=Method.VERIFY,
            params=OperationParams(
                kind=OperationKind.VERIFY_REQUEST,
                payload=payload,
            ),
        )
    )


def _fingerprint_recording(path: Path) -> _RecordingFingerprint:
    if not isinstance(path, Path):
        raise ValueError("runtime recording path must be a pathlib.Path")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(
            "runtime recording must be a non-symlink regular file"
        )
    if before.st_size > MAX_RUNTIME_RECORDING_BYTES:
        raise ValueError("runtime recording exceeds the supported byte limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise ValueError("runtime recording identity changed before read")
        digest = hashlib.sha256()
        total = 0
        while True:
            remaining = MAX_RUNTIME_RECORDING_BYTES - total
            chunk = os.read(descriptor, min(65_536, remaining + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RUNTIME_RECORDING_BYTES:
                raise ValueError(
                    "runtime recording exceeds the supported byte limit"
                )
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        opened.st_size,
        opened.st_mtime_ns,
        opened.st_dev,
        opened.st_ino,
    ) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_dev,
        after.st_ino,
    ):
        raise ValueError("runtime recording changed while hashing")
    return _RecordingFingerprint(
        device=after.st_dev,
        inode=after.st_ino,
        size=after.st_size,
        modified_ns=after.st_mtime_ns,
        digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=digest.hexdigest(),
        ),
    )
