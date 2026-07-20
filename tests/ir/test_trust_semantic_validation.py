from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ucf.ir import IRErrorCode, IRValidationError, parse_trust_ir_json

FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "trust" / "v1"
)
COMPLETE = json.loads((FIXTURES / "complete.json").read_text(encoding="utf-8"))


def _parse(document):
    return parse_trust_ir_json(json.dumps(document))


def _record(document, kind, *, record_id=None):
    return next(
        record
        for record in document["records"]
        if record["kind"] == kind
        and (record_id is None or record["id"] == record_id)
    )


def test_trust_record_identities_are_globally_unique_across_kinds():
    mutated = copy.deepcopy(COMPLETE)
    _record(mutated, "declaration")["id"] = "source.declaration"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.DUPLICATE_IDENTITY


def test_missing_internal_record_reference_is_rejected():
    mutated = copy.deepcopy(COMPLETE)
    _record(mutated, "mapping")["observation"]["target_id"] = "observed.missing"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.BROKEN_REFERENCE


def test_internal_record_reference_kind_must_match_resolved_record():
    mutated = copy.deepcopy(COMPLETE)
    declaration = _record(mutated, "mapping")["declaration"]
    declaration["target_kind"] = "observed_fact"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.WRONG_TARGET_KIND


def test_candidate_subject_references_are_set_like_and_typed():
    mutated = copy.deepcopy(COMPLETE)
    candidate = _record(mutated, "behavior_candidate")
    candidate["subjects"][1] = copy.deepcopy(candidate["subjects"][0])

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.DUPLICATE_REFERENCE


def test_every_derived_record_trace_must_resolve_to_a_source_record():
    mutated = copy.deepcopy(COMPLETE)
    trace = _record(mutated, "mapping")["trace"]
    trace["target_kind"] = "declaration"
    trace["target_id"] = "declaration.reservation-status"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.WRONG_TARGET_KIND


def test_claim_level_requires_its_exact_basis_category():
    mutated = copy.deepcopy(COMPLETE)
    observed_claim = _record(
        mutated,
        "claim",
        record_id="claim.reservation-status-observed",
    )
    observed_claim["basis"] = {
        "kind": "declared_claim_basis",
        "declaration": {
            "kind": "record_ref",
            "target_kind": "declaration",
            "target_id": "declaration.reservation-status",
        },
    }

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.MISSING_CLAIM_BASIS


def test_candidate_cannot_be_used_as_tested_evidence_even_at_confidence_one():
    mutated = copy.deepcopy(COMPLETE)
    candidate = _record(mutated, "behavior_candidate")
    candidate["confidence"]["value"] = "1"
    tested_claim = _record(
        mutated,
        "claim",
        record_id="claim.reservation-present-tested",
    )
    tested_claim["basis"]["evidence"] = {
        "kind": "record_ref",
        "target_kind": "behavior_candidate",
        "target_id": candidate["id"],
    }

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.CANDIDATE_IS_NOT_EVIDENCE


def test_circular_claim_basis_is_rejected_before_evidence_evaluation():
    mutated = copy.deepcopy(COMPLETE)
    tested_claim = _record(
        mutated,
        "claim",
        record_id="claim.reservation-present-tested",
    )
    tested_claim["basis"]["evidence"] = {
        "kind": "record_ref",
        "target_kind": "claim",
        "target_id": tested_claim["id"],
    }

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.CIRCULAR_CLAIM_BASIS
