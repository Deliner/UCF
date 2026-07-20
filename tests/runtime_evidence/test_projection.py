from __future__ import annotations

import pytest

from ucf.ir import (
    canonical_trust_ir_json,
    parse_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import Digest
from ucf.ir.trust_models import ObservedFact, SourceRecord
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceValidationError,
    RuntimeObservation,
    RuntimeObservationRuleRef,
    canonical_runtime_evidence_digest,
    derive_runtime_evidence_result_id,
    project_runtime_evidence_to_trust,
)

from .test_result_validation import _bound_result


def test_accepted_result_projects_only_exact_observed_facts() -> None:
    result, _, behavior, environment = _bound_result()

    trust = project_runtime_evidence_to_trust(
        result,
        behavior=behavior,
        environment=environment,
    )
    encoded = canonical_trust_ir_json(trust)
    reparsed = parse_trust_ir_json(encoded)
    validate_trust_against_behavior(reparsed, behavior)

    assert len(reparsed.records) == 2
    assert {type(record) for record in reparsed.records} == {
        SourceRecord,
        ObservedFact,
    }
    source = next(
        record
        for record in reparsed.records
        if isinstance(record, SourceRecord)
    )
    fact = next(
        record
        for record in reparsed.records
        if isinstance(record, ObservedFact)
    )
    assert source.source_uri == RUNTIME_EVIDENCE_RESULT_SCHEMA_URI
    assert source.source_revision == canonical_runtime_evidence_digest(result)
    assert source.producer == result.producer
    assert source.captured_at == result.request.source.captured_at
    assert fact.subject.target_id == "observation.reservation-created"
    assert fact.assertion.target.subject == "reservation"
    assert fact.assertion.target.path == ("status",)
    assert fact.assertion.value.value == "created"
    assert fact.trace.target_id == source.id

    serialized = encoded.lower()
    for forbidden in (
        '"claim"',
        '"declaration"',
        '"mapping"',
        '"behavior_candidate"',
        '"verification_evidence"',
        '"sampling"',
        '"environment"',
        '"policy"',
    ):
        assert forbidden not in serialized


def test_every_result_coordinate_changes_projection_identity() -> None:
    result, _, behavior, environment = _bound_result()
    original = project_runtime_evidence_to_trust(
        result,
        behavior=behavior,
        environment=environment,
    )
    changed_source = result.request.source.model_copy(
        update={
            "source_revision": Digest(
                kind="digest",
                algorithm="sha-256",
                value="f" * 64,
            )
        }
    )
    changed_request = result.request.model_copy(
        update={"source": changed_source}
    )
    provisional = result.model_copy(
        update={
            "id": f"result.{'0' * 64}",
            "request": changed_request,
        }
    )
    changed = provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )

    projected = project_runtime_evidence_to_trust(
        changed,
        behavior=behavior,
        environment=environment,
    )

    assert projected.document_id != original.document_id
    assert {record.id for record in projected.records}.isdisjoint(
        record.id for record in original.records
    )


def test_rejected_result_cannot_be_projected() -> None:
    result, _, behavior, environment = _bound_result(rejected=True)

    try:
        project_runtime_evidence_to_trust(
            result,
            behavior=behavior,
            environment=environment,
        )
    except RuntimeEvidenceValidationError as error:
        assert error.code is RuntimeEvidenceErrorCode.RESULT_STATUS_MISMATCH
    else:
        raise AssertionError("rejected runtime evidence was projected")


def test_projection_rejects_unknown_policy_rule_ref() -> None:
    result, _, behavior, environment = _bound_result()
    changed_observation = RuntimeObservation(
        kind="runtime_observation",
        rule=RuntimeObservationRuleRef(
            kind="runtime_observation_rule_ref",
            target_id="rule.unknown",
        ),
    )
    provisional = result.model_copy(
        update={
            "id": f"result.{'0' * 64}",
            "observations": (changed_observation,),
        }
    )
    changed = provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )

    with pytest.raises(RuntimeEvidenceValidationError) as captured:
        project_runtime_evidence_to_trust(
            changed,
            behavior=behavior,
            environment=environment,
        )

    assert captured.value.code is RuntimeEvidenceErrorCode.BROKEN_REFERENCE
