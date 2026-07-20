from __future__ import annotations

import hashlib
import json

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.onboarding.test_candidates import _proposal
from tests.onboarding.test_decisions import _decisions
from ucf.inventory import (
    InventoryProvenance,
    InventoryRecordRef,
    InventorySnapshot,
    PublicInterfaceFact,
    RepositoryEntryFact,
    canonical_inventory_json,
    derive_inventory_record_id,
    derive_inventory_source_revision,
)
from ucf.ir.models import Digest, EntityKind, Producer, ValueKind
from ucf.onboarding import (
    CaptureContext,
    EditedDecision,
    InventoryBinding,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    derive_candidate_semantic_digest,
    derive_decision_id,
    derive_discovery_candidate_id,
)
from ucf.ratchet import (
    BehaviorSubjectKey,
    EvaluationOutcome,
    SubjectChangeKind,
    ViolationClassificationKind,
    ViolationInput,
    build_ratchet_assessment,
    derive_subject_snapshots,
    establish_ratchet_baseline,
    evaluate_ratchet,
)

from .test_policy import _policy

type SubjectKey = tuple[str, str, str]

_QUOTE: SubjectKey = (
    "urn:ucf:repository:fixture",
    "use_case",
    "use-case.quote-order",
)
_RECEIPT: SubjectKey = (
    "urn:ucf:repository:fixture",
    "use_case",
    "use-case.render-receipt",
)
_SUBJECTS = frozenset({_QUOTE, _RECEIPT})
_VARIANTS = (
    "capture_only",
    "semantic_edit",
    "accepted_confidence",
    "rejected_confidence",
    "unrelated_inventory_fact",
    "path_rename",
)
_EXPECTED_FINGERPRINT_CHANGES = {
    "capture_only": (frozenset(), frozenset()),
    "semantic_edit": (frozenset({_RECEIPT}), frozenset()),
    "accepted_confidence": (frozenset(), frozenset({_QUOTE})),
    "rejected_confidence": (frozenset(), frozenset()),
    "unrelated_inventory_fact": (frozenset(), frozenset()),
    "path_rename": (frozenset(), frozenset()),
}


def _subject_key(snapshot) -> SubjectKey:
    return (
        snapshot.key.subject_uri,
        snapshot.key.target_kind.value,
        snapshot.key.target_id,
    )


def _fingerprints(bundle) -> dict[SubjectKey, tuple[str, str]]:
    return {
        _subject_key(snapshot): (
            snapshot.semantic.digest.value,
            snapshot.observed.digest.value,
        )
        for snapshot in derive_subject_snapshots(bundle)
    }


def _traces(bundle) -> dict[SubjectKey, object]:
    return {
        _subject_key(snapshot): snapshot.trace.model_dump(mode="json")
        for snapshot in derive_subject_snapshots(bundle)
    }


def _fingerprint_changes(
    left,
    right,
) -> tuple[frozenset[SubjectKey], frozenset[SubjectKey]]:
    before = _fingerprints(left)
    after = _fingerprints(right)
    keys = set(before) | set(after)
    semantic = frozenset(
        key
        for key in keys
        if before.get(key, (None, None))[0]
        != after.get(key, (None, None))[0]
    )
    observed = frozenset(
        key
        for key in keys
        if before.get(key, (None, None))[1]
        != after.get(key, (None, None))[1]
    )
    return semantic, observed


def _capture_only(bundle):
    capture_context = bundle.decisions.capture_context.model_copy(
        update={"captured_at": "2026-07-19T12:00:01Z"}
    )
    provisional = bundle.decisions.model_copy(
        update={"capture_context": capture_context, "decisions": ()}
    )
    decisions = tuple(
        sorted(
            (
                decision.model_copy(
                    update={"id": derive_decision_id(decision, provisional)}
                )
                for decision in bundle.decisions.decisions
            ),
            key=lambda decision: decision.candidate.candidate_id,
        )
    )
    return build_onboarding_bundle(
        bundle.inventory,
        bundle.discovery,
        provisional.model_copy(update={"decisions": decisions}),
    )


def _semantic_change(bundle):
    changed_decisions = []
    for decision in bundle.decisions.decisions:
        if not isinstance(decision, EditedDecision):
            changed_decisions.append(decision)
            continue
        replacement = _proposal("render-receipt")
        changed_entities = []
        for entity in replacement.entities:
            if entity.kind.value not in {
                "proposed_action",
                "proposed_use_case",
            }:
                changed_entities.append(entity)
                continue
            output = entity.output_ports[0].model_copy(
                update={"value_kind": ValueKind.STRING}
            )
            changed_entities.append(
                entity.model_copy(update={"output_ports": (output,)})
            )
        replacement = replacement.model_copy(
            update={"entities": tuple(changed_entities)}
        )
        changed_decisions.append(
            decision.model_copy(
                update={
                    "replacement": replacement,
                    "replacement_digest": derive_candidate_semantic_digest(
                        replacement
                    ),
                }
            )
        )
    provisional = bundle.decisions.model_copy(
        update={"decisions": tuple(changed_decisions)}
    )
    decisions = tuple(
        sorted(
            (
                decision.model_copy(
                    update={"id": derive_decision_id(decision, provisional)}
                )
                for decision in changed_decisions
            ),
            key=lambda decision: decision.candidate.candidate_id,
        )
    )
    return build_onboarding_bundle(
        bundle.inventory,
        bundle.discovery,
        provisional.model_copy(update={"decisions": decisions}),
    )


