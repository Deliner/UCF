from __future__ import annotations

import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from tests.inventory.test_models import _snapshot
from ucf.adapter_protocol import CapabilitySelection
from ucf.inventory import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    InventoryRecordKind,
    InventoryRecordRef,
    PublicInterfaceFact,
    canonical_inventory_json,
)
from ucf.ir.models import Digest, Producer
from ucf.onboarding import (
    DISCOVERY_CAPABILITY,
    DISCOVERY_REQUEST_SCHEMA_URI,
    DISCOVERY_RESULT_SCHEMA_URI,
    ONBOARDING_VERSION,
    DiscoveryCoverage,
    DiscoveryRequest,
    DiscoveryResult,
    InventoryBinding,
    canonical_onboarding_json,
    parse_discovery_request_json,
    parse_discovery_result_json,
)


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def _binding() -> InventoryBinding:
    snapshot = _snapshot()
    return InventoryBinding(
        kind="inventory_binding",
        schema_uri=INVENTORY_SCHEMA_URI,
        inventory_version=INVENTORY_VERSION,
        subject_uri=snapshot.subject_uri,
        source_revision=snapshot.source_revision,
        canonical_digest=_digest(canonical_inventory_json(snapshot)),
    )


def _capability() -> CapabilitySelection:
    return CapabilitySelection(
        kind="capability",
        name=DISCOVERY_CAPABILITY,
        version=ONBOARDING_VERSION,
    )


def _interface_ref() -> InventoryRecordRef:
    interface = next(
        record
        for record in _snapshot().records
        if isinstance(record, PublicInterfaceFact)
    )
    return InventoryRecordRef(
        kind="inventory_record_ref",
        target_kind=InventoryRecordKind.PUBLIC_INTERFACE,
        target_id=interface.id,
    )


def _request() -> DiscoveryRequest:
    return DiscoveryRequest(
        kind="discovery_request_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DISCOVERY_REQUEST_SCHEMA_URI,
        capability=_capability(),
        inventory_binding=_binding(),
        inventory=_snapshot(),
    )


def _result() -> DiscoveryResult:
    return DiscoveryResult(
        kind="discovery_result_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DISCOVERY_RESULT_SCHEMA_URI,
        inventory_binding=_binding(),
        producer=Producer(
            kind="producer",
            name="org.ucf.python-reference-adapter",
            version="1.0.0",
        ),
        capability=_capability(),
        procedure_uri=(
            "urn:ucf:onboarding-procedure:python-ast-discovery:1.0.0"
        ),
        coverage=DiscoveryCoverage(
            kind="discovery_coverage",
            status="complete",
            eligible_subjects=(_interface_ref(),),
            uncovered_subjects=(),
        ),
        diagnostics=(),
        candidates=(),
    )


@pytest.mark.parametrize(
    ("document", "parser"),
    [
        (_request, parse_discovery_request_json),
        (_result, parse_discovery_result_json),
    ],
)
def test_discovery_profiles_have_canonical_strict_round_trips(
    document,
    parser,
):
    expected = document()
    encoded = canonical_onboarding_json(expected)

    assert encoded.endswith(b"\n")
    assert parser(encoded) == expected
    assert canonical_onboarding_json(parser(encoded)) == encoded


@pytest.mark.parametrize(
    ("document", "parser"),
    [
        (_request, parse_discovery_request_json),
        (_result, parse_discovery_result_json),
    ],
)
def test_discovery_profile_parser_rejects_duplicate_members(
    document,
    parser,
):
    encoded = canonical_onboarding_json(document())
    duplicate = encoded.replace(
        b'{"kind":',
        b'{"kind":"duplicate","kind":',
        1,
    )

    with pytest.raises(ValueError, match="duplicate"):
        parser(duplicate)


@pytest.mark.parametrize("document", [_request, _result])
def test_discovery_profiles_reject_unknown_fields(document):
    payload = document().model_dump(mode="json")
    payload["future"] = True

    with pytest.raises(ValidationError):
        type(document()).model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("document", "field", "value"),
    [
        (_request, "onboarding_version", "2.0.0"),
        (_request, "schema_uri", DISCOVERY_RESULT_SCHEMA_URI),
        (_result, "onboarding_version", "2.0.0"),
        (_result, "schema_uri", DISCOVERY_REQUEST_SCHEMA_URI),
    ],
)
def test_discovery_profiles_reject_unsupported_coordinates(
    document,
    field: str,
    value: str,
):
    payload = copy.deepcopy(document().model_dump(mode="json"))
    payload[field] = value

    with pytest.raises(ValidationError):
        type(document()).model_validate_json(json.dumps(payload))
