from __future__ import annotations

import pytest

from tests.ratchet.test_assessment import _assessment as _v1_assessment
from tests.ratchet.test_evaluation import _current as _v1_current
from tests.ratchet.test_touch_projection import (
    _capture_only,
    _inventory_with_records,
    _rebind_inventory,
)
from ucf.adapter_protocol import CapabilitySelection
from ucf.inventory import (
    FactKind,
    InventoryDiagnostic,
    derive_inventory_record_id,
)
from ucf.ratchet import (
    advance_ratchet_baseline as advance_v1_baseline,
)
from ucf.ratchet import (
    build_ratchet_assessment as build_v1_ratchet_assessment,
)
from ucf.ratchet import (
    establish_ratchet_baseline as establish_v1_baseline,
)
from ucf.ratchet import evaluate_ratchet as evaluate_v1_ratchet
from ucf.ratchet.v2 import (
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    CoverageDebtKind,
    RatchetBaselineOrigin,
    RatchetErrorCode,
    RatchetPolicy,
    RatchetRule,
    RatchetValidationError,
    advance_ratchet_baseline,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_policy_id,
    evaluate_ratchet,
    migrate_ratchet_v1_baseline,
    parse_ratchet_baseline_json,
    validate_migrated_ratchet_baseline,
)


def _compatible_target_policy(source) -> RatchetPolicy:
    rules = tuple(
        RatchetRule.model_validate_json(rule.model_dump_json())
        for rule in source.rules
    )
    provisional = RatchetPolicy(
        kind="ratchet_policy",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_POLICY_SCHEMA_URI,
        id=f"policy.{'0' * 64}",
        evaluator=CapabilitySelection(
            kind="capability",
            name=RATCHET_EVALUATOR_CAPABILITY,
            version=RATCHET_VERSION,
        ),
        rules=rules,
    )
    return provisional.model_copy(update={"id": derive_policy_id(provisional)})


def _partial_public_interface_v1_source():
    source_policy, bundle, template = _v1_assessment(violations=False)
    diagnostic = InventoryDiagnostic(
        kind="inventory_diagnostic",
        id=f"diagnostic.{'0' * 64}",
        severity="error",
        code="org.ucf.inventory.public-interface-partial",
        fact_kind=FactKind.PUBLIC_INTERFACE,
        path=".",
        stage="classify",
        message="Public-interface inventory is intentionally partial.",
        provenance=None,
    )
    diagnostic = diagnostic.model_copy(
        update={"id": derive_inventory_record_id(diagnostic)}
    )
    coverage = tuple(
        item.model_copy(update={"status": "partial"})
        if item.fact_kind is FactKind.PUBLIC_INTERFACE
        else item
        for item in bundle.inventory.coverage
    )
    inventory = _inventory_with_records(
        bundle.inventory.model_copy(update={"coverage": coverage}),
        (*bundle.inventory.records, diagnostic),
    )
    bundle = _rebind_inventory(bundle, inventory, {})
    source_assessment = build_v1_ratchet_assessment(
        source_policy,
        bundle,
        producer=template.producer,
        procedure_uri=template.procedure_uri,
        capture_context=template.capture_context,
    )
    source_baseline = establish_v1_baseline(
        source_policy,
        bundle,
        source_assessment,
    )
    return source_policy, bundle, source_assessment, source_baseline


def test_v1_migration_preserves_behavior_and_imports_uncertain_debt() -> None:
    source_policy, bundle, source_assessment = _v1_assessment()
    source_baseline = establish_v1_baseline(
        source_policy,
        bundle,
        source_assessment,
    )
    target_policy = _compatible_target_policy(source_policy)

    migrated = migrate_ratchet_v1_baseline(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
        accepted_source_baseline_id=source_baseline.id,
    )

    assert migrated.origin is RatchetBaselineOrigin.MIGRATED_V1
    assert migrated.generation == source_baseline.generation
    assert len(migrated.behavior.allowances) == len(source_baseline.allowances)
    assert len(migrated.behavior.protected) == len(source_baseline.protected)
    assert len(migrated.coverage.allowances) == 1
    assert migrated.coverage.allowances[0].key.debt_kind is (
        CoverageDebtKind.UNCERTAIN
    )
    assert migrated.migrated_from is not None
    assert migrated.migrated_from.baseline.target_id == source_baseline.id
    assert migrated.migrated_from.assessment.target_id == source_assessment.id
    assert migrated.source_assessment.schema_version == "1.0.0"

    encoded = canonical_ratchet_json(migrated)
    assert parse_ratchet_baseline_json(encoded) == migrated
    validate_migrated_ratchet_baseline(
        target_policy,
        source_policy,
        source_baseline,
        source_assessment,
        bundle,
        migrated,
        accepted_source_baseline_id=source_baseline.id,
    )


