from __future__ import annotations

import hashlib
from pathlib import Path

from ucf.adapter_protocol import CapabilitySelection
from ucf.generation import (
    GENERATION_CAPABILITY,
    GENERATION_PROFILE_PROCEDURE_URI,
    GENERATION_PROFILE_VERSION,
    GENERATION_REQUEST_SCHEMA_URI,
    GENERATION_RESULT_SCHEMA_URI,
    GeneratedFile,
    GenerationEnvironment,
    GenerationPortValue,
    GenerationRequest,
    GenerationResult,
    GenerationVerification,
    derive_generation_request_id,
    derive_generation_result_id,
)
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import (
    Digest,
    EntityKind,
    EntityRef,
    PortRef,
    Producer,
    RecordEntry,
    RecordValue,
    StringValue,
)
from ucf.ir.trust_models import BehaviorEntityRef

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ir" / "v1"
PYTHON_PROFILE_CAPABILITY = "org.ucf.adapter.generation.python-pytest"
PYTHON_PROCEDURE_URI = "urn:ucf:python-pytest:function-test:1.0.0"


def _digest(value: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(value).hexdigest(),
    )


def behavior():
    parsed = parse_ir_json((FIXTURES / "complete.json").read_bytes())
    return parse_ir_json(canonical_ir_json(parsed))


def generation_request() -> GenerationRequest:
    document = behavior()
    behavior_digest = _digest(canonical_ir_json(document).encode("ascii"))
    action_ref = EntityRef(
        kind="entity_ref",
        target_kind=EntityKind.ACTION,
        target_id="action.reserve-item",
    )
    request = GenerationRequest(
        kind="generation_request",
        generation_version=GENERATION_PROFILE_VERSION,
        schema_uri=GENERATION_REQUEST_SCHEMA_URI,
        id=f"generation-request.{'0' * 64}",
        capability=CapabilitySelection(
            kind="capability",
            name=GENERATION_CAPABILITY,
            version=GENERATION_PROFILE_VERSION,
        ),
        profile_capability=CapabilitySelection(
            kind="capability",
            name=PYTHON_PROFILE_CAPABILITY,
            version=GENERATION_PROFILE_VERSION,
        ),
        profile_procedure_uri=GENERATION_PROFILE_PROCEDURE_URI,
        adapter_procedure_uri=PYTHON_PROCEDURE_URI,
        behavior=document,
        subject=BehaviorEntityRef(
            kind="behavior_entity_ref",
            document_id=document.document_id,
            ir_version=document.ir_version,
            canonical_digest=behavior_digest,
            target_kind=EntityKind.ACTION,
            target_id=action_ref.target_id,
        ),
        inputs=(
            GenerationPortValue(
                kind="generation_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=action_ref,
                    direction="input",
                    name="item-id",
                ),
                value=StringValue(kind="string", value="sku-123"),
            ),
        ),
        expected_outputs=(
            GenerationPortValue(
                kind="generation_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=action_ref,
                    direction="output",
                    name="reservation-id",
                ),
                value=StringValue(kind="string", value="reservation-456"),
            ),
        ),
        environment=GenerationEnvironment(
            kind="generation_environment",
            identity_uri="urn:ucf:environment:python-3.12-pytest-9:1.0.0",
            revision=_digest(b"python=3.12.3\npytest=9.1.1\n"),
        ),
        profile_configuration=RecordValue(
            kind="record",
            entries=(
                RecordEntry(
                    kind="record_entry",
                    name="callable",
                    value=StringValue(kind="string", value="reserve_item"),
                ),
                RecordEntry(
                    kind="record_entry",
                    name="module",
                    value=StringValue(kind="string", value="legacy_inventory"),
                ),
                RecordEntry(
                    kind="record_entry",
                    name="parameters",
                    value=RecordValue(
                        kind="record",
                        entries=(
                            RecordEntry(
                                kind="record_entry",
                                name="item-id",
                                value=StringValue(
                                    kind="string",
                                    value="item_id",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    return request.model_copy(
        update={"id": derive_generation_request_id(request)}
    )


def generation_result(
    *,
    request: GenerationRequest | None = None,
) -> GenerationResult:
    request = request or generation_request()
    content = (
        '"""Generated contract test. DO NOT EDIT."""\n'
        "\n"
        "def test_reserve_item_contract() -> None:\n"
        "    assert True\n"
    )
    result = GenerationResult(
        kind="generation_result",
        generation_version=GENERATION_PROFILE_VERSION,
        schema_uri=GENERATION_RESULT_SCHEMA_URI,
        id=f"generation-result.{'0' * 64}",
        status="complete",
        request=request,
        producer=Producer(
            kind="producer",
            name="org.ucf.adapter.python-pytest",
            version=GENERATION_PROFILE_VERSION,
        ),
        capability=request.capability,
        profile_capability=request.profile_capability,
        procedure_uri=request.adapter_procedure_uri,
        files=(
            GeneratedFile(
                kind="generated_file",
                path="test_reserve_item.py",
                ownership="generator_owned",
                media_type="text/x-python",
                encoding="utf-8",
                byte_size=len(content.encode("utf-8")),
                content_digest=_digest(content.encode("utf-8")),
                content=content,
            ),
        ),
        verification=GenerationVerification(
            kind="generation_verification",
            procedure_uri=(
                "urn:ucf:python-pytest:execute-generated-test:1.0.0"
            ),
            working_directory="implementation_root",
            argv=(
                "python3",
                "-m",
                "pytest",
                "-q",
                "{generated_root}",
            ),
        ),
    )
    return result.model_copy(
        update={"id": derive_generation_result_id(result)}
    )
