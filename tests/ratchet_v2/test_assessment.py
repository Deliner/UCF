from __future__ import annotations

import hashlib

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.onboarding.test_codec import _request, _result
from tests.onboarding.test_decisions import _base_decision_set, _decisions
from tests.ratchet.test_touch_projection import (
    _inventory_with_records,
    _rebind_inventory,
)
from ucf.inventory import (
    FactKind,
    InventoryDiagnostic,
    InventoryRecordKind,
    InventoryRecordRef,
    PublicInterfaceFact,
    canonical_inventory_json,
    derive_inventory_record_id,
)
from ucf.ir.models import Digest, Producer
from ucf.onboarding import (
    InventoryBinding,
    build_onboarding_bundle,
    derive_discovery_candidate_id,
)
from ucf.ratchet.v2 import (
    CoverageDebtKind,
    CoverageSubjectState,
    RatchetErrorCode,
    RatchetValidationError,
    build_ratchet_assessment,
    canonical_ratchet_json,
    parse_ratchet_assessment_json,
)

from .test_policy import _policy


def _producer() -> Producer:
    return Producer(
        kind="producer",
        name="org.ucf.fixture-ratchet-assessment",
        version="1.0.0",
    )


def _assessment(bundle=None):
    source = bundle or _bundle()
    return build_ratchet_assessment(
        _policy(),
        source,
        producer=_producer(),
        procedure_uri="urn:ucf:ratchet-assessment:fixture:2.0.0",
        capture_context=source.capture_context,
    )


def _uncovered_bundle():
    inventory = _request().inventory
    discovery = _result()
    discovery = discovery.model_copy(
        update={
            "coverage": discovery.coverage.model_copy(
                update={
                    "status": "partial",
                    "uncovered_subjects": (
                        discovery.coverage.eligible_subjects[0],
                    ),
                }
            )
        }
    )
    return build_onboarding_bundle(
        inventory,
        discovery,
        _base_decision_set(discovery),
    )


def _partial_inventory_bundle():
    bundle = _uncovered_bundle()
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
    return _rebind_inventory(bundle, inventory, {})


def _ambiguous_coverage_bundle():
    base = _uncovered_bundle()
    original = next(
        record
        for record in base.inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    duplicate = original.model_copy(
        update={
            "declaration_digest": Digest(
                kind="digest",
                algorithm="sha-256",
                value="f" * 64,
            )
        }
    )
    duplicate = duplicate.model_copy(
        update={"id": derive_inventory_record_id(duplicate)}
    )
    coverage = tuple(
        item.model_copy(update={"record_count": 2})
        if item.fact_kind is FactKind.PUBLIC_INTERFACE
        else item
        for item in base.inventory.coverage
    )
    inventory = _inventory_with_records(
        base.inventory.model_copy(update={"coverage": coverage}),
        (*base.inventory.records, duplicate),
    )
    binding = InventoryBinding(
        kind="inventory_binding",
        schema_uri=inventory.schema_uri,
        inventory_version=inventory.inventory_version,
        subject_uri=inventory.subject_uri,
        source_revision=inventory.source_revision,
        canonical_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(canonical_inventory_json(inventory)).hexdigest(),
        ),
    )
    references = tuple(
        sorted(
            (
                InventoryRecordRef(
                    kind="inventory_record_ref",
                    target_kind=InventoryRecordKind.PUBLIC_INTERFACE,
                    target_id=record.id,
                )
                for record in (original, duplicate)
            ),
            key=lambda item: (item.target_kind.value, item.target_id),
        )
    )
    discovery = base.discovery.model_copy(
        update={
            "inventory_binding": binding,
            "coverage": base.discovery.coverage.model_copy(
                update={
                    "eligible_subjects": references,
                    "uncovered_subjects": references,
                }
            ),
        }
    )
    return build_onboarding_bundle(
        inventory,
        discovery,
        _base_decision_set(discovery),
    )


