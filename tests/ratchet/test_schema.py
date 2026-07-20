from __future__ import annotations

import copy
import json
import re

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError
from tools.generate_ratchet_schema import build_schemas, render_schemas

from ucf.ir import IRValidationError
from ucf.ratchet import (
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_POLICY_SCHEMA_URI,
    canonical_ratchet_json,
    establish_ratchet_baseline,
    evaluate_ratchet,
    parse_ratchet_assessment_json,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
    parse_ratchet_policy_json,
)

from .test_assessment import _assessment
from .test_evaluation import _current


def _documents():
    policy, bundle, assessment = _assessment()
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    current = _current(policy, bundle, "required-check")
    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
    )
    return {
        RATCHET_POLICY_SCHEMA_URI: policy,
        RATCHET_ASSESSMENT_SCHEMA_URI: assessment,
        RATCHET_BASELINE_SCHEMA_URI: baseline,
        RATCHET_EVALUATION_REPORT_SCHEMA_URI: report,
    }


def _parsers():
    return {
        RATCHET_POLICY_SCHEMA_URI: parse_ratchet_policy_json,
        RATCHET_ASSESSMENT_SCHEMA_URI: parse_ratchet_assessment_json,
        RATCHET_BASELINE_SCHEMA_URI: parse_ratchet_baseline_json,
        RATCHET_EVALUATION_REPORT_SCHEMA_URI: (
            parse_ratchet_evaluation_report_json
        ),
    }


def _schema_by_uri() -> dict[str, dict]:
    return {
        schema["$id"]: schema for schema in build_schemas().values()
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


def test_published_ratchet_schemas_are_current_closed_and_exact() -> None:
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
        assert schema["x-ucf-ratchet-version"] == "1.0.0"
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


def test_each_ratchet_document_validates_only_against_its_schema() -> None:
    documents = _documents()
    schemas = _schema_by_uri()

    for document_uri, document in documents.items():
        accepted = []
        for schema_uri, schema in schemas.items():
            if Draft202012Validator(schema).is_valid(
                document.model_dump(mode="json")
            ):
                accepted.append(schema_uri)
        assert accepted == [document_uri]


@pytest.mark.parametrize(
    ("schema_uri", "nested_path"),
    [
        (RATCHET_POLICY_SCHEMA_URI, ("evaluator",)),
        (
            RATCHET_ASSESSMENT_SCHEMA_URI,
            ("subjects", 0, "semantic"),
        ),
        (RATCHET_BASELINE_SCHEMA_URI, ("source_assessment",)),
        (
            RATCHET_EVALUATION_REPORT_SCHEMA_URI,
            ("weakening_delta",),
        ),
    ],
)
def test_schema_and_runtime_reject_unknown_nested_fields(
    schema_uri: str,
    nested_path: tuple[str | int, ...],
) -> None:
    document = _documents()[schema_uri]
    payload = copy.deepcopy(document.model_dump(mode="json"))
    target = payload
    for coordinate in nested_path:
        target = target[coordinate]
    target["future"] = True

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(_schema_by_uri()[schema_uri]).validate(
            payload
        )
    with pytest.raises(ValidationError):
        _parsers()[schema_uri](json.dumps(payload))


@pytest.mark.parametrize(
    "schema_uri",
    [
        RATCHET_POLICY_SCHEMA_URI,
        RATCHET_ASSESSMENT_SCHEMA_URI,
        RATCHET_BASELINE_SCHEMA_URI,
        RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    ],
)
def test_every_ratchet_parser_rejects_duplicate_raw_members(
    schema_uri: str,
) -> None:
    document = _documents()[schema_uri]
    encoded = canonical_ratchet_json(document).decode("utf-8")
    duplicate = encoded.replace(
        f'"kind":"{document.kind}"',
        f'"kind":"{document.kind}","kind":"{document.kind}"',
        1,
    )

    with pytest.raises(IRValidationError):
        _parsers()[schema_uri](duplicate)


def test_baseline_generation_is_cross_runtime_safe() -> None:
    baseline = _documents()[RATCHET_BASELINE_SCHEMA_URI]
    schema = _schema_by_uri()[RATCHET_BASELINE_SCHEMA_URI]
    generation = schema["properties"]["generation"]
    if "$ref" in generation:
        generation = schema["$defs"][
            generation["$ref"].removeprefix("#/$defs/")
        ]

    assert generation["minimum"] == 0
    assert generation["maximum"] == 9_007_199_254_740_991
    payload = baseline.model_dump(mode="json")
    payload["generation"] = 9_007_199_254_740_992
    encoded = json.dumps(payload, separators=(",", ":"))

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(schema).validate(payload)
    with pytest.raises(IRValidationError):
        parse_ratchet_baseline_json(encoded)


def test_ratchet_schemas_contain_no_ecosystem_or_transport_semantics() -> None:
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
        r"\bhttp\b",
        r"\bcli\b",
        r"\bevent\b",
        r"\bdecorator\b",
        r"\bast\b",
    ):
        assert re.search(prohibited, serialized) is None
