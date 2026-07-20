from __future__ import annotations

import math
import os
import selectors
import signal
import subprocess
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ucf.adapter_conformance.models import (
    CaseStatus,
    ConformanceCase,
    ConformanceCaseResult,
    ConformanceExitCode,
    ConformanceManifest,
    ConformanceReport,
    ExpectStep,
    RunStatus,
    SendStep,
    validate_report_against_manifest,
)
from ucf.adapter_conformance.resources import (
    load_conformance_fixture,
    load_conformance_manifest,
)
from ucf.adapter_protocol import (
    AdapterProtocolError,
    ErrorResponse,
    InitializeResult,
    OperationResult,
    ProtocolCode,
    ShutdownResult,
    SuccessResponse,
    decode_response_frame,
)
from ucf.adapter_protocol.models import (
    MAX_FRAME_BYTES,
    MAX_RETAINED_STDERR_BYTES,
)

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


@dataclass(frozen=True)
class ConformanceTimeouts:
    response: float = 5.0
    write: float = 5.0
    shutdown: float = 2.0
    terminate: float = 1.0
    kill: float = 1.0

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            _validate_timeout(value, name=name)


class _NonConformance(RuntimeError):
    def __init__(
        self,
        actual: str,
        protocol_code: ProtocolCode | None = None,
    ) -> None:
        self.actual = actual
        self.protocol_code = protocol_code
        super().__init__(actual)


class _RunnerFailure(RuntimeError):
    def __init__(self, actual: str) -> None:
        self.actual = actual
        super().__init__(actual)


