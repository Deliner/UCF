from __future__ import annotations

import pytest

from ucf.ir.models import EntityKind
from ucf.ratchet import (
    BehaviorSubjectKey,
    EvaluationOutcome,
    RatchetErrorCode,
    RatchetValidationError,
    ViolationClassificationKind,
    ViolationInput,
    WeakeningDeltaStatus,
    advance_ratchet_baseline,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_baseline_id,
    derive_evaluation_id,
    establish_ratchet_baseline,
    evaluate_ratchet,
    parse_ratchet_evaluation_report_json,
    validate_ratchet_evaluation_report,
)

from .test_assessment import _assessment, _capture_context


def _current(policy, bundle, *slots: str, partial: bool = False):
    subject = BehaviorSubjectKey(
        kind="behavior_subject_key",
        subject_uri=bundle.inventory.subject_uri,
        target_kind=EntityKind.USE_CASE,
        target_id="use-case.quote-order",
    )
    return build_ratchet_assessment(
        policy,
        bundle,
        producer=_assessment()[2].producer,
        procedure_uri="urn:ucf:ratchet-assessment:fixture:1.0.0",
        capture_context=_capture_context(),
        violations=tuple(
            ViolationInput(
                kind="ratchet_violation_input",
                rule_id=policy.rules[0].id,
                subject=subject,
                slot=slot,
                message=f"Violation at {slot}.",
            )
            for slot in slots
        ),
        partial_rule_ids=(
            {policy.rules[0].id} if partial else ()
        ),
    )


def _accepted():
    policy, bundle, initial = _assessment()
    baseline = establish_ratchet_baseline(policy, bundle, initial)
    return policy, bundle, baseline


def test_unchanged_legacy_debt_passes_and_round_trips() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle, "required-check")

    report = evaluate_ratchet(policy, baseline, bundle, current)

    assert report.outcome is EvaluationOutcome.PASS
    assert {
        item.classification for item in report.classifications
    } == {ViolationClassificationKind.UNCHANGED_LEGACY}
    assert report.weakening_delta.status is WeakeningDeltaStatus.NONE
    encoded = canonical_ratchet_json(report)
    parsed = parse_ratchet_evaluation_report_json(encoded)
    assert parsed == report
    validate_ratchet_evaluation_report(
        policy,
        baseline,
        bundle,
        current,
        parsed,
    )


def test_new_violation_on_unchanged_subject_fails_with_review_delta() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(
        policy,
        bundle,
        "required-check",
        "second-check",
    )

    report = evaluate_ratchet(policy, baseline, bundle, current)

    assert report.outcome is EvaluationOutcome.FAIL
    classifications = {
        item.key.slot: item.classification
        for item in report.classifications
    }
    assert classifications == {
        "required-check": ViolationClassificationKind.UNCHANGED_LEGACY,
        "second-check": ViolationClassificationKind.NEW_REGRESSION,
    }
    assert (
        report.weakening_delta.status
        is WeakeningDeltaStatus.REVIEW_REQUIRED
    )
    assert [
        key.slot for key in report.weakening_delta.added_allowances
    ] == ["second-check"]


def test_resolved_improvement_is_tightening_not_a_reset() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle)

    report = evaluate_ratchet(policy, baseline, bundle, current)

    assert report.outcome is EvaluationOutcome.PASS
    assert report.classifications[0].classification is (
        ViolationClassificationKind.RESOLVED
    )
    assert (
        report.weakening_delta.status is WeakeningDeltaStatus.TIGHTENING
    )
    assert [
        key.slot for key in report.weakening_delta.removed_allowances
    ] == ["required-check"]
    assert baseline.allowances
    assert baseline.protected == ()


def test_partial_coverage_cannot_claim_resolution() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle, partial=True)

    report = evaluate_ratchet(policy, baseline, bundle, current)

    assert report.outcome is EvaluationOutcome.INCONCLUSIVE
    assert report.classifications[0].classification is (
        ViolationClassificationKind.UNKNOWN
    )
    assert report.weakening_delta.removed_allowances == ()


def test_partial_coverage_with_present_allowance_is_inconclusive() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(
        policy,
        bundle,
        "required-check",
        partial=True,
    )

    report = evaluate_ratchet(policy, baseline, bundle, current)

    assert report.outcome is EvaluationOutcome.INCONCLUSIVE
    assert report.classifications[0].classification is (
        ViolationClassificationKind.UNCHANGED_LEGACY
    )
    encoded = canonical_ratchet_json(report)
    parsed = parse_ratchet_evaluation_report_json(encoded)
    assert parsed == report
    validate_ratchet_evaluation_report(
        policy,
        baseline,
        bundle,
        current,
        parsed,
    )


def test_observed_regression_under_partial_coverage_still_fails() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(
        policy,
        bundle,
        "required-check",
        "second-check",
        partial=True,
    )

    report = evaluate_ratchet(policy, baseline, bundle, current)

    assert report.outcome is EvaluationOutcome.FAIL
    assert {
        item.classification for item in report.classifications
    } == {
        ViolationClassificationKind.UNCHANGED_LEGACY,
        ViolationClassificationKind.NEW_REGRESSION,
    }


def test_forged_evaluation_report_is_recomputed_and_rejected() -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle, "required-check")
    report = evaluate_ratchet(policy, baseline, bundle, current)
    forged_classification = report.classifications[0].model_copy(
        update={
            "classification": ViolationClassificationKind.NEW_REGRESSION
        }
    )
    forged = report.model_copy(
        update={"classifications": (forged_classification,)}
    )
    forged = forged.model_copy(
        update={"id": derive_evaluation_id(forged)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        validate_ratchet_evaluation_report(
            policy,
            baseline,
            bundle,
            current,
            forged,
        )

    assert captured.value.code is RatchetErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == "$.outcome"


@pytest.mark.parametrize("collection", ["allowances", "protected"])
def test_evaluation_rejects_baseline_keys_for_unknown_policy_rule(
    collection: str,
) -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle, "required-check")
    if collection == "protected":
        resolved = _current(policy, bundle)
        report = evaluate_ratchet(policy, baseline, bundle, resolved)
        baseline = advance_ratchet_baseline(
            policy,
            baseline,
            bundle,
            resolved,
            report,
        )
    values = list(getattr(baseline, collection))
    key = values[0]
    values[0] = key.model_copy(
        update={
            "rule": key.rule.model_copy(
                update={"target_id": "rule.unknown"}
            )
        }
    )
    forged = baseline.model_copy(update={collection: tuple(values)})
    forged = forged.model_copy(
        update={"id": derive_baseline_id(forged)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        evaluate_ratchet(policy, forged, bundle, current)

    assert captured.value.code is RatchetErrorCode.BROKEN_REFERENCE
    assert captured.value.location == f"$.baseline.{collection}"
