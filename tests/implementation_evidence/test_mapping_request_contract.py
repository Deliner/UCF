from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from tests.onboarding.test_bundle import _bundle
from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    IMPLEMENTATION_MAPPING_PROCEDURE_URI,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    ImplementationMappingRequest,
    OnboardingBundleBinding,
    canonical_implementation_evidence_json,
    parse_implementation_mapping_request_json,
)
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    canonical_onboarding_digest,
)


def _target_key(target) -> tuple[str, str]:
    return target.target_kind.value, target.target_id


def _mapping_request() -> ImplementationMappingRequest:
    bundle = _bundle()
    return ImplementationMappingRequest(
        kind="implementation_mapping_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=IMPLEMENTATION_MAPPING_PROCEDURE_URI,
        adapter_procedure_uri=(
            "urn:ucf:fixture-adapter:implementation-mapping:1.0.0"
        ),
        onboarding=OnboardingBundleBinding(
            kind="onboarding_bundle_binding",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        behavior=bundle.behavior,
        inventory=bundle.inventory,
        targets=tuple(
            sorted(
                (
                    materialization.root
                    for materialization in bundle.baseline.materializations
                ),
                key=_target_key,
            )
        ),
    )


def test_mapping_request_is_an_exact_canonical_closed_document() -> None:
    request = _mapping_request()
    encoded = canonical_implementation_evidence_json(request)

    assert encoded.endswith(b"\n")
    assert parse_implementation_mapping_request_json(encoded) == request
    assert (
        canonical_implementation_evidence_json(
            parse_implementation_mapping_request_json(encoded)
        )
        == encoded
    )
    assert request.targets == tuple(sorted(request.targets, key=_target_key))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("implementation_evidence_version",), "2.0.0"),
        (
            ("schema_uri",),
            "urn:ucf:adapter:implementation-mapping-request:2.0.0",
        ),
        (("capability", "name"), "org.ucf.adapter.verification"),
        (("capability", "version"), "2.0.0"),
        (
            ("profile_procedure_uri",),
            "urn:ucf:implementation-evidence:map:2.0.0",
        ),
        (("adapter_procedure_uri",), "not-versioned"),
    ],
)
def test_mapping_request_rejects_incompatible_coordinates(
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = _mapping_request().model_dump(mode="json")
    target = payload
    for coordinate in path[:-1]:
        target = target[coordinate]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        parse_implementation_mapping_request_json(json.dumps(payload))


def test_mapping_request_rejects_unknown_duplicate_and_noncanonical_data() -> None:
    payload = _mapping_request().model_dump(mode="json")
    payload["future"] = True
    with pytest.raises(ValidationError):
        parse_implementation_mapping_request_json(json.dumps(payload))

    encoded = canonical_implementation_evidence_json(_mapping_request())
    duplicate_member = encoded.replace(
        b'{"adapter_procedure_uri":',
        b'{"adapter_procedure_uri":"duplicate",'
        b'"adapter_procedure_uri":',
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_implementation_mapping_request_json(duplicate_member)

    duplicate_target = _mapping_request().model_dump(mode="json")
    duplicate_target["targets"].append(duplicate_target["targets"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        parse_implementation_mapping_request_json(
            json.dumps(duplicate_target)
        )

    reversed_targets = _mapping_request().model_dump(mode="json")
    reversed_targets["targets"].reverse()
    with pytest.raises(ValidationError, match="canonical order"):
        parse_implementation_mapping_request_json(
            json.dumps(reversed_targets)
        )

    empty_targets = _mapping_request().model_dump(mode="json")
    empty_targets["targets"] = []
    with pytest.raises(ValidationError):
        parse_implementation_mapping_request_json(json.dumps(empty_targets))
