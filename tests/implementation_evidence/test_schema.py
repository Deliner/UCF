from __future__ import annotations

import json
import re

from jsonschema import Draft202012Validator
from tools.generate_implementation_evidence_schema import (
    build_schemas,
    render_schemas,
)

from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
)

from .test_mapping_request_contract import _mapping_request
from .test_mapping_result_contract import _mapping_result
from .test_verification_request_contract import _verification_request
from .test_verification_result_contract import _verification_result


def _documents():
    return {
        IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI: (_mapping_request(),),
        IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI: (_mapping_result(),),
        EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI: (
            _verification_request(),
        ),
        EXECUTION_VERIFICATION_RESULT_SCHEMA_URI: (
            _verification_result("passed"),
            _verification_result("failed"),
            _verification_result("error"),
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


def test_published_implementation_evidence_schemas_are_current_closed_exact() -> None:
    built = build_schemas()
    rendered = render_schemas()
    documents = _documents()

    assert {schema["$id"] for schema in built.values()} == set(documents)
    assert len(built) == 4
    for path, schema in built.items():
        assert path.read_text(encoding="utf-8") == rendered[path]
        assert json.loads(path.read_text(encoding="utf-8")) == schema
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["x-ucf-implementation-evidence-version"] == "1.0.0"
        assert schema["x-ucf-runtime-semantic-checks"]
        Draft202012Validator.check_schema(schema)
        reachable, nodes = _reachable_nodes(schema)
        assert reachable == set(schema["$defs"])
        assert all(
            node.get("additionalProperties") is False
            for node in nodes
            if node.get("type") == "object"
        )
        for document in documents[schema["$id"]]:
            Draft202012Validator(schema).validate(
                document.model_dump(mode="json")
            )


def test_each_implementation_document_validates_only_against_its_schema() -> None:
    schemas = {
        schema["$id"]: schema for schema in build_schemas().values()
    }
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


def test_profiles_contain_no_language_framework_or_transport_semantics() -> None:
    serialized = json.dumps(
        list(build_schemas().values()),
        sort_keys=True,
    ).lower()

    for prohibited in (
        r"\bpython\b",
        r"\btypescript\b",
        r"\bjava\b",
        r"\bgo\b",
        r"\bfastify\b",
        r"\bexpress\b",
        r"\bframework\b",
        r"\bhttp\b",
        r"\bcli\b",
        r"\bevent\b",
        r"\bnpm\b",
        r"\bnode\b",
    ):
        assert re.search(prohibited, serialized) is None
