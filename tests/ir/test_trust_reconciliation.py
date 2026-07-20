from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from ucf.ir import (
    IRErrorCode,
    IRValidationError,
    RecordRef,
    canonical_ir_json,
    parse_ir_json,
    parse_trust_ir_json,
    reconcile_mapping,
    validate_trust_against_behavior,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ir"
BEHAVIOR = json.loads((FIXTURE_ROOT / "v1" / "complete.json").read_text())
TRUST = json.loads(
    (FIXTURE_ROOT / "trust" / "v1" / "complete.json").read_text()
)


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


def _bound_documents(behavior_data=None, trust_data=None):
    behavior = parse_ir_json(json.dumps(behavior_data or BEHAVIOR))
    trust_payload = copy.deepcopy(trust_data or TRUST)
    digest = hashlib.sha256(canonical_ir_json(behavior).encode()).hexdigest()
    _set_all_canonical_digests(trust_payload, digest)
    trust = parse_trust_ir_json(json.dumps(trust_payload))
    return behavior, trust


def test_exact_canonical_document_binding_and_conflict_mapping_are_valid():
    behavior, trust = _bound_documents()

    validate_trust_against_behavior(trust, behavior)


def test_reconciliation_is_pure_repeatable_and_preserves_both_inputs():
    behavior, trust = _bound_documents()
    before_trust = trust.model_dump_json()
    before_behavior = behavior.model_dump_json()
    existing = next(record for record in trust.records if record.kind == "mapping")

    first = reconcile_mapping(
        trust,
        behavior,
        mapping_id="mapping.recomputed",
        declaration_id="declaration.reservation-status",
        observation_id="observed.reservation-status",
        trace=existing.trace,
    )
    second = reconcile_mapping(
        trust,
        behavior,
        mapping_id="mapping.recomputed",
        declaration_id="declaration.reservation-status",
        observation_id="observed.reservation-status",
        trace=existing.trace,
    )

    assert first == second
    assert first.disposition == "conflict"
    assert trust.model_dump_json() == before_trust
    assert behavior.model_dump_json() == before_behavior
    observed = next(
        record for record in trust.records if record.kind == "observed_fact"
    )
    assert observed.assertion.value.value == "cancelled"


def test_reconciliation_never_returns_a_mapping_for_different_behavior_slots():
    trust_data = copy.deepcopy(TRUST)
    trust_data["records"] = [
        record
        for record in trust_data["records"]
        if record["id"]
        not in {
            "mapping.reservation-status",
            "claim.reservation-status-mapped",
        }
    ]
    observed = _record(trust_data, "observed_fact")
    observed["assertion"]["target"]["path"] = ["other-status"]
    behavior, trust = _bound_documents(trust_data=trust_data)
    validate_trust_against_behavior(trust, behavior)
    trace = next(
        record
        for record in trust.records
        if record.id == "source.reconciliation"
    )
    trace_ref = RecordRef(
        kind="record_ref",
        target_kind=trace.kind,
        target_id=trace.id,
    )

    with pytest.raises(IRValidationError) as captured:
        reconcile_mapping(
            trust,
            behavior,
            mapping_id="mapping.invalid-slot",
            declaration_id="declaration.reservation-status",
            observation_id="observed.reservation-status",
            trace=trace_ref,
        )

    assert captured.value.code is IRErrorCode.MAPPING_BASIS_MISMATCH


@pytest.mark.parametrize("field", ["document_id", "canonical_digest"])
def test_subject_document_must_match_the_supplied_behavior_ir(field):
    behavior, trust = _bound_documents()
    mutated = copy.deepcopy(BEHAVIOR)
    if field == "document_id":
        mutated["document_id"] = "document.other-reservation"
    else:
        effect = next(
            entity for entity in mutated["entities"] if entity["kind"] == "effect"
        )
        effect["value"]["value"] = "changed"
    different_behavior = parse_ir_json(json.dumps(mutated))

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, different_behavior)

    assert captured.value.code is IRErrorCode.DOCUMENT_IDENTITY_MISMATCH


def test_external_behavior_entity_reference_must_resolve():
    trust_data = copy.deepcopy(TRUST)
    declaration = _record(trust_data, "declaration")
    declaration["subject"]["target_id"] = "effect.missing"
    behavior, trust = _bound_documents(trust_data=trust_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.BROKEN_REFERENCE


def test_external_behavior_entity_reference_kind_must_be_true():
    trust_data = copy.deepcopy(TRUST)
    declaration = _record(trust_data, "declaration")
    declaration["subject"]["target_kind"] = "observation"
    behavior, trust = _bound_documents(trust_data=trust_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.WRONG_TARGET_KIND


@pytest.mark.parametrize(
    "mutate",
    [
        lambda mapping, observed: observed["assertion"]["target"].update(
            {"path": ["other-status"]}
        ),
        lambda mapping, observed: mapping.update({"disposition": "match"}),
    ],
)
def test_mapping_target_and_disposition_must_match_immutable_inputs(mutate):
    trust_data = copy.deepcopy(TRUST)
    mapping = _record(trust_data, "mapping")
    observed = _record(trust_data, "observed_fact")
    mutate(mapping, observed)
    behavior, trust = _bound_documents(trust_data=trust_data)

    with pytest.raises(IRValidationError) as captured:
        validate_trust_against_behavior(trust, behavior)

    assert captured.value.code is IRErrorCode.MAPPING_BASIS_MISMATCH
