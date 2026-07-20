from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ucf.adapter_protocol import CapabilitySelection
from ucf.inventory import InventoryRecordRef, InventorySnapshot
from ucf.ir.models import (
    URI,
    BehaviorIR,
    Check,
    Digest,
    IRModel,
    IRValue,
    ListValue,
    PortRef,
    Producer,
    RecordValue,
    Timestamp,
)
from ucf.ir.trust_models import BehaviorDocumentRef, BehaviorEntityRef
from ucf.ir.validation import validate_ir_value
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
)

IMPLEMENTATION_EVIDENCE_VERSION = "1.0.0"
IMPLEMENTATION_MAPPING_CAPABILITY = "org.ucf.adapter.mapping"
IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:implementation-mapping-request:1.0.0"
)
IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI = (
    "urn:ucf:adapter:implementation-mapping-result:1.0.0"
)
IMPLEMENTATION_MAPPING_PROCEDURE_URI = (
    "urn:ucf:implementation-evidence:map:1.0.0"
)
EXECUTION_VERIFICATION_CAPABILITY = "org.ucf.adapter.verification"
EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:execution-verification-request:1.0.0"
)
EXECUTION_VERIFICATION_RESULT_SCHEMA_URI = (
    "urn:ucf:adapter:execution-verification-result:1.0.0"
)
EXECUTION_VERIFICATION_PROCEDURE_URI = (
    "urn:ucf:implementation-evidence:verify:1.0.0"
)
MAX_IMPLEMENTATION_BINDINGS = 256
type ImplementationMappingResultId = Annotated[
    str,
    Field(pattern=r"^mapping\.[0-9a-f]{64}$"),
]
type ExecutionVerificationResultId = Annotated[
    str,
    Field(pattern=r"^result\.[0-9a-f]{64}$"),
]

_VERSIONED_URN_PATTERN = re.compile(
    r"^urn:[a-z][a-z0-9.-]*(?::[a-z0-9][a-z0-9._-]*)+:"
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)


class OnboardingBundleBinding(IRModel):
    kind: Literal["onboarding_bundle_binding"]
    schema_uri: Literal[ONBOARDING_BUNDLE_SCHEMA_URI]
    schema_version: Literal[ONBOARDING_VERSION]
    canonical_digest: Digest


class ImplementationMappingRequest(IRModel):
    kind: Literal["implementation_mapping_request"]
    implementation_evidence_version: Literal[
        IMPLEMENTATION_EVIDENCE_VERSION
    ]
    schema_uri: Literal[IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI]
    capability: CapabilitySelection
    profile_procedure_uri: Literal[IMPLEMENTATION_MAPPING_PROCEDURE_URI]
    adapter_procedure_uri: URI
    onboarding: OnboardingBundleBinding
    behavior: BehaviorIR
    inventory: InventorySnapshot
    targets: Annotated[
        tuple[BehaviorEntityRef, ...],
        Field(min_length=1, max_length=MAX_IMPLEMENTATION_BINDINGS),
    ]

    @field_validator("adapter_procedure_uri")
    @classmethod
    def validate_adapter_procedure_uri(cls, value: str) -> str:
        if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "mapping adapter procedure must be an explicitly versioned URN"
            )
        return value

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> ImplementationMappingRequest:
        if (
            self.capability.name != IMPLEMENTATION_MAPPING_CAPABILITY
            or self.capability.version != IMPLEMENTATION_EVIDENCE_VERSION
        ):
            raise ValueError(
                "mapping request requires the exact mapping capability"
            )
        identities = tuple(
            (target.target_kind.value, target.target_id)
            for target in self.targets
        )
        if len(identities) != len(set(identities)):
            raise ValueError("mapping request contains duplicate targets")
        if identities != tuple(sorted(identities)):
            raise ValueError(
                "mapping request targets are not in canonical order"
            )
        return self


