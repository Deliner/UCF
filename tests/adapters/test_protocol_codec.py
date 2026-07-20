from __future__ import annotations

import json
from pathlib import Path

import pytest

from ucf.adapter_protocol import (
    ADAPTER_PROTOCOL_VERSION,
    MAX_FRAME_BYTES,
    AdapterPayload,
    AdapterProtocolError,
    CancelNotification,
    CancelParams,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    ErrorData,
    ErrorObject,
    ErrorResponse,
    InitializeParams,
    InitializeResult,
    Method,
    OperationKind,
    OperationParams,
    ProtocolCode,
    Request,
    ShutdownParams,
    SuccessResponse,
    decode_request_frame,
    decode_response_frame,
    encode_frame,
)
from ucf.ir import parse_ir_json
from ucf.ir.models import Producer, RecordValue

BEHAVIOR_FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "v1"
)
TRUST_FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "trust" / "v1"
)


def _initialize_request() -> Request:
    return Request(
        jsonrpc="2.0",
        id="request-1",
        method=Method.INITIALIZE,
        params=InitializeParams(
            kind="initialize_request",
            protocol_version=ADAPTER_PROTOCOL_VERSION,
            client=Producer(
                kind="producer",
                name="org.ucf.core",
                version="0.1.0",
            ),
            capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name="org.ucf.adapter.inventory",
                    minimum_version="1.0.0",
                    required=True,
                ),
            ),
        ),
    )


def _assert_protocol_code(payload: bytes, expected: ProtocolCode) -> None:
    with pytest.raises(AdapterProtocolError) as captured:
        decode_request_frame(payload)

    assert captured.value.category is ErrorCategory.PROTOCOL_FAILURE
    assert captured.value.code is expected


def test_initialize_request_has_one_canonical_closed_wire_representation():
    request = _initialize_request()

    frame = encode_frame(request)

    assert frame.endswith(b"\n")
    assert b"\n" not in frame[:-1]
    assert frame == encode_frame(decode_request_frame(frame))
    assert decode_request_frame(frame) == request
    assert json.loads(frame)["method"] == "ucf.initialize"


def test_operation_request_carries_a_tagged_language_neutral_payload():
    payload = AdapterPayload(
        kind="adapter_payload",
        schema_uri="urn:ucf:adapter:reference",
        schema_version="1.0.0",
        value=RecordValue(kind="record", entries=()),
    )
    request = Request(
        jsonrpc="2.0",
        id="inventory-1",
        method=Method.INVENTORY,
        params=OperationParams(
            kind=OperationKind.INVENTORY_REQUEST,
            payload=payload,
        ),
    )

    decoded = decode_request_frame(encode_frame(request))

    assert decoded == request
    assert decoded.params.payload.kind == "adapter_payload"
    assert "python" not in encode_frame(request).decode("ascii").lower()


def test_operation_request_can_carry_the_accepted_behavior_ir_directly():
    behavior = parse_ir_json((BEHAVIOR_FIXTURES / "minimal.json").read_bytes())
    request = Request(
        jsonrpc="2.0",
        id="mapping-1",
        method=Method.MAP,
        params=OperationParams(
            kind=OperationKind.MAP_REQUEST,
            payload=behavior,
        ),
    )

    decoded = decode_request_frame(encode_frame(request))

    assert decoded == request
    assert decoded.params.payload.kind == "behavior_ir"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"{}\n", ProtocolCode.INVALID_MESSAGE),
        (b"[]\n", ProtocolCode.INVALID_MESSAGE),
        (
            b'{"jsonrpc":"2.0","id":1,"method":"ucf.shutdown",'
            b'"params":{"kind":"shutdown_request"}}\n',
            ProtocolCode.INVALID_MESSAGE,
        ),
        (
            b'{"jsonrpc":"2.0","id":"r","method":"ucf.unknown",'
            b'"params":{}}\n',
            ProtocolCode.METHOD_NOT_FOUND,
        ),
        (
            b'{"jsonrpc":"2.0","id":"r","method":"ucf.shutdown",'
            b'"params":{"kind":"shutdown_request"},"extra":true}\n',
            ProtocolCode.INVALID_MESSAGE,
        ),
        (
            b'{"jsonrpc":"2.0","id":"a","id":"b",'
            b'"method":"ucf.shutdown","params":{"kind":"shutdown_request"}}\n',
            ProtocolCode.PARSE_ERROR,
        ),
        (
            b'{"jsonrpc":"2.0","id":"r","method":"ucf.shutdown",'
            b'"params":{"kind":"shutdown_request","fraction":1.5}}\n',
            ProtocolCode.PARSE_ERROR,
        ),
        (b"\xef\xbb\xbf{}\n", ProtocolCode.PARSE_ERROR),
        (b'{"jsonrpc":"2.0"', ProtocolCode.TRUNCATED_FRAME),
    ],
)
def test_strict_request_boundary_rejects_ambiguous_or_extended_frames(
    payload: bytes,
    code: ProtocolCode,
):
    _assert_protocol_code(payload, code)


