from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.onboarding.test_decisions import _decisions
from tests.ratchet.test_touch_projection import (
    _candidate_confidence_change,
    _capture_only,
    _inventory_with_records,
    _rebind_inventory,
)
from ucf.inventory import PublicInterfaceFact, derive_inventory_record_id
from ucf.ir.models import Producer
from ucf.onboarding import (
    RejectedDecision,
    UncertainDecision,
    build_onboarding_bundle,
    derive_decision_id,
    derive_discovery_candidate_id,
)
from ucf.ratchet.v2 import (
    BehaviorOutcome,
    CombinedOutcome,
    CoverageDebtClassificationKind,
    CoverageOutcome,
    RatchetErrorCode,
    RatchetValidationError,
    ViolationInput,
    WeakeningDeltaStatus,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_baseline_id,
    establish_ratchet_baseline,
    evaluate_ratchet,
    parse_ratchet_evaluation_report_json,
    validate_ratchet_evaluation_report,
)

from .test_assessment import _assessment, _partial_inventory_bundle, _uncovered_bundle
from .test_policy import _policy


def _accepted_uncovered():
    policy = _policy()
    bundle = _uncovered_bundle()
    assessment = _assessment(bundle)
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    return policy, bundle, baseline


def _with_changed_discovery_producer(bundle):
    discovery = bundle.discovery.model_copy(
        update={
            "producer": Producer(
                kind="producer",
                name="org.ucf.changed-discovery-adapter",
                version="2.0.0",
            )
        }
    )
    discovery = discovery.model_copy(
        update={
            "candidates": tuple(
                sorted(
                    (
                        candidate.model_copy(
                            update={
                                "id": derive_discovery_candidate_id(
                                    candidate,
                                    discovery,
                                )
                            }
                        )
                        for candidate in discovery.candidates
                    ),
                    key=lambda item: item.id,
                )
            )
        }
    )
    return build_onboarding_bundle(
        bundle.inventory,
        discovery,
        _decisions(discovery),
    )


def _fully_reviewed_bundle(bundle=None):
    bundle = bundle or _bundle()
    changed = tuple(
        RejectedDecision(
            kind="rejected_decision",
            id=f"decision.{'0' * 64}",
            candidate=decision.candidate,
            reason="The reviewer explicitly rejects this candidate.",
        )
        if isinstance(decision, UncertainDecision)
        else decision
        for decision in bundle.decisions.decisions
    )
    provisional = bundle.decisions.model_copy(
        update={"decisions": changed}
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


def _renamed_interface_bundle():
    bundle = _bundle()
    interface = next(
        record
        for record in bundle.inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    changed = interface.model_copy(update={"name": "shorten_v2"})
    changed = changed.model_copy(
        update={"id": derive_inventory_record_id(changed)}
    )
    inventory = _inventory_with_records(
        bundle.inventory,
        (
            changed if record.id == interface.id else record
            for record in bundle.inventory.records
        ),
    )
    rebound = _rebind_inventory(
        bundle,
        inventory,
        {interface.id: changed.id},
    )
    return _fully_reviewed_bundle(rebound)


def _two_uncertain_bundle():
    bundle = _bundle()
    candidates = {
        candidate.id: candidate for candidate in bundle.discovery.candidates
    }
    changed = []
    for decision in bundle.decisions.decisions:
        candidate = candidates[decision.candidate.candidate_id]
        if candidate.proposal.root.target_id.endswith("normalize-coupon"):
            decision = UncertainDecision(
                kind="uncertain_decision",
                id=f"decision.{'0' * 64}",
                candidate=decision.candidate,
                reason="This second candidate also remains unresolved.",
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


def test_exact_inherited_coverage_debt_has_only_a_qualified_pass() -> None:
    policy, bundle, baseline = _accepted_uncovered()
    current = _assessment(bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.behavior_outcome is BehaviorOutcome.PASS
    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.combined_outcome is (
        CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert [item.classification for item in report.coverage_classifications] == [
        CoverageDebtClassificationKind.UNCHANGED_LEGACY
    ]
    assert report.behavior_delta.status is WeakeningDeltaStatus.NONE
    assert report.coverage_delta.status is WeakeningDeltaStatus.NONE

    encoded = canonical_ratchet_json(report)
    parsed = parse_ratchet_evaluation_report_json(encoded)
    assert parsed == report
    assert canonical_ratchet_json(parsed) == encoded
    validate_ratchet_evaluation_report(
        policy,
        baseline,
        bundle,
        current,
        parsed,
        accepted_baseline_id=baseline.id,
    )


def test_trace_only_change_does_not_create_new_coverage_debt() -> None:
    policy = _policy()
    initial_bundle = _bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _capture_only(initial_bundle)
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.UNCHANGED_LEGACY
    )


def test_observed_change_to_inherited_coverage_debt_fails() -> None:
    policy = _policy()
    initial_bundle = _bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _candidate_confidence_change(
        initial_bundle,
        "legacy-discount-hint",
    )
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_outcome is CoverageOutcome.FAIL
    assert report.combined_outcome is CombinedOutcome.FAIL
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.CHANGED_REGRESSION
    )
    assert report.coverage_delta.status is (
        WeakeningDeltaStatus.REVIEW_REQUIRED
    )


def test_reviewed_candidate_becoming_uncertain_is_reintroduced() -> None:
    policy = _policy()
    initial_bundle = _fully_reviewed_bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _bundle()
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert baseline.coverage.allowances == ()
    assert report.coverage_outcome is CoverageOutcome.FAIL
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.REINTRODUCED
    )


def test_reviewed_recurrence_beats_qualification_drift() -> None:
    policy = _policy()
    initial_bundle = _fully_reviewed_bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _with_changed_discovery_producer(_bundle())
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_comparison == "non_comparable_qualification"
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.REINTRODUCED
    )
    assert report.coverage_outcome is CoverageOutcome.FAIL
    assert report.combined_outcome is CombinedOutcome.FAIL


def test_unmatched_debt_with_qualification_drift_remains_unknown() -> None:
    policy, _, baseline = _accepted_uncovered()
    current_bundle = _with_changed_discovery_producer(_bundle())
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_comparison == "non_comparable_qualification"
    assert {
        item.classification for item in report.coverage_classifications
    } == {CoverageDebtClassificationKind.UNKNOWN}
    assert report.coverage_outcome is CoverageOutcome.INCONCLUSIVE
    assert report.combined_outcome is CombinedOutcome.INCONCLUSIVE


def test_explicit_reconciliation_resolves_only_the_exact_coverage_debt() -> None:
    policy = _policy()
    initial_bundle = _bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _fully_reviewed_bundle()
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_outcome is CoverageOutcome.PASS
    assert report.combined_outcome is CombinedOutcome.PASS
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.RESOLVED
    )
    assert report.coverage_delta.status is WeakeningDeltaStatus.TIGHTENING
    assert report.coverage_delta.removed_allowances == (
        baseline.coverage.allowances[0].key,
    )


