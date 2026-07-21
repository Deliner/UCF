from __future__ import annotations

import asyncio
import copy
import json
import sys
from functools import lru_cache

import pytest

from tests.fixtures.adapters.inventory_reference.implementation_evidence import (
    MAPPING_ADAPTER_PROCEDURE_URI,
    PRODUCER,
    ProfileError,
    build_mapping_payload,
    decode_adapter_payload,
    encode_adapter_payload,
)
from tests.onboarding.test_decisions import _decisions
from tests.onboarding.test_process_client import (
    FIXTURE_ROOT,
    REFERENCE_ADAPTER,
    _collect,
    _request,
)
from ucf.adapter_protocol import (
    AdapterPayload,
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    Method,
    ProtocolCode,
)
from ucf.implementation_evidence import (
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    IMPLEMENTATION_MAPPING_PROCEDURE_URI,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    ImplementationMappingRequest,
    OnboardingBundleBinding,
    canonical_implementation_evidence_json,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    validate_implementation_mapping_request,
    validate_implementation_mapping_result,
)
from ucf.inventory import INVENTORY_CAPABILITY, collect_inventory_from_process
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    derive_discovery_candidate_id,
)

QUOTE_ORDER_INTERFACE_ID = (
    "interface.717f2925dd9050686aabed41e46e691f9dbddcc8ccebe3118c8a34713715cf46"
)
QUOTE_ORDER_SEMANTIC_DIGEST = (
    "cd09cf6ac27457ddbd62715ad903b4b3e0217c6b580cbde1d75c8d2c1b17153a"
)


@lru_cache(maxsize=1)
def _reviewed_bundle():
    evidence = _collect(record_limit=7)
    return build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _decisions(evidence.discovery),
    )


def _mapping_request(bundle=None) -> ImplementationMappingRequest:
    bundle = _reviewed_bundle() if bundle is None else bundle
    materialization = _quote_order_materialization(bundle)
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
        adapter_procedure_uri=MAPPING_ADAPTER_PROCEDURE_URI,
        onboarding=OnboardingBundleBinding(
            kind="onboarding_bundle_binding",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        behavior=bundle.behavior,
        inventory=bundle.inventory,
        targets=(materialization.root,),
    )


def _quote_order_materialization(bundle):
    return next(
        item
        for item in bundle.baseline.materializations
        if item.root.target_id == "use-case.quote-order"
    )


def _mapping_product(request: ImplementationMappingRequest | None = None):
    request = _mapping_request() if request is None else request
    payload = implementation_mapping_request_to_payload(request).model_dump(mode="json")
    return build_mapping_payload(
        payload,
        current_inventory=request.inventory.model_dump(mode="json"),
    )


def _mapping_result(request: ImplementationMappingRequest | None = None):
    product = _mapping_product(request)
    return implementation_mapping_result_from_payload(
        AdapterPayload.model_validate_json(json.dumps(product.payload))
    )


def test_python_reference_maps_exact_reviewed_interface_deterministically():
    bundle = _reviewed_bundle()
    assert len(bundle.baseline.materializations) == 2
    assert {
        summary.disposition.value: len(summary.candidate_ids)
        for summary in bundle.baseline.dispositions
    } == {"accepted": 1, "edited": 1, "rejected": 1, "uncertain": 1}
    request = _mapping_request(bundle)
    validate_implementation_mapping_request(request, bundle=bundle)

    first = _mapping_product(request)
    second = _mapping_product(request)
    first_result = implementation_mapping_result_from_payload(
        AdapterPayload.model_validate_json(json.dumps(first.payload))
    )
    second_result = implementation_mapping_result_from_payload(
        AdapterPayload.model_validate_json(json.dumps(second.payload))
    )
    materialization = _quote_order_materialization(bundle)
    candidate = next(
        item
        for item in bundle.discovery.candidates
        if item.id == materialization.candidate.candidate_id
    )

    assert candidate.id == derive_discovery_candidate_id(
        candidate,
        bundle.discovery,
    )
    assert candidate.semantic_digest.value == QUOTE_ORDER_SEMANTIC_DIGEST
    assert canonical_implementation_evidence_json(first_result) == (
        canonical_implementation_evidence_json(second_result)
    )
    assert first_result.request == request
    assert first_result.producer.model_dump(mode="json") == PRODUCER
    assert first_result.procedure_uri == MAPPING_ADAPTER_PROCEDURE_URI
    assert len(first_result.bindings) == 1
    assert first_result.bindings[0].behavior == materialization.root
    assert first_result.bindings[0].source_records == candidate.evidence
    assert [
        (item.target_kind.value, item.target_id)
        for item in first_result.bindings[0].source_records
    ] == [("public_interface", QUOTE_ORDER_INTERFACE_ID)]
    assert "claims" not in first_result.model_dump(mode="json")

    validate_implementation_mapping_result(
        first_result,
        request=request,
        bundle=bundle,
        current_inventory=bundle.inventory,
        initialized_adapter=first_result.producer,
        negotiated_capabilities={IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0"},
    )


def test_python_reference_adapter_maps_through_the_real_process() -> None:
    bundle = _reviewed_bundle()
    request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
            ),
            cwd=FIXTURE_ROOT,
            requested_capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name=INVENTORY_CAPABILITY,
                    minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                    required=True,
                ),
                CapabilityRequest(
                    kind="capability_request",
                    name=IMPLEMENTATION_MAPPING_CAPABILITY,
                    minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                    required=True,
                ),
            ),
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=5.0,
            )
            payload = await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(request),
                timeout=5.0,
            )
            result = implementation_mapping_result_from_payload(payload)
        finally:
            await adapter.close()
        return initialized, inventory, result, adapter

    initialized, inventory, result, adapter = asyncio.run(scenario())

    assert inventory == bundle.inventory
    assert result == _mapping_result(request)
    validate_implementation_mapping_result(
        result,
        request=request,
        bundle=bundle,
        current_inventory=inventory,
        initialized_adapter=initialized.adapter,
        negotiated_capabilities=adapter.negotiated_capabilities,
    )
    assert adapter.stderr_total_bytes == 0


