from __future__ import annotations

import pytest

from ucf.ratchet import (
    EvaluationOutcome,
    RatchetErrorCode,
    RatchetValidationError,
    SubjectChangeKind,
    WeakeningDeltaStatus,
    canonical_ratchet_json,
    derive_assessment_id,
    derive_evaluation_id,
    derive_violation_id,
    evaluate_ratchet,
    parse_ratchet_assessment_json,
    parse_ratchet_evaluation_report_json,
)

from .test_assessment import _assessment
from .test_evaluation import _accepted, _current


@pytest.mark.parametrize("mutation", ["coverage_subject", "violation_rule"])
def test_assessment_parser_rejects_internal_broken_references(
    mutation: str,
) -> None:
    _, _, assessment = _assessment()
    if mutation == "coverage_subject":
        coverage = assessment.coverage[0]
        broken = coverage.subjects[0].model_copy(
            update={"target_id": f"subject.{'f' * 64}"}
        )
        changed = assessment.model_copy(
            update={
                "coverage": (
                    coverage.model_copy(update={"subjects": (broken,)}),
                )
            }
        )
        location = "$.coverage[0].subjects"
    else:
        violation = assessment.violations[0]
        key = violation.key.model_copy(
            update={
                "rule": violation.key.rule.model_copy(
                    update={"target_id": "rule.unknown"}
                )
            }
        )
        changed = assessment.model_copy(
            update={
                "violations": (
                    violation.model_copy(
                        update={
                            "id": derive_violation_id(key),
                            "key": key,
                        }
                    ),
                )
            }
        )
        location = "$.violations[0].key.rule"
    changed = changed.model_copy(
        update={"id": derive_assessment_id(changed)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_assessment_json(canonical_ratchet_json(changed))

    assert captured.value.code is RatchetErrorCode.BROKEN_REFERENCE
    assert captured.value.location == location


@pytest.mark.parametrize(
    "mutation",
    ["classification_subject", "outcome", "delta_status", "delta_member"],
)
def test_report_parser_rejects_internally_inconsistent_summary(
    mutation: str,
) -> None:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle, "required-check")
    report = evaluate_ratchet(policy, baseline, bundle, current)
    if mutation == "classification_subject":
        classification = report.classifications[0]
        key = classification.key.model_copy(
            update={
                "subject": classification.key.subject.model_copy(
                    update={"target_id": f"subject.{'f' * 64}"}
                )
            }
        )
        changed = report.model_copy(
            update={
                "classifications": (
                    classification.model_copy(update={"key": key}),
                )
            }
        )
        location = "$.classifications[0].key.subject"
        code = RatchetErrorCode.BROKEN_REFERENCE
    elif mutation == "outcome":
        changed = report.model_copy(
            update={"outcome": EvaluationOutcome.FAIL}
        )
        location = "$.outcome"
        code = RatchetErrorCode.SUMMARY_MISMATCH
    elif mutation == "delta_status":
        changed = report.model_copy(
            update={
                "weakening_delta": report.weakening_delta.model_copy(
                    update={
                        "status": WeakeningDeltaStatus.REVIEW_REQUIRED
                    }
                )
            }
        )
        location = "$.weakening_delta.status"
        code = RatchetErrorCode.SUMMARY_MISMATCH
    else:
        changed = report.model_copy(
            update={
                "weakening_delta": report.weakening_delta.model_copy(
                    update={
                        "added_allowances": (
                            report.classifications[0].key,
                        )
                    }
                )
            }
        )
        location = "$.weakening_delta.added_allowances"
        code = RatchetErrorCode.SUMMARY_MISMATCH
    changed = changed.model_copy(
        update={"id": derive_evaluation_id(changed)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_evaluation_report_json(
            canonical_ratchet_json(changed)
        )

    assert captured.value.code is code
    assert captured.value.location == location


def test_unknown_subject_change_makes_report_inconclusive() -> None:
    policy, bundle, baseline = _accepted()
    partial = _current(policy, bundle, partial=True)
    report = evaluate_ratchet(policy, baseline, bundle, partial)

    assert report.outcome is EvaluationOutcome.INCONCLUSIVE
    assert all(
        change.change is not SubjectChangeKind.UNKNOWN_SUBJECT
        for change in report.subject_changes
    )
