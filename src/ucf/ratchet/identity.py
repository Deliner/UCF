from __future__ import annotations

import hashlib
import json

from ucf.ratchet.models import (
    BehaviorSubjectKey,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
    ViolationKey,
)


def derive_policy_id(policy: RatchetPolicy) -> str:
    projection = policy.model_dump(mode="json", exclude={"id"})
    return "policy." + _digest_value(projection)


def derive_assessment_id(assessment: RatchetAssessment) -> str:
    projection = assessment.model_dump(mode="json", exclude={"id"})
    return "assessment." + _digest_value(projection)


def derive_behavior_subject_id(key: BehaviorSubjectKey) -> str:
    return "subject." + _digest_value(key.model_dump(mode="json"))


def derive_violation_id(key: ViolationKey) -> str:
    return "violation." + _digest_value(key.model_dump(mode="json"))


def derive_projection_digest(value: object) -> str:
    return _digest_value(value)


def derive_baseline_id(baseline: RatchetBaseline) -> str:
    projection = baseline.model_dump(mode="json", exclude={"id"})
    return "baseline." + _digest_value(projection)


def derive_evaluation_id(report: RatchetEvaluationReport) -> str:
    projection = report.model_dump(mode="json", exclude={"id"})
    return "evaluation." + _digest_value(projection)


def _digest_value(value: object) -> str:
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
