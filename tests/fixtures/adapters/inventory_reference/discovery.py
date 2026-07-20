from __future__ import annotations

import hashlib

from .profile import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    PRODUCER,
    InvalidProfile,
    canonical_json,
    decode_tagged,
    encode_tagged,
)

DISCOVERY_CAPABILITY = "org.ucf.adapter.discovery"
DISCOVERY_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:discovery-request:1.0.0"
)
DISCOVERY_RESULT_SCHEMA_URI = (
    "urn:ucf:adapter:discovery-result:1.0.0"
)
DISCOVERY_PROCEDURE_URI = (
    "urn:ucf:onboarding-procedure:python-ast-discovery:1.0.0"
)
DISCOVERY_CONFIDENCE_BASIS = (
    "urn:ucf:onboarding-confidence:python-public-function:1.0.0"
)
PYTHON_INTERFACE_DIALECT = (
    "urn:ucf:inventory-interface:python-function:1.0.0"
)

_FUNCTIONS = {
    "format_receipt": {
        "slug": "format-receipt",
        "confidence": "0.82",
        "inputs": (("total-cents", "integer", True),),
        "outputs": (("receipt", "string", True),),
    },
    "legacy_discount_hint": {
        "slug": "legacy-discount-hint",
        "confidence": "0.61",
        "inputs": (("code", "string", True),),
        "outputs": (("discount-percent", "integer", False),),
    },
    "normalize_coupon": {
        "slug": "normalize-coupon",
        "confidence": "0.82",
        "inputs": (("code", "string", True),),
        "outputs": (("normalized-code", "string", True),),
    },
    "quote_order": {
        "slug": "quote-order",
        "confidence": "0.82",
        "inputs": (
            ("quantity", "integer", True),
            ("unit-price-cents", "integer", True),
        ),
        "outputs": (("total-cents", "integer", True),),
    },
}


def decode_discovery_request(
    payload: object,
    *,
    inventory: dict[str, object],
) -> dict[str, object]:
    document = _object(payload, "adapter payload")
    _exact(
        document,
        {"kind", "schema_uri", "schema_version", "value"},
        "adapter payload",
    )
    if (
        document["kind"] != "adapter_payload"
        or document["schema_uri"] != DISCOVERY_REQUEST_SCHEMA_URI
        or document["schema_version"] != INVENTORY_VERSION
    ):
        raise InvalidProfile("discovery payload coordinates are incompatible")

    request = _object(
        decode_tagged(document["value"]),
        "discovery request",
    )
    _exact(
        request,
        {
            "kind",
            "onboarding_version",
            "schema_uri",
            "capability",
            "inventory_binding",
            "inventory",
        },
        "discovery request",
    )
    if (
        request["kind"] != "discovery_request_profile"
        or request["onboarding_version"] != INVENTORY_VERSION
        or request["schema_uri"] != DISCOVERY_REQUEST_SCHEMA_URI
    ):
        raise InvalidProfile("discovery request coordinates are incompatible")
    _validate_capability(request["capability"])

    embedded_inventory = _object(
        request["inventory"],
        "embedded inventory",
    )
    if canonical_json(embedded_inventory) != canonical_json(inventory):
        raise InvalidProfile(
            "discovery request does not embed the inventoried snapshot"
        )
    binding = _object(
        request["inventory_binding"],
        "inventory binding",
    )
    _validate_inventory_binding(binding, inventory)
    return request


def build_discovery_result(
    request: dict[str, object],
) -> dict[str, object]:
    inventory = _object(request["inventory"], "embedded inventory")
    records = _array(inventory["records"], "inventory records")
    interfaces = [
        _object(record, "inventory record")
        for record in records
        if (
            type(record) is dict
            and record.get("kind") == "public_interface"
        )
    ]
    interfaces.sort(key=lambda record: str(record["id"]))

    context = {
        "inventory_binding": request["inventory_binding"],
        "producer": PRODUCER,
        "capability": _capability(),
        "procedure_uri": DISCOVERY_PROCEDURE_URI,
    }
    candidates: list[dict[str, object]] = []
    eligible: list[dict[str, object]] = []
    uncovered: list[dict[str, object]] = []
    seen_names: dict[str, int] = {}
    for interface in interfaces:
        name = interface.get("name")
        if type(name) is str:
            seen_names[name] = seen_names.get(name, 0) + 1
    for interface in interfaces:
        reference = _inventory_reference(interface)
        eligible.append(reference)
        name = interface.get("name")
        specification = (
            _FUNCTIONS.get(name)
            if (
                type(name) is str
                and seen_names.get(name) == 1
                and interface.get("interface_kind_uri")
                == PYTHON_INTERFACE_DIALECT
            )
            else None
        )
        if specification is None:
            uncovered.append(reference)
            continue
        proposal = _proposal(specification)
        candidate = {
            "kind": "discovery_candidate",
            "id": "candidate." + ("0" * 64),
            "semantic_digest": _digest(canonical_json(proposal)),
            "subject": reference,
            "evidence": [reference],
            "confidence": {
                "kind": "confidence",
                "scale": "decimal-0-to-1",
                "value": specification["confidence"],
                "basis": DISCOVERY_CONFIDENCE_BASIS,
            },
            "proposal": proposal,
        }
        candidate["id"] = _candidate_id(candidate, context)
        candidates.append(candidate)

    eligible.sort(key=_reference_key)
    uncovered.sort(key=_reference_key)
    candidates.sort(key=lambda candidate: str(candidate["id"]))
    return {
        "kind": "discovery_result_profile",
        "onboarding_version": INVENTORY_VERSION,
        "schema_uri": DISCOVERY_RESULT_SCHEMA_URI,
        **context,
        "coverage": {
            "kind": "discovery_coverage",
            "status": "partial" if uncovered else "complete",
            "eligible_subjects": eligible,
            "uncovered_subjects": uncovered,
        },
        "diagnostics": [],
        "candidates": candidates,
    }


