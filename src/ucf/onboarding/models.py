from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from ucf.adapter_protocol import CapabilitySelection
from ucf.inventory import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    InventoryConfidence,
    InventoryRecordRef,
    InventorySnapshot,
    canonical_inventory_json,
)
from ucf.ir.models import (
    URI,
    BehaviorIR,
    Digest,
    Identifier,
    IRModel,
    NormalizedVersion,
    Port,
    Producer,
    QualifiedName,
    Timestamp,
)
from ucf.ir.trust_models import (
    BehaviorEntityRef,
    ClaimLevel,
    TrustIR,
)

ONBOARDING_VERSION = "1.0.0"
DISCOVERY_CAPABILITY = "org.ucf.adapter.discovery"
DISCOVERY_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:discovery-request:1.0.0"
)
DISCOVERY_RESULT_SCHEMA_URI = (
    "urn:ucf:adapter:discovery-result:1.0.0"
)
DECISION_SET_SCHEMA_URI = "urn:ucf:onboarding:decision-set:1.0.0"
ONBOARDING_BUNDLE_SCHEMA_URI = "urn:ucf:onboarding:bundle:1.0.0"
MAX_DISCOVERY_CANDIDATES = 10_000
MAX_DISCOVERY_DIAGNOSTICS = 10_000

_VERSIONED_URI_PATTERN = re.compile(
    r"(?:[:/])(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
_VERSIONED_URI_JSON_SCHEMA = {
    "pattern": _VERSIONED_URI_PATTERN.pattern,
}
_DISCOVERY_CAPABILITY_SCHEMA = {
    "properties": {
        "name": {"const": DISCOVERY_CAPABILITY},
        "version": {"const": ONBOARDING_VERSION},
    }
}
type DiscoveryDiagnosticId = Annotated[
    str,
    StringConstraints(pattern=r"^diagnostic\.[0-9a-f]{64}$"),
]
type DiscoveryCandidateId = Annotated[
    str,
    StringConstraints(pattern=r"^candidate\.[0-9a-f]{64}$"),
]
type DecisionId = Annotated[
    str,
    StringConstraints(pattern=r"^decision\.[0-9a-f]{64}$"),
]
type DecisionReason = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
]


class InventoryBinding(IRModel):
    kind: Literal["inventory_binding"]
    schema_uri: Literal[INVENTORY_SCHEMA_URI]
    inventory_version: Literal[INVENTORY_VERSION]
    subject_uri: URI
    source_revision: Digest
    canonical_digest: Digest


class ProposalEntityKind(StrEnum):
    ACTION = "proposed_action"
    BINDING = "proposed_binding"
    STEP = "proposed_step"
    USE_CASE = "proposed_use_case"


class ProposalEntityRef(IRModel):
    kind: Literal["proposal_entity_ref"]
    target_kind: ProposalEntityKind
    target_id: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]


class ProposalPortRef(IRModel):
    kind: Literal["proposal_port_ref"]
    owner: ProposalEntityRef
    direction: Literal["input", "output"]
    name: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]


class ProposedAction(IRModel):
    kind: Literal[ProposalEntityKind.ACTION]
    id: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]
    input_ports: tuple[Port, ...]
    output_ports: tuple[Port, ...]


class ProposedUseCase(IRModel):
    kind: Literal[ProposalEntityKind.USE_CASE]
    id: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]
    input_ports: tuple[Port, ...]
    output_ports: tuple[Port, ...]
    steps: Annotated[
        tuple[ProposalEntityRef, ...],
        Field(min_length=1, max_length=256),
    ]


class ProposedStep(IRModel):
    kind: Literal[ProposalEntityKind.STEP]
    id: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]
    action: ProposalEntityRef
    bindings: tuple[ProposalEntityRef, ...]


class ProposedBinding(IRModel):
    kind: Literal[ProposalEntityKind.BINDING]
    id: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]
    target: ProposalPortRef
    source: ProposalPortRef


type ProposalEntity = Annotated[
    ProposedAction | ProposedBinding | ProposedStep | ProposedUseCase,
    Field(discriminator="kind"),
]


class CandidateProposal(IRModel):
    kind: Literal["candidate_proposal"]
    root: ProposalEntityRef
    entities: Annotated[
        tuple[ProposalEntity, ...],
        Field(min_length=1, max_length=1024),
    ]


