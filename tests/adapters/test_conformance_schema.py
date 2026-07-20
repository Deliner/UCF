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
from pydantic import ValidationError
from tools.generate_adapter_conformance_schema import (
    DEFAULT_OUTPUT,
    SCHEMA_ID,
    build_schema,
    render_schema,
)

from ucf.adapter_conformance import (
    CaseStatus,
    ConformanceCaseResult,
    ConformanceManifest,
    ConformanceReport,
    RunStatus,
    conformance_asset_names,
    conformance_kit_index,
    load_conformance_manifest,
    read_conformance_asset,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def published_schema() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def test_published_conformance_schema_is_current_closed_and_exact(
    published_schema,
):
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_schema()
    assert published_schema == build_schema()
    assert published_schema["$id"] == SCHEMA_ID
    assert published_schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert published_schema["x-ucf-conformance-kit-version"] == "1.0.0"
    assert published_schema["x-ucf-adapter-protocol-version"] == "1.0.0"
    assert "case and step identity uniqueness" in (
        published_schema["x-ucf-runtime-semantic-checks"]
    )
    for definition in (
        "ConformanceManifest",
        "ConformanceFixture",
        "ConformanceReport",
        "ConformanceAsset",
        "ConformanceKitIndex",
        "SendStep",
        "ExpectStep",
    ):
        assert (
            published_schema["$defs"][definition]["additionalProperties"]
            is False
        )
    Draft202012Validator.check_schema(published_schema)


def test_schema_accepts_every_public_json_asset_and_a_report(
    published_schema,
):
    validator = Draft202012Validator(published_schema)
    for name in conformance_asset_names():
        if not name.endswith(".json"):
            continue
        validator.validate(json.loads(read_conformance_asset(name)))

    manifest = load_conformance_manifest()
    report = ConformanceReport(
        kind="adapter_conformance_report",
        kit_version="1.0.0",
        protocol_version="1.0.0",
        profile="org.ucf.adapter-conformance.full",
        status=RunStatus.CONFORMANT,
        cases=tuple(
            ConformanceCaseResult(
                kind="conformance_case_result",
                case_id=case.case_id,
                status=CaseStatus.PASSED,
                expected="fixture_match",
                actual="fixture_match",
                protocol_code=None,
            )
            for case in manifest.cases
        ),
    )
    validator.validate(report.model_dump(mode="json"))
    validator.validate(conformance_kit_index().model_dump(mode="json"))


@pytest.mark.parametrize(
    "mutation",
    ["unknown_field", "wrong_kit_version", "unsafe_resource"],
)
def test_schema_and_runtime_reject_shared_manifest_negatives(
    published_schema,
    mutation: str,
):
    payload = load_conformance_manifest().model_dump(mode="json")
    if mutation == "unknown_field":
        payload["future"] = True
    elif mutation == "wrong_kit_version":
        payload["kit_version"] = "1.0.1"
    else:
        payload["cases"][0]["fixture"] = "../escape.json"

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(published_schema).validate(payload)
    with pytest.raises(ValidationError):
        ConformanceManifest.model_validate_json(json.dumps(payload))


def test_identity_and_status_semantics_are_truthfully_runtime_only(
    published_schema,
):
    payload = load_conformance_manifest().model_dump(mode="json")
    payload["cases"].append(copy.deepcopy(payload["cases"][0]))

    Draft202012Validator(published_schema).validate(payload)
    with pytest.raises(ValidationError, match="case IDs"):
        ConformanceManifest.model_validate_json(json.dumps(payload))


def test_conformance_schema_generation_is_hash_seed_independent(tmp_path):
    generated: list[bytes] = []
    for seed in ("1", "42"):
        output = tmp_path / f"schema-{seed}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "tools"
                    / "generate_adapter_conformance_schema.py"
                ),
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
