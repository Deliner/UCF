from __future__ import annotations

import pytest

from ucf.adapter_protocol import AdapterPayload
from ucf.ir.models import StringValue
from ucf.runtime_evidence import (
    runtime_evidence_request_from_payload,
    runtime_evidence_request_to_payload,
    runtime_evidence_result_from_payload,
    runtime_evidence_result_to_payload,
)

from .test_request_contract import _request
from .test_result_contract import _accepted, _rejected


def test_request_and_result_round_trip_through_exact_adapter_payloads() -> None:
    request = _request()
    accepted = _accepted()
    rejected = _rejected()

    assert runtime_evidence_request_from_payload(
        runtime_evidence_request_to_payload(request)
    ) == request
    assert runtime_evidence_result_from_payload(
        runtime_evidence_result_to_payload(accepted)
    ) == accepted
    assert runtime_evidence_result_from_payload(
        runtime_evidence_result_to_payload(rejected)
    ) == rejected


@pytest.mark.parametrize(
    ("decoder", "payload"),
    [
        (
            runtime_evidence_request_from_payload,
            runtime_evidence_result_to_payload(_accepted()),
        ),
        (
            runtime_evidence_result_from_payload,
            runtime_evidence_request_to_payload(_request()),
        ),
        (
            runtime_evidence_request_from_payload,
            AdapterPayload(
                kind="adapter_payload",
                schema_uri=(
                    "urn:ucf:adapter:runtime-evidence-request:1.0.0"
                ),
                schema_version="1.0.0",
                value=StringValue(kind="string", value="not-a-record"),
            ),
        ),
    ],
)
def test_wire_decoder_rejects_wrong_profile_or_root(
    decoder,
    payload: AdapterPayload,
) -> None:
    with pytest.raises(ValueError):
        decoder(payload)


def test_wire_decoder_rejects_incompatible_outer_version() -> None:
    payload = runtime_evidence_request_to_payload(_request()).model_copy(
        update={"schema_version": "1.1.0"}
    )

    with pytest.raises(ValueError, match="incompatible"):
        runtime_evidence_request_from_payload(payload)