def test_method_and_operation_discriminator_must_match():
    frame = (
        b'{"id":"request-1","jsonrpc":"2.0","method":"ucf.inventory",'
        b'"params":{"kind":"verify_request","payload":'
        b'{"kind":"adapter_payload","schema_uri":"urn:ucf:test",'
        b'"schema_version":"1.0.0","value":{"kind":"null"}}}}\n'
    )

    _assert_protocol_code(frame, ProtocolCode.INVALID_PARAMS)


def test_only_the_cancel_notification_is_accepted_without_an_id():
    notification = CancelNotification(
        jsonrpc="2.0",
        method=Method.CANCEL,
        params=CancelParams(kind="cancel_request", request_id="request-1"),
    )

    assert decode_request_frame(encode_frame(notification)) == notification

    _assert_protocol_code(
        b'{"jsonrpc":"2.0","method":"ucf.shutdown",'
        b'"params":{"kind":"shutdown_request"}}\n',
        ProtocolCode.INVALID_MESSAGE,
    )


def test_frame_limit_is_checked_before_json_decode_or_newline_wait():
    exact_limit_invalid_json = b" " * (MAX_FRAME_BYTES - 1) + b"\n"
    over_limit_without_newline = b" " * (MAX_FRAME_BYTES + 1)

    _assert_protocol_code(exact_limit_invalid_json, ProtocolCode.PARSE_ERROR)
    _assert_protocol_code(
        over_limit_without_newline,
        ProtocolCode.FRAME_TOO_LARGE,
    )


@pytest.mark.parametrize(
    "frame",
    [
        encode_frame(_initialize_request()) + b"\n",
        (
            b'{"jsonrpc":"2.0",\n"id":"request-1",'
            b'"method":"ucf.shutdown",'
            b'"params":{"kind":"shutdown_request"}}\n'
        ),
    ],
)
def test_request_frame_contains_exactly_one_terminal_lf(frame: bytes):
    _assert_protocol_code(frame, ProtocolCode.INVALID_MESSAGE)


def test_response_frame_contains_exactly_one_terminal_lf():
    response = ErrorResponse(
        jsonrpc="2.0",
        id="request-1",
        error=ErrorObject(
            code=-32000,
            message="operation failed",
            data=ErrorData(
                category=ErrorCategory.ADAPTER_FAILURE,
                ucf_code=ProtocolCode.OPERATION_FAILED,
            ),
        ),
    )

    with pytest.raises(AdapterProtocolError) as captured:
        decode_response_frame(encode_frame(response) + b"\n")

    assert captured.value.category is ErrorCategory.PROTOCOL_FAILURE
    assert captured.value.code is ProtocolCode.INVALID_MESSAGE


def test_request_ids_are_bounded_ascii_strings():
    base = json.loads(encode_frame(_initialize_request()))

    for invalid_id in ("", "x" * 65, "contains space", "ümlaut"):
        base["id"] = invalid_id
        _assert_protocol_code(
            json.dumps(base).encode("utf-8") + b"\n",
            ProtocolCode.INVALID_MESSAGE,
        )


def test_shutdown_params_cannot_be_used_with_an_operation_method():
    frame = encode_frame(
        Request(
            jsonrpc="2.0",
            id="shutdown-1",
            method=Method.SHUTDOWN,
            params=ShutdownParams(kind="shutdown_request"),
        )
    )

    assert decode_request_frame(frame).method is Method.SHUTDOWN


def test_success_response_round_trips_with_exact_negotiated_coordinates():
    response = SuccessResponse(
        jsonrpc="2.0",
        id="request-1",
        result=InitializeResult(
            kind="initialize_result",
            protocol_version=ADAPTER_PROTOCOL_VERSION,
            adapter=Producer(
                kind="producer",
                name="org.ucf.reference-adapter",
                version="1.0.0",
            ),
            capabilities=(
                CapabilitySelection(
                    kind="capability",
                    name="org.ucf.adapter.inventory",
                    version="1.0.0",
                ),
            ),
        ),
    )

    assert decode_response_frame(encode_frame(response)) == response


def test_error_response_round_trips_with_normative_symbolic_coordinates():
    response = ErrorResponse(
        jsonrpc="2.0",
        id="request-1",
        error=ErrorObject(
            code=-32000,
            message="operation capability was not negotiated",
            data=ErrorData(
                category=ErrorCategory.PROTOCOL_FAILURE,
                ucf_code=ProtocolCode.CAPABILITY_NOT_NEGOTIATED,
            ),
        ),
    )

    decoded = decode_response_frame(encode_frame(response))

    assert decoded == response
    assert decoded.error.data.ucf_code is ProtocolCode.CAPABILITY_NOT_NEGOTIATED


