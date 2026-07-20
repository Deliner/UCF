from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from ucf.ir.codec import (
    CURRENT_IR_VERSION,
    MAX_SAFE_INTEGER,
    MIN_SAFE_INTEGER,
    SEMANTIC_VERSION,
)

IDENTIFIER_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
SEMANTIC_TOKEN_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
QUALIFIED_NAME_PATTERN = (
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
    r"(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$"
)
URI_PATTERN = r"^[a-z][a-z0-9+.-]*:[^\s]+$"
TIMESTAMP_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
DIGEST_PATTERN = r"^[0-9a-f]{64}$"
DECIMAL_SCHEMA_PATTERN = (
    r"^(?:0|[1-9][0-9]*|-[1-9][0-9]*|"
    r"-?(?:0|[1-9][0-9]*)\.[0-9]*[1-9])$"
)
DECIMAL_PATTERN = re.compile(
    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$"
)

type Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,
    ),
]
type SemanticToken = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=255,
        pattern=SEMANTIC_TOKEN_PATTERN,
    ),
]
type QualifiedName = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=255,
        pattern=QUALIFIED_NAME_PATTERN,
    ),
]
type URI = Annotated[
    str,
    StringConstraints(min_length=3, max_length=2048, pattern=URI_PATTERN),
]
type Timestamp = Annotated[
    str,
    StringConstraints(pattern=TIMESTAMP_PATTERN),
]
type DigestValue = Annotated[
    str,
    StringConstraints(pattern=DIGEST_PATTERN),
]
type SafeInteger = Annotated[
    int,
    Field(ge=MIN_SAFE_INTEGER, le=MAX_SAFE_INTEGER),
]
type CanonicalDecimal = Annotated[
    str,
    StringConstraints(pattern=DECIMAL_SCHEMA_PATTERN),
]
type NormalizedVersion = Annotated[
    str,
    StringConstraints(pattern=SEMANTIC_VERSION.pattern),
]


