from __future__ import annotations

import hashlib
import json

from ucf.ratchet.v2.models import (
    BehaviorSubjectKey,
    CoverageDebtKey,
    CoverageQualification,
    CoverageSubjectKey,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    ViolationKey,
)


def derive_policy_id(policy: RatchetPolicy) -> str:
    payload = policy.model_dump(mode="json", exclude={"id"})
    return "policy." + hashlib.sha256(_canonical_identity_bytes(payload)).hexdigest()


def derive_assessment_id(assessment: RatchetAssessment) -> str:
    payload = assessment.model_dump(mode="json", exclude={"id"})
    return "assessment." + _identity_digest(payload)


def derive_baseline_id(baseline: RatchetBaseline) -> str:
    payload = baseline.model_dump(mode="json", exclude={"id"})
    return "baseline." + _identity_digest(payload)


def derive_evaluation_id(report: RatchetEvaluationReport) -> str:
    payload = report.model_dump(mode="json", exclude={"id"})
    return "evaluation." + _identity_digest(payload)


def derive_behavior_subject_id(key: BehaviorSubjectKey) -> str:
    return "subject." + _identity_digest(key.model_dump(mode="json"))


def derive_coverage_qualification_id(
    qualification: CoverageQualification,
) -> str:
    payload = qualification.model_dump(mode="json", exclude={"id"})
    return "domain." + _identity_digest(payload)


def derive_coverage_subject_id(key: CoverageSubjectKey) -> str:
    return "coverage." + _identity_digest(key.model_dump(mode="json"))


def derive_coverage_debt_id(key: CoverageDebtKey) -> str:
    return "debt." + _identity_digest(key.model_dump(mode="json"))


def derive_violation_id(key: ViolationKey) -> str:
    return "violation." + _identity_digest(key.model_dump(mode="json"))


def derive_projection_digest(value: object) -> str:
    return _identity_digest(value)


def _identity_digest(value: object) -> str:
    return hashlib.sha256(_canonical_identity_bytes(value)).hexdigest()


def _canonical_identity_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
