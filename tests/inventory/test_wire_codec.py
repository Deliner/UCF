from __future__ import annotations

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import AdapterPayload
from ucf.inventory import (
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    IgnorePolicy,
    IgnoreRule,
    InventoryPageRequest,
    InventoryRequest,
    PathSegmentMatcher,
    inventory_request_from_payload,
    inventory_request_to_payload,
)
from ucf.ir.models import RecordEntry, RecordValue, StringValue


def _request() -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version="1.0.0",
            rules=(
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
            record_limit=64,
            cursor=None,
        ),
    )


def test_inventory_request_round_trips_through_tagged_adapter_payload():
    request = _request()
    payload = inventory_request_to_payload(request)

    assert isinstance(payload, AdapterPayload)
    assert payload.schema_uri == INVENTORY_REQUEST_SCHEMA_URI
    assert payload.schema_version == INVENTORY_VERSION
    assert isinstance(payload.value, RecordValue)
    names = tuple(entry.name for entry in payload.value.entries)
    assert names == tuple(sorted(names))
    assert inventory_request_from_payload(payload) == request


def test_inventory_wire_rejects_wrong_coordinates_and_ambiguous_records():
    payload = inventory_request_to_payload(_request())
    assert isinstance(payload.value, RecordValue)

    wrong_uri = payload.model_copy(
        update={"schema_uri": "urn:ucf:adapter:other:1.0.0"}
    )
    with pytest.raises(ValueError, match="coordinates"):
        inventory_request_from_payload(wrong_uri)

    wrong_version = payload.model_copy(update={"schema_version": "1.0.1"})
    with pytest.raises(ValueError, match="coordinates"):
        inventory_request_from_payload(wrong_version)

    reordered = payload.model_copy(
        update={
            "value": RecordValue(
                kind="record",
                entries=tuple(reversed(payload.value.entries)),
            )
        }
    )
    with pytest.raises(ValueError, match="sorted"):
        inventory_request_from_payload(reordered)

    duplicate = payload.model_copy(
        update={
            "value": RecordValue(
                kind="record",
                entries=(
                    payload.value.entries[0],
                    payload.value.entries[0],
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="duplicate"):
        inventory_request_from_payload(duplicate)


def test_inventory_wire_rejects_untagged_shape_and_unknown_logical_field():
    payload = inventory_request_to_payload(_request())
    assert isinstance(payload.value, RecordValue)

    scalar = payload.model_copy(
        update={"value": StringValue(kind="string", value="not a record")}
    )
    with pytest.raises(ValueError, match="record"):
        inventory_request_from_payload(scalar)

    entries = tuple(
        sorted(
            (
                *payload.value.entries,
                RecordEntry(
                    kind="record_entry",
                    name="future",
                    value=StringValue(kind="string", value="unknown"),
                ),
            ),
            key=lambda entry: entry.name,
        )
    )
    unknown = payload.model_copy(
        update={"value": RecordValue(kind="record", entries=entries)}
    )
    with pytest.raises(ValidationError):
        inventory_request_from_payload(unknown)
