from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    EXECUTION_VERIFICATION_PROCEDURE_URI,
    EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
    ExecutionEnvironment,
    ExecutionPortValue,
    ExecutionVerificationRequest,
    ImplementationMappingResultRef,
    ImplementationSource,
    canonical_implementation_evidence_digest,
    canonical_implementation_evidence_json,
    parse_execution_verification_request_json,
)
from ucf.ir.models import (
    Check,
    Digest,
    EntityRef,
    IntegerValue,
    PortRef,
)
from ucf.ir.trust_models import BehaviorDocumentRef

from .test_mapping_result_contract import _mapping_result


def _digest(value: str) -> Digest:
    return Digest(kind="digest", algorithm="sha-256", value=value * 64)


def _verification_request() -> ExecutionVerificationRequest:
    mapping = _mapping_result()
    binding = mapping.bindings[0]
    subject = next(
        entity
        for entity in mapping.request.behavior.entities
        if entity.id == binding.behavior.target_id
    )
    owner = EntityRef(
        kind="entity_ref",
        target_kind=binding.behavior.target_kind,
        target_id=binding.behavior.target_id,
    )
    input_values = {
        "quantity": 2,
        "unit-price-cents": 1250,
    }
    output_values = {"total-cents": 2500}
    return ExecutionVerificationRequest(
        kind="execution_verification_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=EXECUTION_VERIFICATION_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=EXECUTION_VERIFICATION_PROCEDURE_URI,
        adapter_procedure_uri=(
            "urn:ucf:fixture-adapter:execute-quote-order:1.0.0"
        ),
        mapping=ImplementationMappingResultRef(
            kind="implementation_mapping_result_ref",
            schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
            schema_version=IMPLEMENTATION_EVIDENCE_VERSION,
            target_id=mapping.id,
            canonical_digest=canonical_implementation_evidence_digest(mapping),
        ),
        base_behavior=BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id=binding.behavior.document_id,
            ir_version=binding.behavior.ir_version,
            canonical_digest=binding.behavior.canonical_digest,
        ),
        subject=binding.behavior,
        inputs=tuple(
            ExecutionPortValue(
                kind="execution_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=owner,
                    direction="input",
                    name=port.name,
                ),
                value=IntegerValue(
                    kind="integer",
                    value=input_values[port.name],
                ),
            )
            for port in subject.input_ports
        ),
        expected_outputs=tuple(
            ExecutionPortValue(
                kind="execution_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=owner,
                    direction="output",
                    name=port.name,
                ),
                value=IntegerValue(
                    kind="integer",
                    value=output_values[port.name],
                ),
            )
            for port in subject.output_ports
        ),
        source=ImplementationSource(
            kind="implementation_source",
            subject_uri=mapping.request.inventory.subject_uri,
            source_revision=mapping.request.inventory.source_revision,
            records=binding.source_records,
        ),
        environment=ExecutionEnvironment(
            kind="execution_environment",
            identity_uri=(
                "urn:ucf:fixture-environment:node22-linux-loopback:1.0.0"
            ),
            revision=_digest("e"),
        ),
        check=Check(
            kind="check",
            id="check.quote-order.real-http",
            version="1.0.0",
            procedure_uri=(
                "urn:ucf:fixture-check:quote-order-http-contract:1.0.0"
            ),
        ),
    )


def test_verification_request_serializes_every_reproducible_coordinate() -> None:
    request = _verification_request()
    encoded = canonical_implementation_evidence_json(request)

    assert parse_execution_verification_request_json(encoded) == request
    assert (
        canonical_implementation_evidence_json(
            parse_execution_verification_request_json(encoded)
        )
        == encoded
    )
    payload = request.model_dump(mode="json")
    assert payload["subject"]["target_id"]
    assert payload["inputs"]
    assert payload["expected_outputs"]
    assert payload["mapping"]["target_id"].startswith("mapping.")
    assert payload["source"]["source_revision"]
    assert payload["environment"]["revision"]
    assert payload["check"]["procedure_uri"]


def test_distinct_caller_values_have_distinct_wire_identity() -> None:
    first = _verification_request()
    changed_value = first.inputs[0].model_copy(
        update={"value": IntegerValue(kind="integer", value=3)}
    )
    second = first.model_copy(
        update={"inputs": (changed_value, *first.inputs[1:])}
    )

    assert canonical_implementation_evidence_json(first) != (
        canonical_implementation_evidence_json(second)
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("implementation_evidence_version",), "2.0.0"),
        (
            ("schema_uri",),
            "urn:ucf:adapter:execution-verification-request:2.0.0",
        ),
        (("capability", "name"), "org.ucf.adapter.mapping"),
        (("capability", "version"), "2.0.0"),
        (
            ("profile_procedure_uri",),
            "urn:ucf:implementation-evidence:verify:2.0.0",
        ),
        (("adapter_procedure_uri",), "https://example.test/check"),
        (("check", "procedure_uri"), "not-versioned"),
        (("environment", "identity_uri"), "file:///tmp/environment"),
        (
            ("mapping", "schema_uri"),
            "urn:ucf:adapter:implementation-mapping-result:2.0.0",
        ),
        (("mapping", "target_id"), f"result.{'a' * 64}"),
    ],
)
def test_verification_request_rejects_incompatible_coordinates(
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = _verification_request().model_dump(mode="json")
    target = payload
    for coordinate in path[:-1]:
        target = target[coordinate]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        parse_execution_verification_request_json(json.dumps(payload))


def test_verification_request_rejects_unknown_duplicate_and_unbound_data() -> None:
    payload = _verification_request().model_dump(mode="json")
    payload["transport"] = {"method": "POST", "path": "/quote-order"}
    with pytest.raises(ValidationError):
        parse_execution_verification_request_json(json.dumps(payload))

    encoded = canonical_implementation_evidence_json(
        _verification_request()
    )
    duplicate_member = encoded.replace(
        b'{"adapter_procedure_uri":',
        b'{"adapter_procedure_uri":"duplicate",'
        b'"adapter_procedure_uri":',
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_execution_verification_request_json(duplicate_member)

    duplicate_source = _verification_request().model_dump(mode="json")
    duplicate_source["source"]["records"].append(
        duplicate_source["source"]["records"][0]
    )
    with pytest.raises(ValidationError, match="duplicate"):
        parse_execution_verification_request_json(
            json.dumps(duplicate_source)
        )

    empty_source = _verification_request().model_dump(mode="json")
    empty_source["source"]["records"] = []
    with pytest.raises(ValidationError):
        parse_execution_verification_request_json(json.dumps(empty_source))

    stale_subject = _verification_request().model_dump(mode="json")
    stale_subject["subject"]["canonical_digest"]["value"] = "f" * 64
    with pytest.raises(ValidationError, match="base behavior"):
        parse_execution_verification_request_json(
            json.dumps(stale_subject)
        )


@pytest.mark.parametrize("mutation", ["duplicate", "noncanonical"])
def test_verification_request_rejects_noncanonical_nested_ir_values(
    mutation: str,
) -> None:
    payload = _verification_request().model_dump(mode="json")
    entries = [
        {
            "kind": "record_entry",
            "name": "zulu",
            "value": {"kind": "integer", "value": 1},
        },
        {
            "kind": "record_entry",
            "name": "alpha" if mutation == "noncanonical" else "zulu",
            "value": {"kind": "integer", "value": 2},
        },
    ]
    payload["inputs"][0]["value"] = {
        "kind": "record",
        "entries": entries,
    }

    with pytest.raises(ValidationError):
        parse_execution_verification_request_json(json.dumps(payload))
