from __future__ import annotations

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import AdapterPayload
from ucf.ir.models import RecordEntry, RecordValue, StringValue
from ucf.onboarding import (
    DISCOVERY_REQUEST_SCHEMA_URI,
    DISCOVERY_RESULT_SCHEMA_URI,
    discovery_request_from_payload,
    discovery_request_to_payload,
    discovery_result_from_payload,
    discovery_result_to_payload,
)

from .test_codec import _request
from .test_decisions import _discovery


@pytest.mark.parametrize(
    ("document", "encode", "decode", "schema_uri"),
    [
        (
            _request,
            discovery_request_to_payload,
            discovery_request_from_payload,
            DISCOVERY_REQUEST_SCHEMA_URI,
        ),
        (
            _discovery,
            discovery_result_to_payload,
            discovery_result_from_payload,
            DISCOVERY_RESULT_SCHEMA_URI,
        ),
    ],
)
def test_discovery_profile_round_trips_through_generic_adapter_payload(
    document,
    encode,
    decode,
    schema_uri: str,
):
    expected = document()
    payload = encode(expected)

    assert isinstance(payload, AdapterPayload)
    assert payload.schema_uri == schema_uri
    assert payload.schema_version == "1.0.0"
    assert isinstance(payload.value, RecordValue)
    assert decode(payload) == expected


def test_discovery_wire_rejects_wrong_coordinates_and_ambiguous_records():
    payload = discovery_request_to_payload(_request())
    assert isinstance(payload.value, RecordValue)

    with pytest.raises(ValueError, match="coordinates"):
        discovery_request_from_payload(
            payload.model_copy(update={"schema_version": "1.0.1"})
        )
    reordered = payload.model_copy(
        update={
            "value": RecordValue(
                kind="record",
                entries=tuple(reversed(payload.value.entries)),
            )
        }
    )
    with pytest.raises(ValueError, match="sorted"):
        discovery_request_from_payload(reordered)
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
        discovery_request_from_payload(duplicate)


def test_generic_wire_does_not_make_the_profile_open():
    payload = discovery_result_to_payload(_discovery())
    assert isinstance(payload.value, RecordValue)
    entries = tuple(
        sorted(
            (
                *payload.value.entries,
                RecordEntry(
                    kind="record_entry",
                    name="future",
                    value=StringValue(kind="string", value="not accepted"),
                ),
            ),
            key=lambda entry: entry.name,
        )
    )
    changed = payload.model_copy(
        update={"value": RecordValue(kind="record", entries=entries)}
    )

    with pytest.raises(ValidationError):
        discovery_result_from_payload(changed)
