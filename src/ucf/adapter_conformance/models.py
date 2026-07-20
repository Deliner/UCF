from __future__ import annotations

import json
from enum import IntEnum, StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from ucf.adapter_protocol import (
    ADAPTER_PROTOCOL_VERSION,
    ErrorCategory,
    ProtocolCode,
)
from ucf.adapter_protocol.errors import (
    error_category_for_code,
    json_rpc_error_code,
)
from ucf.adapter_protocol.models import (
    MAX_FRAME_BYTES,
    Payload,
    RequestId,
)
from ucf.ir import decode_strict_json_object
from ucf.ir.models import (
    DigestValue,
    Identifier,
    IRModel,
    QualifiedName,
    SafeInteger,
    SemanticToken,
)

CONFORMANCE_KIT_VERSION = "1.0.0"
CONFORMANCE_PROFILE = "org.ucf.adapter-conformance.full"
CONTROL_SCHEMA_URI = "urn:ucf:adapter-conformance:control:1.0.0"

type ResourcePath = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=255,
        pattern=(
            r"^[A-Za-z0-9_][A-Za-z0-9._-]*"
            r"(?:/[A-Za-z0-9_][A-Za-z0-9._-]*)*$"
        ),
    ),
]


class CaseProcedure(StrEnum):
    INITIALIZE_SHUTDOWN = "initialize_shutdown"
    INCOMPATIBLE_VERSION = "incompatible_version"
    DUPLICATE_CAPABILITY = "duplicate_capability"
    UNSUPPORTED_REQUIRED = "unsupported_required"
    LIFECYCLE = "lifecycle"
    CAPABILITY_GATE = "capability_gate"
    OPERATION_FAMILIES = "operation_families"
    TARGETED_CANCELLATION = "targeted_cancellation"
    PARSE_ERROR = "parse_error"
    INVALID_MESSAGE = "invalid_message"
    OPTIONAL_CAPABILITY = "optional_capability"
    CANCEL_NOOP = "cancel_noop"
    DUPLICATE_REQUEST_ID = "duplicate_request_id"
    UNKNOWN_METHOD = "unknown_method"
    INVALID_PARAMS = "invalid_params"
    DUPLICATE_JSON_MEMBER = "duplicate_json_member"
    SHUTDOWN_PENDING = "shutdown_pending"


class CaseStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class RunStatus(StrEnum):
    CONFORMANT = "conformant"
    NON_CONFORMANT = "non_conformant"
    RUNNER_ERROR = "runner_error"


class ConformanceExitCode(IntEnum):
    CONFORMANT = 0
    NON_CONFORMANT = 1
    RUNNER_ERROR = 3


class ConformanceCase(IRModel):
    kind: Literal["conformance_case"]
    case_id: Identifier
    surface: Literal["universal", "control_profile"]
    isolation: Literal["fresh_process"]
    procedure: CaseProcedure
    fixture: ResourcePath
    required_capabilities: tuple[QualifiedName, ...]

    @field_validator("fixture")
    @classmethod
    def validate_fixture_path(cls, value: str) -> str:
        return validate_resource_path(value)

    @model_validator(mode="after")
    def validate_required_capabilities(self) -> ConformanceCase:
        if len(self.required_capabilities) != len(
            set(self.required_capabilities)
        ):
            raise ValueError(
                "conformance case required capabilities must be unique"
            )
        return self


class FaultProfile(IRModel):
    kind: Literal["fault_profile"]
    fault_id: Identifier
    arguments: Annotated[tuple[str, ...], Field(min_length=1, max_length=8)]
    expected_case_id: Identifier

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or "\0" in item for item in value):
            raise ValueError("fault arguments must be nonempty argv strings")
        return value


