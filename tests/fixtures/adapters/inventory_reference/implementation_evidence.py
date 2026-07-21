from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

VERSION = "1.0.0"
PRODUCER: dict[str, object] = {
    "kind": "producer",
    "name": "org.ucf.inventory-reference-adapter",
    "version": VERSION,
}
MAPPING_CAPABILITY = "org.ucf.adapter.mapping"
MAPPING_REQUEST_SCHEMA_URI = "urn:ucf:adapter:implementation-mapping-request:1.0.0"
MAPPING_RESULT_SCHEMA_URI = "urn:ucf:adapter:implementation-mapping-result:1.0.0"
MAPPING_PROFILE_PROCEDURE_URI = "urn:ucf:implementation-evidence:map:1.0.0"
MAPPING_ADAPTER_PROCEDURE_URI = "urn:ucf:adapter:python-reference-static-mapping:1.0.0"
VERIFICATION_CAPABILITY = "org.ucf.adapter.verification"
VERIFICATION_REQUEST_SCHEMA_URI = "urn:ucf:adapter:execution-verification-request:1.0.0"
VERIFICATION_RESULT_SCHEMA_URI = "urn:ucf:adapter:execution-verification-result:1.0.0"
VERIFICATION_PROFILE_PROCEDURE_URI = "urn:ucf:implementation-evidence:verify:1.0.0"
VERIFICATION_ADAPTER_PROCEDURE_URI = (
    "urn:ucf:adapter:python-reference-native-check-verification:1.0.0"
)
ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:cpython-linux-native-check-process:1.0.0"
)
CHECK_ID = "check.quote-order.native-python"
CHECK_PROCEDURE_URI = "urn:ucf:fixture-check:quote-order-python-native-contract:1.0.0"
ONBOARDING_SCHEMA_URI = "urn:ucf:onboarding:bundle:1.0.0"
SUBJECT_ID = "use-case.quote-order"
_RENDER_SUBJECT_ID = "use-case.render-receipt"

_ACTION_ID = "action.quote-order"
_RENDER_ACTION_ID = "action.render-receipt"
_QUANTITY_BINDING_ID = "binding.quote-order.quantity"
_UNIT_PRICE_BINDING_ID = "binding.quote-order.unit-price-cents"
_RENDER_QUANTITY_BINDING_ID = "binding.render-receipt.quantity"
_STEP_ID = "step.quote-order"
_RENDER_STEP_ID = "step.render-receipt"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991

type ErrorCode = Literal["invalid_params", "operation_failed"]
type VerificationOutcome = Literal["passed", "failed", "error"]


class ProfileError(ValueError):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BuiltPayload:
    logical: dict[str, object]
    payload: dict[str, object]


@dataclass(frozen=True)
class VerificationPlan:
    request: dict[str, object]
    expected_total_cents: int


def build_mapping_payload(
    payload: object,
    *,
    current_inventory: object,
) -> BuiltPayload:
    request = decode_adapter_payload(
        payload,
        expected_schema_uri=MAPPING_REQUEST_SCHEMA_URI,
    )
    inventory = _object(current_inventory, "current inventory")
    target = _validate_mapping_request(request, inventory)
    source_records = _quote_order_source_records(inventory)
    projection: dict[str, object] = {
        "kind": "implementation_mapping_result",
        "implementation_evidence_version": VERSION,
        "schema_uri": MAPPING_RESULT_SCHEMA_URI,
        "status": "complete",
        "request": request,
        "producer": PRODUCER,
        "capability": _capability(MAPPING_CAPABILITY),
        "procedure_uri": MAPPING_ADAPTER_PROCEDURE_URI,
        "bindings": [
            {
                "kind": "implementation_binding",
                "behavior": target,
                "source_records": source_records,
            }
        ],
    }
    result = {"id": f"mapping.{_sha256(projection)}", **projection}
    return BuiltPayload(
        logical=result,
        payload=encode_adapter_payload(
            result,
            schema_uri=MAPPING_RESULT_SCHEMA_URI,
        ),
    )


