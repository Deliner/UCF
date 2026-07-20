from __future__ import annotations

from ucf.ir.models import Digest
from ucf.ratchet.identity import derive_projection_digest
from ucf.ratchet.models import (
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetAssessment,
    RatchetAssessmentRef,
    RatchetBaseline,
    RatchetBaselineRef,
    RatchetEvaluationReport,
    RatchetEvaluationReportRef,
    RatchetPolicy,
    RatchetPolicyRef,
)


def policy_ref(policy: RatchetPolicy) -> RatchetPolicyRef:
    return RatchetPolicyRef(
        kind="ratchet_policy_ref",
        schema_uri=RATCHET_POLICY_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=policy.id,
        canonical_digest=_model_digest(policy),
    )


def assessment_ref(
    assessment: RatchetAssessment,
) -> RatchetAssessmentRef:
    return RatchetAssessmentRef(
        kind="ratchet_assessment_ref",
        schema_uri=RATCHET_ASSESSMENT_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=assessment.id,
        canonical_digest=_model_digest(assessment),
    )


def baseline_ref(baseline: RatchetBaseline) -> RatchetBaselineRef:
    return RatchetBaselineRef(
        kind="ratchet_baseline_ref",
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=baseline.id,
        canonical_digest=_model_digest(baseline),
        generation=baseline.generation,
    )


def evaluation_ref(
    report: RatchetEvaluationReport,
) -> RatchetEvaluationReportRef:
    return RatchetEvaluationReportRef(
        kind="ratchet_evaluation_report_ref",
        schema_uri=RATCHET_EVALUATION_REPORT_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=report.id,
        canonical_digest=_model_digest(report),
    )


def _model_digest(model) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=derive_projection_digest(model.model_dump(mode="json")),
    )
