from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from ucf.ir import (
    ClaimLevel,
    IRErrorCode,
    IRValidationError,
    canonical_ir_json,
    parse_ir_json,
    parse_trust_ir_json,
    supported_claim_levels,
    validate_trust_against_behavior,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ir"
BEHAVIOR = json.loads((FIXTURE_ROOT / "v1" / "complete.json").read_text())
TRUST = json.loads(
    (FIXTURE_ROOT / "trust" / "v1" / "complete.json").read_text()
)


def _entity(document, kind):
    return next(entity for entity in document["entities"] if entity["kind"] == kind)


def _record(document, kind, *, record_id=None):
    return next(
        record
        for record in document["records"]
        if record["kind"] == kind
        and (record_id is None or record["id"] == record_id)
    )


def _set_all_canonical_digests(value, digest):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "canonical_digest":
                nested["value"] = digest
            else:
                _set_all_canonical_digests(nested, digest)
    elif isinstance(value, list):
        for nested in value:
            _set_all_canonical_digests(nested, digest)


def _bound_documents(*, behavior_data=None, trust_data=None):
    behavior = parse_ir_json(json.dumps(behavior_data or BEHAVIOR))
    trust_payload = copy.deepcopy(trust_data or TRUST)
    digest = hashlib.sha256(canonical_ir_json(behavior).encode()).hexdigest()
    _set_all_canonical_digests(trust_payload, digest)
    trust = parse_trust_ir_json(json.dumps(trust_payload))
    return behavior, trust


def test_claim_levels_are_independent_supported_predicates_not_a_maximum():
    behavior, trust = _bound_documents()

    assert supported_claim_levels(trust, behavior) == frozenset(
        {
            ClaimLevel.OBSERVED,
            ClaimLevel.DECLARED,
            ClaimLevel.MAPPED,
            ClaimLevel.TESTED,
        }
    )
    assert ClaimLevel.VERIFIED not in supported_claim_levels(trust, behavior)


@pytest.mark.parametrize(
    ("claim_id", "target_kind", "target_id"),
    [
        (
            "claim.reservation-status-observed",
            "action",
            "action.reserve-item",
        ),
        (
            "claim.reservation-status-declared",
            "action",
            "action.reserve-item",
        ),
        (
            "claim.reservation-status-mapped",
            "invariant",
            "invariant.reservation-present",
        ),
    ],
)
def test_fact_and_mapping_claim_subjects_must_match_their_exact_basis(
    claim_id,
    target_kind,
    target_id,
):
    trust_data = copy.deepcopy(TRUST)
    claim = _record(trust_data, "claim", record_id=claim_id)
    claim["subject"]["target_kind"] = target_kind
    claim["subject"]["target_id"] = target_id
    behavior, trust = _bound_documents(trust_data=trust_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.CLAIM_BASIS_MISMATCH


@pytest.mark.parametrize("outcome", ["failed", "error"])
def test_nonpassing_evidence_never_yields_tested(outcome):
    behavior_data = copy.deepcopy(BEHAVIOR)
    _entity(behavior_data, "verification_evidence")["outcome"] = outcome
    behavior, trust = _bound_documents(behavior_data=behavior_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.EVIDENCE_NOT_PASSED


def test_stale_evidence_never_yields_tested():
    behavior_data = copy.deepcopy(BEHAVIOR)
    evidence = _entity(behavior_data, "verification_evidence")
    evidence["source_revision"]["value"] = "9" * 64
    behavior, trust = _bound_documents(behavior_data=behavior_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.STALE_EVIDENCE


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        (
            "subject",
            lambda document: _entity(document, "verification_evidence").update(
                {
                    "subjects": [
                        {
                            "kind": "entity_ref",
                            "target_kind": "effect",
                            "target_id": "effect.reservation-created",
                        }
                    ]
                }
            ),
        ),
        (
            "check",
            lambda document: _entity(document, "verification_evidence")[
                "check"
            ].update({"id": "check.other"}),
        ),
        (
            "environment",
            lambda document: _entity(document, "verification_evidence")[
                "environment"
            ].update({"value": "9" * 64}),
        ),
        (
            "producer",
            lambda document: _entity(document, "provenance")["producer"].update(
                {"name": "org.ucf.other"}
            ),
        ),
    ],
)
def test_mismatched_evidence_coordinate_never_yields_tested(field, mutate):
    behavior_data = copy.deepcopy(BEHAVIOR)
    mutate(behavior_data)
    behavior, trust = _bound_documents(behavior_data=behavior_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.CLAIM_BASIS_MISMATCH
    assert field in captured.value.location


def test_verified_is_explicitly_unavailable_even_with_a_passed_test_nearby():
    trust_data = copy.deepcopy(TRUST)
    claim = _record(
        trust_data,
        "claim",
        record_id="claim.reservation-present-tested",
    )
    claim["level"] = "verified"
    claim["basis"] = {"kind": "verified_claim_basis"}
    behavior, trust = _bound_documents(trust_data=trust_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.VERIFIED_UNAVAILABLE


def test_every_accepted_claim_traces_to_an_immutable_source_and_tool_version():
    behavior, trust = _bound_documents()
    validate_trust_against_behavior(trust, behavior)
    records = {record.id: record for record in trust.records}

    for claim in (record for record in trust.records if record.kind == "claim"):
        source = records[claim.trace.target_id]
        assert source.kind == "source_record"
        assert source.source_revision.value
        assert source.producer.name == "org.ucf.fixture.claim-evaluator"
        assert source.producer.version == "1.0.0"