def encode_discovery_result_payload(
    result: dict[str, object],
    *,
    schema_uri: str = DISCOVERY_RESULT_SCHEMA_URI,
) -> dict[str, object]:
    return {
        "kind": "adapter_payload",
        "schema_uri": schema_uri,
        "schema_version": INVENTORY_VERSION,
        "value": encode_tagged(result),
    }


def _validate_capability(value: object) -> None:
    capability = _object(value, "discovery capability")
    _exact(capability, {"kind", "name", "version"}, "capability")
    if capability != _capability():
        raise InvalidProfile("discovery capability is incompatible")


def _validate_inventory_binding(
    binding: dict[str, object],
    inventory: dict[str, object],
) -> None:
    _exact(
        binding,
        {
            "kind",
            "schema_uri",
            "inventory_version",
            "subject_uri",
            "source_revision",
            "canonical_digest",
        },
        "inventory binding",
    )
    expected = {
        "kind": "inventory_binding",
        "schema_uri": INVENTORY_SCHEMA_URI,
        "inventory_version": INVENTORY_VERSION,
        "subject_uri": inventory["subject_uri"],
        "source_revision": inventory["source_revision"],
        "canonical_digest": _digest(canonical_json(inventory)),
    }
    if binding != expected:
        raise InvalidProfile(
            "inventory binding does not name the exact inventoried snapshot"
        )


def _proposal(specification: dict[str, object]) -> dict[str, object]:
    slug = str(specification["slug"])
    action_id = f"action.{slug}"
    step_id = f"step.{slug}"
    use_case_id = f"use-case.{slug}"
    action_reference = _entity_reference("proposed_action", action_id)
    step_reference = _entity_reference("proposed_step", step_id)
    use_case_reference = _entity_reference(
        "proposed_use_case",
        use_case_id,
    )
    inputs = [
        _port(name, value_kind, required)
        for name, value_kind, required in specification["inputs"]
    ]
    outputs = [
        _port(name, value_kind, required)
        for name, value_kind, required in specification["outputs"]
    ]
    bindings: list[dict[str, object]] = []
    binding_references: list[dict[str, object]] = []
    for port in inputs:
        binding_id = f"binding.{slug}.{port['name']}"
        binding_reference = _entity_reference(
            "proposed_binding",
            binding_id,
        )
        binding_references.append(binding_reference)
        bindings.append(
            {
                "kind": "proposed_binding",
                "id": binding_id,
                "target": {
                    "kind": "proposal_port_ref",
                    "owner": step_reference,
                    "direction": "input",
                    "name": port["name"],
                },
                "source": {
                    "kind": "proposal_port_ref",
                    "owner": use_case_reference,
                    "direction": "input",
                    "name": port["name"],
                },
            }
        )
    entities = [
        {
            "kind": "proposed_action",
            "id": action_id,
            "input_ports": inputs,
            "output_ports": outputs,
        },
        *bindings,
        {
            "kind": "proposed_step",
            "id": step_id,
            "action": action_reference,
            "bindings": binding_references,
        },
        {
            "kind": "proposed_use_case",
            "id": use_case_id,
            "input_ports": inputs,
            "output_ports": outputs,
            "steps": [step_reference],
        },
    ]
    entities.sort(key=lambda entity: (str(entity["kind"]), str(entity["id"])))
    return {
        "kind": "candidate_proposal",
        "root": use_case_reference,
        "entities": entities,
    }


def _candidate_id(
    candidate: dict[str, object],
    context: dict[str, object],
) -> str:
    projected_candidate = {
        key: value
        for key, value in candidate.items()
        if key not in {"id", "semantic_digest"}
    }
    projection = {
        "candidate": projected_candidate,
        "capability": context["capability"],
        "inventory_binding": context["inventory_binding"],
        "procedure_uri": context["procedure_uri"],
        "producer": context["producer"],
    }
    return "candidate." + hashlib.sha256(
        canonical_json(projection)
    ).hexdigest()


def _inventory_reference(
    interface: dict[str, object],
) -> dict[str, object]:
    identifier = interface.get("id")
    if type(identifier) is not str:
        raise InvalidProfile("public interface identifier is invalid")
    return {
        "kind": "inventory_record_ref",
        "target_kind": "public_interface",
        "target_id": identifier,
    }


def _entity_reference(
    kind: str,
    identifier: str,
) -> dict[str, object]:
    return {
        "kind": "proposal_entity_ref",
        "target_kind": kind,
        "target_id": identifier,
    }


def _port(
    name: str,
    value_kind: str,
    required: bool,
) -> dict[str, object]:
    return {
        "kind": "port",
        "name": name,
        "value_kind": value_kind,
        "required": required,
    }


def _capability() -> dict[str, str]:
    return {
        "kind": "capability",
        "name": DISCOVERY_CAPABILITY,
        "version": INVENTORY_VERSION,
    }


def _digest(payload: bytes) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": hashlib.sha256(payload).hexdigest(),
    }


def _reference_key(reference: dict[str, object]) -> tuple[str, str]:
    return (
        str(reference["target_kind"]),
        str(reference["target_id"]),
    )


def _exact(
    value: dict[str, object],
    expected: set[str],
    label: str,
) -> None:
    if set(value) != expected:
        raise InvalidProfile(f"{label} fields are not exact")


def _object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise InvalidProfile(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list:
        raise InvalidProfile(f"{label} must be a list")
    return value
