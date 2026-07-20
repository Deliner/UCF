from __future__ import annotations

import hashlib
import json

import pytest

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ExecutionEvidenceContext,
    canonical_change_lifecycle_json,
    derive_implementation_record,
    parse_implementation_record_json,
)
from ucf.implementation_evidence import (
    canonical_implementation_evidence_digest,
    derive_execution_verification_result_id,
)
from ucf.inventory import canonical_inventory_json
from ucf.ir.models import Producer
from ucf.onboarding import canonical_onboarding_digest

from ._fixture_factory import (
    behavior_pair,
    completed_graph,
    evidence_context,
    task_graph,
)

_BASE_BEHAVIOR, _FINAL_BEHAVIOR = behavior_pair()


def test_implementation_requires_fully_validated_execution_context() -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)

    record = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
        evidence_contexts=(context,),
    )
    assert record.bindings[0].result == context.result

    forged = context.result.model_copy(
        update={
            "producer": Producer(
                kind="producer",
                name="org.example.uninitialized",
                version="9.9.9",
            )
        }
    )
    forged = forged.model_copy(
        update={"id": derive_execution_verification_result_id(forged)}
    )
    forged_context = ExecutionEvidenceContext(
        result=forged,
        mapping_result=context.mapping_result,
        bundle=context.bundle,
        current_inventory=context.current_inventory,
        mapping_initialized_adapter=context.mapping_initialized_adapter,
        initialized_adapter=context.initialized_adapter,
        negotiated_capabilities=context.negotiated_capabilities,
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            evidence_contexts=(forged_context,),
        )
    assert captured.value.code is (ChangeLifecycleErrorCode.EVIDENCE_CONTEXT_INVALID)


def test_implementation_persists_context_validation_coordinates() -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)

    record = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
        evidence_contexts=(context,),
    )

    receipt = record.bindings[0].validation
    assert receipt.assurance == "context_validated_import"
    assert receipt.procedure_uri == (
        "urn:ucf:change-lifecycle:evidence-context-validation:1.0.0"
    )
    assert receipt.result_digest == (
        canonical_implementation_evidence_digest(context.result)
    )
    assert receipt.mapping_result_digest == (
        canonical_implementation_evidence_digest(context.mapping_result)
    )
    assert receipt.onboarding_bundle_digest == (
        canonical_onboarding_digest(context.bundle)
    )
    assert (
        receipt.current_inventory_digest.value
        == hashlib.sha256(
            canonical_inventory_json(context.current_inventory)
        ).hexdigest()
    )
    assert receipt.mapping_initialized_adapter == (context.mapping_initialized_adapter)
    assert receipt.verification_initialized_adapter == (context.initialized_adapter)
    assert tuple(
        (capability.name, capability.version)
        for capability in receipt.negotiated_capabilities
    ) == tuple(sorted(context.negotiated_capabilities.items()))


def test_implementation_wire_rejects_a_stale_validation_receipt() -> None:
    proposal, delta, graph = task_graph()
    context = evidence_context(delta)
    record = derive_implementation_record(
        completed_graph(
            graph,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        ),
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
        evidence_contexts=(context,),
    )
    payload = json.loads(canonical_change_lifecycle_json(record))
    payload["bindings"][0]["validation"]["result_digest"]["value"] = "0" * 64

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_implementation_record_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
