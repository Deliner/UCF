from __future__ import annotations

from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GO_STDLIB_ADAPTER_INPUTS,
    GO_STDLIB_FIXTURE_INPUTS,
    GoStdlibHarness,
    SourceContractError,
    copy_go_stdlib_adapter,
    copy_go_stdlib_fixture,
    go_stdlib_adapter_manifest,
    go_stdlib_fixture_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_go_stdlib_harness_builds_reproducible_external_processes(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")

    assert not go_stdlib_harness.adapter_root.is_relative_to(PROJECT_ROOT)
    assert not go_stdlib_harness.adapter_entry.is_relative_to(PROJECT_ROOT)
    assert not go_stdlib_harness.fixture_entry.is_relative_to(PROJECT_ROOT)
    assert not target.fixture_root.is_relative_to(PROJECT_ROOT)
    assert target.adapter_entry == go_stdlib_harness.adapter_entry
    assert target.fixture_entry == go_stdlib_harness.fixture_entry
    assert target.source_manifest == (
        go_stdlib_harness.fixture_source_manifest
    )
    assert {
        entry[0] for entry in go_stdlib_harness.adapter_source_manifest
    } == GO_STDLIB_ADAPTER_INPUTS
    assert {
        entry[0] for entry in target.source_manifest
    } == GO_STDLIB_FIXTURE_INPUTS
    assert go_stdlib_harness.build_receipt.go_version == (
        "go version go1.26.5 linux/amd64"
    )
    assert dict(go_stdlib_harness.build_receipt.environment) == {
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
    assert len(go_stdlib_harness.build_receipt.adapter_sha256) == 64
    assert len(go_stdlib_harness.build_receipt.fixture_sha256) == 64
    assert go_stdlib_harness.build_receipt.adapter_size > 0
    assert go_stdlib_harness.build_receipt.fixture_size > 0
    assert go_stdlib_adapter_manifest(
        go_stdlib_harness.adapter_root
    ) == go_stdlib_harness.adapter_source_manifest
    assert go_stdlib_fixture_manifest(target.fixture_root) == (
        target.source_manifest
    )


def test_go_stdlib_source_contract_rejects_unsafe_and_unexpected_inputs(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    adapter_with_output = tmp_path / "adapter-with-output"
    copy_go_stdlib_adapter(
        go_stdlib_harness.adapter_root,
        adapter_with_output,
    )
    generated = adapter_with_output / "out"
    generated.mkdir()
    (generated / "checkout-sentinel").write_text(
        "must not be copied",
        encoding="utf-8",
    )
    copied_adapter = tmp_path / "copied-adapter"
    copied_manifest = copy_go_stdlib_adapter(
        adapter_with_output,
        copied_adapter,
    )
    assert not (copied_adapter / "out").exists()
    assert copied_manifest == go_stdlib_harness.adapter_source_manifest

    (adapter_with_output / "future.txt").write_text(
        "unexpected source",
        encoding="utf-8",
    )
    with pytest.raises(
        SourceContractError,
        match="unexpected adapter input",
    ):
        go_stdlib_adapter_manifest(adapter_with_output)

    linked_fixture = tmp_path / "linked-fixture"
    copy_go_stdlib_fixture(
        go_stdlib_harness.fixture_source_root,
        linked_fixture,
    )
    (linked_fixture / "quote" / "linked.go").symlink_to("service.go")
    with pytest.raises(
        SourceContractError,
        match="must not be a symlink",
    ):
        go_stdlib_fixture_manifest(linked_fixture)

    with pytest.raises(
        SourceContractError,
        match="must not contain one another",
    ):
        copy_go_stdlib_fixture(
            go_stdlib_harness.fixture_source_root,
            go_stdlib_harness.fixture_source_root / "nested-copy",
        )


def test_go_stdlib_source_contract_rejects_modified_upstream_notices(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "adapter"
    copy_go_stdlib_adapter(
        PROJECT_ROOT / "adapters" / "go-stdlib",
        copied,
    )
    patents = copied / "third_party" / "go" / "PATENTS"
    patents.write_bytes(patents.read_bytes() + b"\nmodified\n")

    with pytest.raises(
        SourceContractError,
        match="upstream notice is not exact",
    ):
        go_stdlib_adapter_manifest(copied)
