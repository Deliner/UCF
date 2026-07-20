from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.models import Digest
from ucf.ir.trust_models import BehaviorDocumentRef
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_CAPABILITY,
    RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
    RUNTIME_EVIDENCE_IMPORT_PROCEDURE_URI,
    RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEnvironment,
    RuntimeEnvironmentRef,
    RuntimeEvidenceImportRequest,
    RuntimeSamplingScope,
    RuntimeSource,
    canonical_runtime_evidence_digest,
    canonical_runtime_evidence_json,
    parse_runtime_environment_json,
    parse_runtime_evidence_request_json,
)

from .test_models import _policy


def _digest(value: str) -> Digest:
    return Digest(kind="digest", algorithm="sha-256", value=value * 64)


def _environment() -> RuntimeEnvironment:
    return RuntimeEnvironment(
        kind="runtime_environment",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri=RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
        environment_uri=(
            "urn:ucf:fixture-environment:runtime-import:1.0.0"
        ),
        revision=_digest("b"),
    )


def _request() -> RuntimeEvidenceImportRequest:
    environment = _environment()
    return RuntimeEvidenceImportRequest(
        kind="runtime_evidence_import_request",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri=RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=RUNTIME_EVIDENCE_CAPABILITY,
            version=RUNTIME_EVIDENCE_VERSION,
        ),
        behavior=BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id="document.checkout-reservation",
            ir_version="1.0.0",
            canonical_digest=_digest("a"),
        ),
        source=RuntimeSource(
            kind="runtime_source",
            source_uri="urn:ucf:runtime-recording:fixture-v1",
            source_revision=_digest("c"),
            captured_at="2026-07-19T08:30:00Z",
        ),
        environment=RuntimeEnvironmentRef(
            kind="runtime_environment_ref",
            schema_uri=RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
            schema_version=RUNTIME_EVIDENCE_VERSION,
            environment_uri=environment.environment_uri,
            revision=environment.revision,
            canonical_digest=canonical_runtime_evidence_digest(environment),
        ),
        sampling=RuntimeSamplingScope(
            kind="runtime_sampling_scope",
            procedure_uri=(
                "urn:ucf:runtime-sampling:recorded-partial:1.0.0"
            ),
            completeness="partial",
            total_known=False,
        ),
        policy=_policy(),
        procedure_uri=RUNTIME_EVIDENCE_IMPORT_PROCEDURE_URI,
        adapter_procedure_uri=(
            "urn:ucf:fixture-adapter:runtime-evidence:1.0.0"
        ),
    )


def test_environment_and_request_round_trip_with_exact_coordinates() -> None:
    environment = _environment()
    request = _request()

    assert (
        parse_runtime_environment_json(
            canonical_runtime_evidence_json(environment)
        )
        == environment
    )
    assert (
        parse_runtime_evidence_request_json(
            canonical_runtime_evidence_json(request)
        )
        == request
    )
    assert request.environment.canonical_digest == (
        canonical_runtime_evidence_digest(environment)
    )
    assert request.sampling.completeness == "partial"
    assert request.sampling.total_known is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("capability", "name"), "org.ucf.adapter.verification"),
        (("capability", "version"), "2.0.0"),
        (("sampling", "completeness"), "complete"),
        (("sampling", "total_known"), True),
        (("procedure_uri",), "urn:ucf:runtime-evidence:import:2.0.0"),
        (
            ("adapter_procedure_uri",),
            "https://user@example.test/procedure/1.0.0",
        ),
        (("source", "source_uri"), "file:///tmp/recording.json"),
        (
            ("source", "source_uri"),
            "https://user@example.test/recording",
        ),
    ],
)
def test_request_rejects_unsupported_or_unsafe_coordinates(
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = _request().model_dump(mode="json")
    target = payload
    for coordinate in path[:-1]:
        target = target[coordinate]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        parse_runtime_evidence_request_json(json.dumps(payload))


def test_request_rejects_unknown_fields_and_policy_behavior_mismatch() -> None:
    payload = _request().model_dump(mode="json")
    payload["future"] = True
    with pytest.raises(ValidationError):
        parse_runtime_evidence_request_json(json.dumps(payload))

    mismatched = _request().model_dump(mode="json")
    mismatched["policy"]["rules"][0]["subject"]["canonical_digest"][
        "value"
    ] = "f" * 64
    with pytest.raises(ValueError, match="behavior"):
        parse_runtime_evidence_request_json(json.dumps(mismatched))

    encoded = canonical_runtime_evidence_json(_environment()).decode("utf-8")
    duplicate = encoded.replace(
        '"kind":"runtime_environment"',
        '"kind":"runtime_environment","kind":"runtime_environment"',
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_runtime_environment_json(duplicate)
