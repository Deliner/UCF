from __future__ import annotations

import hashlib
import re
from typing import Annotated, Literal

from pydantic import (
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ucf.adapter_protocol import (
    CapabilitySelection,
    ir_value_to_json_profile,
)
from ucf.ir.models import (
    URI,
    BehaviorIR,
    Digest,
    EntityKind,
    IRModel,
    IRValue,
    ListValue,
    PortRef,
    Producer,
    RecordValue,
    SafeInteger,
)
from ucf.ir.trust_models import BehaviorEntityRef
from ucf.ir.validation import validate_ir_value

GENERATION_PROFILE_VERSION = "1.0.0"
GENERATION_CAPABILITY = "org.ucf.adapter.generation"
GENERATION_REQUEST_SCHEMA_URI = "urn:ucf:generation:request:1.0.0"
GENERATION_RESULT_SCHEMA_URI = "urn:ucf:generation:result:1.0.0"
GENERATION_PROFILE_PROCEDURE_URI = "urn:ucf:generation:manifest:1.0.0"
MAX_GENERATED_FILES = 64
MAX_GENERATED_FILE_BYTES = 131_072
MAX_GENERATED_TOTAL_BYTES = 524_288
MAX_GENERATED_PATH_SEGMENTS = 16
MAX_VERIFICATION_ARGUMENTS = 32

type GenerationRequestId = Annotated[
    str,
    StringConstraints(pattern=r"^generation-request\.[0-9a-f]{64}$"),
]
type GenerationResultId = Annotated[
    str,
    StringConstraints(pattern=r"^generation-result\.[0-9a-f]{64}$"),
]
type GeneratedPath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=240),
]
type MediaType = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=127,
        pattern=(
            r"^[a-z0-9][a-z0-9!#$&^_.+-]*/"
            r"[a-z0-9][a-z0-9!#$&^_.+-]*$"
        ),
    ),
]
type VerificationArgument = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
]

_VERSIONED_URN_PATTERN = re.compile(
    r"^urn:[a-z][a-z0-9.-]*(?::[a-z0-9][a-z0-9._-]*)+:"
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
_PATH_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class GenerationEnvironment(IRModel):
    kind: Literal["generation_environment"]
    identity_uri: URI
    revision: Digest

    @field_validator("identity_uri")
    @classmethod
    def validate_identity_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "generation environment")


class GenerationPortValue(IRModel):
    kind: Literal["generation_port_value"]
    port: PortRef
    value: IRValue

    @model_validator(mode="after")
    def validate_value(self) -> GenerationPortValue:
        validate_ir_value(self.value)
        _validate_canonical_ir_value(self.value)
        return self


class GenerationRequest(IRModel):
    kind: Literal["generation_request"]
    generation_version: Literal[GENERATION_PROFILE_VERSION]
    schema_uri: Literal[GENERATION_REQUEST_SCHEMA_URI]
    id: GenerationRequestId
    capability: CapabilitySelection
    profile_capability: CapabilitySelection
    profile_procedure_uri: Literal[GENERATION_PROFILE_PROCEDURE_URI]
    adapter_procedure_uri: URI
    behavior: BehaviorIR
    subject: BehaviorEntityRef
    inputs: Annotated[
        tuple[GenerationPortValue, ...],
        Field(max_length=MAX_GENERATED_FILES),
    ]
    expected_outputs: Annotated[
        tuple[GenerationPortValue, ...],
        Field(min_length=1, max_length=MAX_GENERATED_FILES),
    ]
    environment: GenerationEnvironment
    profile_configuration: RecordValue

    @field_validator("adapter_procedure_uri")
    @classmethod
    def validate_adapter_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "generation adapter procedure")

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> GenerationRequest:
        if (
            self.capability.name != GENERATION_CAPABILITY
            or self.capability.version != GENERATION_PROFILE_VERSION
        ):
            raise ValueError(
                "generation request requires the exact generation capability"
            )
        if (
            self.profile_capability.name == GENERATION_CAPABILITY
            or self.profile_capability.version != GENERATION_PROFILE_VERSION
        ):
            raise ValueError(
                "generation request requires a distinct exact profile capability"
            )
        if self.subject.target_kind is not EntityKind.ACTION:
            raise ValueError(
                "generation request currently supports an action subject"
            )
        self._validate_port_values(self.inputs, direction="input")
        self._validate_port_values(
            self.expected_outputs,
            direction="output",
        )
        try:
            decoded = ir_value_to_json_profile(self.profile_configuration)
        except ValueError as error:
            if "duplicate" in str(error):
                raise ValueError(
                    "generation profile configuration contains duplicate names"
                ) from error
            raise ValueError(
                "generation profile configuration is not canonical"
            ) from error
        if not isinstance(decoded, dict):
            raise ValueError(
                "generation profile configuration must be a record"
            )
        return self

    def _validate_port_values(
        self,
        values: tuple[GenerationPortValue, ...],
        *,
        direction: Literal["input", "output"],
    ) -> None:
        identities = tuple(
            (
                item.port.owner.target_kind.value,
                item.port.owner.target_id,
                item.port.direction,
                item.port.name,
            )
            for item in values
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                f"generation {direction} values contain duplicate ports"
            )
        if identities != tuple(sorted(identities)):
            raise ValueError(
                f"generation {direction} values are not in canonical order"
            )
        for item in values:
            if item.port.direction != direction:
                raise ValueError(
                    f"generation {direction} value has wrong direction"
                )
            if (
                item.port.owner.target_kind is not self.subject.target_kind
                or item.port.owner.target_id != self.subject.target_id
            ):
                raise ValueError(
                    f"generation {direction} value owner differs from subject"
                )


