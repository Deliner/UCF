from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    ImplementationMappingResultRef,
)
from ucf.inventory import INVENTORY_SCHEMA_URI, INVENTORY_VERSION
from ucf.ir import CURRENT_TRUST_IR_VERSION
from ucf.ir.models import URI, Digest, Identifier, IRModel, SemanticToken
from ucf.ir.trust_models import BehaviorDocumentRef
from ucf.ratchet.models import BehaviorSubjectKey, OnboardingBundleRef

EVIDENCE_STATUS_VERSION = "1.0.0"
VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI = (
    "urn:ucf:evidence-status:envelope:1.0.0"
)
VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI = (
    "urn:ucf:evidence-status:assessment:1.0.0"
)
EVIDENCE_RECORD_PROCEDURE_URI = "urn:ucf:evidence-status:record:1.0.0"
EVIDENCE_ASSESS_PROCEDURE_URI = "urn:ucf:evidence-status:assess:1.0.0"
BEHAVIOR_PROJECTION_PROCEDURE_URI = (
    "urn:ucf:evidence-status:project-behavior:1.0.0"
)
SOURCE_PROJECTION_PROCEDURE_URI = (
    "urn:ucf:evidence-status:project-source:1.0.0"
)
MAPPING_PROJECTION_PROCEDURE_URI = (
    "urn:ucf:evidence-status:project-mapping:1.0.0"
)
EXECUTION_PROJECTION_PROCEDURE_URI = (
    "urn:ucf:evidence-status:project-execution:1.0.0"
)
MAX_PROJECTION_MEMBERS = 4096
MAX_STATUS_REASONS = 13

type VerificationEvidenceEnvelopeId = Annotated[
    str,
    StringConstraints(pattern=r"^envelope\.[0-9a-f]{64}$"),
]
type VerificationEvidenceAssessmentId = Annotated[
    str,
    StringConstraints(pattern=r"^assessment\.[0-9a-f]{64}$"),
]
type ExecutionVerificationResultId = Annotated[
    str,
    StringConstraints(pattern=r"^result\.[0-9a-f]{64}$"),
]
type TestedClaimId = Annotated[
    str,
    StringConstraints(pattern=r"^claim\.tested\.[0-9a-f]{64}$"),
]


class EvidenceStatus(StrEnum):
    FRESH = "fresh"
    INDETERMINATE = "indeterminate"
    STALE = "stale"


class EvidenceStatusReasonCode(StrEnum):
    BEHAVIOR_SUBJECT_CHANGED = "behavior_subject_changed"
    CHECK_CHANGED = "check_changed"
    CURRENT_CONTEXT_UNAVAILABLE = "current_context_unavailable"
    ENVIRONMENT_CHANGED = "environment_changed"
    EXPECTED_OUTPUT_CHANGED = "expected_output_changed"
    INPUT_CHANGED = "input_changed"
    INVENTORY_ADAPTER_CHANGED = "inventory_adapter_changed"
    MAPPING_ADAPTER_CHANGED = "mapping_adapter_changed"
    MAPPING_BINDING_CHANGED = "mapping_binding_changed"
    PROCEDURE_CHANGED = "procedure_changed"
    RESULT_CHANGED = "result_changed"
    SOURCE_BINDING_CHANGED = "source_binding_changed"
    VERIFICATION_ADAPTER_CHANGED = "verification_adapter_changed"


class EvidenceProjectionMember(IRModel):
    kind: Literal["evidence_projection_member"]
    target_kind: SemanticToken
    target_id: Identifier
    digest: Digest


class _EvidenceProjection(IRModel):
    members: Annotated[
        tuple[EvidenceProjectionMember, ...],
        Field(min_length=1, max_length=MAX_PROJECTION_MEMBERS),
    ]
    digest: Digest

    @model_validator(mode="after")
    def validate_projection(self) -> _EvidenceProjection:
        keys = tuple(
            (member.target_kind, member.target_id)
            for member in self.members
        )
        if len(keys) != len(set(keys)):
            raise ValueError("evidence projection contains duplicate members")
        if keys != tuple(sorted(keys)):
            raise ValueError(
                "evidence projection members are not in canonical order"
            )
        expected = _canonical_digest(
            self.model_dump(mode="json", exclude={"digest"})
        )
        if self.digest != expected:
            raise ValueError(
                "evidence projection digest does not match its exact members"
            )
        return self


