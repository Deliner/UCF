from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from ucf.ir.codec import CURRENT_IR_VERSION
from ucf.ir.models import (
    URI,
    Check,
    Digest,
    DomainTarget,
    EntityKind,
    Identifier,
    IRModel,
    IRValue,
    Producer,
    Timestamp,
    _validate_utc_timestamp,
)

CURRENT_TRUST_IR_VERSION = "1.0.0"
CONFIDENCE_PATTERN = r"^(?:0|1|0\.[0-9]*[1-9])$"
_CONFIDENCE_PATTERN = re.compile(CONFIDENCE_PATTERN)

type ConfidenceValue = Annotated[
    str,
    StringConstraints(max_length=64, pattern=CONFIDENCE_PATTERN),
]


class TrustRecordKind(StrEnum):
    SOURCE_RECORD = "source_record"
    DECLARATION = "declaration"
    OBSERVED_FACT = "observed_fact"
    BEHAVIOR_CANDIDATE = "behavior_candidate"
    MAPPING = "mapping"
    CLAIM = "claim"


class ClaimLevel(StrEnum):
    OBSERVED = "observed"
    DECLARED = "declared"
    MAPPED = "mapped"
    TESTED = "tested"
    VERIFIED = "verified"


class BehaviorDocumentRef(IRModel):
    kind: Literal["behavior_document_ref"]
    document_id: Identifier
    ir_version: Literal[CURRENT_IR_VERSION]
    canonical_digest: Digest


class BehaviorEntityRef(IRModel):
    kind: Literal["behavior_entity_ref"]
    document_id: Identifier
    ir_version: Literal[CURRENT_IR_VERSION]
    canonical_digest: Digest
    target_kind: EntityKind
    target_id: Identifier


class RecordRef(IRModel):
    kind: Literal["record_ref"]
    target_kind: TrustRecordKind
    target_id: Identifier


class FactAssertion(IRModel):
    kind: Literal["fact_assertion"]
    target: DomainTarget
    value: IRValue


class Confidence(IRModel):
    kind: Literal["confidence"]
    scale: Literal["decimal-0-to-1"]
    value: ConfidenceValue

    @field_validator("value")
    @classmethod
    def validate_canonical_confidence(cls, value: str) -> str:
        if _CONFIDENCE_PATTERN.fullmatch(value) is None:
            raise ValueError("confidence value is not in canonical form")
        return value


class SourceRecord(IRModel):
    kind: Literal[TrustRecordKind.SOURCE_RECORD]
    id: Identifier
    source_uri: URI
    source_revision: Digest
    producer: Producer
    captured_at: Timestamp

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: str) -> str:
        return _validate_utc_timestamp(value)


class Declaration(IRModel):
    kind: Literal[TrustRecordKind.DECLARATION]
    id: Identifier
    subject: BehaviorEntityRef
    trace: RecordRef


class ObservedFact(IRModel):
    kind: Literal[TrustRecordKind.OBSERVED_FACT]
    id: Identifier
    subject: BehaviorEntityRef
    assertion: FactAssertion
    trace: RecordRef


class BehaviorCandidate(IRModel):
    kind: Literal[TrustRecordKind.BEHAVIOR_CANDIDATE]
    id: Identifier
    candidate_type: Literal["mapping"]
    subjects: Annotated[tuple[RecordRef, ...], Field(min_length=2)]
    confidence: Confidence
    trace: RecordRef


class TrustMapping(IRModel):
    kind: Literal[TrustRecordKind.MAPPING]
    id: Identifier
    declaration: RecordRef
    observation: RecordRef
    relationship: Literal["same-behavior-slot"]
    disposition: Literal["match", "conflict"]
    trace: RecordRef


class ObservedClaimBasis(IRModel):
    kind: Literal["observed_claim_basis"]
    fact: RecordRef


class DeclaredClaimBasis(IRModel):
    kind: Literal["declared_claim_basis"]
    declaration: RecordRef


class MappedClaimBasis(IRModel):
    kind: Literal["mapped_claim_basis"]
    mapping: RecordRef


type EvidenceRef = Annotated[
    BehaviorEntityRef | RecordRef,
    Field(discriminator="kind"),
]


class TestedClaimBasis(IRModel):
    kind: Literal["tested_claim_basis"]
    evidence: EvidenceRef
    artifact: RecordRef
    check: Check
    environment: Digest
    producer: Producer


class VerifiedClaimBasis(IRModel):
    kind: Literal["verified_claim_basis"]


type ClaimBasis = Annotated[
    ObservedClaimBasis
    | DeclaredClaimBasis
    | MappedClaimBasis
    | TestedClaimBasis
    | VerifiedClaimBasis,
    Field(discriminator="kind"),
]


class Claim(IRModel):
    kind: Literal[TrustRecordKind.CLAIM]
    id: Identifier
    level: ClaimLevel
    subject: BehaviorEntityRef
    basis: ClaimBasis
    trace: RecordRef


type TrustRecord = Annotated[
    SourceRecord
    | Declaration
    | ObservedFact
    | BehaviorCandidate
    | TrustMapping
    | Claim,
    Field(discriminator="kind"),
]


class TrustIR(IRModel):
    kind: Literal["trust_ir"]
    trust_ir_version: Literal[CURRENT_TRUST_IR_VERSION]
    document_id: Identifier
    subject_document: BehaviorDocumentRef
    records: tuple[TrustRecord, ...]
