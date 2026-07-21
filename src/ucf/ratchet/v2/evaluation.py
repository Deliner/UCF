from __future__ import annotations

from ucf.onboarding import OnboardingBundle
from ucf.ratchet.v2.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.v2.identity import (
    derive_coverage_debt_id,
    derive_evaluation_id,
    derive_violation_id,
)
from ucf.ratchet.v2.models import (
    RATCHET_EVALUATION_PROCEDURE_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_VERSION,
    BehaviorOutcome,
    BehaviorSubjectChange,
    BehaviorSubjectChangeKind,
    BehaviorSubjectRef,
    BehaviorWeakeningDelta,
    CombinedOutcome,
    CoverageComparisonStatus,
    CoverageDebtClassification,
    CoverageDebtClassificationKind,
    CoverageDebtKind,
    CoverageOutcome,
    CoverageSubjectChange,
    CoverageSubjectChangeKind,
    CoverageSubjectRef,
    CoverageWeakeningDelta,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    ViolationClassification,
    ViolationClassificationKind,
    WeakeningDeltaStatus,
)
from ucf.ratchet.v2.references import assessment_ref, baseline_ref, policy_ref
from ucf.ratchet.v2.validation import (
    validate_ratchet_assessment,
    validate_ratchet_baseline_structure,
)

_BEHAVIOR_REGRESSIONS = {
    ViolationClassificationKind.NEW_REGRESSION,
    ViolationClassificationKind.REINTRODUCED,
    ViolationClassificationKind.TOUCHED_LEGACY,
}
_COVERAGE_REGRESSIONS = {
    CoverageDebtClassificationKind.NEW_REGRESSION,
    CoverageDebtClassificationKind.CHANGED_REGRESSION,
    CoverageDebtClassificationKind.REINTRODUCED,
}


def evaluate_ratchet(
    policy: RatchetPolicy,
    baseline: RatchetBaseline,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
    *,
    accepted_baseline_id: str,
) -> RatchetEvaluationReport:
    validate_ratchet_assessment(policy, bundle, assessment)
    validate_ratchet_baseline_structure(baseline)
    if baseline.id != accepted_baseline_id:
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "baseline differs from the independently accepted identity",
            location="$.accepted_baseline_id",
        )
    if baseline.policy != policy_ref(policy):
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "baseline policy differs from the exact evaluation policy",
            location="$.baseline.policy",
        )
    rules = {(rule.id, rule.version) for rule in policy.rules}
    for collection in ("allowances", "protected"):
        keys = getattr(baseline.behavior, collection)
        if any(
            (key.rule.target_id, key.rule.version) not in rules
            for key in keys
        ):
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "baseline behavior key names an unknown policy rule",
                location=f"$.baseline.behavior.{collection}",
            )
    return _derive_evaluation(policy, baseline, assessment)


def _derive_evaluation(
    policy: RatchetPolicy,
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
) -> RatchetEvaluationReport:
    behavior_changes = _behavior_subject_changes(baseline, assessment)
    behavior_classifications = _behavior_classifications(
        baseline,
        assessment,
        behavior_changes,
    )
    coverage_comparison = _coverage_comparison(baseline, assessment)
    coverage_changes = _coverage_subject_changes(
        baseline,
        assessment,
        comparable=(
            coverage_comparison is CoverageComparisonStatus.COMPARABLE
        ),
    )
    coverage_classifications = _coverage_classifications(
        baseline,
        assessment,
        coverage_comparison,
    )
    behavior_outcome = _behavior_outcome(
        assessment,
        behavior_changes,
        behavior_classifications,
    )
    coverage_outcome = _coverage_outcome(
        assessment,
        coverage_comparison,
        coverage_changes,
        coverage_classifications,
    )
    combined_outcome = _combined_outcome(
        behavior_outcome,
        coverage_outcome,
    )
    provisional = RatchetEvaluationReport(
        kind="ratchet_evaluation_report",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_EVALUATION_REPORT_SCHEMA_URI,
        id=f"evaluation.{'0' * 64}",
        policy=policy_ref(policy),
        baseline=baseline_ref(baseline),
        assessment=assessment_ref(assessment),
        procedure_uri=RATCHET_EVALUATION_PROCEDURE_URI,
        behavior_subject_changes=behavior_changes,
        behavior_classifications=behavior_classifications,
        coverage_comparison=coverage_comparison,
        coverage_subject_changes=coverage_changes,
        coverage_classifications=coverage_classifications,
        behavior_outcome=behavior_outcome,
        coverage_outcome=coverage_outcome,
        combined_outcome=combined_outcome,
        behavior_delta=_behavior_delta(behavior_classifications),
        coverage_delta=_coverage_delta(coverage_classifications),
    )
    return provisional.model_copy(
        update={"id": derive_evaluation_id(provisional)}
    )


