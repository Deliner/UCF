from __future__ import annotations

import copy
import json
import re

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError
from tools.generate_onboarding_schema import (
    build_schemas,
    render_schemas,
)

from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    DISCOVERY_REQUEST_SCHEMA_URI,
    DISCOVERY_RESULT_SCHEMA_URI,
    ONBOARDING_BUNDLE_SCHEMA_URI,
)

from .test_bundle import _bundle
from .test_codec import _request
from .test_decisions import _decisions, _discovery


def _documents():
    discovery = _discovery()
    return {
        DISCOVERY_REQUEST_SCHEMA_URI: _request(),
        DISCOVERY_RESULT_SCHEMA_URI: discovery,
        DECISION_SET_SCHEMA_URI: _decisions(discovery),
        ONBOARDING_BUNDLE_SCHEMA_URI: _bundle(),
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


def test_published_onboarding_schemas_are_current_closed_and_exact():
    built = build_schemas()
    rendered = render_schemas()
    documents = _documents()

    assert set(schema["$id"] for schema in built.values()) == set(documents)
    for path, schema in built.items():
        assert path.read_text(encoding="utf-8") == rendered[path]
        assert json.loads(path.read_text(encoding="utf-8")) == schema
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["x-ucf-onboarding-version"] == "1.0.0"
        assert schema["x-ucf-runtime-semantic-checks"]
        Draft202012Validator.check_schema(schema)
        reachable, nodes = _reachable_nodes(schema)
        assert reachable == set(schema["$defs"])
        assert all(
            node.get("additionalProperties") is False
            for node in nodes
            if node.get("type") == "object"
        )
        Draft202012Validator(schema).validate(
            documents[schema["$id"]].model_dump(mode="json")
        )


@pytest.mark.parametrize(
    ("schema_uri", "nested_path"),
    [
        (DISCOVERY_REQUEST_SCHEMA_URI, ("inventory_binding",)),
        (DISCOVERY_RESULT_SCHEMA_URI, ("coverage",)),
        (DECISION_SET_SCHEMA_URI, ("capture_context",)),
        (ONBOARDING_BUNDLE_SCHEMA_URI, ("baseline",)),
    ],
)
def test_schema_and_runtime_reject_unknown_nested_fields(
    schema_uri: str,
    nested_path: tuple[str, ...],
):
    documents = _documents()
    document = documents[schema_uri]
    payload = copy.deepcopy(document.model_dump(mode="json"))
    target = payload
    for coordinate in nested_path:
        target = target[coordinate]
    target["future"] = True
    schema = next(
        schema
        for schema in build_schemas().values()
        if schema["$id"] == schema_uri
    )

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(payload)
    with pytest.raises(ValidationError):
        type(document).model_validate_json(json.dumps(payload))


def test_onboarding_schemas_contain_no_ecosystem_semantics():
    serialized = json.dumps(
        list(build_schemas().values()),
        sort_keys=True,
    ).lower()

    for prohibited in (
        r"\bpython\b",
        r"\btypescript\b",
        r"\bjava\b",
        r"\bspring\b",
        r"\bframework\b",
    ):
        assert re.search(prohibited, serialized) is None


def test_discovery_procedure_uri_schema_matches_runtime_version_constraint():
    document = _discovery()
    payload = document.model_dump(mode="json")
    payload["procedure_uri"] = "urn:ucf:onboarding-procedure:unversioned"
    schema = next(
        schema
        for schema in build_schemas().values()
        if schema["$id"] == DISCOVERY_RESULT_SCHEMA_URI
    )

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(payload)
    with pytest.raises(ValidationError):
        type(document).model_validate(payload)
