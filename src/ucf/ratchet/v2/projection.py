from __future__ import annotations

import json

from ucf.inventory import (
    BuildManifestFact,
    FactKind,
    InventoryProvenance,
    PublicInterfaceFact,
    RepositoryEntryFact,
)
from ucf.ir.models import Digest, EntityKind
from ucf.onboarding import (
    AcceptedDecision,
    DispositionKind,
    EditedDecision,
    OnboardingBundle,
    RejectedDecision,
    UncertainDecision,
    validate_onboarding_bundle,
)
from ucf.ratchet.v2.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.v2.identity import (
    derive_behavior_subject_id,
    derive_coverage_debt_id,
    derive_coverage_qualification_id,
    derive_coverage_subject_id,
    derive_projection_digest,
)
from ucf.ratchet.v2.models import (
    BEHAVIOR_OBSERVED_FINGERPRINT_ALGORITHM_URI,
    BEHAVIOR_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
    COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI,
    COVERAGE_QUALIFICATION_ALGORITHM_URI,
    COVERAGE_RECONCILIATION_ALGORITHM_URI,
    COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
    COVERAGE_SUBJECT_KEY_ALGORITHM_URI,
    BehaviorObservedFingerprint,
    BehaviorSemanticFingerprint,
    BehaviorSubjectKey,
    BehaviorSubjectSnapshot,
    BehaviorSubjectTrace,
    CoverageAssessmentLedger,
    CoverageDebtKey,
    CoverageDebtKind,
    CoverageDebtSnapshot,
    CoverageObservedFingerprint,
    CoverageQualification,
    CoverageReconciliationSnapshot,
    CoverageReconciliationTrace,
    CoverageSemanticFingerprint,
    CoverageSubjectGroup,
    CoverageSubjectKey,
    CoverageSubjectRef,
    CoverageSubjectState,
    CoverageSubjectTrace,
)
from ucf.ratchet.v2.references import onboarding_bundle_ref


def derive_behavior_subject_snapshots(
    bundle: OnboardingBundle,
) -> tuple[BehaviorSubjectSnapshot, ...]:
    validate_onboarding_bundle(bundle)
    bundle_reference = onboarding_bundle_ref(bundle)
    behavior_entities = {entity.id: entity for entity in bundle.behavior.entities}
    inventory_records = {record.id: record for record in bundle.inventory.records}
    candidates = {candidate.id: candidate for candidate in bundle.discovery.candidates}
    candidate_positions = {
        candidate.id: position
        for position, candidate in enumerate(bundle.discovery.candidates)
    }
    snapshots = []
    for materialization in bundle.baseline.materializations:
        candidate = candidates.get(materialization.candidate.candidate_id)
        if candidate is None:
            _broken("materialization candidate does not exist", "$.baseline")
        key = BehaviorSubjectKey(
            kind="behavior_subject_key",
            subject_uri=bundle.inventory.subject_uri,
            target_kind=materialization.root.target_kind,
            target_id=materialization.root.target_id,
        )
        snapshot = BehaviorSubjectSnapshot(
            kind="behavior_subject_snapshot",
            id=derive_behavior_subject_id(key),
            key=key,
            semantic=BehaviorSemanticFingerprint(
                kind="behavior_semantic_fingerprint",
                algorithm_uri=BEHAVIOR_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
                digest=_digest(
                    _behavior_semantic_projection(
                        materialization.entities,
                        behavior_entities,
                    )
                ),
            ),
            observed=BehaviorObservedFingerprint(
                kind="behavior_observed_fingerprint",
                algorithm_uri=BEHAVIOR_OBSERVED_FINGERPRINT_ALGORITHM_URI,
                digest=_digest(
                    _candidate_observed_projection(
                        candidate,
                        inventory_records,
                        location=(
                            "$.discovery.candidates"
                            f"[{candidate_positions[candidate.id]}]"
                        ),
                    )
                ),
            ),
            trace=BehaviorSubjectTrace(
                kind="ratchet_behavior_subject_trace",
                onboarding_bundle=bundle_reference,
                behavior=materialization.root,
                inventory_source_revision=bundle.inventory.source_revision,
                candidate=materialization.candidate,
                decision_id=materialization.decision_id,
            ),
        )
        snapshots.append(snapshot)
    return tuple(sorted(snapshots, key=_behavior_subject_key))