class DiscoveryCandidate(IRModel):
    kind: Literal["discovery_candidate"]
    id: DiscoveryCandidateId
    semantic_digest: Digest
    subject: InventoryRecordRef
    evidence: Annotated[
        tuple[InventoryRecordRef, ...],
        Field(min_length=1, max_length=256),
    ]
    confidence: InventoryConfidence
    proposal: CandidateProposal


class DiscoveryDiagnostic(IRModel):
    kind: Literal["discovery_diagnostic"]
    id: DiscoveryDiagnosticId
    severity: Literal["info", "warning", "error"]
    code: QualifiedName
    message: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    evidence: InventoryRecordRef | None


class DiscoveryCoverage(IRModel):
    kind: Literal["discovery_coverage"]
    status: Literal["complete", "partial"]
    eligible_subjects: Annotated[
        tuple[InventoryRecordRef, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]
    uncovered_subjects: Annotated[
        tuple[InventoryRecordRef, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]

    @model_validator(mode="after")
    def validate_status(self) -> DiscoveryCoverage:
        if self.status == "complete" and self.uncovered_subjects:
            raise ValueError(
                "complete discovery coverage cannot contain uncovered subjects"
            )
        if self.status == "partial" and not self.uncovered_subjects:
            raise ValueError(
                "partial discovery coverage requires uncovered subjects"
            )
        return self


class DiscoveryRequest(IRModel):
    kind: Literal["discovery_request_profile"]
    onboarding_version: Literal[ONBOARDING_VERSION]
    schema_uri: Literal[DISCOVERY_REQUEST_SCHEMA_URI]
    capability: CapabilitySelection = Field(
        json_schema_extra=_DISCOVERY_CAPABILITY_SCHEMA
    )
    inventory_binding: InventoryBinding
    inventory: InventorySnapshot

    @model_validator(mode="after")
    def validate_request(self) -> DiscoveryRequest:
        _validate_discovery_capability(self.capability)
        _validate_inventory_binding(
            self.inventory_binding,
            self.inventory,
        )
        return self


class DiscoveryResult(IRModel):
    kind: Literal["discovery_result_profile"]
    onboarding_version: Literal[ONBOARDING_VERSION]
    schema_uri: Literal[DISCOVERY_RESULT_SCHEMA_URI]
    inventory_binding: InventoryBinding
    producer: Producer
    capability: CapabilitySelection = Field(
        json_schema_extra=_DISCOVERY_CAPABILITY_SCHEMA
    )
    procedure_uri: URI = Field(
        json_schema_extra=_VERSIONED_URI_JSON_SCHEMA
    )
    coverage: DiscoveryCoverage
    diagnostics: Annotated[
        tuple[DiscoveryDiagnostic, ...],
        Field(max_length=MAX_DISCOVERY_DIAGNOSTICS),
    ]
    candidates: Annotated[
        tuple[DiscoveryCandidate, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_uri(cls, value: str) -> str:
        return _validate_versioned_uri(value)

    @model_validator(mode="after")
    def validate_result(self) -> DiscoveryResult:
        _validate_discovery_capability(self.capability)
        return self


class DiscoveryDocumentRef(IRModel):
    kind: Literal["discovery_document_ref"]
    schema_uri: Literal[DISCOVERY_RESULT_SCHEMA_URI]
    schema_version: Literal[ONBOARDING_VERSION]
    canonical_digest: Digest


class CandidateRef(IRModel):
    kind: Literal["candidate_ref"]
    discovery_digest: Digest
    candidate_id: DiscoveryCandidateId
    semantic_digest: Digest


class CaptureContext(IRModel):
    kind: Literal["capture_context"]
    captured_at: Timestamp
    environment: Digest

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ValueError(
                "capture timestamp is not a valid UTC date and time"
            ) from error
        return value


class AcceptedDecision(IRModel):
    kind: Literal["accepted_decision"]
    id: DecisionId
    candidate: CandidateRef
    reason: DecisionReason


class EditedDecision(IRModel):
    kind: Literal["edited_decision"]
    id: DecisionId
    candidate: CandidateRef
    reason: DecisionReason
    replacement_digest: Digest
    replacement: CandidateProposal


class RejectedDecision(IRModel):
    kind: Literal["rejected_decision"]
    id: DecisionId
    candidate: CandidateRef
    reason: DecisionReason


class UncertainDecision(IRModel):
    kind: Literal["uncertain_decision"]
    id: DecisionId
    candidate: CandidateRef
    reason: DecisionReason


type Decision = Annotated[
    AcceptedDecision
    | EditedDecision
    | RejectedDecision
    | UncertainDecision,
    Field(discriminator="kind"),
]


class DecisionSet(IRModel):
    kind: Literal["decision_set_profile"]
    onboarding_version: Literal[ONBOARDING_VERSION]
    schema_uri: Literal[DECISION_SET_SCHEMA_URI]
    discovery: DiscoveryDocumentRef
    inventory_binding: InventoryBinding
    reviewer: Producer
    capture_context: CaptureContext
    decisions: Annotated[
        tuple[Decision, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]


class BehaviorMaterialization(IRModel):
    kind: Literal["behavior_materialization"]
    candidate: CandidateRef
    decision_id: DecisionId
    root: BehaviorEntityRef
    entities: Annotated[
        tuple[BehaviorEntityRef, ...],
        Field(min_length=1, max_length=1025),
    ]


class BundleDocumentKind(StrEnum):
    INVENTORY = "inventory"
    DISCOVERY = "discovery"
    DECISIONS = "decisions"
    BEHAVIOR = "behavior"
    TRUST = "trust"


class DispositionKind(StrEnum):
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class BundleDocumentRef(IRModel):
    kind: Literal["bundle_document_ref"]
    document_kind: BundleDocumentKind
    schema_uri: URI
    schema_version: NormalizedVersion
    canonical_digest: Digest


class DispositionSummary(IRModel):
    kind: Literal["disposition_summary"]
    disposition: DispositionKind
    candidate_ids: Annotated[
        tuple[DiscoveryCandidateId, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]


class ClaimLevelSummary(IRModel):
    kind: Literal["claim_level_summary"]
    level: ClaimLevel
    claim_ids: Annotated[
        tuple[Identifier, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES * 2),
    ]


class OnboardingBaseline(IRModel):
    kind: Literal["onboarding_baseline"]
    documents: Annotated[
        tuple[BundleDocumentRef, ...],
        Field(min_length=5, max_length=5),
    ]
    dispositions: Annotated[
        tuple[DispositionSummary, ...],
        Field(min_length=4, max_length=4),
    ]
    materializations: Annotated[
        tuple[BehaviorMaterialization, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]
    discovery_status: Literal["complete", "partial"]
    uncovered_subjects: Annotated[
        tuple[InventoryRecordRef, ...],
        Field(max_length=MAX_DISCOVERY_CANDIDATES),
    ]
    claim_levels: Annotated[
        tuple[ClaimLevelSummary, ...],
        Field(min_length=5, max_length=5),
    ]


class OnboardingBundle(IRModel):
    kind: Literal["onboarding_bundle"]
    onboarding_version: Literal[ONBOARDING_VERSION]
    schema_uri: Literal[ONBOARDING_BUNDLE_SCHEMA_URI]
    capture_context: CaptureContext
    inventory: InventorySnapshot
    discovery: DiscoveryResult
    decisions: DecisionSet
    behavior: BehaviorIR
    trust: TrustIR
    baseline: OnboardingBaseline


def _validate_discovery_capability(
    capability: CapabilitySelection,
) -> None:
    if (
        capability.name != DISCOVERY_CAPABILITY
        or capability.version != ONBOARDING_VERSION
    ):
        raise ValueError(
            "discovery capability coordinates are incompatible"
        )


def _validate_inventory_binding(
    binding: InventoryBinding,
    inventory: InventorySnapshot,
) -> None:
    digest = hashlib.sha256(canonical_inventory_json(inventory)).hexdigest()
    if (
        binding.subject_uri != inventory.subject_uri
        or binding.source_revision != inventory.source_revision
        or binding.canonical_digest.value != digest
    ):
        raise ValueError("inventory binding does not match the exact snapshot")


def _validate_versioned_uri(value: str) -> str:
    if _VERSIONED_URI_PATTERN.search(value) is None:
        raise ValueError("URI must end with a semantic version")
    return value
