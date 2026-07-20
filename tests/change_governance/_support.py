from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.change_lifecycle._fixture_factory import proposal
from ucf.change_lifecycle import (
    BehaviorDelta,
    ChangeProposal,
    derive_behavior_delta,
)
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import BehaviorIR

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_COMPLETE_BEHAVIOR = (
    _REPOSITORY_ROOT / "tests" / "fixtures" / "ir" / "v1" / "complete.json"
)


def base_behavior() -> BehaviorIR:
    return parse_ir_json(_COMPLETE_BEHAVIOR.read_bytes())


def additive_root_final(base: BehaviorIR) -> BehaviorIR:
    payload = json.loads(canonical_ir_json(base))
    provenance = next(
        entity["provenance"]
        for entity in payload["entities"]
        if entity["kind"] == "use_case"
    )
    payload["entities"].append(
        {
            "kind": "use_case",
            "id": "use-case.health-check",
            "input_ports": [],
            "output_ports": [],
            "steps": [],
            "invariants": [],
            "requires": [],
            "provenance": provenance,
        }
    )
    payload["roots"].append(
        {
            "kind": "entity_ref",
            "target_kind": "use_case",
            "target_id": "use-case.health-check",
        }
    )
    return parse_ir_json(json.dumps(payload))


def root_loss_final(base: BehaviorIR) -> BehaviorIR:
    payload = json.loads(canonical_ir_json(base))
    payload["roots"] = [
        {
            "kind": "entity_ref",
            "target_kind": "use_case",
            "target_id": "use-case.health-check",
        }
    ]
    provenance = next(
        entity["provenance"]
        for entity in payload["entities"]
        if entity["kind"] == "use_case"
    )
    payload["entities"].append(
        {
            "kind": "use_case",
            "id": "use-case.health-check",
            "input_ports": [],
            "output_ports": [],
            "steps": [],
            "invariants": [],
            "requires": [],
            "provenance": provenance,
        }
    )
    return parse_ir_json(json.dumps(payload))


def output_requiredness_final(base: BehaviorIR) -> BehaviorIR:
    payload = json.loads(canonical_ir_json(base))
    use_case = next(
        entity for entity in payload["entities"] if entity["kind"] == "use_case"
    )
    use_case["output_ports"][0]["required"] = False
    return parse_ir_json(json.dumps(payload))


def input_requiredness_final(base: BehaviorIR) -> BehaviorIR:
    payload = json.loads(canonical_ir_json(base))
    use_case = next(
        entity for entity in payload["entities"] if entity["kind"] == "use_case"
    )
    use_case["input_ports"][0]["required"] = False
    return parse_ir_json(json.dumps(payload))


def capability_addition_final(
    base: BehaviorIR,
    *,
    required: bool,
) -> BehaviorIR:
    payload = json.loads(canonical_ir_json(base))
    provenance = next(
        entity["provenance"]
        for entity in payload["entities"]
        if entity["kind"] == "capability_requirement"
    )
    payload["entities"].append(
        {
            "kind": "capability_requirement",
            "id": "capability.unreferenced",
            "name": "fixture.unreferenced",
            "minimum_version": "1.0.0",
            "required": required,
            "provenance": provenance,
        }
    )
    return parse_ir_json(json.dumps(payload))


def mutate_behavior(
    base: BehaviorIR,
    mutation: Callable[[dict[str, Any]], None],
) -> BehaviorIR:
    payload = json.loads(canonical_ir_json(base))
    mutation(payload)
    return parse_ir_json(json.dumps(payload))


def change_pair(
    base: BehaviorIR,
    final: BehaviorIR,
) -> tuple[ChangeProposal, BehaviorDelta]:
    change_proposal = proposal(base)
    return (
        change_proposal,
        derive_behavior_delta(change_proposal, base, final),
    )
