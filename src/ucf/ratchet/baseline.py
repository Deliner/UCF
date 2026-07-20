from __future__ import annotations

from ucf.onboarding import OnboardingBundle
from ucf.ratchet.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.identity import (
    derive_baseline_id,
    derive_violation_id,
)
from ucf.ratchet.models import (
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_VERSION,
    EvaluationOutcome,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    ViolationClassificationKind,
)
from ucf.ratchet.references import (
    assessment_ref,
    baseline_ref,
    evaluation_ref,
)
from ucf.ratchet.validation import (
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
    baseline = _derive_initial_baseline(assessment)
    validate_initial_ratchet_baseline(
        policy,
        bundle,
        assessment,
        baseline,
    )
    return baseline


def _derive_initial_baseline(
    assessment: RatchetAssessment,
) -> RatchetBaseline:
    provisional = RatchetBaseline(
        kind="ratchet_baseline",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        id=f"baseline.{'0' * 64}",
        generation=0,
        policy=assessment.policy,
        source_assessment=assessment_ref(assessment),
        source_evaluation=None,
        predecessor=None,
        subjects=assessment.subjects,
        allowances=tuple(
            sorted(
                (violation.key for violation in assessment.violations),
                key=derive_violation_id,
            )
        ),
        protected=(),
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
) -> RatchetBaseline:
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
            "baseline advance requires complete subject and rule coverage",
            location="$.source_assessment.coverage",
        )
    if report.outcome is not EvaluationOutcome.PASS:
        raise RatchetValidationError(
            RatchetErrorCode.ILLEGAL_WEAKENING,
            "only a passing evaluation can advance the accepted baseline",
            location="$.outcome",
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
    )
    return successor


def _derive_successor_baseline(
    predecessor: RatchetBaseline,
    assessment: RatchetAssessment,
    report: RatchetEvaluationReport,
) -> RatchetBaseline:
    allowances = tuple(
        sorted(
            (
                item.key
                for item in report.classifications
                if item.classification
                is ViolationClassificationKind.UNCHANGED_LEGACY
            ),
            key=derive_violation_id,
        )
    )
    resolved = {
        derive_violation_id(item.key): item.key
        for item in report.classifications
        if item.classification is ViolationClassificationKind.RESOLVED
    }
    protected = {
        derive_violation_id(key): key for key in predecessor.protected
    }
    protected.update(resolved)
    provisional = RatchetBaseline(
        kind="ratchet_baseline",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        id=f"baseline.{'0' * 64}",
        generation=predecessor.generation + 1,
        policy=predecessor.policy,
        source_assessment=assessment_ref(assessment),
        source_evaluation=evaluation_ref(report),
        predecessor=baseline_ref(predecessor),
        subjects=assessment.subjects,
        allowances=allowances,
        protected=tuple(
            protected[identifier] for identifier in sorted(protected)
        ),
    )
    return provisional.model_copy(
        update={"id": derive_baseline_id(provisional)}
    )
