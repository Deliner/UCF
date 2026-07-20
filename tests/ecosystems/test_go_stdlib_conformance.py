from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GO_STDLIB_ADAPTER_INPUTS,
    SourceContractError,
    go_stdlib_adapter_manifest,
)
from tools.go_stdlib_toolchain import resolve_go_stdlib_binary

from ucf.adapter_conformance import (
    CaseStatus,
    ConformanceTimeouts,
    RunStatus,
    canonical_conformance_json,
    run_conformance,
)
from ucf.adapter_protocol import MAX_FRAME_BYTES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_SOURCE_ROOT = PROJECT_ROOT / "adapters" / "go-stdlib"
EXPECTED_CONFORMANCE_SHA256 = (
    "fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384"
)


def test_go_stdlib_adapter_passes_public_conformance_reproducibly(
    tmp_path: Path,
) -> None:
    source_before = go_stdlib_adapter_manifest(ADAPTER_SOURCE_ROOT)
    assert {entry[0] for entry in source_before} == (
        GO_STDLIB_ADAPTER_INPUTS
    )
    adapter_entry = _build_adapter(tmp_path)

    timeouts = ConformanceTimeouts(
        response=1.0,
        write=1.0,
        shutdown=1.0,
        terminate=0.2,
        kill=0.5,
    )
    first = run_conformance(
        command=(str(adapter_entry), "--conformance"),
        cwd=tmp_path,
        timeouts=timeouts,
    )
    second = run_conformance(
        command=(str(adapter_entry), "--conformance"),
        cwd=tmp_path,
        timeouts=timeouts,
    )
    _print_report(first)

    assert first.status is RunStatus.CONFORMANT
    assert all(case.status is CaseStatus.PASSED for case in first.cases)
    canonical_report = canonical_conformance_json(first)
    assert canonical_report == canonical_conformance_json(second)
    report_sha256 = hashlib.sha256(canonical_report).hexdigest()
    print(f"canonical conformance SHA-256: {report_sha256}", flush=True)
    assert report_sha256 == EXPECTED_CONFORMANCE_SHA256
    assert go_stdlib_adapter_manifest(ADAPTER_SOURCE_ROOT) == source_before


def test_go_stdlib_adapter_discards_oversized_frame_and_recovers(
    tmp_path: Path,
) -> None:
    source_before = go_stdlib_adapter_manifest(ADAPTER_SOURCE_ROOT)
    adapter_entry = _build_adapter(tmp_path)
    initialize = _request_frame(
        "initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [],
        },
    )
    shutdown = _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    oversized = b"x" * (MAX_FRAME_BYTES + 1) + b"\n"
    payload = oversized + initialize + shutdown
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=payload,
    )
    print(
        "oversized recovery: "
        f"exit={return_code} responses={len(responses)} "
        f"stderr_bytes={len(stderr)}",
        flush=True,
    )

    assert return_code == 0
    assert stderr == b""
    assert len(responses) == 3
    assert responses[0]["id"] is None
    assert responses[0]["error"]["data"] == {
        "category": "protocol_failure",
        "ucf_code": "frame_too_large",
    }
    assert responses[1]["id"] == "initialize"
    assert responses[1]["result"]["kind"] == "initialize_result"
    assert responses[2] == {
        "id": "shutdown",
        "jsonrpc": "2.0",
        "result": {"kind": "shutdown_result"},
    }
    assert go_stdlib_adapter_manifest(ADAPTER_SOURCE_ROOT) == source_before


def test_go_stdlib_adapter_rejects_unqualified_client_without_state_change(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    bad_initialize = _request_frame(
        "bad-initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "unqualified",
                "version": "1.0.0",
            },
            "capabilities": [],
        },
    )
    good_initialize = _request_frame(
        "good-initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [],
        },
    )
    shutdown = _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=bad_initialize + good_initialize + shutdown,
    )
    print(
        "qualified client boundary: "
        f"exit={return_code} responses={len(responses)}",
        flush=True,
    )

    assert return_code == 0
    assert stderr == b""
    assert responses[0]["id"] == "bad-initialize"
    assert responses[0]["error"]["data"]["ucf_code"] == "invalid_params"
    assert responses[1]["id"] == "good-initialize"
    assert responses[1]["result"]["adapter"] == {
        "kind": "producer",
        "name": "org.ucf.adapter.go-stdlib",
        "version": "1.0.0",
    }
    assert responses[2]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_rejects_invalid_capability_names_without_state_change(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    bad_names = ("inventory", "a." + ("b" * 254))
    payload = b"".join(
        _request_frame(
            f"bad-capability-{index}",
            "ucf.initialize",
            {
                "kind": "initialize_request",
                "protocol_version": "1.0.0",
                "client": {
                    "kind": "producer",
                    "name": "org.ucf.ecosystem-test",
                    "version": "1.0.0",
                },
                "capabilities": [
                    {
                        "kind": "capability_request",
                        "name": name,
                        "minimum_version": "1.0.0",
                        "required": False,
                    }
                ],
            },
        )
        for index, name in enumerate(bad_names)
    )
    payload += _request_frame(
        "good-initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [],
        },
    )
    payload += _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=payload,
    )

    assert return_code == 0
    assert stderr == b""
    assert len(responses) == 4
    for index in range(2):
        assert responses[index]["id"] == f"bad-capability-{index}"
        assert (
            responses[index]["error"]["data"]["ucf_code"]
            == "invalid_params"
        )
    assert responses[2]["result"]["kind"] == "initialize_result"
    assert responses[3]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_negotiates_a_supported_minimum_version(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    initialize = _request_frame(
        "initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [
                {
                    "kind": "capability_request",
                    "name": "org.ucf.adapter.inventory",
                    "minimum_version": "0.9.0",
                    "required": True,
                }
            ],
        },
    )
    shutdown = _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=initialize + shutdown,
    )

    assert return_code == 0
    assert stderr == b""
    assert responses[0]["result"]["capabilities"] == [
        {
            "kind": "capability",
            "name": "org.ucf.adapter.inventory",
            "version": "1.0.0",
        }
    ]
    assert responses[1]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_default_mode_rejects_unimplemented_product_capabilities(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    unsupported = (
        "org.ucf.adapter.generation",
        "org.ucf.adapter.verification",
    )
    payload = b"".join(
        _request_frame(
            f"unsupported-{index}",
            "ucf.initialize",
            {
                "kind": "initialize_request",
                "protocol_version": "1.0.0",
                "client": {
                    "kind": "producer",
                    "name": "org.ucf.ecosystem-test",
                    "version": "1.0.0",
                },
                "capabilities": [
                    {
                        "kind": "capability_request",
                        "name": name,
                        "minimum_version": "1.0.0",
                        "required": True,
                    }
                ],
            },
        )
        for index, name in enumerate(unsupported)
    )
    payload += _request_frame(
        "supported",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [
                {
                    "kind": "capability_request",
                    "name": "org.ucf.adapter.inventory",
                    "minimum_version": "1.0.0",
                    "required": True,
                },
                {
                    "kind": "capability_request",
                    "name": "org.ucf.adapter.discovery",
                    "minimum_version": "1.0.0",
                    "required": True,
                },
            ],
        },
    )
    payload += _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )

    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=payload,
    )

    assert return_code == 0
    assert stderr == b""
    assert [
        response["error"]["data"]["ucf_code"]
        for response in responses[:2]
    ] == ["unsupported_capability"] * 2
    assert [
        selection["name"]
        for selection in responses[2]["result"]["capabilities"]
    ] == [
        "org.ucf.adapter.discovery",
        "org.ucf.adapter.inventory",
    ]
    assert responses[3]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_sorts_negotiated_capabilities(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    requested_names = (
        "org.ucf.adapter.discovery",
        "org.ucf.adapter.inventory",
    )
    initialize = _request_frame(
        "initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [
                {
                    "kind": "capability_request",
                    "name": name,
                    "minimum_version": "1.0.0",
                    "required": True,
                }
                for name in requested_names
            ],
        },
    )
    shutdown = _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=initialize + shutdown,
    )

    assert return_code == 0
    assert stderr == b""
    assert [
        selection["name"]
        for selection in responses[0]["result"]["capabilities"]
    ] == sorted(requested_names)
    assert responses[1]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_rejects_duplicate_nested_record_entries(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    capabilities = (
        "org.ucf.adapter.inventory",
        "org.ucf.adapter.discovery",
    )
    initialize = _request_frame(
        "initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [
                {
                    "kind": "capability_request",
                    "name": name,
                    "minimum_version": "1.0.0",
                    "required": True,
                }
                for name in capabilities
            ],
        },
    )
    duplicate_record = {
        "kind": "record",
        "entries": [
            {
                "kind": "record_entry",
                "name": "x",
                "value": {"kind": "null"},
            },
            {
                "kind": "record_entry",
                "name": "x",
                "value": {"kind": "null"},
            },
        ],
    }
    payload = initialize
    for request_id, method, kind in (
        ("inventory-duplicate", "ucf.inventory", "inventory_request"),
        ("discover-duplicate", "ucf.discover", "discover_request"),
    ):
        payload += _request_frame(
            request_id,
            method,
            {
                "kind": kind,
                "payload": _control_payload(duplicate_record),
            },
        )
    payload += _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=payload,
    )

    assert return_code == 0
    assert stderr == b""
    assert responses[0]["result"]["kind"] == "initialize_result"
    assert [
        response["error"]["data"]["ucf_code"]
        for response in responses[1:3]
    ] == ["invalid_params", "invalid_params"]
    assert responses[3]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_writes_canonical_ascii_frames(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    initialize = _request_frame(
        "initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [
                {
                    "kind": "capability_request",
                    "name": "org.ucf.adapter.inventory",
                    "minimum_version": "1.0.0",
                    "required": True,
                }
            ],
        },
    )
    echo = _request_frame(
        "echo",
        "ucf.inventory",
        {
            "kind": "inventory_request",
            "payload": _control_payload(
                {"kind": "string", "value": "café 😀"}
            ),
        },
    )
    shutdown = _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, stdout, stderr = _run_raw_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=initialize + echo + shutdown,
    )
    lines = stdout.splitlines()
    print(
        "canonical output boundary: "
        f"exit={return_code} ascii={stdout.isascii()} frames={len(lines)}",
        flush=True,
    )

    assert return_code == 0
    assert stderr == b""
    assert len(lines) == 3
    assert stdout.isascii()
    for line in lines:
        decoded = json.loads(line)
        assert line == json.dumps(
            decoded,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")


def test_go_stdlib_adapter_enforces_sixty_four_pending_requests(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    initialize = _request_frame(
        "initialize",
        "ucf.initialize",
        {
            "kind": "initialize_request",
            "protocol_version": "1.0.0",
            "client": {
                "kind": "producer",
                "name": "org.ucf.ecosystem-test",
                "version": "1.0.0",
            },
            "capabilities": [
                {
                    "kind": "capability_request",
                    "name": "org.ucf.adapter.inventory",
                    "minimum_version": "1.0.0",
                    "required": True,
                }
            ],
        },
    )
    block_payload = {
        "kind": "adapter_payload",
        "schema_uri": "urn:ucf:adapter-conformance:control:1.0.0",
        "schema_version": "1.0.0",
        "value": {
            "kind": "record",
            "entries": [
                {
                    "kind": "record_entry",
                    "name": "operation",
                    "value": {"kind": "string", "value": "block"},
                }
            ],
        },
    }
    payload = initialize
    for index in range(65):
        payload += _request_frame(
            f"block-{index}",
            "ucf.inventory",
            {
                "kind": "inventory_request",
                "payload": block_payload,
            },
        )
    for index in range(64):
        payload += (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "ucf.cancel",
                    "params": {
                        "kind": "cancel_request",
                        "request_id": f"block-{index}",
                    },
                },
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
    payload += _request_frame(
        "shutdown",
        "ucf.shutdown",
        {"kind": "shutdown_request"},
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=payload,
    )
    error_codes = [
        response.get("error", {}).get("data", {}).get("ucf_code")
        for response in responses
    ]

    assert return_code == 0
    assert stderr == b""
    assert error_codes.count("too_many_pending") == 1
    assert error_codes.count("request_cancelled") == 64
    assert responses[-1]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_reserves_final_session_request_for_shutdown(
    tmp_path: Path,
) -> None:
    adapter_entry = _build_adapter(tmp_path)
    parts = [
        _request_frame(
            "initialize",
            "ucf.initialize",
            {
                "kind": "initialize_request",
                "protocol_version": "1.0.0",
                "client": {
                    "kind": "producer",
                    "name": "org.ucf.ecosystem-test",
                    "version": "1.0.0",
                },
                "capabilities": [],
            },
        )
    ]
    verify_params = {
        "kind": "verify_request",
        "payload": _control_payload({"kind": "null"}),
    }
    parts.extend(
        _request_frame(
            f"rejected-{index}",
            "ucf.verify",
            verify_params,
        )
        for index in range(65_534)
    )
    parts.append(
        _request_frame(
            "over-budget",
            "ucf.verify",
            verify_params,
        )
    )
    parts.append(
        _request_frame(
            "shutdown",
            "ucf.shutdown",
            {"kind": "shutdown_request"},
        )
    )
    return_code, responses, stderr = _run_transcript(
        adapter_entry,
        cwd=tmp_path,
        payload=b"".join(parts),
        timeout=20.0,
    )
    print(
        "session request boundary: "
        f"exit={return_code} responses={len(responses)}",
        flush=True,
    )

    assert return_code == 0
    assert stderr == b""
    assert len(responses) == 65_537
    assert (
        responses[-2]["error"]["data"]["ucf_code"]
        == "session_request_limit"
    )
    assert responses[-1]["result"] == {"kind": "shutdown_result"}


def test_go_stdlib_adapter_manifest_rejects_unexpected_input(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "adapter"
    shutil.copytree(ADAPTER_SOURCE_ROOT, copied, symlinks=True)
    (copied / "future.txt").write_text(
        "not part of the adapter source contract",
        encoding="utf-8",
    )

    with pytest.raises(
        SourceContractError,
        match="unexpected adapter input",
    ):
        go_stdlib_adapter_manifest(copied)


def _control_payload(value: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "adapter_payload",
        "schema_uri": "urn:ucf:adapter-conformance:control:1.0.0",
        "schema_version": "1.0.0",
        "value": {
            "kind": "record",
            "entries": [
                {
                    "kind": "record_entry",
                    "name": "operation",
                    "value": {"kind": "string", "value": "echo"},
                },
                {
                    "kind": "record_entry",
                    "name": "value",
                    "value": value,
                },
            ],
        },
    }


def _build_adapter(tmp_path: Path) -> Path:
    go_bin = resolve_go_stdlib_binary()
    environment = _go_environment(tmp_path)
    adapter_entry = tmp_path / "ucf-go-stdlib-adapter"
    _run_observable(
        (
            str(go_bin),
            "build",
            "-mod=readonly",
            "-trimpath",
            "-buildvcs=false",
            "-ldflags=-buildid=",
            "-o",
            str(adapter_entry),
            "./cmd/adapter",
        ),
        cwd=ADAPTER_SOURCE_ROOT,
        environment=environment,
    )
    assert stat.S_ISREG(adapter_entry.stat().st_mode)
    return adapter_entry


def _request_frame(
    request_id: str,
    method: str,
    params: dict[str, object],
) -> bytes:
    return (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def _run_transcript(
    adapter_entry: Path,
    *,
    cwd: Path,
    payload: bytes,
    timeout: float = 5.0,
) -> tuple[int, list[dict[str, object]], bytes]:
    return_code, stdout, stderr = _run_raw_transcript(
        adapter_entry,
        cwd=cwd,
        payload=payload,
        timeout=timeout,
    )
    responses = [
        json.loads(line)
        for line in stdout.splitlines()
        if line
    ]
    return return_code, responses, stderr


def _run_raw_transcript(
    adapter_entry: Path,
    *,
    cwd: Path,
    payload: bytes,
    timeout: float = 5.0,
) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(
        (str(adapter_entry),),
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1.0)
        raise
    return process.returncode, stdout, stderr


def _go_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "CGO_ENABLED": "0",
            "GOARCH": "amd64",
            "GOENV": "off",
            "GOOS": "linux",
            "GOPATH": str(tmp_path / "gopath"),
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "GOCACHE": str(tmp_path / "gocache"),
            "GOPROXY": "off",
            "GOSUMDB": "off",
        }
    )
    return environment


def _run_observable(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> str:
    print(f"$ {cwd} $ {shlex.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    output: list[str] = []
    for line in process.stdout:
        print(line, end="", flush=True)
        output.append(line)
    return_code = process.wait()
    assert return_code == 0, (
        f"external Go command failed with exit {return_code}: "
        f"{shlex.join(command)}"
    )
    return "".join(output)


def _print_report(report) -> None:
    print(f"conformance status: {report.status.value}", flush=True)
    for case in report.cases:
        print(
            f"{case.case_id}: {case.status.value} ({case.actual})",
            flush=True,
        )