def test_python_reference_map_observes_targeted_process_cancellation() -> None:
    bundle = _reviewed_bundle()
    request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
                "--mode",
                "block-map",
            ),
            cwd=FIXTURE_ROOT,
            requested_capabilities=tuple(
                CapabilityRequest(
                    kind="capability_request",
                    name=name,
                    minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                    required=True,
                )
                for name in (
                    INVENTORY_CAPABILITY,
                    IMPLEMENTATION_MAPPING_CAPABILITY,
                )
            ),
        )
        try:
            await adapter.start()
            await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=5.0,
            )
            call = await adapter.begin(
                Method.MAP,
                implementation_mapping_request_to_payload(request),
            )
            with pytest.raises(AdapterProtocolError) as cancelled:
                await call.cancel()
            assert cancelled.value.request_id == call.request_id
            assert cancelled.value.category is ErrorCategory.CANCELLED
            assert cancelled.value.code is ProtocolCode.REQUEST_CANCELLED
        finally:
            await adapter.close()
        return adapter

    adapter = asyncio.run(scenario())

    assert adapter.stderr_total_bytes == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "capability",
        "profile-procedure",
        "adapter-procedure",
        "inventory",
        "target",
        "graph",
        "unknown",
    ],
)
def test_python_reference_mapping_rejects_rebound_profile_before_result(
    mutation: str,
):
    request = _mapping_request()
    logical = request.model_dump(mode="json")
    current_inventory = copy.deepcopy(logical["inventory"])
    if mutation == "version":
        logical["implementation_evidence_version"] = "2.0.0"
    elif mutation == "capability":
        logical["capability"]["name"] = "org.ucf.adapter.verification"
    elif mutation == "profile-procedure":
        logical["profile_procedure_uri"] = "urn:ucf:implementation-evidence:map:2.0.0"
    elif mutation == "adapter-procedure":
        logical["adapter_procedure_uri"] = (
            "urn:ucf:adapter:python-reference-other:1.0.0"
        )
    elif mutation == "inventory":
        logical["inventory"]["source_revision"]["value"] = "f" * 64
    elif mutation == "target":
        logical["targets"][0]["target_id"] = "use-case.other"
    elif mutation == "graph":
        use_case = next(
            entity
            for entity in logical["behavior"]["entities"]
            if entity["id"] == "use-case.quote-order"
        )
        use_case["input_ports"][0]["name"] = "count"
    else:
        logical["future"] = True

    payload = encode_adapter_payload(
        logical,
        schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    )
    with pytest.raises(ProfileError) as captured:
        build_mapping_payload(
            payload,
            current_inventory=current_inventory,
        )

    assert captured.value.code == "invalid_params"


def test_python_reference_mapping_rejects_noncanonical_tagged_records():
    request = _mapping_request()
    payload = implementation_mapping_request_to_payload(request).model_dump(mode="json")
    entries = payload["value"]["entries"]
    entries[0], entries[1] = entries[1], entries[0]

    with pytest.raises(ProfileError) as captured:
        build_mapping_payload(
            payload,
            current_inventory=request.inventory.model_dump(mode="json"),
        )

    assert captured.value.code == "invalid_params"


def test_python_reference_mapping_payload_round_trips_closed_logical_json():
    request = _mapping_request()
    payload = implementation_mapping_request_to_payload(request).model_dump(mode="json")

    assert decode_adapter_payload(
        payload,
        expected_schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    ) == request.model_dump(mode="json")
