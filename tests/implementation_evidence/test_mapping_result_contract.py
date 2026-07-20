from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from tests.onboarding.test_bundle import _bundle
from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
    ImplementationBinding,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    ImplementationMappingResult,
    canonical_implementation_evidence_json,
    derive_implementation_mapping_result_id,
    parse_implementation_mapping_result_json,
)
from ucf.ir.models import Producer

from .test_mapping_request_contract import _mapping_request, _target_key


def _mapping_result() -> ImplementationMappingResult:
    request = _mapping_request()
    bundle = _bundle()
    materializations = {
        materialization.root: materialization
        for materialization in bundle.baseline.materializations
    }
    candidates = {
        candidate.id: candidate for candidate in bundle.discovery.candidates
    }
    bindings = tuple(
        ImplementationBinding(
            kind="implementation_binding",
            behavior=target,
            source_records=candidates[
                materializations[target].candidate.candidate_id
            ].evidence,
        )
        for target in request.targets
    )
    provisional = ImplementationMappingResult(
        kind="implementation_mapping_result",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
        id=f"mapping.{'0' * 64}",
        status="complete",
        request=request,
        producer=Producer(
            kind="producer",
            name="org.ucf.fixture-adapter",
            version="1.0.0",
        ),
        capability=CapabilitySelection(
            kind="capability",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        procedure_uri=request.adapter_procedure_uri,
        bindings=bindings,
    )
    return provisional.model_copy(
        update={"id": derive_implementation_mapping_result_id(provisional)}
    )


def test_mapping_result_is_content_identified_closed_and_canonical() -> None:
    result = _mapping_result()
    encoded = canonical_implementation_evidence_json(result)

    assert parse_implementation_mapping_result_json(encoded) == result
    assert (
        canonical_implementation_evidence_json(
            parse_implementation_mapping_result_json(encoded)
        )
        == encoded
    )
    assert result.id == derive_implementation_mapping_result_id(result)
    assert tuple(
        _target_key(binding.behavior) for binding in result.bindings
    ) == tuple(
        sorted(_target_key(binding.behavior) for binding in result.bindings)
    )
    serialized = json.dumps(
        [binding.model_dump(mode="json") for binding in result.bindings],
        sort_keys=True,
    )
    assert "claim" not in serialized
    assert "mapping_basis" not in serialized


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "version",
        "schema",
        "status",
        "capability",
        "procedure",
        "identity",
        "duplicate_binding",
        "noncanonical_binding",
        "duplicate_source",
    ],
)
def test_mapping_result_rejects_every_untrusted_structural_boundary(
    mutation: str,
) -> None:
    payload = _mapping_result().model_dump(mode="json")
    if mutation == "unknown":
        payload["claims"] = []
    elif mutation == "version":
        payload["implementation_evidence_version"] = "2.0.0"
    elif mutation == "schema":
        payload["schema_uri"] = (
            "urn:ucf:adapter:implementation-mapping-result:2.0.0"
        )
    elif mutation == "status":
        payload["status"] = "partial"
    elif mutation == "capability":
        payload["capability"]["name"] = "org.ucf.adapter.verification"
    elif mutation == "procedure":
        payload["procedure_uri"] = (
            "urn:ucf:fixture-adapter:other-mapping:1.0.0"
        )
    elif mutation == "identity":
        payload["id"] = f"mapping.{'f' * 64}"
    elif mutation == "duplicate_binding":
        payload["bindings"].append(payload["bindings"][0])
    elif mutation == "noncanonical_binding":
        payload["bindings"].reverse()
    else:
        payload["bindings"][0]["source_records"].append(
            payload["bindings"][0]["source_records"][0]
        )

    expected = (
        ImplementationEvidenceValidationError
        if mutation == "identity"
        else ValidationError
    )
    with pytest.raises(expected) as captured:
        parse_implementation_mapping_result_json(json.dumps(payload))
    if mutation == "identity":
        assert captured.value.code is (
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH
        )
