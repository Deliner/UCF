from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ucf.ir import (
    BehaviorIR,
    IRErrorCode,
    IRValidationError,
    canonical_ir_json,
    parse_ir_json,
    validate_required_capabilities,
)

IR_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "v1" / "complete.json"
)
COMMON_CAPABILITIES = {"org.ucf.rule.preserve": "1.0.0"}
PLATFORM_CAPABILITIES = {
    "http": "org.ucf.platform.http-loopback",
    "cli": "org.ucf.platform.cli-process",
    "event": "org.ucf.platform.file-spool-event",
}
PLATFORM_CAPABILITY_ID = "capability.state-assignment"
NEUTRAL_CAPABILITY_ID = "capability.platform-boundary"
NEUTRAL_CAPABILITY_NAME = "org.ucf.platform.boundary"

TRANSPORT_SPECIFIC_FIELD_TOKENS = {
    "transport",
    "platform",
    "http",
    "method",
    "status",
    "header",
    "headers",
    "cli",
    "argv",
    "stdin",
    "stdout",
    "stderr",
    "exit",
    "event",
    "message",
    "broker",
    "topic",
    "partition",
    "group",
    "ack",
    "acknowledgement",
    "language",
    "framework",
    "build",
    "tool",
    "runtime",
    "implementation",
}


@pytest.fixture(scope="module")
def canonical_platform_documents() -> dict[str, BehaviorIR]:
    base = json.loads(IR_FIXTURE.read_text(encoding="utf-8"))
    return {
        platform: _platform_document(
            base,
            platform=platform,
            capability_name=capability_name,
        )
        for platform, capability_name in PLATFORM_CAPABILITIES.items()
    }


def test_http_cli_and_event_documents_share_one_neutral_ir_projection(
    canonical_platform_documents: dict[str, BehaviorIR],
) -> None:
    canonical_documents = {
        platform: canonical_ir_json(document)
        for platform, document in canonical_platform_documents.items()
    }

    assert len(set(canonical_documents.values())) == len(PLATFORM_CAPABILITIES)
    assert all(
        canonical_ir_json(parse_ir_json(payload)) == payload
        for payload in canonical_documents.values()
    )

    projections = {
        json.dumps(
            _neutral_projection(document),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        for document in canonical_platform_documents.values()
    }
    assert len(projections) == 1

    projection = json.loads(projections.pop())
    assert Counter(entity["kind"] for entity in projection["entities"]) == Counter(
        {
            "action": 1,
            "binding": 1,
            "capability_requirement": 2,
            "effect": 1,
            "invariant": 1,
            "observation": 1,
            "provenance": 1,
            "step": 1,
            "use_case": 1,
            "verification_evidence": 1,
        }
    )


def test_platform_coordinates_do_not_add_transport_specific_ir_fields(
    canonical_platform_documents: dict[str, BehaviorIR],
) -> None:
    for document in canonical_platform_documents.values():
        payload = json.loads(canonical_ir_json(document))
        fields = tuple(_field_owners(payload))

        assert {
            field
            for field, _owner_kind in fields
            if set(field.replace("-", "_").split("_")) & TRANSPORT_SPECIFIC_FIELD_TOKENS
        } == set()
        assert {owner_kind for field, owner_kind in fields if field == "path"} == {
            "domain_target"
        }


@pytest.mark.parametrize("platform", tuple(PLATFORM_CAPABILITIES))
@pytest.mark.parametrize(
    "available_version",
    [None, "0.9.9"],
    ids=["missing", "too-old"],
)
def test_missing_or_too_old_platform_capability_is_rejected_explicitly(
    canonical_platform_documents: dict[str, BehaviorIR],
    platform: str,
    available_version: str | None,
) -> None:
    capability_name = PLATFORM_CAPABILITIES[platform]
    available = dict(COMMON_CAPABILITIES)
    if available_version is not None:
        available[capability_name] = available_version

    with pytest.raises(IRValidationError) as captured:
        validate_required_capabilities(
            canonical_platform_documents[platform],
            available,
        )

    assert captured.value.code is IRErrorCode.UNSUPPORTED_CAPABILITY
    assert capability_name in captured.value.message
    assert captured.value.location is not None
    assert captured.value.location.endswith(".minimum_version")


def test_exact_platform_capability_versions_are_accepted(
    canonical_platform_documents: dict[str, BehaviorIR],
) -> None:
    for platform, document in canonical_platform_documents.items():
        validate_required_capabilities(
            document,
            {
                **COMMON_CAPABILITIES,
                PLATFORM_CAPABILITIES[platform]: "1.0.0",
            },
        )


def _platform_document(
    base: dict[str, Any],
    *,
    platform: str,
    capability_name: str,
) -> BehaviorIR:
    payload = copy.deepcopy(base)
    capability_id = f"capability.platform-{platform}"
    payload["document_id"] = f"document.checkout-reservation-{platform}"

    for value in _objects(payload):
        if (
            value.get("kind") == "entity_ref"
            and value.get("target_id") == PLATFORM_CAPABILITY_ID
        ):
            value["target_id"] = capability_id

    capability = next(
        entity
        for entity in payload["entities"]
        if entity.get("id") == PLATFORM_CAPABILITY_ID
    )
    capability["id"] = capability_id
    capability["name"] = capability_name
    return parse_ir_json(json.dumps(payload))


def _neutral_projection(document: BehaviorIR) -> dict[str, Any]:
    payload = json.loads(canonical_ir_json(document))
    capability = next(
        entity
        for entity in payload["entities"]
        if entity.get("name") in PLATFORM_CAPABILITIES.values()
    )
    capability_id = capability["id"]
    payload["document_id"] = "document.checkout-reservation-platform-neutral"

    for value in _objects(payload):
        if (
            value.get("kind") == "entity_ref"
            and value.get("target_id") == capability_id
        ):
            value["target_id"] = NEUTRAL_CAPABILITY_ID
        if (
            value.get("kind") == "capability_requirement"
            and value.get("id") == capability_id
        ):
            value["id"] = NEUTRAL_CAPABILITY_ID
            value["name"] = NEUTRAL_CAPABILITY_NAME
    return payload


def _objects(value: Any) -> tuple[dict[str, Any], ...]:
    found: list[dict[str, Any]] = []
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            found.append(current)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return tuple(found)


def _field_owners(value: Any) -> tuple[tuple[str, str | None], ...]:
    fields: list[tuple[str, str | None]] = []
    for item in _objects(value):
        owner_kind = item.get("kind")
        fields.extend((field, owner_kind) for field in item)
    return tuple(fields)
