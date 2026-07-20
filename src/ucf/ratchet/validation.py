from __future__ import annotations

from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    OnboardingBundle,
    canonical_onboarding_digest,
)
from ucf.ratchet.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.identity import (
    derive_assessment_id,
    derive_baseline_id,
    derive_behavior_subject_id,
    derive_evaluation_id,
    derive_policy_id,
    derive_violation_id,
)
from ucf.ratchet.models import (
    EvaluationOutcome,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    SubjectChangeKind,
    ViolationClassificationKind,
    WeakeningDeltaStatus,
)
from ucf.ratchet.references import policy_ref


def validate_ratchet_policy(policy: RatchetPolicy) -> None:
    rule_ids = tuple(rule.id for rule in policy.rules)
    if len(rule_ids) != len(set(rule_ids)):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            "ratchet rule IDs must be unique",
            location="$.rules",
        )
    if rule_ids != tuple(sorted(rule_ids)):
        raise RatchetValidationError(
            RatchetErrorCode.NON_CANONICAL_ORDER,
            "ratchet rules must be sorted by ID",
            location="$.rules",
        )
    if policy.id != derive_policy_id(policy):
        raise RatchetValidationError(
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
            "ratchet policy ID is not derived from its exact content",
            location="$.id",
        )


def validate_ratchet_assessment(
    policy: RatchetPolicy,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
) -> None:
    from ucf.ratchet.projection import derive_subject_snapshots

    validate_ratchet_policy(policy)
    validate_ratchet_assessment_structure(assessment)
    expected_policy = policy_ref(policy)
    if assessment.policy != expected_policy:
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "assessment policy reference differs from the exact policy",
            location="$.policy",
        )
    expected_source = assessment.source.model_copy(
        update={
            "schema_uri": ONBOARDING_BUNDLE_SCHEMA_URI,
            "schema_version": ONBOARDING_VERSION,
            "canonical_digest": canonical_onboarding_digest(bundle),
        }
    )
    if assessment.source != expected_source:
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "assessment source differs from the exact onboarding bundle",
            location="$.source",
        )
    if assessment.subject_coverage != bundle.discovery.coverage.status:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "assessment subject coverage differs from discovery coverage",
            location="$.subject_coverage",
        )
    expected_subjects = derive_subject_snapshots(bundle)
    if assessment.subjects != expected_subjects:
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "assessment subjects differ from their exact bundle projection",
            location="$.subjects",
        )
    _validate_assessment_references(policy, assessment)


def validate_ratchet_assessment_structure(
    assessment: RatchetAssessment,
) -> None:
    _validate_subjects(assessment.subjects, location="$.subjects")
    coverage_keys = tuple(
        (coverage.rule.target_id, coverage.rule.version)
        for coverage in assessment.coverage
    )
    _require_unique_and_sorted(
        coverage_keys,
        location="$.coverage",
        label="rule coverage",
    )
    violation_ids = tuple(
        violation.id for violation in assessment.violations
    )
    _require_unique_and_sorted(
        violation_ids,
        location="$.violations",
        label="violations",
    )
    for index, violation in enumerate(assessment.violations):
        if violation.id != derive_violation_id(violation.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "violation ID is not derived from its stable key",
                location=f"$.violations[{index}].id",
            )
    _validate_assessment_internal_references(assessment)
    if assessment.id != derive_assessment_id(assessment):
        raise RatchetValidationError(
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
            "assessment ID is not derived from its exact content",
            location="$.id",
        )


def validate_initial_ratchet_baseline(
    policy: RatchetPolicy,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
    baseline: RatchetBaseline,
) -> None:
    from ucf.ratchet.baseline import _derive_initial_baseline

    validate_ratchet_assessment(policy, bundle, assessment)
    if (
        assessment.subject_coverage != "complete"
        or any(
            coverage.status != "complete"
            for coverage in assessment.coverage
        )
    ):
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_COVERAGE,
            "initial baseline requires complete subject and rule coverage",
            location="$.source_assessment.coverage",
        )
    expected = _derive_initial_baseline(assessment)
    for field, location in (
        ("policy", "$.policy"),
        ("source_assessment", "$.source_assessment"),
        ("source_evaluation", "$.source_evaluation"),
        ("predecessor", "$.predecessor"),
        ("generation", "$.generation"),
        ("subjects", "$.subjects"),
        ("allowances", "$.allowances"),
        ("protected", "$.protected"),
    ):
        if getattr(baseline, field) != getattr(expected, field):
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "initial baseline differs from its exact source assessment",
                location=location,
            )
    validate_ratchet_baseline_structure(baseline)
    if baseline.id != expected.id:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "initial baseline identity differs from its derived state",
            location="$.id",
        )