def derive_coverage_ledger(bundle: OnboardingBundle) -> CoverageAssessmentLedger:
    validate_onboarding_bundle(bundle)
    records = {record.id: record for record in bundle.inventory.records}
    candidates_by_subject: dict[str, list] = {}
    for candidate in bundle.discovery.candidates:
        candidates_by_subject.setdefault(candidate.subject.target_id, []).append(
            candidate
        )
    decisions = {
        decision.candidate.candidate_id: decision
        for decision in bundle.decisions.decisions
    }
    candidate_positions = {
        candidate.id: position
        for position, candidate in enumerate(bundle.discovery.candidates)
    }
    bundle_reference = onboarding_bundle_ref(bundle)
    groups = []
    stable_keys = set()
    for reference in bundle.discovery.coverage.eligible_subjects:
        subject = records.get(reference.target_id)
        if not isinstance(subject, PublicInterfaceFact):
            raise RatchetValidationError(
                RatchetErrorCode.WRONG_TARGET_KIND,
                "coverage subject is not a public interface",
                location="$.discovery.coverage.eligible_subjects",
            )
        key = CoverageSubjectKey(
            kind="coverage_subject_key",
            subject_uri=bundle.inventory.subject_uri,
            target_kind="public_interface",
            interface_kind_uri=subject.interface_kind_uri,
            container=subject.container,
            name=subject.name,
        )
        key_identity = _canonical_value(key.model_dump(mode="json"))
        if key_identity in stable_keys:
            raise RatchetValidationError(
                RatchetErrorCode.AMBIGUOUS_COVERAGE_IDENTITY,
                "public interfaces have the same path-independent key",
                location="$.coverage.groups",
            )
        stable_keys.add(key_identity)
        reconciliations = _derive_reconciliations(
            subject,
            candidates_by_subject.get(subject.id, []),
            decisions,
            records,
            candidate_positions,
        )
        state = (
            CoverageSubjectState.RECONCILED
            if reconciliations
            else CoverageSubjectState.UNCOVERED
        )
        trace = _coverage_subject_trace(
            bundle,
            bundle_reference,
            reference,
        )
        group = CoverageSubjectGroup(
            kind="coverage_subject_group",
            id=derive_coverage_subject_id(key),
            key=key,
            state=state,
            semantic=_coverage_semantic_fingerprint(
                {
                    "state": state.value,
                    "reconciliations": [
                        item.semantic.digest.model_dump(mode="json")
                        for item in reconciliations
                    ],
                }
            ),
            observed=_coverage_observed_fingerprint(
                {
                    "interface": _normalize_public_interface(
                        subject,
                        records,
                        location=(
                            "$.discovery.coverage.eligible_subjects"
                        ),
                    ),
                    "reconciliations": [
                        item.observed.digest.model_dump(mode="json")
                        for item in reconciliations
                    ],
                }
            ),
            reconciliations=reconciliations,
            trace=trace,
        )
        groups.append(group)
    groups = tuple(sorted(groups, key=_coverage_group_key))
    debts = _derive_coverage_debts(groups)
    return CoverageAssessmentLedger(
        kind="ratchet_coverage_assessment",
        qualification=_derive_qualification(bundle, records),
        inventory_coverage=_public_interface_coverage(bundle),
        discovery_coverage=bundle.discovery.coverage.status,
        groups=groups,
        debts=debts,
    )


