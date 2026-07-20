from __future__ import annotations

import pytest

from ucf.onboarding import (
    RejectedDecision,
    build_onboarding_bundle,
    derive_decision_id,
)
from ucf.ratchet import (
    EvaluationOutcome,
    RatchetErrorCode,
    RatchetValidationError,
    ViolationClassificationKind,
    advance_ratchet_baseline,
    derive_baseline_id,
    derive_evaluation_id,
    evaluate_ratchet,
    validate_successor_ratchet_baseline,
)

from .test_evaluation import _accepted, _current


def _without_quote_subject(bundle):
    changed = []
    for decision in bundle.decisions.decisions:
        candidate = next(
            candidate
            for candidate in bundle.discovery.candidates
            if candidate.id == decision.candidate.candidate_id
        )
        if candidate.proposal.root.target_id != "use-case.quote-order":
            changed.append(decision)
            continue
        changed.append(
            RejectedDecision(
                kind="rejected_decision",
                id=f"decision.{'0' * 64}",
                candidate=decision.candidate,
                reason="The behavior was removed from the current system.",
            )
        )
    provisional = bundle.decisions.model_copy(
        update={"decisions": tuple(changed)}
    )
    decisions = tuple(
        sorted(
            (
                decision.model_copy(
                    update={"id": derive_decision_id(decision, provisional)}
                )
                for decision in changed
            ),
            key=lambda item: item.candidate.candidate_id,
        )
    )
    return build_onboarding_bundle(
        bundle.inventory,
        bundle.discovery,
        provisional.model_copy(update={"decisions": decisions}),
    )


def test_passing_improvement_creates_exact_tightening_successor() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle)
    report = evaluate_ratchet(policy, baseline, bundle, current)

    successor = advance_ratchet_baseline(
        policy,
        baseline,
        bundle,
        current,
        report,
    )

    assert successor.generation == 1
    assert successor.predecessor is not None
    assert successor.predecessor.target_id == baseline.id
    assert successor.source_evaluation is not None
    assert successor.source_evaluation.target_id == report.id
    assert successor.source_assessment.target_id == current.id
    assert successor.allowances == ()
    assert [key.slot for key in successor.protected] == [
        "required-check"
    ]
    assert baseline.allowances
    assert baseline.protected == ()
    validate_successor_ratchet_baseline(
        policy,
        baseline,
        bundle,
        current,
        report,
        successor,
    )


def test_protected_resolution_reintroduction_fails() -> None:
    policy, bundle, baseline = _accepted()
    resolved = _current(policy, bundle)
    report = evaluate_ratchet(policy, baseline, bundle, resolved)
    successor = advance_ratchet_baseline(
        policy,
        baseline,
        bundle,
        resolved,
        report,
    )
    reintroduced = _current(policy, bundle, "required-check")

    result = evaluate_ratchet(
        policy,
        successor,
        bundle,
        reintroduced,
    )

    assert result.outcome is EvaluationOutcome.FAIL
    assert result.classifications[0].classification is (
        ViolationClassificationKind.REINTRODUCED
    )


@pytest.mark.parametrize("scenario", ["regression", "inconclusive"])
def test_non_passing_evaluation_cannot_advance(scenario: str) -> None:
    policy, bundle, baseline = _accepted()
    if scenario == "regression":
        current = _current(
            policy,
            bundle,
            "required-check",
            "second-check",
        )
        expected = RatchetErrorCode.ILLEGAL_WEAKENING
    else:
        current = _current(policy, bundle, partial=True)
        expected = RatchetErrorCode.INCOMPLETE_COVERAGE
    report = evaluate_ratchet(policy, baseline, bundle, current)

    with pytest.raises(RatchetValidationError) as captured:
        advance_ratchet_baseline(
            policy,
            baseline,
            bundle,
            current,
            report,
        )

    assert captured.value.code is expected


def test_advance_recomputes_and_rejects_a_forged_report() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle)
    report = evaluate_ratchet(policy, baseline, bundle, current)
    forged = report.model_copy(
        update={"outcome": EvaluationOutcome.INCONCLUSIVE}
    )
    forged = forged.model_copy(
        update={"id": derive_evaluation_id(forged)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        advance_ratchet_baseline(
            policy,
            baseline,
            bundle,
            current,
            forged,
        )

    assert captured.value.code is RatchetErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == "$.outcome"


@pytest.mark.parametrize("mutation", ["allowance", "protection"])
def test_successor_validation_rejects_implicit_weakening(
    mutation: str,
) -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle)
    report = evaluate_ratchet(policy, baseline, bundle, current)
    successor = advance_ratchet_baseline(
        policy,
        baseline,
        bundle,
        current,
        report,
    )
    if mutation == "allowance":
        forged = successor.model_copy(
            update={"allowances": baseline.allowances}
        )
        location = "$.allowances"
    else:
        forged = successor.model_copy(update={"protected": ()})
        location = "$.protected"
    forged = forged.model_copy(
        update={"id": derive_baseline_id(forged)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        validate_successor_ratchet_baseline(
            policy,
            baseline,
            bundle,
            current,
            report,
            forged,
        )

    assert captured.value.code is RatchetErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == location


def test_removed_subject_resolution_remains_historically_protected() -> None:
    policy, bundle, baseline = _accepted()
    reduced_bundle = _without_quote_subject(bundle)
    current = _current(policy, reduced_bundle)
    report = evaluate_ratchet(
        policy,
        baseline,
        reduced_bundle,
        current,
    )

    successor = advance_ratchet_baseline(
        policy,
        baseline,
        reduced_bundle,
        current,
        report,
    )

    assert [change.change for change in report.subject_changes] == [
        "removed_subject",
        "unchanged",
    ]
    assert successor.allowances == ()
    assert [key.slot for key in successor.protected] == [
        "required-check"
    ]
    assert all(
        key.subject.target_id
        not in {subject.id for subject in successor.subjects}
        for key in successor.protected
    )
