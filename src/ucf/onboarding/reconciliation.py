from __future__ import annotations

import hashlib

from ucf.ir import CURRENT_IR_VERSION, canonical_ir_json, parse_ir_json
from ucf.ir.models import (
    Action,
    ArtifactSource,
    BehaviorIR,
    Binding,
    Digest,
    Entity,
    EntityKind,
    EntityRef,
    PortRef,
    Provenance,
    Step,
    UseCase,
)
from ucf.ir.trust_models import BehaviorEntityRef
from ucf.onboarding.codec import canonical_onboarding_digest
from ucf.onboarding.errors import (
    OnboardingErrorCode,
    OnboardingValidationError,
)
from ucf.onboarding.models import (
    AcceptedDecision,
    BehaviorMaterialization,
    CandidateProposal,
    Decision,
    DecisionSet,
    DiscoveryCandidate,
    DiscoveryResult,
    EditedDecision,
    ProposalEntityKind,
    ProposalEntityRef,
    ProposalPortRef,
    ProposedAction,
    ProposedBinding,
    ProposedStep,
    ProposedUseCase,
)
from ucf.onboarding.validation import (
    validate_candidate_proposal,
    validate_decision_set,
)

_BEHAVIOR_KIND = {
    ProposalEntityKind.ACTION: EntityKind.ACTION,
    ProposalEntityKind.BINDING: EntityKind.BINDING,
    ProposalEntityKind.STEP: EntityKind.STEP,
    ProposalEntityKind.USE_CASE: EntityKind.USE_CASE,
}


def materialize_behavior(
    discovery: DiscoveryResult,
    decision_set: DecisionSet,
) -> tuple[BehaviorIR, tuple[BehaviorMaterialization, ...]]:
    validate_decision_set(discovery, decision_set)
    candidates_by_id = {
        candidate.id: candidate for candidate in discovery.candidates
    }
    selected: list[
        tuple[DiscoveryCandidate, Decision, CandidateProposal]
    ] = []
    for decision in decision_set.decisions:
        if isinstance(decision, AcceptedDecision):
            proposal = candidates_by_id[
                decision.candidate.candidate_id
            ].proposal
        elif isinstance(decision, EditedDecision):
            proposal = decision.replacement
        else:
            continue
        validate_candidate_proposal(proposal)
        selected.append(
            (
                candidates_by_id[decision.candidate.candidate_id],
                decision,
                proposal,
            )
        )

    proposal_ids = [
        entity.id
        for _, _, proposal in selected
        for entity in proposal.entities
    ]
    if len(proposal_ids) != len(set(proposal_ids)):
        raise OnboardingValidationError(
            OnboardingErrorCode.DUPLICATE_IDENTITY,
            "accepted and edited proposals collide on behavior entity IDs",
            location="$.behavior.entities",
        )

    decision_digest = canonical_onboarding_digest(decision_set)
    entities: list[Entity] = []
    root_refs: list[EntityRef] = []
    provenance_ids: dict[str, str] = {}
    for _, decision, proposal in selected:
        provenance_id = (
            "provenance."
            + hashlib.sha256(decision.id.encode("ascii")).hexdigest()
        )
        if (
            provenance_id in proposal_ids
            or provenance_id in provenance_ids.values()
        ):
            raise OnboardingValidationError(
                OnboardingErrorCode.DUPLICATE_IDENTITY,
                "decision provenance collides on a behavior entity ID",
                location="$.behavior.entities",
            )
        provenance_ids[decision.id] = provenance_id
        provenance_ref = EntityRef(
            kind="entity_ref",
            target_kind=EntityKind.PROVENANCE,
            target_id=provenance_id,
        )
        entities.append(
            Provenance(
                kind=EntityKind.PROVENANCE,
                id=provenance_id,
                source=ArtifactSource(
                    kind="artifact_source",
                    uri=(
                        "urn:ucf:onboarding:decision-set:"
                        f"{decision_digest.value}"
                    ),
                    revision=decision_digest,
                ),
                producer=decision_set.reviewer,
                captured_at=decision_set.capture_context.captured_at,
            )
        )
        entities.extend(
            _materialize_proposal(
                proposal,
                provenance=provenance_ref,
            )
        )
        root_refs.append(_entity_ref(proposal.root))

    behavior = parse_ir_json(
        canonical_ir_json(
            BehaviorIR(
                kind="behavior_ir",
                ir_version=CURRENT_IR_VERSION,
                document_id=f"behavior.{decision_digest.value}",
                roots=tuple(root_refs),
                entities=tuple(entities),
            )
        )
    )
    behavior_digest = hashlib.sha256(
        canonical_ir_json(behavior).encode("ascii")
    ).hexdigest()
    behavior_index = {entity.id: entity for entity in behavior.entities}
    materializations = []
    for _, decision, proposal in selected:
        proposal_entity_ids = {
            entity.id for entity in proposal.entities
        }
        link_entity_ids = (
            *proposal_entity_ids,
            provenance_ids[decision.id],
        )
        references = tuple(
            sorted(
                (
                    _behavior_ref(
                        behavior,
                        behavior_digest,
                        behavior_index[identifier],
                    )
                    for identifier in link_entity_ids
                ),
                key=lambda reference: (
                    reference.target_kind.value,
                    reference.target_id,
                ),
            )
        )
        root_entity = behavior_index[proposal.root.target_id]
        materializations.append(
            BehaviorMaterialization(
                kind="behavior_materialization",
                candidate=decision.candidate,
                decision_id=decision.id,
                root=_behavior_ref(
                    behavior,
                    behavior_digest,
                    root_entity,
                ),
                entities=references,
            )
        )
    return behavior, tuple(materializations)


