from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    ExecutionVerificationResult,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    canonical_implementation_evidence_json,
    derive_execution_verification_result_id,
    parse_execution_verification_result_json,
)
from ucf.ir.models import Producer

from .test_verification_request_contract import _verification_request


def _verification_result(
    outcome: str = "passed",
) -> ExecutionVerificationResult:
    request = _verification_request()
    provisional = ExecutionVerificationResult(
        kind="execution_verification_result",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
        id=f"result.{'0' * 64}",
        status="completed",
        request=request,
        outcome=outcome,
        executed_at="2026-07-19T15:00:00Z",
        producer=Producer(
            kind="producer",
            name="org.ucf.fixture-adapter",
            version="1.0.0",
        ),
        capability=CapabilitySelection(
            kind="capability",
            name=EXECUTION_VERIFICATION_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        procedure_uri=request.adapter_procedure_uri,
    )
    return provisional.model_copy(
        update={"id": derive_execution_verification_result_id(provisional)}
    )


@pytest.mark.parametrize("outcome", ["passed", "failed", "error"])
def test_verification_result_is_content_identified_closed_and_canonical(
    outcome: str,
) -> None:
    result = _verification_result(outcome)
    encoded = canonical_implementation_evidence_json(result)

    assert parse_execution_verification_result_json(encoded) == result
    assert (
        canonical_implementation_evidence_json(
            parse_execution_verification_result_json(encoded)
        )
        == encoded
    )
    assert result.id == derive_execution_verification_result_id(result)
    payload = result.model_dump(mode="json")
    for forbidden in (
        "body",
        "headers",
        "message",
        "stderr",
        "stdout",
        "duration",
        "stack",
    ):
        assert forbidden not in payload


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "version",
        "schema",
        "status",
        "outcome",
        "timestamp",
        "capability",
        "procedure",
        "identity",
    ],
)
def test_verification_result_rejects_every_untrusted_boundary(
    mutation: str,
) -> None:
    payload = _verification_result().model_dump(mode="json")
    if mutation == "unknown":
        payload["stdout"] = "sensitive"
    elif mutation == "version":
        payload["implementation_evidence_version"] = "2.0.0"
    elif mutation == "schema":
        payload["schema_uri"] = (
            "urn:ucf:adapter:execution-verification-result:2.0.0"
        )
    elif mutation == "status":
        payload["status"] = "partial"
    elif mutation == "outcome":
        payload["outcome"] = "unknown"
    elif mutation == "timestamp":
        payload["executed_at"] = "2026-07-19T15:00:00.123Z"
    elif mutation == "capability":
        payload["capability"]["name"] = "org.ucf.adapter.mapping"
    elif mutation == "procedure":
        payload["procedure_uri"] = (
            "urn:ucf:fixture-adapter:another-check:1.0.0"
        )
    else:
        payload["id"] = f"result.{'f' * 64}"

    expected = (
        ImplementationEvidenceValidationError
        if mutation == "identity"
        else ValidationError
    )
    with pytest.raises(expected) as captured:
        parse_execution_verification_result_json(json.dumps(payload))
    if mutation == "identity":
        assert captured.value.code is (
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH
        )
