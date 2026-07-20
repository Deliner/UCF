from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from ucf.evidence_status import (
    EVIDENCE_STATUS_VERSION,
    VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI,
    VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
    EvidenceStatusReasonCode,
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
    assess_verification_evidence,
    canonical_evidence_status_json,
    parse_verification_evidence_assessment_json,
    parse_verification_evidence_envelope_json,
    record_verification_evidence,
)

from ._support import (
    baseline_context,
    current_assessment_arguments,
    record_arguments,
    recorded_assessment_arguments,
    target_source_context,
)

_RECORD_PROCEDURE_URI = "urn:ucf:evidence-status:record:1.0.0"
_ASSESS_PROCEDURE_URI = "urn:ucf:evidence-status:assess:1.0.0"

_REASON_CODES = (
    "behavior_subject_changed",
    "check_changed",
    "current_context_unavailable",
    "environment_changed",
    "expected_output_changed",
    "input_changed",
    "inventory_adapter_changed",
    "mapping_adapter_changed",
    "mapping_binding_changed",
    "procedure_changed",
    "result_changed",
    "source_binding_changed",
    "verification_adapter_changed",
)


def _digest(fill: str) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": fill * 64,
    }


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _content_id(prefix: str, payload: dict[str, object]) -> str:
    projection = {key: value for key, value in payload.items() if key != "id"}
    return f"{prefix}.{hashlib.sha256(_canonical_bytes(projection)).hexdigest()}"


def _document_digest(payload: dict[str, object]) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
    }


def envelope_payload() -> dict[str, object]:
    context = baseline_context()
    return record_verification_evidence(
        context.result,
        **record_arguments(context),
    ).model_dump(mode="json")


def _current_coordinates() -> dict[str, object]:
    return assessment_payload()["current"]


def assessment_payload(
    *,
    status: str = "stale",
) -> dict[str, object]:
    recorded = baseline_context()
    envelope = record_verification_evidence(
        recorded.result,
        **record_arguments(recorded),
    )
    current_arguments = {}
    if status == "fresh":
        current_arguments = current_assessment_arguments(recorded)
    elif status == "stale":
        current_arguments = current_assessment_arguments(
            target_source_context()
        )
    return assess_verification_evidence(
        envelope,
        **recorded_assessment_arguments(recorded),
        **current_arguments,
    ).model_dump(mode="json")


def envelope() -> VerificationEvidenceEnvelope:
    return parse_verification_evidence_envelope_json(json.dumps(envelope_payload()))


def assessment(
    *,
    status: str = "stale",
) -> VerificationEvidenceAssessment:
    return parse_verification_evidence_assessment_json(
        json.dumps(assessment_payload(status=status))
    )


def _reidentify(prefix: str, payload: dict[str, object]) -> None:
    payload["id"] = _content_id(prefix, payload)


def test_public_contract_has_exact_version_schema_and_procedures() -> None:
    assert EVIDENCE_STATUS_VERSION == "1.0.0"
    assert VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI == (
        "urn:ucf:evidence-status:envelope:1.0.0"
    )
    assert VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI == (
        "urn:ucf:evidence-status:assessment:1.0.0"
    )
    assert envelope().procedure_uri == _RECORD_PROCEDURE_URI
    assert assessment().procedure_uri == _ASSESS_PROCEDURE_URI


def test_envelope_exposes_exact_refs_selective_projections_and_trace() -> None:
    payload = envelope().model_dump(mode="json")

    assert payload["verification_result"] == (envelope_payload()["verification_result"])
    assert payload["claim"] == envelope_payload()["claim"]
    assert payload["subject"] == envelope_payload()["subject"]
    assert tuple(payload["recorded"]) == (
        "kind",
        "behavior",
        "source",
        "mapping",
        "execution",
    )
    assert all(
        payload["recorded"][scope]["members"]
        for scope in ("behavior", "source", "mapping", "execution")
    )
    assert tuple(payload["trace"]) == (
        "kind",
        "behavior",
        "onboarding",
        "inventory",
        "mapping",
    )
    assert (
        payload["trace"]["inventory"]["subject_uri"]
        == (payload["subject"]["subject_uri"])
    )


