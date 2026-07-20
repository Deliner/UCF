from __future__ import annotations

import pytest

from ucf.adapter_protocol import AdapterPayload
from ucf.implementation_evidence import (
    execution_verification_request_from_payload,
    execution_verification_request_to_payload,
    execution_verification_result_from_payload,
    execution_verification_result_to_payload,
    implementation_mapping_request_from_payload,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    implementation_mapping_result_to_payload,
)
from ucf.ir.models import StringValue

from .test_mapping_request_contract import _mapping_request
from .test_mapping_result_contract import _mapping_result
from .test_verification_request_contract import _verification_request
from .test_verification_result_contract import _verification_result


@pytest.mark.parametrize(
    ("document", "encoder", "decoder"),
    [
        (
            _mapping_request,
            implementation_mapping_request_to_payload,
            implementation_mapping_request_from_payload,
        ),
        (
            _mapping_result,
            implementation_mapping_result_to_payload,
            implementation_mapping_result_from_payload,
        ),
        (
            _verification_request,
            execution_verification_request_to_payload,
            execution_verification_request_from_payload,
        ),
        (
            _verification_result,
            execution_verification_result_to_payload,
            execution_verification_result_from_payload,
        ),
    ],
)
def test_each_profile_round_trips_through_its_exact_adapter_payload(
    document,
    encoder,
    decoder,
) -> None:
    expected = document()

    assert decoder(encoder(expected)) == expected


@pytest.mark.parametrize(
    ("decoder", "payload"),
    [
        (
            implementation_mapping_request_from_payload,
            implementation_mapping_result_to_payload(_mapping_result()),
        ),
        (
            implementation_mapping_result_from_payload,
            execution_verification_request_to_payload(
                _verification_request()
            ),
        ),
        (
            execution_verification_request_from_payload,
            execution_verification_result_to_payload(_verification_result()),
        ),
        (
            execution_verification_result_from_payload,
            implementation_mapping_request_to_payload(_mapping_request()),
        ),
        (
            implementation_mapping_request_from_payload,
            AdapterPayload(
                kind="adapter_payload",
                schema_uri=(
                    "urn:ucf:adapter:implementation-mapping-request:1.0.0"
                ),
                schema_version="1.0.0",
                value=StringValue(kind="string", value="not-a-record"),
            ),
        ),
    ],
)
def test_wire_decoder_rejects_wrong_profile_or_nonrecord_root(
    decoder,
    payload: AdapterPayload,
) -> None:
    with pytest.raises(ValueError):
        decoder(payload)


def test_wire_decoder_rejects_incompatible_outer_version() -> None:
    payload = implementation_mapping_request_to_payload(
        _mapping_request()
    ).model_copy(update={"schema_version": "1.1.0"})

    with pytest.raises(ValueError, match="incompatible"):
        implementation_mapping_request_from_payload(payload)