def decode_verification_plan(
    payload: object,
    *,
    current_inventory: object,
    mapping: object,
    expected_environment: object,
) -> VerificationPlan:
    request = decode_adapter_payload(
        payload,
        expected_schema_uri=VERIFICATION_REQUEST_SCHEMA_URI,
    )
    inventory = _object(current_inventory, "current inventory")
    mapping_value = _object(mapping, "mapping")
    environment = _object(expected_environment, "execution environment")
    context = _verification_mapping_context(mapping_value, inventory)
    _require_exact(
        request,
        {
            "kind",
            "implementation_evidence_version",
            "schema_uri",
            "capability",
            "profile_procedure_uri",
            "adapter_procedure_uri",
            "mapping",
            "base_behavior",
            "subject",
            "inputs",
            "expected_outputs",
            "source",
            "environment",
            "check",
        },
        "verification request",
    )
    if (
        request["kind"] != "execution_verification_request"
        or request["implementation_evidence_version"] != VERSION
        or request["schema_uri"] != VERIFICATION_REQUEST_SCHEMA_URI
        or request["capability"] != _capability(VERIFICATION_CAPABILITY)
        or request["profile_procedure_uri"] != VERIFICATION_PROFILE_PROCEDURE_URI
        or request["adapter_procedure_uri"] != VERIFICATION_ADAPTER_PROCEDURE_URI
    ):
        _invalid("verification request coordinates are incompatible")
    comparisons = {
        "mapping": context["mapping"],
        "base_behavior": context["base_behavior"],
        "subject": context["subject"],
        "source": context["source"],
        "environment": environment,
        "check": _supported_check(),
    }
    for name, expected in comparisons.items():
        if request[name] != expected:
            _invalid(f"verification {name} differs from current context")
    quantity = _read_integer_port(
        request["inputs"],
        index=0,
        direction="input",
        name="quantity",
    )
    unit_price = _read_integer_port(
        request["inputs"],
        index=1,
        direction="input",
        name="unit-price-cents",
    )
    if (
        type(request["inputs"]) is not list
        or len(request["inputs"]) != 2
        or quantity != 2
        or unit_price != 1250
    ):
        _invalid("verification inputs are outside the supported procedure")
    expected_total = _read_integer_port(
        request["expected_outputs"],
        index=0,
        direction="output",
        name="total-cents",
    )
    if (
        type(request["expected_outputs"]) is not list
        or len(request["expected_outputs"]) != 1
        or expected_total < 0
    ):
        _invalid("verification output is outside the supported procedure")
    return VerificationPlan(
        request=request,
        expected_total_cents=expected_total,
    )


