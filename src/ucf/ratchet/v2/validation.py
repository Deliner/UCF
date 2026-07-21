from __future__ import annotations

from ucf.onboarding import OnboardingBundle
from ucf.ratchet.v2.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.v2.identity import (
    derive_assessment_id,
    derive_baseline_id,
    derive_behavior_subject_id,
    derive_coverage_debt_id,
    derive_coverage_qualification_id,
    derive_coverage_subject_id,
    derive_evaluation_id,
    derive_policy_id,
    derive_violation_id,
)
from ucf.ratchet.v2.models import (
    BehaviorOutcome,
    BehaviorSubjectChangeKind,
    BehaviorSubjectSnapshot,
    BehaviorWeakeningDelta,
    CombinedOutcome,
    CoverageComparisonStatus,
    CoverageDebtClassificationKind,
    CoverageOutcome,
    CoverageQualification,
    CoverageSubjectChangeKind,
    CoverageSubjectGroup,
    CoverageWeakeningDelta,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    ViolationClassificationKind,
    WeakeningDeltaStatus,
)


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
    from ucf.ratchet.v2.projection import (
        derive_behavior_subject_snapshots,
        derive_coverage_ledger,
    )
    from ucf.ratchet.v2.references import onboarding_bundle_ref, policy_ref

    validate_ratchet_policy(policy)
    validate_ratchet_assessment_structure(assessment)
    if assessment.policy != policy_ref(policy):
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "assessment policy differs from the exact policy",
            location="$.policy",
        )
    if assessment.source != onboarding_bundle_ref(bundle):
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "assessment source differs from the exact onboarding bundle",
            location="$.source",
        )
    expected_subjects = derive_behavior_subject_snapshots(bundle)
    if assessment.behavior.subjects != expected_subjects:
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "behavior subjects differ from their exact bundle projection",
            location="$.behavior.subjects",
        )
    expected_coverage = derive_coverage_ledger(bundle)
    if assessment.coverage != expected_coverage:
        raise RatchetValidationError(
            RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "coverage ledger differs from its exact bundle projection",
            location="$.coverage",
        )
    _validate_assessment_references(policy, assessment)


def validate_ratchet_assessment_structure(
    assessment: RatchetAssessment,
) -> None:
    from ucf.ratchet.v2.projection import _derive_coverage_debts

    _validate_behavior_subjects(assessment)
    _validate_rule_coverage(assessment)
    _validate_violations(assessment)
    _validate_coverage_qualification(
        assessment.coverage.qualification,
        location="$.coverage.qualification",
    )
    groups = assessment.coverage.groups
    _validate_coverage_groups(groups, location="$.coverage.groups")
    expected_debts = _derive_coverage_debts(groups)
    if assessment.coverage.debts != expected_debts:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "coverage debts differ from exact groups and dispositions",
            location="$.coverage.debts",
        )
    debt_ids = tuple(debt.id for debt in assessment.coverage.debts)
    _require_unique_and_sorted(
        debt_ids,
        location="$.coverage.debts",
        label="coverage debts",
    )
    for position, debt in enumerate(assessment.coverage.debts):
        if debt.id != derive_coverage_debt_id(debt.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "coverage debt ID is not derived from its stable key",
                location=f"$.coverage.debts[{position}].id",
            )
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
    from ucf.ratchet.v2.baseline import _derive_initial_baseline

    validate_ratchet_assessment(policy, bundle, assessment)
    if assessment.coverage.inventory_coverage != "complete":
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_COMPARISON_DOMAIN,
            "initial baseline requires a complete public-interface inventory",
            location="$.source_assessment.coverage.inventory_coverage",
        )
    if any(
        coverage.status != "complete"
        for coverage in assessment.behavior.coverage
    ):
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_RULE_COVERAGE,
            "initial baseline requires complete rule coverage",
            location="$.source_assessment.behavior.coverage",
        )
    expected = _derive_initial_baseline(assessment)
    for field, location in (
        ("origin", "$.origin"),
        ("generation", "$.generation"),
        ("policy", "$.policy"),
        ("source_assessment", "$.source_assessment"),
        ("source_evaluation", "$.source_evaluation"),
        ("predecessor", "$.predecessor"),
        ("migrated_from", "$.migrated_from"),
        ("behavior", "$.behavior"),
        ("coverage", "$.coverage"),
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


def validate_successor_ratchet_baseline(
    policy: RatchetPolicy,
    predecessor: RatchetBaseline,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
    report: RatchetEvaluationReport,
    baseline: RatchetBaseline,
    *,
    accepted_predecessor_id: str,
) -> None:
    from ucf.ratchet.v2.baseline import _derive_successor_baseline

    validate_ratchet_evaluation_report(
        policy,
        predecessor,
        bundle,
        assessment,
        report,
        accepted_baseline_id=accepted_predecessor_id,
    )
    if assessment.coverage.inventory_coverage != "complete":
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_COMPARISON_DOMAIN,
            "successor requires a complete public-interface inventory",
            location="$.source_assessment.coverage.inventory_coverage",
        )
    if any(
        coverage.status != "complete"
        for coverage in assessment.behavior.coverage
    ):
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_RULE_COVERAGE,
            "successor requires complete rule coverage",
            location="$.source_assessment.behavior.coverage",
        )
    if report.combined_outcome not in {
        CombinedOutcome.PASS,
        CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT,
    }:
        raise RatchetValidationError(
            RatchetErrorCode.ILLEGAL_WEAKENING,
            "successor requires a passing or qualified passing evaluation",
            location="$.source_evaluation",
        )
    expected = _derive_successor_baseline(
        predecessor,
        assessment,
        report,
    )
    for field in RatchetBaseline.model_fields:
        if getattr(baseline, field) != getattr(expected, field):
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "successor differs from its exact accepted evaluation",
                location=f"$.{field}",
            )
    validate_ratchet_baseline_structure(baseline)


