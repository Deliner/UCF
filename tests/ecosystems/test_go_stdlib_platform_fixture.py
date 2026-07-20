from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from tools.go_stdlib_platform_contract import (
    GO_STDLIB_PLATFORM_BINARY_SHA256,
    GO_STDLIB_PLATFORM_BUILD_COMMANDS,
    GO_STDLIB_PLATFORM_BUILD_METADATA,
    GO_STDLIB_PLATFORM_INPUTS,
    GO_STDLIB_PLATFORM_SOURCE_REVISION,
    GoStdlibPlatformHarness,
    SourceContractError,
    copy_go_stdlib_platform_fixture,
    go_stdlib_platform_manifest,
    go_stdlib_platform_source_revision,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_SOURCE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "go_stdlib_legacy_platforms"
)
EXPECTED_GO_ENVIRONMENT = {
    "CGO_ENABLED": "0",
    "GOARCH": "amd64",
    "GOAMD64": "v1",
    "GOENV": "off",
    "GOOS": "linux",
    "GOPROXY": "off",
    "GOSUMDB": "off",
    "GOTELEMETRY": "off",
    "GOTOOLCHAIN": "local",
    "GOWORK": "off",
}


def test_go_stdlib_platform_source_contract_is_exact_and_closed(
    tmp_path: Path,
) -> None:
    source_before = go_stdlib_platform_manifest(PLATFORM_SOURCE_ROOT)
    copied_root = tmp_path / "platform-source"
    copied = copy_go_stdlib_platform_fixture(
        PLATFORM_SOURCE_ROOT,
        copied_root,
    )

    assert {relative for relative, _, _ in copied} == (
        GO_STDLIB_PLATFORM_INPUTS
    )
    assert len(copied) == 9
    assert copied == source_before
    assert not copied_root.is_relative_to(PROJECT_ROOT)
    assert go_stdlib_platform_source_revision(copied) == (
        GO_STDLIB_PLATFORM_SOURCE_REVISION
    )
    assert go_stdlib_platform_manifest(copied_root) == copied
    assert go_stdlib_platform_manifest(PLATFORM_SOURCE_ROOT) == source_before


