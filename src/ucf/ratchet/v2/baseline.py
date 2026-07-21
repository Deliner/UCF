from __future__ import annotations

from ucf.onboarding import OnboardingBundle
from ucf.ratchet.v2.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.v2.identity import (
    derive_baseline_id,
    derive_coverage_debt_id,
    derive_violation_id,
)
from ucf.ratchet.v2.models import (
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_VERSION,
    BehaviorBaselineLedger,
    CoverageBaselineLedger,
    RatchetAssessment,
    RatchetBaseline,
    RatchetBaselineOrigin,
    RatchetEvaluationReport,
    RatchetPolicy,
    ViolationClassificationKind,
)
from ucf.ratchet.v2.references import (
    assessment_ref,
    baseline_ref,
    evaluation_ref,
)
from ucf.ratchet.v2.validation import (
    validate_initial_ratchet_baseline,
    validate_ratchet_assessment,
    validate_ratchet_evaluation_report,
    validate_successor_ratchet_baseline,
)


def establish_ratchet_baseline(
    policy: RatchetPolicy,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
) -> RatchetBaseline:
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
    baseline = _derive_initial_baseline(assessment)
    validate_initial_ratchet_baseline(policy, bundle, assessment, baseline)
    return baseline


def _derive_initial_baseline(
    assessment: RatchetAssessment,
) -> RatchetBaseline:
    provisional = RatchetBaseline(
        kind="ratchet_baseline",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        id=f"baseline.{'0' * 64}",
        origin=RatchetBaselineOrigin.INITIAL,
        generation=0,
        policy=assessment.policy,
        source_assessment=assessment_ref(assessment),
        source_evaluation=None,
        predecessor=None,
        migrated_from=None,
        behavior=BehaviorBaselineLedger(
            kind="ratchet_behavior_baseline",
            subjects=assessment.behavior.subjects,
            allowances=tuple(
                sorted(
                    (
                        violation.key
                        for violation in assessment.behavior.violations
                    ),
                    key=derive_violation_id,
                )
            ),
            protected=(),
        ),
        coverage=CoverageBaselineLedger(
            kind="ratchet_coverage_baseline",
            qualification=assessment.coverage.qualification,
            groups=assessment.coverage.groups,
            allowances=assessment.coverage.debts,
            protected=(),
        ),
    )
    return provisional.model_copy(
        update={"id": derive_baseline_id(provisional)}
    )


def advance_ratchet_baseline(
    policy: RatchetPolicy,
    predecessor: RatchetBaseline,
    bundle: OnboardingBundle,
    assessment: RatchetAssessment,
    report: RatchetEvaluationReport,
    *,
    accepted_predecessor_id: str,
) -> RatchetBaseline:
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
            "baseline advance requires a complete public-interface inventory",
            location="$.source_assessment.coverage.inventory_coverage",
        )
    if any(
        coverage.status != "complete"
        for coverage in assessment.behavior.coverage
    ):
        raise RatchetValidationError(
            RatchetErrorCode.INCOMPLETE_RULE_COVERAGE,
            "baseline advance requires complete rule coverage",
            location="$.source_assessment.behavior.coverage",
        )
    if report.combined_outcome not in {
        "pass",
        "pass_with_legacy_coverage_debt",
    }:
        raise RatchetValidationError(
            RatchetErrorCode.ILLEGAL_WEAKENING,
            "only a passing or qualified passing evaluation can advance",
            location="$.combined_outcome",
        )
    successor = _derive_successor_baseline(
        predecessor,
        assessment,
        report,
    )
    validate_successor_ratchet_baseline(
        policy,
        predecessor,
        bundle,
        assessment,
        report,
        successor,
        accepted_predecessor_id=accepted_predecessor_id,
    )
    return successor


def _derive_successor_baseline(
    predecessor: RatchetBaseline,
    assessment: RatchetAssessment,
    report: RatchetEvaluationReport,
) -> RatchetBaseline:
    behavior_allowances = tuple(
        sorted(
            (
                item.key
                for item in report.behavior_classifications
                if item.classification
                is ViolationClassificationKind.UNCHANGED_LEGACY
            ),
            key=derive_violation_id,
        )
    )
    behavior_protected = {
        derive_violation_id(key): key
        for key in predecessor.behavior.protected
    }
    behavior_protected.update(
        {
            derive_violation_id(item.key): item.key
            for item in report.behavior_classifications
            if item.classification is ViolationClassificationKind.RESOLVED
        }
    )
    coverage_protected = {
        derive_coverage_debt_id(key): key
        for key in predecessor.coverage.protected
    }
    coverage_protected.update(
        {
            derive_coverage_debt_id(item.key): item.key
            for item in report.coverage_classifications
            if item.classification.value == "resolved"
        }
    )
    provisional = RatchetBaseline(
        kind="ratchet_baseline",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        id=f"baseline.{'0' * 64}",
        origin=RatchetBaselineOrigin.SUCCESSOR,
        generation=predecessor.generation + 1,
        policy=predecessor.policy,
        source_assessment=assessment_ref(assessment),
        source_evaluation=evaluation_ref(report),
        predecessor=baseline_ref(predecessor),
        migrated_from=None,
        behavior=BehaviorBaselineLedger(
            kind="ratchet_behavior_baseline",
            subjects=assessment.behavior.subjects,
            allowances=behavior_allowances,
            protected=tuple(
                behavior_protected[identifier]
                for identifier in sorted(behavior_protected)
            ),
        ),
        coverage=CoverageBaselineLedger(
            kind="ratchet_coverage_baseline",
            qualification=assessment.coverage.qualification,
            groups=assessment.coverage.groups,
            allowances=assessment.coverage.debts,
            protected=tuple(
                coverage_protected[identifier]
                for identifier in sorted(coverage_protected)
            ),
        ),
    )
    return provisional.model_copy(
        update={"id": derive_baseline_id(provisional)}
    )
