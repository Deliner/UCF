from __future__ import annotations

import hashlib

from ucf.inventory.codec import canonical_inventory_json
from ucf.inventory.models import (
    INVENTORY_SCHEMA_URI,
    MAX_INVENTORY_PAGES,
    MAX_INVENTORY_RECORDS,
    MAX_PAGE_RECORDS,
    InventoryPage,
    InventoryRecord,
    InventorySnapshot,
)


def assemble_inventory_pages(
    pages: tuple[InventoryPage, ...],
    *,
    record_limit: int,
) -> InventorySnapshot:
    if (
        isinstance(record_limit, bool)
        or not isinstance(record_limit, int)
        or not 1 <= record_limit <= MAX_PAGE_RECORDS
    ):
        raise ValueError("inventory request record limit is invalid")
    if not pages:
        raise ValueError("inventory page sequence must not be empty")
    if len(pages) > MAX_INVENTORY_PAGES:
        raise ValueError("inventory page sequence exceeds the page limit")
    if sum(len(page.records) for page in pages) > MAX_INVENTORY_RECORDS:
        raise ValueError(
            "inventory page sequence exceeds the record limit"
        )
    if any(len(page.records) > record_limit for page in pages):
        raise ValueError(
            "inventory page exceeds its request record limit"
        )

    first = pages[0]
    expected_cursor = None
    terminal = False
    records: list[InventoryRecord] = []
    previous_key: tuple[str, str] | None = None

    for page in pages:
        if terminal:
            raise ValueError("inventory page appears after terminal page")
        if page.request_cursor != expected_cursor:
            raise ValueError(
                "inventory page request cursor breaks the page chain"
            )
        if _page_header(page) != _page_header(first):
            raise ValueError("inventory page headers do not match")
        for record in page.records:
            key = (record.kind, record.id)
            if previous_key is not None and key <= previous_key:
                raise ValueError(
                    "inventory pages overlap or are not globally ordered"
                )
            previous_key = key
            records.append(record)
        expected_cursor = page.next_cursor
        terminal = page.complete

    if not terminal or expected_cursor is not None:
        raise ValueError("inventory page sequence is incomplete")

    snapshot = InventorySnapshot(
        kind="inventory_snapshot",
        inventory_version=first.inventory_version,
        schema_uri=INVENTORY_SCHEMA_URI,
        subject_uri=first.subject_uri,
        path_identity=first.path_identity,
        source_revision=first.source_revision,
        producer=first.producer,
        capability=first.capability,
        applied_policy=first.applied_policy,
        coverage=first.coverage,
        records=tuple(records),
    )
    actual_digest = hashlib.sha256(
        canonical_inventory_json(snapshot)
    ).hexdigest()
    if actual_digest != first.snapshot_digest.value:
        raise ValueError(
            "assembled inventory snapshot digest does not match its pages"
        )
    return snapshot


def _page_header(page: InventoryPage) -> tuple[object, ...]:
    return (
        page.inventory_version,
        page.schema_uri,
        page.subject_uri,
        page.path_identity,
        page.source_revision,
        page.snapshot_digest,
        page.producer,
        page.capability,
        page.applied_policy,
        page.coverage,
    )
