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
    DeclaredBasis,
    canonical_change_governance_json,
    create_decision_assessment,
    derive_impact_report,
    parse_decision_assessment_json,
    validate_decision_assessment,
)
from ucf.ir.models import Digest


def _basis(decision_class: DecisionClass) -> DeclaredBasis:
    return DeclaredBasis(
        kind="declared_basis",
        source_uri=f"urn:ucf:test:assessment:{decision_class.value}",
        source_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value="a" * 64,
        ),
        summary=f"reviewed {decision_class.value}",
    )


def _declared(
    decision_class: DecisionClass,
    disposition: DecisionDisposition = DecisionDisposition.DOES_NOT_APPLY,
) -> DecisionClassAssessment:
    return DecisionClassAssessment(
        kind="decision_class_assessment",
        decision_class=decision_class,
        disposition=disposition,
        basis=AssessmentBasis.DECLARED,
        declared_basis=_basis(decision_class),
    )


def _impact(*, breaking: bool):
    base = base_behavior()
    final = root_loss_final(base) if breaking else additive_root_final(base)
    proposal, delta = change_pair(base, final)
    impact = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    return base, final, proposal, delta, impact


def test_compatible_assessment_requires_all_six_explicit_classifications() -> None:
    base, final, proposal, delta, impact = _impact(breaking=False)
    declarations = tuple(_declared(item) for item in DecisionClass)

    assessment = create_decision_assessment(
        impact,
        declarations,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    assert len(assessment.assessments) == 6
    assert all(
        item.basis is AssessmentBasis.DECLARED
        and item.disposition is DecisionDisposition.DOES_NOT_APPLY
        for item in assessment.assessments
    )
    assert (
        parse_decision_assessment_json(canonical_change_governance_json(assessment))
        == assessment
    )
    assert (
        validate_decision_assessment(
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        == assessment
    )

    with pytest.raises(ChangeGovernanceValidationError) as error:
        create_decision_assessment(
            impact,
            declarations[:-1],
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
    assert error.value.code is ChangeGovernanceErrorCode.INCOMPLETE_ASSESSMENT


def test_structural_break_forces_public_contract_applies_and_cannot_downgrade() -> None:
    base, final, proposal, delta, impact = _impact(breaking=True)
    declarations = tuple(
        _declared(item)
        for item in DecisionClass
        if item is not DecisionClass.PUBLIC_CONTRACT
    )

    assessment = create_decision_assessment(
        impact,
        declarations,
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    public = assessment.assessments[0]
    assert public.decision_class is DecisionClass.PUBLIC_CONTRACT
    assert public.disposition is DecisionDisposition.APPLIES
    assert public.basis is AssessmentBasis.DERIVED
    assert public.declared_basis is None

    with pytest.raises(ChangeGovernanceValidationError) as error:
        create_decision_assessment(
            impact,
            (_declared(DecisionClass.PUBLIC_CONTRACT), *declarations),
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
    assert error.value.code is ChangeGovernanceErrorCode.DERIVED_CLASS_MISMATCH


def test_assessment_is_bound_to_the_exact_impact_bytes() -> None:
    base, final, proposal, delta, impact = _impact(breaking=False)
    assessment = create_decision_assessment(
        impact,
        tuple(_declared(item) for item in DecisionClass),
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    forged = assessment.model_copy(
        update={
            "impact": assessment.impact.model_copy(
                update={
                    "canonical_digest": Digest(
                        kind="digest",
                        algorithm="sha-256",
                        value="f" * 64,
                    )
                }
            )
        }
    )

    with pytest.raises(ChangeGovernanceValidationError) as error:
        validate_decision_assessment(
            forged,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )

    assert error.value.code is ChangeGovernanceErrorCode.CONTENT_IDENTITY_MISMATCH
