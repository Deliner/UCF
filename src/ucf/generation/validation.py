from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pydantic import ValidationError as PydanticValidationError

from ucf.adapter_protocol import (
    AdapterPayload,
    AdapterProtocolError,
    Method,
    OperationKind,
    OperationParams,
    OperationResult,
    ProtocolCode,
    Request,
    SuccessResponse,
    encode_frame,
    json_profile_to_ir_value,
)
from ucf.generation.errors import (
    GenerationErrorCode,
    GenerationValidationError,
)
from ucf.generation.identity import (
    derive_generation_request_id,
    derive_generation_result_id,
)
from ucf.generation.models import (
    GENERATION_PROFILE_VERSION,
    GENERATION_REQUEST_SCHEMA_URI,
    GENERATION_RESULT_SCHEMA_URI,
    GenerationPortValue,
    GenerationRequest,
    GenerationResult,
)
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import (
    Action,
    Digest,
    IRModel,
    Port,
    Producer,
    ValueKind,
)


def validate_generation_request(request: GenerationRequest) -> None:
    request = _revalidate_model(request, GenerationRequest)
    try:
        behavior = parse_ir_json(canonical_ir_json(request.behavior))
    except ValueError as error:
        _fail(
            GenerationErrorCode.INVALID_STRUCTURE,
            "generation request Behavior IR is not valid",
            location="$.behavior",
        )
        raise AssertionError("unreachable") from error
    if request.behavior != behavior:
        _fail(
            GenerationErrorCode.NON_CANONICAL_ORDER,
            "generation request embeds noncanonical Behavior IR ordering",
            location="$.behavior",
        )
    if request.id != derive_generation_request_id(request):
        _fail(
            GenerationErrorCode.REQUEST_IDENTITY_MISMATCH,
            "generation request ID differs from its canonical content",
            location="$.id",
        )
    _validate_frame_budget(request)
    behavior_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_ir_json(behavior).encode("ascii")
        ).hexdigest(),
    )
    comparisons = (
        ("document_id", request.subject.document_id, behavior.document_id),
        ("ir_version", request.subject.ir_version, behavior.ir_version),
        (
            "canonical_digest",
            request.subject.canonical_digest,
            behavior_digest,
        ),
    )
    for field, actual, expected in comparisons:
        if actual != expected:
            _fail(
                GenerationErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                f"generation subject {field} differs from the Behavior IR",
                location=f"$.subject.{field}",
            )
    entities = {entity.id: entity for entity in behavior.entities}
    subject = entities.get(request.subject.target_id)
    if subject is None:
        _fail(
            GenerationErrorCode.BROKEN_REFERENCE,
            "generation subject does not resolve in the Behavior IR",
            location="$.subject",
        )
    if (
        subject.kind is not request.subject.target_kind
        or not isinstance(subject, Action)
    ):
        _fail(
            GenerationErrorCode.WRONG_TARGET_KIND,
            "generation subject kind differs from the resolved action",
            location="$.subject.target_kind",
        )
    _validate_port_values(
        request.inputs,
        ports=subject.input_ports,
        location="$.inputs",
    )
    _validate_port_values(
        request.expected_outputs,
        ports=subject.output_ports,
        location="$.expected_outputs",
    )


def validate_generation_result_structure(
    result: GenerationResult,
) -> None:
    result = _revalidate_model(result, GenerationResult)
    validate_generation_request(result.request)
    if result.id != derive_generation_result_id(result):
        _fail(
            GenerationErrorCode.CONTENT_IDENTITY_MISMATCH,
            "generation result ID differs from its canonical content",
            location="$.id",
        )
    _validate_frame_budget(result)


