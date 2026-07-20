from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError
from tools.generate_inventory_schema import (
    DEFAULT_OUTPUT,
    PAGE_SCHEMA_OUTPUT,
    REQUEST_SCHEMA_OUTPUT,
    build_schema,
    build_schemas,
    render_schema,
    render_schemas,
)

from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_PAGE_SCHEMA_URI,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    InventoryPage,
    InventoryPageRequest,
    InventoryRequest,
    InventorySnapshot,
)

from .test_models import _policy, _snapshot
from .test_paging import _pages

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def published_schemas() -> dict[str, dict]:
    return {
        INVENTORY_SCHEMA_URI: json.loads(
            DEFAULT_OUTPUT.read_text(encoding="utf-8")
        ),
        INVENTORY_REQUEST_SCHEMA_URI: json.loads(
            REQUEST_SCHEMA_OUTPUT.read_text(encoding="utf-8")
        ),
        INVENTORY_PAGE_SCHEMA_URI: json.loads(
            PAGE_SCHEMA_OUTPUT.read_text(encoding="utf-8")
        ),
    }


def _request() -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=_policy(),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=256,
            cursor=None,
        ),
    )


def _reachable_schema_nodes(schema: dict) -> tuple[set[str], list[dict]]:
    definitions = schema["$defs"]
    reachable_definitions: set[str] = set()
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
        if reference is not None:
            assert isinstance(reference, str)
            assert reference.startswith("#/$defs/")
            name = reference.removeprefix("#/$defs/")
            assert name in definitions
            reachable_definitions.add(name)
            visit(definitions[name])
        for key, value in node.items():
            if key not in {"$defs", "$ref"}:
                visit(value)

    visit({key: value for key, value in schema.items() if key != "$defs"})
    return reachable_definitions, nodes


def test_published_inventory_schemas_are_current_closed_and_exact(
    published_schemas,
):
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_schema()
    assert json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8")) == (
        build_schema()
    )
    built_by_uri = {
        schema["$id"]: schema for schema in build_schemas().values()
    }
    assert published_schemas == built_by_uri
    for path, rendered in render_schemas().items():
        assert path.read_text(encoding="utf-8") == rendered

    for schema_uri, schema in published_schemas.items():
        assert schema["$id"] == schema_uri
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["x-ucf-inventory-version"] == "1.0.0"
        Draft202012Validator.check_schema(schema)

        reachable, nodes = _reachable_schema_nodes(schema)
        assert reachable == set(schema["$defs"])
        object_nodes = [
            node for node in nodes if node.get("type") == "object"
        ]
        assert object_nodes
        assert all(
            node.get("additionalProperties") is False
            for node in object_nodes
        )


@pytest.mark.parametrize(
    ("document_kind", "nested_path"),
    [
        ("request", ("ignore_policy", "rules", 0, "matcher")),
        ("page", ("request_cursor",)),
        ("snapshot", ("records", 0, "producer")),
    ],
)
def test_schema_and_runtime_reject_unknown_fields_at_nested_boundaries(
    published_schemas,
    document_kind: str,
    nested_path: tuple[object, ...],
):
    if document_kind == "request":
        model = InventoryRequest
        payload = _request().model_dump(mode="json")
        schema_uri = INVENTORY_REQUEST_SCHEMA_URI
    elif document_kind == "page":
        model = InventoryPage
        payload = _pages()[1].model_dump(mode="json")
        schema_uri = INVENTORY_PAGE_SCHEMA_URI
    else:
        model = InventorySnapshot
        payload = _snapshot().model_dump(mode="json")
        schema_uri = INVENTORY_SCHEMA_URI

    target = payload
    for coordinate in nested_path:
        target = target[coordinate]
    target["future"] = True

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(published_schemas[schema_uri]).validate(payload)
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(payload))


def test_content_identity_and_cross_record_checks_are_runtime_only(
    published_schemas,
):
    payload = _snapshot().model_dump(mode="json")
    payload["source_revision"]["value"] = "f" * 64

    snapshot_schema = published_schemas[INVENTORY_SCHEMA_URI]
    Draft202012Validator(snapshot_schema).validate(payload)
    with pytest.raises(ValidationError, match="source revision"):
        InventorySnapshot.model_validate_json(json.dumps(payload))
    assert "content-derived source revision" in (
        snapshot_schema["x-ucf-runtime-semantic-checks"]
    )


