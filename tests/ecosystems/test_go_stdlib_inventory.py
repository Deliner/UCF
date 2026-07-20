from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GoStdlibHarness,
    GoStdlibTarget,
    go_stdlib_fixture_manifest,
)

from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    BuildManifestFact,
    FactKind,
    IgnorePolicy,
    InventoryDiagnostic,
    InventoryPageRequest,
    InventoryProvenance,
    InventoryRequest,
    PublicInterfaceFact,
    RepositoryEntryFact,
    canonical_inventory_json,
    collect_inventory_from_process,
    inventory_page_from_payload,
    inventory_request_to_payload,
)
from ucf.inventory import TestAssetFact as InventoryTestAssetFact
from ucf.ir.models import Digest

SUBJECT_URI = "urn:ucf:repository:go-stdlib-legacy-quote"
SOURCE_REVISION = (
    "8c95d059aef410657d42e4544d34935c5f422efa9394f1242ee858e02a1c3ff8"
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
        5,
        "aaccb1a00557171b31d00a99a6a2666856e417964732490685cdcba9f02de491",
    ),
    "README.md": (
        "file",
        791,
        "c604b3077303764d4804cd25ab1c60d21ef5e8495eeb290e0d22177ba158e8f3",
    ),
    "cmd": ("directory", None, None),
    "cmd/server": ("directory", None, None),
    "cmd/server/main.go": (
        "file",
        1_197,
        "3f321da079270a3de9884112025a1d91de7be0a303134bac024b49bb9dbfd66f",
    ),
    "go.mod": (
        "file",
        63,
        "22df18de3163ccabe06ed8c4104f01c118d8827970652a65a12e1b5f90357d64",
    ),
    "quote": ("directory", None, None),
    "quote/service.go": (
        "file",
        2_081,
        "089be784fd41b88ee456e359615fa9d24b573564573321e5a76e836860e3888c",
    ),
    "quote/service_test.go": (
        "file",
        2_555,
        "dc5494d4c248c8baee44b090dd079b8de4c2dc13b4ccc379244604ce158d7580",
    ),
}
EXPECTED_MANIFESTS = {
    (
        "go.mod",
        "urn:ucf:inventory-dialect:go-module:1.0.0",
        (1, 1, 5, 19),
    ),
}
EXPECTED_INTERFACES = {
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-exported-function:1.0.0",
        "QuoteOrder",
        None,
        (11, 1, 19, 2),
        "7f6634e8d2e95f65534eed0c686afa92bfb54341b1c65cd1391fbbec54249bb7",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-exported-function:1.0.0",
        "FormatReceipt",
        None,
        (21, 1, 23, 2),
        "101aa20f501220b13317bd879ab7f4679097f73839179c82705334cb62b27361",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-exported-function:1.0.0",
        "NormalizeCoupon",
        None,
        (25, 1, 27, 2),
        "655f767ec6c080eb9079f79c026e5fad29a33a0b04aba864dc90e5144a6798b5",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-exported-function:1.0.0",
        "LegacyDiscountHint",
        None,
        (29, 1, 35, 2),
        "04d62c03a4d305bb7579c19efe42713b4e538738f45a06a386b0ef1123c9e6e2",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-net-http-literal-route:1.0.0",
        "POST /quote-order",
        "Handler",
        (44, 2, 69, 4),
        "4a2d80ac33e034fcd6ba186dc6d51718ba984dee8b6897c11a3251f6065462fd",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-net-http-handler:1.0.0",
        "quote.Handler.func1",
        "POST /quote-order",
        (44, 38, 69, 3),
        "6645b228429429bd80f19b139891af06761cc37d347ff889d3a4248e139b3cf8",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-json-request-field:1.0.0",
        "unit_price_cents",
        "quoteOrderBody",
        (38, 2, 38, 47),
        "ebc507192373f135036b9a9f26247eeb15a34c4dab316afa0b57663269e71dcb",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-json-request-field:1.0.0",
        "quantity",
        "quoteOrderBody",
        (39, 2, 39, 39),
        "1fdd2a7c12b6b200ff1fa5eb644044c2b60ccbab23c08605a110874083e1b075",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-json-response-field:1.0.0",
        "error",
        "POST /quote-order",
        (49, 62, 49, 88),
        "5bb22bef6a4259406aa6f4a7ef7a1e6f120cdd3368b17778207780abac73a04e",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-json-response-field:1.0.0",
        "receipt",
        "POST /quote-order",
        (66, 4, 66, 39),
        "61eb49b41ba8db631036823c767cc837ff882f7cc37843cfa860d74df911c828",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-json-response-field:1.0.0",
        "total_cents",
        "POST /quote-order",
        (67, 4, 67, 24),
        "e83c2577d0b669d3c0152b3d02017129b6a22aa91b52eca6d4f33d9321723e4c",
    ),
    (
        "quote/service.go",
        "urn:ucf:inventory-interface:go-http-response-write:1.0.0",
        "http-response-write",
        "POST /quote-order",
        (44, 38, 69, 3),
        "6645b228429429bd80f19b139891af06761cc37d347ff889d3a4248e139b3cf8",
    ),
}
EXPECTED_TESTS = {
    (
        "quote/service_test.go",
        "urn:ucf:inventory-test:go-native-test-function:1.0.0",
        "TestRealHTTPQuoteOrderReturnsLegacyResult",
        (12, 1, 24, 2),
    ),
    (
        "quote/service_test.go",
        "urn:ucf:inventory-test:go-native-test-function:1.0.0",
        "TestRealHTTPQuoteOrderRejectsZeroQuantity",
        (26, 1, 35, 2),
    ),
    (
        "quote/service_test.go",
        "urn:ucf:inventory-test:go-native-test-function:1.0.0",
        "TestLegacyBusinessFunctionsRetainStandaloneSemantics",
        (37, 1, 60, 2),
    ),
}