class ConformanceManifest(IRModel):
    kind: Literal["adapter_conformance_manifest"]
    kit_version: Literal[CONFORMANCE_KIT_VERSION]
    protocol_version: Literal[ADAPTER_PROTOCOL_VERSION]
    profile: Literal[CONFORMANCE_PROFILE]
    control_schema_uri: Literal[CONTROL_SCHEMA_URI]
    cases: Annotated[tuple[ConformanceCase, ...], Field(min_length=1)]
    fault_profiles: tuple[FaultProfile, ...]
    sample_adapter: ResourcePath
    fault_adapter: ResourcePath

    @field_validator("sample_adapter", "fault_adapter")
    @classmethod
    def validate_adapter_path(cls, value: str) -> str:
        return validate_resource_path(value)

    @model_validator(mode="after")
    def validate_identities(self) -> ConformanceManifest:
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("conformance case IDs must be unique")
        fault_ids = tuple(item.fault_id for item in self.fault_profiles)
        if len(fault_ids) != len(set(fault_ids)):
            raise ValueError("conformance fault IDs must be unique")
        known_cases = set(case_ids)
        broken = sorted(
            {
                item.expected_case_id
                for item in self.fault_profiles
                if item.expected_case_id not in known_cases
            }
        )
        if broken:
            raise ValueError(
                f"fault profile references an unknown case: {broken}"
            )
        return self


