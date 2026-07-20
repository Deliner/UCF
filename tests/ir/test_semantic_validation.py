from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ucf.ir import (
    IRErrorCode,
    IRValidationError,
    parse_ir_json,
    validate_required_capabilities,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "v1"
COMPLETE = json.loads((FIXTURES / "complete.json").read_text())


def _parse(document):
    return parse_ir_json(json.dumps(document))


def _entity(document, kind):
    return next(entity for entity in document["entities"] if entity["kind"] == kind)


def test_entity_identities_are_globally_unique_across_kinds():
    mutated = copy.deepcopy(COMPLETE)
    _entity(mutated, "action")["id"] = _entity(mutated, "use_case")["id"]

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.DUPLICATE_IDENTITY


def test_missing_reference_target_is_rejected():
    mutated = copy.deepcopy(COMPLETE)
    _entity(mutated, "action")["effects"][0]["target_id"] = "effect.missing"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.BROKEN_REFERENCE


def test_reference_declared_kind_must_match_the_target_entity():
    mutated = copy.deepcopy(COMPLETE)
    _entity(mutated, "action")["effects"][0]["target_kind"] = "observation"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.WRONG_TARGET_KIND


def test_reference_kind_must_be_valid_for_its_field():
    mutated = copy.deepcopy(COMPLETE)
    observation = _entity(mutated, "observation")
    _entity(mutated, "action")["effects"][0] = {
        "kind": "entity_ref",
        "target_kind": "observation",
        "target_id": observation["id"],
    }

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.WRONG_TARGET_KIND


def test_duplicate_ports_are_not_silently_collapsed():
    mutated = copy.deepcopy(COMPLETE)
    action = _entity(mutated, "action")
    action["input_ports"].append(copy.deepcopy(action["input_ports"][0]))

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.DUPLICATE_PORT


def test_duplicate_set_like_references_are_rejected():
    mutated = copy.deepcopy(COMPLETE)
    action = _entity(mutated, "action")
    action["requires"].append(copy.deepcopy(action["requires"][0]))

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.DUPLICATE_REFERENCE


def test_capability_names_are_unique_even_when_entity_ids_differ():
    mutated = copy.deepcopy(COMPLETE)
    capabilities = [
        entity
        for entity in mutated["entities"]
        if entity["kind"] == "capability_requirement"
    ]
    capabilities[1]["name"] = capabilities[0]["name"]

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.DUPLICATE_CAPABILITY


def test_binding_port_reference_must_resolve_through_the_step_action():
    mutated = copy.deepcopy(COMPLETE)
    _entity(mutated, "binding")["target"]["name"] = "missing-input"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.UNKNOWN_PORT


def test_binding_target_must_be_an_input_port():
    mutated = copy.deepcopy(COMPLETE)
    binding = _entity(mutated, "binding")
    binding["target"]["direction"] = "output"
    binding["target"]["name"] = "reservation-id"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.INVALID_BINDING


def test_binding_source_and_target_value_kinds_must_match():
    mutated = copy.deepcopy(COMPLETE)
    use_case = _entity(mutated, "use_case")
    use_case["input_ports"][0]["value_kind"] = "integer"

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.INVALID_BINDING


@pytest.mark.parametrize("kind", ["effect", "invariant"])
def test_opaque_semantics_require_at_least_one_capability(kind):
    mutated = copy.deepcopy(COMPLETE)
    _entity(mutated, kind)["requires"] = []

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert captured.value.code is IRErrorCode.INVALID_STRUCTURE


def test_opaque_semantics_cannot_depend_only_on_optional_capabilities():
    mutated = copy.deepcopy(COMPLETE)
    rule_capability = next(
        entity
        for entity in mutated["entities"]
        if entity.get("name") == "org.ucf.rule.preserve"
    )
    rule_capability["required"] = False

    with pytest.raises(IRValidationError) as captured:
        _parse(mutated)

    assert (
        captured.value.code
        is IRErrorCode.MISSING_CAPABILITY_REQUIREMENT
    )


@pytest.mark.parametrize(
    "available",
    [
        {},
        {
            "org.ucf.rule.preserve": "1.0.0",
            "org.ucf.state.assign": "0.9.0",
        },
    ],
)
def test_required_capabilities_fail_when_missing_or_too_old(available):
    document = _parse(COMPLETE)

    with pytest.raises(IRValidationError) as captured:
        validate_required_capabilities(document, available)

    assert captured.value.code is IRErrorCode.UNSUPPORTED_CAPABILITY


def test_sufficient_capabilities_are_accepted_explicitly():
    document = _parse(COMPLETE)

    validate_required_capabilities(
        document,
        {
            "org.ucf.rule.preserve": "1.0.0",
            "org.ucf.state.assign": "1.2.0",
        },
    )
