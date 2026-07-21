from __future__ import annotations

import hashlib

from ucf.ir.models import Digest
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    OnboardingBundle,
    canonical_onboarding_digest,
)
from ucf.ratchet.v2.codec import canonical_ratchet_json
from ucf.ratchet.v2.models import (
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    OnboardingBundleRef,
    RatchetAssessment,
    RatchetAssessmentRef,
    RatchetBaseline,
    RatchetBaselineRef,
    RatchetEvaluationReport,
    RatchetEvaluationReportRef,
    RatchetPolicy,
    RatchetPolicyRef,
    RatchetV1AssessmentRef,
    RatchetV1BaselineRef,
    RatchetV1PolicyRef,
)


def policy_ref(policy: RatchetPolicy) -> RatchetPolicyRef:
    return RatchetPolicyRef(
        kind="ratchet_policy_ref",
        schema_uri=RATCHET_POLICY_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=policy.id,
        canonical_digest=_digest(canonical_ratchet_json(policy)),
    )


def onboarding_bundle_ref(bundle: OnboardingBundle) -> OnboardingBundleRef:
    return OnboardingBundleRef(
        kind="onboarding_bundle_ref",
        schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
        schema_version=ONBOARDING_VERSION,
        canonical_digest=canonical_onboarding_digest(bundle),
    )


def assessment_ref(assessment: RatchetAssessment) -> RatchetAssessmentRef:
    return RatchetAssessmentRef(
        kind="ratchet_assessment_ref",
        schema_uri=RATCHET_ASSESSMENT_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=assessment.id,
        canonical_digest=_digest(canonical_ratchet_json(assessment)),
    )


def baseline_ref(baseline: RatchetBaseline) -> RatchetBaselineRef:
    return RatchetBaselineRef(
        kind="ratchet_baseline_ref",
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
        schema_version=RATCHET_VERSION,
        target_id=baseline.id,
        canonical_digest=_digest(canonical_ratchet_json(baseline)),
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
        canonical_digest=_digest(canonical_ratchet_json(report)),
    )


def v1_policy_ref(policy) -> RatchetV1PolicyRef:
    from ucf.ratchet import canonical_ratchet_json as canonical_v1_json

    return RatchetV1PolicyRef(
        kind="ratchet_policy_ref",
        schema_uri="urn:ucf:ratchet:policy:1.0.0",
        schema_version="1.0.0",
        target_id=policy.id,
        canonical_digest=_digest(canonical_v1_json(policy)),
    )


def v1_assessment_ref(assessment) -> RatchetV1AssessmentRef:
    from ucf.ratchet import canonical_ratchet_json as canonical_v1_json

    return RatchetV1AssessmentRef(
        kind="ratchet_assessment_ref",
        schema_uri="urn:ucf:ratchet:assessment:1.0.0",
        schema_version="1.0.0",
        target_id=assessment.id,
        canonical_digest=_digest(canonical_v1_json(assessment)),
    )


def v1_baseline_ref(baseline) -> RatchetV1BaselineRef:
    from ucf.ratchet import canonical_ratchet_json as canonical_v1_json

    return RatchetV1BaselineRef(
        kind="ratchet_baseline_ref",
        schema_uri="urn:ucf:ratchet:baseline:1.0.0",
        schema_version="1.0.0",
        target_id=baseline.id,
        canonical_digest=_digest(canonical_v1_json(baseline)),
        generation=baseline.generation,
    )


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )
