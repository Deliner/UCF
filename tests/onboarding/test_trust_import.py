from __future__ import annotations

import pytest

from ucf.ir import (
    ClaimLevel,
    canonical_trust_ir_json,
    supported_claim_levels,
    validate_trust_against_behavior,
)
from ucf.ir.trust_models import (
    Claim,
    Declaration,
    ObservedFact,
    SourceRecord,
)
from ucf.onboarding import (
    OnboardingErrorCode,
    OnboardingValidationError,
    RejectedDecision,
    build_onboarding_trust,
    canonical_onboarding_digest,
    materialize_behavior,
    validate_onboarding_trust,
)

from .test_decisions import _decisions, _discovery


def _documents():
    discovery = _discovery()
    decisions = _decisions(discovery)
    behavior, materializations = materialize_behavior(
        discovery,
        decisions,
    )
    trust = build_onboarding_trust(
        discovery,
        decisions,
        behavior,
        materializations,
    )
    return discovery, decisions, behavior, trust


def test_post_decision_trust_preserves_observed_and_declared_without_promotion():
    discovery, decisions, behavior, trust = _documents()

    validate_trust_against_behavior(trust, behavior)
    validate_onboarding_trust(trust, behavior)
    assert supported_claim_levels(trust, behavior) == frozenset(
        {ClaimLevel.OBSERVED, ClaimLevel.DECLARED}
    )
    assert sum(isinstance(record, SourceRecord) for record in trust.records) == 2
    assert sum(isinstance(record, Declaration) for record in trust.records) == 2
    assert sum(isinstance(record, ObservedFact) for record in trust.records) == 2
    assert sum(isinstance(record, Claim) for record in trust.records) == 4
    assert all(
        record.kind
        not in {"behavior_candidate", "mapping"}
        for record in trust.records
    )
    source_revisions = {
        record.source_revision
        for record in trust.records
        if isinstance(record, SourceRecord)
    }
    assert source_revisions == {
        canonical_onboarding_digest(discovery),
        canonical_onboarding_digest(decisions),
    }


def test_post_decision_trust_is_byte_deterministic():
    first = _documents()
    second = _documents()

    assert canonical_trust_ir_json(first[3]) == canonical_trust_ir_json(
        second[3]
    )


def test_behavior_bound_observations_trace_explicit_reconciliation():
    _, _, _, trust = _documents()
    decision_bound = [
        record
        for record in trust.records
        if isinstance(record, ObservedFact)
        or (
            isinstance(record, Claim)
            and record.level is ClaimLevel.OBSERVED
        )
    ]

    assert decision_bound
    assert all(
        record.trace.target_id == "source.decisions"
        for record in decision_bound
    )


def test_brn002_trust_rejects_mapped_tested_or_verified_promotion():
    _, _, behavior, trust = _documents()
    records = list(trust.records)
    position = next(
        index
        for index, record in enumerate(records)
        if isinstance(record, Claim)
    )
    records[position] = records[position].model_copy(
        update={"level": ClaimLevel.TESTED}
    )
    promoted = trust.model_copy(update={"records": tuple(records)})

    with pytest.raises(OnboardingValidationError) as captured:
        validate_onboarding_trust(promoted, behavior)

    assert captured.value.code is OnboardingErrorCode.ILLEGAL_PROMOTION
    assert captured.value.location.endswith(".level")


def test_trust_builder_rejects_materialization_forged_from_rejected_decision():
    discovery = _discovery()
    decisions = _decisions(discovery)
    behavior, materializations = materialize_behavior(
        discovery,
        decisions,
    )
    rejected = next(
        decision
        for decision in decisions.decisions
        if isinstance(decision, RejectedDecision)
    )
    forged = materializations[0].model_copy(
        update={
            "candidate": rejected.candidate,
            "decision_id": rejected.id,
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        build_onboarding_trust(
            discovery,
            decisions,
            behavior,
            (forged, *materializations[1:]),
        )

    assert captured.value.code is OnboardingErrorCode.ILLEGAL_PROMOTION
    assert captured.value.location == "$.materializations"