@pytest.mark.parametrize(
    ("coordinates", "numeric_code"),
    [
        (
            '"category":"protocol_failure",'
            '"ucf_code":"process_exited"',
            -32000,
        ),
        (
            '"category":"adapter_failure",'
            '"ucf_code":"parse_error"',
            -32700,
        ),
        (
            '"category":"cancelled",'
            '"ucf_code":"operation_failed"',
            -32000,
        ),
    ],
)
def test_error_category_and_symbolic_code_must_agree(
    coordinates: str,
    numeric_code: int,
):
    frame = (
        f'{{"jsonrpc":"2.0","id":"r","error":{{"code":{numeric_code},'
        f'"message":"bad coordinates","data":{{{coordinates}}}}}}}\n'
    ).encode()

    with pytest.raises(AdapterProtocolError) as captured:
        decode_response_frame(frame)

    assert captured.value.category is ErrorCategory.PROCESS_FAILURE
    assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT


@pytest.mark.parametrize(
    ("category", "code"),
    [
        ("timeout", "operation_timeout"),
        ("process_failure", "process_exited"),
    ],
)
def test_adapter_response_cannot_claim_a_local_only_outcome(
    category: str,
    code: str,
):
    frame = (
        '{"jsonrpc":"2.0","id":"r","error":{"code":-32000,'
        '"message":"forged local outcome","data":'
        f'{{"category":"{category}","ucf_code":"{code}"}}}}}}\n'
    ).encode()

    with pytest.raises(AdapterProtocolError) as captured:
        decode_response_frame(frame)

    assert captured.value.category is ErrorCategory.PROCESS_FAILURE
    assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT


def test_local_structured_error_coordinates_cannot_contradict_each_other():
    with pytest.raises(ValueError):
        AdapterProtocolError(
            ErrorCategory.CANCELLED,
            ProtocolCode.PROCESS_EXITED,
            "contradictory local error",
        )


@pytest.mark.parametrize(
    "frame",
    [
        b'{"jsonrpc":"2.0","id":"r"}\n',
        b'{"jsonrpc":"2.0","id":"r","result":{},'
        b'"error":{"code":-32000,"message":"bad","data":'
        b'{"category":"adapter_failure","ucf_code":"operation_failed"}}}\n',
        b'{"jsonrpc":"2.0","id":"r","result":{},"extra":true}\n',
        b'{"jsonrpc":"2.0","id":1,"result":{}}\n',
        b'{"jsonrpc":"2.0","id":null,"result":{}}\n',
        b'{"jsonrpc":"2.0","id":"r","error":{"code":-32000,'
        b'"message":"bad","data":{"category":"adapter_failure"}}}\n',
    ],
)
def test_invalid_adapter_response_shape_fails_closed(frame: bytes):
    with pytest.raises(AdapterProtocolError) as captured:
        decode_response_frame(frame)

    assert captured.value.category is ErrorCategory.PROCESS_FAILURE
    assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT


def test_duplicate_selected_capability_is_invalid_adapter_output():
    frame = (
        b'{"id":"request-1","jsonrpc":"2.0","result":'
        b'{"adapter":{"kind":"producer","name":"org.ucf.reference-adapter",'
        b'"version":"1.0.0"},"capabilities":['
        b'{"kind":"capability","name":"org.ucf.adapter.inventory",'
        b'"version":"1.0.0"},'
        b'{"kind":"capability","name":"org.ucf.adapter.inventory",'
        b'"version":"1.0.0"}],"kind":"initialize_result",'
        b'"protocol_version":"1.0.0"}}\n'
    )

    with pytest.raises(AdapterProtocolError) as captured:
        decode_response_frame(frame)

    assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT


@pytest.mark.parametrize("payload_kind", ["behavior", "trust", "adapter"])
def test_operation_payload_is_semantically_validated_before_dispatch(
    payload_kind: str,
):
    if payload_kind == "behavior":
        payload = json.loads((BEHAVIOR_FIXTURES / "minimal.json").read_text())
        payload["roots"] = [
            {
                "kind": "entity_ref",
                "target_kind": "action",
                "target_id": "action.missing",
            }
        ]
    elif payload_kind == "trust":
        payload = json.loads((TRUST_FIXTURES / "complete.json").read_text())
        payload["records"][4]["trace"]["target_id"] = "source.missing"
    else:
        payload = {
            "kind": "adapter_payload",
            "schema_uri": "urn:ucf:adapter:test",
            "schema_version": "1.0.0",
            "value": {
                "kind": "record",
                "entries": [
                    {
                        "kind": "record_entry",
                        "name": "duplicate",
                        "value": {"kind": "null"},
                    },
                    {
                        "kind": "record_entry",
                        "name": "duplicate",
                        "value": {"kind": "null"},
                    },
                ],
            },
        }
    frame = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "method": "ucf.inventory",
        "params": {
            "kind": "inventory_request",
            "payload": payload,
        },
    }

    _assert_protocol_code(
        json.dumps(frame).encode("utf-8") + b"\n",
        ProtocolCode.INVALID_PARAMS,
    )


def test_error_numeric_code_must_match_its_normative_symbolic_code():
    frame = (
        b'{"id":"request-1","jsonrpc":"2.0","error":'
        b'{"code":-32700,"message":"failed","data":'
        b'{"category":"adapter_failure","ucf_code":"operation_failed"}}}\n'
    )

    with pytest.raises(AdapterProtocolError) as captured:
        decode_response_frame(frame)

    assert captured.value.code is ProtocolCode.INVALID_ADAPTER_OUTPUT