def build_verification_result_payload(
    request: object,
    *,
    outcome: VerificationOutcome,
    executed_at: str,
) -> BuiltPayload:
    request_value = _object(request, "verification request")
    if outcome not in {"passed", "failed", "error"}:
        _invalid("verification outcome is unsupported")
    try:
        parsed = datetime.strptime(executed_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ProfileError(
            "invalid_params",
            "verification timestamp is not whole-second UTC",
        ) from error
    if parsed.year < 1:
        _invalid("verification timestamp is invalid")
    projection: dict[str, object] = {
        "kind": "execution_verification_result",
        "implementation_evidence_version": VERSION,
        "schema_uri": VERIFICATION_RESULT_SCHEMA_URI,
        "status": "completed",
        "request": request_value,
        "outcome": outcome,
        "executed_at": executed_at,
        "producer": PRODUCER,
        "capability": _capability(VERIFICATION_CAPABILITY),
        "procedure_uri": VERIFICATION_ADAPTER_PROCEDURE_URI,
    }
    result = {"id": f"result.{_sha256(projection)}", **projection}
    return BuiltPayload(
        logical=result,
        payload=encode_adapter_payload(
            result,
            schema_uri=VERIFICATION_RESULT_SCHEMA_URI,
        ),
    )


def encode_adapter_payload(
    document: object,
    *,
    schema_uri: str,
) -> dict[str, object]:
    if type(schema_uri) is not str:
        _invalid("adapter payload schema URI is invalid")
    return {
        "kind": "adapter_payload",
        "schema_uri": schema_uri,
        "schema_version": VERSION,
        "value": _encode_tagged(document, depth=0),
    }


def decode_adapter_payload(
    payload: object,
    *,
    expected_schema_uri: str,
) -> dict[str, object]:
    value = _object(payload, "adapter payload")
    _require_exact(
        value,
        {"kind", "schema_uri", "schema_version", "value"},
        "adapter payload",
    )
    if (
        value["kind"] != "adapter_payload"
        or value["schema_uri"] != expected_schema_uri
        or value["schema_version"] != VERSION
    ):
        _invalid("adapter payload coordinates are incompatible")
    decoded = _decode_tagged(value["value"], depth=0)
    if type(decoded) is not dict:
        _invalid("adapter payload root is not a record")
    return decoded


def canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProfileError(
            "invalid_params",
            "profile value is not canonical JSON",
        ) from error


def _validate_mapping_request(
    request: dict[str, object],
    inventory: dict[str, object],
) -> dict[str, object]:
    _require_exact(
        request,
        {
            "kind",
            "implementation_evidence_version",
            "schema_uri",
            "capability",
            "profile_procedure_uri",
            "adapter_procedure_uri",
            "onboarding",
            "behavior",
            "inventory",
            "targets",
        },
        "mapping request",
    )
    if (
        request["kind"] != "implementation_mapping_request"
        or request["implementation_evidence_version"] != VERSION
        or request["schema_uri"] != MAPPING_REQUEST_SCHEMA_URI
        or request["capability"] != _capability(MAPPING_CAPABILITY)
        or request["profile_procedure_uri"] != MAPPING_PROFILE_PROCEDURE_URI
        or request["adapter_procedure_uri"] != MAPPING_ADAPTER_PROCEDURE_URI
    ):
        _invalid("mapping request coordinates are incompatible")
    onboarding = _object(request["onboarding"], "onboarding binding")
    _require_exact(
        onboarding,
        {"kind", "schema_uri", "schema_version", "canonical_digest"},
        "onboarding binding",
    )
    if (
        onboarding["kind"] != "onboarding_bundle_binding"
        or onboarding["schema_uri"] != ONBOARDING_SCHEMA_URI
        or onboarding["schema_version"] != VERSION
        or not _valid_digest(onboarding["canonical_digest"])
    ):
        _invalid("mapping onboarding binding is incompatible")
    if request["inventory"] != inventory:
        _invalid("mapping request inventory differs from current inventory")
    behavior = _object(request["behavior"], "Behavior IR")
    _validate_quote_order_behavior(behavior)
    targets = request["targets"]
    if type(targets) is not list or len(targets) != 1:
        _invalid("mapping request requires one supported target")
    target = _object(targets[0], "mapping target")
    expected_target = {
        "kind": "behavior_entity_ref",
        "document_id": behavior["document_id"],
        "ir_version": behavior["ir_version"],
        "canonical_digest": _digest(_sha256(behavior)),
        "target_kind": "use_case",
        "target_id": SUBJECT_ID,
    }
    if target != expected_target:
        _invalid("mapping target does not bind the supported Behavior root")
    return target


def _validate_quote_order_behavior(behavior: dict[str, object]) -> None:
    _require_exact(
        behavior,
        {"kind", "ir_version", "document_id", "roots", "entities"},
        "Behavior IR",
    )
    if (
        behavior["kind"] != "behavior_ir"
        or behavior["ir_version"] != VERSION
        or type(behavior["document_id"]) is not str
        or _IDENTIFIER.fullmatch(behavior["document_id"]) is None
    ):
        _invalid("mapping Behavior IR coordinates are incompatible")
    roots = behavior["roots"]
    entities = behavior["entities"]
    if roots != [
        _entity_ref("use_case", SUBJECT_ID),
        _entity_ref("use_case", _RENDER_SUBJECT_ID),
    ]:
        _invalid("mapping Behavior root is unsupported")
    if type(entities) is not list or len(entities) != 11:
        _invalid("mapping Behavior graph shape is unsupported")
    if any(type(entity) is not dict for entity in entities):
        _invalid("mapping Behavior entity is not a record")
    if any(
        type(entity.get("kind")) is not str
        or type(entity.get("id")) is not str
        or _IDENTIFIER.fullmatch(entity["id"]) is None
        for entity in entities
    ):
        _invalid("mapping Behavior entity identity is invalid")
    identities = [(entity.get("kind"), entity.get("id")) for entity in entities]
    if identities != sorted(identities) or len(set(identities)) != len(identities):
        _invalid("mapping Behavior entities are not canonical")
    index = {(entity["kind"], entity["id"]): entity for entity in entities}
    provenance_items = [
        entity for entity in entities if entity.get("kind") == "provenance"
    ]
    if len(provenance_items) != 2:
        _invalid("mapping Behavior provenance is unavailable")
    for provenance in provenance_items:
        _validate_provenance(provenance)
    provenance_ref = _referenced_provenance(index, SUBJECT_ID)
    render_provenance_ref = _referenced_provenance(index, _RENDER_SUBJECT_ID)
    if provenance_ref == render_provenance_ref:
        _invalid("mapping Behavior reviewed roots share forged provenance")
    expected = {
        ("action", _ACTION_ID): {
            "kind": "action",
            "id": _ACTION_ID,
            "input_ports": _input_ports(),
            "output_ports": _output_ports(),
            "effects": [],
            "requires": [],
            "provenance": provenance_ref,
        },
        ("binding", _QUANTITY_BINDING_ID): _binding(
            _QUANTITY_BINDING_ID,
            "quantity",
            provenance_ref,
        ),
        ("binding", _UNIT_PRICE_BINDING_ID): _binding(
            _UNIT_PRICE_BINDING_ID,
            "unit-price-cents",
            provenance_ref,
        ),
        ("step", _STEP_ID): {
            "kind": "step",
            "id": _STEP_ID,
            "action": _entity_ref("action", _ACTION_ID),
            "bindings": [
                _entity_ref("binding", _QUANTITY_BINDING_ID),
                _entity_ref("binding", _UNIT_PRICE_BINDING_ID),
            ],
            "effects": [],
            "observations": [],
            "requires": [],
            "provenance": provenance_ref,
        },
        ("use_case", SUBJECT_ID): {
            "kind": "use_case",
            "id": SUBJECT_ID,
            "input_ports": _input_ports(),
            "output_ports": _output_ports(),
            "steps": [_entity_ref("step", _STEP_ID)],
            "invariants": [],
            "requires": [],
            "provenance": provenance_ref,
        },
        ("action", _RENDER_ACTION_ID): {
            "kind": "action",
            "id": _RENDER_ACTION_ID,
            "input_ports": [_port("quantity")],
            "output_ports": _output_ports(),
            "effects": [],
            "requires": [],
            "provenance": render_provenance_ref,
        },
        ("binding", _RENDER_QUANTITY_BINDING_ID): {
            "kind": "binding",
            "id": _RENDER_QUANTITY_BINDING_ID,
            "target": _port_ref(
                "step",
                _RENDER_STEP_ID,
                "quantity",
            ),
            "source": _port_ref(
                "use_case",
                _RENDER_SUBJECT_ID,
                "quantity",
            ),
            "provenance": render_provenance_ref,
        },
        ("step", _RENDER_STEP_ID): {
            "kind": "step",
            "id": _RENDER_STEP_ID,
            "action": _entity_ref("action", _RENDER_ACTION_ID),
            "bindings": [
                _entity_ref("binding", _RENDER_QUANTITY_BINDING_ID),
            ],
            "effects": [],
            "observations": [],
            "requires": [],
            "provenance": render_provenance_ref,
        },
        ("use_case", _RENDER_SUBJECT_ID): {
            "kind": "use_case",
            "id": _RENDER_SUBJECT_ID,
            "input_ports": [_port("quantity")],
            "output_ports": _output_ports(),
            "steps": [_entity_ref("step", _RENDER_STEP_ID)],
            "invariants": [],
            "requires": [],
            "provenance": render_provenance_ref,
        },
    }
    for identity, expected_entity in expected.items():
        if index.get(identity) != expected_entity:
            _invalid("mapping Behavior graph does not resolve canonically")


def _referenced_provenance(
    index: dict[tuple[object, object], dict[str, object]],
    subject_id: str,
) -> dict[str, object]:
    subject = index.get(("use_case", subject_id))
    if subject is None:
        _invalid("mapping Behavior reviewed root is unavailable")
    reference = _object(subject.get("provenance"), "Behavior provenance reference")
    _require_exact(
        reference,
        {"kind", "target_kind", "target_id"},
        "Behavior provenance reference",
    )
    target_id = reference["target_id"]
    if (
        reference["kind"] != "entity_ref"
        or reference["target_kind"] != "provenance"
        or type(target_id) is not str
        or ("provenance", target_id) not in index
    ):
        _invalid("mapping Behavior provenance reference is broken")
    return reference


def _validate_provenance(value: dict[str, object]) -> None:
    _require_exact(
        value,
        {"kind", "id", "source", "producer", "captured_at"},
        "Behavior provenance",
    )
    source = _object(value["source"], "provenance source")
    producer = _object(value["producer"], "provenance producer")
    if (
        value["kind"] != "provenance"
        or type(value["id"]) is not str
        or not str(value["id"]).startswith("provenance.")
        or not _valid_timestamp(value["captured_at"])
        or set(source) != {"kind", "uri", "revision"}
        or source["kind"] != "artifact_source"
        or type(source["uri"]) is not str
        or not str(source["uri"]).startswith("urn:")
        or not _valid_digest(source["revision"])
        or set(producer) != {"kind", "name", "version"}
        or producer["kind"] != "producer"
        or type(producer["name"]) is not str
        or producer["version"] != VERSION
    ):
        _invalid("mapping Behavior provenance is incompatible")


def _quote_order_source_records(
    inventory: dict[str, object],
) -> list[dict[str, object]]:
    records = inventory.get("records")
    if type(records) is not list:
        _invalid("current inventory records are unavailable")
    matches = []
    for record in records:
        if type(record) is not dict or record.get("kind") != "public_interface":
            continue
        if record.get("name") != "quote_order":
            continue
        if (
            record.get("interface_kind_uri")
            != "urn:ucf:inventory-interface:python-function:1.0.0"
            or record.get("container") is not None
            or type(record.get("id")) is not str
            or not str(record["id"]).startswith("interface.")
            or not _valid_digest(record.get("declaration_digest"))
        ):
            _invalid("quote-order public interface is incompatible")
        matches.append(record)
    if len(matches) != 1:
        _invalid("quote-order implementation evidence is unavailable")
    return [
        {
            "kind": "inventory_record_ref",
            "target_kind": "public_interface",
            "target_id": matches[0]["id"],
        }
    ]


def _verification_mapping_context(
    mapping: dict[str, object],
    inventory: dict[str, object],
) -> dict[str, object]:
    _require_exact(
        mapping,
        {
            "kind",
            "implementation_evidence_version",
            "schema_uri",
            "id",
            "status",
            "request",
            "producer",
            "capability",
            "procedure_uri",
            "bindings",
        },
        "mapping result",
    )
    projection = {name: value for name, value in mapping.items() if name != "id"}
    if (
        mapping["kind"] != "implementation_mapping_result"
        or mapping["implementation_evidence_version"] != VERSION
        or mapping["schema_uri"] != MAPPING_RESULT_SCHEMA_URI
        or mapping["id"] != f"mapping.{_sha256(projection)}"
        or mapping["status"] != "complete"
        or mapping["producer"] != PRODUCER
        or mapping["capability"] != _capability(MAPPING_CAPABILITY)
        or mapping["procedure_uri"] != MAPPING_ADAPTER_PROCEDURE_URI
    ):
        _invalid("verification mapping result is incompatible")
    mapping_request = _object(mapping["request"], "mapping request")
    if mapping_request.get("inventory") != inventory:
        _invalid("verification mapping inventory is stale")
    bindings = mapping["bindings"]
    if type(bindings) is not list or len(bindings) != 1:
        _invalid("verification mapping binding is unavailable")
    binding = _object(bindings[0], "mapping binding")
    _require_exact(
        binding,
        {"kind", "behavior", "source_records"},
        "mapping binding",
    )
    expected_records = _quote_order_source_records(inventory)
    subject = _object(binding["behavior"], "mapping subject")
    if (
        binding["kind"] != "implementation_binding"
        or binding["source_records"] != expected_records
        or subject.get("target_kind") != "use_case"
        or subject.get("target_id") != SUBJECT_ID
    ):
        _invalid("verification mapping subject is unsupported")
    return {
        "mapping": {
            "kind": "implementation_mapping_result_ref",
            "schema_uri": MAPPING_RESULT_SCHEMA_URI,
            "schema_version": VERSION,
            "target_id": mapping["id"],
            "canonical_digest": _digest(_sha256(mapping)),
        },
        "base_behavior": {
            "kind": "behavior_document_ref",
            "document_id": subject["document_id"],
            "ir_version": subject["ir_version"],
            "canonical_digest": subject["canonical_digest"],
        },
        "subject": subject,
        "source": {
            "kind": "implementation_source",
            "subject_uri": inventory["subject_uri"],
            "source_revision": inventory["source_revision"],
            "records": expected_records,
        },
    }


def _read_integer_port(
    values: object,
    *,
    index: int,
    direction: str,
    name: str,
) -> int:
    if type(values) is not list or index >= len(values):
        _invalid("verification port values are unavailable")
    item = _object(values[index], "verification port value")
    _require_exact(item, {"kind", "port", "value"}, "port value")
    expected_port = {
        "kind": "port_ref",
        "owner": _entity_ref("use_case", SUBJECT_ID),
        "direction": direction,
        "name": name,
    }
    integer = _object(item["value"], "integer port value")
    if (
        item["kind"] != "execution_port_value"
        or item["port"] != expected_port
        or set(integer) != {"kind", "value"}
        or integer["kind"] != "integer"
        or type(integer["value"]) is not int
        or not -_MAX_SAFE_INTEGER <= integer["value"] <= _MAX_SAFE_INTEGER
    ):
        _invalid("verification port value is incompatible")
    return integer["value"]


def _supported_check() -> dict[str, object]:
    return {
        "kind": "check",
        "id": CHECK_ID,
        "version": VERSION,
        "procedure_uri": CHECK_PROCEDURE_URI,
    }


def _binding(
    identifier: str,
    name: str,
    provenance: dict[str, object],
) -> dict[str, object]:
    return {
        "kind": "binding",
        "id": identifier,
        "target": _port_ref("step", _STEP_ID, name),
        "source": _port_ref("use_case", SUBJECT_ID, name),
        "provenance": provenance,
    }


def _input_ports() -> list[dict[str, object]]:
    return [_port("quantity"), _port("unit-price-cents")]


def _output_ports() -> list[dict[str, object]]:
    return [_port("total-cents")]


def _port(name: str) -> dict[str, object]:
    return {
        "kind": "port",
        "name": name,
        "value_kind": "integer",
        "required": True,
    }


def _entity_ref(kind: str, identifier: str) -> dict[str, object]:
    return {"kind": "entity_ref", "target_kind": kind, "target_id": identifier}


def _port_ref(kind: str, identifier: str, name: str) -> dict[str, object]:
    return {
        "kind": "port_ref",
        "owner": _entity_ref(kind, identifier),
        "direction": "input",
        "name": name,
    }


def _capability(name: str) -> dict[str, object]:
    return {"kind": "capability", "name": name, "version": VERSION}


def _digest(value: str) -> dict[str, object]:
    return {"kind": "digest", "algorithm": "sha-256", "value": value}


def _valid_digest(value: object) -> bool:
    return (
        type(value) is dict
        and set(value) == {"kind", "algorithm", "value"}
        and value["kind"] == "digest"
        and value["algorithm"] == "sha-256"
        and type(value["value"]) is str
        and _DIGEST.fullmatch(value["value"]) is not None
    )


def _valid_timestamp(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _invalid(f"{label} is not a record")
    return value


def _require_exact(
    value: dict[str, object],
    fields: set[str],
    label: str,
) -> None:
    if set(value) != fields:
        _invalid(f"{label} fields are not exact")


def _encode_tagged(value: object, *, depth: int) -> dict[str, object]:
    if depth > 128:
        _invalid("profile value exceeds maximum nesting depth")
    if value is None:
        return {"kind": "null"}
    if type(value) is bool:
        return {"kind": "boolean", "value": value}
    if type(value) is int:
        if not -_MAX_SAFE_INTEGER <= value <= _MAX_SAFE_INTEGER:
            _invalid("profile integer is outside the safe range")
        return {"kind": "integer", "value": value}
    if type(value) is str:
        return {"kind": "string", "value": value}
    if type(value) is list or type(value) is tuple:
        return {
            "kind": "list",
            "items": [_encode_tagged(item, depth=depth + 1) for item in value],
        }
    if type(value) is dict:
        if any(type(name) is not str for name in value):
            _invalid("profile record name is not a string")
        return {
            "kind": "record",
            "entries": [
                {
                    "kind": "record_entry",
                    "name": name,
                    "value": _encode_tagged(value[name], depth=depth + 1),
                }
                for name in sorted(value)
            ],
        }
    _invalid("profile value has an unsupported JSON type")


def _decode_tagged(value: object, *, depth: int) -> object:
    if depth > 128:
        _invalid("tagged value exceeds maximum nesting depth")
    tagged = _object(value, "tagged value")
    kind = tagged.get("kind")
    if kind == "null":
        _require_exact(tagged, {"kind"}, "null value")
        return None
    if kind == "boolean":
        _require_exact(tagged, {"kind", "value"}, "boolean value")
        if type(tagged["value"]) is not bool:
            _invalid("tagged boolean is invalid")
        return tagged["value"]
    if kind == "integer":
        _require_exact(tagged, {"kind", "value"}, "integer value")
        integer = tagged["value"]
        if (
            type(integer) is not int
            or not -_MAX_SAFE_INTEGER <= integer <= _MAX_SAFE_INTEGER
        ):
            _invalid("tagged integer is outside the safe range")
        return integer
    if kind == "string":
        _require_exact(tagged, {"kind", "value"}, "string value")
        if type(tagged["value"]) is not str:
            _invalid("tagged string is invalid")
        return tagged["value"]
    if kind == "list":
        _require_exact(tagged, {"kind", "items"}, "list value")
        items = tagged["items"]
        if type(items) is not list:
            _invalid("tagged list items are invalid")
        return [_decode_tagged(item, depth=depth + 1) for item in items]
    if kind == "record":
        _require_exact(tagged, {"kind", "entries"}, "record value")
        entries = tagged["entries"]
        if type(entries) is not list:
            _invalid("tagged record entries are invalid")
        result: dict[str, object] = {}
        names: list[str] = []
        for entry_value in entries:
            entry = _object(entry_value, "record entry")
            _require_exact(entry, {"kind", "name", "value"}, "record entry")
            name = entry["name"]
            if entry["kind"] != "record_entry" or type(name) is not str:
                _invalid("tagged record entry is invalid")
            if name in result:
                _invalid("tagged record contains duplicate names")
            names.append(name)
            result[name] = _decode_tagged(entry["value"], depth=depth + 1)
        if names != sorted(names):
            _invalid("tagged record entries are not canonical")
        return result
    _invalid("tagged value kind is unsupported")


def _invalid(message: str) -> None:
    raise ProfileError("invalid_params", message)