def _derive_reconciliations(
    subject: PublicInterfaceFact,
    candidates,
    decisions,
    records,
    candidate_positions,
) -> tuple[CoverageReconciliationSnapshot, ...]:
    reconciliations = []
    semantic_coordinates = set()
    for candidate in candidates:
        decision = decisions.get(candidate.id)
        if decision is None:
            _broken("candidate has no exact decision", "$.decisions")
        semantic_coordinate = candidate.semantic_digest.value
        if semantic_coordinate in semantic_coordinates:
            raise RatchetValidationError(
                RatchetErrorCode.AMBIGUOUS_COVERAGE_IDENTITY,
                "one interface has duplicate candidate semantic identities",
                location="$.coverage.groups.reconciliations",
            )
        semantic_coordinates.add(semantic_coordinate)
        disposition = _disposition(decision)
        replacement = (
            decision.replacement_digest
            if isinstance(decision, EditedDecision)
            else None
        )
        reconciliations.append(
            CoverageReconciliationSnapshot(
                kind="coverage_reconciliation_snapshot",
                disposition=disposition,
                candidate_semantic_digest=candidate.semantic_digest,
                replacement_semantic_digest=replacement,
                semantic=_coverage_semantic_fingerprint(
                    {
                        "candidate_semantic_digest": (
                            candidate.semantic_digest.model_dump(mode="json")
                        ),
                        "disposition": disposition.value,
                        "replacement_semantic_digest": (
                            None
                            if replacement is None
                            else replacement.model_dump(mode="json")
                        ),
                    }
                ),
                observed=_coverage_observed_fingerprint(
                    {
                        "interface": _normalize_public_interface(
                            subject,
                            records,
                            location=(
                                "$.discovery.candidates"
                                f"[{candidate_positions[candidate.id]}]"
                                ".subject"
                            ),
                        ),
                        "candidate": _candidate_observed_projection(
                            candidate,
                            records,
                            location=(
                                "$.discovery.candidates"
                                f"[{candidate_positions[candidate.id]}]"
                            ),
                        ),
                    }
                ),
                trace=CoverageReconciliationTrace(
                    kind="coverage_reconciliation_trace",
                    candidate=decision.candidate,
                    decision_id=decision.id,
                ),
            )
        )
    return tuple(
        sorted(
            reconciliations,
            key=lambda item: (
                item.candidate_semantic_digest.value,
                item.disposition.value,
                ""
                if item.replacement_semantic_digest is None
                else item.replacement_semantic_digest.value,
            ),
        )
    )


def _derive_coverage_debts(
    groups: tuple[CoverageSubjectGroup, ...],
) -> tuple[CoverageDebtSnapshot, ...]:
    debts = []
    for group in groups:
        subject_ref = CoverageSubjectRef(
            kind="coverage_subject_ref",
            target_id=group.id,
        )
        if group.state is CoverageSubjectState.UNCOVERED:
            key = CoverageDebtKey(
                kind="coverage_debt_key",
                debt_kind=CoverageDebtKind.UNCOVERED,
                subject=subject_ref,
                candidate_semantic_digest=None,
            )
            debts.append(
                CoverageDebtSnapshot(
                    kind="coverage_debt_snapshot",
                    id=derive_coverage_debt_id(key),
                    key=key,
                    semantic=group.semantic,
                    observed=group.observed,
                    subject_trace=group.trace,
                    reconciliation_trace=None,
                )
            )
            continue
        for reconciliation in group.reconciliations:
            if reconciliation.disposition is not DispositionKind.UNCERTAIN:
                continue
            key = CoverageDebtKey(
                kind="coverage_debt_key",
                debt_kind=CoverageDebtKind.UNCERTAIN,
                subject=subject_ref,
                candidate_semantic_digest=(
                    reconciliation.candidate_semantic_digest
                ),
            )
            debts.append(
                CoverageDebtSnapshot(
                    kind="coverage_debt_snapshot",
                    id=derive_coverage_debt_id(key),
                    key=key,
                    semantic=reconciliation.semantic,
                    observed=reconciliation.observed,
                    subject_trace=group.trace,
                    reconciliation_trace=reconciliation.trace,
                )
            )
    return tuple(sorted(debts, key=lambda item: item.id))


def _disposition(decision):
    if isinstance(decision, AcceptedDecision):
        return DispositionKind.ACCEPTED
    if isinstance(decision, EditedDecision):
        return DispositionKind.EDITED
    if isinstance(decision, RejectedDecision):
        return DispositionKind.REJECTED
    if isinstance(decision, UncertainDecision):
        return DispositionKind.UNCERTAIN
    raise TypeError("unsupported onboarding decision")


