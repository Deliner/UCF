from __future__ import annotations

from pathlib import Path

import pytest
from tools.typescript_fastify_adapter_contract import (
    SourceContractError,
    TypeScriptFastifyHarness,
    copy_typescript_fastify_adapter,
    copy_typescript_fastify_fixture,
    typescript_fastify_adapter_manifest,
    typescript_fastify_fixture_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BUILD_COMMANDS = (
    ("node", "--version"),
    ("npm", "--version"),
    ("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"),
    ("npm", "run", "build"),
    ("npm", "test"),
)


def test_typescript_fastify_harness_builds_one_exact_external_adapter(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "harness-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)

    assert not typescript_fastify_harness.adapter_root.is_relative_to(
        PROJECT_ROOT
    )
    assert not typescript_fastify_harness.adapter_entry.is_relative_to(
        PROJECT_ROOT
    )
    assert not target.fixture_root.is_relative_to(PROJECT_ROOT)
    assert target.adapter_entry == typescript_fastify_harness.adapter_entry
    assert before == target.source_manifest
    assert len(before) == 7
    assert (
        typescript_fastify_harness.build_receipt.node_version
        == "v22.22.3"
    )
    assert typescript_fastify_harness.build_receipt.npm_version == "10.9.8"
    assert (
        typescript_fastify_harness.build_receipt.commands
        == EXPECTED_BUILD_COMMANDS
    )
    assert typescript_fastify_adapter_manifest(
        typescript_fastify_harness.adapter_root
    ) == typescript_fastify_harness.adapter_source_manifest
    assert all(
        not relative.startswith(
            (".artifacts/", ".npm/", "dist/", "node_modules/")
        )
        for relative, _, _ in (
            typescript_fastify_harness.adapter_source_manifest
        )
    )
    assert typescript_fastify_fixture_manifest(target.fixture_root) == before


def test_typescript_fastify_source_contract_rejects_unexpected_and_unsafe_inputs(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "contract-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest
    assert len(before) == 7

    unexpected = tmp_path / "unexpected-input"
    copy_typescript_fastify_fixture(target.fixture_root, unexpected)
    (unexpected / "future.txt").write_text("not part of the fixture")
    with pytest.raises(
        SourceContractError,
        match="unexpected source input",
    ):
        typescript_fastify_fixture_manifest(unexpected)

    linked = tmp_path / "linked-input"
    copy_typescript_fastify_fixture(target.fixture_root, linked)
    (linked / "src" / "linked.ts").symlink_to("service.ts")
    with pytest.raises(
        SourceContractError,
        match="must not be a symlink",
    ):
        typescript_fastify_fixture_manifest(linked)

    with pytest.raises(
        SourceContractError,
        match="must not contain one another",
    ):
        copy_typescript_fastify_fixture(
            target.fixture_root,
            target.fixture_root / "nested-copy",
        )

    adapter_with_generated = tmp_path / "adapter-with-generated"
    copy_typescript_fastify_adapter(
        typescript_fastify_harness.adapter_root,
        adapter_with_generated,
    )
    (adapter_with_generated / "dist").mkdir()
    (adapter_with_generated / "dist" / "checkout-sentinel.js").write_text(
        "must not be copied"
    )
    (adapter_with_generated / "node_modules").mkdir()
    (
        adapter_with_generated / "node_modules" / "checkout-sentinel"
    ).write_text("must not be copied")
    external_adapter_copy = tmp_path / "external-adapter-copy"
    copied_adapter_manifest = copy_typescript_fastify_adapter(
        adapter_with_generated,
        external_adapter_copy,
    )
    assert not (external_adapter_copy / "dist").exists()
    assert not (external_adapter_copy / "node_modules").exists()
    assert copied_adapter_manifest == typescript_fastify_adapter_manifest(
        adapter_with_generated
    )

    (adapter_with_generated / "src" / "unexpected.js").write_text(
        "wrong source suffix"
    )
    with pytest.raises(
        SourceContractError,
        match="unexpected source input",
    ):
        typescript_fastify_adapter_manifest(adapter_with_generated)

    assert typescript_fastify_fixture_manifest(target.fixture_root) == before
