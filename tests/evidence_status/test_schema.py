from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
from tools.generate_evidence_status_schema import (
    build_schemas,
    render_schemas,
)

from ucf.evidence_status import (
    VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI,
    VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
)

from .test_contract import assessment, envelope

_SCHEMA_DIRECTORY = Path(
    "src/ucf/schemas/evidence_status/v1"
).resolve()


def _documents():
    return {
        VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI: (envelope(),),
        VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI: (
            assessment(status="fresh"),
            assessment(status="stale"),
            assessment(status="indeterminate"),
        ),
    }


def _reachable_nodes(schema: dict) -> tuple[set[str], list[dict]]:
    definitions = schema["$defs"]
    reachable: set[str] = set()
    visited: set[int] = set()
    nodes: list[dict] = []

    def visit(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict) or id(node) in visited:
            return
        visited.add(id(node))
        nodes.append(node)
        reference = node.get("$ref")
        if isinstance(reference, str):
            assert reference.startswith("#/$defs/")
            name = reference.removeprefix("#/$defs/")
            reachable.add(name)
            visit(definitions[name])
        for key, value in node.items():
            if key not in {"$defs", "$ref"}:
                visit(value)

    visit({key: value for key, value in schema.items() if key != "$defs"})
    return reachable, nodes


def test_published_schemas_are_current_closed_exact_and_reachable() -> None:
    built = build_schemas()
    rendered = render_schemas()
    documents = _documents()

    assert set(built) == {
        _SCHEMA_DIRECTORY / "envelope.schema.json",
        _SCHEMA_DIRECTORY / "assessment.schema.json",
    }
    assert set(rendered) == set(built)
    assert {schema["$id"] for schema in built.values()} == set(documents)
    for path, schema in built.items():
        assert path.read_text(encoding="utf-8") == rendered[path]
        assert json.loads(rendered[path]) == schema
        assert schema["$schema"] == ("https://json-schema.org/draft/2020-12/schema")
        assert schema["x-ucf-evidence-status-version"] == "1.0.0"
        assert schema["x-ucf-evidence-status-semantic-checks"]
        Draft202012Validator.check_schema(schema)
        reachable, nodes = _reachable_nodes(schema)
        assert reachable == set(schema["$defs"])
        assert all(
            node.get("additionalProperties") is False
            for node in nodes
            if node.get("type") == "object"
        )
        for document in documents[schema["$id"]]:
            Draft202012Validator(schema).validate(document.model_dump(mode="json"))


def test_each_document_validates_only_against_its_exact_schema() -> None:
    schemas = {schema["$id"]: schema for schema in build_schemas().values()}
    for document_uri, documents in _documents().items():
        for document in documents:
            accepted = [
                schema_uri
                for schema_uri, schema in schemas.items()
                if Draft202012Validator(schema).is_valid(
                    document.model_dump(mode="json")
                )
            ]
            assert accepted == [document_uri]


def test_schemas_reject_unknown_and_incompatible_nested_shapes() -> None:
    schemas = {schema["$id"]: schema for schema in build_schemas().values()}
    envelope_document = envelope().model_dump(mode="json")
    assessment_document = assessment().model_dump(mode="json")

    unknown = deepcopy(envelope_document)
    unknown["recorded"]["behavior"]["members"][0]["transport"] = "http"
    assert not Draft202012Validator(
        schemas[VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI]
    ).is_valid(unknown)

    incompatible = deepcopy(assessment_document)
    incompatible["evidence_status_version"] = "2.0.0"
    assert not Draft202012Validator(
        schemas[VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI]
    ).is_valid(incompatible)


def test_schema_annotations_name_runtime_only_checks_without_authenticity() -> None:
    schemas = list(build_schemas().values())
    annotations = {
        schema["x-ucf-document-kind"]: tuple(
            schema["x-ucf-evidence-status-semantic-checks"]
        )
        for schema in schemas
    }

    assert set(annotations) == {
        "verification_evidence_envelope",
        "verification_evidence_assessment",
    }
    assert any(
        "canonical unique projection members" in check
        for check in annotations["verification_evidence_envelope"]
    )
    assert any(
        "canonical unique reasons" in check
        for check in annotations["verification_evidence_assessment"]
    )
    assert any(
        "trace coordinates are not standalone stale predicates" in check
        for check in annotations["verification_evidence_envelope"]
    )
    assert all(
        prohibited not in check.lower()
        for checks in annotations.values()
        for check in checks
        for prohibited in (
            "authenticated",
            "signature",
            "non-repudiation",
            "formal verification",
        )
    )


def test_schemas_contain_no_language_framework_or_transport_semantics() -> None:
    serialized = json.dumps(
        list(build_schemas().values()),
        sort_keys=True,
    ).lower()

    for prohibited in (
        r"\bpython\b",
        r"\bpytest\b",
        r"\btypescript\b",
        r"\bjavascript\b",
        r"\bjava\b",
        r"\bspring\b",
        r"\bgo\b",
        r"\bframework\b",
        r"\bhttp\b",
        r"\bcli\b",
        r"\bevent\b",
        r"\btransport\b",
        r"\broute\b",
        r"\bmethod\b",
        r"\btopic\b",
    ):
        assert re.search(prohibited, serialized) is None