def test_nonzero_v1_tip_becomes_v2_root_without_generation_reset() -> None:
    source_policy, bundle, source_assessment = _v1_assessment()
    source_baseline = establish_v1_baseline(
        source_policy,
        bundle,
        source_assessment,
    )
    current_v1 = _v1_current(source_policy, bundle)
    report_v1 = evaluate_v1_ratchet(
        source_policy,
        source_baseline,
        bundle,
        current_v1,
    )
    source_tip = advance_v1_baseline(
        source_policy,
        source_baseline,
        bundle,
        current_v1,
        report_v1,
    )
    target_policy = _compatible_target_policy(source_policy)

    migrated = migrate_ratchet_v1_baseline(
        target_policy,
        source_policy,
        source_tip,
        current_v1,
        bundle,
        accepted_source_baseline_id=source_tip.id,
    )

    assert migrated.generation == 1
    assert migrated.predecessor is None
    assert migrated.migrated_from is not None
    assert migrated.migrated_from.baseline.generation == 1
    assert len(migrated.behavior.protected) == 1

    current_v2 = build_ratchet_assessment(
        target_policy,
        bundle,
        producer=current_v1.producer,
        procedure_uri="urn:ucf:ratchet-assessment:migrated:2.0.0",
        capture_context=current_v1.capture_context,
    )
    report_v2 = evaluate_ratchet(
        target_policy,
        migrated,
        bundle,
        current_v2,
        accepted_baseline_id=migrated.id,
    )
    successor = advance_ratchet_baseline(
        target_policy,
        migrated,
        bundle,
        current_v2,
        report_v2,
        accepted_predecessor_id=migrated.id,
    )
    assert successor.generation == 2


def test_migration_rejects_mismatched_source_bundle() -> None:
    source_policy, bundle, source_assessment = _v1_assessment()
    source_baseline = establish_v1_baseline(
        source_policy,
        bundle,
        source_assessment,
    )
    target_policy = _compatible_target_policy(source_policy)

    with pytest.raises(RatchetValidationError) as captured:
        migrate_ratchet_v1_baseline(
            target_policy,
            source_policy,
            source_baseline,
            source_assessment,
            _capture_only(bundle),
            accepted_source_baseline_id=source_baseline.id,
        )

    assert captured.value.code is RatchetErrorCode.MIGRATION_SOURCE_MISMATCH
    assert captured.value.location == "$.source"


def test_migration_requires_the_accepted_v1_tip_identity() -> None:
    source_policy, bundle, source_assessment = _v1_assessment()
    source_baseline = establish_v1_baseline(
        source_policy,
        bundle,
        source_assessment,
    )
    target_policy = _compatible_target_policy(source_policy)

    with pytest.raises(RatchetValidationError) as captured:
        migrate_ratchet_v1_baseline(
            target_policy,
            source_policy,
            source_baseline,
            source_assessment,
            bundle,
            accepted_source_baseline_id=f"baseline.{'f' * 64}",
        )

    assert captured.value.code is RatchetErrorCode.MIGRATION_SOURCE_MISMATCH
    assert captured.value.location == "$.accepted_source_baseline_id"


def test_migration_rejects_partial_public_interface_inventory_domain() -> None:
    source_policy, bundle, source_assessment, source_baseline = (
        _partial_public_interface_v1_source()
    )
    target_policy = _compatible_target_policy(source_policy)

    assert bundle.discovery.coverage.status == "complete"
    assert source_assessment.subject_coverage == "complete"
    assert (
        next(
            item.status
            for item in bundle.inventory.coverage
            if item.fact_kind is FactKind.PUBLIC_INTERFACE
        )
        == "partial"
    )

    with pytest.raises(RatchetValidationError) as captured:
        migrate_ratchet_v1_baseline(
            target_policy,
            source_policy,
            source_baseline,
            source_assessment,
            bundle,
            accepted_source_baseline_id=source_baseline.id,
        )

    assert captured.value.code is (RatchetErrorCode.INCOMPLETE_COMPARISON_DOMAIN)
    assert captured.value.location == (
        "$.source_assessment.coverage.inventory_coverage"
    )


def test_migrated_validation_rejects_partial_public_interface_source() -> None:
    full_policy, full_bundle, full_assessment = _v1_assessment()
    full_baseline = establish_v1_baseline(
        full_policy,
        full_bundle,
        full_assessment,
    )
    full_target = _compatible_target_policy(full_policy)
    forged = migrate_ratchet_v1_baseline(
        full_target,
        full_policy,
        full_baseline,
        full_assessment,
        full_bundle,
        accepted_source_baseline_id=full_baseline.id,
    )
    source_policy, bundle, source_assessment, source_baseline = (
        _partial_public_interface_v1_source()
    )

    with pytest.raises(RatchetValidationError) as captured:
        validate_migrated_ratchet_baseline(
            _compatible_target_policy(source_policy),
            source_policy,
            source_baseline,
            source_assessment,
            bundle,
            forged,
            accepted_source_baseline_id=source_baseline.id,
        )

    assert captured.value.code is (RatchetErrorCode.INCOMPLETE_COMPARISON_DOMAIN)
    assert captured.value.location == (
        "$.source_assessment.coverage.inventory_coverage"
    )
