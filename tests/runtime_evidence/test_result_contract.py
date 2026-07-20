from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.models import Producer
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_CAPABILITY,
    RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEvidenceAcceptedResult,
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceRejectedResult,
    RuntimeEvidenceValidationError,
    RuntimeObservation,
    RuntimeObservationRuleRef,
    RuntimePolicyRejectionCode,
    RuntimeSanitizationSummary,
    canonical_runtime_evidence_json,
    derive_runtime_evidence_result_id,
    parse_runtime_evidence_result_json,
)

from .test_request_contract import _request


def _producer() -> Producer:
    return Producer(
        kind="producer",
        name="org.ucf.fixture-runtime-adapter",
        version="1.0.0",
    )


def _accepted() -> RuntimeEvidenceAcceptedResult:
    request = _request()
    provisional = RuntimeEvidenceAcceptedResult(
        kind="runtime_evidence_result",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri=RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
        id=f"result.{'0' * 64}",
        status="accepted",
        request=request,
        producer=_producer(),
        capability=CapabilitySelection(
            kind="capability",
            name=RUNTIME_EVIDENCE_CAPABILITY,
            version=RUNTIME_EVIDENCE_VERSION,
        ),
        procedure_uri=request.adapter_procedure_uri,
        sanitization=RuntimeSanitizationSummary(
            kind="runtime_sanitization_summary",
            selected_rule_count=1,
            forbidden_match_count=0,
            raw_retained=False,
        ),
        observations=(
            RuntimeObservation(
                kind="runtime_observation",
                rule=RuntimeObservationRuleRef(
                    kind="runtime_observation_rule_ref",
                    target_id="rule.reservation-created",
                ),
            ),
        ),
    )
    return provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )


def _rejected() -> RuntimeEvidenceRejectedResult:
    request = _request()
    provisional = RuntimeEvidenceRejectedResult(
        kind="runtime_evidence_result",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri=RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
        id=f"result.{'0' * 64}",
        status="rejected",
        request=request,
        producer=_producer(),
        capability=CapabilitySelection(
            kind="capability",
            name=RUNTIME_EVIDENCE_CAPABILITY,
            version=RUNTIME_EVIDENCE_VERSION,
        ),
        procedure_uri=request.adapter_procedure_uri,
        reason_codes=(
            RuntimePolicyRejectionCode.SELECTED_VALUE_NOT_ALLOWED,
        ),
    )
    return provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )


@pytest.mark.parametrize("result", [_accepted(), _rejected()])
def test_accepted_and_rejected_results_are_exact_canonical_documents(
    result: RuntimeEvidenceAcceptedResult | RuntimeEvidenceRejectedResult,
) -> None:
    encoded = canonical_runtime_evidence_json(result)

    assert parse_runtime_evidence_result_json(encoded) == result
    assert (
        canonical_runtime_evidence_json(
            parse_runtime_evidence_result_json(encoded)
        )
        == encoded
    )
    assert result.id == derive_runtime_evidence_result_id(result)


def test_accepted_result_names_only_policy_rules() -> None:
    payload = _accepted().model_dump(mode="json")

    assert payload["observations"] == [
        {
            "kind": "runtime_observation",
            "rule": {
                "kind": "runtime_observation_rule_ref",
                "target_id": "rule.reservation-created",
            },
        }
    ]
    serialized = json.dumps(payload["observations"], sort_keys=True)
    assert "subject" not in serialized
    assert "assertion" not in serialized
    assert "claim" not in serialized


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "version",
        "capability",
        "procedure",
        "summary",
        "duplicate_observation",
        "identity",
        "claim",
    ],
)
def test_accepted_result_rejects_every_untrusted_boundary(
    mutation: str,
) -> None:
    payload = _accepted().model_dump(mode="json")
    if mutation == "unknown":
        payload["future"] = True
    elif mutation == "version":
        payload["runtime_evidence_version"] = "2.0.0"
    elif mutation == "capability":
        payload["capability"]["name"] = "org.ucf.adapter.verification"
    elif mutation == "procedure":
        payload["procedure_uri"] = (
            "urn:ucf:fixture-adapter:another-procedure:1.0.0"
        )
    elif mutation == "summary":
        payload["sanitization"]["selected_rule_count"] = 2
    elif mutation == "duplicate_observation":
        payload["observations"].append(payload["observations"][0])
        payload["sanitization"]["selected_rule_count"] = 2
    elif mutation == "identity":
        payload["id"] = f"result.{'f' * 64}"
    else:
        payload["claims"] = []

    expected = (
        RuntimeEvidenceValidationError
        if mutation in {"summary", "duplicate_observation", "identity"}
        else ValidationError
    )
    with pytest.raises(expected) as captured:
        parse_runtime_evidence_result_json(json.dumps(payload))

    expected_codes = {
        "summary": RuntimeEvidenceErrorCode.SUMMARY_MISMATCH,
        "duplicate_observation": (
            RuntimeEvidenceErrorCode.DUPLICATE_IDENTITY
        ),
        "identity": RuntimeEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
    }
    if mutation in expected_codes:
        assert captured.value.code is expected_codes[mutation]


def test_rejected_result_has_only_closed_code_only_reasons() -> None:
    payload = _rejected().model_dump(mode="json")
    assert "observations" not in payload
    assert "sanitization" not in payload

    payload["message"] = "peer-authored prose"
    with pytest.raises(ValidationError):
        parse_runtime_evidence_result_json(json.dumps(payload))

    invalid = _rejected().model_dump(mode="json")
    invalid["reason_codes"] = ["unknown_reason"]
    with pytest.raises(ValidationError):
        parse_runtime_evidence_result_json(json.dumps(invalid))

    duplicate = _rejected().model_dump(mode="json")
    duplicate["reason_codes"] = [
        "selected_secret",
        "selected_secret",
    ]
    with pytest.raises(RuntimeEvidenceValidationError) as captured:
        parse_runtime_evidence_result_json(json.dumps(duplicate))
    assert captured.value.code is RuntimeEvidenceErrorCode.DUPLICATE_IDENTITY


def test_result_rejects_noncanonical_observation_and_reason_order() -> None:
    accepted = _accepted().model_dump(mode="json")
    accepted["observations"] = [
        {
            "kind": "runtime_observation",
            "rule": {
                "kind": "runtime_observation_rule_ref",
                "target_id": "rule.zulu",
            },
        },
        {
            "kind": "runtime_observation",
            "rule": {
                "kind": "runtime_observation_rule_ref",
                "target_id": "rule.alpha",
            },
        },
    ]
    accepted["sanitization"]["selected_rule_count"] = 2
    with pytest.raises(RuntimeEvidenceValidationError) as captured:
        parse_runtime_evidence_result_json(json.dumps(accepted))
    assert captured.value.code is (
        RuntimeEvidenceErrorCode.NON_CANONICAL_ORDER
    )

    rejected = _rejected().model_dump(mode="json")
    rejected["reason_codes"] = [
        "selected_secret",
        "selected_personal_data",
    ]
    with pytest.raises(RuntimeEvidenceValidationError) as captured:
        parse_runtime_evidence_result_json(json.dumps(rejected))
    assert captured.value.code is (
        RuntimeEvidenceErrorCode.NON_CANONICAL_ORDER
    )
