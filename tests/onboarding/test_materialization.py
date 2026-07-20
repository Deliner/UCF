from __future__ import annotations

import pytest

from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import Binding, Provenance, UseCase
from ucf.onboarding import (
    EditedDecision,
    OnboardingErrorCode,
    OnboardingValidationError,
    canonical_onboarding_digest,
    derive_candidate_semantic_digest,
    derive_decision_id,
    materialize_behavior,
)

from .test_candidates import _proposal
from .test_decisions import _decisions, _discovery


def test_only_accepted_and_edited_proposals_materialize_as_valid_behavior():
    discovery = _discovery()
    decisions = _decisions(discovery)

    behavior, materializations = materialize_behavior(
        discovery,
        decisions,
    )

    assert parse_ir_json(canonical_ir_json(behavior)) == behavior
    use_case_ids = {
        entity.id
        for entity in behavior.entities
        if isinstance(entity, UseCase)
    }
    assert use_case_ids == {
        "use-case.quote-order",
        "use-case.render-receipt",
    }
    assert all(
        prohibited not in {entity.id for entity in behavior.entities}
        for prohibited in (
            "use-case.format-receipt",
            "use-case.normalize-coupon",
            "use-case.legacy-discount-hint",
        )
    )
    assert len(materializations) == 2
    assert {
        link.candidate.candidate_id for link in materializations
    } == {
        decision.candidate.candidate_id
        for decision in decisions.decisions
        if decision.kind in {"accepted_decision", "edited_decision"}
    }
    assert any(isinstance(entity, Binding) for entity in behavior.entities)


def test_materialization_is_byte_deterministic_and_decision_bound():
    discovery = _discovery()
    decisions = _decisions(discovery)

    first, first_links = materialize_behavior(discovery, decisions)
    second, second_links = materialize_behavior(discovery, decisions)

    assert canonical_ir_json(first) == canonical_ir_json(second)
    assert first_links == second_links
    expected_revision = canonical_onboarding_digest(decisions)
    provenances = tuple(
        entity
        for entity in first.entities
        if isinstance(entity, Provenance)
    )
    assert len(provenances) == 2
    assert all(
        provenance.source.revision == expected_revision
        and provenance.producer == decisions.reviewer
        and provenance.captured_at
        == decisions.capture_context.captured_at
        for provenance in provenances
    )


def test_cross_proposal_entity_collision_fails_atomically():
    discovery = _discovery()
    decisions = _decisions(discovery)
    values = list(decisions.decisions)
    position = next(
        index
        for index, decision in enumerate(values)
        if isinstance(decision, EditedDecision)
    )
    replacement = _proposal("quote-order")
    changed = values[position].model_copy(
        update={
            "replacement": replacement,
            "replacement_digest": derive_candidate_semantic_digest(
                replacement
            ),
        }
    )
    changed = changed.model_copy(
        update={"id": derive_decision_id(changed, decisions)}
    )
    values[position] = changed
    collision = decisions.model_copy(update={"decisions": tuple(values)})

    with pytest.raises(OnboardingValidationError) as captured:
        materialize_behavior(discovery, collision)

    assert captured.value.code is OnboardingErrorCode.DUPLICATE_IDENTITY
    assert captured.value.location == "$.behavior.entities"