class BehaviorEvidenceProjection(_EvidenceProjection):
    kind: Literal["behavior_evidence_projection"]
    procedure_uri: Literal[BEHAVIOR_PROJECTION_PROCEDURE_URI]


class SourceEvidenceProjection(_EvidenceProjection):
    kind: Literal["source_evidence_projection"]
    procedure_uri: Literal[SOURCE_PROJECTION_PROCEDURE_URI]


class MappingEvidenceProjection(_EvidenceProjection):
    kind: Literal["mapping_evidence_projection"]
    procedure_uri: Literal[MAPPING_PROJECTION_PROCEDURE_URI]


class ExecutionEvidenceProjection(_EvidenceProjection):
    kind: Literal["execution_evidence_projection"]
    procedure_uri: Literal[EXECUTION_PROJECTION_PROCEDURE_URI]


class RecordedEvidenceCoordinates(IRModel):
    kind: Literal["recorded_evidence_coordinates"]
    behavior: BehaviorEvidenceProjection
    source: SourceEvidenceProjection
    mapping: MappingEvidenceProjection
    execution: ExecutionEvidenceProjection


class InventorySnapshotRef(IRModel):
    kind: Literal["inventory_snapshot_ref"]
    schema_uri: Literal[INVENTORY_SCHEMA_URI]
    schema_version: Literal[INVENTORY_VERSION]
    subject_uri: URI
    source_revision: Digest
    canonical_digest: Digest


class EvidenceTraceCoordinates(IRModel):
    kind: Literal["evidence_trace_coordinates"]
    behavior: BehaviorDocumentRef
    onboarding: OnboardingBundleRef
    inventory: InventorySnapshotRef
    mapping: ImplementationMappingResultRef


class ExecutionVerificationResultRef(IRModel):
    kind: Literal["execution_verification_result_ref"]
    schema_uri: Literal[EXECUTION_VERIFICATION_RESULT_SCHEMA_URI]
    schema_version: Literal[IMPLEMENTATION_EVIDENCE_VERSION]
    target_id: ExecutionVerificationResultId
    canonical_digest: Digest


class CurrentEvidenceCoordinates(IRModel):
    kind: Literal["current_evidence_coordinates"]
    subject: BehaviorSubjectKey
    verification_result: ExecutionVerificationResultRef
    behavior: BehaviorEvidenceProjection
    source: SourceEvidenceProjection
    mapping: MappingEvidenceProjection
    execution: ExecutionEvidenceProjection
    trace: EvidenceTraceCoordinates

    @model_validator(mode="after")
    def validate_subject_trace(self) -> CurrentEvidenceCoordinates:
        if self.trace.inventory.subject_uri != self.subject.subject_uri:
            raise ValueError(
                "current inventory subject differs from the evidence subject"
            )
        _require_subject_member(self.subject, self.behavior)
        _require_subject_member(self.subject, self.mapping)
        return self


class TrustClaimRef(IRModel):
    kind: Literal["trust_claim_ref"]
    trust_ir_version: Literal[CURRENT_TRUST_IR_VERSION]
    document_id: Identifier
    canonical_digest: Digest
    target_id: TestedClaimId


class VerificationEvidenceEnvelope(IRModel):
    kind: Literal["verification_evidence_envelope"]
    evidence_status_version: Literal[EVIDENCE_STATUS_VERSION]
    schema_uri: Literal[VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI]
    id: VerificationEvidenceEnvelopeId
    procedure_uri: Literal[EVIDENCE_RECORD_PROCEDURE_URI]
    verification_result: ExecutionVerificationResultRef
    claim: TrustClaimRef
    subject: BehaviorSubjectKey
    recorded: RecordedEvidenceCoordinates
    trace: EvidenceTraceCoordinates

    @model_validator(mode="after")
    def validate_envelope(self) -> VerificationEvidenceEnvelope:
        if self.trace.inventory.subject_uri != self.subject.subject_uri:
            raise ValueError(
                "inventory trace subject differs from the evidence subject"
            )
        _require_subject_member(self.subject, self.recorded.behavior)
        _require_subject_member(self.subject, self.recorded.mapping)
        if self.id != _content_id("envelope", self):
            raise ValueError(
                "verification evidence envelope ID does not match its content"
            )
        return self