def _materialize_proposal(
    proposal: CandidateProposal,
    *,
    provenance: EntityRef,
) -> tuple[Entity, ...]:
    materialized: list[Entity] = []
    for entity in proposal.entities:
        if isinstance(entity, ProposedAction):
            materialized.append(
                Action(
                    kind=EntityKind.ACTION,
                    id=entity.id,
                    input_ports=entity.input_ports,
                    output_ports=entity.output_ports,
                    effects=(),
                    requires=(),
                    provenance=provenance,
                )
            )
        elif isinstance(entity, ProposedBinding):
            materialized.append(
                Binding(
                    kind=EntityKind.BINDING,
                    id=entity.id,
                    target=_port_ref(entity.target),
                    source=_port_ref(entity.source),
                    provenance=provenance,
                )
            )
        elif isinstance(entity, ProposedStep):
            materialized.append(
                Step(
                    kind=EntityKind.STEP,
                    id=entity.id,
                    action=_entity_ref(entity.action),
                    bindings=tuple(
                        _entity_ref(reference)
                        for reference in entity.bindings
                    ),
                    effects=(),
                    observations=(),
                    requires=(),
                    provenance=provenance,
                )
            )
        elif isinstance(entity, ProposedUseCase):
            materialized.append(
                UseCase(
                    kind=EntityKind.USE_CASE,
                    id=entity.id,
                    input_ports=entity.input_ports,
                    output_ports=entity.output_ports,
                    steps=tuple(
                        _entity_ref(reference)
                        for reference in entity.steps
                    ),
                    invariants=(),
                    requires=(),
                    provenance=provenance,
                )
            )
    return tuple(materialized)


def _entity_ref(reference: ProposalEntityRef) -> EntityRef:
    return EntityRef(
        kind="entity_ref",
        target_kind=_BEHAVIOR_KIND[reference.target_kind],
        target_id=reference.target_id,
    )


def _port_ref(reference: ProposalPortRef) -> PortRef:
    return PortRef(
        kind="port_ref",
        owner=_entity_ref(reference.owner),
        direction=reference.direction,
        name=reference.name,
    )


def _behavior_ref(
    behavior: BehaviorIR,
    canonical_digest: str,
    entity: Entity,
) -> BehaviorEntityRef:
    return BehaviorEntityRef(
        kind="behavior_entity_ref",
        document_id=behavior.document_id,
        ir_version=behavior.ir_version,
        canonical_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=canonical_digest,
        ),
        target_kind=entity.kind,
        target_id=entity.id,
    )
