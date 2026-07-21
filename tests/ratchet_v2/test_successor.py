from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.onboarding.test_decisions import _base_decision_set
from ucf.ir.models import Producer
from ucf.onboarding import build_onboarding_bundle
from ucf.ratchet.v2 import (
    CombinedOutcome,
    CoverageDebtClassificationKind,
    RatchetBaselineOrigin,
    RatchetErrorCode,
    RatchetValidationError,
    advance_ratchet_baseline,
    establish_ratchet_baseline,
    evaluate_ratchet,
    validate_successor_ratchet_baseline,
)

from .test_assessment import _assessment
from .test_evaluation import (
    _accepted_uncovered,
    _fully_reviewed_bundle,
    _two_uncertain_bundle,
)
from .test_policy import _policy


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
    return build_onboarding_bundle(
        bundle.inventory,
        discovery,
        _base_decision_set(discovery),
    )


def test_coverage_resolution_is_protected_by_exact_successor() -> None:
    policy, initial_bundle, baseline = _accepted_uncovered()
    current_bundle = _fully_reviewed_bundle()
    current = _assessment(current_bundle)
    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    successor = advance_ratchet_baseline(
        policy,
        baseline,
        current_bundle,
        current,
        report,
        accepted_predecessor_id=baseline.id,
    )

    assert successor.origin is RatchetBaselineOrigin.SUCCESSOR
    assert successor.generation == baseline.generation + 1
    assert successor.predecessor is not None
    assert successor.predecessor.target_id == baseline.id
    assert successor.source_evaluation is not None
    assert successor.source_evaluation.target_id == report.id
    assert successor.coverage.allowances == ()
    assert successor.coverage.protected == (
        baseline.coverage.allowances[0].key,
    )
    validate_successor_ratchet_baseline(
        policy,
        baseline,
        current_bundle,
        current,
        report,
        successor,
        accepted_predecessor_id=baseline.id,
    )

    reintroduced = _assessment(initial_bundle)
    result = evaluate_ratchet(
        policy,
        successor,
        initial_bundle,
        reintroduced,
        accepted_baseline_id=successor.id,
    )
    assert result.combined_outcome is CombinedOutcome.FAIL
    assert result.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.REINTRODUCED
    )


def test_qualified_pass_advances_without_hiding_inherited_debt() -> None:
    policy, bundle, baseline = _accepted_uncovered()
    current = _assessment(bundle)
    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
        accepted_baseline_id=baseline.id,
    )

    successor = advance_ratchet_baseline(
        policy,
        baseline,
        bundle,
        current,
        report,
        accepted_predecessor_id=baseline.id,
    )

    assert report.combined_outcome is (
        CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert successor.coverage.allowances == current.coverage.debts
    assert successor.coverage.protected == ()
    assert successor.coverage.groups == current.coverage.groups


def test_new_coverage_debt_cannot_advance() -> None:
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

    with pytest.raises(RatchetValidationError) as captured:
        advance_ratchet_baseline(
            policy,
            baseline,
            current_bundle,
            current,
            report,
            accepted_predecessor_id=baseline.id,
        )

    assert captured.value.code is RatchetErrorCode.ILLEGAL_WEAKENING
    assert captured.value.location == "$.combined_outcome"


def test_protected_reintroduction_fails_even_when_domain_changed() -> None:
    policy, initial_bundle, baseline = _accepted_uncovered()
    resolved_bundle = _fully_reviewed_bundle()
    resolved = _assessment(resolved_bundle)
    resolution = evaluate_ratchet(
        policy,
        baseline,
        resolved_bundle,
        resolved,
        accepted_baseline_id=baseline.id,
    )
    successor = advance_ratchet_baseline(
        policy,
        baseline,
        resolved_bundle,
        resolved,
        resolution,
        accepted_predecessor_id=baseline.id,
    )
    changed_domain_bundle = _with_changed_discovery_producer(initial_bundle)
    reintroduced = _assessment(changed_domain_bundle)

    report = evaluate_ratchet(
        policy,
        successor,
        changed_domain_bundle,
        reintroduced,
        accepted_baseline_id=successor.id,
    )

    assert report.coverage_comparison == "non_comparable_qualification"
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.REINTRODUCED
    )
    assert report.combined_outcome is CombinedOutcome.FAIL


def test_mixed_group_successor_keeps_one_allowance_and_protects_one() -> None:
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

    successor = advance_ratchet_baseline(
        policy,
        baseline,
        current_bundle,
        current,
        report,
        accepted_predecessor_id=baseline.id,
    )

    assert len(successor.coverage.allowances) == 1
    assert len(successor.coverage.protected) == 1
    assert successor.coverage.allowances[0].key != (
        successor.coverage.protected[0]
    )

    reintroduced = _assessment(initial_bundle)
    result = evaluate_ratchet(
        policy,
        successor,
        initial_bundle,
        reintroduced,
        accepted_baseline_id=successor.id,
    )
    assert {
        item.classification for item in result.coverage_classifications
    } == {
        CoverageDebtClassificationKind.UNCHANGED_LEGACY,
        CoverageDebtClassificationKind.REINTRODUCED,
    }
    assert result.combined_outcome is CombinedOutcome.FAIL
