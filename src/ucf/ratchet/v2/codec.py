from __future__ import annotations

import json

from pydantic import ValidationError

from ucf.ir import decode_strict_json_object
from ucf.ratchet.v2.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.v2.models import (
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
)
from ucf.ratchet.v2.validation import (
    validate_ratchet_assessment_structure,
    validate_ratchet_baseline_structure,
    validate_ratchet_evaluation_report_structure,
    validate_ratchet_policy,
)

type RatchetDocument = (
    RatchetAssessment | RatchetBaseline | RatchetEvaluationReport | RatchetPolicy
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
    decoded = _decode_ratchet_document(
        payload,
        kind="ratchet_policy",
        schema_uri=RATCHET_POLICY_SCHEMA_URI,
    )
    _require_supported_evaluator(decoded)
    policy = _validate_model(decoded, RatchetPolicy)
    validate_ratchet_policy(policy)
    return policy


def parse_ratchet_assessment_json(
    payload: str | bytes,
) -> RatchetAssessment:
    decoded = _decode_ratchet_document(
        payload,
        kind="ratchet_assessment",
        schema_uri=RATCHET_ASSESSMENT_SCHEMA_URI,
    )
    assessment = _validate_model(decoded, RatchetAssessment)
    validate_ratchet_assessment_structure(assessment)
    return assessment


def parse_ratchet_baseline_json(payload: str | bytes) -> RatchetBaseline:
    decoded = _decode_ratchet_document(
        payload,
        kind="ratchet_baseline",
        schema_uri=RATCHET_BASELINE_SCHEMA_URI,
    )
    baseline = _validate_model(decoded, RatchetBaseline)
    validate_ratchet_baseline_structure(baseline)
    return baseline


def parse_ratchet_evaluation_report_json(
    payload: str | bytes,
) -> RatchetEvaluationReport:
    decoded = _decode_ratchet_document(
        payload,
        kind="ratchet_evaluation_report",
        schema_uri=RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    )
    report = _validate_model(decoded, RatchetEvaluationReport)
    validate_ratchet_evaluation_report_structure(report)
    return report


def _decode_ratchet_document(
    payload: str | bytes,
    *,
    kind: str,
    schema_uri: str,
) -> dict:
    decoded = decode_strict_json_object(payload)
    if decoded.get("ratchet_version") != RATCHET_VERSION:
        raise RatchetValidationError(
            RatchetErrorCode.UNSUPPORTED_RATCHET_VERSION,
            f"Ratchet profile {RATCHET_VERSION} is required",
            location="$.ratchet_version",
        )
    for coordinate, expected in (("kind", kind), ("schema_uri", schema_uri)):
        if decoded.get(coordinate) != expected:
            raise RatchetValidationError(
                RatchetErrorCode.WRONG_TARGET_KIND,
                f"expected {coordinate} {expected!r}",
                location=f"$.{coordinate}",
            )
    return decoded


def _require_supported_evaluator(decoded: dict) -> None:
    evaluator = decoded.get("evaluator")
    if not isinstance(evaluator, dict):
        return
    expected = {
        "name": RATCHET_EVALUATOR_CAPABILITY,
        "version": RATCHET_VERSION,
    }
    for coordinate, value in expected.items():
        if evaluator.get(coordinate) != value:
            raise RatchetValidationError(
                RatchetErrorCode.UNSUPPORTED_CAPABILITY,
                "ratchet evaluator must be "
                f"{RATCHET_EVALUATOR_CAPABILITY}@{RATCHET_VERSION}",
                location=f"$.evaluator.{coordinate}",
            )


def _validate_model(decoded: dict, model):
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    try:
        return model.model_validate_json(normalized)
    except ValidationError as exc:
        limit_error = next(
            (error for error in exc.errors() if error["type"] == "too_long"),
            None,
        )
        if limit_error is None:
            raise
        raise RatchetValidationError(
            RatchetErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "collection exceeds its published maximum size",
            location=_json_path(limit_error["loc"]),
        ) from None


def _json_path(location: tuple[str | int, ...]) -> str:
    path = "$"
    for coordinate in location:
        if isinstance(coordinate, int):
            path += f"[{coordinate}]"
        else:
            path += f".{coordinate}"
    return path
