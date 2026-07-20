from __future__ import annotations

import json
import re

from jsonschema import Draft202012Validator
from tools.generate_generation_schema import build_schemas, render_schemas

from ucf.generation import (
    GENERATION_REQUEST_SCHEMA_URI,
    GENERATION_RESULT_SCHEMA_URI,
)

from ._support import generation_request, generation_result


def _documents():
    request = generation_request()
    return {
        GENERATION_REQUEST_SCHEMA_URI: (request,),
        GENERATION_RESULT_SCHEMA_URI: (
            generation_result(request=request),
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


def test_published_generation_schemas_are_current_closed_and_exact() -> None:
    built = build_schemas()
    rendered = render_schemas()
    documents = _documents()

    assert {schema["$id"] for schema in built.values()} == set(documents)
    assert len(built) == 2
    for path, schema in built.items():
        assert path.read_text(encoding="utf-8") == rendered[path]
        assert json.loads(path.read_text(encoding="utf-8")) == schema
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["x-ucf-generation-version"] == "1.0.0"
        assert schema["x-ucf-generation-semantic-checks"]
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


def test_each_generation_document_validates_only_against_its_schema() -> None:
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


def test_generation_schemas_contain_no_ecosystem_or_transport_semantics() -> None:
    serialized = json.dumps(
        list(build_schemas().values()),
        sort_keys=True,
    ).lower()

    for prohibited in (
        r"\bpython\b",
        r"\bpytest\b",
        r"\btypescript\b",
        r"\bjava\b",
        r"\bspring\b",
        r"\bframework\b",
        r"\bhttp\b",
        r"\bcli\b",
        r"\bevent\b",
    ):
        assert re.search(prohibited, serialized) is None