def _derive_qualification(bundle, records) -> CoverageQualification:
    procedures = set()
    for reference in bundle.discovery.coverage.eligible_subjects:
        subject = records[reference.target_id]
        if not isinstance(subject, PublicInterfaceFact):
            continue
        provenance = records.get(subject.provenance.target_id)
        if isinstance(provenance, InventoryProvenance):
            procedures.add(provenance.procedure_uri)
    for candidate in bundle.discovery.candidates:
        for reference in candidate.evidence:
            record = records[reference.target_id]
            if not isinstance(record, BuildManifestFact):
                continue
            provenance = records.get(record.provenance.target_id)
            if isinstance(provenance, InventoryProvenance):
                procedures.add(provenance.procedure_uri)
    provisional = CoverageQualification(
        kind="coverage_qualification",
        id=f"domain.{'0' * 64}",
        algorithm_uri=COVERAGE_QUALIFICATION_ALGORITHM_URI,
        subject_uri=bundle.inventory.subject_uri,
        inventory_schema_uri=bundle.inventory.schema_uri,
        inventory_version=bundle.inventory.inventory_version,
        inventory_producer=bundle.inventory.producer,
        inventory_capability=bundle.inventory.capability,
        inventory_path_identity=bundle.inventory.path_identity,
        inventory_ignore_policy_digest=_digest(
            bundle.inventory.applied_policy.model_dump(mode="json")
        ),
        inventory_procedure_uris=tuple(sorted(procedures)),
        discovery_schema_uri=bundle.discovery.schema_uri,
        discovery_version=bundle.discovery.onboarding_version,
        discovery_producer=bundle.discovery.producer,
        discovery_capability=bundle.discovery.capability,
        discovery_procedure_uri=bundle.discovery.procedure_uri,
        subject_key_algorithm_uri=COVERAGE_SUBJECT_KEY_ALGORITHM_URI,
        reconciliation_algorithm_uri=COVERAGE_RECONCILIATION_ALGORITHM_URI,
        semantic_fingerprint_algorithm_uri=(
            COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI
        ),
        observed_fingerprint_algorithm_uri=(
            COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI
        ),
    )
    return provisional.model_copy(
        update={"id": derive_coverage_qualification_id(provisional)}
    )


def _public_interface_coverage(bundle) -> str:
    return next(
        item.status
        for item in bundle.inventory.coverage
        if item.fact_kind is FactKind.PUBLIC_INTERFACE
    )


def _coverage_subject_trace(bundle, bundle_reference, reference):
    return CoverageSubjectTrace(
        kind="coverage_subject_trace",
        onboarding_bundle=bundle_reference,
        inventory_source_revision=bundle.inventory.source_revision,
        interface=reference,
    )


def _behavior_semantic_projection(references, entities) -> object:
    projected = []
    for reference in references:
        entity = entities.get(reference.target_id)
        if entity is None:
            _broken("materialized behavior entity does not exist", "$.behavior")
        if EntityKind(entity.kind) is not reference.target_kind:
            raise RatchetValidationError(
                RatchetErrorCode.WRONG_TARGET_KIND,
                "materialized behavior reference has the wrong target kind",
                location="$.baseline.materializations",
            )
        if EntityKind(entity.kind) is EntityKind.PROVENANCE:
            continue
        projected.append(entity.model_dump(mode="json", exclude={"provenance"}))
    return {
        "entities": sorted(
            projected,
            key=lambda value: (value["kind"], value["id"]),
        )
    }


def _candidate_observed_projection(candidate, records, *, location: str) -> object:
    evidence = [
        _normalize_candidate_evidence(
            _resolve_record(
                ref.target_id,
                records,
                location=f"{location}.evidence[{position}]",
            ),
            records,
            location=f"{location}.evidence[{position}]",
        )
        for position, ref in enumerate(candidate.evidence)
    ]
    return {
        "confidence": candidate.confidence.model_dump(mode="json"),
        "evidence": sorted(evidence, key=_canonical_value),
        "subject": _normalize_public_interface(
            _resolve_record(
                candidate.subject.target_id,
                records,
                location=f"{location}.subject",
            ),
            records,
            location=f"{location}.subject",
        ),
    }


