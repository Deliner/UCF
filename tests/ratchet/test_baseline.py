from __future__ import annotations

import pytest

from ucf.ratchet import (
    RatchetErrorCode,
    RatchetValidationError,
    build_ratchet_assessment,
    canonical_ratchet_json,
    establish_ratchet_baseline,
    parse_ratchet_baseline_json,
    validate_initial_ratchet_baseline,
)

from .test_assessment import (
    _assessment,
    _capture_context,
    _partial_bundle,
)
from .test_policy import _policy


def test_initial_baseline_records_only_current_legacy_allowances() -> None:
    policy, bundle, assessment = _assessment()

    baseline = establish_ratchet_baseline(policy, bundle, assessment)

    assert baseline.generation == 0
    assert baseline.predecessor is None
    assert baseline.subjects == assessment.subjects
    assert baseline.allowances == tuple(
        violation.key for violation in assessment.violations
    )
    assert baseline.protected == ()
    validate_initial_ratchet_baseline(
        policy,
        bundle,
        assessment,
        baseline,
    )


def test_initial_baseline_round_trip_is_deterministic() -> None:
    policy, bundle, assessment = _assessment()
    first = establish_ratchet_baseline(policy, bundle, assessment)
    second = establish_ratchet_baseline(policy, bundle, assessment)
    encoded = canonical_ratchet_json(first)

    assert first == second
    assert canonical_ratchet_json(second) == encoded
    parsed = parse_ratchet_baseline_json(encoded)
    assert parsed == first
    validate_initial_ratchet_baseline(
        policy,
        bundle,
        assessment,
        parsed,
    )


def test_initial_baseline_rejects_partial_rule_coverage() -> None:
    policy, bundle, _ = _assessment()
    partial = build_ratchet_assessment(
        policy,
        bundle,
        producer=_assessment()[2].producer,
        procedure_uri="urn:ucf:ratchet-assessment:fixture:1.0.0",
        capture_context=_capture_context(),
        partial_rule_ids={policy.rules[0].id},
    )

    with pytest.raises(RatchetValidationError) as captured:
        establish_ratchet_baseline(policy, bundle, partial)

    assert captured.value.code is RatchetErrorCode.INCOMPLETE_COVERAGE
    assert captured.value.location == "$.source_assessment.coverage"


def test_initial_baseline_rejects_partial_subject_coverage() -> None:
    policy = _policy()
    bundle = _partial_bundle()
    assessment = build_ratchet_assessment(
        policy,
        bundle,
        producer=_assessment()[2].producer,
        procedure_uri="urn:ucf:ratchet-assessment:fixture:1.0.0",
        capture_context=_capture_context(),
    )

    with pytest.raises(RatchetValidationError) as captured:
        establish_ratchet_baseline(policy, bundle, assessment)

    assert captured.value.code is RatchetErrorCode.INCOMPLETE_COVERAGE
    assert captured.value.location == "$.source_assessment.coverage"


@pytest.mark.parametrize("mutation", ["allowance", "subjects", "source"])
def test_initial_baseline_rejects_forged_derived_state(mutation: str) -> None:
    policy, bundle, assessment = _assessment()
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    if mutation == "allowance":
        forged = baseline.model_copy(update={"allowances": ()})
        location = "$.allowances"
    elif mutation == "subjects":
        forged = baseline.model_copy(update={"subjects": ()})
        location = "$.subjects"
    else:
        forged = baseline.model_copy(
            update={
                "source_assessment": baseline.source_assessment.model_copy(
                    update={"target_id": f"assessment.{'f' * 64}"}
                )
            }
        )
        location = "$.source_assessment"

    with pytest.raises(RatchetValidationError) as captured:
        validate_initial_ratchet_baseline(
            policy,
            bundle,
            assessment,
            forged,
        )

    assert captured.value.code is RatchetErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == location