class ImplementationBinding(IRModel):
    kind: Literal["implementation_binding"]
    behavior: BehaviorEntityRef
    source_records: Annotated[
        tuple[InventoryRecordRef, ...],
        Field(min_length=1, max_length=MAX_IMPLEMENTATION_BINDINGS),
    ]

    @model_validator(mode="after")
    def validate_source_records(self) -> ImplementationBinding:
        identities = tuple(
            (reference.target_kind.value, reference.target_id)
            for reference in self.source_records
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "implementation binding contains duplicate source records"
            )
        if identities != tuple(sorted(identities)):
            raise ValueError(
                "implementation binding source records are not in "
                "canonical order"
            )
        return self


class ImplementationMappingResult(IRModel):
    kind: Literal["implementation_mapping_result"]
    implementation_evidence_version: Literal[
        IMPLEMENTATION_EVIDENCE_VERSION
    ]
    schema_uri: Literal[IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI]
    id: ImplementationMappingResultId
    status: Literal["complete"]
    request: ImplementationMappingRequest
    producer: Producer
    capability: CapabilitySelection
    procedure_uri: URI
    bindings: Annotated[
        tuple[ImplementationBinding, ...],
        Field(min_length=1, max_length=MAX_IMPLEMENTATION_BINDINGS),
    ]

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "mapping result procedure must be an explicitly versioned URN"
            )
        return value

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> ImplementationMappingResult:
        if (
            self.capability.name != IMPLEMENTATION_MAPPING_CAPABILITY
            or self.capability.version != IMPLEMENTATION_EVIDENCE_VERSION
        ):
            raise ValueError(
                "mapping result requires the exact mapping capability"
            )
        if self.procedure_uri != self.request.adapter_procedure_uri:
            raise ValueError(
                "mapping result procedure differs from the request"
            )
        identities = tuple(
            (binding.behavior.target_kind.value, binding.behavior.target_id)
            for binding in self.bindings
        )
        if len(identities) != len(set(identities)):
            raise ValueError("mapping result contains duplicate bindings")
        if identities != tuple(sorted(identities)):
            raise ValueError(
                "mapping result bindings are not in canonical order"
            )
        return self


class ImplementationMappingResultRef(IRModel):
    kind: Literal["implementation_mapping_result_ref"]
    schema_uri: Literal[IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI]
    schema_version: Literal[IMPLEMENTATION_EVIDENCE_VERSION]
    target_id: ImplementationMappingResultId
    canonical_digest: Digest


class ImplementationSource(IRModel):
    kind: Literal["implementation_source"]
    subject_uri: URI
    source_revision: Digest
    records: Annotated[
        tuple[InventoryRecordRef, ...],
        Field(min_length=1, max_length=MAX_IMPLEMENTATION_BINDINGS),
    ]

    @model_validator(mode="after")
    def validate_records(self) -> ImplementationSource:
        identities = tuple(
            (reference.target_kind.value, reference.target_id)
            for reference in self.records
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "implementation source contains duplicate records"
            )
        if identities != tuple(sorted(identities)):
            raise ValueError(
                "implementation source records are not in canonical order"
            )
        return self


class ExecutionEnvironment(IRModel):
    kind: Literal["execution_environment"]
    identity_uri: URI
    revision: Digest

    @field_validator("identity_uri")
    @classmethod
    def validate_identity_uri(cls, value: str) -> str:
        if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "execution environment identity must be an explicitly "
                "versioned URN"
            )
        return value


class ExecutionPortValue(IRModel):
    kind: Literal["execution_port_value"]
    port: PortRef
    value: IRValue

    @model_validator(mode="after")
    def validate_value(self) -> ExecutionPortValue:
        validate_ir_value(self.value)
        _validate_canonical_ir_value(self.value)
        return self