class VerificationEvidenceEnvelopeRef(IRModel):
    kind: Literal["verification_evidence_envelope_ref"]
    schema_uri: Literal[VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI]
    schema_version: Literal[EVIDENCE_STATUS_VERSION]
    target_id: VerificationEvidenceEnvelopeId
    canonical_digest: Digest


class EvidenceStatusReason(IRModel):
    kind: Literal["evidence_status_reason"]
    code: EvidenceStatusReasonCode
    recorded: Digest | None
    current: Digest | None

    @model_validator(mode="after")
    def validate_coordinates(self) -> EvidenceStatusReason:
        unavailable = (
            self.code is EvidenceStatusReasonCode.CURRENT_CONTEXT_UNAVAILABLE
        )
        if unavailable != (
            self.recorded is None and self.current is None
        ):
            raise ValueError(
                "evidence status reason has incompatible coordinate shape"
            )
        if not unavailable and (
            self.recorded is None or self.current is None
        ):
            raise ValueError(
                "stale evidence reason requires both coordinate digests"
            )
        return self


class VerificationEvidenceAssessment(IRModel):
    kind: Literal["verification_evidence_assessment"]
    evidence_status_version: Literal[EVIDENCE_STATUS_VERSION]
    schema_uri: Literal[VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI]
    id: VerificationEvidenceAssessmentId
    procedure_uri: Literal[EVIDENCE_ASSESS_PROCEDURE_URI]
    envelope: VerificationEvidenceEnvelopeRef
    status: EvidenceStatus
    current: CurrentEvidenceCoordinates | None
    reasons: Annotated[
        tuple[EvidenceStatusReason, ...],
        Field(max_length=MAX_STATUS_REASONS),
    ]

    @model_validator(mode="after")
    def validate_assessment(self) -> VerificationEvidenceAssessment:
        codes = tuple(reason.code.value for reason in self.reasons)
        if len(codes) != len(set(codes)):
            raise ValueError("evidence assessment contains duplicate reasons")
        if codes != tuple(sorted(codes)):
            raise ValueError(
                "evidence assessment reasons are not in canonical order"
            )
        unavailable = (
            len(self.reasons) == 1
            and self.reasons[0].code
            is EvidenceStatusReasonCode.CURRENT_CONTEXT_UNAVAILABLE
        )
        if self.status is EvidenceStatus.FRESH:
            valid_shape = self.current is not None and not self.reasons
        elif self.status is EvidenceStatus.STALE:
            valid_shape = (
                self.current is not None
                and bool(self.reasons)
                and not unavailable
            )
        else:
            valid_shape = self.current is None and unavailable
        if not valid_shape:
            raise ValueError(
                "evidence assessment status has an incompatible shape"
            )
        if self.id != _content_id("assessment", self):
            raise ValueError(
                "verification evidence assessment ID does not match its content"
            )
        return self


type EvidenceStatusDocument = (
    VerificationEvidenceAssessment | VerificationEvidenceEnvelope
)


def _require_subject_member(
    subject: BehaviorSubjectKey,
    projection: _EvidenceProjection,
) -> None:
    if not any(
        member.target_kind == subject.target_kind.value
        and member.target_id == subject.target_id
        for member in projection.members
    ):
        raise ValueError(
            "evidence subject is absent from a required projection"
        )


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _canonical_digest(value: object) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(_canonical_bytes(value)).hexdigest(),
    )


def _content_id(prefix: str, document: IRModel) -> str:
    return (
        f"{prefix}."
        + hashlib.sha256(
            _canonical_bytes(
                document.model_dump(mode="json", exclude={"id"})
            )
        ).hexdigest()
    )
