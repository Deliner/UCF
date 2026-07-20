from __future__ import annotations

import pytest

from ucf.onboarding import (
    CandidateProposal,
    OnboardingErrorCode,
    OnboardingValidationError,
    ProposalEntityKind,
    ProposalEntityRef,
    ProposedAction,
    ProposedStep,
    validate_candidate_proposal,
)

from .test_candidates import _proposal


def test_proposal_graph_is_closed_language_neutral_and_resolved():
    validate_candidate_proposal(_proposal())


def test_proposal_root_must_resolve_to_the_exact_use_case_kind():
    proposal = _proposal()
    changed = proposal.model_copy(
        update={
            "root": proposal.root.model_copy(
                update={"target_kind": ProposalEntityKind.ACTION}
            )
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_candidate_proposal(changed)

    assert captured.value.code is OnboardingErrorCode.WRONG_TARGET_KIND
    assert captured.value.location == "$.root"


def test_proposal_rejects_broken_step_action_reference():
    proposal = _proposal()
    entities = list(proposal.entities)
    position = next(
        index
        for index, entity in enumerate(entities)
        if isinstance(entity, ProposedStep)
    )
    entities[position] = entities[position].model_copy(
        update={
            "action": ProposalEntityRef(
                kind="proposal_entity_ref",
                target_kind=ProposalEntityKind.ACTION,
                target_id="action.missing",
            )
        }
    )
    changed = proposal.model_copy(update={"entities": tuple(entities)})

    with pytest.raises(OnboardingValidationError) as captured:
        validate_candidate_proposal(changed)

    assert captured.value.code is OnboardingErrorCode.BROKEN_REFERENCE


def test_proposal_rejects_an_unreachable_entity():
    proposal = _proposal()
    orphan = ProposedAction(
        kind=ProposalEntityKind.ACTION,
        id="action.orphan",
        input_ports=(),
        output_ports=(),
    )
    changed = proposal.model_copy(
        update={
            "entities": tuple(
                sorted(
                    (*proposal.entities, orphan),
                    key=lambda entity: (entity.kind, entity.id),
                )
            )
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_candidate_proposal(changed)

    assert captured.value.code is OnboardingErrorCode.UNREACHABLE_ENTITY
    assert captured.value.location == "$.entities"


def test_proposal_requires_one_binding_for_every_required_action_input():
    proposal = _proposal()
    entities = list(proposal.entities)
    position = next(
        index
        for index, entity in enumerate(entities)
        if isinstance(entity, ProposedStep)
    )
    entities[position] = entities[position].model_copy(
        update={"bindings": ()}
    )
    changed = proposal.model_copy(update={"entities": tuple(entities)})

    with pytest.raises(OnboardingValidationError) as captured:
        validate_candidate_proposal(changed)

    assert captured.value.code is OnboardingErrorCode.INVALID_PROPOSAL
    assert captured.value.location.endswith(".bindings")


def test_proposal_entities_must_be_in_canonical_order():
    proposal = _proposal()
    changed = proposal.model_copy(
        update={"entities": tuple(reversed(proposal.entities))}
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_candidate_proposal(changed)

    assert captured.value.code is OnboardingErrorCode.NON_CANONICAL_ORDER
    assert captured.value.location == "$.entities"


def test_proposal_rejects_duplicate_global_entity_identity():
    proposal = _proposal()
    duplicate = proposal.entities[0].model_copy(
        update={"kind": ProposalEntityKind.USE_CASE}
    )
    changed = CandidateProposal.model_construct(
        kind="candidate_proposal",
        root=proposal.root,
        entities=(*proposal.entities, duplicate),
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_candidate_proposal(changed)

    assert captured.value.code is OnboardingErrorCode.DUPLICATE_IDENTITY