class GeneratedFile(IRModel):
    kind: Literal["generated_file"]
    path: GeneratedPath
    ownership: Literal["generator_owned"]
    media_type: MediaType
    encoding: Literal["utf-8"]
    byte_size: Annotated[SafeInteger, Field(ge=0, le=MAX_GENERATED_FILE_BYTES)]
    content_digest: Digest
    content: Annotated[
        str,
        StringConstraints(max_length=MAX_GENERATED_FILE_BYTES),
    ]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        segments = value.split("/")
        if (
            value.startswith("/")
            or "\\" in value
            or "\0" in value
            or len(segments) > MAX_GENERATED_PATH_SEGMENTS
            or any(
                not segment
                or segment in {".", ".."}
                or segment.endswith(".")
                or _PATH_SEGMENT_PATTERN.fullmatch(segment) is None
                or segment.split(".", 1)[0].casefold()
                in _WINDOWS_RESERVED_NAMES
                for segment in segments
            )
        ):
            raise ValueError("generated file path is not a safe relative path")
        return value

    @model_validator(mode="after")
    def validate_content_identity(self) -> GeneratedFile:
        encoded = self.content.encode("utf-8")
        if len(encoded) != self.byte_size:
            raise ValueError(
                "generated file byte size differs from its UTF-8 content"
            )
        if hashlib.sha256(encoded).hexdigest() != self.content_digest.value:
            raise ValueError(
                "generated file content digest differs from its UTF-8 content"
            )
        return self


class GenerationVerification(IRModel):
    kind: Literal["generation_verification"]
    procedure_uri: URI
    working_directory: Literal["implementation_root"]
    argv: Annotated[
        tuple[VerificationArgument, ...],
        Field(min_length=1, max_length=MAX_VERIFICATION_ARGUMENTS),
    ]

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "generation verification procedure")

    @field_validator("argv")
    @classmethod
    def validate_argv(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any("\0" in argument or "\n" in argument for argument in value):
            raise ValueError(
                "generation verification arguments contain unsafe characters"
            )
        return value


class GenerationResult(IRModel):
    kind: Literal["generation_result"]
    generation_version: Literal[GENERATION_PROFILE_VERSION]
    schema_uri: Literal[GENERATION_RESULT_SCHEMA_URI]
    id: GenerationResultId
    status: Literal["complete"]
    request: GenerationRequest
    producer: Producer
    capability: CapabilitySelection
    profile_capability: CapabilitySelection
    procedure_uri: URI
    files: Annotated[
        tuple[GeneratedFile, ...],
        Field(min_length=1, max_length=MAX_GENERATED_FILES),
    ]
    verification: GenerationVerification

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "generation result procedure")

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> GenerationResult:
        if self.capability != self.request.capability:
            raise ValueError(
                "generation result generic capability differs from the request"
            )
        if self.profile_capability != self.request.profile_capability:
            raise ValueError(
                "generation result profile capability differs from the request"
            )
        if self.procedure_uri != self.request.adapter_procedure_uri:
            raise ValueError(
                "generation result procedure differs from the request"
            )
        paths = tuple(item.path for item in self.files)
        folded_paths = tuple(path.casefold() for path in paths)
        if len(folded_paths) != len(set(folded_paths)):
            raise ValueError(
                "generation result contains duplicate generated paths"
            )
        folded_path_set = set(folded_paths)
        if any(
            "/".join(path.casefold().split("/")[:position])
            in folded_path_set
            for path in paths
            for position in range(1, len(path.split("/")))
        ):
            raise ValueError(
                "generation result contains a file-directory ancestor collision"
            )
        if paths != tuple(sorted(paths)):
            raise ValueError(
                "generation result files are not in canonical path order"
            )
        if sum(item.byte_size for item in self.files) > MAX_GENERATED_TOTAL_BYTES:
            raise ValueError(
                "generation result exceeds the total generated byte limit"
            )
        return self


type GenerationDocument = GenerationRequest | GenerationResult


def _validate_versioned_uri(value: str, label: str) -> str:
    if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be an explicitly versioned URN")
    return value


def _validate_canonical_ir_value(value: IRValue) -> None:
    if isinstance(value, ListValue):
        for item in value.items:
            _validate_canonical_ir_value(item)
    elif isinstance(value, RecordValue):
        names = tuple(entry.name for entry in value.entries)
        if names != tuple(sorted(names)):
            raise ValueError(
                "generation record value entries are not in canonical order"
            )
        for entry in value.entries:
            _validate_canonical_ir_value(entry.value)