def test_inventory_schemas_contain_no_ecosystem_semantics(published_schemas):
    serialized = json.dumps(published_schemas, sort_keys=True).lower()

    for prohibited_pattern in (
        r"\bpython\b",
        r"\btypescript\b",
        r"\bjava\b",
        r"\bspring\b",
        r"\bpytest\b",
        r"\bframework\b",
    ):
        assert re.search(prohibited_pattern, serialized) is None


def test_inventory_schema_generation_is_hash_seed_independent(tmp_path):
    generated: list[dict[str, bytes]] = []
    for seed in ("1", "42"):
        output_directory = tmp_path / f"schemas-{seed}"
        result = subprocess.run(
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "tools"
                        / "generate_inventory_schema.py"
                    ),
                "--output-directory",
                str(output_directory),
            ],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        generated.append(
            {
                path.name: path.read_bytes()
                for path in sorted(output_directory.iterdir())
            }
        )

    expected = {
        path.name: path.read_bytes()
        for path in (
            DEFAULT_OUTPUT,
            PAGE_SCHEMA_OUTPUT,
            REQUEST_SCHEMA_OUTPUT,
        )
    }
    assert generated[0] == generated[1] == expected


def test_schema_rejects_wrong_branch_coordinates(published_schemas):
    payload = copy.deepcopy(_request().model_dump(mode="json"))
    payload["schema_uri"] = INVENTORY_PAGE_SCHEMA_URI

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(
            published_schemas[INVENTORY_REQUEST_SCHEMA_URI]
        ).validate(payload)
    with pytest.raises(ValidationError):
        InventoryRequest.model_validate_json(json.dumps(payload))


def test_each_public_profile_uri_has_one_exact_schema_resource(
    published_schemas,
):
    documents = {
        INVENTORY_SCHEMA_URI: _snapshot(),
        INVENTORY_REQUEST_SCHEMA_URI: _request(),
        INVENTORY_PAGE_SCHEMA_URI: _pages()[0],
    }

    assert set(published_schemas) == set(documents)
    for schema_uri, schema in published_schemas.items():
        assert schema["$id"] == schema_uri
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(documents[schema_uri].model_dump(mode="json"))
        for other_uri, other_document in documents.items():
            if other_uri != schema_uri:
                with pytest.raises(JsonSchemaValidationError):
                    validator.validate(
                        other_document.model_dump(mode="json")
                    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("name", "org.ucf.adapter.other"),
        ("version", "2.0.0"),
    ),
)
def test_page_schema_rejects_unsupported_inventory_capability(
    published_schemas,
    field: str,
    invalid_value: str,
):
    payload = _pages()[0].model_dump(mode="json")
    payload["capability"][field] = invalid_value

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(
            published_schemas[INVENTORY_PAGE_SCHEMA_URI]
        ).validate(payload)
    assert payload["capability"]["name"] != INVENTORY_CAPABILITY or (
        payload["capability"]["version"] != INVENTORY_VERSION
    )


@pytest.mark.parametrize("field", ("basis", "procedure_uri"))
def test_snapshot_schema_rejects_unversioned_evidence_uri(
    published_schemas,
    field: str,
):
    payload = _snapshot().model_dump(mode="json")
    if field == "basis":
        fact = next(
            record
            for record in payload["records"]
            if "confidence" in record
        )
        fact["confidence"]["basis"] = "urn:ucf:inventory:basis"
    else:
        provenance = next(
            record
            for record in payload["records"]
            if record["kind"] == "inventory_provenance"
        )
        provenance["procedure_uri"] = "urn:ucf:inventory:procedure"

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(
            published_schemas[INVENTORY_SCHEMA_URI]
        ).validate(payload)


