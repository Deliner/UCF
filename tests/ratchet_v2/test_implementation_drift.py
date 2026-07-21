from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.ratchet.test_touch_projection import (
    _capture_only,
    _inventory_with_records,
    _path_rename,
    _rebind_inventory,
)
from tests.ratchet_v2.test_assessment import _assessment
from tests.ratchet_v2.test_policy import _policy
from ucf.inventory import (
    FactKind,
    InventoryProvenance,
    PublicInterfaceFact,
    RepositoryEntryFact,
    derive_inventory_record_id,
)
from ucf.ir.models import Digest
from ucf.ratchet.v2 import (
    BehaviorSubjectChangeKind,
    CombinedOutcome,
    CoverageDebtClassificationKind,
    CoverageOutcome,
    CoverageSubjectChangeKind,
    RatchetErrorCode,
    RatchetValidationError,
    establish_ratchet_baseline,
    evaluate_ratchet,
)
from ucf.ratchet.v2.projection import _normalize_public_interface


def _digest(value: str) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=value * 64,
    )


def _backing_records(bundle):
    records = {record.id: record for record in bundle.inventory.records}
    interface = next(
        record
        for record in bundle.inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    entry = records[interface.entry.target_id]
    provenance = records[interface.provenance.target_id]
    assert isinstance(entry, RepositoryEntryFact)
    assert isinstance(provenance, InventoryProvenance)
    return interface, entry, provenance


def _edit_entry_content(bundle, path: str, digest_character: str):
    entry = next(
        record
        for record in bundle.inventory.records
        if isinstance(record, RepositoryEntryFact) and record.path == path
    )
    records = {record.id: record for record in bundle.inventory.records}
    provenance = records[entry.provenance.target_id]
    assert isinstance(provenance, InventoryProvenance)
    content_digest = _digest(digest_character)
    changed_provenance = provenance.model_copy(
        update={"content_digest": content_digest}
    )
    changed_provenance = changed_provenance.model_copy(
        update={"id": derive_inventory_record_id(changed_provenance)}
    )
    changed_entry = entry.model_copy(
        update={
            "content_digest": content_digest,
            "provenance": entry.provenance.model_copy(
                update={"target_id": changed_provenance.id}
            ),
        }
    )
    changed_entry = changed_entry.model_copy(
        update={"id": derive_inventory_record_id(changed_entry)}
    )
    replacements = {
        provenance.id: changed_provenance,
        entry.id: changed_entry,
    }
    for interface in (
        record
        for record in bundle.inventory.records
        if isinstance(record, PublicInterfaceFact)
        and record.entry.target_id == entry.id
    ):
        changed_interface = interface.model_copy(
            update={
                "entry": interface.entry.model_copy(
                    update={"target_id": changed_entry.id}
                ),
                "provenance": interface.provenance.model_copy(
                    update={"target_id": changed_provenance.id}
                ),
            }
        )
        changed_interface = changed_interface.model_copy(
            update={"id": derive_inventory_record_id(changed_interface)}
        )
        replacements[interface.id] = changed_interface
    inventory = _inventory_with_records(
        bundle.inventory,
        (
            replacements.get(record.id, record)
            for record in bundle.inventory.records
        ),
    )
    return _rebind_inventory(
        bundle,
        inventory,
        {
            old_id: replacement.id
            for old_id, replacement in replacements.items()
        },
    )


def _body_only_edit(bundle):
    return _edit_entry_content(bundle, "src/service.py", "a")


def _bundle_with_unrelated_entry():
    bundle = _bundle()
    _, source_entry, source_provenance = _backing_records(bundle)
    content_digest = _digest("8")
    provenance = source_provenance.model_copy(
        update={
            "source_path": "src/unrelated.py",
            "content_digest": content_digest,
        }
    )
    provenance = provenance.model_copy(
        update={"id": derive_inventory_record_id(provenance)}
    )
    entry = source_entry.model_copy(
        update={
            "path": "src/unrelated.py",
            "size_bytes": 18,
            "content_digest": content_digest,
            "provenance": source_entry.provenance.model_copy(
                update={"target_id": provenance.id}
            ),
        }
    )
    entry = entry.model_copy(
        update={"id": derive_inventory_record_id(entry)}
    )
    coverage = tuple(
        item.model_copy(update={"record_count": item.record_count + 1})
        if item.fact_kind is FactKind.REPOSITORY_ENTRY
        else item
        for item in bundle.inventory.coverage
    )
    inventory = _inventory_with_records(
        bundle.inventory.model_copy(update={"coverage": coverage}),
        (*bundle.inventory.records, provenance, entry),
    )
    return _rebind_inventory(bundle, inventory, {})


def _unrelated_body_edit(bundle):
    return _edit_entry_content(bundle, "src/unrelated.py", "9")


def _observation(assessment) -> tuple[object, ...]:
    return (
        tuple(
            (subject.id, subject.semantic, subject.observed)
            for subject in assessment.behavior.subjects
        ),
        tuple(
            (
                group.id,
                group.semantic,
                group.observed,
                tuple(
                    (item.semantic, item.observed)
                    for item in group.reconciliations
                ),
            )
            for group in assessment.coverage.groups
        ),
        tuple(
            (debt.id, debt.semantic, debt.observed)
            for debt in assessment.coverage.debts
        ),
    )


def _evaluate_transition(initial_bundle, current_bundle):
    policy = _policy()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current = _assessment(current_bundle)
    report = evaluate_ratchet(
        policy,
        baseline,
        current_bundle,
        current,
        accepted_baseline_id=baseline.id,
    )
    return initial, current, report


def test_body_only_edit_of_the_exact_backing_entry_is_observed_and_fails() -> None:
    initial_bundle = _bundle()
    current_bundle = _body_only_edit(initial_bundle)
    initial_interface, initial_entry, _ = _backing_records(initial_bundle)
    current_interface, current_entry, _ = _backing_records(current_bundle)

    assert initial_bundle.inventory.source_revision != (
        current_bundle.inventory.source_revision
    )
    assert initial_entry.path == current_entry.path
    assert initial_entry.content_digest != current_entry.content_digest
    assert initial_entry.id != current_entry.id
    assert initial_interface.declaration_digest == (
        current_interface.declaration_digest
    )
    assert initial_interface.id != current_interface.id

    initial, current, report = _evaluate_transition(
        initial_bundle,
        current_bundle,
    )
    assert [subject.semantic for subject in initial.behavior.subjects] == [
        subject.semantic for subject in current.behavior.subjects
    ]
    assert all(
        before.observed != after.observed
        for before, after in zip(
            initial.behavior.subjects,
            current.behavior.subjects,
            strict=True,
        )
    )
    initial_group = initial.coverage.groups[0]
    current_group = current.coverage.groups[0]
    assert initial_group.id == current_group.id
    assert initial_group.semantic == current_group.semantic
    assert initial_group.observed != current_group.observed
    assert all(
        before.semantic == after.semantic
        and before.observed != after.observed
        for before, after in zip(
            initial_group.reconciliations,
            current_group.reconciliations,
            strict=True,
        )
    )
    assert initial.coverage.debts[0].id == current.coverage.debts[0].id
    assert initial.coverage.debts[0].observed != current.coverage.debts[0].observed
    assert {item.change for item in report.behavior_subject_changes} == {
        BehaviorSubjectChangeKind.OBSERVED_CHANGED
    }
    assert report.coverage_subject_changes[0].change is (
        CoverageSubjectChangeKind.OBSERVED_CHANGED
    )
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.CHANGED_REGRESSION
    )
    assert report.coverage_outcome is CoverageOutcome.FAIL
    assert report.combined_outcome is CombinedOutcome.FAIL


