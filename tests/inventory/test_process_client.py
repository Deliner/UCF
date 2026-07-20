from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import socket
import sys
import threading
from pathlib import Path

import pytest

from ucf.adapter_protocol import (
    MAX_FRAME_BYTES,
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    Method,
    ProcessState,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    IgnorePolicy,
    IgnoreRule,
    InventoryCursor,
    InventoryPageRequest,
    InventoryRecordKind,
    InventoryRequest,
    PathSegmentMatcher,
    canonical_inventory_json,
    collect_inventory,
    inventory_page_from_payload,
    inventory_request_to_payload,
)
from ucf.ir.models import Digest

from .reference_adapter_harness import nonfollowing_tree_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT / "tests" / "fixtures" / "brownfield" / "inventory_mixed"
)
REFERENCE_ADAPTER = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "inventory_reference_adapter.py"
)
FAST_TIMEOUTS = ProcessTimeouts(
    initialize=2.0,
    operation=5.0,
    write=1.0,
    cancellation=0.2,
    shutdown=1.0,
    terminate=0.2,
    kill=0.5,
)


def _request(*, record_limit: int = 5) -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:inventory-mixed",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version="1.0.0",
            rules=(
                IgnoreRule(
                    kind="ignore_rule",
                    id="ignore.generated",
                    reason="org.ucf.inventory.generated",
                    matcher=PathSegmentMatcher(
                        kind="path_segment",
                        segment="generated",
                    ),
                ),
                IgnoreRule(
                    kind="ignore_rule",
                    id="ignore.vendor",
                    reason="org.ucf.inventory.vendor",
                    matcher=PathSegmentMatcher(
                        kind="path_segment",
                        segment="vendor",
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


def _collect_reference_inventory(
    repository: Path,
    *,
    record_limit: int = 5,
):
    async def scenario():
        return await collect_inventory(
            command=(sys.executable, str(REFERENCE_ADAPTER)),
            cwd=repository,
            request=_request(record_limit=record_limit),
            timeouts=FAST_TIMEOUTS,
        )

    return asyncio.run(scenario())


def test_client_collects_complete_repeatable_multipage_inventory():
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)

    async def scenario():
        command = (sys.executable, str(REFERENCE_ADAPTER))
        first = await collect_inventory(
            command=command,
            cwd=FIXTURE_ROOT,
            request=_request(),
            timeouts=FAST_TIMEOUTS,
        )
        second = await collect_inventory(
            command=command,
            cwd=FIXTURE_ROOT,
            request=_request(record_limit=1),
            timeouts=FAST_TIMEOUTS,
        )
        return first, second

    first, second = asyncio.run(scenario())

    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before
    assert canonical_inventory_json(first) == canonical_inventory_json(second)
    counts = {
        item.fact_kind: item.record_count for item in first.coverage
    }
    assert counts == {
        FactKind.API_DESCRIPTION: 1,
        FactKind.BUILD_MANIFEST: 1,
        FactKind.PUBLIC_INTERFACE: 2,
        FactKind.REPOSITORY_ENTRY: 9,
        FactKind.TEST_ASSET: 2,
    }
    assert all(item.status == "complete" for item in first.coverage)
    assert sum(
        record.kind == "inventory_ignore_match"
        for record in first.records
    ) == 2
    assert not any(
        record.kind == "inventory_diagnostic" for record in first.records
    )


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    (
        ("wrong-profile", ProtocolCode.INVALID_ADAPTER_OUTPUT),
        ("invalid-page", ProtocolCode.INVALID_ADAPTER_OUTPUT),
        ("fail-second-page", ProtocolCode.OPERATION_FAILED),
    ),
)
def test_client_rejects_adapter_failure_without_returning_partial_inventory(
    mode: str,
    expected_code: ProtocolCode,
):
    async def scenario():
        await collect_inventory(
            command=(
                sys.executable,
                str(REFERENCE_ADAPTER),
                "--mode",
                mode,
            ),
            cwd=FIXTURE_ROOT,
            request=_request(record_limit=1),
            timeouts=FAST_TIMEOUTS,
        )

    with pytest.raises(AdapterProtocolError) as caught:
        asyncio.run(scenario())

    assert caught.value.code is expected_code


def test_client_rejects_initial_cursor_before_spawning_adapter():
    cursor = InventoryCursor(
        kind="inventory_cursor",
        snapshot_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value="0" * 64,
        ),
        after_kind=InventoryRecordKind.REPOSITORY_ENTRY,
        after_id=f"entry.{'0' * 64}",
    )
    request = _request().model_copy(
        update={
            "page": InventoryPageRequest(
                kind="inventory_page_request",
                record_limit=1,
                cursor=cursor,
            )
        }
    )

    async def scenario():
        await collect_inventory(
            command=("adapter-that-must-not-be-spawned",),
            cwd=FIXTURE_ROOT,
            request=request,
            timeouts=FAST_TIMEOUTS,
        )

    with pytest.raises(
        ValueError,
        match="inventory collection must start without a cursor",
    ):
        asyncio.run(scenario())


