from __future__ import annotations

import copy
import json
import re

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError
from tools.generate_ratchet_v2_schema import build_schemas, render_schemas

from ucf.ir import IRValidationError
from ucf.ratchet.v2 import (
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetErrorCode,
    RatchetValidationError,
    canonical_ratchet_json,
    establish_ratchet_baseline,
    evaluate_ratchet,
    parse_ratchet_assessment_json,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
    parse_ratchet_policy_json,
)
from ucf.ratchet.v2.models import MAX_RATCHET_RULES

from .test_assessment import _assessment, _uncovered_bundle
from .test_policy import _policy


def _documents():
    policy = _policy()
    bundle = _uncovered_bundle()
    assessment = _assessment(bundle)
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        assessment,
        accepted_baseline_id=baseline.id,
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


def _schemas_by_uri():
    return {schema["$id"]: schema for schema in build_schemas().values()}


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


def test_published_v2_schemas_are_current_closed_and_exact() -> None:
    built = build_schemas()
    rendered = render_schemas()
    documents = _documents()

    assert len(built) == 4
    assert {schema["$id"] for schema in built.values()} == set(documents)
    for path, schema in built.items():
        assert path.read_text(encoding="utf-8") == rendered[path]
        assert json.loads(path.read_text(encoding="utf-8")) == schema
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["x-ucf-ratchet-version"] == "2.0.0"
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


def test_each_v2_document_validates_only_against_its_schema() -> None:
    documents = _documents()
    schemas = _schemas_by_uri()

    for document_uri, document in documents.items():
        accepted = [
            schema_uri
            for schema_uri, schema in schemas.items()
            if Draft202012Validator(schema).is_valid(
                document.model_dump(mode="json")
            )
        ]
        assert accepted == [document_uri]


@pytest.mark.parametrize(
    ("schema_uri", "nested_path"),
    [
        (RATCHET_POLICY_SCHEMA_URI, ("evaluator",)),
        (RATCHET_ASSESSMENT_SCHEMA_URI, ("coverage", "qualification")),
        (RATCHET_BASELINE_SCHEMA_URI, ("coverage",)),
        (RATCHET_EVALUATION_REPORT_SCHEMA_URI, ("coverage_delta",)),
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
        Draft202012Validator(_schemas_by_uri()[schema_uri]).validate(payload)
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
def test_every_v2_parser_rejects_duplicate_raw_members(schema_uri: str) -> None:
    document = _documents()[schema_uri]
    encoded = canonical_ratchet_json(document).decode("utf-8")
    duplicate = encoded.replace(
        f'"kind":"{document.kind}"',
        f'"kind":"{document.kind}","kind":"{document.kind}"',
        1,
    )

    with pytest.raises(IRValidationError):
        _parsers()[schema_uri](duplicate)


@pytest.mark.parametrize("schema_uri", list(_documents()))
@pytest.mark.parametrize("ratchet_version", [None, "1.0.0", "3.0.0"])
def test_every_v2_parser_explicitly_rejects_incompatible_versions(
    schema_uri: str,
    ratchet_version: str | None,
) -> None:
    payload = _documents()[schema_uri].model_dump(mode="json")
    if ratchet_version is None:
        del payload["ratchet_version"]
    else:
        payload["ratchet_version"] = ratchet_version

    with pytest.raises(RatchetValidationError) as captured:
        _parsers()[schema_uri](json.dumps(payload))

    assert captured.value.code is RatchetErrorCode.UNSUPPORTED_RATCHET_VERSION
    assert captured.value.location == "$.ratchet_version"


@pytest.mark.parametrize("schema_uri", list(_documents()))
@pytest.mark.parametrize("coordinate", ["kind", "schema_uri"])
def test_every_v2_parser_explicitly_rejects_cross_kind_coordinates(
    schema_uri: str,
    coordinate: str,
) -> None:
    documents = _documents()
    payload = documents[schema_uri].model_dump(mode="json")
    other_uri = next(uri for uri in documents if uri != schema_uri)
    payload[coordinate] = documents[other_uri].model_dump(mode="json")[
        coordinate
    ]

    with pytest.raises(RatchetValidationError) as captured:
        _parsers()[schema_uri](json.dumps(payload))

    assert captured.value.code is RatchetErrorCode.WRONG_TARGET_KIND
    assert captured.value.location == f"$.{coordinate}"


@pytest.mark.parametrize(
    ("coordinate", "unsupported"),
    [
        ("name", "org.example.unsupported"),
        ("version", "3.0.0"),
    ],
)
def test_policy_schema_and_runtime_reject_unsupported_evaluator(
    coordinate: str,
    unsupported: str,
) -> None:
    payload = _policy().model_dump(mode="json")
    payload["evaluator"][coordinate] = unsupported

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(
            _schemas_by_uri()[RATCHET_POLICY_SCHEMA_URI]
        ).validate(payload)
    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_policy_json(json.dumps(payload))

    assert captured.value.code is RatchetErrorCode.UNSUPPORTED_CAPABILITY
    assert captured.value.location == f"$.evaluator.{coordinate}"
    assert RATCHET_EVALUATOR_CAPABILITY in str(captured.value)
    assert RATCHET_VERSION in str(captured.value)


def test_policy_parser_reports_collection_limit_with_stable_error() -> None:
    payload = _policy().model_dump(mode="json")
    payload["rules"] = payload["rules"] * (MAX_RATCHET_RULES + 1)

    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_policy_json(json.dumps(payload))

    assert captured.value.code is RatchetErrorCode.RESOURCE_LIMIT_EXCEEDED
    assert captured.value.location == "$.rules"


def test_v2_schemas_have_no_ecosystem_or_transport_semantics() -> None:
    serialized = json.dumps(list(build_schemas().values()), sort_keys=True).lower()

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
