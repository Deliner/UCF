from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from ucf.ir import (
    CURRENT_TRUST_IR_VERSION,
    ClaimLevel,
    IRErrorCode,
    IRValidationError,
    TrustRecordKind,
    canonical_trust_ir_json,
    parse_trust_ir_json,
)

FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "trust" / "v1"
)
COMPLETE = json.loads((FIXTURES / "complete.json").read_text(encoding="utf-8"))


def _record(document, kind: TrustRecordKind):
    return next(record for record in document.records if record.kind is kind)


def test_complete_fixture_retains_distinct_immutable_trust_categories():
    document = parse_trust_ir_json((FIXTURES / "complete.json").read_bytes())

    assert CURRENT_TRUST_IR_VERSION == "1.0.0"
    assert {record.kind for record in document.records} == set(TrustRecordKind)
    declaration = _record(document, TrustRecordKind.DECLARATION)
    observed = _record(document, TrustRecordKind.OBSERVED_FACT)
    mapping = _record(document, TrustRecordKind.MAPPING)
    candidate = _record(document, TrustRecordKind.BEHAVIOR_CANDIDATE)
    claims = [
        record
        for record in document.records
        if record.kind is TrustRecordKind.CLAIM
    ]

    assert declaration.id == "declaration.reservation-status"
    assert observed.assertion.value.value == "cancelled"
    assert mapping.disposition == "conflict"
    assert candidate.confidence.value == "0.62"
    assert {claim.level for claim in claims} == {
        ClaimLevel.OBSERVED,
        ClaimLevel.DECLARED,
        ClaimLevel.MAPPED,
        ClaimLevel.TESTED,
    }
    with pytest.raises(ValidationError):
        observed.id = "observed.rewritten"


def test_trust_canonical_round_trip_is_deterministic_without_erasing_conflict():
    reordered = copy.deepcopy(COMPLETE)
    reordered["records"].reverse()

    first = canonical_trust_ir_json(parse_trust_ir_json(json.dumps(reordered)))
    second = canonical_trust_ir_json(parse_trust_ir_json(first))

    assert first == second
    assert first.endswith("\n")
    assert "\n" not in first[:-1]
    decoded = json.loads(first)
    identities = [(record["kind"], record["id"]) for record in decoded["records"]]
    assert identities == sorted(identities)
    assert next(
        record
        for record in decoded["records"]
        if record["kind"] == "observed_fact"
    )["assertion"]["value"]["value"] == "cancelled"
    assert next(
        record for record in decoded["records"] if record["kind"] == "mapping"
    )["disposition"] == "conflict"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda value: value.update({"unexpected": True}),
            IRErrorCode.UNKNOWN_FIELD,
        ),
        (
            lambda value: value.update({"trust_ir_version": "1.1.0"}),
            IRErrorCode.UNSUPPORTED_VERSION,
        ),
        (
            lambda value: next(
                record
                for record in value["records"]
                if record["kind"] == "behavior_candidate"
            )["confidence"].update({"value": "0.620"}),
            IRErrorCode.INVALID_VALUE,
        ),
    ],
)
def test_trust_contract_rejects_unknown_fields_versions_and_noncanonical_confidence(
    mutate,
    expected_code,
):
    mutated = copy.deepcopy(COMPLETE)
    mutate(mutated)

    with pytest.raises(IRValidationError) as captured:
        parse_trust_ir_json(json.dumps(mutated))

    assert captured.value.code is expected_code


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (
            (FIXTURES / "complete.json")
            .read_text(encoding="utf-8")
            .replace(
                '"kind": "trust_ir",',
                '"kind": "trust_ir", "kind": "trust_ir",',
                1,
            ),
            IRErrorCode.DUPLICATE_JSON_MEMBER,
        ),
        (
            (FIXTURES / "complete.json")
            .read_text(encoding="utf-8")
            .replace('"value": "0.62"', '"value": 0.62', 1),
            IRErrorCode.INVALID_VALUE,
        ),
    ],
)
def test_trust_parser_reuses_the_strict_raw_json_boundary(payload, expected_code):
    with pytest.raises(IRValidationError) as captured:
        parse_trust_ir_json(payload)

    assert captured.value.code is expected_code


@pytest.mark.parametrize(
    "value",
    ["2023-02-29T00:00:00Z", "0000-01-01T00:00:00Z"],
)
def test_source_record_timestamps_reject_invalid_calendar_dates(value):
    mutated = copy.deepcopy(COMPLETE)
    source = next(
        record for record in mutated["records"] if record["kind"] == "source_record"
    )
    source["captured_at"] = value

    with pytest.raises(IRValidationError) as captured:
        parse_trust_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.INVALID_VALUE


def test_confidence_length_is_bounded_even_when_its_spelling_is_canonical():
    mutated = copy.deepcopy(COMPLETE)
    candidate = next(
        record
        for record in mutated["records"]
        if record["kind"] == "behavior_candidate"
    )
    candidate["confidence"]["value"] = "0." + ("1" * 64)

    with pytest.raises(IRValidationError) as captured:
        parse_trust_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.INVALID_VALUE


def test_trust_canonical_bytes_round_trip_through_node_json():
    mutated = copy.deepcopy(COMPLETE)
    source = next(
        record for record in mutated["records"] if record["kind"] == "source_record"
    )
    source["source_uri"] = "urn:ucf:source:réview-😀"
    canonical = canonical_trust_ir_json(
        parse_trust_ir_json(json.dumps(mutated, ensure_ascii=False))
    )
    script = """
const fs = require("fs");
const order = value => {
  if (Array.isArray(value)) return value.map(order);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value).sort().map(key => [key, order(value[key])])
    );
  }
  return value;
};
const parsed = JSON.parse(fs.readFileSync(0, "utf8"));
const ascii = JSON.stringify(order(parsed)).replace(
  /[\\u007f-\\uffff]/g,
  character => "\\\\u" + character.charCodeAt(0).toString(16).padStart(4, "0")
);
process.stdout.write(ascii + "\\n");
"""

    result = subprocess.run(
        ["node", "-e", script],
        input=canonical,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == canonical
