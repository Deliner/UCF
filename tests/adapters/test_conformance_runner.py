from __future__ import annotations

import math
import os
import shutil
import signal
import sys
import time
from pathlib import Path

import pytest

from ucf.adapter_conformance import (
    CaseStatus,
    ConformanceExitCode,
    ConformanceTimeouts,
    RunStatus,
    canonical_conformance_json,
    conformance_assets,
    exit_code_for_report,
    load_conformance_manifest,
    run_conformance,
    validate_report_against_manifest,
)
from ucf.adapter_conformance.runner import _RawAdapterSession
from ucf.adapter_protocol import MAX_FRAME_BYTES, ProtocolCode

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_FAULT_ADAPTER = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "adapters" / "fault_adapter.py"
)
PYTHON_REFERENCE_ADAPTER = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "reference_adapter.py"
)
_CLEAN_SHUTDOWN_CHILD = r"""
import json
import os
import subprocess
import sys

if "UCF_AMBIENT_SECRET" in os.environ:
    raise SystemExit(17)
initialize = json.loads(sys.stdin.readline())
mode = os.environ["UCF_RUNNER_REGRESSION_MODE"]
if (
    any(
        name in os.environ
        for name in ("PYTHONDONTWRITEBYTECODE", "PYTHONUTF8")
    )
    and mode != "explicit_language_runtime"
):
    raise SystemExit(18)
if mode == "receive_stderr":
    sys.stderr.write("x" * 2_000_000)
    sys.stderr.flush()
print(json.dumps({
    "jsonrpc": "2.0",
    "id": initialize["id"],
    "result": {
        "kind": "initialize_result",
        "protocol_version": "1.0.0",
        "adapter": {
            "kind": "producer",
            "name": "org.ucf.runner-regression",
            "version": "1.0.0",
        },
        "capabilities": [],
    },
}), flush=True)
shutdown = json.loads(sys.stdin.readline())
print(json.dumps({
    "jsonrpc": "2.0",
    "id": shutdown["id"],
    "result": {"kind": "shutdown_result"},
}), flush=True)
if mode == "stderr":
    sys.stderr.write("x" * 2_000_000)
    sys.stderr.flush()
elif mode == "descendant":
    descendant = subprocess.Popen(
        (
            sys.executable,
            "-c",
            "import signal,time;"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
            "time.sleep(30)",
        ),
        stdin=subprocess.DEVNULL,
    )
    with open(
        os.environ["UCF_DESCENDANT_PID_FILE"],
        "w",
        encoding="utf-8",
    ) as output:
        output.write(str(descendant.pid))
"""
_STATEFUL_WRAPPER = r"""
import os
import sys
from pathlib import Path

marker = Path(os.environ["TMPDIR"]) / ".conformance-case-marker"
if marker.exists():
    raise SystemExit(17)
marker.write_text("case-local", encoding="utf-8")
node = os.environ["UCF_NODE"]
sample = os.environ["UCF_SAMPLE"]
os.execv(node, (node, sample, *sys.argv[1:]))
"""
_OVERSIZED_OUTPUT_CHILD = r"""
import os
import sys

sys.stdin.readline()
payload = b"x" * ({frame_bytes} + 1)
if os.environ["UCF_OVERSIZED_TERMINATED"] == "true":
    payload += b"\n"
sys.stdout.buffer.write(payload)
sys.stdout.buffer.flush()
"""
_WRITE_PHASE_STDERR_CHILD = r"""
import sys
import time

sys.stderr.buffer.write(b"x" * 2_000_000)
sys.stderr.buffer.flush()
sys.stdin.buffer.readline()
time.sleep(30)
"""


def _node_command(name: str, *arguments: str) -> tuple[str, ...]:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node is required by the adapter conformance contract")
    logical_name = name if "/" in name else f"samples/{name}"
    sample = conformance_assets()
    for segment in logical_name.split("/"):
        sample = sample.joinpath(segment)
    assert sample.is_file()
    return (node, str(sample), *arguments)


def _timeouts(response: float = 1.0) -> ConformanceTimeouts:
    return ConformanceTimeouts(
        response=response,
        write=1.0,
        shutdown=1.0,
        terminate=0.5,
        kill=0.5,
    )


def _single_case_manifest():
    manifest = load_conformance_manifest()
    return manifest.model_copy(
        update={
            "cases": (manifest.cases[0],),
            "fault_profiles": (),
        }
    )


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_dependency_free_sample_passes_the_same_manifest_reproducibly(
    tmp_path: Path,
):
    manifest = load_conformance_manifest()
    command = _node_command("reference_adapter.mjs")

    first = run_conformance(
        command=command,
        cwd=tmp_path,
        timeouts=_timeouts(),
    )
    second = run_conformance(
        command=command,
        cwd=tmp_path,
        timeouts=_timeouts(),
    )

    validate_report_against_manifest(first, manifest)
    assert first.status is RunStatus.CONFORMANT
    assert all(case.status is CaseStatus.PASSED for case in first.cases)
    assert exit_code_for_report(first) is ConformanceExitCode.CONFORMANT
    assert canonical_conformance_json(first) == canonical_conformance_json(
        second
    )
    report = canonical_conformance_json(first)
    assert str(tmp_path).encode() not in report
    assert command[0].encode() not in report
    assert b"duration" not in report
    assert b"stderr" not in report