def validate_migrated_ratchet_baseline(
    target_policy,
    source_policy,
    source_baseline,
    source_assessment,
    bundle: OnboardingBundle,
    baseline: RatchetBaseline,
    *,
    accepted_source_baseline_id: str,
) -> None:
    from ucf.ratchet.v2.migration import (
        _derive_migrated_baseline,
        _validate_migration_sources,
    )

    _validate_migration_sources(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
        accepted_source_baseline_id=accepted_source_baseline_id,
    )
    expected = _derive_migrated_baseline(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
    )
    for field in RatchetBaseline.model_fields:
        if getattr(baseline, field) != getattr(expected, field):
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "migrated baseline differs from its exact v1 source",
                location=f"$.{field}",
            )
    validate_ratchet_baseline_structure(baseline)


def validate_ratchet_baseline_structure(
    baseline: RatchetBaseline,
) -> None:
    _validate_behavior_subject_sequence(
        baseline.behavior.subjects,
        location="$.behavior.subjects",
    )
    subject_ids = {subject.id for subject in baseline.behavior.subjects}
    allowance_ids = tuple(
        derive_violation_id(key) for key in baseline.behavior.allowances
    )
    protected_ids = tuple(
        derive_violation_id(key) for key in baseline.behavior.protected
    )
    _require_unique_and_sorted(
        allowance_ids,
        location="$.behavior.allowances",
        label="behavior allowances",
    )
    _require_unique_and_sorted(
        protected_ids,
        location="$.behavior.protected",
        label="protected behavior resolutions",
    )
    if set(allowance_ids) & set(protected_ids):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            "behavior allowances and protections must be disjoint",
            location="$.behavior",
        )
    if any(
        key.subject.target_id not in subject_ids
        for key in baseline.behavior.allowances
    ):
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "behavior allowance names an unknown current subject",
            location="$.behavior.allowances",
        )

    _validate_coverage_qualification(
        baseline.coverage.qualification,
        location="$.coverage.qualification",
    )
    _validate_coverage_groups(
        baseline.coverage.groups,
        location="$.coverage.groups",
    )
    from ucf.ratchet.v2.projection import _derive_coverage_debts

    projected_debt_sequence = _derive_coverage_debts(
        baseline.coverage.groups
    )
    if baseline.coverage.allowances != projected_debt_sequence:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "coverage allowances must equal all current unresolved debt",
            location="$.coverage.allowances",
        )
    projected_debts = {
        debt.id: debt for debt in projected_debt_sequence
    }
    coverage_allowance_ids = tuple(
        debt.id for debt in baseline.coverage.allowances
    )
    _require_unique_and_sorted(
        coverage_allowance_ids,
        location="$.coverage.allowances",
        label="coverage allowances",
    )
    for position, debt in enumerate(baseline.coverage.allowances):
        if debt.id != derive_coverage_debt_id(debt.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "coverage allowance ID is not derived from its stable key",
                location=f"$.coverage.allowances[{position}].id",
            )
        if projected_debts.get(debt.id) != debt:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "coverage allowance is absent from the current group state",
                location=f"$.coverage.allowances[{position}]",
            )
    coverage_protected_ids = tuple(
        derive_coverage_debt_id(key) for key in baseline.coverage.protected
    )
    _require_unique_and_sorted(
        coverage_protected_ids,
        location="$.coverage.protected",
        label="protected coverage resolutions",
    )
    if set(coverage_allowance_ids) & set(coverage_protected_ids):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            "coverage allowances and protections must be disjoint",
            location="$.coverage",
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
    *,
    accepted_baseline_id: str,
) -> None:
    from ucf.ratchet.v2.evaluation import evaluate_ratchet

    validate_ratchet_evaluation_report_structure(report)
    expected = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        assessment,
        accepted_baseline_id=accepted_baseline_id,
    )
    for field in RatchetEvaluationReport.model_fields:
        if getattr(report, field) != getattr(expected, field):
            raise RatchetValidationError(
                RatchetErrorCode.SUMMARY_MISMATCH,
                "evaluation report differs from the exact recomputed result",
                location=f"$.{field}",
            )