def test_client_collects_snapshot_larger_than_one_protocol_frame(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    bulk = repository / "bulk"
    bulk.mkdir()
    for index in range(1_200):
        (bulk / f"module_{index:04d}.py").write_text(
            f"VALUE_{index:04d} = {index}\n",
            encoding="utf-8",
        )

    async def scenario():
        snapshots = []
        for record_limit in (256, 127):
            snapshots.append(
                await collect_inventory(
                    command=(sys.executable, str(REFERENCE_ADAPTER)),
                    cwd=repository,
                    request=_request(record_limit=record_limit),
                    timeouts=ProcessTimeouts(
                        initialize=2.0,
                        operation=20.0,
                        write=1.0,
                        cancellation=0.2,
                        shutdown=1.0,
                        terminate=0.2,
                        kill=0.5,
                    ),
                )
            )
        return tuple(snapshots)

    snapshot, alternate = asyncio.run(scenario())

    assert len(canonical_inventory_json(snapshot)) > MAX_FRAME_BYTES
    assert canonical_inventory_json(alternate) == canonical_inventory_json(
        snapshot
    )
    assert (
        sum(
            item.record_count
            for item in snapshot.coverage
            if item.fact_kind is FactKind.REPOSITORY_ENTRY
        )
        == 1_210
    )


def test_ignored_content_and_membership_do_not_change_snapshot(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    before = _collect_reference_inventory(repository)

    generated = repository / "generated"
    (generated / "client.py").write_text(
        "RAISE_IF_READ = object()\n",
        encoding="utf-8",
    )
    nested = generated / "new" / "deep"
    nested.mkdir(parents=True)
    (nested / "secret.py").write_text(
        "IGNORED_SECRET = 'must not be inventoried'\n",
        encoding="utf-8",
    )
    after = _collect_reference_inventory(repository, record_limit=1)

    assert canonical_inventory_json(after) == canonical_inventory_json(before)


def test_included_content_changes_only_path_related_record_identities(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    before = _collect_reference_inventory(repository)
    changed_path = "src/legacy_service/api.py"

    source = repository / changed_path
    source.write_text(
        source.read_text(encoding="utf-8") + "\nNEW_PUBLIC_VALUE = 2\n",
        encoding="utf-8",
    )
    after = _collect_reference_inventory(repository, record_limit=1)

    def related_ids(snapshot) -> set[str]:
        provenance_ids = {
            record.id
            for record in snapshot.records
            if record.kind == "inventory_provenance"
            and record.source_path == changed_path
        }
        entry_ids = {
            record.id
            for record in snapshot.records
            if record.kind == "repository_entry"
            and record.path == changed_path
        }
        return provenance_ids | entry_ids | {
            record.id
            for record in snapshot.records
            if (
                getattr(record, "provenance", None) is not None
                and record.provenance.target_id in provenance_ids
            )
            or (
                getattr(record, "entry", None) is not None
                and record.entry.target_id in entry_ids
            )
        }

    before_ids = {record.id for record in before.records}
    after_ids = {record.id for record in after.records}
    changed_ids = related_ids(before) | related_ids(after)

    assert before.source_revision != after.source_revision
    assert before_ids ^ after_ids == changed_ids


def test_symlinks_and_nonregular_entries_have_bounded_explicit_outcomes(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    outside = tmp_path / "outside.txt"
    outside_bytes = b"outside content must never cross the inventory boundary"
    outside.write_bytes(outside_bytes)
    (repository / "escape").symlink_to(outside)
    (repository / "cycle").symlink_to(".")
    os.mkfifo(repository / "pipe")
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(repository / "socket"))
    try:
        snapshot = _collect_reference_inventory(repository)
    finally:
        server.close()

    encoded = canonical_inventory_json(snapshot)
    assert hashlib.sha256(outside_bytes).hexdigest().encode() not in encoded
    entries = {
        record.path: record
        for record in snapshot.records
        if record.kind == "repository_entry"
    }
    assert entries["escape"].entry_kind == "symlink"
    assert entries["cycle"].entry_kind == "symlink"
    assert "pipe" not in entries
    assert "socket" not in entries
    diagnostic_paths = {
        record.path
        for record in snapshot.records
        if record.kind == "inventory_diagnostic"
    }
    assert {"pipe", "socket"} <= diagnostic_paths
    coverage = {item.fact_kind: item.status for item in snapshot.coverage}
    assert coverage[FactKind.REPOSITORY_ENTRY] == "partial"


def test_multiple_unsafe_names_produce_one_stable_parent_diagnostic(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    (repository / "bad?one.py").write_text("FIRST = 1\n", encoding="utf-8")
    (repository / "bad*two.py").write_text("SECOND = 2\n", encoding="utf-8")

    snapshot = _collect_reference_inventory(repository)

    diagnostics = [
        record
        for record in snapshot.records
        if record.kind == "inventory_diagnostic"
    ]
    assert [
        (record.code, record.path, record.stage) for record in diagnostics
    ] == [("org.ucf.inventory.path-unsupported", ".", "enumerate")]
    coverage = {item.fact_kind: item.status for item in snapshot.coverage}
    assert coverage[FactKind.REPOSITORY_ENTRY] == "partial"


def test_portable_path_collision_is_explicit_and_does_not_merge_files(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    (repository / "Case.py").write_text("FIRST = 1\n", encoding="utf-8")
    (repository / "case.py").write_text("SECOND = 2\n", encoding="utf-8")

    snapshot = _collect_reference_inventory(repository)

    entries = {
        record.path
        for record in snapshot.records
        if record.kind == "repository_entry"
    }
    assert "Case.py" in entries
    assert "case.py" not in entries
    assert any(
        record.kind == "inventory_diagnostic"
        and record.code == "org.ucf.inventory.path-collision"
        and record.path == "case.py"
        for record in snapshot.records
    )


def test_reference_adapter_acknowledges_cancellation_and_remains_usable(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    large_file = repository / "large.bin"
    with large_file.open("wb") as stream:
        stream.seek(128 * 1024 * 1024 - 1)
        stream.write(b"\0")

    async def scenario():
        adapter = AdapterProcess(
            command=(sys.executable, str(REFERENCE_ADAPTER)),
            cwd=repository,
            requested_capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name=INVENTORY_CAPABILITY,
                    minimum_version=INVENTORY_VERSION,
                    required=True,
                ),
            ),
            timeouts=ProcessTimeouts(
                initialize=2.0,
                operation=1.0,
                write=1.0,
                cancellation=0.02,
                shutdown=1.0,
                terminate=0.2,
                kill=0.5,
            ),
        )
        try:
            await adapter.start()
            with pytest.raises(AdapterProtocolError) as caught:
                await adapter.call(
                    Method.INVENTORY,
                    inventory_request_to_payload(_request()),
                    timeout=0.001,
                )
            state_after_cancel = adapter.state
            large_file.unlink()
            payload = await adapter.call(
                Method.INVENTORY,
                inventory_request_to_payload(_request(record_limit=256)),
                timeout=2.0,
            )
            page = inventory_page_from_payload(payload)
            return caught.value.code, state_after_cancel, page.kind
        finally:
            await adapter.close()

    code, state, page_kind = asyncio.run(scenario())

    assert code is ProtocolCode.OPERATION_TIMEOUT
    assert state is ProcessState.READY
    assert page_kind == "inventory_page"


def test_mid_scan_file_mutation_marks_inventory_explicitly_partial(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    changing = repository / "changing.bin"
    with changing.open("wb") as stream:
        stream.seek(32 * 1024 * 1024 - 1)
        stream.write(b"\0")

    descriptor = os.open(changing, os.O_RDWR)
    stop = threading.Event()

    def mutate() -> None:
        value = 0
        while not stop.is_set():
            os.pwrite(descriptor, bytes((value,)), 0)
            value ^= 1

    writer = threading.Thread(target=mutate)
    writer.start()
    try:
        snapshot = _collect_reference_inventory(repository)
    finally:
        stop.set()
        writer.join()
        os.close(descriptor)

    assert not any(
        record.kind == "repository_entry"
        and record.path == "changing.bin"
        for record in snapshot.records
    )
    assert any(
        record.kind == "inventory_diagnostic"
        and record.code == "org.ucf.inventory.source-changed"
        and record.path == "changing.bin"
        for record in snapshot.records
    )
    coverage = {item.fact_kind: item.status for item in snapshot.coverage}
    assert all(status == "partial" for status in coverage.values())


def test_unreadable_file_is_not_silently_omitted(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    unreadable = repository / "unreadable.py"
    unreadable.write_text("SECRET = 1\n", encoding="utf-8")
    unreadable.chmod(0)
    try:
        snapshot = _collect_reference_inventory(repository)
    finally:
        unreadable.chmod(0o600)

    assert not any(
        record.kind == "repository_entry"
        and record.path == "unreadable.py"
        for record in snapshot.records
    )
    assert any(
        record.kind == "inventory_diagnostic"
        and record.code == "org.ucf.inventory.entry-inaccessible"
        and record.path == "unreadable.py"
        for record in snapshot.records
    )
    coverage = {item.fact_kind: item.status for item in snapshot.coverage}
    assert coverage[FactKind.REPOSITORY_ENTRY] == "partial"


def test_classification_failure_marks_only_its_fact_category_partial(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    (repository / "api" / "openapi.json").write_text(
        "{not-json",
        encoding="utf-8",
    )

    snapshot = _collect_reference_inventory(repository)

    assert any(
        record.kind == "inventory_diagnostic"
        and record.code == "org.ucf.inventory.classification-failed"
        and record.fact_kind is FactKind.API_DESCRIPTION
        and record.path == "api/openapi.json"
        for record in snapshot.records
    )
    coverage = {item.fact_kind: item.status for item in snapshot.coverage}
    assert coverage[FactKind.API_DESCRIPTION] == "partial"
    assert all(
        status == "complete"
        for fact_kind, status in coverage.items()
        if fact_kind is not FactKind.API_DESCRIPTION
    )


@pytest.mark.parametrize(
    ("relative_path", "content", "fact_kind"),
    (
        pytest.param(
            "api/openapi.json",
            "[" * 10_000 + "0" + "]" * 10_000,
            FactKind.API_DESCRIPTION,
            id="openapi-recursion",
        ),
        pytest.param(
            "pyproject.toml",
            "project = { x = "
            + "[" * 10_000
            + "0"
            + "]" * 10_000
            + " }\n",
            FactKind.BUILD_MANIFEST,
            id="toml-recursion",
        ),
        pytest.param(
            "src/deep.py",
            "def public(x=" + "not " * 2_000 + "True):\n    pass\n",
            FactKind.PUBLIC_INTERFACE,
            id="python-recursion",
        ),
        pytest.param(
            "src/unary.py",
            "x=" + "-" * 100_000 + "1\n",
            FactKind.PUBLIC_INTERFACE,
            id="python-memory",
        ),
    ),
)
def test_parser_resource_exhaustion_is_a_partial_classification_diagnostic(
    tmp_path,
    relative_path: str,
    content: str,
    fact_kind: FactKind,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    snapshot = _collect_reference_inventory(repository)

    assert any(
        record.kind == "inventory_diagnostic"
        and record.code == "org.ucf.inventory.classification-failed"
        and record.fact_kind is fact_kind
        and record.path == relative_path
        for record in snapshot.records
    )
    coverage = {item.fact_kind: item.status for item in snapshot.coverage}
    assert coverage[fact_kind] == "partial"