def _unsupported_direct_evidence_bundle():
    base = _bundle()
    records = {record.id: record for record in base.inventory.records}
    changed_candidates = []
    changed_candidate_id = None
    for candidate in base.discovery.candidates:
        if changed_candidate_id is not None:
            changed_candidates.append(candidate)
            continue
        subject = records[candidate.subject.target_id]
        assert isinstance(subject, PublicInterfaceFact)
        evidence = tuple(
            sorted(
                (*candidate.evidence, subject.entry),
                key=lambda item: (item.target_kind.value, item.target_id),
            )
        )
        changed = candidate.model_copy(update={"evidence": evidence})
        changed_candidates.append(changed)
        changed_candidate_id = candidate.id
    provisional = base.discovery.model_copy(
        update={"candidates": tuple(changed_candidates)}
    )
    rebound = []
    for candidate in changed_candidates:
        if candidate.id == changed_candidate_id:
            candidate = candidate.model_copy(
                update={
                    "id": derive_discovery_candidate_id(
                        candidate,
                        provisional,
                    )
                }
            )
        rebound.append(candidate)
    discovery = provisional.model_copy(
        update={
            "candidates": tuple(
                sorted(rebound, key=lambda item: item.id)
            )
        }
    )
    return build_onboarding_bundle(
        base.inventory,
        discovery,
        _decisions(discovery),
    )


def test_v2_assessment_projects_candidate_groups_and_granular_debt() -> None:
    bundle = _bundle()
    assessment = _assessment(bundle)

    assert assessment.coverage.inventory_coverage == "complete"
    assert assessment.coverage.discovery_coverage == "complete"
    assert assessment.coverage.qualification.subject_uri == (
        bundle.inventory.subject_uri
    )
    assert assessment.coverage.qualification.inventory_producer == (
        bundle.inventory.producer
    )
    assert assessment.coverage.qualification.discovery_producer == (
        bundle.discovery.producer
    )
    assert len(assessment.behavior.subjects) == 2
    assert len(assessment.coverage.groups) == 1

    group = assessment.coverage.groups[0]
    assert group.state is CoverageSubjectState.RECONCILED
    assert [item.disposition.value for item in group.reconciliations] == [
        "edited",
        "accepted",
        "rejected",
        "uncertain",
    ]
    assert len(assessment.coverage.debts) == 1
    debt = assessment.coverage.debts[0]
    assert debt.key.debt_kind is CoverageDebtKind.UNCERTAIN
    assert debt.key.candidate_semantic_digest is not None
    assert debt.key.subject.target_id == group.id

    encoded = canonical_ratchet_json(assessment)
    assert parse_ratchet_assessment_json(encoded) == assessment
    assert canonical_ratchet_json(parse_ratchet_assessment_json(encoded)) == (
        encoded
    )


def test_v2_assessment_keeps_enumerated_uncovered_interface_as_debt() -> None:
    assessment = _assessment(_uncovered_bundle())

    assert assessment.coverage.inventory_coverage == "complete"
    assert assessment.coverage.discovery_coverage == "partial"
    assert len(assessment.behavior.subjects) == 0
    assert len(assessment.coverage.groups) == 1
    assert assessment.coverage.groups[0].state is (
        CoverageSubjectState.UNCOVERED
    )
    assert len(assessment.coverage.debts) == 1
    assert assessment.coverage.debts[0].key.debt_kind is (
        CoverageDebtKind.UNCOVERED
    )
    assert assessment.coverage.debts[0].key.candidate_semantic_digest is None


def test_v2_assessment_rejects_ambiguous_path_independent_subject_keys() -> None:
    with pytest.raises(RatchetValidationError) as captured:
        _assessment(_ambiguous_coverage_bundle())

    assert captured.value.code is (
        RatchetErrorCode.AMBIGUOUS_COVERAGE_IDENTITY
    )
    assert captured.value.location == "$.coverage.groups"


def test_v2_assessment_rejects_unsupported_direct_evidence_kind() -> None:
    bundle = _unsupported_direct_evidence_bundle()
    target_id = next(
        candidate.id
        for candidate in bundle.discovery.candidates
        if any(
            reference.target_kind is InventoryRecordKind.REPOSITORY_ENTRY
            for reference in candidate.evidence
        )
    )
    target_position = next(
        position
        for position, candidate in enumerate(bundle.discovery.candidates)
        if candidate.id == target_id
    )
    evidence_position = next(
        position
        for position, reference in enumerate(
            bundle.discovery.candidates[target_position].evidence
        )
        if reference.target_kind is InventoryRecordKind.REPOSITORY_ENTRY
    )

    with pytest.raises(RatchetValidationError) as captured:
        _assessment(bundle)

    assert captured.value.code is RatchetErrorCode.UNSUPPORTED_EVIDENCE_KIND
    assert captured.value.location == (
        f"$.discovery.candidates[{target_position}]"
        f".evidence[{evidence_position}]"
    )