def validate_ratchet_evaluation_report_structure(
    report: RatchetEvaluationReport,
) -> None:
    behavior_subject_ids = tuple(
        item.subject.target_id for item in report.behavior_subject_changes
    )
    _require_unique_and_sorted(
        behavior_subject_ids,
        location="$.behavior_subject_changes",
        label="behavior subject changes",
    )
    behavior_classification_ids = tuple(
        derive_violation_id(item.key)
        for item in report.behavior_classifications
    )
    _require_unique_and_sorted(
        behavior_classification_ids,
        location="$.behavior_classifications",
        label="behavior classifications",
    )
    if any(
        item.key.subject.target_id not in set(behavior_subject_ids)
        for item in report.behavior_classifications
    ):
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "behavior classification names an unknown report subject",
            location="$.behavior_classifications",
        )

    coverage_subject_ids = tuple(
        item.subject.target_id for item in report.coverage_subject_changes
    )
    _require_unique_and_sorted(
        coverage_subject_ids,
        location="$.coverage_subject_changes",
        label="coverage subject changes",
    )
    coverage_classification_ids = tuple(
        derive_coverage_debt_id(item.key)
        for item in report.coverage_classifications
    )
    _require_unique_and_sorted(
        coverage_classification_ids,
        location="$.coverage_classifications",
        label="coverage classifications",
    )
    if any(
        item.key.subject.target_id not in set(coverage_subject_ids)
        for item in report.coverage_classifications
    ):
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "coverage classification names an unknown report subject",
            location="$.coverage_classifications",
        )
    _validate_report_deltas(report)
    _validate_report_outcomes(report)
    if report.id != derive_evaluation_id(report):
        raise RatchetValidationError(
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
            "evaluation ID is not derived from its exact content",
            location="$.id",
        )


