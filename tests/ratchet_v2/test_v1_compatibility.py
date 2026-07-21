from __future__ import annotations

import hashlib
from pathlib import Path

import ucf.ratchet as ratchet_v1

PROJECT_ROOT = Path(__file__).resolve().parents[2]

V1_EXPORTS = (
    "MAX_RATCHET_RULES",
    "MAX_RATCHET_SUBJECTS",
    "MAX_RATCHET_VIOLATIONS",
    "OBSERVED_FINGERPRINT_ALGORITHM_URI",
    "RATCHET_ASSESSMENT_SCHEMA_URI",
    "RATCHET_BASELINE_SCHEMA_URI",
    "RATCHET_EVALUATOR_CAPABILITY",
    "RATCHET_EVALUATION_PROCEDURE_URI",
    "RATCHET_EVALUATION_REPORT_SCHEMA_URI",
    "RATCHET_POLICY_SCHEMA_URI",
    "RATCHET_VERSION",
    "SEMANTIC_FINGERPRINT_ALGORITHM_URI",
    "BehaviorSubjectKey",
    "BehaviorSubjectRef",
    "BehaviorSubjectSnapshot",
    "EvaluationOutcome",
    "ObservedFingerprint",
    "OnboardingBundleRef",
    "RatchetAssessment",
    "RatchetAssessmentRef",
    "RatchetBaseline",
    "RatchetBaselineRef",
    "RatchetEvaluationReport",
    "RatchetEvaluationReportRef",
    "RatchetDocument",
    "RatchetErrorCode",
    "RatchetPolicy",
    "RatchetPolicyRef",
    "RatchetRule",
    "RatchetRuleRef",
    "RatchetViolation",
    "RatchetValidationError",
    "RuleCoverage",
    "SemanticFingerprint",
    "SubjectTrace",
    "SubjectChange",
    "SubjectChangeKind",
    "ViolationInput",
    "ViolationClassification",
    "ViolationClassificationKind",
    "ViolationKey",
    "WeakeningDelta",
    "WeakeningDeltaStatus",
    "advance_ratchet_baseline",
    "build_ratchet_assessment",
    "canonical_ratchet_json",
    "derive_assessment_id",
    "derive_baseline_id",
    "derive_behavior_subject_id",
    "derive_policy_id",
    "derive_evaluation_id",
    "derive_subject_snapshots",
    "derive_violation_id",
    "establish_ratchet_baseline",
    "evaluate_ratchet",
    "parse_ratchet_assessment_json",
    "parse_ratchet_baseline_json",
    "parse_ratchet_evaluation_report_json",
    "parse_ratchet_policy_json",
    "validate_initial_ratchet_baseline",
    "validate_ratchet_assessment",
    "validate_ratchet_baseline_structure",
    "validate_ratchet_evaluation_report",
    "validate_ratchet_policy",
    "validate_successor_ratchet_baseline",
)

FROZEN_SCHEMA_SHA256 = {
    "src/ucf/schemas/evidence_status/v1/assessment.schema.json": (
        "c6b08549c7377298e720d4b52e2be8777ab2a232e27c5d92eb11c5d357b722cc"
    ),
    "src/ucf/schemas/evidence_status/v1/envelope.schema.json": (
        "445288afc98c81d2102ac0e7a58d112ded86857f69362258c3007d18ab8f3032"
    ),
    "src/ucf/schemas/ratchet/v1/assessment.schema.json": (
        "00892992ea665bf55ff296e234b62ff6f018b5c5300389b98f032191e75ecd1c"
    ),
    "src/ucf/schemas/ratchet/v1/baseline.schema.json": (
        "40118901bf382b6ccf9f061456cbd37dc8b84802d3140f1f5c03de7326f78dc0"
    ),
    "src/ucf/schemas/ratchet/v1/evaluation-report.schema.json": (
        "57541c9708c4aeb3af68916bbfbd0f6c37c18f219d252cf4276f16d8ec15579f"
    ),
    "src/ucf/schemas/ratchet/v1/policy.schema.json": (
        "b1679f80ecc3ec6019767e905390df900677b6c972e5a6a9816df30227ee6cf0"
    ),
}


def test_ratchet_v1_public_surface_and_dependent_schema_bytes_are_frozen() -> None:
    assert tuple(ratchet_v1.__all__) == V1_EXPORTS
    assert {
        relative: hashlib.sha256(
            (PROJECT_ROOT / relative).read_bytes()
        ).hexdigest()
        for relative in FROZEN_SCHEMA_SHA256
    } == FROZEN_SCHEMA_SHA256
