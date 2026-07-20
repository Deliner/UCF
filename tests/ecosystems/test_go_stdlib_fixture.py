from __future__ import annotations

import json
import os
import re
import selectors
import shlex
import shutil
import signal
import stat
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GO_STDLIB_FIXTURE_INPUTS,
    SourceContractError,
    go_stdlib_fixture_manifest,
)
from tools.go_stdlib_toolchain import (
    GoStdlibToolchainError,
    resolve_go_stdlib_binary,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "go_stdlib_legacy_quote"
)


def test_go_stdlib_toolchain_prefers_valid_explicit_binary(
    tmp_path: Path,
) -> None:
    explicit = _write_fake_go(
        tmp_path / "explicit" / "go",
        "go version go1.26.5 linux/amd64",
    )
    path_go = _write_fake_go(
        tmp_path / "path" / "go",
        "go version go1.25.0 linux/amd64",
    )

    resolved = resolve_go_stdlib_binary(
        {
            "PATH": str(path_go.parent),
            "UCF_GO_BIN": str(explicit),
        }
    )

    assert resolved == explicit.resolve(strict=True)


def test_go_stdlib_toolchain_rejects_invalid_explicit_without_fallback(
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "explicit" / "go"
    explicit.parent.mkdir()
    explicit.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path_go = _write_fake_go(
        tmp_path / "path" / "go",
        "go version go1.26.5 linux/amd64",
    )

    with pytest.raises(
        GoStdlibToolchainError,
        match="UCF_GO_BIN",
    ):
        resolve_go_stdlib_binary(
            {
                "PATH": str(path_go.parent),
                "UCF_GO_BIN": str(explicit),
            }
        )


def test_go_stdlib_toolchain_uses_exact_path_binary(
    tmp_path: Path,
) -> None:
    path_go = _write_fake_go(
        tmp_path / "path" / "go",
        "go version go1.26.5 linux/amd64",
    )

    resolved = resolve_go_stdlib_binary({"PATH": str(path_go.parent)})

    assert resolved == path_go.resolve(strict=True)


def test_go_stdlib_toolchain_falls_back_from_incompatible_path_to_home_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path_go = _write_fake_go(
        tmp_path / "path" / "go",
        "go version go1.25.0 linux/amd64",
    )
    home = tmp_path / "portable-home"
    cached_go = _write_fake_go(
        home
        / ".cache"
        / "ucf-toolchains"
        / "go1.26.5"
        / "go"
        / "bin"
        / "go",
        "go version go1.26.5 linux/amd64",
    )
    monkeypatch.setenv("HOME", str(home))

    resolved = resolve_go_stdlib_binary({"PATH": str(path_go.parent)})

    assert resolved == cached_go.resolve(strict=True)


def test_go_stdlib_fixture_builds_and_passes_native_http_behavior(
    tmp_path: Path,
) -> None:
    source_before = go_stdlib_fixture_manifest(FIXTURE_ROOT)
    assert {entry[0] for entry in source_before} == (
        GO_STDLIB_FIXTURE_INPUTS
    )

    workspace = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, workspace, symlinks=True)
    copied = go_stdlib_fixture_manifest(workspace)
    assert copied == source_before

    go_bin = resolve_go_stdlib_binary()
    environment = _go_environment(tmp_path)
    _run_observable(
        (str(go_bin), "mod", "tidy", "-diff"),
        cwd=workspace,
        environment=environment,
    )
    _run_observable(
        (str(go_bin), "mod", "verify"),
        cwd=workspace,
        environment=environment,
    )
    assert (
        _run_observable(
            (str(go_bin), "list", "-mod=readonly", "-m", "all"),
            cwd=workspace,
            environment=environment,
        )
        == "example.com/legacyquotes\n"
    )
    _run_observable(
        (str(go_bin), "vet", "-mod=readonly", "./..."),
        cwd=workspace,
        environment=environment,
    )
    _run_observable(
        (
            str(go_bin),
            "test",
            "-count=1",
            "-mod=readonly",
            "-trimpath",
            "-buildvcs=false",
            "./...",
        ),
        cwd=workspace,
        environment=environment,
    )
    server = tmp_path / "quote-server"
    _run_observable(
        (
            str(go_bin),
            "build",
            "-mod=readonly",
            "-trimpath",
            "-buildvcs=false",
            "-ldflags=-buildid=",
            "-o",
            str(server),
            "./cmd/server",
        ),
        cwd=workspace,
        environment=environment,
    )
    metadata = server.stat()
    assert stat.S_ISREG(metadata.st_mode)
    assert metadata.st_size > 0
    _exercise_server(server)
    assert go_stdlib_fixture_manifest(workspace) == copied
    assert go_stdlib_fixture_manifest(FIXTURE_ROOT) == source_before