def _validate_report_deltas(report: RatchetEvaluationReport) -> None:
    behavior_regressions = {
        ViolationClassificationKind.NEW_REGRESSION,
        ViolationClassificationKind.REINTRODUCED,
        ViolationClassificationKind.TOUCHED_LEGACY,
    }
    expected_behavior_added = tuple(
        item.key
        for item in report.behavior_classifications
        if item.classification in behavior_regressions
    )
    expected_behavior_removed = tuple(
        item.key
        for item in report.behavior_classifications
        if item.classification is ViolationClassificationKind.RESOLVED
    )
    expected_behavior_unprotected = tuple(
        item.key
        for item in report.behavior_classifications
        if item.classification is ViolationClassificationKind.REINTRODUCED
    )
    expected_behavior_delta = BehaviorWeakeningDelta(
        kind="ratchet_behavior_delta",
        status=_expected_delta_status(
            expected_behavior_added,
            expected_behavior_removed,
        ),
        added_allowances=expected_behavior_added,
        removed_allowances=expected_behavior_removed,
        removed_protections=expected_behavior_unprotected,
    )
    if report.behavior_delta != expected_behavior_delta:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "behavior delta differs from exact classifications",
            location="$.behavior_delta",
        )

    coverage_regressions = {
        CoverageDebtClassificationKind.NEW_REGRESSION,
        CoverageDebtClassificationKind.CHANGED_REGRESSION,
        CoverageDebtClassificationKind.REINTRODUCED,
    }
    expected_coverage_added = tuple(
        item.key
        for item in report.coverage_classifications
        if item.classification in coverage_regressions
    )
    expected_coverage_removed = tuple(
        item.key
        for item in report.coverage_classifications
        if item.classification is CoverageDebtClassificationKind.RESOLVED
    )
    expected_coverage_unprotected = tuple(
        item.key
        for item in report.coverage_classifications
        if item.classification is CoverageDebtClassificationKind.REINTRODUCED
    )
    expected_coverage_delta = CoverageWeakeningDelta(
        kind="ratchet_coverage_delta",
        status=_expected_delta_status(
            expected_coverage_added,
            expected_coverage_removed,
        ),
        added_allowances=expected_coverage_added,
        removed_allowances=expected_coverage_removed,
        removed_protections=expected_coverage_unprotected,
    )
    if report.coverage_delta != expected_coverage_delta:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "coverage delta differs from exact classifications",
            location="$.coverage_delta",
        )


def _validate_report_outcomes(report: RatchetEvaluationReport) -> None:
    behavior_regressions = {
        ViolationClassificationKind.NEW_REGRESSION,
        ViolationClassificationKind.REINTRODUCED,
        ViolationClassificationKind.TOUCHED_LEGACY,
    }
    if any(
        item.classification in behavior_regressions
        for item in report.behavior_classifications
    ):
        allowed_behavior = {BehaviorOutcome.FAIL}
    elif any(
        item.classification is ViolationClassificationKind.UNKNOWN
        for item in report.behavior_classifications
    ) or any(
        item.change is BehaviorSubjectChangeKind.UNKNOWN_SUBJECT
        for item in report.behavior_subject_changes
    ):
        allowed_behavior = {BehaviorOutcome.INCONCLUSIVE}
    else:
        allowed_behavior = {BehaviorOutcome.PASS, BehaviorOutcome.INCONCLUSIVE}
    if report.behavior_outcome not in allowed_behavior:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "behavior outcome differs from internal evidence",
            location="$.behavior_outcome",
        )

    coverage_regressions = {
        CoverageDebtClassificationKind.NEW_REGRESSION,
        CoverageDebtClassificationKind.CHANGED_REGRESSION,
        CoverageDebtClassificationKind.REINTRODUCED,
    }
    if any(
        item.classification in coverage_regressions
        for item in report.coverage_classifications
    ):
        expected_coverage = CoverageOutcome.FAIL
    elif (
        report.coverage_comparison is not CoverageComparisonStatus.COMPARABLE
        or any(
            item.classification is CoverageDebtClassificationKind.UNKNOWN
            for item in report.coverage_classifications
        )
        or any(
            item.change is CoverageSubjectChangeKind.UNKNOWN_SUBJECT
            for item in report.coverage_subject_changes
        )
    ):
        expected_coverage = CoverageOutcome.INCONCLUSIVE
    elif any(
        item.classification
        is CoverageDebtClassificationKind.UNCHANGED_LEGACY
        for item in report.coverage_classifications
    ):
        expected_coverage = CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    else:
        expected_coverage = CoverageOutcome.PASS
    if report.coverage_outcome is not expected_coverage:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "coverage outcome differs from internal evidence",
            location="$.coverage_outcome",
        )
    expected_combined = _expected_combined_outcome(
        report.behavior_outcome,
        report.coverage_outcome,
    )
    if report.combined_outcome is not expected_combined:
        raise RatchetValidationError(
            RatchetErrorCode.SUMMARY_MISMATCH,
            "combined outcome differs from component outcomes",
            location="$.combined_outcome",
        )


