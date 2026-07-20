from __future__ import annotations

import json
from pathlib import Path

import pytest

from ucf.ir.codec import CURRENT_IR_VERSION, decode_ir_json
from ucf.ir.errors import IRErrorCode, IRValidationError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "v1"


def test_strict_json_boundary_accepts_the_exact_current_envelope_version():
    document = decode_ir_json((FIXTURES / "minimal.json").read_bytes())

    assert document["ir_version"] == CURRENT_IR_VERSION == "1.0.0"


@pytest.mark.parametrize("version", ["0.9.0", "1.0.1", "1.1.0", "2.0.0"])
def test_strict_json_boundary_rejects_every_unpublished_version(version):
    payload = {
        "kind": "behavior_ir",
        "ir_version": version,
        "document_id": "document.empty",
        "roots": [],
        "entities": [],
    }

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(json.dumps(payload))

    assert captured.value.code is IRErrorCode.UNSUPPORTED_VERSION
    assert version in str(captured.value)


@pytest.mark.parametrize("version", [None, "", "1", "1.0", "01.0.0", 1])
def test_strict_json_boundary_rejects_missing_or_malformed_version(version):
    payload = {
        "kind": "behavior_ir",
        "document_id": "document.empty",
        "roots": [],
        "entities": [],
    }
    if version is not None:
        payload["ir_version"] = version

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(json.dumps(payload))

    assert captured.value.code is IRErrorCode.MALFORMED_VERSION


def test_strict_json_boundary_rejects_duplicate_object_members():
    payload = (
        '{"kind":"behavior_ir","ir_version":"1.0.0",'
        '"document_id":"first","document_id":"second",'
        '"roots":[],"entities":[]}'
    )

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(payload)

    assert captured.value.code is IRErrorCode.DUPLICATE_JSON_MEMBER
    assert "document_id" in str(captured.value)


@pytest.mark.parametrize(
    "token",
    ["NaN", "Infinity", "-Infinity", "-0", "1.5", "1e3"],
)
def test_strict_json_boundary_rejects_noncanonical_json_numbers(token):
    payload = (
        '{"kind":"behavior_ir","ir_version":"1.0.0",'
        '"document_id":"document.empty","roots":[],"entities":[],'
        f'"unexpected_number":{token}'
        "}"
    )

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(payload)

    assert captured.value.code is IRErrorCode.INVALID_VALUE


@pytest.mark.parametrize("value", [-9007199254740992, 9007199254740992])
def test_strict_json_boundary_rejects_integers_outside_cross_runtime_range(value):
    payload = {
        "kind": "behavior_ir",
        "ir_version": "1.0.0",
        "document_id": "document.empty",
        "roots": [],
        "entities": [],
        "unexpected_integer": value,
    }

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(json.dumps(payload))

    assert captured.value.code is IRErrorCode.INVALID_VALUE


def test_extremely_large_integer_uses_the_stable_ir_error_boundary():
    payload = (
        '{"kind":"behavior_ir","ir_version":"1.0.0",'
        '"document_id":"document.empty","roots":[],"entities":[],'
        f'"unexpected_integer":{"9" * 5000}'
        "}"
    )

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(payload)

    assert captured.value.code is IRErrorCode.INVALID_VALUE


def test_excessive_json_nesting_uses_the_stable_ir_error_boundary():
    nested = "[" * 1100 + "null" + "]" * 1100
    payload = (
        '{"kind":"behavior_ir","ir_version":"1.0.0",'
        '"document_id":"document.empty","roots":[],"entities":[],'
        f'"unexpected":{nested}'
        "}"
    )

    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(payload)

    assert captured.value.code is IRErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize(
    "payload",
    [
        b"\xef\xbb\xbf{}",
        b"\xff",
        b"[]",
        b'{"ir_version":',
    ],
)
def test_strict_json_boundary_rejects_noncanonical_or_malformed_documents(payload):
    with pytest.raises(IRValidationError) as captured:
        decode_ir_json(payload)

    assert captured.value.code in {
        IRErrorCode.INVALID_JSON,
        IRErrorCode.INVALID_STRUCTURE,
        IRErrorCode.MALFORMED_VERSION,
    }
