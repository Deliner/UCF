from __future__ import annotations

import asyncio
from pathlib import Path

from tools.typescript_fastify_adapter_contract import (
    TypeScriptFastifyHarness,
    TypeScriptFastifyTarget,
    typescript_fastify_fixture_manifest,
)

from ucf.adapter_protocol import (
    AdapterProcess,
    CapabilityRequest,
    ProcessTimeouts,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    BuildManifestFact,
    FactKind,
    IgnorePolicy,
    IgnoreRule,
    InventoryPageRequest,
    InventoryProvenance,
    InventoryRequest,
    PathSegmentMatcher,
    PublicInterfaceFact,
    RepositoryEntryFact,
    canonical_inventory_json,
    collect_inventory_from_process,
)
from ucf.inventory import (
    TestAssetFact as InventoryTestAssetFact,
)

SOURCE_REVISION = (
    "3edbe720c9cc3f47b2dfdd2283c94c13a954931c6d3cde7fdb95ec48b0646e9e"
)
FAST_TIMEOUTS = ProcessTimeouts(
    initialize=2.0,
    operation=10.0,
    write=1.0,
    cancellation=0.2,
    shutdown=1.0,
    terminate=0.2,
    kill=0.5,
)

EXPECTED_ENTRIES = {
    ".": ("directory", None, None),
    ".gitignore": (
        "file",
        20,
        "58aea3d6b4b0f8799c1e00c3b023898516997f6369ee8e13d8d4b4215f70a62b",
    ),
    "README.md": (
        "file",
        273,
        "a0ae43b15b5d77a7c96ebca7cd7c1a3c6d9a2dc2646a2416a6205b3da9a81067",
    ),
    "package-lock.json": (
        "file",
        36_351,
        "45a07317fb5d806f665bf679a3c36fc88baeb2c0526391bb2f4186e1c5d88437",
    ),
    "package.json": (
        "file",
        427,
        "b3695b7cf8f9c0d8a3214afdc6a4ba4ab91ac3085ae3258125c73e62e52c08f2",
    ),
    "src": ("directory", None, None),
    "src/service.test.ts": (
        "file",
        1_749,
        "d100ffae4b66af1ac79955d90b1543828fc8339a457901ac6df2b66f05552ad2",
    ),
    "src/service.ts": (
        "file",
        1_739,
        "508c7e86b39282b74514a55ffd1cd7854cfeb9653e0f062985d8a5b2008dadca",
    ),
    "tsconfig.json": (
        "file",
        396,
        "d2c47f62b1f65baa2e79426368e8f330387504ed208ce7ecf7de75a851450586",
    ),
}

EXPECTED_MANIFESTS = {
    (
        "package-lock.json",
        "urn:ucf:inventory-dialect:npm-lockfile-v3:1.0.0",
        (1, 1, 1047, 2),
    ),
    (
        "package.json",
        "urn:ucf:inventory-dialect:npm-package-json:1.0.0",
        (1, 1, 22, 2),
    ),
    (
        "tsconfig.json",
        "urn:ucf:inventory-dialect:typescript-config:1.0.0",
        (1, 1, 18, 2),
    ),
}

EXPECTED_INTERFACES = {
    (
        "src/service.ts",
        "urn:ucf:inventory-interface:typescript-exported-function:1.0.0",
        "quoteOrder",
        None,
        (15, 1, 26, 2),
    ),
    (
        "src/service.ts",
        "urn:ucf:inventory-interface:typescript-exported-function:1.0.0",
        "formatReceipt",
        None,
        (28, 1, 30, 2),
    ),
    (
        "src/service.ts",
        "urn:ucf:inventory-interface:typescript-exported-function:1.0.0",
        "normalizeCoupon",
        None,
        (32, 1, 34, 2),
    ),
    (
        "src/service.ts",
        "urn:ucf:inventory-interface:typescript-exported-function:1.0.0",
        "legacyDiscountHint",
        None,
        (36, 1, 38, 2),
    ),
    (
        "src/service.ts",
        "urn:ucf:inventory-interface:typescript-exported-function:1.0.0",
        "buildApp",
        None,
        (40, 1, 62, 2),
    ),
    (
        "src/service.ts",
        "urn:ucf:inventory-interface:fastify-literal-route:1.0.0",
        "POST /quote-order",
        "buildApp",
        (43, 3, 59, 6),
    ),
}

