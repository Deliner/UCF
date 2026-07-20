from __future__ import annotations

from ucf.onboarding import OnboardingBundle
from ucf.ratchet.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.identity import (
    derive_evaluation_id,
    derive_violation_id,
)
from ucf.ratchet.models import (
    RATCHET_EVALUATION_PROCEDURE_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_VERSION,
    BehaviorSubjectRef,
    EvaluationOutcome,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    SubjectChange,
    SubjectChangeKind,
    ViolationClassification,
    ViolationClassificationKind,
    WeakeningDelta,
    WeakeningDeltaStatus,
)
from ucf.ratchet.references import assessment_ref, baseline_ref, policy_ref
from ucf.ratchet.validation import (
    validate_ratchet_assessment,
    validate_ratchet_baseline_structure,
)

_REGRESSIONS = {
    ViolationClassificationKind.NEW_REGRESSION,
    ViolationClassificationKind.REINTRODUCED,
    ViolationClassificationKind.TOUCHED_LEGACY,
}


def evaluate_ratchet(
    policy: RatchetPolicy,
    baseline: RatchetBaseline,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
) -> RatchetEvaluationReport:
    validate_ratchet_assessment(policy, bundle, assessment)
    validate_ratchet_baseline_structure(baseline)
    if baseline.policy != policy_ref(policy):
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "baseline policy differs from the exact evaluation policy",
            location="$.baseline.policy",
        )
    rules = {
        (rule.id, rule.version) for rule in policy.rules
    }
    for collection in ("allowances", "protected"):
        if any(
            (key.rule.target_id, key.rule.version) not in rules
            for key in getattr(baseline, collection)
        ):
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "baseline violation key names an unknown policy rule",
                location=f"$.baseline.{collection}",
            )
    report = _derive_evaluation(policy, baseline, assessment)
    return report


def _derive_evaluation(
    policy: RatchetPolicy,
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
) -> RatchetEvaluationReport:
    changes = _subject_changes(baseline, assessment)
    change_by_subject = {
        change.subject.target_id: change.change for change in changes
    }
    allowances = {
        derive_violation_id(key): key for key in baseline.allowances
    }
    protected = {
        derive_violation_id(key): key for key in baseline.protected
    }
    current = {
        violation.id: violation.key for violation in assessment.violations
    }
    coverage_by_rule = {
        (coverage.rule.target_id, coverage.rule.version): coverage.status
        for coverage in assessment.coverage
    }
    classifications = []
    for identifier, key in current.items():
        if identifier in protected:
            classification = ViolationClassificationKind.REINTRODUCED
        elif identifier not in allowances:
            classification = ViolationClassificationKind.NEW_REGRESSION
        elif (
            change_by_subject[key.subject.target_id]
            is not SubjectChangeKind.UNCHANGED
        ):
            classification = ViolationClassificationKind.TOUCHED_LEGACY
        else:
            classification = ViolationClassificationKind.UNCHANGED_LEGACY
        classifications.append(
            ViolationClassification(
                kind="ratchet_violation_classification",
                classification=classification,
                key=key,
            )
        )
    for identifier, key in allowances.items():
        if identifier in current:
            continue
        coverage = coverage_by_rule.get(
            (key.rule.target_id, key.rule.version)
        )
        if (
            assessment.subject_coverage == "complete"
            and coverage == "complete"
        ):
            classification = ViolationClassificationKind.RESOLVED
        else:
            classification = ViolationClassificationKind.UNKNOWN
        classifications.append(
            ViolationClassification(
                kind="ratchet_violation_classification",
                classification=classification,
                key=key,
            )
        )
    classifications = sorted(
        classifications,
        key=lambda item: derive_violation_id(item.key),
    )
    has_regression = any(
        item.classification in _REGRESSIONS for item in classifications
    )
    has_unknown = any(
        item.classification is ViolationClassificationKind.UNKNOWN
        for item in classifications
    ) or any(
        change.change is SubjectChangeKind.UNKNOWN_SUBJECT
        for change in changes
    ) or assessment.subject_coverage != "complete" or any(
        coverage.status != "complete"
        for coverage in assessment.coverage
    )
    if has_regression:
        outcome = EvaluationOutcome.FAIL
    elif has_unknown:
        outcome = EvaluationOutcome.INCONCLUSIVE
    else:
        outcome = EvaluationOutcome.PASS
    added_allowances = tuple(
        item.key
        for item in classifications
        if item.classification
        in {
            ViolationClassificationKind.NEW_REGRESSION,
            ViolationClassificationKind.REINTRODUCED,
        }
    )
    removed_allowances = tuple(
        item.key
        for item in classifications
        if item.classification is ViolationClassificationKind.RESOLVED
    )
    removed_protections = tuple(
        item.key
        for item in classifications
        if item.classification is ViolationClassificationKind.REINTRODUCED
    )
    if has_regression:
        delta_status = WeakeningDeltaStatus.REVIEW_REQUIRED
    elif removed_allowances:
        delta_status = WeakeningDeltaStatus.TIGHTENING
    else:
        delta_status = WeakeningDeltaStatus.NONE
    provisional = RatchetEvaluationReport(
        kind="ratchet_evaluation_report",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_EVALUATION_REPORT_SCHEMA_URI,
        id=f"evaluation.{'0' * 64}",
        policy=policy_ref(policy),
        baseline=baseline_ref(baseline),
        assessment=assessment_ref(assessment),
        procedure_uri=RATCHET_EVALUATION_PROCEDURE_URI,
        subject_changes=changes,
        classifications=tuple(classifications),
        outcome=outcome,
        weakening_delta=WeakeningDelta(
            kind="weakening_delta",
            status=delta_status,
            added_allowances=added_allowances,
            removed_allowances=removed_allowances,
            removed_protections=removed_protections,
        ),
    )
    return provisional.model_copy(
        update={"id": derive_evaluation_id(provisional)}
    )


def _subject_changes(
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
) -> tuple[SubjectChange, ...]:
    previous = {subject.id: subject for subject in baseline.subjects}
    current = {subject.id: subject for subject in assessment.subjects}
    changes = []
    for identifier in sorted(set(previous) | set(current)):
        old = previous.get(identifier)
        new = current.get(identifier)
        if old is None:
            change = SubjectChangeKind.NEW_SUBJECT
        elif new is None:
            change = (
                SubjectChangeKind.REMOVED_SUBJECT
                if assessment.subject_coverage == "complete"
                else SubjectChangeKind.UNKNOWN_SUBJECT
            )
        else:
            semantic_changed = old.semantic != new.semantic
            observed_changed = old.observed != new.observed
            if semantic_changed and observed_changed:
                change = SubjectChangeKind.SEMANTIC_AND_OBSERVED_CHANGED
            elif semantic_changed:
                change = SubjectChangeKind.SEMANTIC_CHANGED
            elif observed_changed:
                change = SubjectChangeKind.OBSERVED_CHANGED
            else:
                change = SubjectChangeKind.UNCHANGED
        subject = new if new is not None else old
        changes.append(
            SubjectChange(
                kind="ratchet_subject_change",
                subject=BehaviorSubjectRef(
                    kind="behavior_subject_ref",
                    target_id=subject.id,
                ),
                change=change,
            )
        )
    return tuple(changes)
