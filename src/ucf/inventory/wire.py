from __future__ import annotations

import json

from ucf.adapter_protocol import (
    AdapterPayload,
    ir_value_to_json_profile,
    json_profile_to_ir_value,
)
from ucf.inventory.models import (
    INVENTORY_PAGE_SCHEMA_URI,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    InventoryPage,
    InventoryRequest,
)


def inventory_request_to_payload(
    request: InventoryRequest,
) -> AdapterPayload:
    return _to_payload(request, INVENTORY_REQUEST_SCHEMA_URI)


def inventory_request_from_payload(
    payload: AdapterPayload,
) -> InventoryRequest:
    return _from_payload(
        payload,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        model=InventoryRequest,
    )


def inventory_page_to_payload(page: InventoryPage) -> AdapterPayload:
    return _to_payload(page, INVENTORY_PAGE_SCHEMA_URI)


def inventory_page_from_payload(payload: AdapterPayload) -> InventoryPage:
    return _from_payload(
        payload,
        schema_uri=INVENTORY_PAGE_SCHEMA_URI,
        model=InventoryPage,
    )


def _to_payload(document, schema_uri: str) -> AdapterPayload:
    return AdapterPayload(
        kind="adapter_payload",
        schema_uri=schema_uri,
        schema_version=INVENTORY_VERSION,
        value=json_profile_to_ir_value(
            document.model_dump(mode="json")
        ),
    )


def _from_payload(payload, *, schema_uri: str, model):
    if not isinstance(payload, AdapterPayload):
        raise ValueError("inventory payload must be an adapter payload")
    if (
        payload.schema_uri != schema_uri
        or payload.schema_version != INVENTORY_VERSION
    ):
        raise ValueError("inventory payload coordinates are incompatible")
    decoded = ir_value_to_json_profile(payload.value)
    if not isinstance(decoded, dict):
        raise ValueError("inventory payload root must be a record")
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)
