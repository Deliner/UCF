from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.models import (
    SEMANTIC_TOKEN_PATTERN,
    URI,
    BooleanValue,
    Digest,
    EntityKind,
    Identifier,
    IntegerValue,
    IRModel,
    Producer,
    SafeInteger,
    StringValue,
    Timestamp,
)
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    BehaviorEntityRef,
    FactAssertion,
)

RUNTIME_EVIDENCE_VERSION = "1.0.0"
RUNTIME_EVIDENCE_CAPABILITY = "org.ucf.adapter.runtime-evidence"
RUNTIME_EVIDENCE_POLICY_SCHEMA_URI = (
    "urn:ucf:runtime-evidence:policy:1.0.0"
)
RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI = (
    "urn:ucf:runtime-evidence:environment:1.0.0"
)
RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:runtime-evidence-request:1.0.0"
)
RUNTIME_EVIDENCE_RESULT_SCHEMA_URI = (
    "urn:ucf:adapter:runtime-evidence-result:1.0.0"
)
RUNTIME_EVIDENCE_IMPORT_PROCEDURE_URI = (
    "urn:ucf:runtime-evidence:recorded-import:1.0.0"
)
MAX_RUNTIME_EVIDENCE_RULES = 64
MAX_RUNTIME_STRING_VALUE_LENGTH = 128
MAX_RUNTIME_TARGET_PATH = 16

_VERSIONED_URN_PATTERN = re.compile(
    r"^urn:[a-z][a-z0-9.-]*(?::[a-z0-9][a-z0-9._-]*)+:"
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
_SAFE_STRING_PATTERN = re.compile(SEMANTIC_TOKEN_PATTERN)
_SAFE_OPAQUE_URN_PATTERN = re.compile(
    r"^urn:[a-z][a-z0-9.-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)+$"
)
type RuntimeEvidenceResultId = Annotated[
    str,
    Field(pattern=r"^result\.[0-9a-f]{64}$"),
]


class RuntimeObservationRule(IRModel):
    kind: Literal["runtime_observation_rule"]
    id: Identifier
    selector_uri: URI
    subject: BehaviorEntityRef
    assertion: FactAssertion

    @field_validator("selector_uri")
    @classmethod
    def validate_selector_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "runtime selector")

    @model_validator(mode="after")
    def validate_assertion(self) -> RuntimeObservationRule:
        if self.subject.target_kind is not EntityKind.OBSERVATION:
            raise ValueError(
                "runtime observation rule must target an observation entity"
            )
        if not 1 <= len(self.assertion.target.path) <= MAX_RUNTIME_TARGET_PATH:
            raise ValueError(
                "runtime observation target path is outside supported bounds"
            )
        value = self.assertion.value
        if isinstance(value, StringValue):
            if (
                len(value.value) > MAX_RUNTIME_STRING_VALUE_LENGTH
                or _SAFE_STRING_PATTERN.fullmatch(value.value) is None
            ):
                raise ValueError(
                    "runtime observation string value is not a bounded "
                    "semantic token"
                )
        elif not isinstance(value, (BooleanValue, IntegerValue)):
            raise ValueError(
                "runtime observation value kind is not supported"
            )
        return self


class RuntimeEvidencePolicy(IRModel):
    kind: Literal["runtime_evidence_policy"]
    runtime_evidence_version: Literal[RUNTIME_EVIDENCE_VERSION]
    schema_uri: Literal[RUNTIME_EVIDENCE_POLICY_SCHEMA_URI]
    policy_uri: URI
    secret_handling: Literal["reject"]
    personal_data_handling: Literal["reject"]
    unselected_handling: Literal["omit"]
    raw_retention: Literal["none"]
    rules: Annotated[
        tuple[RuntimeObservationRule, ...],
        Field(min_length=1, max_length=MAX_RUNTIME_EVIDENCE_RULES),
    ]

    @field_validator("policy_uri")
    @classmethod
    def validate_policy_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "runtime evidence policy")

    @model_validator(mode="after")
    def validate_rules(self) -> RuntimeEvidencePolicy:
        identifiers = tuple(rule.id for rule in self.rules)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("runtime evidence policy contains duplicate rules")
        if identifiers != tuple(sorted(identifiers)):
            raise ValueError(
                "runtime evidence policy rules are not in canonical order"
            )
        selectors = tuple(rule.selector_uri for rule in self.rules)
        if len(selectors) != len(set(selectors)):
            raise ValueError(
                "runtime evidence policy contains duplicate selectors"
            )
        projections = tuple(
            (rule.subject, rule.assertion) for rule in self.rules
        )
        if len(projections) != len(set(projections)):
            raise ValueError(
                "runtime evidence policy contains duplicate projections"
            )
        documents = {
            (
                rule.subject.document_id,
                rule.subject.ir_version,
                rule.subject.canonical_digest,
            )
            for rule in self.rules
        }
        if len(documents) != 1:
            raise ValueError(
                "runtime evidence policy rules must bind one behavior document"
            )
        return self


class RuntimeEnvironment(IRModel):
    kind: Literal["runtime_environment"]
    runtime_evidence_version: Literal[RUNTIME_EVIDENCE_VERSION]
    schema_uri: Literal[RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI]
    environment_uri: URI
    revision: Digest

    @field_validator("environment_uri")
    @classmethod
    def validate_environment_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "runtime environment")


class RuntimeEnvironmentRef(IRModel):
    kind: Literal["runtime_environment_ref"]
    schema_uri: Literal[RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI]
    schema_version: Literal[RUNTIME_EVIDENCE_VERSION]
    environment_uri: URI
    revision: Digest
    canonical_digest: Digest

    @field_validator("environment_uri")
    @classmethod
    def validate_environment_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "runtime environment")