def test_go_stdlib_inventory_observes_exact_frozen_filesystem(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    snapshot, stderr_total, stderr_tail = _collect(target, record_limit=256)

    entries = {
        record.path: (
            record.entry_kind,
            record.size_bytes,
            (
                record.content_digest.value
                if record.content_digest is not None
                else None
            ),
        )
        for record in snapshot.records
        if isinstance(record, RepositoryEntryFact)
    }
    coverage = {
        item.fact_kind: (item.status, item.record_count)
        for item in snapshot.coverage
    }

    assert snapshot.subject_uri == SUBJECT_URI
    assert snapshot.producer.name == "org.ucf.adapter.go-stdlib"
    assert snapshot.producer.version == "1.0.0"
    assert snapshot.source_revision.value == SOURCE_REVISION
    assert entries == EXPECTED_ENTRIES
    assert coverage[FactKind.REPOSITORY_ENTRY] == ("complete", 10)
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_inventory_classifies_exact_go_facts(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    snapshot, stderr_total, stderr_tail = _collect(target, record_limit=256)
    repeated, repeated_stderr_total, repeated_stderr_tail = _collect(
        target,
        record_limit=256,
    )
    by_id = {record.id: record for record in snapshot.records}

    coverage = {
        item.fact_kind: (item.status, item.record_count)
        for item in snapshot.coverage
    }
    manifests = {
        (
            _entry_path(record, by_id),
            record.dialect_uri,
            _span(record, by_id),
        )
        for record in snapshot.records
        if isinstance(record, BuildManifestFact)
    }
    interfaces = {
        (
            _entry_path(record, by_id),
            record.interface_kind_uri,
            record.name,
            record.container,
            _span(record, by_id),
            record.declaration_digest.value,
        )
        for record in snapshot.records
        if isinstance(record, PublicInterfaceFact)
    }
    tests = {
        (
            _entry_path(record, by_id),
            record.test_kind_uri,
            record.name,
            _span(record, by_id),
        )
        for record in snapshot.records
        if isinstance(record, InventoryTestAssetFact)
    }

    assert canonical_inventory_json(snapshot) == canonical_inventory_json(
        repeated
    )
    assert len(snapshot.records) == 51
    assert snapshot.source_revision.value == SOURCE_REVISION
    assert coverage == {
        FactKind.API_DESCRIPTION: ("complete", 0),
        FactKind.BUILD_MANIFEST: ("complete", 1),
        FactKind.PUBLIC_INTERFACE: ("complete", 12),
        FactKind.REPOSITORY_ENTRY: ("complete", 10),
        FactKind.TEST_ASSET: ("complete", 3),
    }
    assert manifests == EXPECTED_MANIFESTS
    assert interfaces == EXPECTED_INTERFACES
    assert tests == EXPECTED_TESTS
    assert not any(
        isinstance(record, InventoryDiagnostic)
        for record in snapshot.records
    )
    classified = tuple(
        record
        for record in snapshot.records
        if isinstance(
            record,
            BuildManifestFact
            | PublicInterfaceFact
            | InventoryTestAssetFact,
        )
    )
    assert len(classified) == 16
    assert all(
        record.level == "observed"
        and record.confidence.value == "1"
        and record.confidence.basis
        == "urn:ucf:inventory-procedure:direct-observation:1.0.0"
        for record in classified
    )
    assert {
        by_id[record.provenance.target_id].procedure_uri
        for record in classified
    } == {
        "urn:ucf:inventory-procedure:"
        "go-stdlib-syntax-classification:1.0.0"
    }
    assert stderr_total == repeated_stderr_total == 0
    assert stderr_tail == repeated_stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_inventory_paginates_repeatably_at_seven_and_one(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    before = go_stdlib_fixture_manifest(target.fixture_root)

    seven, seven_stderr_total, seven_stderr_tail = _collect(
        target,
        record_limit=7,
    )
    one, one_stderr_total, one_stderr_tail = _collect(
        target,
        record_limit=1,
    )

    assert canonical_inventory_json(seven) == canonical_inventory_json(one)
    assert seven.source_revision.value == SOURCE_REVISION
    assert len(seven.records) == 51
    assert seven_stderr_total == one_stderr_total == 0
    assert seven_stderr_tail == one_stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_inventory_rejects_stale_and_unknown_cursors_and_recovers(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    before = go_stdlib_fixture_manifest(target.fixture_root)

    async def scenario():
        adapter = _adapter(target)
        try:
            await adapter.start()
            first = await _page(adapter, _request(7))
            assert first.next_cursor is not None

            stale = first.next_cursor.model_copy(
                update={
                    "snapshot_digest": Digest(
                        kind="digest",
                        algorithm="sha-256",
                        value="0" * 64,
                    )
                }
            )
            with pytest.raises(AdapterProtocolError) as stale_error:
                await _page(adapter, _request(7, cursor=stale))

            prefix = first.next_cursor.after_id.split(".", maxsplit=1)[0]
            unknown = first.next_cursor.model_copy(
                update={"after_id": f"{prefix}.{'0' * 64}"}
            )
            with pytest.raises(AdapterProtocolError) as unknown_error:
                await _page(adapter, _request(7, cursor=unknown))

            continued = await _page(
                adapter,
                _request(7, cursor=first.next_cursor),
            )
            repeated = await _page(
                adapter,
                _request(7, cursor=first.next_cursor),
            )
            return (
                stale_error.value,
                unknown_error.value,
                first.next_cursor,
                continued,
                repeated,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    (
        stale,
        unknown,
        first_cursor,
        continued,
        repeated,
        stderr_total,
        stderr_tail,
    ) = asyncio.run(scenario())

    assert stale.category is unknown.category is ErrorCategory.ADAPTER_FAILURE
    assert stale.code is unknown.code is ProtocolCode.OPERATION_FAILED
    assert continued.request_cursor == first_cursor
    assert continued.records
    assert continued == repeated
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_inventory_invalidates_run_when_source_changes_between_pages(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    source = target.fixture_root / "quote" / "service.go"
    original = source.read_bytes()

    async def scenario():
        adapter = _adapter(target)
        try:
            await adapter.start()
            first = await _page(adapter, _request(7))
            assert first.next_cursor is not None

            source.write_bytes(original + b"\n// source drift\n")
            with pytest.raises(AdapterProtocolError) as changed_error:
                await _page(
                    adapter,
                    _request(7, cursor=first.next_cursor),
                )

            source.write_bytes(original)
            with pytest.raises(AdapterProtocolError) as invalidated_error:
                await _page(
                    adapter,
                    _request(7, cursor=first.next_cursor),
                )

            restarted = await _page(adapter, _request(7))
            return (
                changed_error.value,
                invalidated_error.value,
                restarted,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    changed, invalidated, restarted, stderr_total, stderr_tail = asyncio.run(
        scenario()
    )

    assert changed.category is ErrorCategory.ADAPTER_FAILURE
    assert changed.code is ProtocolCode.OPERATION_FAILED
    assert invalidated.category is ErrorCategory.ADAPTER_FAILURE
    assert invalidated.code is ProtocolCode.OPERATION_FAILED
    assert restarted.request_cursor is None
    assert restarted.source_revision.value == SOURCE_REVISION
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_inventory_failed_restart_invalidates_previous_run(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    unexpected = target.fixture_root / "unexpected.txt"

    async def scenario():
        adapter = _adapter(target)
        try:
            await adapter.start()
            first = await _page(adapter, _request(7))
            assert first.next_cursor is not None

            unexpected.write_text("unexpected\n", encoding="utf-8")
            with pytest.raises(AdapterProtocolError) as restart_error:
                await _page(adapter, _request(7))
            unexpected.unlink()

            with pytest.raises(AdapterProtocolError) as old_cursor_error:
                await _page(
                    adapter,
                    _request(7, cursor=first.next_cursor),
                )
            restarted = await _page(adapter, _request(7))
            return (
                restart_error.value,
                old_cursor_error.value,
                restarted,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    restart, old_cursor, restarted, stderr_total, stderr_tail = asyncio.run(
        scenario()
    )

    assert restart.category is ErrorCategory.ADAPTER_FAILURE
    assert restart.code is ProtocolCode.OPERATION_FAILED
    assert old_cursor.category is ErrorCategory.ADAPTER_FAILURE
    assert old_cursor.code is ProtocolCode.OPERATION_FAILED
    assert restarted.request_cursor is None
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_inventory_rejects_route_detached_from_returned_mux(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    source = target.fixture_root / "quote" / "service.go"
    changed = source.read_text(encoding="utf-8").replace(
        '\tmux.HandleFunc("POST /quote-order",',
        "\tother := http.NewServeMux()\n"
        '\tother.HandleFunc("POST /quote-order",',
        1,
    )
    source.write_text(changed, encoding="utf-8")
    before = go_stdlib_fixture_manifest(target.fixture_root)

    async def scenario():
        adapter = _adapter(target)
        try:
            await adapter.start()
            with pytest.raises(AdapterProtocolError) as rejected:
                await _page(adapter, _request(256))
            return (
                rejected.value,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    rejected, stderr_total, stderr_tail = asyncio.run(scenario())

    assert rejected.category is ErrorCategory.ADAPTER_FAILURE
    assert rejected.code is ProtocolCode.OPERATION_FAILED
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


@pytest.mark.parametrize(
    "mutation",
    ("route-literal", "exported-declaration", "malformed-source"),
)
def test_go_stdlib_inventory_rejects_unsupported_go_syntax_without_writes(
    mutation: str,
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "target")
    source = target.fixture_root / "quote" / "service.go"
    original = source.read_text(encoding="utf-8")
    if mutation == "route-literal":
        changed = original.replace(
            '"POST /quote-order"',
            '"GET /quote-order"',
            1,
        )
    elif mutation == "exported-declaration":
        changed = original + "\nfunc UnexpectedDeclaration() {}\n"
    else:
        changed = original.replace(
            "func Handler() http.Handler {",
            "func Handler( http.Handler {",
            1,
        )
    assert changed != original
    source.write_text(changed, encoding="utf-8")
    before = go_stdlib_fixture_manifest(target.fixture_root)

    async def scenario():
        adapter = _adapter(target)
        try:
            await adapter.start()
            with pytest.raises(AdapterProtocolError) as rejected:
                await _page(adapter, _request(256))
            return (
                rejected.value,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    rejected, stderr_total, stderr_tail = asyncio.run(scenario())

    assert rejected.category is ErrorCategory.ADAPTER_FAILURE
    assert rejected.code is ProtocolCode.OPERATION_FAILED
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


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


def _request(
    record_limit: int,
    *,
    cursor=None,
) -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri=SUBJECT_URI,
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version=INVENTORY_VERSION,
            rules=(),
        ),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=record_limit,
            cursor=cursor,
        ),
    )


def _adapter(target: GoStdlibTarget) -> AdapterProcess:
    return AdapterProcess(
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


async def _page(
    adapter: AdapterProcess,
    request: InventoryRequest,
):
    payload = await adapter.call(
        Method.INVENTORY,
        inventory_request_to_payload(request),
        timeout=10.0,
    )
    return inventory_page_from_payload(payload)


def _collect(
    target: GoStdlibTarget,
    *,
    record_limit: int,
):
    async def scenario():
        adapter = _adapter(target)
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
