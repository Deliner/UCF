from __future__ import annotations

import json

from ucf.inventory.models import (
    IgnorePolicy,
    InventoryPage,
    InventoryRequest,
    InventorySnapshot,
)
from ucf.ir import decode_strict_json_object

type InventoryDocument = InventoryRequest | InventoryPage | InventorySnapshot


def canonical_inventory_json(document: InventoryDocument) -> bytes:
    return (
        json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def parse_inventory_snapshot_json(
    payload: str | bytes,
) -> InventorySnapshot:
    return _parse_inventory_json(payload, InventorySnapshot)


def parse_inventory_request_json(
    payload: str | bytes,
) -> InventoryRequest:
    return _parse_inventory_json(payload, InventoryRequest)


def parse_inventory_page_json(
    payload: str | bytes,
) -> InventoryPage:
    return _parse_inventory_json(payload, InventoryPage)


def parse_ignore_policy_json(payload: str | bytes) -> IgnorePolicy:
    return _parse_inventory_json(payload, IgnorePolicy)


def _parse_inventory_json(payload, model):
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)
