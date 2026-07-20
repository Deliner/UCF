from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.ir.models import Digest, Producer
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    EditedDecision,
    OnboardingErrorCode,
    OnboardingValidationError,
    RejectedDecision,
    UncertainDecision,
    canonical_onboarding_digest,
    canonical_onboarding_json,
    derive_candidate_semantic_digest,
    derive_decision_id,
    parse_decision_set_json,
    validate_decision_set,
)

from .test_candidates import _candidate, _proposal
from .test_codec import _result

_ZERO = "0" * 64


def _discovery():
    candidates = tuple(
        sorted(
            (
                _candidate("quote-order"),
                _candidate("format-receipt"),
                _candidate("normalize-coupon"),
                _candidate("legacy-discount-hint"),
            ),
            key=lambda item: item.id,
        )
    )
    return _result().model_copy(update={"candidates": candidates})


def _candidate_ref(discovery, candidate) -> CandidateRef:
    return CandidateRef(
        kind="candidate_ref",
        discovery_digest=canonical_onboarding_digest(discovery),
        candidate_id=candidate.id,
        semantic_digest=candidate.semantic_digest,
    )


def _base_decision_set(discovery) -> DecisionSet:
    return DecisionSet(
        kind="decision_set_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DECISION_SET_SCHEMA_URI,
        discovery=DiscoveryDocumentRef(
            kind="discovery_document_ref",
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=canonical_onboarding_digest(discovery),
        ),
        inventory_binding=discovery.inventory_binding,
        reviewer=Producer(
            kind="producer",
            name="org.ucf.fixture-reviewer",
            version="1.0.0",
        ),
        capture_context=CaptureContext(
            kind="capture_context",
            captured_at="2026-07-19T12:00:00Z",
            environment=Digest(
                kind="digest",
                algorithm="sha-256",
                value="a" * 64,
            ),
        ),
        decisions=(),
    )


def _decisions(discovery=None) -> DecisionSet:
    discovery = discovery or _discovery()
    base = _base_decision_set(discovery)
    provisional = []
    for candidate in discovery.candidates:
        candidate_ref = _candidate_ref(discovery, candidate)
        use_case = candidate.proposal.root.target_id
        common = {
            "id": f"decision.{_ZERO}",
            "candidate": candidate_ref,
        }
        if use_case.endswith("quote-order"):
            decision = AcceptedDecision(
                kind="accepted_decision",
                reason="Matches the existing native behavior checks.",
                **common,
            )
        elif use_case.endswith("format-receipt"):
            replacement = _proposal("render-receipt")
            decision = EditedDecision(
                kind="edited_decision",
                reason="Use the reviewed product vocabulary.",
                replacement_digest=derive_candidate_semantic_digest(
                    replacement
                ),
                replacement=replacement,
                **common,
            )
        elif use_case.endswith("normalize-coupon"):
            decision = RejectedDecision(
                kind="rejected_decision",
                reason="Internal lookup helper, not a user behavior.",
                **common,
            )
        else:
            decision = UncertainDecision(
                kind="uncertain_decision",
                reason="No executable check establishes intended semantics.",
                **common,
            )
        provisional.append(
            decision.model_copy(
                update={"id": derive_decision_id(decision, base)}
            )
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    provisional,
                    key=lambda item: item.candidate.candidate_id,
                )
            )
        }
    )


def test_decision_set_round_trips_all_four_exact_dispositions():
    discovery = _discovery()
    decisions = _decisions(discovery)
    encoded = canonical_onboarding_json(decisions)

    assert parse_decision_set_json(encoded) == decisions
    assert canonical_onboarding_json(parse_decision_set_json(encoded)) == (
        encoded
    )
    assert {decision.kind for decision in decisions.decisions} == {
        "accepted_decision",
        "edited_decision",
        "rejected_decision",
        "uncertain_decision",
    }
    validate_decision_set(discovery, decisions)


def test_decision_union_rejects_replacement_on_an_accepted_decision():
    decisions = _decisions()
    accepted = next(
        decision
        for decision in decisions.decisions
        if decision.kind == "accepted_decision"
    )
    payload = accepted.model_dump(mode="json")
    payload["replacement"] = _proposal().model_dump(mode="json")

    with pytest.raises(ValidationError):
        AcceptedDecision.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "unknown_candidate",
        "stale_discovery",
        "stale_semantic_digest",
        "forged_decision_id",
        "stale_replacement",
    ],
)
def test_invalid_or_stale_decision_set_is_rejected_atomically(
    mutation: str,
):
    discovery = _discovery()
    decision_set = _decisions(discovery)
    values = list(decision_set.decisions)
    if mutation == "missing":
        values.pop()
    elif mutation == "duplicate":
        values[-1] = values[0]
    elif mutation == "unknown_candidate":
        values[0] = values[0].model_copy(
            update={
                "candidate": values[0].candidate.model_copy(
                    update={"candidate_id": f"candidate.{'f' * 64}"}
                )
            }
        )
    elif mutation == "stale_discovery":
        values[0] = values[0].model_copy(
            update={
                "candidate": values[0].candidate.model_copy(
                    update={
                        "discovery_digest": Digest(
                            kind="digest",
                            algorithm="sha-256",
                            value="f" * 64,
                        )
                    }
                )
            }
        )
    elif mutation == "stale_semantic_digest":
        values[0] = values[0].model_copy(
            update={
                "candidate": values[0].candidate.model_copy(
                    update={
                        "semantic_digest": Digest(
                            kind="digest",
                            algorithm="sha-256",
                            value="f" * 64,
                        )
                    }
                )
            }
        )
    elif mutation == "forged_decision_id":
        values[0] = values[0].model_copy(
            update={"id": f"decision.{'f' * 64}"}
        )
    else:
        position = next(
            index
            for index, decision in enumerate(values)
            if decision.kind == "edited_decision"
        )
        values[position] = values[position].model_copy(
            update={
                "replacement_digest": Digest(
                    kind="digest",
                    algorithm="sha-256",
                    value="f" * 64,
                )
            }
        )
    changed = decision_set.model_copy(update={"decisions": tuple(values)})

    with pytest.raises(OnboardingValidationError) as captured:
        validate_decision_set(discovery, changed)

    expected = (
        OnboardingErrorCode.CONTENT_IDENTITY_MISMATCH
        if mutation == "forged_decision_id"
        else OnboardingErrorCode.STALE_DECISION
    )
    assert captured.value.code is expected