def test_unrelated_entry_body_edit_remains_trace_only_for_target_observation() -> None:
    initial_bundle = _bundle_with_unrelated_entry()
    current_bundle = _unrelated_body_edit(initial_bundle)

    assert initial_bundle.inventory.source_revision != (
        current_bundle.inventory.source_revision
    )
    initial, current, report = _evaluate_transition(
        initial_bundle,
        current_bundle,
    )

    assert _observation(initial) == _observation(current)
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.UNCHANGED_LEGACY
    )
    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.coverage_delta.added_allowances == ()


@pytest.mark.parametrize(
    "change",
    [_capture_only, _path_rename],
    ids=["capture", "path"],
)
def test_capture_and_path_trace_churn_do_not_change_target_observation(
    change: Callable,
) -> None:
    initial_bundle = _bundle()
    current_bundle = change(initial_bundle)
    initial, current, report = _evaluate_transition(
        initial_bundle,
        current_bundle,
    )

    assert _observation(initial) == _observation(current)
    assert report.coverage_classifications[0].classification is (
        CoverageDebtClassificationKind.UNCHANGED_LEGACY
    )
    assert report.coverage_outcome is (
        CoverageOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )
    assert report.coverage_delta.added_allowances == ()


@pytest.mark.parametrize(
    ("target", "expected_code"),
    [
        (f"entry.{'f' * 64}", RatchetErrorCode.BROKEN_REFERENCE),
        (None, RatchetErrorCode.WRONG_TARGET_KIND),
    ],
    ids=["broken", "wrong-kind"],
)
def test_public_interface_backing_entry_is_resolved_strictly(
    target: str | None,
    expected_code: RatchetErrorCode,
) -> None:
    bundle = _bundle()
    interface, _, provenance = _backing_records(bundle)
    changed = interface.model_copy(
        update={
            "entry": interface.entry.model_copy(
                update={"target_id": target or provenance.id}
            )
        }
    )
    records = {record.id: record for record in bundle.inventory.records}

    with pytest.raises(RatchetValidationError) as captured:
        _normalize_public_interface(
            changed,
            records,
            location="$.interface",
        )

    assert captured.value.code is expected_code
    assert captured.value.location == "$.interface.entry"