def validate_generation_result(
    result: GenerationResult,
    *,
    request: GenerationRequest,
    initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> None:
    validate_generation_result_structure(result)
    validate_generation_request(request)
    if result.request != request:
        _fail(
            GenerationErrorCode.REQUEST_IDENTITY_MISMATCH,
            "generation result embeds a different request",
            location="$.request",
        )
    if result.producer != initialized_adapter:
        _fail(
            GenerationErrorCode.PRODUCER_IDENTITY_MISMATCH,
            "generation result producer differs from the initialized adapter",
            location="$.producer",
        )
    for field, capability in (
        ("capability", result.capability),
        ("profile_capability", result.profile_capability),
    ):
        if negotiated_capabilities.get(capability.name) != capability.version:
            _fail(
                GenerationErrorCode.CAPABILITY_MISMATCH,
                "generation result capability was not negotiated exactly",
                location=f"$.{field}",
            )
    if result.capability != request.capability:
        _fail(
            GenerationErrorCode.CAPABILITY_MISMATCH,
            "generation result generic capability differs from the request",
            location="$.capability",
        )
    if result.profile_capability != request.profile_capability:
        _fail(
            GenerationErrorCode.CAPABILITY_MISMATCH,
            "generation result profile capability differs from the request",
            location="$.profile_capability",
        )
    if result.procedure_uri != request.adapter_procedure_uri:
        _fail(
            GenerationErrorCode.PROCEDURE_MISMATCH,
            "generation result procedure differs from the request",
            location="$.procedure_uri",
        )


def _validate_port_values(
    values: tuple[GenerationPortValue, ...],
    *,
    ports: tuple[Port, ...],
    location: str,
) -> None:
    available = {port.name: port for port in ports}
    required_names = {port.name for port in ports if port.required}
    supplied_names: set[str] = set()
    for position, item in enumerate(values):
        item_location = f"{location}[{position}]"
        port = available.get(item.port.name)
        if port is None:
            _fail(
                GenerationErrorCode.BROKEN_REFERENCE,
                "generation value names an unknown behavior port",
                location=f"{item_location}.port.name",
            )
        supplied_names.add(item.port.name)
        actual_kind = ValueKind(item.value.kind)
        if (
            actual_kind is ValueKind.NULL
            and port.required
            or actual_kind is not ValueKind.NULL
            and actual_kind is not port.value_kind
        ):
            _fail(
                GenerationErrorCode.VALUE_KIND_MISMATCH,
                "generation value kind differs from the behavior port",
                location=f"{item_location}.value",
            )
    if not required_names.issubset(supplied_names):
        _fail(
            GenerationErrorCode.INCOMPLETE_PORT_VALUES,
            "generation values omit a required behavior port",
            location=location,
        )


def _revalidate_model[ModelT: IRModel](
    value: ModelT,
    model_type: type[ModelT],
) -> ModelT:
    if type(value) is not model_type:
        _fail(
            GenerationErrorCode.INVALID_STRUCTURE,
            "document must use its exact declared model type",
            location="$",
        )
    try:
        return model_type.model_validate_json(
            json.dumps(
                value.model_dump(mode="json", warnings=False),
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            )
        )
    except (
        AttributeError,
        PydanticValidationError,
        TypeError,
        ValueError,
    ) as error:
        _fail(
            GenerationErrorCode.INVALID_STRUCTURE,
            "document does not satisfy its closed structural profile",
            location="$",
        )
        raise AssertionError("unreachable") from error


def _validate_frame_budget(
    document: GenerationRequest | GenerationResult,
) -> None:
    is_request = isinstance(document, GenerationRequest)
    schema_uri = (
        GENERATION_REQUEST_SCHEMA_URI
        if is_request
        else GENERATION_RESULT_SCHEMA_URI
    )
    payload = AdapterPayload(
        kind="adapter_payload",
        schema_uri=schema_uri,
        schema_version=GENERATION_PROFILE_VERSION,
        value=json_profile_to_ir_value(
            document.model_dump(mode="json", warnings=False)
        ),
    )
    if is_request:
        message = Request(
            jsonrpc="2.0",
            id="x" * 64,
            method=Method.GENERATE,
            params=OperationParams(
                kind=OperationKind.GENERATE_REQUEST,
                payload=payload,
            ),
        )
        label = "request"
    else:
        message = SuccessResponse(
            jsonrpc="2.0",
            id="x" * 64,
            result=OperationResult(
                kind=OperationKind.GENERATE_RESULT,
                payload=payload,
            ),
        )
        label = "result"
    try:
        encode_frame(message)
    except AdapterProtocolError as error:
        if error.code is not ProtocolCode.FRAME_TOO_LARGE:
            raise
        _fail(
            GenerationErrorCode.FRAME_BUDGET_EXCEEDED,
            f"generation {label} exceeds the adapter protocol frame budget",
            location="$",
        )
        raise AssertionError("unreachable") from error


def _fail(
    code: GenerationErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise GenerationValidationError(code, message, location=location)
