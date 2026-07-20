from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import Digest
from ucf.runtime_evidence import (
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceImportRequest,
    RuntimeEvidenceValidationError,
    canonical_runtime_evidence_digest,
    validate_runtime_evidence_request,
)

from .test_request_contract import _environment, _request

_FIXTURE = Path("tests/fixtures/ir/v1/complete.json")


def _behavior_digest(behavior) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_ir_json(behavior).encode("ascii")
        ).hexdigest(),
    )


def _bound_request() -> tuple:
    behavior = parse_ir_json(_FIXTURE.read_bytes())
    environment = _environment()
    payload = _request().model_dump(mode="json")
    behavior_digest = _behavior_digest(behavior).model_dump(mode="json")
    payload["behavior"] = {
        "kind": "behavior_document_ref",
        "document_id": behavior.document_id,
        "ir_version": behavior.ir_version,
        "canonical_digest": behavior_digest,
    }
    for rule in payload["policy"]["rules"]:
        rule["subject"]["document_id"] = behavior.document_id
        rule["subject"]["ir_version"] = behavior.ir_version
        rule["subject"]["canonical_digest"] = behavior_digest
    payload["environment"]["canonical_digest"] = (
        canonical_runtime_evidence_digest(environment).model_dump(mode="json")
    )
    request = RuntimeEvidenceImportRequest.model_validate_json(
        json.dumps(payload)
    )
    return request, behavior, environment


def test_request_context_resolves_exact_declared_observation() -> None:
    request, behavior, environment = _bound_request()

    validate_runtime_evidence_request(
        request,
        behavior=behavior,
        environment=environment,
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_location"),
    [
        (
            "behavior_digest",
            RuntimeEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "$.behavior.canonical_digest",
        ),
        (
            "environment_digest",
            RuntimeEvidenceErrorCode.ENVIRONMENT_IDENTITY_MISMATCH,
            "$.environment.canonical_digest",
        ),
        (
            "broken_subject",
            RuntimeEvidenceErrorCode.BROKEN_REFERENCE,
            "$.policy.rules[0].subject",
        ),
        (
            "assertion",
            RuntimeEvidenceErrorCode.ASSERTION_MISMATCH,
            "$.policy.rules[0].assertion",
        ),
    ],
)
def test_request_context_rejects_forged_or_misbound_coordinates(
    mutation: str,
    expected_code: RuntimeEvidenceErrorCode,
    expected_location: str,
) -> None:
    request, behavior, environment = _bound_request()
    payload = request.model_dump(mode="json")
    if mutation == "behavior_digest":
        payload["behavior"]["canonical_digest"]["value"] = "f" * 64
        payload["policy"]["rules"][0]["subject"]["canonical_digest"][
            "value"
        ] = "f" * 64
    elif mutation == "environment_digest":
        payload["environment"]["canonical_digest"]["value"] = "f" * 64
    elif mutation == "broken_subject":
        payload["policy"]["rules"][0]["subject"]["target_id"] = (
            "observation.unknown"
        )
    else:
        payload["policy"]["rules"][0]["assertion"]["value"]["value"] = (
            "reserved"
        )
    changed = RuntimeEvidenceImportRequest.model_validate_json(
        json.dumps(payload)
    )

    with pytest.raises(RuntimeEvidenceValidationError) as captured:
        validate_runtime_evidence_request(
            changed,
            behavior=behavior,
            environment=environment,
        )

    assert captured.value.code is expected_code
    assert captured.value.location == expected_location
