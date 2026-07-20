from __future__ import annotations

import pytest

from ucf.inventory import (
    InventoryConfidence,
    InventoryRecordKind,
    InventoryRecordRef,
    PublicInterfaceFact,
)
from ucf.ir.models import Port, ValueKind
from ucf.onboarding import (
    CandidateProposal,
    DiscoveryCandidate,
    DiscoveryDiagnostic,
    OnboardingErrorCode,
    OnboardingValidationError,
    ProposalEntityKind,
    ProposalEntityRef,
    ProposalPortRef,
    ProposedAction,
    ProposedBinding,
    ProposedStep,
    ProposedUseCase,
    derive_candidate_semantic_digest,
    derive_discovery_candidate_id,
    validate_discovery_exchange,
)

from .test_codec import _request, _result

_ZERO = "0" * 64


def _evidence_ref() -> InventoryRecordRef:
    interface = next(
        record
        for record in _request().inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    return InventoryRecordRef(
        kind="inventory_record_ref",
        target_kind=InventoryRecordKind.PUBLIC_INTERFACE,
        target_id=interface.id,
    )


def _proposal(suffix: str = "quote-order") -> CandidateProposal:
    action_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.ACTION,
        target_id=f"action.{suffix}",
    )
    use_case_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.USE_CASE,
        target_id=f"use-case.{suffix}",
    )
    step_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.STEP,
        target_id=f"step.{suffix}",
    )
    binding_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.BINDING,
        target_id=f"binding.{suffix}.quantity",
    )
    input_ports = (
        Port(
            kind="port",
            name="quantity",
            value_kind=ValueKind.INTEGER,
            required=True,
        ),
    )
    output_ports = (
        Port(
            kind="port",
            name="total-cents",
            value_kind=ValueKind.INTEGER,
            required=True,
        ),
    )
    entities = (
        ProposedAction(
            kind=ProposalEntityKind.ACTION,
            id=action_ref.target_id,
            input_ports=input_ports,
            output_ports=output_ports,
        ),
        ProposedBinding(
            kind=ProposalEntityKind.BINDING,
            id=binding_ref.target_id,
            target=ProposalPortRef(
                kind="proposal_port_ref",
                owner=step_ref,
                direction="input",
                name="quantity",
            ),
            source=ProposalPortRef(
                kind="proposal_port_ref",
                owner=use_case_ref,
                direction="input",
                name="quantity",
            ),
        ),
        ProposedStep(
            kind=ProposalEntityKind.STEP,
            id=step_ref.target_id,
            action=action_ref,
            bindings=(binding_ref,),
        ),
        ProposedUseCase(
            kind=ProposalEntityKind.USE_CASE,
            id=use_case_ref.target_id,
            input_ports=input_ports,
            output_ports=output_ports,
            steps=(step_ref,),
        ),
    )
    return CandidateProposal(
        kind="candidate_proposal",
        root=use_case_ref,
        entities=tuple(
            sorted(entities, key=lambda entity: (entity.kind, entity.id))
        ),
    )


def _candidate(
    suffix: str = "quote-order",
    *,
    evidence: tuple[InventoryRecordRef, ...] | None = None,
    confidence: str = "0.82",
) -> DiscoveryCandidate:
    proposal = _proposal(suffix)
    candidate = DiscoveryCandidate(
        kind="discovery_candidate",
        id=f"candidate.{_ZERO}",
        semantic_digest=derive_candidate_semantic_digest(proposal),
        subject=_evidence_ref(),
        evidence=evidence or (_evidence_ref(),),
        confidence=InventoryConfidence(
            kind="confidence",
            scale="decimal-0-to-1",
            value=confidence,
            basis=(
                "urn:ucf:onboarding-confidence:"
                "python-public-function:1.0.0"
            ),
        ),
        proposal=proposal,
    )
    return candidate.model_copy(
        update={
            "id": derive_discovery_candidate_id(candidate, _result()),
        }
    )


def _validate(*candidates: DiscoveryCandidate) -> None:
    validate_discovery_exchange(
        _request(),
        _result().model_copy(update={"candidates": candidates}),
    )


def _diagnostic(
    suffix: str,
    *,
    evidence: InventoryRecordRef | None = None,
) -> DiscoveryDiagnostic:
    return DiscoveryDiagnostic(
        kind="discovery_diagnostic",
        id=f"diagnostic.{suffix * 64}",
        severity="warning",
        code="org.ucf.discovery.review",
        message=f"Review diagnostic {suffix}.",
        evidence=_evidence_ref() if evidence is None else evidence,
    )


def test_candidate_graph_has_content_identity_and_resolved_evidence():
    candidate = _candidate()

    _validate(candidate)
    assert candidate.id.startswith("candidate.")
    assert candidate.semantic_digest == derive_candidate_semantic_digest(
        candidate.proposal
    )