class _RawAdapterSession:
    def __init__(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
        timeouts: ConformanceTimeouts,
    ) -> None:
        kwargs: dict[str, object] = {}
        if os.name == "posix":
            kwargs["start_new_session"] = True
        try:
            self._process = subprocess.Popen(
                command,
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                **kwargs,
            )
        except (OSError, ValueError) as error:
            raise _RunnerFailure("runner_start_failed") from error
        if (
            self._process.stdin is None
            or self._process.stdout is None
            or self._process.stderr is None
        ):
            self._terminate_failed_start()
            raise _RunnerFailure("runner_start_failed")
        self._stdin = self._process.stdin
        self._stdout = self._process.stdout
        self._stderr = self._process.stderr
        os.set_blocking(self._stdin.fileno(), False)
        os.set_blocking(self._stdout.fileno(), False)
        os.set_blocking(self._stderr.fileno(), False)
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._stdout, selectors.EVENT_READ, "stdout")
        self._selector.register(self._stderr, selectors.EVENT_READ, "stderr")
        self._stdout_buffer = bytearray()
        self._stderr_tail = bytearray()
        self._stdout_eof = False
        self._stderr_eof = False
        self._timeouts = timeouts
        self._finished = False

    def send(self, frame: str) -> None:
        payload = frame.encode("utf-8") + b"\n"
        deadline = time.monotonic() + self._timeouts.write
        offset = 0
        self._selector.register(
            self._stdin,
            selectors.EVENT_WRITE,
            "stdin",
        )
        try:
            while offset < len(payload):
                if self._process.poll() is not None:
                    raise _NonConformance(
                        "process_exited",
                        ProtocolCode.PROCESS_EXITED,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _NonConformance(
                        "write_timeout",
                        ProtocolCode.WRITE_TIMEOUT,
                    )
                events = self._selector.select(remaining)
                if not events:
                    raise _NonConformance(
                        "write_timeout",
                        ProtocolCode.WRITE_TIMEOUT,
                    )
                for key, _ in events:
                    if key.data != "stdin":
                        self._read_ready_stream(key.data)
                        continue
                    try:
                        written = os.write(
                            self._stdin.fileno(),
                            payload[offset:],
                        )
                    except BlockingIOError:
                        continue
                    except (
                        BrokenPipeError,
                        ConnectionError,
                        OSError,
                    ) as error:
                        raise _NonConformance(
                            "process_exited",
                            ProtocolCode.PROCESS_EXITED,
                        ) from error
                    offset += written
        finally:
            self._unregister(self._stdin)

    def receive(self):
        deadline = time.monotonic() + self._timeouts.response
        while True:
            newline = self._stdout_buffer.find(b"\n")
            if newline >= 0:
                frame = bytes(self._stdout_buffer[: newline + 1])
                del self._stdout_buffer[: newline + 1]
                try:
                    return decode_response_frame(frame)
                except AdapterProtocolError as error:
                    protocol_code = (
                        error.code
                        if error.code is ProtocolCode.FRAME_TOO_LARGE
                        else ProtocolCode.INVALID_ADAPTER_OUTPUT
                    )
                    raise _NonConformance(
                        "invalid_adapter_output",
                        protocol_code,
                    ) from error
            if len(self._stdout_buffer) > MAX_FRAME_BYTES:
                raise _NonConformance(
                    "invalid_adapter_output",
                    ProtocolCode.FRAME_TOO_LARGE,
                )
            if self._stdout_eof:
                code = (
                    ProtocolCode.TRUNCATED_FRAME
                    if self._stdout_buffer
                    else ProtocolCode.PROCESS_EXITED
                )
                raise _NonConformance("process_exited", code)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _NonConformance("response_timeout")
            events = self._selector.select(remaining)
            if not events:
                raise _NonConformance("response_timeout")
            for key, _ in events:
                self._read_ready_stream(key.data)

    def finish_cleanly(self) -> None:
        self._close_stdin()
        try:
            returncode = self._wait_for_exit_while_draining()
        except subprocess.TimeoutExpired as error:
            self.terminate()
            raise _NonConformance(
                "shutdown_timeout",
                ProtocolCode.SHUTDOWN_TIMEOUT,
            ) from error
        if os.name == "posix" and self._group_exists():
            self.terminate()
            raise _NonConformance(
                "process_group_survived",
                ProtocolCode.PROCESS_EXITED,
            )
        self._drain_after_exit()
        if returncode != 0:
            self._finish_handles()
            self._finished = True
            raise _NonConformance(
                "process_exited",
                ProtocolCode.PROCESS_EXITED,
            )
        if self._stdout_buffer:
            self._finish_handles()
            self._finished = True
            raise _NonConformance(
                "unexpected_response",
                ProtocolCode.CORRELATION_FAILURE,
            )
        self._finish_handles()
        self._finished = True

    def _wait_for_exit_while_draining(self) -> int:
        deadline = time.monotonic() + self._timeouts.shutdown
        while True:
            returncode = self._process.poll()
            if returncode is not None:
                return returncode
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(
                    self._process.args,
                    self._timeouts.shutdown,
                )
            events = self._selector.select(min(remaining, 0.05))
            for key, _ in events:
                self._read_ready_stream(key.data)

    def terminate(self) -> None:
        if self._finished:
            return
        self._close_stdin()
        process = self._process
        if os.name == "posix":
            self._signal_group(signal.SIGTERM)
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=self._timeouts.terminate)
        except subprocess.TimeoutExpired:
            pass
        if os.name == "posix" and self._group_exists():
            self._signal_group(signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
        if process.poll() is None:
            try:
                process.wait(timeout=self._timeouts.kill)
            except subprocess.TimeoutExpired as error:
                self._finish_handles()
                self._finished = True
                raise _RunnerFailure("runner_cleanup_failed") from error
        if os.name == "posix":
            deadline = time.monotonic() + self._timeouts.kill
            while self._group_exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            if self._group_exists():
                self._finish_handles()
                self._finished = True
                raise _RunnerFailure("runner_cleanup_failed")
        self._finish_handles()
        self._finished = True

    def _read_ready_stream(self, stream: str) -> None:
        file = self._stdout if stream == "stdout" else self._stderr
        try:
            chunk = os.read(file.fileno(), 65_536)
        except BlockingIOError:
            return
        except OSError as error:
            raise _RunnerFailure("runner_io_failed") from error
        if stream == "stdout":
            if chunk:
                self._stdout_buffer.extend(chunk)
                if len(self._stdout_buffer) > MAX_FRAME_BYTES:
                    raise _NonConformance(
                        "invalid_adapter_output",
                        ProtocolCode.FRAME_TOO_LARGE,
                    )
            else:
                self._stdout_eof = True
                self._unregister(file)
            return
        if chunk:
            self._stderr_tail.extend(chunk)
            overflow = len(self._stderr_tail) - MAX_RETAINED_STDERR_BYTES
            if overflow > 0:
                del self._stderr_tail[:overflow]
        else:
            self._stderr_eof = True
            self._unregister(file)

    def _drain_after_exit(self) -> None:
        deadline = time.monotonic() + self._timeouts.kill
        while (
            (not self._stdout_eof or not self._stderr_eof)
            and time.monotonic() < deadline
        ):
            events = self._selector.select(0)
            if not events:
                for stream, file in (
                    ("stdout", self._stdout),
                    ("stderr", self._stderr),
                ):
                    if (
                        stream == "stdout"
                        and self._stdout_eof
                        or stream == "stderr"
                        and self._stderr_eof
                    ):
                        continue
                    self._read_ready_stream(stream)
                continue
            for key, _ in events:
                self._read_ready_stream(key.data)

    def _close_stdin(self) -> None:
        if not self._stdin.closed:
            self._stdin.close()

    def _unregister(self, file) -> None:
        try:
            self._selector.unregister(file)
        except KeyError:
            pass

    def _group_exists(self) -> bool:
        if os.name != "posix":
            return False
        try:
            os.killpg(self._process.pid, 0)
        except ProcessLookupError:
            return False
        return True

    def _signal_group(self, sig: signal.Signals) -> None:
        try:
            os.killpg(self._process.pid, sig)
        except ProcessLookupError:
            pass

    def _finish_handles(self) -> None:
        self._selector.close()
        for file in (self._stdin, self._stdout, self._stderr):
            if not file.closed:
                file.close()

    def _terminate_failed_start(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait()


def run_conformance(
    *,
    command: tuple[str, ...],
    cwd: Path,
    timeouts: ConformanceTimeouts | None = None,
    environment: Mapping[str, str] | None = None,
    manifest: ConformanceManifest | None = None,
) -> ConformanceReport:
    _validate_command(command)
    resolved_cwd = _validate_cwd(cwd)
    explicit_environment = _validate_environment(environment)
    selected_manifest = manifest or load_conformance_manifest()
    selected_timeouts = timeouts or ConformanceTimeouts()
    child_environment = _minimal_environment(explicit_environment)
    results: list[ConformanceCaseResult] = []
    runner_failed = False

    for case in selected_manifest.cases:
        if runner_failed:
            results.append(
                _case_result(
                    case,
                    status=CaseStatus.ERROR,
                    actual="runner_not_run",
                )
            )
            continue
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"ucf-conformance-{case.case_id}-"
            ) as temporary:
                case_directory = Path(temporary)
                case_environment = {
                    **child_environment,
                    "HOME": str(case_directory),
                    "TMPDIR": str(case_directory),
                    "TEMP": str(case_directory),
                    "TMP": str(case_directory),
                }
                _run_case(
                    case=case,
                    command=command,
                    cwd=resolved_cwd,
                    environment=case_environment,
                    timeouts=selected_timeouts,
                )
        except _NonConformance as error:
            results.append(
                _case_result(
                    case,
                    status=CaseStatus.FAILED,
                    actual=error.actual,
                    protocol_code=error.protocol_code,
                )
            )
        except _RunnerFailure as error:
            results.append(
                _case_result(
                    case,
                    status=CaseStatus.ERROR,
                    actual=error.actual,
                )
            )
            runner_failed = True
        else:
            results.append(
                _case_result(
                    case,
                    status=CaseStatus.PASSED,
                    actual="fixture_match",
                )
            )

    statuses = {item.status for item in results}
    if CaseStatus.ERROR in statuses:
        status = RunStatus.RUNNER_ERROR
    elif CaseStatus.FAILED in statuses:
        status = RunStatus.NON_CONFORMANT
    else:
        status = RunStatus.CONFORMANT
    report = ConformanceReport(
        kind="adapter_conformance_report",
        kit_version=selected_manifest.kit_version,
        protocol_version=selected_manifest.protocol_version,
        profile=selected_manifest.profile,
        status=status,
        cases=tuple(results),
    )
    validate_report_against_manifest(report, selected_manifest)
    return report


def exit_code_for_report(report: ConformanceReport) -> ConformanceExitCode:
    return {
        RunStatus.CONFORMANT: ConformanceExitCode.CONFORMANT,
        RunStatus.NON_CONFORMANT: ConformanceExitCode.NON_CONFORMANT,
        RunStatus.RUNNER_ERROR: ConformanceExitCode.RUNNER_ERROR,
    }[report.status]


def _run_case(
    *,
    case: ConformanceCase,
    command: tuple[str, ...],
    cwd: Path,
    environment: Mapping[str, str],
    timeouts: ConformanceTimeouts,
) -> None:
    fixture = load_conformance_fixture(case.fixture)
    if (
        fixture.case_id != case.case_id
        or fixture.procedure is not case.procedure
    ):
        raise _RunnerFailure("runner_fixture_mismatch")
    session = _RawAdapterSession(
        command=command,
        cwd=cwd,
        environment=environment,
        timeouts=timeouts,
    )
    clean_shutdown = False
    failure: BaseException | None = None
    try:
        for step in fixture.steps:
            if isinstance(step, SendStep):
                session.send(step.frame)
                continue
            response = session.receive()
            _validate_response(response, step)
            if (
                step.outcome == "success"
                and step.result_kind == "shutdown_result"
            ):
                clean_shutdown = True
        if clean_shutdown:
            session.finish_cleanly()
        else:
            session.terminate()
    except (_NonConformance, _RunnerFailure) as error:
        failure = error
    finally:
        if not session._finished:
            try:
                session.terminate()
            except _RunnerFailure as cleanup_error:
                failure = cleanup_error
    if failure is not None:
        raise failure


def _validate_response(response, expected: ExpectStep) -> None:
    if response.id != expected.request_id:
        raise _NonConformance(
            "unexpected_response",
            ProtocolCode.CORRELATION_FAILURE,
        )
    if expected.outcome == "error":
        if not isinstance(response, ErrorResponse):
            raise _NonConformance("unexpected_response")
        if (
            response.error.code != expected.jsonrpc_code
            or response.error.data.category is not expected.error_category
            or response.error.data.ucf_code is not expected.protocol_code
        ):
            raise _NonConformance("unexpected_response")
        return
    if not isinstance(response, SuccessResponse):
        raise _NonConformance("unexpected_response")
    result = response.result
    result_kind = result.kind.value if hasattr(result.kind, "value") else result.kind
    if result_kind != expected.result_kind:
        raise _NonConformance("unexpected_response")
    if isinstance(result, InitializeResult):
        selected = tuple(item.name for item in result.capabilities)
        if selected != expected.selected_capabilities:
            raise _NonConformance("unexpected_response")
        return
    if isinstance(result, OperationResult):
        if result.payload != expected.expected_payload:
            raise _NonConformance("unexpected_response")
        return
    if not isinstance(result, ShutdownResult):
        raise _NonConformance("unexpected_response")


def _case_result(
    case: ConformanceCase,
    *,
    status: CaseStatus,
    actual: str,
    protocol_code: ProtocolCode | None = None,
) -> ConformanceCaseResult:
    return ConformanceCaseResult(
        kind="conformance_case_result",
        case_id=case.case_id,
        status=status,
        expected="fixture_match",
        actual=actual,
        protocol_code=protocol_code,
    )


def _validate_command(command: tuple[str, ...]) -> None:
    if (
        not isinstance(command, tuple)
        or not command
        or any(
            not isinstance(item, str) or not item or "\0" in item
            for item in command
        )
    ):
        raise ValueError("adapter command must be a nonempty argv tuple")


def _validate_cwd(cwd: Path) -> Path:
    if not isinstance(cwd, Path):
        raise ValueError("adapter cwd must be a pathlib.Path")
    resolved = cwd.resolve()
    if not resolved.is_dir():
        raise ValueError("adapter cwd must be an existing directory")
    return resolved


def _validate_environment(
    environment: Mapping[str, str] | None,
) -> dict[str, str]:
    selected = dict(environment or {})
    if any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or not key
        or "=" in key
        or "\0" in key
        or "\0" in value
        for key, value in selected.items()
    ):
        raise ValueError("adapter environment contains an invalid entry")
    return selected


def _minimal_environment(explicit: Mapping[str, str]) -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in _MINIMAL_ENV_ALLOWLIST
        if key in os.environ
    }
    environment.update(explicit)
    return environment


def _validate_timeout(value: float, *, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} timeout must be a finite positive number")
