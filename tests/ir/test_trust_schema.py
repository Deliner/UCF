from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from tools.generate_trust_ir_schema import (
    DEFAULT_OUTPUT,
    SCHEMA_ID,
    build_schema,
    render_schema,
)

from ucf.ir import IRErrorCode, IRValidationError, parse_trust_ir_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "ir" / "trust" / "v1"
COMPLETE = json.loads((FIXTURES / "complete.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def published_schema() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def test_published_trust_schema_is_current_closed_and_exact_version(
    published_schema,
):
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_schema()
    assert published_schema == build_schema()
    assert published_schema["$id"] == SCHEMA_ID
    assert published_schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert published_schema["x-ucf-trust-ir-version"] == "1.0.0"
    assert published_schema["additionalProperties"] is False
    assert (
        published_schema["properties"]["trust_ir_version"]["const"] == "1.0.0"
    )
    checks = published_schema["x-ucf-runtime-semantic-checks"]
    assert "canonical Behavior IR document binding" in checks
    assert "exact claim evidence evaluation" in checks
    Draft202012Validator.check_schema(published_schema)


def test_independent_schema_evaluator_accepts_complete_trust_fixture(
    published_schema,
):
    Draft202012Validator(published_schema).validate(COMPLETE)
    parse_trust_ir_json((FIXTURES / "complete.json").read_bytes())


def test_runtime_and_schema_reject_unknown_fields(published_schema):
    mutated = copy.deepcopy(COMPLETE)
    mutated["records"][0]["unexpected"] = True

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(published_schema).validate(mutated)
    with pytest.raises(IRValidationError) as captured:
        parse_trust_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.UNKNOWN_FIELD


def test_cross_record_semantics_are_truthfully_runtime_only(published_schema):
    mutated = copy.deepcopy(COMPLETE)
    mapping = next(
        record for record in mutated["records"] if record["kind"] == "mapping"
    )
    mapping["observation"]["target_id"] = "observed.missing"

    Draft202012Validator(published_schema).validate(mutated)
    with pytest.raises(IRValidationError) as captured:
        parse_trust_ir_json(json.dumps(mutated))

    assert captured.value.code is IRErrorCode.BROKEN_REFERENCE


def test_trust_schema_has_no_raw_fractional_number_or_platform_terms(
    published_schema,
):
    serialized = json.dumps(published_schema, sort_keys=True).lower()

    assert '"type": "number"' not in serialized
    for prohibited in (
        '"python"',
        '"pytest"',
        '"framework"',
        '"build_tool"',
        '"transport"',
    ):
        assert prohibited not in serialized


def test_trust_schema_generation_is_hash_seed_independent(tmp_path):
    generated: list[bytes] = []
    for seed in ("1", "42"):
        output = tmp_path / f"schema-{seed}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "generate_trust_ir_schema.py"),
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
