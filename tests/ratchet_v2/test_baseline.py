from __future__ import annotations

import pytest

from ucf.ratchet.v2 import (
    RatchetBaselineOrigin,
    RatchetErrorCode,
    RatchetValidationError,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_baseline_id,
    establish_ratchet_baseline,
    parse_ratchet_baseline_json,
)

from .test_assessment import (
    _assessment,
    _partial_inventory_bundle,
    _uncovered_bundle,
)
from .test_policy import _policy


def test_v2_establishes_enumerated_legacy_coverage_debt() -> None:
    policy = _policy()
    bundle = _uncovered_bundle()
    assessment = _assessment(bundle)

    baseline = establish_ratchet_baseline(policy, bundle, assessment)

    assert baseline.origin is RatchetBaselineOrigin.INITIAL
    assert baseline.generation == 0
    assert baseline.predecessor is None
    assert baseline.source_evaluation is None
    assert baseline.migrated_from is None
    assert baseline.behavior.subjects == assessment.behavior.subjects
    assert baseline.behavior.allowances == ()
    assert baseline.behavior.protected == ()
    assert baseline.coverage.qualification == (
        assessment.coverage.qualification
    )
    assert baseline.coverage.groups == assessment.coverage.groups
    assert baseline.coverage.allowances == assessment.coverage.debts
    assert len(baseline.coverage.allowances) == 1
    assert baseline.coverage.protected == ()

    encoded = canonical_ratchet_json(baseline)
    assert parse_ratchet_baseline_json(encoded) == baseline
    assert canonical_ratchet_json(parse_ratchet_baseline_json(encoded)) == (
        encoded
    )


@pytest.mark.parametrize("mutation", ["omit", "protect_current"])
def test_baseline_parser_rejects_untracked_current_coverage_debt(
    mutation: str,
) -> None:
    policy = _policy()
    bundle = _uncovered_bundle()
    baseline = establish_ratchet_baseline(
        policy,
        bundle,
        _assessment(bundle),
    )
    debt = baseline.coverage.allowances[0]
    coverage = baseline.coverage.model_copy(
        update={
            "allowances": (),
            "protected": (debt.key,) if mutation == "protect_current" else (),
        }
    )
    forged = baseline.model_copy(update={"coverage": coverage})
    forged = forged.model_copy(update={"id": derive_baseline_id(forged)})

    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_baseline_json(canonical_ratchet_json(forged))

    assert captured.value.code is RatchetErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == "$.coverage.allowances"


def test_baseline_parser_rejects_recomputed_group_semantic_fingerprint() -> None:
    policy = _policy()
    bundle = _uncovered_bundle()
    baseline = establish_ratchet_baseline(
        policy,
        bundle,
        _assessment(bundle),
    )
    group = baseline.coverage.groups[0]
    changed_semantic = group.semantic.model_copy(
        update={
            "digest": group.semantic.digest.model_copy(
                update={"value": "f" * 64}
            )
        }
    )
    changed_group = group.model_copy(update={"semantic": changed_semantic})
    debt = baseline.coverage.allowances[0].model_copy(
        update={"semantic": changed_semantic}
    )
    coverage = baseline.coverage.model_copy(
        update={"groups": (changed_group,), "allowances": (debt,)}
    )
    forged = baseline.model_copy(update={"coverage": coverage})
    forged = forged.model_copy(update={"id": derive_baseline_id(forged)})

    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_baseline_json(canonical_ratchet_json(forged))

    assert captured.value.code is RatchetErrorCode.CONTENT_IDENTITY_MISMATCH
    assert captured.value.location == "$.coverage.groups[0].semantic"


def test_initial_baseline_rejects_partial_inventory_domain() -> None:
    policy = _policy()
    bundle = _partial_inventory_bundle()
    assessment = _assessment(bundle)

    with pytest.raises(RatchetValidationError) as captured:
        establish_ratchet_baseline(policy, bundle, assessment)

    assert captured.value.code is (
        RatchetErrorCode.INCOMPLETE_COMPARISON_DOMAIN
    )
    assert captured.value.location == (
        "$.source_assessment.coverage.inventory_coverage"
    )


def test_initial_baseline_rejects_partial_rule_coverage() -> None:
    policy = _policy()
    bundle = _uncovered_bundle()
    source = _assessment(bundle)
    assessment = build_ratchet_assessment(
        policy,
        bundle,
        producer=source.producer,
        procedure_uri=source.procedure_uri,
        capture_context=source.capture_context,
        partial_rule_ids={policy.rules[0].id},
    )

    with pytest.raises(RatchetValidationError) as captured:
        establish_ratchet_baseline(policy, bundle, assessment)

    assert captured.value.code is RatchetErrorCode.INCOMPLETE_RULE_COVERAGE
    assert captured.value.location == (
        "$.source_assessment.behavior.coverage"
    )