def test_existing_python_reference_process_passes_the_same_manifest(
    tmp_path: Path,
):
    report = run_conformance(
        command=(sys.executable, str(PYTHON_REFERENCE_ADAPTER)),
        cwd=tmp_path,
        timeouts=_timeouts(),
    )

    assert report.status is RunStatus.CONFORMANT
    assert all(case.status is CaseStatus.PASSED for case in report.cases)


@pytest.mark.parametrize(
    "fault_profile",
    load_conformance_manifest().fault_profiles,
    ids=lambda profile: profile.fault_id,
)
def test_each_fault_profile_fails_only_its_named_case(
    tmp_path: Path,
    fault_profile,
):
    manifest = load_conformance_manifest()
    report = run_conformance(
        command=_node_command(
            manifest.fault_adapter,
            *fault_profile.arguments,
        ),
        cwd=tmp_path,
        timeouts=_timeouts(response=0.05),
    )
    failed = {
        case.case_id
        for case in report.cases
        if case.status is CaseStatus.FAILED
    }

    assert report.status is RunStatus.NON_CONFORMANT
    assert failed == {fault_profile.expected_case_id}
    assert all(case.status is not CaseStatus.ERROR for case in report.cases)
    assert exit_code_for_report(report) is ConformanceExitCode.NON_CONFORMANT


def test_start_failure_is_a_deterministic_runner_error(tmp_path: Path):
    report = run_conformance(
        command=("ucf-conformance-command-that-does-not-exist",),
        cwd=tmp_path,
        timeouts=_timeouts(),
    )

    assert report.status is RunStatus.RUNNER_ERROR
    assert report.cases[0].status is CaseStatus.ERROR
    assert report.cases[0].actual == "runner_start_failed"
    assert all(
        case.actual in {"runner_start_failed", "runner_not_run"}
        for case in report.cases
    )
    assert exit_code_for_report(report) is ConformanceExitCode.RUNNER_ERROR


def test_response_timeout_is_nonconformance_and_teardown_is_bounded():
    started = time.monotonic()
    report = run_conformance(
        command=(
            sys.executable,
            str(PYTHON_FAULT_ADAPTER),
            "block-before-initialize-response",
        ),
        cwd=REPOSITORY_ROOT,
        timeouts=_timeouts(response=0.05),
    )
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    assert report.status is RunStatus.NON_CONFORMANT
    assert report.cases[0].status is CaseStatus.FAILED
    assert report.cases[0].actual == "response_timeout"
    assert all(case.status is not CaseStatus.ERROR for case in report.cases)


def test_clean_shutdown_drains_large_stderr_without_false_timeout(
    tmp_path: Path,
):
    report = run_conformance(
        command=(sys.executable, "-c", _CLEAN_SHUTDOWN_CHILD),
        cwd=tmp_path,
        environment={"UCF_RUNNER_REGRESSION_MODE": "stderr"},
        manifest=_single_case_manifest(),
        timeouts=_timeouts(response=0.5),
    )

    assert report.status is RunStatus.CONFORMANT


def test_receive_phase_drains_stderr_before_valid_response(
    tmp_path: Path,
):
    started = time.monotonic()
    report = run_conformance(
        command=(sys.executable, "-c", _CLEAN_SHUTDOWN_CHILD),
        cwd=tmp_path,
        environment={"UCF_RUNNER_REGRESSION_MODE": "receive_stderr"},
        manifest=_single_case_manifest(),
        timeouts=_timeouts(response=2.0),
    )
    elapsed = time.monotonic() - started

    assert elapsed < 4.0
    assert report.status is RunStatus.CONFORMANT


def test_candidate_does_not_inherit_undeclared_ambient_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("UCF_AMBIENT_SECRET", "must-not-cross")
    report = run_conformance(
        command=(sys.executable, "-c", _CLEAN_SHUTDOWN_CHILD),
        cwd=tmp_path,
        environment={"UCF_RUNNER_REGRESSION_MODE": "clean"},
        manifest=_single_case_manifest(),
        timeouts=_timeouts(response=0.5),
    )

    assert report.status is RunStatus.CONFORMANT


def test_candidate_receives_explicit_language_runtime_environment(
    tmp_path: Path,
):
    report = run_conformance(
        command=(sys.executable, "-c", _CLEAN_SHUTDOWN_CHILD),
        cwd=tmp_path,
        environment={
            "PYTHONUTF8": "1",
            "UCF_RUNNER_REGRESSION_MODE": "explicit_language_runtime",
        },
        manifest=_single_case_manifest(),
        timeouts=_timeouts(response=0.5),
    )

    assert report.status is RunStatus.CONFORMANT