@pytest.mark.parametrize(
    "mutation",
    (
        "file-subject",
        "absolute-root",
        "reversed-fact-kinds",
        "reserved-ignore-segment",
        "duplicate-ignore-rule",
        "terminal-page-with-cursor",
        "cursor-kind-id-mismatch",
        "reversed-coverage",
        "directory-with-size",
        "provenance-span-without-digest",
    ),
)
def test_schema_and_runtime_reject_the_same_local_profile_invariants(
    published_schemas,
    mutation: str,
):
    if mutation in {
        "file-subject",
        "absolute-root",
        "reversed-fact-kinds",
        "reserved-ignore-segment",
        "duplicate-ignore-rule",
    }:
        model = InventoryRequest
        schema_uri = INVENTORY_REQUEST_SCHEMA_URI
        payload = _request().model_dump(mode="json")
        if mutation == "file-subject":
            payload["subject_uri"] = "file:///private/repository"
        elif mutation == "absolute-root":
            payload["root_path"] = "C:/source"
        elif mutation == "reversed-fact-kinds":
            payload["fact_kinds"].reverse()
        elif mutation == "reserved-ignore-segment":
            payload["ignore_policy"]["rules"][0]["matcher"]["segment"] = "CON"
        else:
            payload["ignore_policy"]["rules"].append(
                copy.deepcopy(payload["ignore_policy"]["rules"][0])
            )
    elif mutation in {
        "terminal-page-with-cursor",
        "cursor-kind-id-mismatch",
        "reversed-coverage",
    }:
        model = InventoryPage
        schema_uri = INVENTORY_PAGE_SCHEMA_URI
        payload = _pages()[0].model_dump(mode="json")
        if mutation == "terminal-page-with-cursor":
            payload["complete"] = True
        elif mutation == "cursor-kind-id-mismatch":
            payload["next_cursor"]["after_kind"] = "api_description"
        else:
            payload["coverage"].reverse()
    else:
        model = InventorySnapshot
        schema_uri = INVENTORY_SCHEMA_URI
        payload = _snapshot().model_dump(mode="json")
        if mutation == "directory-with-size":
            directory = next(
                record
                for record in payload["records"]
                if record["kind"] == "repository_entry"
                and record["entry_kind"] == "directory"
            )
            directory["size_bytes"] = 0
        else:
            provenance = next(
                record
                for record in payload["records"]
                if record["kind"] == "inventory_provenance"
                and record["content_digest"] is None
            )
            provenance["source_span"] = {
                "kind": "source_span",
                "start_line": 1,
                "start_column": 1,
                "end_line": 1,
                "end_column": 1,
            }

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(
            published_schemas[schema_uri]
        ).validate(payload)
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_unexpressible_local_invariants_name_normative_algorithms(
    published_schemas,
):
    expected_algorithms = {
        "urn:ucf:inventory-algorithm:cursor-coordinate:1.0.0",
        "urn:ucf:inventory-algorithm:ignore-policy:1.0.0",
        "urn:ucf:inventory-algorithm:page-terminal:1.0.0",
        "urn:ucf:inventory-algorithm:portable-path:1.0.0",
        "urn:ucf:inventory-algorithm:source-span-order:1.0.0",
    }
    for schema in published_schemas.values():
        assert set(schema["x-ucf-normative-algorithms"]) == (
            expected_algorithms
        )

    request_schema = published_schemas[INVENTORY_REQUEST_SCHEMA_URI]
    repository_path = request_schema["$defs"]["RepositoryPath"]
    ignore_rules = request_schema["$defs"]["IgnorePolicy"][
        "properties"
    ]["rules"]
    assert repository_path["x-ucf-normalization"] == "unicode-nfc"
    assert repository_path["x-ucf-validation-algorithm"].endswith(
        "portable-path:1.0.0"
    )
    assert ignore_rules["x-ucf-canonical-order-by"] == ["id"]
    assert "id" in ignore_rules["x-ucf-unique-by"]

    decomposed = _request().model_dump(mode="json")
    decomposed["root_path"] = "e\u0301.py"
    Draft202012Validator(request_schema).validate(decomposed)
    with pytest.raises(ValidationError):
        InventoryRequest.model_validate(decomposed)

    snapshot_schema = published_schemas[INVENTORY_SCHEMA_URI]
    source_span = snapshot_schema["$defs"]["SourceSpan"]
    assert source_span["x-ucf-validation-algorithm"].endswith(
        "source-span-order:1.0.0"
    )
    reversed_span = _snapshot().model_dump(mode="json")
    provenance = next(
        record
        for record in reversed_span["records"]
        if record["kind"] == "inventory_provenance"
        and record["content_digest"] is not None
    )
    provenance["source_span"] = {
        "kind": "source_span",
        "start_line": 2,
        "start_column": 1,
        "end_line": 1,
        "end_column": 1,
    }
    Draft202012Validator(snapshot_schema).validate(reversed_span)
    with pytest.raises(ValidationError):
        InventorySnapshot.model_validate(reversed_span)