def _validate_utc_timestamp(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError("timestamp is not a valid UTC date and time") from error
    return value


class EntityKind(StrEnum):
    ACTION = "action"
    USE_CASE = "use_case"
    STEP = "step"
    BINDING = "binding"
    EFFECT = "effect"
    OBSERVATION = "observation"
    INVARIANT = "invariant"
    PROVENANCE = "provenance"
    VERIFICATION_EVIDENCE = "verification_evidence"
    CAPABILITY_REQUIREMENT = "capability_requirement"


class ValueKind(StrEnum):
    NULL = "null"
    BOOLEAN = "boolean"
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    TIMESTAMP = "timestamp"
    LIST = "list"
    RECORD = "record"


class IRModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


class EntityRef(IRModel):
    kind: Literal["entity_ref"]
    target_kind: EntityKind
    target_id: Identifier


type NonEmptyEntityRefs = Annotated[
    tuple[EntityRef, ...],
    Field(min_length=1),
]


class Port(IRModel):
    kind: Literal["port"]
    name: Identifier
    value_kind: ValueKind
    required: bool


class PortRef(IRModel):
    kind: Literal["port_ref"]
    owner: EntityRef
    direction: Literal["input", "output"]
    name: Identifier


class NullValue(IRModel):
    kind: Literal["null"]


class BooleanValue(IRModel):
    kind: Literal["boolean"]
    value: bool


class StringValue(IRModel):
    kind: Literal["string"]
    value: str


class IntegerValue(IRModel):
    kind: Literal["integer"]
    value: SafeInteger


class DecimalValue(IRModel):
    kind: Literal["decimal"]
    value: CanonicalDecimal

    @field_validator("value")
    @classmethod
    def validate_canonical_decimal(cls, value: str) -> str:
        if DECIMAL_PATTERN.fullmatch(value) is None or value == "-0":
            raise ValueError("decimal value is not in canonical form")
        return value


class TimestampValue(IRModel):
    kind: Literal["timestamp"]
    value: Timestamp

    @field_validator("value")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        return _validate_utc_timestamp(value)


class ListValue(IRModel):
    kind: Literal["list"]
    items: tuple[IRValue, ...]


class RecordEntry(IRModel):
    kind: Literal["record_entry"]
    name: Identifier
    value: IRValue


class RecordValue(IRModel):
    kind: Literal["record"]
    entries: tuple[RecordEntry, ...]


type IRValue = Annotated[
    NullValue
    | BooleanValue
    | StringValue
    | IntegerValue
    | DecimalValue
    | TimestampValue
    | ListValue
    | RecordValue,
    Field(discriminator="kind"),
]


class DomainTarget(IRModel):
    kind: Literal["domain_target"]
    subject: SemanticToken
    path: tuple[SemanticToken, ...]


class DeclaredRule(IRModel):
    kind: Literal["declared_rule"]
    dialect: URI
    statement: Annotated[str, StringConstraints(min_length=1)]


class Digest(IRModel):
    kind: Literal["digest"]
    algorithm: Literal["sha-256"]
    value: DigestValue


class ArtifactSource(IRModel):
    kind: Literal["artifact_source"]
    uri: URI
    revision: Digest


class Producer(IRModel):
    kind: Literal["producer"]
    name: QualifiedName
    version: NormalizedVersion


class Check(IRModel):
    kind: Literal["check"]
    id: Identifier
    version: NormalizedVersion
    procedure_uri: URI


class Action(IRModel):
    kind: Literal[EntityKind.ACTION]
    id: Identifier
    input_ports: tuple[Port, ...]
    output_ports: tuple[Port, ...]
    effects: tuple[EntityRef, ...]
    requires: tuple[EntityRef, ...]
    provenance: EntityRef


class UseCase(IRModel):
    kind: Literal[EntityKind.USE_CASE]
    id: Identifier
    input_ports: tuple[Port, ...]
    output_ports: tuple[Port, ...]
    steps: tuple[EntityRef, ...]
    invariants: tuple[EntityRef, ...]
    requires: tuple[EntityRef, ...]
    provenance: EntityRef


class Step(IRModel):
    kind: Literal[EntityKind.STEP]
    id: Identifier
    action: EntityRef
    bindings: tuple[EntityRef, ...]
    effects: tuple[EntityRef, ...]
    observations: tuple[EntityRef, ...]
    requires: tuple[EntityRef, ...]
    provenance: EntityRef


type BindingSource = Annotated[
    PortRef
    | NullValue
    | BooleanValue
    | StringValue
    | IntegerValue
    | DecimalValue
    | TimestampValue
    | ListValue
    | RecordValue,
    Field(discriminator="kind"),
]


class Binding(IRModel):
    kind: Literal[EntityKind.BINDING]
    id: Identifier
    target: PortRef
    source: BindingSource
    provenance: EntityRef


class Effect(IRModel):
    kind: Literal[EntityKind.EFFECT]
    id: Identifier
    operation: SemanticToken
    target: DomainTarget
    value: IRValue
    requires: NonEmptyEntityRefs
    provenance: EntityRef


class Observation(IRModel):
    kind: Literal[EntityKind.OBSERVATION]
    id: Identifier
    subject: EntityRef
    target: DomainTarget
    value: IRValue
    provenance: EntityRef


class Invariant(IRModel):
    kind: Literal[EntityKind.INVARIANT]
    id: Identifier
    applies_to: tuple[EntityRef, ...]
    condition: DeclaredRule
    requires: NonEmptyEntityRefs
    provenance: EntityRef


class Provenance(IRModel):
    kind: Literal[EntityKind.PROVENANCE]
    id: Identifier
    source: ArtifactSource
    producer: Producer
    captured_at: Timestamp

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: str) -> str:
        return _validate_utc_timestamp(value)


class VerificationEvidence(IRModel):
    kind: Literal[EntityKind.VERIFICATION_EVIDENCE]
    id: Identifier
    subjects: tuple[EntityRef, ...]
    check: Check
    outcome: Literal["passed", "failed", "error"]
    executed_at: Timestamp
    source_revision: Digest
    environment: Digest
    provenance: EntityRef

    @field_validator("executed_at")
    @classmethod
    def validate_executed_at(cls, value: str) -> str:
        return _validate_utc_timestamp(value)


class CapabilityRequirement(IRModel):
    kind: Literal[EntityKind.CAPABILITY_REQUIREMENT]
    id: Identifier
    name: QualifiedName
    minimum_version: NormalizedVersion
    required: bool
    provenance: EntityRef


type Entity = Annotated[
    Action
    | UseCase
    | Step
    | Binding
    | Effect
    | Observation
    | Invariant
    | Provenance
    | VerificationEvidence
    | CapabilityRequirement,
    Field(discriminator="kind"),
]


class BehaviorIR(IRModel):
    kind: Literal["behavior_ir"]
    ir_version: Literal[CURRENT_IR_VERSION]
    document_id: Identifier
    roots: tuple[EntityRef, ...]
    entities: tuple[Entity, ...]


_recursive_namespace = {"IRValue": IRValue}
ListValue.model_rebuild(_types_namespace=_recursive_namespace)
RecordEntry.model_rebuild(_types_namespace=_recursive_namespace)
RecordValue.model_rebuild(_types_namespace=_recursive_namespace)