def _write_fake_go(path: Path, version_output: str) -> Path:
    path.parent.mkdir(parents=True)
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{version_output}'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_go_stdlib_fixture_manifest_rejects_unexpected_input(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, copied, symlinks=True)
    (copied / "future.txt").write_text(
        "not part of the frozen fixture",
        encoding="utf-8",
    )

    with pytest.raises(
        SourceContractError,
        match="unexpected fixture input",
    ):
        go_stdlib_fixture_manifest(copied)


def _go_environment(tmp_path: Path) -> dict[str, str]:
    go_cache = tmp_path / "gocache"
    module_cache = tmp_path / "gomodcache"
    go_path = tmp_path / "gopath"
    temporary = tmp_path / "gotmp"
    for directory in (go_cache, module_cache, go_path, temporary):
        directory.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "CGO_ENABLED": "0",
            "GOARCH": "amd64",
            "GOAMD64": "v1",
            "GOENV": "off",
            "GOEXPERIMENT": "",
            "GOFLAGS": "",
            "GOOS": "linux",
            "GOPATH": str(go_path),
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "GOCACHE": str(go_cache),
            "GOMODCACHE": str(module_cache),
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "GOTELEMETRY": "off",
            "GOTMPDIR": str(temporary),
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


def _exercise_server(server: Path) -> None:
    command = (str(server), "--listen=127.0.0.1:0")
    print(f"$ {shlex.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        readiness = _read_bounded_line(
            process.stdout.fileno(),
            byte_limit=128,
            timeout=2.0,
        )
        match = re.fullmatch(
            rb"READY http://127\.0\.0\.1:([1-9][0-9]{0,4})\n",
            readiness,
        )
        assert match is not None, f"invalid readiness line: {readiness!r}"
        port = int(match.group(1))
        assert port <= 65_535
        assert process.poll() is None

        positive_status, positive_body = _post_json(
            f"http://127.0.0.1:{port}/quote-order",
            {"unit_price_cents": 1250, "quantity": 2},
        )
        assert positive_status == 200
        assert positive_body == {
            "receipt": "Total: 25.00",
            "total_cents": 2500,
        }
        invalid_status, invalid_body = _post_json(
            f"http://127.0.0.1:{port}/quote-order",
            {"unit_price_cents": 1250, "quantity": 0},
        )
        assert invalid_status == 400
        assert invalid_body == {"error": "quantity must be positive"}

        os.killpg(process.pid, signal.SIGTERM)
        return_code = process.wait(timeout=3.0)
        stdout_tail = process.stdout.read()
        stderr = process.stderr.read()
        print(
            f"fixture server exit={return_code} stderr_bytes={len(stderr)}",
            flush=True,
        )
        assert return_code == 0
        assert stdout_tail == b""
        assert stderr == b""
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1.0)


def _read_bounded_line(
    descriptor: int,
    *,
    byte_limit: int,
    timeout: float,
) -> bytes:
    selector = selectors.DefaultSelector()
    selector.register(descriptor, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    payload = bytearray()
    try:
        while len(payload) <= byte_limit:
            remaining = deadline - time.monotonic()
            assert remaining > 0, "fixture readiness timed out"
            assert selector.select(remaining), "fixture readiness timed out"
            chunk = os.read(descriptor, 1)
            assert chunk, "fixture exited before readiness"
            payload.extend(chunk)
            if chunk == b"\n":
                return bytes(payload)
        raise AssertionError("fixture readiness line is too large")
    finally:
        selector.close()


def _post_json(url: str, body: dict[str, int]) -> tuple[int, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, separators=(",", ":")).encode("ascii"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=2.0)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())
