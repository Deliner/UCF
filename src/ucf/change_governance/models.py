from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ucf.change_lifecycle.models import (
    BehaviorDeltaRef,
    ChangeProposalRef,
    OpenSpecChangeId,
)
from ucf.ir.models import (
    URI,
    Digest,
    EntityKind,
    Identifier,
    IRModel,
    SafeInteger,
)
from ucf.ir.trust_models import BehaviorDocumentRef

CHANGE_GOVERNANCE_VERSION = "1.0.0"
IMPACT_REPORT_SCHEMA_URI = "urn:ucf:change-governance:impact-report:1.0.0"
DECISION_ASSESSMENT_SCHEMA_URI = "urn:ucf:change-governance:decision-assessment:1.0.0"
DECISION_DECLARATION_SCHEMA_URI = "urn:ucf:change-governance:decision-declaration:1.0.0"
GATE_EVALUATION_SCHEMA_URI = "urn:ucf:change-governance:gate-evaluation:1.0.0"
STRUCTURAL_IMPACT_PROCEDURE_URI = "urn:ucf:change-governance:structural-impact:1.0.0"
HUMAN_DECISION_POLICY_URI = "urn:ucf:change-governance:human-decision-policy:1.0.0"
GATE_EVALUATION_PROCEDURE_URI = (
    "urn:ucf:change-governance:gate-evaluation:procedure:1.0.0"
)

type ImpactFieldPath = Annotated[
    str,
    StringConstraints(max_length=2048),
]
type GovernanceReason = Annotated[
    str,
    StringConstraints(min_length=1, max_length=2048),
]


class DecisionClass(StrEnum):
    PUBLIC_CONTRACT = "public_contract_or_serialized_boundary"
    PRODUCTION_DEPENDENCY = "production_dependency_license_or_hosted_service"
    IRREVERSIBLE_MIGRATION = "destructive_or_irreversible_migration"
    CONTROL_WEAKENING = "security_privacy_correctness_or_gate_weakening"
    PRODUCT_SEMANTICS = "material_product_semantics"
    SCOPE_EXPANSION = "scope_expansion_for_preexisting_failure"


class CompatibilityOutcome(StrEnum):
    COMPATIBLE = "compatible"
    BREAKING = "breaking"
    UNRESOLVED = "unresolved"


class CompatibilityProfile(StrEnum):
    BACKWARD_COMPATIBLE_GRAPH_EXTENSION = "backward_compatible_graph_extension"
    BREAKING_BASE_ROOT_CONTRACT = "breaking_base_root_contract"
    BREAKING_REQUIRED_CAPABILITY = "breaking_required_capability"
    COMPATIBILITY_UNRESOLVED = "compatibility_unresolved"


class ImpactPrecision(StrEnum):
    DEFINITE = "definite"
    MAY_AFFECT = "may_affect"
    UNRESOLVED = "unresolved"


class GraphSide(StrEnum):
    BASE = "base"
    FINAL = "final"


class ImpactRelation(StrEnum):
    ROOT_REFERENCE = "root_reference"
    ENTITY_REFERENCE = "entity_reference"
    PORT_SELECTION = "port_selection"
    STEP_PORT_DEFINITION = "step_port_definition"
    REQUIRED_CAPABILITY = "required_capability"


class UnresolvedImpactReason(StrEnum):
    OPAQUE_DECLARED_RULE = "opaque_declared_rule"
    DOMAIN_SEMANTICS = "domain_semantics"
    VALUE_SEMANTICS = "value_semantics"
    PROVENANCE_CONTEXT = "provenance_context"
    VERIFICATION_CONTEXT = "verification_context"
    CAPABILITY_SEMANTICS = "capability_semantics"


class ImpactSubject(IRModel):
    kind: Literal["impact_subject"]
    operation: Literal["added", "modified", "removed", "unchanged"]
    target_kind: EntityKind
    target_id: Identifier


class ImpactFinding(IRModel):
    kind: Literal["impact_finding"]
    subject: ImpactSubject
    precision: ImpactPrecision
    changed_paths: Annotated[
        tuple[ImpactFieldPath, ...],
        Field(min_length=1),
    ]

    @model_validator(mode="after")
    def validate_changed_paths(self) -> ImpactFinding:
        if len(self.changed_paths) != len(set(self.changed_paths)):
            raise ValueError("impact finding contains duplicate changed paths")
        if self.changed_paths != tuple(sorted(self.changed_paths)):
            raise ValueError("impact finding changed paths are not canonical")
        return self


