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
from tools.generate_adapter_protocol_schema import (
    DEFAULT_OUTPUT,
    SCHEMA_ID,
    build_schema,
    render_schema,
)

from ucf.adapter_protocol import (
    AdapterProtocolError,
    decode_request_frame,
    decode_response_frame,
    encode_frame,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "protocol"
    / "v1"
    / "reference-transcript.json"
)


@pytest.fixture(scope="module")
def published_schema() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def transcript() -> dict:
    return json.loads(TRANSCRIPT.read_text(encoding="utf-8"))


def test_published_protocol_schema_is_current_closed_and_exact(
    published_schema,
):
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_schema()
    assert published_schema == build_schema()
    assert published_schema["$id"] == SCHEMA_ID
    assert published_schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert published_schema["x-ucf-adapter-protocol-version"] == "1.0.0"
    assert published_schema["x-ucf-max-frame-bytes"] == 1_048_576
    assert "method/params discriminator agreement" in (
        published_schema["x-ucf-runtime-semantic-checks"]
    )
    for definition in (
        "Request",
        "CancelNotification",
        "SuccessResponse",
        "ErrorResponse",
    ):
        assert (
            published_schema["$defs"][definition]["additionalProperties"]
            is False
        )
    Draft202012Validator.check_schema(published_schema)


def test_reference_transcript_is_schema_valid_and_byte_canonical(
    published_schema,
    transcript,
):
    assert transcript["fixture_version"] == 1
    assert transcript["protocol_version"] == "1.0.0"
    assert {
        frame["message"].get("method")
        for frame in transcript["frames"]
        if "method" in frame["message"]
    } == {
        "ucf.initialize",
        "ucf.inventory",
        "ucf.discover",
        "ucf.map",
        "ucf.generate",
        "ucf.verify",
        "ucf.cancel",
        "ucf.shutdown",
    }
    validator = Draft202012Validator(published_schema)
    for frame in transcript["frames"]:
        message = frame["message"]
        validator.validate(message)
        encoded = (
            json.dumps(
                message,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
        parsed = (
            decode_request_frame(encoded)
            if frame["direction"] == "core_to_adapter"
            else decode_response_frame(encoded)
        )
        assert encode_frame(parsed) == encoded


@pytest.mark.parametrize(
    "mutation",
    ["unknown_field", "numeric_id", "wrong_jsonrpc"],
)
def test_schema_and_runtime_reject_shared_wire_negatives(
    published_schema,
    transcript,
    mutation: str,
):
    message = copy.deepcopy(transcript["frames"][0]["message"])
    if mutation == "unknown_field":
        message["future"] = True
    elif mutation == "numeric_id":
        message["id"] = 1
    else:
        message["jsonrpc"] = "1.0"

    with pytest.raises(JsonSchemaValidationError):
        Draft202012Validator(published_schema).validate(message)
    encoded = json.dumps(message).encode("utf-8") + b"\n"
    with pytest.raises(AdapterProtocolError):
        decode_request_frame(encoded)


def test_cross_field_semantics_are_truthfully_runtime_only(
    published_schema,
    transcript,
):
    message = copy.deepcopy(transcript["frames"][2]["message"])
    message["params"]["kind"] = "verify_request"

    Draft202012Validator(published_schema).validate(message)
    with pytest.raises(AdapterProtocolError):
        decode_request_frame(json.dumps(message).encode("utf-8") + b"\n")


def test_protocol_schema_generation_is_hash_seed_independent(tmp_path):
    generated: list[bytes] = []
    for seed in ("1", "42"):
        output = tmp_path / f"schema-{seed}.json"
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "generate_adapter_protocol_schema.py"),
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
