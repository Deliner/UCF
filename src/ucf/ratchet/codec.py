from __future__ import annotations

import json

from ucf.ir import decode_strict_json_object
from ucf.ratchet.models import (
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
)
from ucf.ratchet.validation import (
    validate_ratchet_assessment_structure,
    validate_ratchet_baseline_structure,
    validate_ratchet_evaluation_report_structure,
    validate_ratchet_policy,
)

type RatchetDocument = (
    RatchetPolicy
    | RatchetAssessment
    | RatchetBaseline
    | RatchetEvaluationReport
)


def canonical_ratchet_json(document: RatchetDocument) -> bytes:
    return (
        json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def parse_ratchet_policy_json(payload: str | bytes) -> RatchetPolicy:
    policy = _parse_ratchet_json(payload, RatchetPolicy)
    validate_ratchet_policy(policy)
    return policy


def parse_ratchet_assessment_json(
    payload: str | bytes,
) -> RatchetAssessment:
    assessment = _parse_ratchet_json(payload, RatchetAssessment)
    validate_ratchet_assessment_structure(assessment)
    return assessment


def parse_ratchet_baseline_json(payload: str | bytes) -> RatchetBaseline:
    baseline = _parse_ratchet_json(payload, RatchetBaseline)
    validate_ratchet_baseline_structure(baseline)
    return baseline


def parse_ratchet_evaluation_report_json(
    payload: str | bytes,
) -> RatchetEvaluationReport:
    report = _parse_ratchet_json(payload, RatchetEvaluationReport)
    validate_ratchet_evaluation_report_structure(report)
    return report


def _parse_ratchet_json(payload, model):
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)