class EntityCoordinate(IRModel):
    kind: Literal["entity_coordinate"]
    target_kind: EntityKind
    target_id: Identifier


class PortCoordinate(IRModel):
    kind: Literal["port_coordinate"]
    owner_kind: Literal[
        EntityKind.ACTION,
        EntityKind.USE_CASE,
        EntityKind.STEP,
    ]
    owner_id: Identifier
    direction: Literal["input", "output"]
    name: Identifier
    resolved_action_id: Identifier | None

    @model_validator(mode="after")
    def validate_resolution(self) -> PortCoordinate:
        if self.owner_kind is EntityKind.STEP and self.resolved_action_id is None:
            raise ValueError("step port coordinate requires its resolved action")
        if (
            self.owner_kind is not EntityKind.STEP
            and self.resolved_action_id is not None
        ):
            raise ValueError("only a step port coordinate may name a resolved action")
        return self


class DocumentCoordinate(IRModel):
    kind: Literal["document_coordinate"]
    document_id: Identifier


type ImpactCoordinate = Annotated[
    EntityCoordinate | PortCoordinate | DocumentCoordinate,
    Field(discriminator="kind"),
]


class ImpactEdge(IRModel):
    kind: Literal["impact_edge"]
    side: GraphSide
    source: ImpactCoordinate
    target: ImpactCoordinate
    field_path: ImpactFieldPath
    relation: ImpactRelation
    precision: ImpactPrecision

    @model_validator(mode="after")
    def validate_field_path(self) -> ImpactEdge:
        if not self.field_path.startswith("/"):
            raise ValueError("impact edge field path must be a JSON pointer")
        return self


class ImpactWitness(IRModel):
    kind: Literal["impact_witness"]
    direct_subject: ImpactSubject
    side: GraphSide
    affected: ImpactCoordinate
    precision: ImpactPrecision
    edge_indexes: Annotated[
        tuple[SafeInteger, ...],
        Field(min_length=1),
    ]


class UnresolvedImpact(IRModel):
    kind: Literal["unresolved_impact"]
    subject: ImpactSubject
    changed_path: ImpactFieldPath
    sides: Annotated[
        tuple[GraphSide, ...],
        Field(min_length=1, max_length=2),
    ]
    reason: UnresolvedImpactReason

    @model_validator(mode="after")
    def validate_sides(self) -> UnresolvedImpact:
        if len(self.sides) != len(set(self.sides)):
            raise ValueError("unresolved impact contains duplicate graph sides")
        expected = tuple(sorted(self.sides, key=lambda side: side.value))
        if self.sides != expected:
            raise ValueError("unresolved impact graph sides are not canonical")
        return self


class CompatibilityAssessment(IRModel):
    kind: Literal["compatibility_assessment"]
    outcome: CompatibilityOutcome
    profile: CompatibilityProfile
    reasons: Annotated[
        tuple[GovernanceReason, ...],
        Field(min_length=1),
    ]

    @model_validator(mode="after")
    def validate_reasons(self) -> CompatibilityAssessment:
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("compatibility assessment contains duplicate reasons")
        if self.reasons != tuple(sorted(self.reasons)):
            raise ValueError("compatibility reasons are not canonical")
        if (
            self.outcome is CompatibilityOutcome.COMPATIBLE
            and self.profile
            is not CompatibilityProfile.BACKWARD_COMPATIBLE_GRAPH_EXTENSION
        ):
            raise ValueError("compatible outcome uses the wrong profile")
        if (
            self.outcome is CompatibilityOutcome.UNRESOLVED
            and self.profile is not CompatibilityProfile.COMPATIBILITY_UNRESOLVED
        ):
            raise ValueError("unresolved outcome uses the wrong profile")
        if self.outcome is CompatibilityOutcome.BREAKING and self.profile not in {
            CompatibilityProfile.BREAKING_BASE_ROOT_CONTRACT,
            CompatibilityProfile.BREAKING_REQUIRED_CAPABILITY,
        }:
            raise ValueError("breaking outcome uses the wrong profile")
        return self


