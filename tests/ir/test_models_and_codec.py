from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from ucf.ir import (
    EntityKind,
    IRErrorCode,
    IRValidationError,
    canonical_ir_json,
    parse_ir_json,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "v1"
COMPLETE = json.loads((FIXTURES / "complete.json").read_text())


def _entity(document, kind: EntityKind):
    return next(entity for entity in document.entities if entity.kind is kind)


def test_complete_golden_fixture_contains_every_minimum_ir_concept():
    document = parse_ir_json((FIXTURES / "complete.json").read_bytes())

    assert {entity.kind for entity in document.entities} == set(EntityKind)
    assert _entity(document, EntityKind.ACTION).input_ports[0].name == "item-id"
    assert _entity(document, EntityKind.USE_CASE).steps[0].target_id == (
        "step.reserve-item"
    )
    assert _entity(document, EntityKind.BINDING).source.kind == "port_ref"
    assert _entity(document, EntityKind.EFFECT).operation == "assign"
    assert _entity(document, EntityKind.OBSERVATION).value.kind == "string"
    assert _entity(document, EntityKind.INVARIANT).condition.kind == "declared_rule"
    assert _entity(document, EntityKind.PROVENANCE).producer.version == "1.0.0"
    assert _entity(document, EntityKind.VERIFICATION_EVIDENCE).outcome == "passed"
    assert (
        _entity(document, EntityKind.CAPABILITY_REQUIREMENT).name
        == "org.ucf.state.assign"
    )


def test_canonical_round_trip_is_byte_deterministic_and_field_ordered():
    original = copy.deepcopy(COMPLETE)
    original["entities"].reverse()
    original["roots"].reverse()

    first = canonical_ir_json(parse_ir_json(json.dumps(original)))
    second = canonical_ir_json(parse_ir_json(first))

    assert first == second
    assert first.endswith("\n")
    assert not first.endswith("\n\n")
    assert "\n" not in first[:-1]
    decoded = json.loads(first)
    entity_keys = [
        (entity["kind"], entity["id"]) for entity in decoded["entities"]
    ]
    assert entity_keys == sorted(entity_keys)
    assert list(decoded) == sorted(decoded)


def test_canonical_output_ascii_escapes_non_ascii_user_text():
    mutated = copy.deepcopy(COMPLETE)
    invariant = next(
        entity for entity in mutated["entities"] if entity["kind"] == "invariant"
    )
    invariant["condition"]["statement"] = "réservation présente"

    encoded = canonical_ir_json(parse_ir_json(json.dumps(mutated)))

    assert "réservation" not in encoded
    assert "r\\u00e9servation pr\\u00e9sente" in encoded


def test_canonical_output_preserves_step_order_but_sorts_set_like_refs():
    mutated = copy.deepcopy(COMPLETE)
    use_case = next(
        entity for entity in mutated["entities"] if entity["kind"] == "use_case"
    )
    original_step = next(
        entity for entity in mutated["entities"] if entity["kind"] == "step"
    )
    later_step = copy.deepcopy(original_step)
    later_step["id"] = "step.reserve-item-later"
    later_step["bindings"] = []
    mutated["entities"].append(later_step)
    use_case["steps"].insert(
        0,
        {
            "kind": "entity_ref",
            "target_kind": "step",
            "target_id": later_step["id"],
        },
    )
    use_case["requires"].append(
        {
            "kind": "entity_ref",
            "target_kind": "capability_requirement",
            "target_id": "capability.state-assignment",
        }
    )

    decoded = json.loads(canonical_ir_json(parse_ir_json(json.dumps(mutated))))
    canonical_use_case = next(
        entity for entity in decoded["entities"] if entity["kind"] == "use_case"
    )

    assert [ref["target_id"] for ref in canonical_use_case["steps"]] == [
        "step.reserve-item-later",
        "step.reserve-item",
    ]
    assert [ref["target_id"] for ref in canonical_use_case["requires"]] == [
        "capability.rule-preservation",
        "capability.state-assignment",
    ]


def test_closed_recursive_values_have_one_canonical_representation():
    mutated = copy.deepcopy(COMPLETE)
    effect = next(
        entity for entity in mutated["entities"] if entity["kind"] == "effect"
    )
    effect["value"] = {
        "kind": "record",
        "entries": [
            {
                "kind": "record_entry",
                "name": "z-last",
                "value": {
                    "kind": "list",
                    "items": [
                        {"kind": "null"},
                        {"kind": "boolean", "value": True},
                        {"kind": "integer", "value": 42},
                        {"kind": "decimal", "value": "12.34"},
                    ],
                },
            },
            {
                "kind": "record_entry",
                "name": "a-first",
                "value": {
                    "kind": "timestamp",
                    "value": "2026-07-19T00:00:00Z",
                },
            },
        ],
    }

    encoded = canonical_ir_json(parse_ir_json(json.dumps(mutated)))
    decoded = json.loads(encoded)
    canonical_effect = next(
        entity for entity in decoded["entities"] if entity["kind"] == "effect"
    )

    assert [
        entry["name"] for entry in canonical_effect["value"]["entries"]
    ] == ["a-first", "z-last"]


def test_rfc3339_year_with_leading_zeroes_is_platform_independent():
    mutated = copy.deepcopy(COMPLETE)
    effect = next(
        entity for entity in mutated["entities"] if entity["kind"] == "effect"
    )
    effect["value"] = {
        "kind": "timestamp",
        "value": "0001-01-01T00:00:00Z",
    }

    document = parse_ir_json(json.dumps(mutated))

    assert _entity(document, EntityKind.EFFECT).value.value == (
        "0001-01-01T00:00:00Z"
    )


@pytest.mark.parametrize(
    "value",
    ["0000-01-01T00:00:00Z", "2023-02-29T00:00:00Z"],
)
def test_timestamp_values_reject_invalid_calendar_dates(value):
    mutated = copy.deepcopy(COMPLETE)
    effect = next(
        entity for entity in mutated["entities"] if entity["kind"] == "effect"
    )
    effect["value"] = {"kind": "timestamp", "value": value}

    with pytest.raises(IRValidationError) as captured:
        parse_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.INVALID_VALUE


@pytest.mark.parametrize("value", ["01", "-0", "1.0", "1.230", "1e3", "+1"])
def test_decimal_values_reject_noncanonical_spellings(value):
    mutated = copy.deepcopy(COMPLETE)
    effect = next(
        entity for entity in mutated["entities"] if entity["kind"] == "effect"
    )
    effect["value"] = {"kind": "decimal", "value": value}

    with pytest.raises(IRValidationError) as captured:
        parse_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.INVALID_VALUE


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ((), {"unknown": True}),
        (("entities", 0), {"unknown": True}),
        (("entities", 0, "input_ports", 0), {"unknown": True}),
    ],
)
def test_unknown_fields_fail_at_every_modeled_layer(path, value):
    mutated = copy.deepcopy(COMPLETE)
    target = mutated
    for segment in path:
        target = target[segment]
    target.update(value)

    with pytest.raises(IRValidationError) as captured:
        parse_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.UNKNOWN_FIELD


def test_strict_model_types_do_not_coerce_strings_to_booleans():
    mutated = copy.deepcopy(COMPLETE)
    action = next(
        entity for entity in mutated["entities"] if entity["kind"] == "action"
    )
    action["input_ports"][0]["required"] = "true"

    with pytest.raises(IRValidationError) as captured:
        parse_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize("name", ["assign", "Org.ucf.assign", "org..assign"])
def test_capability_names_are_lowercase_qualified_names(name):
    mutated = copy.deepcopy(COMPLETE)
    capability = next(
        entity
        for entity in mutated["entities"]
        if entity["kind"] == "capability_requirement"
    )
    capability["name"] = name

    with pytest.raises(IRValidationError) as captured:
        parse_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.INVALID_STRUCTURE


def test_canonical_golden_bytes_round_trip_through_node_json():
    mutated = copy.deepcopy(COMPLETE)
    invariant = next(
        entity for entity in mutated["entities"] if entity["kind"] == "invariant"
    )
    invariant["condition"]["statement"] = "réservation 😀"
    canonical = canonical_ir_json(
        parse_ir_json(json.dumps(mutated, ensure_ascii=False))
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