def _expected_delta_status(added: tuple, removed: tuple) -> WeakeningDeltaStatus:
    if added:
        return WeakeningDeltaStatus.REVIEW_REQUIRED
    if removed:
        return WeakeningDeltaStatus.TIGHTENING
    return WeakeningDeltaStatus.NONE


def _expected_combined_outcome(
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


def _validate_coverage_qualification(
    qualification: CoverageQualification,
    *,
    location: str,
) -> None:
    if qualification.id != derive_coverage_qualification_id(qualification):
        raise RatchetValidationError(
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
            "coverage qualification ID differs from its exact content",
            location=f"{location}.id",
        )
    _require_unique_and_sorted(
        qualification.inventory_procedure_uris,
        location=f"{location}.inventory_procedure_uris",
        label="inventory procedure URIs",
    )


def _validate_coverage_groups(
    groups: tuple[CoverageSubjectGroup, ...],
    *,
    location: str,
) -> None:
    from ucf.ratchet.v2.projection import _coverage_semantic_fingerprint

    group_keys = tuple(
        (
            group.key.subject_uri,
            group.key.target_kind,
            group.key.interface_kind_uri,
            group.key.container or "",
            group.key.name,
        )
        for group in groups
    )
    if len(group_keys) != len(set(group_keys)):
        raise RatchetValidationError(
            RatchetErrorCode.AMBIGUOUS_COVERAGE_IDENTITY,
            "coverage subject keys must be unique",
            location=location,
        )
    if group_keys != tuple(sorted(group_keys)):
        raise RatchetValidationError(
            RatchetErrorCode.NON_CANONICAL_ORDER,
            "coverage groups must be in stable-key order",
            location=location,
        )
    for position, group in enumerate(groups):
        if group.id != derive_coverage_subject_id(group.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "coverage subject ID is not derived from its stable key",
                location=f"{location}[{position}].id",
            )
        reconciliation_keys = tuple(
            (
                item.candidate_semantic_digest.value,
                item.disposition.value,
                ""
                if item.replacement_semantic_digest is None
                else item.replacement_semantic_digest.value,
            )
            for item in group.reconciliations
        )
        semantic_ids = tuple(key[0] for key in reconciliation_keys)
        reconciliation_location = (
            f"{location}[{position}].reconciliations"
        )
        if len(semantic_ids) != len(set(semantic_ids)):
            raise RatchetValidationError(
                RatchetErrorCode.AMBIGUOUS_COVERAGE_IDENTITY,
                "candidate semantic identities must be unique per subject",
                location=reconciliation_location,
            )
        if reconciliation_keys != tuple(sorted(reconciliation_keys)):
            raise RatchetValidationError(
                RatchetErrorCode.NON_CANONICAL_ORDER,
                "coverage reconciliations must be canonically ordered",
                location=reconciliation_location,
            )
        for reconciliation_position, item in enumerate(group.reconciliations):
            expected_semantic = _coverage_semantic_fingerprint(
                {
                    "candidate_semantic_digest": (
                        item.candidate_semantic_digest.model_dump(mode="json")
                    ),
                    "disposition": item.disposition.value,
                    "replacement_semantic_digest": (
                        None
                        if item.replacement_semantic_digest is None
                        else item.replacement_semantic_digest.model_dump(
                            mode="json"
                        )
                    ),
                }
            )
            if item.semantic != expected_semantic:
                raise RatchetValidationError(
                    RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                    "reconciliation semantic fingerprint is not derived",
                    location=(
                        f"{reconciliation_location}"
                        f"[{reconciliation_position}].semantic"
                    ),
                )
        expected_group_semantic = _coverage_semantic_fingerprint(
            {
                "state": group.state.value,
                "reconciliations": [
                    item.semantic.digest.model_dump(mode="json")
                    for item in group.reconciliations
                ],
            }
        )
        if group.semantic != expected_group_semantic:
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "coverage group semantic fingerprint is not derived",
                location=f"{location}[{position}].semantic",
            )