class SendStep(IRModel):
    kind: Literal["send"]
    step_id: Identifier
    frame: Annotated[str, StringConstraints(min_length=1)]

    @field_validator("frame")
    @classmethod
    def validate_frame(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("fixture frame must omit its terminal LF")
        if len(value.encode("utf-8")) + 1 > MAX_FRAME_BYTES:
            raise ValueError("fixture frame exceeds the protocol byte limit")
        return value


type SuccessResultKind = Literal[
    "initialize_result",
    "inventory_result",
    "discover_result",
    "map_result",
    "generate_result",
    "verify_result",
    "shutdown_result",
]


class ExpectStep(IRModel):
    kind: Literal["expect"]
    step_id: Identifier
    request_id: RequestId | None
    outcome: Literal["success", "error"]
    result_kind: SuccessResultKind | None
    error_category: ErrorCategory | None
    protocol_code: ProtocolCode | None
    jsonrpc_code: int | None
    selected_capabilities: tuple[QualifiedName, ...]
    expected_payload: Payload | None

    @model_validator(mode="after")
    def validate_coordinates(self) -> ExpectStep:
        if self.outcome == "success":
            if (
                self.request_id is None
                or self.result_kind is None
                or self.error_category is not None
                or self.protocol_code is not None
                or self.jsonrpc_code is not None
            ):
                raise ValueError(
                    "success expectation has incompatible coordinates"
                )
            if self.result_kind == "initialize_result":
                if self.expected_payload is not None:
                    raise ValueError(
                        "initialize expectation cannot contain a payload"
                    )
                if len(self.selected_capabilities) != len(
                    set(self.selected_capabilities)
                ):
                    raise ValueError(
                        "initialize expectation capabilities must be unique"
                    )
                return self
            if self.result_kind == "shutdown_result":
                if self.selected_capabilities or self.expected_payload is not None:
                    raise ValueError(
                        "shutdown expectation cannot contain result data"
                    )
                return self
            if (
                self.selected_capabilities
                or self.expected_payload is None
            ):
                raise ValueError(
                    "operation expectation requires only an exact payload"
                )
            return self
        if (
            self.result_kind is not None
            or self.error_category is None
            or self.protocol_code is None
            or self.jsonrpc_code is None
            or self.selected_capabilities
            or self.expected_payload is not None
        ):
            raise ValueError("error expectation has incompatible coordinates")
        if self.error_category is not error_category_for_code(
            self.protocol_code
        ):
            raise ValueError("error expectation category does not match code")
        if self.jsonrpc_code != json_rpc_error_code(self.protocol_code):
            raise ValueError(
                "error expectation JSON-RPC code does not match symbolic code"
            )
        return self


type FixtureStep = Annotated[
    SendStep | ExpectStep,
    Field(discriminator="kind"),
]


class ConformanceFixture(IRModel):
    kind: Literal["adapter_conformance_fixture"]
    kit_version: Literal[CONFORMANCE_KIT_VERSION]
    case_id: Identifier
    procedure: CaseProcedure
    steps: Annotated[tuple[FixtureStep, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def validate_steps(self) -> ConformanceFixture:
        step_ids = tuple(item.step_id for item in self.steps)
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("conformance fixture step IDs must be unique")
        if not any(isinstance(item, SendStep) for item in self.steps):
            raise ValueError("conformance fixture must send at least one frame")
        if not any(isinstance(item, ExpectStep) for item in self.steps):
            raise ValueError(
                "conformance fixture must expect at least one response"
            )
        return self


class ConformanceCaseResult(IRModel):
    kind: Literal["conformance_case_result"]
    case_id: Identifier
    status: CaseStatus
    expected: SemanticToken
    actual: SemanticToken
    protocol_code: ProtocolCode | None


class ConformanceReport(IRModel):
    kind: Literal["adapter_conformance_report"]
    kit_version: Literal[CONFORMANCE_KIT_VERSION]
    protocol_version: Literal[ADAPTER_PROTOCOL_VERSION]
    profile: Literal[CONFORMANCE_PROFILE]
    status: RunStatus
    cases: Annotated[tuple[ConformanceCaseResult, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_status_and_identities(self) -> ConformanceReport:
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("conformance report case IDs must be unique")
        statuses = {item.status for item in self.cases}
        if CaseStatus.ERROR in statuses:
            expected_status = RunStatus.RUNNER_ERROR
        elif CaseStatus.FAILED in statuses:
            expected_status = RunStatus.NON_CONFORMANT
        else:
            expected_status = RunStatus.CONFORMANT
        if self.status is not expected_status:
            raise ValueError(
                "conformance report status does not match its case results"
            )
        return self


class ConformanceAsset(IRModel):
    kind: Literal["conformance_asset"]
    name: ResourcePath
    sha256: DigestValue
    size: Annotated[SafeInteger, Field(ge=1)]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_resource_path(value)


class ConformanceKitIndex(IRModel):
    kind: Literal["adapter_conformance_kit_index"]
    kit_version: Literal[CONFORMANCE_KIT_VERSION]
    protocol_version: Literal[ADAPTER_PROTOCOL_VERSION]
    assets: Annotated[tuple[ConformanceAsset, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_assets(self) -> ConformanceKitIndex:
        names = tuple(asset.name for asset in self.assets)
        if len(names) != len(set(names)):
            raise ValueError("conformance asset names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("conformance assets must be sorted by name")
        return self


type ConformanceDocument = Annotated[
    ConformanceManifest
    | ConformanceFixture
    | ConformanceReport
    | ConformanceKitIndex,
    Field(discriminator="kind"),
]


def validate_resource_path(value: str) -> str:
    if (
        not value
        or value == "."
        or value.startswith("/")
        or "\\" in value
        or "//" in value
        or "\0" in value
    ):
        raise ValueError("conformance resource path is not normalized")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("conformance resource path is not normalized")
    if str(path) != value:
        raise ValueError("conformance resource path is not normalized")
    return value


def canonical_conformance_json(
    document: (
        ConformanceFixture
        | ConformanceManifest
        | ConformanceReport
        | ConformanceKitIndex
    ),
) -> bytes:
    return (
        json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def parse_conformance_manifest_json(
    payload: str | bytes,
) -> ConformanceManifest:
    return _parse_conformance_json(
        payload,
        ConformanceManifest,
    )


def parse_conformance_fixture_json(
    payload: str | bytes,
) -> ConformanceFixture:
    return _parse_conformance_json(
        payload,
        ConformanceFixture,
    )


def parse_conformance_report_json(
    payload: str | bytes,
) -> ConformanceReport:
    return _parse_conformance_json(
        payload,
        ConformanceReport,
    )


def parse_conformance_kit_index_json(
    payload: str | bytes,
) -> ConformanceKitIndex:
    return _parse_conformance_json(
        payload,
        ConformanceKitIndex,
    )


def _parse_conformance_json[Document: IRModel](
    payload: str | bytes,
    model: type[Document],
) -> Document:
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)


def validate_report_against_manifest(
    report: ConformanceReport,
    manifest: ConformanceManifest,
) -> None:
    if (
        report.kit_version != manifest.kit_version
        or report.protocol_version != manifest.protocol_version
        or report.profile != manifest.profile
    ):
        raise ValueError(
            "conformance report coordinates do not match the manifest"
        )
    report_ids = tuple(item.case_id for item in report.cases)
    manifest_ids = tuple(item.case_id for item in manifest.cases)
    if report_ids != manifest_ids:
        raise ValueError(
            "conformance report case IDs must exactly match manifest order"
        )
