from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import MAX_REQUESTS_PER_SESSION
from ucf.inventory import (
    INVENTORY_PAGE_SCHEMA_URI,
    MAX_INVENTORY_PAGES,
    MAX_INVENTORY_RECORDS,
    InventoryCursor,
    InventoryPage,
    InventoryProvenance,
    InventoryRecordKind,
    assemble_inventory_pages,
    canonical_inventory_json,
    inventory_page_from_payload,
    inventory_page_to_payload,
)
from ucf.ir.models import Digest

from .test_models import _identified, _producer, _snapshot


def _digest(value: str) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=value,
    )


def _pages() -> tuple[InventoryPage, InventoryPage]:
    snapshot = _snapshot()
    snapshot_digest = _digest(
        hashlib.sha256(canonical_inventory_json(snapshot)).hexdigest()
    )
    first_records = snapshot.records[:2]
    second_records = snapshot.records[2:]
    last = first_records[-1]
    cursor = InventoryCursor(
        kind="inventory_cursor",
        snapshot_digest=snapshot_digest,
        after_kind=InventoryRecordKind(last.kind),
        after_id=last.id,
    )
    common = {
        "inventory_version": snapshot.inventory_version,
        "schema_uri": INVENTORY_PAGE_SCHEMA_URI,
        "subject_uri": snapshot.subject_uri,
        "path_identity": snapshot.path_identity,
        "source_revision": snapshot.source_revision,
        "snapshot_digest": snapshot_digest,
        "producer": snapshot.producer,
        "capability": snapshot.capability,
        "applied_policy": snapshot.applied_policy,
        "coverage": snapshot.coverage,
    }
    return (
        InventoryPage(
            kind="inventory_page",
            **common,
            request_cursor=None,
            records=first_records,
            next_cursor=cursor,
            complete=False,
        ),
        InventoryPage(
            kind="inventory_page",
            **common,
            request_cursor=cursor,
            records=second_records,
            next_cursor=None,
            complete=True,
        ),
    )


def test_pages_round_trip_and_assemble_to_exact_canonical_snapshot():
    pages = _pages()

    for page in pages:
        assert inventory_page_from_payload(
            inventory_page_to_payload(page)
        ) == page
    assembled = assemble_inventory_pages(pages, record_limit=256)

    assert assembled == _snapshot()
    assert canonical_inventory_json(assembled) == canonical_inventory_json(
        _snapshot()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "changed_header",
        "cursor_gap",
        "overlap",
        "premature_end",
        "digest_mismatch",
    ],
)
def test_page_assembly_rejects_mixed_incomplete_or_ambiguous_runs(
    mutation: str,
):
    first, second = _pages()
    pages = [first, second]

    if mutation == "changed_header":
        pages[1] = second.model_copy(
            update={"subject_uri": "urn:ucf:repository:other"}
        )
    elif mutation == "cursor_gap":
        pages[1] = second.model_copy(update={"request_cursor": None})
    elif mutation == "overlap":
        pages[1] = second.model_copy(
            update={"records": (first.records[-1], *second.records)}
        )
    elif mutation == "premature_end":
        pages = [first]
    else:
        bad = _digest("f" * 64)
        pages = [
            first.model_copy(update={"snapshot_digest": bad}),
            second.model_copy(update={"snapshot_digest": bad}),
        ]

    with pytest.raises(ValueError):
        assemble_inventory_pages(tuple(pages), record_limit=256)


def test_cursor_and_page_records_reject_kind_id_mismatches():
    snapshot_digest = _digest("f" * 64)
    with pytest.raises(ValidationError, match="cursor"):
        InventoryCursor(
            kind="inventory_cursor",
            snapshot_digest=snapshot_digest,
            after_kind=InventoryRecordKind.PUBLIC_INTERFACE,
            after_id="entry." + "0" * 64,
        )

    first, _ = _pages()
    payload = first.model_dump(mode="json")
    payload["records"][0]["id"] = "entry." + "f" * 64
    with pytest.raises(ValidationError, match="ID prefix"):
        InventoryPage.model_validate_json(json.dumps(payload))


def test_page_assembly_enforces_the_originating_request_limit():
    pages = _pages()

    with pytest.raises(ValueError, match="request record limit"):
        assemble_inventory_pages(pages, record_limit=1)


def _bulk_provenance(count: int) -> tuple[InventoryProvenance, ...]:
    records = (
        _identified(
            InventoryProvenance(
                kind="inventory_provenance",
                id="provenance." + "0" * 64,
                source_path=f"bulk/{index:06d}",
                content_digest=None,
                source_span=None,
                producer=_producer(),
                procedure_uri=(
                    "urn:ucf:inventory-procedure:fixture-bulk:1.0.0"
                ),
            )
        )
        for index in range(count)
    )
    return tuple(sorted(records, key=lambda record: record.id))


def test_page_and_assembler_enforce_closed_resource_ceilings():
    assert MAX_INVENTORY_PAGES == MAX_REQUESTS_PER_SESSION - 2
    assert MAX_INVENTORY_RECORDS <= MAX_INVENTORY_PAGES

    first, _ = _pages()
    payload = first.model_dump(mode="json")
    payload["records"] = [
        record.model_dump(mode="json")
        for record in _bulk_provenance(257)
    ]
    payload["complete"] = True
    payload["next_cursor"] = None
    with pytest.raises(ValidationError, match="256"):
        InventoryPage.model_validate_json(json.dumps(payload))

    one_page = first.model_copy(
        update={
            "records": _bulk_provenance(1),
            "complete": True,
            "next_cursor": None,
        }
    )
    with pytest.raises(ValueError, match="page limit"):
        assemble_inventory_pages(
            (one_page,) * (MAX_INVENTORY_PAGES + 1),
            record_limit=256,
        )

    full_page = first.model_copy(
        update={
            "records": _bulk_provenance(256),
            "complete": True,
            "next_cursor": None,
        }
    )
    with pytest.raises(ValueError, match="record limit"):
        assemble_inventory_pages(
            (full_page,)
            * ((MAX_INVENTORY_RECORDS // 256) + 1),
            record_limit=256,
        )