EXPECTED_TESTS = {
    (
        "src/service.test.ts",
        "real HTTP quote-order path returns the legacy quote result",
        (23, 1, 35, 4),
    ),
    (
        "src/service.test.ts",
        "real HTTP quote-order path rejects zero quantity",
        (37, 1, 48, 4),
    ),
    (
        "src/service.test.ts",
        "legacy business functions retain their standalone semantics",
        (50, 1, 62, 4),
    ),
}


def _request(record_limit: int) -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:typescript-fastify-legacy-quote",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version=INVENTORY_VERSION,
            rules=(
                IgnoreRule(
                    kind="ignore_rule",
                    id="ignore.dist",
                    reason="org.ucf.inventory.generated",
                    matcher=PathSegmentMatcher(
                        kind="path_segment",
                        segment="dist",
                    ),
                ),
                IgnoreRule(
                    kind="ignore_rule",
                    id="ignore.node-modules",
                    reason="org.ucf.inventory.generated",
                    matcher=PathSegmentMatcher(
                        kind="path_segment",
                        segment="node_modules",
                    ),
                ),
            ),
        ),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=record_limit,
            cursor=None,
        ),
    )


def _collect(target: TypeScriptFastifyTarget, record_limit: int):
    async def scenario():
        adapter = AdapterProcess(
            command=target.command(),
            cwd=target.fixture_root,
            requested_capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name=INVENTORY_CAPABILITY,
                    minimum_version=INVENTORY_VERSION,
                    required=True,
                ),
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            await adapter.start()
            snapshot = await collect_inventory_from_process(
                adapter,
                request=_request(record_limit),
                operation_timeout=10.0,
            )
        finally:
            await adapter.close()
        return snapshot, adapter.stderr_total_bytes, adapter.stderr_tail

    return asyncio.run(scenario())


def test_typescript_fastify_inventory_is_exact_repeatable_and_read_only(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "inventory-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest
    assert len(before) == 7

    first, first_stderr_bytes, first_stderr_tail = _collect(target, 7)
    second, second_stderr_bytes, second_stderr_tail = _collect(target, 1)

    assert typescript_fastify_fixture_manifest(target.fixture_root) == before
    assert canonical_inventory_json(first) == canonical_inventory_json(second)
    assert first.source_revision.value == SOURCE_REVISION
    assert first.producer.name == "org.ucf.adapter.typescript-fastify"
    assert first.producer.version == "1.0.0"
    assert first_stderr_bytes == second_stderr_bytes == 0
    assert first_stderr_tail == second_stderr_tail == b""
    assert len(first.records) == 42
    assert {
        item.fact_kind: (item.status, item.record_count)
        for item in first.coverage
    } == {
        FactKind.API_DESCRIPTION: ("complete", 0),
        FactKind.BUILD_MANIFEST: ("complete", 3),
        FactKind.PUBLIC_INTERFACE: ("complete", 6),
        FactKind.REPOSITORY_ENTRY: ("complete", 9),
        FactKind.TEST_ASSET: ("complete", 3),
    }

    by_id = {record.id: record for record in first.records}
    entries = {
        record.path: (
            record.entry_kind,
            record.size_bytes,
            (
                None
                if record.content_digest is None
                else record.content_digest.value
            ),
        )
        for record in first.records
        if isinstance(record, RepositoryEntryFact)
    }
    assert entries == EXPECTED_ENTRIES

    manifests = {
        (
            _entry_path(record, by_id),
            record.dialect_uri,
            _span(record, by_id),
        )
        for record in first.records
        if isinstance(record, BuildManifestFact)
    }
    assert manifests == EXPECTED_MANIFESTS

    interfaces = {
        (
            _entry_path(record, by_id),
            record.interface_kind_uri,
            record.name,
            record.container,
            _span(record, by_id),
        )
        for record in first.records
        if isinstance(record, PublicInterfaceFact)
    }
    assert interfaces == EXPECTED_INTERFACES

    tests = {
        (
            _entry_path(record, by_id),
            record.name,
            _span(record, by_id),
        )
        for record in first.records
        if isinstance(record, InventoryTestAssetFact)
    }
    assert tests == EXPECTED_TESTS


def _entry_path(record, by_id: dict[str, object]) -> str:
    entry = by_id[record.entry.target_id]
    assert isinstance(entry, RepositoryEntryFact)
    return entry.path


def _span(record, by_id: dict[str, object]) -> tuple[int, int, int, int]:
    provenance = by_id[record.provenance.target_id]
    assert isinstance(provenance, InventoryProvenance)
    span = provenance.source_span
    assert span is not None
    return (
        span.start_line,
        span.start_column,
        span.end_line,
        span.end_column,
    )
