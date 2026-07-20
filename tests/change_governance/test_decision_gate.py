from __future__ import annotations

import pytest

from tests.change_governance._support import (
    additive_root_final,
    base_behavior,
    change_pair,
    root_loss_final,
)
from ucf.change_governance import (
    AssessmentBasis,
    ChangeGovernanceErrorCode,
    ChangeGovernanceValidationError,
    DecisionClass,
    DecisionClassAssessment,
    DecisionDisposition,
    DecisionEvidence,
    DecisionOutcome,
    DeclaredBasis,
    DeclaredDecision,
    GateStatus,
    canonical_change_governance_json,
    create_decision_assessment,
    create_decision_declaration,
    derive_impact_report,
    evaluate_change_gate,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
    validate_decision_declaration,
    validate_gate_evaluation,
)
from ucf.ir.models import Digest


def _digest(character: str = "a") -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=character * 64,
    )


def _classification(
    decision_class: DecisionClass,
    disposition: DecisionDisposition = DecisionDisposition.DOES_NOT_APPLY,
) -> DecisionClassAssessment:
    return DecisionClassAssessment(
        kind="decision_class_assessment",
        decision_class=decision_class,
        disposition=disposition,
        basis=AssessmentBasis.DECLARED,
        declared_basis=DeclaredBasis(
            kind="declared_basis",
            source_uri=f"urn:ucf:test:classification:{decision_class.value}",
            source_digest=_digest(),
            summary=f"classified {decision_class.value}",
        ),
    )


def _decision(
    decision_class: DecisionClass,
    outcome: DecisionOutcome,
) -> DeclaredDecision:
    return DeclaredDecision(
        kind="declared_decision",
        decision_class=decision_class,
        outcome=outcome,
        evidence=DecisionEvidence(
            kind="decision_evidence",
            source_uri=f"urn:ucf:test:decision:{decision_class.value}",
            source_digest=_digest("b"),
            summary=f"decided {decision_class.value}",
        ),
    )


def _chain(*, breaking: bool, unresolved: DecisionClass | None = None):
    base = base_behavior()
    final = root_loss_final(base) if breaking else additive_root_final(base)
    proposal, delta = change_pair(base, final)
    impact = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    declarations = tuple(
        _classification(
            decision_class,
            DecisionDisposition.UNRESOLVED
            if decision_class is unresolved
            else DecisionDisposition.DOES_NOT_APPLY,
        )
        for decision_class in DecisionClass
        if decision_class not in impact.derived_required_classes
    )
    assessment = create_decision_assessment(
        impact,
        declarations,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    return base, final, proposal, delta, impact, assessment


def test_compatible_change_passes_without_a_meaningless_declaration() -> None:
    base, final, proposal, delta, impact, assessment = _chain(breaking=False)

    gate = evaluate_change_gate(
        assessment,
        impact,
        None,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    assert gate.status is GateStatus.PASS_NO_DECISION
    assert gate.declaration is None
    assert gate.required_classes == ()
    assert gate.blockers == ()
    assert parse_gate_evaluation_json(canonical_change_governance_json(gate)) == gate
    assert (
        validate_gate_evaluation(
            gate,
            assessment,
            impact,
            None,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        == gate
    )

    with pytest.raises(ChangeGovernanceValidationError) as error:
        create_decision_declaration(
            assessment,
            impact,
            (),
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
    assert error.value.code is ChangeGovernanceErrorCode.DECISION_SET_MISMATCH


def test_breaking_change_blocks_until_exact_decision_then_preserves_rejection() -> None:
    base, final, proposal, delta, impact, assessment = _chain(breaking=True)

    missing = evaluate_change_gate(
        assessment,
        impact,
        None,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    assert missing.status is GateStatus.BLOCK_DECISION_REQUIRED
    assert missing.required_classes == (DecisionClass.PUBLIC_CONTRACT,)

    approved = create_decision_declaration(
        assessment,
        impact,
        (_decision(DecisionClass.PUBLIC_CONTRACT, DecisionOutcome.APPROVED),),
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    approved_gate = evaluate_change_gate(
        assessment,
        impact,
        approved,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    assert approved_gate.status is GateStatus.PASS_APPROVED
    assert (
        parse_decision_declaration_json(canonical_change_governance_json(approved))
        == approved
    )
    assert (
        validate_decision_declaration(
            approved,
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        == approved
    )

    rejected = create_decision_declaration(
        assessment,
        impact,
        (_decision(DecisionClass.PUBLIC_CONTRACT, DecisionOutcome.REJECTED),),
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    rejected_gate = evaluate_change_gate(
        assessment,
        impact,
        rejected,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    assert rejected_gate.status is GateStatus.BLOCK_REJECTED


def test_unresolved_class_blocks_and_cannot_be_approved_away() -> None:
    base, final, proposal, delta, impact, assessment = _chain(
        breaking=False,
        unresolved=DecisionClass.PRODUCT_SEMANTICS,
    )

    gate = evaluate_change_gate(
        assessment,
        impact,
        None,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    assert gate.status is GateStatus.BLOCK_UNRESOLVED
    assert [blocker.decision_class for blocker in gate.blockers] == [
        DecisionClass.PRODUCT_SEMANTICS
    ]
    with pytest.raises(ChangeGovernanceValidationError) as error:
        create_decision_declaration(
            assessment,
            impact,
            (
                _decision(
                    DecisionClass.PRODUCT_SEMANTICS,
                    DecisionOutcome.APPROVED,
                ),
            ),
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
    assert error.value.code is ChangeGovernanceErrorCode.UNRESOLVED_ASSESSMENT


def test_partial_and_extra_decision_sets_fail_explicitly() -> None:
    base, final, proposal, delta, impact, assessment = _chain(breaking=True)

    for decisions in (
        (),
        (
            _decision(
                DecisionClass.PUBLIC_CONTRACT,
                DecisionOutcome.APPROVED,
            ),
            _decision(
                DecisionClass.PRODUCTION_DEPENDENCY,
                DecisionOutcome.APPROVED,
            ),
        ),
    ):
        with pytest.raises(ChangeGovernanceValidationError) as error:
            create_decision_declaration(
                assessment,
                impact,
                decisions,
                proposal,
                delta,
                base_behavior=base,
                final_behavior=final,
            )
        assert error.value.code is ChangeGovernanceErrorCode.DECISION_SET_MISMATCH