def test_forged_candidate_identity_is_rejected():
    candidate = _candidate().model_copy(
        update={"id": f"candidate.{'f' * 64}"}
    )

    with pytest.raises(OnboardingValidationError) as captured:
        _validate(candidate)

    assert captured.value.code is (
        OnboardingErrorCode.CONTENT_IDENTITY_MISMATCH
    )
    assert captured.value.location == "$.candidates[0].id"


def test_candidate_with_broken_inventory_reference_is_rejected():
    broken = InventoryRecordRef(
        kind="inventory_record_ref",
        target_kind=InventoryRecordKind.PUBLIC_INTERFACE,
        target_id=f"interface.{'f' * 64}",
    )
    candidate = _candidate(evidence=(broken,))

    with pytest.raises(OnboardingValidationError) as captured:
        _validate(candidate)

    assert captured.value.code is OnboardingErrorCode.BROKEN_REFERENCE
    assert captured.value.location == "$.candidates[0].evidence[0]"


def test_candidate_with_wrong_inventory_target_kind_is_rejected():
    evidence = _evidence_ref().model_copy(
        update={"target_kind": InventoryRecordKind.TEST_ASSET}
    )
    candidate = _candidate(evidence=(evidence,))

    with pytest.raises(OnboardingValidationError) as captured:
        _validate(candidate)

    assert captured.value.code is OnboardingErrorCode.WRONG_TARGET_KIND
    assert captured.value.location == "$.candidates[0].evidence[0]"


def test_semantically_duplicate_candidates_are_rejected():
    first = _candidate(confidence="0.82")
    second = _candidate(confidence="0.61")
    ordered = tuple(sorted((first, second), key=lambda item: item.id))

    with pytest.raises(OnboardingValidationError) as captured:
        _validate(*ordered)

    assert captured.value.code is OnboardingErrorCode.DUPLICATE_IDENTITY
    assert captured.value.location == "$.candidates"


def test_candidates_must_be_in_canonical_content_identity_order():
    first = _candidate("quote-order")
    second = _candidate("format-receipt")
    canonical = tuple(sorted((first, second), key=lambda item: item.id))
    assert canonical[0].id != canonical[1].id

    with pytest.raises(OnboardingValidationError) as captured:
        _validate(*reversed(canonical))

    assert captured.value.code is OnboardingErrorCode.NON_CANONICAL_ORDER
    assert captured.value.location == "$.candidates"


def test_complete_coverage_requires_a_candidate_for_every_eligible_subject():
    with pytest.raises(OnboardingValidationError) as captured:
        _validate()

    assert captured.value.code is OnboardingErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == "$.coverage"


def test_partial_coverage_may_retain_an_explicit_uncovered_subject():
    base = _result()
    result = base.model_copy(
        update={
            "coverage": base.coverage.model_copy(
                update={
                    "status": "partial",
                    "uncovered_subjects": (_evidence_ref(),),
                }
            )
        }
    )

    validate_discovery_exchange(_request(), result)


def test_discovery_diagnostic_ids_must_be_unique():
    diagnostic = _diagnostic("a")
    result = _result().model_copy(
        update={
            "candidates": (_candidate(),),
            "diagnostics": (
                diagnostic,
                diagnostic.model_copy(update={"message": "Duplicate ID."}),
            ),
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_discovery_exchange(_request(), result)

    assert captured.value.code is OnboardingErrorCode.DUPLICATE_IDENTITY
    assert captured.value.location == "$.diagnostics"


def test_discovery_diagnostic_evidence_must_resolve():
    broken = InventoryRecordRef(
        kind="inventory_record_ref",
        target_kind=InventoryRecordKind.PUBLIC_INTERFACE,
        target_id=f"interface.{'f' * 64}",
    )
    result = _result().model_copy(
        update={
            "candidates": (_candidate(),),
            "diagnostics": (_diagnostic("a", evidence=broken),),
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_discovery_exchange(_request(), result)

    assert captured.value.code is OnboardingErrorCode.BROKEN_REFERENCE
    assert captured.value.location == "$.diagnostics[0].evidence"


def test_discovery_diagnostic_evidence_kind_must_match_target():
    wrong_kind = _evidence_ref().model_copy(
        update={"target_kind": InventoryRecordKind.TEST_ASSET}
    )
    result = _result().model_copy(
        update={
            "candidates": (_candidate(),),
            "diagnostics": (_diagnostic("a", evidence=wrong_kind),),
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_discovery_exchange(_request(), result)

    assert captured.value.code is OnboardingErrorCode.WRONG_TARGET_KIND
    assert captured.value.location == "$.diagnostics[0].evidence"


def test_discovery_diagnostics_must_be_in_canonical_id_order():
    result = _result().model_copy(
        update={
            "candidates": (_candidate(),),
            "diagnostics": (_diagnostic("f"), _diagnostic("a")),
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_discovery_exchange(_request(), result)

    assert captured.value.code is OnboardingErrorCode.NON_CANONICAL_ORDER
    assert captured.value.location == "$.diagnostics"