def validate_ratchet_baseline_structure(
    baseline: RatchetBaseline,
) -> None:
    _validate_subjects(baseline.subjects, location="$.subjects")
    subject_ids = {subject.id for subject in baseline.subjects}
    allowance_ids = tuple(
        derive_violation_id(key) for key in baseline.allowances
    )
    protected_ids = tuple(
        derive_violation_id(key) for key in baseline.protected
    )
    _require_unique_and_sorted(
        allowance_ids,
        location="$.allowances",
        label="baseline allowances",
    )
    _require_unique_and_sorted(
        protected_ids,
        location="$.protected",
        label="protected resolutions",
    )
    if set(allowance_ids) & set(protected_ids):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            "allowances and protected resolutions must be disjoint",
            location="$",
        )
    if any(
        key.subject.target_id not in subject_ids
        for key in baseline.allowances
    ):
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "baseline allowance names an unknown current subject",
            location="$.allowances",
        )
    if baseline.id != derive_baseline_id(baseline):
        raise RatchetValidationError(
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
            "baseline ID is not derived from its exact content",
            location="$.id",
        )


def validate_ratchet_evaluation_report(
    policy: RatchetPolicy,
    baseline: RatchetBaseline,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
    report: RatchetEvaluationReport,
) -> None:
    from ucf.ratchet.evaluation import evaluate_ratchet

    validate_ratchet_evaluation_report_structure(report)
    expected = evaluate_ratchet(policy, baseline, bundle, assessment)
    for field in (
        "policy",
        "baseline",
        "assessment",
        "procedure_uri",
        "subject_changes",
        "classifications",
        "outcome",
        "weakening_delta",
        "id",
    ):
        if getattr(report, field) != getattr(expected, field):
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "evaluation report differs from the exact recomputed result",
                location=f"$.{field}",
            )


def validate_successor_ratchet_baseline(
    policy: RatchetPolicy,
    predecessor: RatchetBaseline,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
    report: RatchetEvaluationReport,
    baseline: RatchetBaseline,
) -> None:
    from ucf.ratchet.baseline import _derive_successor_baseline

    validate_ratchet_evaluation_report(
        policy,
        predecessor,
        bundle,
        assessment,
        report,
    )
    if (
        assessment.subject_coverage != "complete"
        or any(
            coverage.status != "complete"
            for coverage in assessment.coverage
        )
    ):
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_COVERAGE,
            "successor baseline requires complete subject and rule coverage",
            location="$.source_assessment.coverage",
        )
    if report.outcome != "pass":
        raise RatchetValidationError(
            RatchetErrorCode.ILLEGAL_WEAKENING,
            "successor baseline requires a passing evaluation",
            location="$.source_evaluation",
        )
    expected = _derive_successor_baseline(
        predecessor,
        assessment,
        report,
    )
    for field, location in (
        ("policy", "$.policy"),
        ("source_assessment", "$.source_assessment"),
        ("source_evaluation", "$.source_evaluation"),
        ("predecessor", "$.predecessor"),
        ("generation", "$.generation"),
        ("subjects", "$.subjects"),
        ("allowances", "$.allowances"),
        ("protected", "$.protected"),
    ):
        if getattr(baseline, field) != getattr(expected, field):
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "successor baseline differs from its exact evaluation",
                location=location,
            )
    validate_ratchet_baseline_structure(baseline)
    if baseline.id != expected.id:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "successor baseline identity differs from its derived state",
            location="$.id",
        )


def validate_ratchet_evaluation_report_structure(
    report: RatchetEvaluationReport,
) -> None:
    subject_ids = tuple(
        change.subject.target_id for change in report.subject_changes
    )
    _require_unique_and_sorted(
        subject_ids,
        location="$.subject_changes",
        label="subject changes",
    )
    classification_ids = tuple(
        derive_violation_id(item.key) for item in report.classifications
    )
    _require_unique_and_sorted(
        classification_ids,
        location="$.classifications",
        label="violation classifications",
    )
    subject_id_set = set(subject_ids)
    for index, classification in enumerate(report.classifications):
        if classification.key.subject.target_id not in subject_id_set:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "classification names an unknown report subject",
                location=(
                    f"$.classifications[{index}].key.subject"
                ),
            )
    for field in (
        "added_allowances",
        "removed_allowances",
        "removed_protections",
    ):
        values = tuple(
            derive_violation_id(key)
            for key in getattr(report.weakening_delta, field)
        )
        _require_unique_and_sorted(
            values,
            location=f"$.weakening_delta.{field}",
            label=field.replace("_", " "),
        )
    regressions = {
        ViolationClassificationKind.NEW_REGRESSION,
        ViolationClassificationKind.REINTRODUCED,
        ViolationClassificationKind.TOUCHED_LEGACY,
    }
    has_regression = any(
        item.classification in regressions
        for item in report.classifications
    )
    has_unknown = any(
        item.classification is ViolationClassificationKind.UNKNOWN
        for item in report.classifications
    ) or any(
        change.change is SubjectChangeKind.UNKNOWN_SUBJECT
        for change in report.subject_changes
    )
    expected_outcomes = (
        {EvaluationOutcome.FAIL}
        if has_regression
        else {EvaluationOutcome.INCONCLUSIVE}
        if has_unknown
        else {
            EvaluationOutcome.PASS,
            EvaluationOutcome.INCONCLUSIVE,
        }
    )
    if report.outcome not in expected_outcomes:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "evaluation outcome differs from its internal evidence",
            location="$.outcome",
        )
    expected_delta = {
        "added_allowances": tuple(
            item.key
            for item in report.classifications
            if item.classification
            in {
                ViolationClassificationKind.NEW_REGRESSION,
                ViolationClassificationKind.REINTRODUCED,
            }
        ),
        "removed_allowances": tuple(
            item.key
            for item in report.classifications
            if item.classification is ViolationClassificationKind.RESOLVED
        ),
        "removed_protections": tuple(
            item.key
            for item in report.classifications
            if item.classification
            is ViolationClassificationKind.REINTRODUCED
        ),
    }
    for field, expected in expected_delta.items():
        if getattr(report.weakening_delta, field) != expected:
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "weakening delta differs from its classifications",
                location=f"$.weakening_delta.{field}",
            )
    expected_delta_status = (
        WeakeningDeltaStatus.REVIEW_REQUIRED
        if has_regression
        else WeakeningDeltaStatus.TIGHTENING
        if expected_delta["removed_allowances"]
        else WeakeningDeltaStatus.NONE
    )
    if report.weakening_delta.status is not expected_delta_status:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "weakening delta status differs from its exact members",
            location="$.weakening_delta.status",
        )
    if report.id != derive_evaluation_id(report):
        raise RatchetValidationError(
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
            "evaluation ID is not derived from its exact content",
            location="$.id",
        )