class ExecutionVerificationRequest(IRModel):
    kind: Literal["execution_verification_request"]
    implementation_evidence_version: Literal[
        IMPLEMENTATION_EVIDENCE_VERSION
    ]
    schema_uri: Literal[EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI]
    capability: CapabilitySelection
    profile_procedure_uri: Literal[EXECUTION_VERIFICATION_PROCEDURE_URI]
    adapter_procedure_uri: URI
    mapping: ImplementationMappingResultRef
    base_behavior: BehaviorDocumentRef
    subject: BehaviorEntityRef
    inputs: Annotated[
        tuple[ExecutionPortValue, ...],
        Field(max_length=MAX_IMPLEMENTATION_BINDINGS),
    ]
    expected_outputs: Annotated[
        tuple[ExecutionPortValue, ...],
        Field(max_length=MAX_IMPLEMENTATION_BINDINGS),
    ]
    source: ImplementationSource
    environment: ExecutionEnvironment
    check: Check

    @field_validator("adapter_procedure_uri")
    @classmethod
    def validate_adapter_procedure_uri(cls, value: str) -> str:
        if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "verification adapter procedure must be an explicitly "
                "versioned URN"
            )
        return value

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> ExecutionVerificationRequest:
        if (
            self.capability.name != EXECUTION_VERIFICATION_CAPABILITY
            or self.capability.version != IMPLEMENTATION_EVIDENCE_VERSION
        ):
            raise ValueError(
                "verification request requires the exact verification "
                "capability"
            )
        if _VERSIONED_URN_PATTERN.fullmatch(self.check.procedure_uri) is None:
            raise ValueError(
                "verification check procedure must be an explicitly "
                "versioned URN"
            )
        if (
            self.subject.document_id != self.base_behavior.document_id
            or self.subject.ir_version != self.base_behavior.ir_version
            or self.subject.canonical_digest
            != self.base_behavior.canonical_digest
        ):
            raise ValueError(
                "verification subject does not bind the base behavior"
            )
        self._validate_port_values(self.inputs, direction="input")
        self._validate_port_values(
            self.expected_outputs,
            direction="output",
        )
        return self

    def _validate_port_values(
        self,
        values: tuple[ExecutionPortValue, ...],
        *,
        direction: Literal["input", "output"],
    ) -> None:
        identities = tuple(
            (
                value.port.owner.target_kind.value,
                value.port.owner.target_id,
                value.port.direction,
                value.port.name,
            )
            for value in values
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                f"verification {direction} values contain duplicate ports"
            )
        if identities != tuple(sorted(identities)):
            raise ValueError(
                f"verification {direction} values are not in canonical order"
            )
        for value in values:
            if value.port.direction != direction:
                raise ValueError(
                    f"verification {direction} value has wrong direction"
                )
            if (
                value.port.owner.target_kind
                is not self.subject.target_kind
                or value.port.owner.target_id != self.subject.target_id
            ):
                raise ValueError(
                    f"verification {direction} value owner differs from subject"
                )


class ExecutionVerificationResult(IRModel):
    kind: Literal["execution_verification_result"]
    implementation_evidence_version: Literal[
        IMPLEMENTATION_EVIDENCE_VERSION
    ]
    schema_uri: Literal[EXECUTION_VERIFICATION_RESULT_SCHEMA_URI]
    id: ExecutionVerificationResultId
    status: Literal["completed"]
    request: ExecutionVerificationRequest
    outcome: Literal["passed", "failed", "error"]
    executed_at: Timestamp
    producer: Producer
    capability: CapabilitySelection
    procedure_uri: URI

    @field_validator("executed_at")
    @classmethod
    def validate_executed_at(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ValueError(
                "execution timestamp is not a valid whole-second UTC time"
            ) from error
        return value

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "verification result procedure must be an explicitly "
                "versioned URN"
            )
        return value

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> ExecutionVerificationResult:
        if (
            self.capability.name != EXECUTION_VERIFICATION_CAPABILITY
            or self.capability.version != IMPLEMENTATION_EVIDENCE_VERSION
        ):
            raise ValueError(
                "verification result requires the exact verification "
                "capability"
            )
        if self.procedure_uri != self.request.adapter_procedure_uri:
            raise ValueError(
                "verification result procedure differs from the request"
            )
        return self


type ImplementationEvidenceProfileDocument = (
    ExecutionVerificationRequest
    | ExecutionVerificationResult
    | ImplementationMappingRequest
    | ImplementationMappingResult
)


def _validate_canonical_ir_value(value: IRValue) -> None:
    if isinstance(value, ListValue):
        for item in value.items:
            _validate_canonical_ir_value(item)
    elif isinstance(value, RecordValue):
        names = tuple(entry.name for entry in value.entries)
        if names != tuple(sorted(names)):
            raise ValueError(
                "execution record value entries are not in canonical order"
            )
        for entry in value.entries:
            _validate_canonical_ir_value(entry.value)