def _behavior_subject_changes(
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
) -> tuple[BehaviorSubjectChange, ...]:
    previous = {subject.id: subject for subject in baseline.behavior.subjects}
    current = {subject.id: subject for subject in assessment.behavior.subjects}
    changes = []
    for identifier in sorted(set(previous) | set(current)):
        old = previous.get(identifier)
        new = current.get(identifier)
        if old is None:
            change = BehaviorSubjectChangeKind.NEW_SUBJECT
        elif new is None:
            change = (
                BehaviorSubjectChangeKind.REMOVED_SUBJECT
                if assessment.coverage.discovery_coverage == "complete"
                else BehaviorSubjectChangeKind.UNKNOWN_SUBJECT
            )
        else:
            change = _fingerprint_change(
                old.semantic,
                new.semantic,
                old.observed,
                new.observed,
                BehaviorSubjectChangeKind,
            )
        subject = new if new is not None else old
        assert subject is not None
        changes.append(
            BehaviorSubjectChange(
                kind="ratchet_behavior_subject_change",
                subject=BehaviorSubjectRef(
                    kind="behavior_subject_ref",
                    target_id=subject.id,
                ),
                change=change,
            )
        )
    return tuple(changes)


def _behavior_classifications(
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
    changes: tuple[BehaviorSubjectChange, ...],
) -> tuple[ViolationClassification, ...]:
    change_by_subject = {
        change.subject.target_id: change.change for change in changes
    }
    allowances = {
        derive_violation_id(key): key
        for key in baseline.behavior.allowances
    }
    protected = {
        derive_violation_id(key): key for key in baseline.behavior.protected
    }
    current = {
        violation.id: violation.key
        for violation in assessment.behavior.violations
    }
    coverage_by_rule = {
        (coverage.rule.target_id, coverage.rule.version): coverage.status
        for coverage in assessment.behavior.coverage
    }
    classifications = []
    for identifier, key in current.items():
        if identifier in protected:
            classification = ViolationClassificationKind.REINTRODUCED
        elif identifier not in allowances:
            classification = ViolationClassificationKind.NEW_REGRESSION
        elif (
            change_by_subject[key.subject.target_id]
            is not BehaviorSubjectChangeKind.UNCHANGED
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
        subject_change = change_by_subject.get(key.subject.target_id)
        rule_status = coverage_by_rule.get(
            (key.rule.target_id, key.rule.version)
        )
        if (
            rule_status == "complete"
            and subject_change is not BehaviorSubjectChangeKind.UNKNOWN_SUBJECT
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
    return tuple(
        sorted(
            classifications,
            key=lambda item: derive_violation_id(item.key),
        )
    )


def _coverage_comparison(
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
) -> CoverageComparisonStatus:
    if baseline.coverage.qualification != assessment.coverage.qualification:
        return CoverageComparisonStatus.NON_COMPARABLE_QUALIFICATION
    if assessment.coverage.inventory_coverage != "complete":
        return CoverageComparisonStatus.INCOMPLETE_INVENTORY
    return CoverageComparisonStatus.COMPARABLE


def _coverage_subject_changes(
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
    *,
    comparable: bool,
) -> tuple[CoverageSubjectChange, ...]:
    previous = {group.id: group for group in baseline.coverage.groups}
    current = {group.id: group for group in assessment.coverage.groups}
    changes = []
    for identifier in sorted(set(previous) | set(current)):
        old = previous.get(identifier)
        new = current.get(identifier)
        if not comparable:
            change = CoverageSubjectChangeKind.UNKNOWN_SUBJECT
        elif old is None:
            change = CoverageSubjectChangeKind.NEW_SUBJECT
        elif new is None:
            change = CoverageSubjectChangeKind.UNKNOWN_SUBJECT
        else:
            change = _fingerprint_change(
                old.semantic,
                new.semantic,
                old.observed,
                new.observed,
                CoverageSubjectChangeKind,
            )
        subject = new if new is not None else old
        assert subject is not None
        changes.append(
            CoverageSubjectChange(
                kind="ratchet_coverage_subject_change",
                subject=CoverageSubjectRef(
                    kind="coverage_subject_ref",
                    target_id=subject.id,
                ),
                change=change,
            )
        )
    return tuple(changes)


def _coverage_classifications(
    baseline: RatchetBaseline,
    assessment: RatchetAssessment,
    comparison: CoverageComparisonStatus,
) -> tuple[CoverageDebtClassification, ...]:
    previous = {debt.id: debt for debt in baseline.coverage.allowances}
    protected = {
        derive_coverage_debt_id(key): key
        for key in baseline.coverage.protected
    }
    current = {debt.id: debt for debt in assessment.coverage.debts}
    current_groups = {group.id: group for group in assessment.coverage.groups}
    classifications = []
    for identifier in sorted(set(previous) | set(current)):
        old = previous.get(identifier)
        new = current.get(identifier)
        key = new.key if new is not None else old.key
        if new is not None and identifier in protected:
            classification = CoverageDebtClassificationKind.REINTRODUCED
        elif new is not None and _was_explicitly_reviewed(
            new,
            baseline.coverage.groups,
        ):
            classification = CoverageDebtClassificationKind.REINTRODUCED
        elif comparison is CoverageComparisonStatus.NON_COMPARABLE_QUALIFICATION:
            classification = CoverageDebtClassificationKind.UNKNOWN
        elif new is not None:
            if old is None:
                classification = CoverageDebtClassificationKind.NEW_REGRESSION
            elif (
                old.semantic == new.semantic
                and old.observed == new.observed
            ):
                classification = (
                    CoverageDebtClassificationKind.UNCHANGED_LEGACY
                )
            else:
                classification = (
                    CoverageDebtClassificationKind.CHANGED_REGRESSION
                )
        elif _is_explicitly_resolved(old, current_groups):
            classification = CoverageDebtClassificationKind.RESOLVED
        else:
            classification = CoverageDebtClassificationKind.UNKNOWN
        classifications.append(
            CoverageDebtClassification(
                kind="ratchet_coverage_debt_classification",
                classification=classification,
                key=key,
            )
        )
    return tuple(classifications)


def _was_explicitly_reviewed(debt, previous_groups: tuple) -> bool:
    if debt.key.debt_kind is not CoverageDebtKind.UNCERTAIN:
        return False
    group = next(
        (
            item
            for item in previous_groups
            if item.id == debt.key.subject.target_id
        ),
        None,
    )
    if group is None:
        return False
    return any(
        item.candidate_semantic_digest
        == debt.key.candidate_semantic_digest
        and item.disposition.value != "uncertain"
        for item in group.reconciliations
    )


def _is_explicitly_resolved(debt, current_groups: dict) -> bool:
    group = current_groups.get(debt.key.subject.target_id)
    if group is None:
        return False
    if debt.key.debt_kind is CoverageDebtKind.UNCOVERED:
        return bool(group.reconciliations) and all(
            item.disposition.value != "uncertain"
            for item in group.reconciliations
        )
    return any(
        item.candidate_semantic_digest
        == debt.key.candidate_semantic_digest
        and item.disposition.value != "uncertain"
        for item in group.reconciliations
    )


def _behavior_outcome(
    assessment: RatchetAssessment,
    changes: tuple[BehaviorSubjectChange, ...],
    classifications: tuple[ViolationClassification, ...],
) -> BehaviorOutcome:
    if any(
        item.classification in _BEHAVIOR_REGRESSIONS
        for item in classifications
    ):
        return BehaviorOutcome.FAIL
    if (
        any(
            item.classification is ViolationClassificationKind.UNKNOWN
            for item in classifications
        )
        or any(
            change.change is BehaviorSubjectChangeKind.UNKNOWN_SUBJECT
            for change in changes
        )
        or any(
            coverage.status != "complete"
            for coverage in assessment.behavior.coverage
        )
    ):
        return BehaviorOutcome.INCONCLUSIVE
    return BehaviorOutcome.PASS


def _coverage_outcome(
    assessment: RatchetAssessment,
    comparison: CoverageComparisonStatus,
    changes: tuple[CoverageSubjectChange, ...],
    classifications: tuple[CoverageDebtClassification, ...],
) -> CoverageOutcome:
    if any(
        item.classification in _COVERAGE_REGRESSIONS
        for item in classifications
    ):
        return CoverageOutcome.FAIL
    if (
        comparison is not CoverageComparisonStatus.COMPARABLE
        or any(
            item.classification is CoverageDebtClassificationKind.UNKNOWN
            for item in classifications
        )
        or any(
            change.change is CoverageSubjectChangeKind.UNKNOWN_SUBJECT
            for change in changes
        )
        or assessment.coverage.inventory_coverage != "complete"
    ):
        return CoverageOutcome.INCONCLUSIVE
    if any(
        item.classification
        is CoverageDebtClassificationKind.UNCHANGED_LEGACY
        for item in classifications
    ):
        return CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    return CoverageOutcome.PASS


def _combined_outcome(
    behavior: BehaviorOutcome,
    coverage: CoverageOutcome,
) -> CombinedOutcome:
    if behavior is BehaviorOutcome.FAIL or coverage is CoverageOutcome.FAIL:
        return CombinedOutcome.FAIL
    if (
        behavior is BehaviorOutcome.INCONCLUSIVE
        or coverage is CoverageOutcome.INCONCLUSIVE
    ):
        return CombinedOutcome.INCONCLUSIVE
    if coverage is CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT:
        return CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    return CombinedOutcome.PASS


def _behavior_delta(
    classifications: tuple[ViolationClassification, ...],
) -> BehaviorWeakeningDelta:
    regressions = tuple(
        item.key
        for item in classifications
        if item.classification in _BEHAVIOR_REGRESSIONS
    )
    resolutions = tuple(
        item.key
        for item in classifications
        if item.classification is ViolationClassificationKind.RESOLVED
    )
    reintroduced = tuple(
        item.key
        for item in classifications
        if item.classification is ViolationClassificationKind.REINTRODUCED
    )
    return BehaviorWeakeningDelta(
        kind="ratchet_behavior_delta",
        status=_delta_status(regressions, resolutions),
        added_allowances=regressions,
        removed_allowances=resolutions,
        removed_protections=reintroduced,
    )


def _coverage_delta(
    classifications: tuple[CoverageDebtClassification, ...],
) -> CoverageWeakeningDelta:
    regressions = tuple(
        item.key
        for item in classifications
        if item.classification in _COVERAGE_REGRESSIONS
    )
    resolutions = tuple(
        item.key
        for item in classifications
        if item.classification is CoverageDebtClassificationKind.RESOLVED
    )
    reintroduced = tuple(
        item.key
        for item in classifications
        if item.classification is CoverageDebtClassificationKind.REINTRODUCED
    )
    return CoverageWeakeningDelta(
        kind="ratchet_coverage_delta",
        status=_delta_status(regressions, resolutions),
        added_allowances=regressions,
        removed_allowances=resolutions,
        removed_protections=reintroduced,
    )


def _delta_status(regressions: tuple, resolutions: tuple) -> WeakeningDeltaStatus:
    if regressions:
        return WeakeningDeltaStatus.REVIEW_REQUIRED
    if resolutions:
        return WeakeningDeltaStatus.TIGHTENING
    return WeakeningDeltaStatus.NONE


def _fingerprint_change(
    old_semantic,
    new_semantic,
    old_observed,
    new_observed,
    change_kind,
):
    semantic_changed = old_semantic != new_semantic
    observed_changed = old_observed != new_observed
    if semantic_changed and observed_changed:
        return change_kind.SEMANTIC_AND_OBSERVED_CHANGED
    if semantic_changed:
        return change_kind.SEMANTIC_CHANGED
    if observed_changed:
        return change_kind.OBSERVED_CHANGED
    return change_kind.UNCHANGED