def _candidate_confidence_change(bundle, suffix: str):
    candidates = []
    for candidate in bundle.discovery.candidates:
        if not candidate.proposal.root.target_id.endswith(suffix):
            candidates.append(candidate)
            continue
        changed = candidate.model_copy(
            update={
                "confidence": candidate.confidence.model_copy(
                    update={"value": "0.81"}
                )
            }
        )
        candidates.append(
            changed.model_copy(
                update={
                    "id": derive_discovery_candidate_id(
                        changed,
                        bundle.discovery,
                    )
                }
            )
        )
    discovery = bundle.discovery.model_copy(
        update={
            "candidates": tuple(
                sorted(candidates, key=lambda candidate: candidate.id)
            )
        }
    )
    return build_onboarding_bundle(
        bundle.inventory,
        discovery,
        _decisions(discovery),
    )


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def _replace_ref(
    reference: InventoryRecordRef,
    id_mapping: dict[str, str],
) -> InventoryRecordRef:
    replacement = id_mapping.get(reference.target_id)
    if replacement is None:
        return reference
    return reference.model_copy(update={"target_id": replacement})


def _inventory_with_records(inventory, records) -> InventorySnapshot:
    ordered = tuple(sorted(records, key=lambda record: (record.kind, record.id)))
    payload = inventory.model_dump(mode="json")
    payload["records"] = [
        record.model_dump(mode="json") for record in ordered
    ]
    payload["source_revision"] = derive_inventory_source_revision(
        ordered
    ).model_dump(mode="json")
    return InventorySnapshot.model_validate_json(
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _rebind_inventory(bundle, inventory, id_mapping: dict[str, str]):
    binding = InventoryBinding(
        kind="inventory_binding",
        schema_uri=inventory.schema_uri,
        inventory_version=inventory.inventory_version,
        subject_uri=inventory.subject_uri,
        source_revision=inventory.source_revision,
        canonical_digest=_digest(canonical_inventory_json(inventory)),
    )
    coverage = bundle.discovery.coverage.model_copy(
        update={
            "eligible_subjects": tuple(
                _replace_ref(reference, id_mapping)
                for reference in bundle.discovery.coverage.eligible_subjects
            ),
            "uncovered_subjects": tuple(
                _replace_ref(reference, id_mapping)
                for reference in bundle.discovery.coverage.uncovered_subjects
            ),
        }
    )
    candidates = tuple(
        candidate.model_copy(
            update={
                "subject": _replace_ref(candidate.subject, id_mapping),
                "evidence": tuple(
                    _replace_ref(reference, id_mapping)
                    for reference in candidate.evidence
                ),
            }
        )
        for candidate in bundle.discovery.candidates
    )
    diagnostics = tuple(
        diagnostic.model_copy(
            update={
                "evidence": (
                    None
                    if diagnostic.evidence is None
                    else _replace_ref(diagnostic.evidence, id_mapping)
                )
            }
        )
        for diagnostic in bundle.discovery.diagnostics
    )
    provisional = bundle.discovery.model_copy(
        update={
            "inventory_binding": binding,
            "coverage": coverage,
            "candidates": candidates,
            "diagnostics": diagnostics,
        }
    )
    candidates = tuple(
        sorted(
            (
                candidate.model_copy(
                    update={
                        "id": derive_discovery_candidate_id(
                            candidate,
                            provisional,
                        )
                    }
                )
                for candidate in candidates
            ),
            key=lambda candidate: candidate.id,
        )
    )
    discovery = provisional.model_copy(update={"candidates": candidates})
    return build_onboarding_bundle(
        inventory,
        discovery,
        _decisions(discovery),
    )


def _unrelated_inventory_confidence_change(bundle):
    records = []
    id_mapping: dict[str, str] = {}
    for record in bundle.inventory.records:
        if isinstance(record, RepositoryEntryFact) and record.path == "src":
            changed = record.model_copy(
                update={
                    "confidence": record.confidence.model_copy(
                        update={"value": "0.75"}
                    )
                }
            )
            changed = changed.model_copy(
                update={"id": derive_inventory_record_id(changed)}
            )
            records.append(changed)
            id_mapping[record.id] = changed.id
        else:
            records.append(record)
    assert id_mapping
    inventory = _inventory_with_records(bundle.inventory, records)
    return _rebind_inventory(bundle, inventory, id_mapping)


def _path_rename(bundle):
    old_provenance = next(
        record
        for record in bundle.inventory.records
        if isinstance(record, InventoryProvenance)
        and record.source_path == "src/service.py"
    )
    old_entry = next(
        record
        for record in bundle.inventory.records
        if isinstance(record, RepositoryEntryFact)
        and record.path == "src/service.py"
    )
    old_interface = next(
        record
        for record in bundle.inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    new_provenance = old_provenance.model_copy(
        update={"source_path": "src/renamed_service.py"}
    )
    new_provenance = new_provenance.model_copy(
        update={"id": derive_inventory_record_id(new_provenance)}
    )
    new_entry = old_entry.model_copy(
        update={
            "path": "src/renamed_service.py",
            "provenance": old_entry.provenance.model_copy(
                update={"target_id": new_provenance.id}
            ),
        }
    )
    new_entry = new_entry.model_copy(
        update={"id": derive_inventory_record_id(new_entry)}
    )
    new_interface = old_interface.model_copy(
        update={
            "provenance": old_interface.provenance.model_copy(
                update={"target_id": new_provenance.id}
            ),
            "entry": old_interface.entry.model_copy(
                update={"target_id": new_entry.id}
            ),
        }
    )
    new_interface = new_interface.model_copy(
        update={"id": derive_inventory_record_id(new_interface)}
    )
    replacements = {
        old_provenance.id: new_provenance,
        old_entry.id: new_entry,
        old_interface.id: new_interface,
    }
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


def _variant(bundle, name: str):
    if name == "capture_only":
        return _capture_only(bundle)
    if name == "semantic_edit":
        return _semantic_change(bundle)
    if name == "accepted_confidence":
        return _candidate_confidence_change(bundle, "quote-order")
    if name == "rejected_confidence":
        return _candidate_confidence_change(bundle, "normalize-coupon")
    if name == "unrelated_inventory_fact":
        return _unrelated_inventory_confidence_change(bundle)
    if name == "path_rename":
        return _path_rename(bundle)
    raise AssertionError(f"unknown fixture variant: {name}")


def _capture_context() -> CaptureContext:
    return CaptureContext(
        kind="capture_context",
        captured_at="2026-07-19T13:00:00Z",
        environment=Digest(
            kind="digest",
            algorithm="sha-256",
            value="c" * 64,
        ),
    )


def _assessment(policy, bundle, target: SubjectKey):
    return build_ratchet_assessment(
        policy,
        bundle,
        producer=Producer(
            kind="producer",
            name="org.ucf.fixture-assessor",
            version="1.0.0",
        ),
        procedure_uri="urn:ucf:ratchet-assessment:fixture:1.0.0",
        capture_context=_capture_context(),
        violations=(
            ViolationInput(
                kind="ratchet_violation_input",
                rule_id=policy.rules[0].id,
                subject=BehaviorSubjectKey(
                    kind="behavior_subject_key",
                    subject_uri=target[0],
                    target_kind=EntityKind(target[1]),
                    target_id=target[2],
                ),
                slot="required-check",
                message="No current tested claim is attached.",
            ),
        ),
    )


@pytest.mark.parametrize("variant_name", _VARIANTS)
def test_touch_projection_changes_only_the_intended_subject(
    variant_name: str,
) -> None:
    base = _bundle()
    changed = _variant(base, variant_name)

    assert canonical_onboarding_digest(changed) != (
        canonical_onboarding_digest(base)
    )
    assert set(_fingerprints(base)) == _SUBJECTS
    assert set(_fingerprints(changed)) == _SUBJECTS
    assert _fingerprint_changes(base, changed) == (
        _EXPECTED_FINGERPRINT_CHANGES[variant_name]
    )
    assert {
        key
        for key in _SUBJECTS
        if _traces(base)[key] != _traces(changed)[key]
    } == _SUBJECTS


@pytest.mark.parametrize("variant_name", _VARIANTS)
def test_evaluator_uses_fingerprints_instead_of_exact_trace_drift(
    variant_name: str,
) -> None:
    base = _bundle()
    changed = _variant(base, variant_name)
    policy = _policy()
    expected_semantic, expected_observed = (
        _EXPECTED_FINGERPRINT_CHANGES[variant_name]
    )
    target = (
        _RECEIPT if variant_name == "semantic_edit" else _QUOTE
    )
    baseline = establish_ratchet_baseline(
        policy,
        base,
        _assessment(policy, base, target),
    )
    current = _assessment(policy, changed, target)

    report = evaluate_ratchet(policy, baseline, changed, current)

    id_to_key = {
        subject.id: _subject_key(subject) for subject in current.subjects
    }
    expected_changes = {
        key: (
            SubjectChangeKind.SEMANTIC_CHANGED
            if key in expected_semantic
            else SubjectChangeKind.OBSERVED_CHANGED
            if key in expected_observed
            else SubjectChangeKind.UNCHANGED
        )
        for key in _SUBJECTS
    }
    assert {
        id_to_key[change.subject.target_id]: change.change
        for change in report.subject_changes
    } == expected_changes
    touched = bool(expected_semantic or expected_observed)
    assert report.classifications[0].classification is (
        ViolationClassificationKind.TOUCHED_LEGACY
        if touched
        else ViolationClassificationKind.UNCHANGED_LEGACY
    )
    assert report.outcome is (
        EvaluationOutcome.FAIL if touched else EvaluationOutcome.PASS
    )