def _validate_assessment_internal_references(
    assessment: RatchetAssessment,
) -> None:
    subjects = {subject.id for subject in assessment.subjects}
    rules = {
        (coverage.rule.target_id, coverage.rule.version)
        for coverage in assessment.coverage
    }
    all_subject_refs = tuple(sorted(subjects))
    for index, coverage in enumerate(assessment.coverage):
        references = tuple(
            reference.target_id for reference in coverage.subjects
        )
        _require_unique_and_sorted(
            references,
            location=f"$.coverage[{index}].subjects",
            label="coverage subjects",
        )
        if not set(references) <= subjects:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "coverage names an unknown behavior subject",
                location=f"$.coverage[{index}].subjects",
            )
        if coverage.status == "complete" and references != all_subject_refs:
            raise RatchetValidationError(
                RatchetErrorCode.INCOMPLETE_COVERAGE,
                "complete rule coverage must name every current subject",
                location=f"$.coverage[{index}].subjects",
            )
    for index, violation in enumerate(assessment.violations):
        rule_key = (
            violation.key.rule.target_id,
            violation.key.rule.version,
        )
        if rule_key not in rules:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names a rule absent from assessment coverage",
                location=f"$.violations[{index}].key.rule",
            )
        if violation.key.subject.target_id not in subjects:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names an unknown behavior subject",
                location=f"$.violations[{index}].key.subject",
            )


def _validate_subjects(subjects: tuple, *, location: str) -> None:
    subject_keys = tuple(
        (
            subject.key.subject_uri,
            subject.key.target_kind.value,
            subject.key.target_id,
        )
        for subject in subjects
    )
    _require_unique_and_sorted(
        subject_keys,
        location=location,
        label="assessment subjects",
    )
    subject_ids = tuple(subject.id for subject in subjects)
    if len(subject_ids) != len(set(subject_ids)):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            "assessment subject IDs must be unique",
            location=location,
        )
    for index, subject in enumerate(subjects):
        if subject.id != derive_behavior_subject_id(subject.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "behavior subject ID is not derived from its stable key",
                location=f"{location}[{index}].id",
            )


def _validate_assessment_references(
    policy: RatchetPolicy,
    assessment: RatchetAssessment,
) -> None:
    rules = {(rule.id, rule.version) for rule in policy.rules}
    if len(assessment.coverage) != len(rules):
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "assessment must contain one coverage record per policy rule",
            location="$.coverage",
        )
    for index, coverage in enumerate(assessment.coverage):
        rule_key = (coverage.rule.target_id, coverage.rule.version)
        if rule_key not in rules:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "coverage names an unknown policy rule",
                location=f"$.coverage[{index}].rule",
            )
    for index, violation in enumerate(assessment.violations):
        rule_key = (
            violation.key.rule.target_id,
            violation.key.rule.version,
        )
        if rule_key not in rules:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names an unknown policy rule",
                location=f"$.violations[{index}].key.rule",
            )


def _require_unique_and_sorted(
    values: tuple,
    *,
    location: str,
    label: str,
) -> None:
    if len(values) != len(set(values)):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            f"{label} must be unique",
            location=location,
        )
    if values != tuple(sorted(values)):
        raise RatchetValidationError(
            RatchetErrorCode.NON_CANONICAL_ORDER,
            f"{label} must be in canonical order",
            location=location,
        )