class RuntimeSource(IRModel):
    kind: Literal["runtime_source"]
    source_uri: URI
    source_revision: Digest
    captured_at: Timestamp

    @field_validator("source_uri")
    @classmethod
    def validate_source_uri(cls, value: str) -> str:
        if _SAFE_OPAQUE_URN_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "runtime source URI must be a safe opaque URN"
            )
        return value

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ValueError(
                "runtime capture timestamp is not a valid UTC date and time"
            ) from error
        return value


class RuntimeSamplingScope(IRModel):
    kind: Literal["runtime_sampling_scope"]
    procedure_uri: URI
    completeness: Literal["partial"]
    total_known: Literal[False]

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value, "runtime sampling procedure")


class RuntimeEvidenceImportRequest(IRModel):
    kind: Literal["runtime_evidence_import_request"]
    runtime_evidence_version: Literal[RUNTIME_EVIDENCE_VERSION]
    schema_uri: Literal[RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI]
    capability: CapabilitySelection
    behavior: BehaviorDocumentRef
    source: RuntimeSource
    environment: RuntimeEnvironmentRef
    sampling: RuntimeSamplingScope
    policy: RuntimeEvidencePolicy
    procedure_uri: Literal[RUNTIME_EVIDENCE_IMPORT_PROCEDURE_URI]
    adapter_procedure_uri: URI

    @field_validator("adapter_procedure_uri")
    @classmethod
    def validate_adapter_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(
            value,
            "runtime evidence adapter procedure",
        )

    @model_validator(mode="after")
    def validate_coordinates(self) -> RuntimeEvidenceImportRequest:
        if (
            self.capability.name != RUNTIME_EVIDENCE_CAPABILITY
            or self.capability.version != RUNTIME_EVIDENCE_VERSION
        ):
            raise ValueError(
                "runtime evidence request requires the exact profile "
                "capability"
            )
        for rule in self.policy.rules:
            if (
                rule.subject.document_id != self.behavior.document_id
                or rule.subject.ir_version != self.behavior.ir_version
                or rule.subject.canonical_digest
                != self.behavior.canonical_digest
            ):
                raise ValueError(
                    "runtime evidence policy does not bind the request "
                    "behavior"
                )
        return self


class RuntimeObservationRuleRef(IRModel):
    kind: Literal["runtime_observation_rule_ref"]
    target_id: Identifier


class RuntimeObservation(IRModel):
    kind: Literal["runtime_observation"]
    rule: RuntimeObservationRuleRef


class RuntimeSanitizationSummary(IRModel):
    kind: Literal["runtime_sanitization_summary"]
    selected_rule_count: Annotated[
        SafeInteger,
        Field(ge=1, le=MAX_RUNTIME_EVIDENCE_RULES),
    ]
    forbidden_match_count: Literal[0]
    raw_retained: Literal[False]


class RuntimePolicyRejectionCode(StrEnum):
    SELECTED_PERSONAL_DATA = "selected_personal_data"
    SELECTED_SECRET = "selected_secret"
    SELECTED_VALUE_NOT_ALLOWED = "selected_value_not_allowed"


class _RuntimeEvidenceResultBase(IRModel):
    kind: Literal["runtime_evidence_result"]
    runtime_evidence_version: Literal[RUNTIME_EVIDENCE_VERSION]
    schema_uri: Literal[RUNTIME_EVIDENCE_RESULT_SCHEMA_URI]
    id: RuntimeEvidenceResultId
    request: RuntimeEvidenceImportRequest
    producer: Producer
    capability: CapabilitySelection
    procedure_uri: URI

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(
            value,
            "runtime evidence result procedure",
        )

    @model_validator(mode="after")
    def validate_profile_coordinates(self) -> _RuntimeEvidenceResultBase:
        if (
            self.capability.name != RUNTIME_EVIDENCE_CAPABILITY
            or self.capability.version != RUNTIME_EVIDENCE_VERSION
        ):
            raise ValueError(
                "runtime evidence result requires the exact profile "
                "capability"
            )
        if self.procedure_uri != self.request.adapter_procedure_uri:
            raise ValueError(
                "runtime evidence result procedure differs from the request"
            )
        return self


class RuntimeEvidenceAcceptedResult(_RuntimeEvidenceResultBase):
    status: Literal["accepted"]
    sanitization: RuntimeSanitizationSummary
    observations: Annotated[
        tuple[RuntimeObservation, ...],
        Field(min_length=1, max_length=MAX_RUNTIME_EVIDENCE_RULES),
    ]


class RuntimeEvidenceRejectedResult(_RuntimeEvidenceResultBase):
    status: Literal["rejected"]
    reason_codes: Annotated[
        tuple[RuntimePolicyRejectionCode, ...],
        Field(min_length=1, max_length=3),
    ]


type RuntimeEvidenceResult = Annotated[
    RuntimeEvidenceAcceptedResult | RuntimeEvidenceRejectedResult,
    Field(discriminator="status"),
]


type RuntimeEvidenceProfileDocument = (
    RuntimeEnvironment
    | RuntimeEvidenceAcceptedResult
    | RuntimeEvidenceImportRequest
    | RuntimeEvidencePolicy
    | RuntimeEvidenceRejectedResult
)


def _validate_versioned_uri(value: str, label: str) -> str:
    if _VERSIONED_URN_PATTERN.fullmatch(value) is None:
        raise ValueError(
            f"{label} URI is not a safe explicitly versioned URN"
        )
    return value
