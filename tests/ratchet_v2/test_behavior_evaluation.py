from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.ratchet.test_assessment import _partial_bundle
from tests.ratchet.test_touch_projection import (
    _candidate_confidence_change,
    _semantic_change,
)
from ucf.onboarding import (
    RejectedDecision,
    build_onboarding_bundle,
    derive_decision_id,
)
from ucf.ratchet.v2 import (
    BehaviorOutcome,
    BehaviorSubjectChangeKind,
    CombinedOutcome,
    ViolationClassificationKind,
    ViolationInput,
    advance_ratchet_baseline,
    build_ratchet_assessment,
    establish_ratchet_baseline,
    evaluate_ratchet,
)

from .test_assessment import _assessment
from .test_policy import _policy


def _behavior_assessment(
    policy,
    bundle,
    *,
    target_id: str = "use-case.quote-order",
    slots: tuple[str, ...] = (),
    partial: bool = False,
):
    source = _assessment(bundle)
    subject = next(
        item.key
        for item in source.behavior.subjects
        if item.key.target_id == target_id
    )
    return build_ratchet_assessment(
        policy,
        bundle,
        producer=source.producer,
        procedure_uri=source.procedure_uri,
        capture_context=source.capture_context,
        violations=tuple(
            ViolationInput(
                kind="ratchet_violation_input",
                rule_id=policy.rules[0].id,
                subject=subject,
                slot=slot,
                message=f"Violation in {slot}.",
            )
            for slot in slots
        ),
        partial_rule_ids={policy.rules[0].id} if partial else (),
    )


def _accepted_with_behavior_debt(*, target_id="use-case.quote-order"):
    policy = _policy()
    bundle = _bundle()
    assessment = _behavior_assessment(
        policy,
        bundle,
        target_id=target_id,
        slots=("legacy",),
    )
    return (
        policy,
        bundle,
        establish_ratchet_baseline(policy, bundle, assessment),
    )


def _with_quote_rejected():
    bundle = _bundle()
    candidates = {
        candidate.id: candidate for candidate in bundle.discovery.candidates
    }
    changed = []
    for decision in bundle.decisions.decisions:
        candidate = candidates[decision.candidate.candidate_id]
        if candidate.proposal.root.target_id == "use-case.quote-order":
            decision = RejectedDecision(
                kind="rejected_decision",
                id=f"decision.{'0' * 64}",
                candidate=decision.candidate,
                reason="Explicit review removes this behavior from scope.",
            )
        changed.append(decision)
    provisional = bundle.decisions.model_copy(
        update={"decisions": tuple(changed)}
    )
    decisions = tuple(
        sorted(
            (
                decision.model_copy(
                    update={"id": derive_decision_id(decision, provisional)}
                )
                for decision in changed
            ),
            key=lambda item: item.candidate.candidate_id,
        )
    )
    return build_onboarding_bundle(
        bundle.inventory,
        bundle.discovery,
        provisional.model_copy(update={"decisions": decisions}),
    )


def test_unchanged_legacy_behavior_debt_passes_without_promotion() -> None:
    policy, bundle, baseline = _accepted_with_behavior_debt()
    current = _behavior_assessment(policy, bundle, slots=("legacy",))

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.behavior_outcome is BehaviorOutcome.PASS
    assert report.behavior_classifications[0].classification is (
        ViolationClassificationKind.UNCHANGED_LEGACY
    )
    assert report.combined_outcome.value == (
        "pass_with_legacy_coverage_debt"
    )


def test_new_behavior_violation_fails() -> None:
    policy, bundle, baseline = _accepted_with_behavior_debt()
    current = _behavior_assessment(
        policy,
        bundle,
        slots=("legacy", "new-regression"),
    )

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.behavior_outcome is BehaviorOutcome.FAIL
    assert {
        item.classification for item in report.behavior_classifications
    } == {
        ViolationClassificationKind.UNCHANGED_LEGACY,
        ViolationClassificationKind.NEW_REGRESSION,
    }
    assert report.combined_outcome is CombinedOutcome.FAIL


@pytest.mark.parametrize(
    ("target_id", "mutator", "expected_change"),
    [
        (
            "use-case.quote-order",
            lambda bundle: _candidate_confidence_change(
                bundle,
                "quote-order",
            ),
            BehaviorSubjectChangeKind.OBSERVED_CHANGED,
        ),
        (
            "use-case.render-receipt",
            _semantic_change,
            BehaviorSubjectChangeKind.SEMANTIC_CHANGED,
        ),
    ],
)
def test_touched_legacy_behavior_debt_fails(
    target_id,
    mutator,
    expected_change,
) -> None:
    policy, bundle, baseline = _accepted_with_behavior_debt(
        target_id=target_id
    )
    current_bundle = mutator(bundle)
    current = _behavior_assessment(
        policy,
        current_bundle,
        target_id=target_id,
        slots=("legacy",),
    )

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    change = next(
        item.change
        for item in report.behavior_subject_changes
        if item.subject.target_id
        == next(
            subject.id
            for subject in current.behavior.subjects
            if subject.key.target_id == target_id
        )
    )
    assert change is expected_change
    assert report.behavior_classifications[0].classification is (
        ViolationClassificationKind.TOUCHED_LEGACY
    )
    assert report.behavior_outcome is BehaviorOutcome.FAIL


def test_resolution_is_protected_and_reintroduction_fails() -> None:
    policy, bundle, baseline = _accepted_with_behavior_debt()
    resolved = _behavior_assessment(policy, bundle)
    resolution = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        resolved,
        accepted_baseline_id=baseline.id,
    )
    successor = advance_ratchet_baseline(
        policy,
        baseline,
        bundle,
        resolved,
        resolution,
        accepted_predecessor_id=baseline.id,
    )

    assert resolution.behavior_classifications[0].classification is (
        ViolationClassificationKind.RESOLVED
    )
    assert len(successor.behavior.protected) == 1
    reintroduced = _behavior_assessment(policy, bundle, slots=("legacy",))
    report = evaluate_ratchet(
        policy,
        successor,
        bundle,
        reintroduced,
        accepted_baseline_id=successor.id,
    )
    assert report.behavior_classifications[0].classification is (
        ViolationClassificationKind.REINTRODUCED
    )
    assert report.behavior_outcome is BehaviorOutcome.FAIL


def test_partial_discovery_cannot_claim_behavior_resolution() -> None:
    policy, _, baseline = _accepted_with_behavior_debt()
    bundle = _partial_bundle()
    source = _assessment(bundle)
    current = build_ratchet_assessment(
        policy,
        bundle,
        producer=source.producer,
        procedure_uri=source.procedure_uri,
        capture_context=source.capture_context,
    )

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    classification = next(
        item.classification
        for item in report.behavior_classifications
        if item.key.slot == "legacy"
    )
    assert classification is ViolationClassificationKind.UNKNOWN
    assert report.behavior_outcome is BehaviorOutcome.INCONCLUSIVE


def test_explicit_rejection_can_shrink_behavior_scope_and_protect_resolution() -> None:
    policy, _, baseline = _accepted_with_behavior_debt()
    bundle = _with_quote_rejected()
    current = _assessment(bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert BehaviorSubjectChangeKind.REMOVED_SUBJECT in {
        item.change for item in report.behavior_subject_changes
    }
    classification = next(
        item.classification
        for item in report.behavior_classifications
        if item.key.slot == "legacy"
    )
    assert classification is ViolationClassificationKind.RESOLVED
    assert report.behavior_outcome is BehaviorOutcome.PASS