@pytest.mark.parametrize("status", ("fresh", "stale", "indeterminate"))
def test_assessment_exposes_exact_envelope_ref_and_three_states(
    status: str,
) -> None:
    payload = assessment(status=status).model_dump(mode="json")

    assert payload["status"] == status
    assert payload["envelope"]["target_id"] == envelope_payload()["id"]
    assert payload["envelope"]["canonical_digest"] == (
        _document_digest(envelope_payload())
    )
    if status == "fresh":
        assert payload["current"] is not None
        assert payload["reasons"] == []
    elif status == "stale":
        assert payload["current"] is not None
        assert [reason["code"] for reason in payload["reasons"]] == [
            "mapping_binding_changed",
            "source_binding_changed",
        ]
    else:
        assert payload["current"] is None
        assert [reason["code"] for reason in payload["reasons"]] == [
            "current_context_unavailable"
        ]


def test_models_are_strict_closed_and_immutable() -> None:
    recorded = envelope()
    evaluated = assessment()

    assert recorded.model_config["extra"] == "forbid"
    assert recorded.model_config["frozen"] is True
    assert recorded.model_config["strict"] is True
    assert evaluated.model_config["extra"] == "forbid"
    assert evaluated.model_config["frozen"] is True
    assert evaluated.model_config["strict"] is True
    with pytest.raises(ValidationError):
        recorded.id = f"envelope.{'f' * 64}"
    with pytest.raises(ValidationError):
        evaluated.status = "fresh"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_status_version", "2.0.0"),
        (
            "schema_uri",
            "urn:ucf:evidence-status:envelope:2.0.0",
        ),
        (
            "procedure_uri",
            "urn:ucf:evidence-status:record:2.0.0",
        ),
    ],
)
def test_envelope_rejects_incompatible_wire_coordinates(
    field: str,
    value: str,
) -> None:
    payload = envelope_payload()
    payload[field] = value
    _reidentify("envelope", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_status_version", "2.0.0"),
        (
            "schema_uri",
            "urn:ucf:evidence-status:assessment:2.0.0",
        ),
        (
            "procedure_uri",
            "urn:ucf:evidence-status:assess:2.0.0",
        ),
        ("status", "verified"),
    ],
)
def test_assessment_rejects_incompatible_wire_coordinates(
    field: str,
    value: str,
) -> None:
    payload = assessment_payload()
    payload[field] = value
    _reidentify("assessment", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(json.dumps(payload))


@pytest.mark.parametrize(
    "location",
    (
        (),
        ("verification_result",),
        ("claim",),
        ("subject",),
        ("recorded", "behavior"),
        ("recorded", "behavior", "members", 0),
        ("trace",),
        ("trace", "inventory"),
    ),
)
def test_envelope_rejects_unknown_fields_at_every_boundary(
    location: tuple[str | int, ...],
) -> None:
    payload = envelope_payload()
    target: object = payload
    for coordinate in location:
        target = target[coordinate]
    assert isinstance(target, dict)
    target["transport"] = "http"
    if location[:1] == ("recorded",):
        projection = payload["recorded"][location[1]]
        projection["digest"] = _document_digest(
            {key: value for key, value in projection.items() if key != "digest"}
        )
    _reidentify("envelope", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(json.dumps(payload))


@pytest.mark.parametrize(
    "location",
    (
        (),
        ("envelope",),
        ("current",),
        ("current", "behavior"),
        ("reasons", 0),
    ),
)
def test_assessment_rejects_unknown_fields_at_every_boundary(
    location: tuple[str | int, ...],
) -> None:
    payload = assessment_payload()
    target: object = payload
    for coordinate in location:
        target = target[coordinate]
    assert isinstance(target, dict)
    target["framework"] = "spring"
    if location[:2] == ("current", "behavior"):
        projection = payload["current"]["behavior"]
        projection["digest"] = _document_digest(
            {key: value for key, value in projection.items() if key != "digest"}
        )
    _reidentify("assessment", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("scope", "mutation"),
    [
        ("behavior", "duplicate"),
        ("behavior", "noncanonical"),
        ("source", "duplicate"),
        ("source", "noncanonical"),
        ("mapping", "duplicate"),
        ("mapping", "noncanonical"),
        ("execution", "duplicate"),
        ("execution", "noncanonical"),
    ],
)
def test_envelope_rejects_duplicate_or_noncanonical_projection_members(
    scope: str,
    mutation: str,
) -> None:
    payload = envelope_payload()
    members = payload["recorded"][scope]["members"]
    if mutation == "duplicate":
        members.append(deepcopy(members[0]))
    elif len(members) == 1:
        earlier = deepcopy(members[0])
        earlier["target_kind"] = "action"
        earlier["target_id"] = "action.out-of-order"
        members.append(earlier)
    else:
        members.reverse()
    projection = payload["recorded"][scope]
    projection["digest"] = _document_digest(
        {key: value for key, value in projection.items() if key != "digest"}
    )
    _reidentify("envelope", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(json.dumps(payload))


@pytest.mark.parametrize("mutation", ("duplicate", "noncanonical"))
def test_assessment_rejects_duplicate_or_noncanonical_reasons(
    mutation: str,
) -> None:
    payload = assessment_payload()
    reasons = payload["reasons"]
    if mutation == "duplicate":
        reasons[1] = deepcopy(reasons[0])
    else:
        reasons.reverse()
    _reidentify("assessment", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (
            ("verification_result", "target_id"),
            f"mapping.{'f' * 64}",
        ),
        (
            ("claim", "target_id"),
            f"source.execution.{'f' * 64}",
        ),
        (
            ("recorded", "behavior", "members", 3, "target_id"),
            "use-case.other",
        ),
        (
            ("trace", "inventory", "subject_uri"),
            "urn:ucf:repository:other",
        ),
    ],
)
def test_envelope_rejects_broken_structural_references(
    path: tuple[str | int, ...],
    value: str,
) -> None:
    payload = envelope_payload()
    target: object = payload
    for coordinate in path[:-1]:
        target = target[coordinate]
    assert isinstance(target, dict)
    target[path[-1]] = value
    if path[:3] == ("recorded", "behavior", "members"):
        projection = payload["recorded"]["behavior"]
        projection["digest"] = _document_digest(
            {key: nested for key, nested in projection.items() if key != "digest"}
        )
    _reidentify("envelope", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(json.dumps(payload))


def test_projection_digest_must_match_exact_canonical_members() -> None:
    payload = envelope_payload()
    payload["recorded"]["source"]["digest"] = _digest("f")
    _reidentify("envelope", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("status", "current", "reasons"),
    [
        ("fresh", "keep", "stale"),
        ("stale", "keep", "empty"),
        ("stale", "none", "stale"),
        ("indeterminate", "keep", "unavailable"),
        ("indeterminate", "none", "empty"),
    ],
)
def test_assessment_rejects_ambiguous_status_shape(
    status: str,
    current: str,
    reasons: str,
) -> None:
    payload = assessment_payload(status=status)
    if current == "none":
        payload["current"] = None
    elif status == "indeterminate":
        payload["current"] = _current_coordinates()
    if reasons == "empty":
        payload["reasons"] = []
    elif reasons == "stale":
        payload["reasons"] = assessment_payload(status="stale")["reasons"]
    else:
        payload["reasons"] = assessment_payload(status="indeterminate")["reasons"]
    _reidentify("assessment", payload)

    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(json.dumps(payload))


def test_reason_taxonomy_is_closed_and_language_neutral() -> None:
    assert tuple(sorted(_REASON_CODES)) == _REASON_CODES
    assert {code.value for code in EvidenceStatusReasonCode} == set(
        _REASON_CODES
    )
    for code in _REASON_CODES:
        if code == "current_context_unavailable":
            payload = assessment_payload(status="indeterminate")
        else:
            payload = assessment_payload()
            payload["reasons"] = [
                {
                    "kind": "evidence_status_reason",
                    "code": code,
                    "recorded": _digest("1"),
                    "current": _digest("2"),
                }
            ]
        _reidentify("assessment", payload)
        parsed = parse_verification_evidence_assessment_json(json.dumps(payload))
        assert str(parsed.reasons[0].code) == code

    payload = assessment_payload()
    payload["reasons"][0]["code"] = "http_route_changed"
    _reidentify("assessment", payload)
    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(json.dumps(payload))


def test_canonicalization_revalidates_corrupted_model_copies() -> None:
    corrupted_envelope = envelope().model_copy(update={"id": f"envelope.{'f' * 64}"})
    corrupted_assessment = assessment().model_copy(
        update={"id": f"assessment.{'f' * 64}"}
    )

    with pytest.raises((ValidationError, ValueError)):
        canonical_evidence_status_json(corrupted_envelope)
    with pytest.raises((ValidationError, ValueError)):
        canonical_evidence_status_json(corrupted_assessment)


def test_canonicalization_rejects_foreign_models_and_hidden_fields() -> None:
    document = envelope()
    hidden_root = document.model_copy(update={"transport": "http"})
    hidden_nested = document.model_copy(
        update={
            "trace": document.trace.model_copy(
                update={"framework": "spring"}
            )
        }
    )

    with pytest.raises(TypeError, match="exact evidence-status"):
        canonical_evidence_status_json(baseline_context().result)
    with pytest.raises(ValueError, match="unknown field"):
        canonical_evidence_status_json(hidden_root)
    with pytest.raises(ValueError, match="unknown field"):
        canonical_evidence_status_json(hidden_nested)