class ImpactReport(IRModel):
    kind: Literal["impact_report"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[IMPACT_REPORT_SCHEMA_URI]
    change_id: OpenSpecChangeId
    proposal: ChangeProposalRef
    delta: BehaviorDeltaRef
    base_behavior: BehaviorDocumentRef
    final_behavior: BehaviorDocumentRef
    procedure_uri: Literal[STRUCTURAL_IMPACT_PROCEDURE_URI]
    decision_policy_uri: Literal[HUMAN_DECISION_POLICY_URI]
    findings: Annotated[
        tuple[ImpactFinding, ...],
        Field(min_length=1),
    ]
    edges: tuple[ImpactEdge, ...]
    witnesses: tuple[ImpactWitness, ...]
    unresolved: tuple[UnresolvedImpact, ...]
    compatibility: CompatibilityAssessment
    derived_required_classes: tuple[DecisionClass, ...]

    @model_validator(mode="after")
    def validate_shape(self) -> ImpactReport:
        if (
            self.proposal.change_id != self.change_id
            or self.delta.change_id != self.change_id
        ):
            raise ValueError("impact report predecessor change IDs disagree")
        if (
            self.base_behavior.document_id != self.final_behavior.document_id
            or self.base_behavior.ir_version != self.final_behavior.ir_version
        ):
            raise ValueError("impact report behavior document identities disagree")
        if self.base_behavior.canonical_digest == self.final_behavior.canonical_digest:
            raise ValueError(
                "impact report base and final behavior digests must differ"
            )
        _require_unique_canonical(
            self.findings,
            key=_finding_key,
            label="impact findings",
        )
        if any(finding.subject.operation == "unchanged" for finding in self.findings):
            raise ValueError("impact report cannot contain unchanged direct subjects")
        _require_unique_canonical(
            self.edges,
            key=_edge_key,
            label="impact edges",
        )
        _require_unique_canonical(
            self.witnesses,
            key=_witness_key,
            identity_key=_witness_identity_key,
            label="impact witnesses",
        )
        _require_unique_canonical(
            self.unresolved,
            key=_unresolved_key,
            label="unresolved impacts",
        )
        finding_subjects = {_subject_key(finding.subject) for finding in self.findings}
        for position, witness in enumerate(self.witnesses):
            if _subject_key(witness.direct_subject) not in finding_subjects:
                raise ValueError(f"impact witness {position} names no direct finding")
            _validate_witness(
                witness,
                edges=self.edges,
                position=position,
            )
        for position, unresolved in enumerate(self.unresolved):
            if _subject_key(unresolved.subject) not in finding_subjects:
                raise ValueError(
                    f"unresolved impact {position} names no direct finding"
                )
        expected_classes = (
            (DecisionClass.PUBLIC_CONTRACT,)
            if self.compatibility.outcome is CompatibilityOutcome.BREAKING
            else ()
        )
        if self.derived_required_classes != expected_classes:
            raise ValueError(
                "impact report derived decision classes disagree with compatibility"
            )
        return self


class ImpactReportRef(IRModel):
    kind: Literal["impact_report_ref"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[IMPACT_REPORT_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class DecisionDisposition(StrEnum):
    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    UNRESOLVED = "unresolved"


class AssessmentBasis(StrEnum):
    DERIVED = "derived"
    DECLARED = "declared"


class DeclaredBasis(IRModel):
    kind: Literal["declared_basis"]
    source_uri: URI
    source_digest: Digest
    summary: GovernanceReason


class DecisionClassAssessment(IRModel):
    kind: Literal["decision_class_assessment"]
    decision_class: DecisionClass
    disposition: DecisionDisposition
    basis: AssessmentBasis
    declared_basis: DeclaredBasis | None

    @model_validator(mode="after")
    def validate_basis(self) -> DecisionClassAssessment:
        if self.basis is AssessmentBasis.DERIVED:
            if self.disposition is not DecisionDisposition.APPLIES:
                raise ValueError("derived decision class must apply")
            if self.declared_basis is not None:
                raise ValueError(
                    "derived decision class cannot contain a declared basis"
                )
        elif self.declared_basis is None:
            raise ValueError("declared decision class requires an inspectable basis")
        return self


class DecisionAssessment(IRModel):
    kind: Literal["decision_assessment"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[DECISION_ASSESSMENT_SCHEMA_URI]
    change_id: OpenSpecChangeId
    proposal: ChangeProposalRef
    delta: BehaviorDeltaRef
    base_behavior: BehaviorDocumentRef
    final_behavior: BehaviorDocumentRef
    impact: ImpactReportRef
    decision_policy_uri: Literal[HUMAN_DECISION_POLICY_URI]
    assessments: Annotated[
        tuple[DecisionClassAssessment, ...],
        Field(min_length=6, max_length=6),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> DecisionAssessment:
        if (
            self.proposal.change_id != self.change_id
            or self.delta.change_id != self.change_id
            or self.impact.change_id != self.change_id
        ):
            raise ValueError("decision assessment predecessor change IDs disagree")
        if (
            self.base_behavior.document_id != self.final_behavior.document_id
            or self.base_behavior.ir_version != self.final_behavior.ir_version
            or self.base_behavior.canonical_digest
            == self.final_behavior.canonical_digest
        ):
            raise ValueError("decision assessment behavior context is inconsistent")
        classes = tuple(assessment.decision_class for assessment in self.assessments)
        if len(classes) != len(set(classes)):
            raise ValueError("decision assessment contains duplicate classes")
        if classes != tuple(DecisionClass):
            raise ValueError(
                "decision assessment must cover the fixed taxonomy in canonical order"
            )
        return self


class DecisionAssessmentRef(IRModel):
    kind: Literal["decision_assessment_ref"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[DECISION_ASSESSMENT_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionEvidence(IRModel):
    kind: Literal["decision_evidence"]
    source_uri: URI
    source_digest: Digest
    summary: GovernanceReason


class DeclaredDecision(IRModel):
    kind: Literal["declared_decision"]
    decision_class: DecisionClass
    outcome: DecisionOutcome
    evidence: DecisionEvidence


class DecisionDeclaration(IRModel):
    kind: Literal["decision_declaration"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[DECISION_DECLARATION_SCHEMA_URI]
    change_id: OpenSpecChangeId
    proposal: ChangeProposalRef
    delta: BehaviorDeltaRef
    base_behavior: BehaviorDocumentRef
    final_behavior: BehaviorDocumentRef
    impact: ImpactReportRef
    assessment: DecisionAssessmentRef
    decision_policy_uri: Literal[HUMAN_DECISION_POLICY_URI]
    decisions: Annotated[
        tuple[DeclaredDecision, ...],
        Field(min_length=1, max_length=6),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> DecisionDeclaration:
        if (
            self.proposal.change_id != self.change_id
            or self.delta.change_id != self.change_id
            or self.impact.change_id != self.change_id
            or self.assessment.change_id != self.change_id
        ):
            raise ValueError("decision declaration predecessor change IDs disagree")
        if (
            self.base_behavior.document_id != self.final_behavior.document_id
            or self.base_behavior.ir_version != self.final_behavior.ir_version
            or self.base_behavior.canonical_digest
            == self.final_behavior.canonical_digest
        ):
            raise ValueError("decision declaration behavior context is inconsistent")
        classes = tuple(decision.decision_class for decision in self.decisions)
        if len(classes) != len(set(classes)):
            raise ValueError("decision declaration contains duplicate classes")
        if classes != tuple(sorted(classes, key=_decision_class_order)):
            raise ValueError("decision declaration classes are not in taxonomy order")
        return self


class DecisionDeclarationRef(IRModel):
    kind: Literal["decision_declaration_ref"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[DECISION_DECLARATION_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class GateStatus(StrEnum):
    PASS_NO_DECISION = "pass_no_decision"
    PASS_APPROVED = "pass_approved"
    BLOCK_UNRESOLVED = "block_unresolved"
    BLOCK_DECISION_REQUIRED = "block_decision_required"
    BLOCK_REJECTED = "block_rejected"


class GateBlockerReason(StrEnum):
    UNRESOLVED_CLASSIFICATION = "unresolved_classification"
    DECISION_REQUIRED = "decision_required"
    DECISION_REJECTED = "decision_rejected"


class GateBlocker(IRModel):
    kind: Literal["gate_blocker"]
    decision_class: DecisionClass
    reason: GateBlockerReason


class GateEvaluation(IRModel):
    kind: Literal["gate_evaluation"]
    change_governance_version: Literal[CHANGE_GOVERNANCE_VERSION]
    schema_uri: Literal[GATE_EVALUATION_SCHEMA_URI]
    change_id: OpenSpecChangeId
    proposal: ChangeProposalRef
    delta: BehaviorDeltaRef
    base_behavior: BehaviorDocumentRef
    final_behavior: BehaviorDocumentRef
    impact: ImpactReportRef
    assessment: DecisionAssessmentRef
    declaration: DecisionDeclarationRef | None
    decision_policy_uri: Literal[HUMAN_DECISION_POLICY_URI]
    procedure_uri: Literal[GATE_EVALUATION_PROCEDURE_URI]
    status: GateStatus
    required_classes: Annotated[
        tuple[DecisionClass, ...],
        Field(max_length=6),
    ]
    blockers: Annotated[
        tuple[GateBlocker, ...],
        Field(max_length=6),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> GateEvaluation:
        refs = (
            self.proposal.change_id,
            self.delta.change_id,
            self.impact.change_id,
            self.assessment.change_id,
            self.declaration.change_id if self.declaration else self.change_id,
        )
        if any(change_id != self.change_id for change_id in refs):
            raise ValueError("gate evaluation predecessor change IDs disagree")
        if (
            self.base_behavior.document_id != self.final_behavior.document_id
            or self.base_behavior.ir_version != self.final_behavior.ir_version
            or self.base_behavior.canonical_digest
            == self.final_behavior.canonical_digest
        ):
            raise ValueError("gate evaluation behavior context is inconsistent")
        _validate_decision_class_sequence(
            self.required_classes,
            label="gate required classes",
        )
        blocker_classes = tuple(blocker.decision_class for blocker in self.blockers)
        _validate_decision_class_sequence(
            blocker_classes,
            label="gate blockers",
        )
        _validate_gate_status(self)
        return self


def _decision_class_order(decision_class: DecisionClass) -> int:
    return tuple(DecisionClass).index(decision_class)


def _validate_decision_class_sequence(
    classes: tuple[DecisionClass, ...],
    *,
    label: str,
) -> None:
    if len(classes) != len(set(classes)):
        raise ValueError(f"{label} contain duplicate classes")
    if classes != tuple(sorted(classes, key=_decision_class_order)):
        raise ValueError(f"{label} are not in taxonomy order")


def _validate_gate_status(gate: GateEvaluation) -> None:
    if gate.status is GateStatus.PASS_NO_DECISION:
        if gate.declaration is not None or gate.required_classes or gate.blockers:
            raise ValueError(
                "pass_no_decision gate cannot require or reference a decision"
            )
        return
    if gate.status is GateStatus.PASS_APPROVED:
        if gate.declaration is None or not gate.required_classes or gate.blockers:
            raise ValueError(
                "pass_approved gate requires a declaration and no blockers"
            )
        return
    if not gate.blockers:
        raise ValueError("blocked gate requires at least one blocker")
    if gate.status is GateStatus.BLOCK_UNRESOLVED:
        if gate.declaration is not None or any(
            blocker.reason is not GateBlockerReason.UNRESOLVED_CLASSIFICATION
            for blocker in gate.blockers
        ):
            raise ValueError("block_unresolved gate has inconsistent blockers")
        return
    if gate.status is GateStatus.BLOCK_DECISION_REQUIRED:
        if (
            gate.declaration is not None
            or not gate.required_classes
            or any(
                blocker.reason is not GateBlockerReason.DECISION_REQUIRED
                for blocker in gate.blockers
            )
        ):
            raise ValueError("block_decision_required gate has inconsistent blockers")
        return
    if (
        gate.declaration is None
        or not gate.required_classes
        or any(
            blocker.reason is not GateBlockerReason.DECISION_REJECTED
            for blocker in gate.blockers
        )
    ):
        raise ValueError("block_rejected gate has inconsistent blockers")


def _require_unique_canonical(
    values: tuple[object, ...],
    *,
    key,
    label: str,
    identity_key=None,
) -> None:
    keys = tuple(key(value) for value in values)
    identities = (
        tuple(identity_key(value) for value in values)
        if identity_key is not None
        else keys
    )
    if len(identities) != len(set(identities)):
        raise ValueError(f"{label} contain duplicate identities")
    if keys != tuple(sorted(keys)):
        raise ValueError(f"{label} are not in canonical order")


def _subject_key(subject: ImpactSubject) -> tuple[str, str, str]:
    return (
        subject.operation,
        subject.target_kind.value,
        subject.target_id,
    )


def _finding_key(finding: ImpactFinding) -> tuple[object, ...]:
    return (*_subject_key(finding.subject), finding.changed_paths)


def _coordinate_key(coordinate: ImpactCoordinate) -> tuple[str, ...]:
    if isinstance(coordinate, EntityCoordinate):
        return (
            coordinate.kind,
            coordinate.target_kind.value,
            coordinate.target_id,
        )
    if isinstance(coordinate, PortCoordinate):
        return (
            coordinate.kind,
            coordinate.owner_kind.value,
            coordinate.owner_id,
            coordinate.direction,
            coordinate.name,
            coordinate.resolved_action_id or "",
        )
    return (coordinate.kind, coordinate.document_id)


def _edge_key(edge: ImpactEdge) -> tuple[object, ...]:
    return (
        edge.side.value,
        _coordinate_key(edge.source),
        _coordinate_key(edge.target),
        edge.field_path,
        edge.relation.value,
        edge.precision.value,
    )


def _witness_identity_key(witness: ImpactWitness) -> tuple[object, ...]:
    return (
        witness.side.value,
        _subject_key(witness.direct_subject),
        _coordinate_key(witness.affected),
    )


def _witness_key(witness: ImpactWitness) -> tuple[object, ...]:
    return (*_witness_identity_key(witness), witness.edge_indexes)


def _unresolved_key(unresolved: UnresolvedImpact) -> tuple[object, ...]:
    return (
        _subject_key(unresolved.subject),
        unresolved.changed_path,
        tuple(side.value for side in unresolved.sides),
        unresolved.reason.value,
    )


def _coordinate_binds_subject(
    coordinate: ImpactCoordinate,
    subject: ImpactSubject,
) -> bool:
    if isinstance(coordinate, EntityCoordinate):
        return (
            coordinate.target_kind is subject.target_kind
            and coordinate.target_id == subject.target_id
        )
    if isinstance(coordinate, PortCoordinate):
        return (
            coordinate.owner_kind is subject.target_kind
            and coordinate.owner_id == subject.target_id
        )
    return False


def _validate_witness(
    witness: ImpactWitness,
    *,
    edges: tuple[ImpactEdge, ...],
    position: int,
) -> None:
    if len(witness.edge_indexes) != len(set(witness.edge_indexes)):
        raise ValueError(f"impact witness {position} repeats an edge")
    if any(index < 0 or index >= len(edges) for index in witness.edge_indexes):
        raise ValueError(f"impact witness {position} names an out-of-range edge")
    path = tuple(edges[index] for index in witness.edge_indexes)
    if any(edge.side is not witness.side for edge in path):
        raise ValueError(f"impact witness {position} crosses graph sides")
    current = path[0].target
    if not _coordinate_binds_subject(current, witness.direct_subject):
        raise ValueError(
            f"impact witness {position} does not start at its direct subject"
        )
    seen = {_coordinate_key(current)}
    for edge in path:
        if edge.target != current:
            raise ValueError(f"impact witness {position} is discontinuous")
        current = edge.source
        key = _coordinate_key(current)
        if key in seen:
            raise ValueError(f"impact witness {position} contains a coordinate cycle")
        seen.add(key)
    if current != witness.affected:
        raise ValueError(f"impact witness {position} ends at the wrong coordinate")
    precisions = {edge.precision for edge in path}
    expected_precision = (
        ImpactPrecision.UNRESOLVED
        if ImpactPrecision.UNRESOLVED in precisions
        else (
            ImpactPrecision.MAY_AFFECT
            if ImpactPrecision.MAY_AFFECT in precisions
            else ImpactPrecision.DEFINITE
        )
    )
    if witness.precision is not expected_precision:
        raise ValueError(f"impact witness {position} precision disagrees with its path")