def _normalize_candidate_evidence(record, records, *, location: str) -> object:
    if isinstance(record, PublicInterfaceFact):
        return _normalize_public_interface(record, records, location=location)
    if isinstance(record, BuildManifestFact):
        entry = _resolve_record(
            record.entry.target_id,
            records,
            location=f"{location}.entry",
        )
        if not isinstance(entry, RepositoryEntryFact):
            raise RatchetValidationError(
                RatchetErrorCode.WRONG_TARGET_KIND,
                "build manifest entry has the wrong target kind",
                location=f"{location}.entry",
            )
        return {
            "kind": record.kind,
            "dialect_uri": record.dialect_uri,
            "confidence": record.confidence.model_dump(mode="json"),
            "entry": {
                "kind": entry.kind,
                "entry_kind": entry.entry_kind,
                "content_digest": (
                    None
                    if entry.content_digest is None
                    else entry.content_digest.model_dump(mode="json")
                ),
                "symlink_target_digest": (
                    None
                    if entry.symlink_target_digest is None
                    else entry.symlink_target_digest.model_dump(mode="json")
                ),
                "confidence": entry.confidence.model_dump(mode="json"),
            },
        }
    raise RatchetValidationError(
        RatchetErrorCode.UNSUPPORTED_EVIDENCE_KIND,
        (
            f"inventory record kind {record.kind!r} is unsupported by "
            "observed-fingerprint profile 2.0.0"
        ),
        location=location,
    )


def _normalize_public_interface(record, records, *, location: str) -> object:
    if not isinstance(record, PublicInterfaceFact):
        raise RatchetValidationError(
            RatchetErrorCode.WRONG_TARGET_KIND,
            "candidate subject is not a public interface",
            location=location,
        )
    entry_location = f"{location}.entry"
    entry = _resolve_record(
        record.entry.target_id,
        records,
        location=entry_location,
    )
    if not isinstance(entry, RepositoryEntryFact):
        raise RatchetValidationError(
            RatchetErrorCode.WRONG_TARGET_KIND,
            "public interface entry has the wrong target kind",
            location=entry_location,
        )
    return {
        "kind": record.kind,
        "interface_kind_uri": record.interface_kind_uri,
        "container": record.container,
        "name": record.name,
        "declaration_digest": record.declaration_digest.model_dump(
            mode="json"
        ),
        "entry_content_digest": (
            None
            if entry.content_digest is None
            else entry.content_digest.model_dump(mode="json")
        ),
        "confidence": record.confidence.model_dump(mode="json"),
    }


def _resolve_record(identifier: str, records, *, location: str):
    record = records.get(identifier)
    if record is None:
        _broken("inventory evidence does not exist", location)
    return record


def _coverage_semantic_fingerprint(value: object) -> CoverageSemanticFingerprint:
    return CoverageSemanticFingerprint(
        kind="coverage_semantic_fingerprint",
        algorithm_uri=COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
        digest=_digest(value),
    )


def _coverage_observed_fingerprint(value: object) -> CoverageObservedFingerprint:
    return CoverageObservedFingerprint(
        kind="coverage_observed_fingerprint",
        algorithm_uri=COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI,
        digest=_digest(value),
    )


def _digest(value: object) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=derive_projection_digest(value),
    )


def _canonical_value(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _behavior_subject_key(snapshot: BehaviorSubjectSnapshot):
    return (
        snapshot.key.subject_uri,
        snapshot.key.target_kind.value,
        snapshot.key.target_id,
    )


def _coverage_group_key(group: CoverageSubjectGroup):
    return (
        group.key.subject_uri,
        group.key.target_kind,
        group.key.interface_kind_uri,
        group.key.container or "",
        group.key.name,
    )


def _broken(message: str, location: str):
    raise RatchetValidationError(
        RatchetErrorCode.BROKEN_REFERENCE,
        message,
        location=location,
    )
