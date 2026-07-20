from __future__ import annotations

import asyncio
from pathlib import Path

from tools.typescript_fastify_adapter_contract import (
    TypeScriptFastifyHarness,
    TypeScriptFastifyTarget,
    typescript_fastify_fixture_manifest,
)

from tests.ecosystems.test_typescript_fastify_discovery import (
    EXPECTED_SEMANTIC_DIGESTS,
    _collect,
)
from tests.ecosystems.test_typescript_fastify_inventory import (
    FAST_TIMEOUTS,
    SOURCE_REVISION,
    _request,
)
from ucf.adapter_protocol import (
    AdapterProcess,
    CapabilityRequest,
    CapabilitySelection,
    Method,
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
from ucf.inventory import collect_inventory_from_process
from ucf.ir import ClaimLevel
from ucf.ir.models import Digest, Producer
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    RejectedDecision,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    derive_decision_id,
)

MAPPING_PROCEDURE_URI = (
    "urn:ucf:adapter:typescript-fastify-static-mapping:1.0.0"
)


def test_typescript_fastify_maps_the_reviewed_quote_order_deterministically(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "mapping-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest
    assert len(before) == 7
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )
    assert len(bundle.baseline.materializations) == 1
    materialization = bundle.baseline.materializations[0]
    candidate = next(
        candidate
        for candidate in bundle.discovery.candidates
        if candidate.id == materialization.candidate.candidate_id
    )
    assert candidate.semantic_digest.value == EXPECTED_SEMANTIC_DIGESTS[
        "use-case.quote-order"
    ]
    assert _claim_ids(bundle, ClaimLevel.MAPPED) == ()

    request = _mapping_request(bundle)
    validate_implementation_mapping_request(request, bundle=bundle)

    first = _map(
        target=target,
        request=request,
        bundle=bundle,
        record_limit=7,
        hash_seed=1,
    )
    second = _map(
        target=target,
        request=request,
        bundle=bundle,
        record_limit=1,
        hash_seed=31_337,
    )

    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert first.stderr_bytes == second.stderr_bytes == 0
    assert first.stderr_tail == second.stderr_tail == b""
    assert first.inventory == second.inventory == bundle.inventory
    assert canonical_implementation_evidence_json(first.result) == (
        canonical_implementation_evidence_json(second.result)
    )
    assert first.result.request == request
    assert first.result.producer.name == (
        "org.ucf.adapter.typescript-fastify"
    )
    assert first.result.procedure_uri == MAPPING_PROCEDURE_URI
    assert first.result.bindings[0].behavior == materialization.root
    assert first.result.bindings[0].source_records == candidate.evidence
    assert len(first.result.bindings[0].source_records) == 5
    assert first.inventory.source_revision.value == SOURCE_REVISION
    assert _claim_ids(bundle, ClaimLevel.MAPPED) == ()
    assert typescript_fastify_fixture_manifest(target.fixture_root) == before


def _reviewed_bundle(
    *,
    target: TypeScriptFastifyTarget,
    stderr_path: Path,
):
    evidence = _collect(
        target=target,
        record_limit=7,
        hash_seed=1,
        stderr_path=stderr_path,
    )
    decisions = _quote_order_decisions(evidence.discovery)
    return build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        decisions,
    )


def _mapping_request(bundle) -> ImplementationMappingRequest:
    materialization = bundle.baseline.materializations[0]
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
        adapter_procedure_uri=MAPPING_PROCEDURE_URI,
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


class _MappingRun:
    def __init__(
        self,
        *,
        result,
        inventory,
        stderr_bytes: int,
        stderr_tail: bytes,
    ) -> None:
        self.result = result
        self.inventory = inventory
        self.stderr_bytes = stderr_bytes
        self.stderr_tail = stderr_tail


def _map(
    *,
    target: TypeScriptFastifyTarget,
    request: ImplementationMappingRequest,
    bundle,
    record_limit: int,
    hash_seed: int,
) -> _MappingRun:
    async def scenario() -> _MappingRun:
        adapter = AdapterProcess(
            command=target.command(hash_seed=hash_seed),
            cwd=target.fixture_root,
            requested_capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name="org.ucf.adapter.inventory",
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
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(record_limit),
                operation_timeout=10.0,
            )
            assert inventory == request.inventory
            payload = await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(request),
                timeout=10.0,
            )
            result = implementation_mapping_result_from_payload(payload)
            validate_implementation_mapping_result(
                result,
                request=request,
                bundle=bundle,
                current_inventory=inventory,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
        finally:
            await adapter.close()
        return _MappingRun(
            result=result,
            inventory=inventory,
            stderr_bytes=adapter.stderr_total_bytes,
            stderr_tail=adapter.stderr_tail,
        )

    return asyncio.run(scenario())


def _quote_order_decisions(discovery) -> DecisionSet:
    base = DecisionSet(
        kind="decision_set_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DECISION_SET_SCHEMA_URI,
        discovery=DiscoveryDocumentRef(
            kind="discovery_document_ref",
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=canonical_onboarding_digest(discovery),
        ),
        inventory_binding=discovery.inventory_binding,
        reviewer=Producer(
            kind="producer",
            name="org.ucf.ecosystem-reviewer",
            version="1.0.0",
        ),
        capture_context=CaptureContext(
            kind="capture_context",
            captured_at="2026-07-19T12:00:00Z",
            environment=Digest(
                kind="digest",
                algorithm="sha-256",
                value="a" * 64,
            ),
        ),
        decisions=(),
    )
    decisions = []
    for candidate in discovery.candidates:
        candidate_ref = CandidateRef(
            kind="candidate_ref",
            discovery_digest=canonical_onboarding_digest(discovery),
            candidate_id=candidate.id,
            semantic_digest=candidate.semantic_digest,
        )
        common = {
            "id": f"decision.{'0' * 64}",
            "candidate": candidate_ref,
        }
        if candidate.proposal.root.target_id == "use-case.quote-order":
            decision = AcceptedDecision(
                kind="accepted_decision",
                reason="Matches the frozen native HTTP behavior.",
                **common,
            )
        else:
            decision = RejectedDecision(
                kind="rejected_decision",
                reason="Outside the reviewed quote-order acceptance scope.",
                **common,
            )
        decisions.append(
            decision.model_copy(
                update={"id": derive_decision_id(decision, base)}
            )
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    decisions,
                    key=lambda item: item.candidate.candidate_id,
                )
            )
        }
    )


def _claim_ids(bundle, level: ClaimLevel) -> tuple[str, ...]:
    return next(
        summary.claim_ids
        for summary in bundle.baseline.claim_levels
        if summary.level is level
    )
