"""Runtime and published JSON Schema parity tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from tools.generate_spec_schema import (
    DEFAULT_OUTPUT,
    SCHEMA_ID,
    build_schema,
    render_schema,
)

from ucf.models.spec import SpecParseError, parse_spec

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STRUCTURAL_NEGATIVE_FIXTURES = [
    {
        "kind": "action",
        "metadata": {"name": "unknown-root"},
        "unknown": True,
    },
    {
        "kind": "action",
        "metadata": {"name": "unknown-nested", "unknown": True},
    },
    {
        "kind": "action",
        "metadata": {"name": "bad-field-type"},
        "input": {"value": {"type": "future"}},
    },
    {
        "metadata": {"name": "missing-kind"},
    },
    {
        "kind": "action",
        "metadata": {"name": "coerced-value"},
        "platform": {"cli": {"command": "run", "exit_code": "0"}},
    },
    {
        "kind": "usecase",
        "metadata": {"name": "internal-alias"},
        "invariants": [{"ref": "invariants/example"}],
    },
    {
        "kind": "usecase",
        "metadata": {"name": "empty-expression"},
        "steps": [
            {
                "id": "run",
                "use": "actions/run",
                "when": "   ",
            }
        ],
    },
    {
        "kind": "usecase",
        "metadata": {"name": "conflicting-expressions"},
        "steps": [
            {
                "id": "run",
                "use": "actions/run",
                "when": "ready",
                "skip_if": "disabled",
            }
        ],
    },
]


@pytest.fixture(scope="module")
def published_schema() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def test_published_schema_is_current_and_valid(published_schema) -> None:
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_schema()
    assert published_schema == build_schema()
    assert published_schema["$id"] == SCHEMA_ID
    assert published_schema["x-ucf-schema-version"] == "1"
    assert published_schema["discriminator"]["propertyName"] == "kind"
    assert len(published_schema["oneOf"]) == 6
    Draft202012Validator.check_schema(published_schema)


def test_published_schema_validates_every_repository_spec(published_schema) -> None:
    validator = Draft202012Validator(published_schema)
    failures: list[str] = []
    paths = sorted((PROJECT_ROOT / "specs").rglob("*.yaml"))
    paths.extend(sorted((PROJECT_ROOT / "specs").rglob("*.yml")))

    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for error in validator.iter_errors(document):
            location = ".".join(str(part) for part in error.absolute_path)
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}:{location}: {error.message}"
            )

    assert failures == []


@pytest.mark.parametrize("payload", STRUCTURAL_NEGATIVE_FIXTURES)
def test_runtime_and_schema_reject_same_structural_fixtures(
    published_schema,
    payload,
) -> None:
    with pytest.raises(SpecParseError):
        parse_spec(payload)

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(published_schema).validate(payload)


def test_schema_generation_is_hash_seed_independent(tmp_path) -> None:
    generated: list[bytes] = []
    for seed in ("1", "42"):
        output = tmp_path / f"schema-{seed}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "generate_spec_schema.py"),
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