def test_write_phase_drains_stderr_while_peer_waits_to_read(tmp_path: Path):
    session = _RawAdapterSession(
        command=(sys.executable, "-c", _WRITE_PHASE_STDERR_CHILD),
        cwd=tmp_path,
        environment={},
        timeouts=_timeouts(response=0.5),
    )
    try:
        session.send("x" * (MAX_FRAME_BYTES - 1))
        assert len(session._stderr_tail) == 65_536
    finally:
        session.terminate()


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_clean_shutdown_reaps_inherited_descendant_and_rejects_leak(
    tmp_path: Path,
):
    pid_file = tmp_path / "descendant.pid"
    report = run_conformance(
        command=(sys.executable, "-c", _CLEAN_SHUTDOWN_CHILD),
        cwd=tmp_path,
        environment={
            "UCF_RUNNER_REGRESSION_MODE": "descendant",
            "UCF_DESCENDANT_PID_FILE": str(pid_file),
        },
        manifest=_single_case_manifest(),
        timeouts=_timeouts(response=0.5),
    )

    descendant_pid = int(pid_file.read_text(encoding="utf-8"))
    try:
        assert report.status is RunStatus.NON_CONFORMANT
        assert report.cases[0].actual == "process_group_survived"
        assert not _pid_exists(descendant_pid)
    finally:
        if _pid_exists(descendant_pid):
            os.kill(descendant_pid, signal.SIGKILL)


def test_each_case_uses_fresh_writable_scratch_directory(tmp_path: Path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node is required by the adapter conformance contract")
    sample = conformance_assets().joinpath(
        "samples",
        "reference_adapter.mjs",
    )
    environment = {
        "UCF_NODE": node,
        "UCF_SAMPLE": str(sample),
    }
    command = (sys.executable, "-c", _STATEFUL_WRAPPER)

    first = run_conformance(
        command=command,
        cwd=tmp_path,
        environment=environment,
        timeouts=_timeouts(),
    )
    second = run_conformance(
        command=command,
        cwd=tmp_path,
        environment=environment,
        timeouts=_timeouts(),
    )

    assert first.status is second.status is RunStatus.CONFORMANT
    assert canonical_conformance_json(first) == canonical_conformance_json(
        second
    )
    assert not (tmp_path / ".conformance-case-marker").exists()


def test_relative_adapter_script_is_resolved_from_declared_cwd(
    tmp_path: Path,
):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node is required by the adapter conformance contract")
    sample = conformance_assets().joinpath(
        "samples",
        "reference_adapter.mjs",
    )
    script = tmp_path / "adapter.py"
    script.write_text(
        "import os,sys\n"
        "node=os.environ['UCF_NODE']\n"
        "sample=os.environ['UCF_SAMPLE']\n"
        "os.execv(node,(node,sample,*sys.argv[1:]))\n",
        encoding="utf-8",
    )

    report = run_conformance(
        command=(sys.executable, "adapter.py"),
        cwd=tmp_path,
        environment={
            "UCF_NODE": node,
            "UCF_SAMPLE": str(sample),
        },
        timeouts=_timeouts(),
    )

    assert report.status is RunStatus.CONFORMANT


@pytest.mark.parametrize("terminated", [False, True])
def test_oversized_output_has_one_stable_protocol_coordinate(
    tmp_path: Path,
    terminated: bool,
):
    report = run_conformance(
        command=(
            sys.executable,
            "-c",
            _OVERSIZED_OUTPUT_CHILD.format(frame_bytes=MAX_FRAME_BYTES),
        ),
        cwd=tmp_path,
        environment={
            "UCF_OVERSIZED_TERMINATED": str(terminated).lower(),
        },
        manifest=_single_case_manifest(),
        timeouts=_timeouts(response=0.5),
    )

    assert report.status is RunStatus.NON_CONFORMANT
    assert report.cases[0].actual == "invalid_adapter_output"
    assert report.cases[0].protocol_code is ProtocolCode.FRAME_TOO_LARGE


@pytest.mark.parametrize("value", [0, -1, math.inf, math.nan, True])
def test_runner_rejects_invalid_timeouts_before_start(value: float):
    with pytest.raises(ValueError, match="finite positive"):
        ConformanceTimeouts(response=value)


@pytest.mark.parametrize(
    "command",
    [
        (),
        ("",),
        ("node", ""),
        ("node", "bad\0argument"),
    ],
)
def test_runner_rejects_invalid_argv_before_start(
    tmp_path: Path,
    command: tuple[str, ...],
):
    with pytest.raises(ValueError, match="argv"):
        run_conformance(
            command=command,
            cwd=tmp_path,
            timeouts=_timeouts(),
        )
