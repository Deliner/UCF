from __future__ import annotations

import pytest

from ucf.ir import ClaimLevel
from ucf.onboarding import (
    BundleDocumentKind,
    DispositionKind,
    OnboardingErrorCode,
    OnboardingValidationError,
    build_onboarding_bundle,
    canonical_onboarding_json,
    parse_onboarding_bundle_json,
    validate_onboarding_bundle,
)

from .test_codec import _request
from .test_decisions import _decisions, _discovery


def _bundle():
    discovery = _discovery()
    decisions = _decisions(discovery)
    return build_onboarding_bundle(
        _request().inventory,
        discovery,
        decisions,
    )


def test_bundle_round_trip_is_self_contained_deterministic_and_valid():
    first = _bundle()
    second = _bundle()
    encoded = canonical_onboarding_json(first)

    assert canonical_onboarding_json(second) == encoded
    assert parse_onboarding_bundle_json(encoded) == first
    validate_onboarding_bundle(first)
    assert tuple(
        reference.document_kind
        for reference in first.baseline.documents
    ) == tuple(BundleDocumentKind)
    assert tuple(
        summary.disposition
        for summary in first.baseline.dispositions
    ) == tuple(DispositionKind)
    assert tuple(
        summary.level for summary in first.baseline.claim_levels
    ) == tuple(ClaimLevel)


def test_self_contained_bundle_parser_rejects_semantic_corruption():
    bundle = _bundle()
    documents = list(bundle.baseline.documents)
    documents[0] = documents[0].model_copy(
        update={
            "canonical_digest": documents[0].canonical_digest.model_copy(
                update={"value": "f" * 64}
            )
        }
    )
    corrupted = bundle.model_copy(
        update={
            "baseline": bundle.baseline.model_copy(
                update={"documents": tuple(documents)}
            )
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        parse_onboarding_bundle_json(canonical_onboarding_json(corrupted))

    assert captured.value.code is OnboardingErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == "$.baseline"


def test_baseline_keeps_rejected_uncertain_and_absent_stronger_claims_visible():
    baseline = _bundle().baseline
    dispositions = {
        summary.disposition: summary.candidate_ids
        for summary in baseline.dispositions
    }
    claims = {
        summary.level: summary.claim_ids
        for summary in baseline.claim_levels
    }

    assert all(
        len(dispositions[disposition]) == 1
        for disposition in DispositionKind
    )
    assert claims[ClaimLevel.OBSERVED]
    assert claims[ClaimLevel.DECLARED]
    assert claims[ClaimLevel.MAPPED] == ()
    assert claims[ClaimLevel.TESTED] == ()
    assert claims[ClaimLevel.VERIFIED] == ()


@pytest.mark.parametrize(
    "mutation",
    [
        "document_digest",
        "disposition",
        "materialization",
        "claim_level",
        "capture_context",
    ],
)
def test_bundle_rejects_every_stale_or_forged_baseline_summary(
    mutation: str,
):
    bundle = _bundle()
    baseline = bundle.baseline
    if mutation == "document_digest":
        documents = list(baseline.documents)
        documents[0] = documents[0].model_copy(
            update={
                "canonical_digest": documents[0]
                .canonical_digest.model_copy(update={"value": "f" * 64})
            }
        )
        baseline = baseline.model_copy(
            update={"documents": tuple(documents)}
        )
        changed = bundle.model_copy(update={"baseline": baseline})
    elif mutation == "disposition":
        summaries = list(baseline.dispositions)
        summaries[-1] = summaries[-1].model_copy(
            update={"candidate_ids": ()}
        )
        changed = bundle.model_copy(
            update={
                "baseline": baseline.model_copy(
                    update={"dispositions": tuple(summaries)}
                )
            }
        )
    elif mutation == "materialization":
        changed = bundle.model_copy(
            update={
                "baseline": baseline.model_copy(
                    update={"materializations": ()}
                )
            }
        )
    elif mutation == "claim_level":
        summaries = list(baseline.claim_levels)
        tested = next(
            index
            for index, summary in enumerate(summaries)
            if summary.level is ClaimLevel.TESTED
        )
        summaries[tested] = summaries[tested].model_copy(
            update={"claim_ids": ("claim.forged",)}
        )
        changed = bundle.model_copy(
            update={
                "baseline": baseline.model_copy(
                    update={"claim_levels": tuple(summaries)}
                )
            }
        )
    else:
        changed = bundle.model_copy(
            update={
                "capture_context": bundle.capture_context.model_copy(
                    update={"captured_at": "2026-07-19T12:00:01Z"}
                )
            }
        )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_onboarding_bundle(changed)

    assert captured.value.code in {
        OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH,
        OnboardingErrorCode.SUMMARY_MISMATCH,
    }
