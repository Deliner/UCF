from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    Field,
    StringConstraints,
    model_validator,
)

from ucf.adapter_protocol.errors import (
    ErrorCategory,
    ProtocolCode,
    error_category_for_code,
)
from ucf.ir.models import (
    URI,
    BehaviorIR,
    IRModel,
    IRValue,
    NormalizedVersion,
    Producer,
    QualifiedName,
    SafeInteger,
)
from ucf.ir.trust_models import TrustIR

ADAPTER_PROTOCOL_VERSION = "1.0.0"
JSON_RPC_VERSION = "2.0"
MAX_FRAME_BYTES = 1_048_576
MAX_PENDING_REQUESTS = 64
MAX_REQUESTS_PER_SESSION = 65_536
MAX_RETAINED_STDERR_BYTES = 65_536

type RequestId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$",
    ),
]


class Method(StrEnum):
    INITIALIZE = "ucf.initialize"
    INVENTORY = "ucf.inventory"
    DISCOVER = "ucf.discover"
    MAP = "ucf.map"
    GENERATE = "ucf.generate"
    VERIFY = "ucf.verify"
    CANCEL = "ucf.cancel"
    SHUTDOWN = "ucf.shutdown"


class OperationKind(StrEnum):
    INVENTORY_REQUEST = "inventory_request"
    DISCOVER_REQUEST = "discover_request"
    MAP_REQUEST = "map_request"
    GENERATE_REQUEST = "generate_request"
    VERIFY_REQUEST = "verify_request"
    INVENTORY_RESULT = "inventory_result"
    DISCOVER_RESULT = "discover_result"
    MAP_RESULT = "map_result"
    GENERATE_RESULT = "generate_result"
    VERIFY_RESULT = "verify_result"


class CapabilityRequest(IRModel):
    kind: Literal["capability_request"]
    name: QualifiedName
    minimum_version: NormalizedVersion
    required: bool


class CapabilitySelection(IRModel):
    kind: Literal["capability"]
    name: QualifiedName
    version: NormalizedVersion


class AdapterPayload(IRModel):
    kind: Literal["adapter_payload"]
    schema_uri: URI
    schema_version: NormalizedVersion
    value: IRValue


type Payload = Annotated[
    BehaviorIR | TrustIR | AdapterPayload,
    Field(discriminator="kind"),
]


class InitializeParams(IRModel):
    kind: Literal["initialize_request"]
    protocol_version: NormalizedVersion
    client: Producer
    capabilities: tuple[CapabilityRequest, ...]


class OperationParams(IRModel):
    kind: OperationKind
    payload: Payload

    @model_validator(mode="after")
    def require_request_kind(self) -> OperationParams:
        if not self.kind.value.endswith("_request"):
            raise ValueError("operation params kind must identify a request")
        _validate_payload_semantics(self.payload)
        return self


class CancelParams(IRModel):
    kind: Literal["cancel_request"]
    request_id: RequestId


class ShutdownParams(IRModel):
    kind: Literal["shutdown_request"]


type RequestParams = InitializeParams | OperationParams | ShutdownParams

_METHOD_REQUEST_KIND = {
    Method.INVENTORY: OperationKind.INVENTORY_REQUEST,
    Method.DISCOVER: OperationKind.DISCOVER_REQUEST,
    Method.MAP: OperationKind.MAP_REQUEST,
    Method.GENERATE: OperationKind.GENERATE_REQUEST,
    Method.VERIFY: OperationKind.VERIFY_REQUEST,
}


class Request(IRModel):
    jsonrpc: Literal[JSON_RPC_VERSION]
    id: RequestId
    method: Method
    params: RequestParams

    @model_validator(mode="after")
    def require_method_params_match(self) -> Request:
        if self.method is Method.INITIALIZE:
            if not isinstance(self.params, InitializeParams):
                raise ValueError("initialize requires initialize_request params")
            return self
        if self.method is Method.SHUTDOWN:
            if not isinstance(self.params, ShutdownParams):
                raise ValueError("shutdown requires shutdown_request params")
            return self
        expected = _METHOD_REQUEST_KIND.get(self.method)
        if expected is None or not isinstance(self.params, OperationParams):
            raise ValueError("request method does not accept these params")
        if self.params.kind is not expected:
            raise ValueError(
                f"{self.method.value} requires {expected.value} params"
            )
        return self


class CancelNotification(IRModel):
    jsonrpc: Literal[JSON_RPC_VERSION]
    method: Literal[Method.CANCEL]
    params: CancelParams


type ClientMessage = Request | CancelNotification


class InitializeResult(IRModel):
    kind: Literal["initialize_result"]
    protocol_version: Literal[ADAPTER_PROTOCOL_VERSION]
    adapter: Producer
    capabilities: tuple[CapabilitySelection, ...]

    @model_validator(mode="after")
    def require_unique_capabilities(self) -> InitializeResult:
        names = [item.name for item in self.capabilities]
        if len(names) != len(set(names)):
            raise ValueError("initialize result contains duplicate capabilities")
        return self


class OperationResult(IRModel):
    kind: OperationKind
    payload: Payload

    @model_validator(mode="after")
    def require_result_kind(self) -> OperationResult:
        if not self.kind.value.endswith("_result"):
            raise ValueError("operation result kind must identify a result")
        _validate_payload_semantics(self.payload)
        return self


class ShutdownResult(IRModel):
    kind: Literal["shutdown_result"]


type Result = InitializeResult | OperationResult | ShutdownResult


class ErrorData(IRModel):
    category: ErrorCategory
    ucf_code: ProtocolCode

    @model_validator(mode="after")
    def require_matching_category(self) -> ErrorData:
        if self.category is not error_category_for_code(self.ucf_code):
            raise ValueError(
                "error category does not match the symbolic error code"
            )
        return self


class ErrorObject(IRModel):
    code: SafeInteger
    message: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    data: ErrorData


class SuccessResponse(IRModel):
    jsonrpc: Literal[JSON_RPC_VERSION]
    id: RequestId
    result: Result


class ErrorResponse(IRModel):
    jsonrpc: Literal[JSON_RPC_VERSION]
    id: RequestId | None
    error: ErrorObject

    @model_validator(mode="after")
    def reject_local_only_outcomes(self) -> ErrorResponse:
        if self.error.data.category in {
            ErrorCategory.TIMEOUT,
            ErrorCategory.PROCESS_FAILURE,
        }:
            raise ValueError(
                "adapter response cannot contain a local-only outcome"
            )
        return self


type ServerMessage = SuccessResponse | ErrorResponse


_recursive_namespace = {"IRValue": IRValue, "Payload": Payload}
AdapterPayload.model_rebuild(_types_namespace=_recursive_namespace)
OperationParams.model_rebuild(_types_namespace=_recursive_namespace)
Request.model_rebuild(_types_namespace=_recursive_namespace)
OperationResult.model_rebuild(_types_namespace=_recursive_namespace)
SuccessResponse.model_rebuild(_types_namespace=_recursive_namespace)


def _validate_payload_semantics(payload: Payload) -> None:
    if isinstance(payload, BehaviorIR):
        from ucf.ir.validation import validate_ir_semantics

        validate_ir_semantics(payload)
    elif isinstance(payload, TrustIR):
        from ucf.ir.trust_validation import validate_trust_semantics

        validate_trust_semantics(payload)
    else:
        from ucf.ir.validation import validate_ir_value

        validate_ir_value(payload.value)