def _validate_behavior_subjects(assessment: RatchetAssessment) -> None:
    _validate_behavior_subject_sequence(
        assessment.behavior.subjects,
        location="$.behavior.subjects",
    )


def _validate_behavior_subject_sequence(
    subjects: tuple[BehaviorSubjectSnapshot, ...],
    *,
    location: str,
) -> None:
    keys = tuple(
        (
            subject.key.subject_uri,
            subject.key.target_kind.value,
            subject.key.target_id,
        )
        for subject in subjects
    )
    _require_unique_and_sorted(
        keys,
        location=location,
        label="behavior subjects",
    )
    ids = tuple(subject.id for subject in subjects)
    if len(ids) != len(set(ids)):
        raise RatchetValidationError(
            RatchetErrorCode.DUPLICATE_IDENTITY,
            "behavior subject IDs must be unique",
            location=location,
        )
    for position, subject in enumerate(subjects):
        if subject.id != derive_behavior_subject_id(subject.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "behavior subject ID is not derived from its stable key",
                location=f"{location}[{position}].id",
            )


def _validate_rule_coverage(assessment: RatchetAssessment) -> None:
    subject_ids = tuple(
        subject.id for subject in assessment.behavior.subjects
    )
    coverage_keys = tuple(
        (item.rule.target_id, item.rule.version)
        for item in assessment.behavior.coverage
    )
    _require_unique_and_sorted(
        coverage_keys,
        location="$.behavior.coverage",
        label="rule coverage",
    )
    for position, item in enumerate(assessment.behavior.coverage):
        references = tuple(ref.target_id for ref in item.subjects)
        _require_unique_and_sorted(
            references,
            location=f"$.behavior.coverage[{position}].subjects",
            label="rule coverage subjects",
        )
        if not set(references) <= set(subject_ids):
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "rule coverage names an unknown behavior subject",
                location=f"$.behavior.coverage[{position}].subjects",
            )
        if item.status == "complete" and references != tuple(sorted(subject_ids)):
            raise RatchetValidationError(
                RatchetErrorCode.INCOMPLETE_RULE_COVERAGE,
                "complete rule coverage must name every behavior subject",
                location=f"$.behavior.coverage[{position}].subjects",
            )


def _validate_violations(assessment: RatchetAssessment) -> None:
    subject_ids = {subject.id for subject in assessment.behavior.subjects}
    coverage_rules = {
        (item.rule.target_id, item.rule.version)
        for item in assessment.behavior.coverage
    }
    violation_ids = tuple(
        violation.id for violation in assessment.behavior.violations
    )
    _require_unique_and_sorted(
        violation_ids,
        location="$.behavior.violations",
        label="violations",
    )
    for position, violation in enumerate(assessment.behavior.violations):
        if violation.id != derive_violation_id(violation.key):
            raise RatchetValidationError(
                RatchetErrorCode.CONTENT_IDENTITY_MISMATCH,
                "violation ID is not derived from its stable key",
                location=f"$.behavior.violations[{position}].id",
            )
        rule_key = (
            violation.key.rule.target_id,
            violation.key.rule.version,
        )
        if rule_key not in coverage_rules:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names a rule absent from coverage",
                location=f"$.behavior.violations[{position}].key.rule",
            )
        if violation.key.subject.target_id not in subject_ids:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "violation names an unknown behavior subject",
                location=f"$.behavior.violations[{position}].key.subject",
            )


def _validate_assessment_references(
    policy: RatchetPolicy,
    assessment: RatchetAssessment,
) -> None:
    rules = {(rule.id, rule.version) for rule in policy.rules}
    coverage_rules = {
        (item.rule.target_id, item.rule.version)
        for item in assessment.behavior.coverage
    }
    if coverage_rules != rules or len(assessment.behavior.coverage) != len(rules):
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "assessment requires one coverage record per policy rule",
            location="$.behavior.coverage",
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
