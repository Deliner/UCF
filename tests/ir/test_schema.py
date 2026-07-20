from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from tools.generate_ir_schema import (
    DEFAULT_OUTPUT,
    SCHEMA_ID,
    build_schema,
    render_schema,
)

from ucf.ir import IRErrorCode, IRValidationError, parse_ir_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "ir" / "v1"
INVALID = FIXTURES / "invalid"


@pytest.fixture(scope="module")
def published_schema() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def test_published_ir_schema_is_current_closed_and_valid(published_schema):
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_schema()
    assert published_schema == build_schema()
    assert published_schema["$id"] == SCHEMA_ID
    assert published_schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert published_schema["x-ucf-ir-version"] == "1.0.0"
    assert published_schema["additionalProperties"] is False
    assert (
        published_schema["properties"]["ir_version"]["const"] == "1.0.0"
    )
    assert "maximum JSON nesting depth 128" in (
        published_schema["x-ucf-runtime-semantic-checks"]
    )
    Draft202012Validator.check_schema(published_schema)


@pytest.mark.parametrize("fixture_name", ["minimal.json", "complete.json"])
def test_independent_schema_evaluator_accepts_golden_fixtures(
    published_schema,
    fixture_name,
):
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))

    Draft202012Validator(published_schema).validate(payload)
    parse_ir_json((FIXTURES / fixture_name).read_bytes())


@pytest.mark.parametrize(
    "fixture_name",
    [
        "unknown-root-field.json",
        "unsupported-version.json",
        "unknown-entity-kind.json",
    ],
)
def test_runtime_and_schema_reject_shared_structural_negatives(
    published_schema,
    fixture_name,
):
    payload = json.loads((INVALID / fixture_name).read_text(encoding="utf-8"))

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(published_schema).validate(payload)
    with pytest.raises(IRValidationError):
        parse_ir_json((INVALID / fixture_name).read_bytes())


def test_semantic_reference_checks_are_truthfully_runtime_only(published_schema):
    payload = json.loads(
        (INVALID / "broken-reference.json").read_text(encoding="utf-8")
    )

    Draft202012Validator(published_schema).validate(payload)
    with pytest.raises(IRValidationError) as captured:
        parse_ir_json((INVALID / "broken-reference.json").read_bytes())

    assert captured.value.code is IRErrorCode.BROKEN_REFERENCE


def test_raw_duplicate_members_are_rejected_before_schema_evaluation():
    with pytest.raises(IRValidationError) as captured:
        parse_ir_json((INVALID / "duplicate-member.json").read_bytes())

    assert captured.value.code is IRErrorCode.DUPLICATE_JSON_MEMBER


def test_schema_contains_no_raw_fractional_number_type_or_platform_terms(
    published_schema,
):
    serialized = json.dumps(published_schema, sort_keys=True).lower()

    assert '"type": "number"' not in serialized
    fixture_text = (FIXTURES / "complete.json").read_text(encoding="utf-8").lower()
    for prohibited_pattern in (
        r"\bpython\b",
        r"\bpytest\b",
        r"\bmodule\b",
        r"\bdecorator\b",
        r"\bast\b",
        r"\bframework\b",
        r"\bbuild[ _-]?tool\b",
        r"\btransport\b",
    ):
        assert re.search(prohibited_pattern, serialized) is None
        assert re.search(prohibited_pattern, fixture_text) is None


def test_ir_schema_generation_is_hash_seed_independent(tmp_path):
    generated: list[bytes] = []
    for seed in ("1", "42"):
        output = tmp_path / f"schema-{seed}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "generate_ir_schema.py"),
                "--output",
                str(output),
            ],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        generated.append(output.read_bytes())

    assert generated[0] == generated[1] == DEFAULT_OUTPUT.read_bytes()