def test_go_stdlib_platform_source_contract_rejects_unexpected_input(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "platform-unexpected"
    copy_go_stdlib_platform_fixture(PLATFORM_SOURCE_ROOT, copied_root)
    (copied_root / "future.txt").write_text(
        "outside the frozen fixture",
        encoding="utf-8",
    )

    with pytest.raises(
        SourceContractError,
        match="unexpected platform fixture input: future.txt",
    ):
        go_stdlib_platform_manifest(copied_root)


def test_go_stdlib_platform_source_contract_does_not_follow_symlinks(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "platform-linked"
    copy_go_stdlib_platform_fixture(PLATFORM_SOURCE_ROOT, copied_root)
    (copied_root / "quote" / "linked.go").symlink_to("service.go")

    with pytest.raises(
        SourceContractError,
        match="platform fixture input must not be a symlink: quote/linked.go",
    ):
        go_stdlib_platform_manifest(copied_root)


def test_go_stdlib_platform_harness_builds_exact_reproducible_processes(
    tmp_path: Path,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(
        tmp_path / "platform-target"
    )
    receipt = go_stdlib_platform_harness.build_receipt

    assert not go_stdlib_platform_harness.platform_build_root.is_relative_to(
        PROJECT_ROOT
    )
    assert not go_stdlib_platform_harness.platform_entry.is_relative_to(
        PROJECT_ROOT
    )
    assert not (
        go_stdlib_platform_harness.reproducible_platform_entry.is_relative_to(
            PROJECT_ROOT
        )
    )
    assert not go_stdlib_platform_harness.adapter_entry.is_relative_to(
        PROJECT_ROOT
    )
    assert not target.fixture_root.is_relative_to(PROJECT_ROOT)
    assert target.adapter_entry == go_stdlib_platform_harness.adapter_entry
    assert target.fixture_entry == go_stdlib_platform_harness.platform_entry
    assert target.source_manifest == (
        go_stdlib_platform_harness.platform_source_manifest
    )
    assert target.command() == (str(target.adapter_entry),)
    assert target.verification_command() == (
        str(target.adapter_entry),
        "--platform-fixture-executable",
        str(target.fixture_entry),
    )
    assert {
        relative for relative, _, _ in target.source_manifest
    } == GO_STDLIB_PLATFORM_INPUTS
    assert receipt.go_version == "go version go1.26.5 linux/amd64"
    assert dict(receipt.environment) == EXPECTED_GO_ENVIRONMENT
    assert receipt.commands == GO_STDLIB_PLATFORM_BUILD_COMMANDS
    assert receipt.build_metadata == GO_STDLIB_PLATFORM_BUILD_METADATA
    assert receipt.platform_sha256 == GO_STDLIB_PLATFORM_BINARY_SHA256
    assert receipt.platform_size > 0
    assert (
        hashlib.sha256(
            go_stdlib_platform_harness.platform_entry.read_bytes()
        ).hexdigest()
        == receipt.platform_sha256
    )
    assert (
        go_stdlib_platform_harness.platform_entry.read_bytes()
        == go_stdlib_platform_harness.reproducible_platform_entry.read_bytes()
    )
    assert go_stdlib_platform_manifest(target.fixture_root) == (
        target.source_manifest
    )


def test_go_stdlib_platform_binary_runs_real_cli_and_event_processes(
    tmp_path: Path,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(
        tmp_path / "native-platform-target"
    )
    source_before = go_stdlib_platform_manifest(target.fixture_root)

    quote = _run_platform(
        target.fixture_entry,
        "quote",
        "--unit-price-cents",
        "1250",
        "--quantity",
        "2",
    )
    assert quote.returncode == 0
    assert quote.stdout == (
        b'{"receipt":"Total: 25.00","total_cents":2500}\n'
    )
    assert quote.stderr == b""

    spool_root = tmp_path / "runtime-spool"
    enqueue = _run_platform(
        target.fixture_entry,
        "event",
        "enqueue",
        "--spool",
        str(spool_root),
        "--event-id",
        "event-001",
        "--unit-price-cents",
        "1250",
        "--quantity",
        "2",
    )
    assert enqueue.returncode == 0
    assert enqueue.stdout == (
        b'{"event_id":"event-001","status":"enqueued"}\n'
    )
    assert enqueue.stderr == b""

    unavailable = _run_platform(
        target.fixture_entry,
        "event",
        "observe",
        "--spool",
        str(spool_root),
        "--event-id",
        "event-001",
    )
    assert unavailable.returncode == 3
    assert unavailable.stdout == b""
    assert unavailable.stderr == b"observation unavailable\n"

    dispatch = _run_platform(
        target.fixture_entry,
        "event",
        "dispatch-once",
        "--spool",
        str(spool_root),
    )
    assert dispatch.returncode == 0
    assert dispatch.stdout == (
        b'{"event_id":"event-001","status":"dispatched"}\n'
    )
    assert dispatch.stderr == b""

    observation = _run_platform(
        target.fixture_entry,
        "event",
        "observe",
        "--spool",
        str(spool_root),
        "--event-id",
        "event-001",
    )
    assert observation.returncode == 0
    assert observation.stdout == (
        b'{"event_id":"event-001","receipt":"Total: 25.00",'
        b'"total_cents":2500}\n'
    )
    assert observation.stderr == b""
    assert not spool_root.is_relative_to(target.fixture_root)
    assert go_stdlib_platform_manifest(target.fixture_root) == source_before
    assert (
        go_stdlib_platform_manifest(PLATFORM_SOURCE_ROOT)
        == go_stdlib_platform_harness.platform_source_manifest
    )


def _run_platform(
    executable: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[bytes]:
    print(
        "$ " + " ".join((str(executable), *arguments)),
        flush=True,
    )
    return subprocess.run(
        (str(executable), *arguments),
        capture_output=True,
        check=False,
        timeout=5.0,
    )