def test_partial_rule_coverage_makes_combined_result_inconclusive() -> None:
    policy, bundle, baseline = _accepted_uncovered()
    source = _assessment(bundle)
    current = build_ratchet_assessment(
        policy,
        bundle,
        producer=source.producer,
        procedure_uri=source.procedure_uri,
        capture_context=source.capture_context,
        partial_rule_ids={policy.rules[0].id},
    )

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.behavior_outcome is BehaviorOutcome.INCONCLUSIVE
    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.combined_outcome is CombinedOutcome.INCONCLUSIVE


def test_evaluation_requires_the_independently_accepted_baseline_id() -> None:
    policy = _policy()
    initial_bundle = _bundle()
    initial = _assessment(initial_bundle)
    accepted = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _candidate_confidence_change(
        initial_bundle,
        "legacy-discount-hint",
    )
    current = _assessment(current_bundle)
    forged = accepted.model_copy(
        update={
            "coverage": accepted.coverage.model_copy(
                update={
                    "groups": current.coverage.groups,
                    "allowances": current.coverage.debts,
                }
            )
        }
    )
    forged = forged.model_copy(update={"id": derive_baseline_id(forged)})

    with pytest.raises(RatchetValidationError) as captured:
        evaluate_ratchet(
            policy,
            forged,
            current_bundle,
            current,
            accepted_baseline_id=accepted.id,
        )

    assert captured.value.code is RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH
    assert captured.value.location == "$.accepted_baseline_id"


def test_partial_inventory_is_inconclusive_for_unchanged_visible_debt() -> None:
    policy, _, baseline = _accepted_uncovered()
    current_bundle = _partial_inventory_bundle()
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_comparison == "incomplete_inventory"
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.UNCHANGED_LEGACY
    )
    assert report.coverage_outcome is CoverageOutcome.INCONCLUSIVE
    assert report.combined_outcome is CombinedOutcome.INCONCLUSIVE


def test_visible_new_debt_fails_even_with_partial_inventory() -> None:
    policy = _policy()
    initial_bundle = _fully_reviewed_bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _partial_inventory_bundle()
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_comparison == "incomplete_inventory"
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.NEW_REGRESSION
    )
    assert report.coverage_outcome is CoverageOutcome.FAIL
    assert report.combined_outcome is CombinedOutcome.FAIL


def test_behavior_regression_beats_partial_rule_inconclusive() -> None:
    policy = _policy()
    bundle = _bundle()
    initial = _assessment(bundle)
    baseline = establish_ratchet_baseline(policy, bundle, initial)
    subject = initial.behavior.subjects[0]
    current = build_ratchet_assessment(
        policy,
        bundle,
        producer=initial.producer,
        procedure_uri=initial.procedure_uri,
        capture_context=initial.capture_context,
        violations=(
            ViolationInput(
                kind="ratchet_violation_input",
                rule_id=policy.rules[0].id,
                subject=subject.key,
                slot="new-regression",
                message="A definite new regression is present.",
            ),
        ),
        partial_rule_ids={policy.rules[0].id},
    )

    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.behavior_outcome is BehaviorOutcome.FAIL
    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.combined_outcome is CombinedOutcome.FAIL


def test_mixed_group_resolves_one_debt_without_hiding_the_other() -> None:
    policy = _policy()
    initial_bundle = _two_uncertain_bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _bundle()
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert len(baseline.coverage.allowances) == 2
    assert {
        item.classification for item in report.coverage_classifications
    } == {
        CoverageDebtClassificationKind.RESOLVED,
        CoverageDebtClassificationKind.UNCHANGED_LEGACY,
    }
    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.coverage_delta.status is WeakeningDeltaStatus.TIGHTENING
    assert len(report.coverage_delta.removed_allowances) == 1


def test_missing_predecessor_subject_is_inconclusive_not_resolution() -> None:
    policy = _policy()
    initial_bundle = _fully_reviewed_bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _renamed_interface_bundle()
    current = _assessment(current_bundle)

    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    assert report.coverage_comparison == "comparable"
    assert {
        change.change.value for change in report.coverage_subject_changes
    } == {"unknown_subject", "new_subject"}
    assert report.coverage_classifications == ()
    assert report.coverage_outcome is CoverageOutcome.INCONCLUSIVE
    assert report.combined_outcome is CombinedOutcome.INCONCLUSIVE
