from __future__ import annotations

from ucf.inventory.models import (
    InventoryDiagnostic,
    InventoryFact,
    InventoryProvenance,
    RepositoryEntryFact,
)
from ucf.ir.models import Digest, EntityKind
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    OnboardingBundle,
    canonical_onboarding_digest,
    validate_onboarding_bundle,
)
from ucf.ratchet.errors import RatchetErrorCode, RatchetValidationError
from ucf.ratchet.identity import (
    derive_behavior_subject_id,
    derive_projection_digest,
)
from ucf.ratchet.models import (
    OBSERVED_FINGERPRINT_ALGORITHM_URI,
    SEMANTIC_FINGERPRINT_ALGORITHM_URI,
    BehaviorSubjectKey,
    BehaviorSubjectSnapshot,
    ObservedFingerprint,
    OnboardingBundleRef,
    SemanticFingerprint,
    SubjectTrace,
)


def derive_subject_snapshots(
    bundle: OnboardingBundle,
) -> tuple[BehaviorSubjectSnapshot, ...]:
    validate_onboarding_bundle(bundle)
    bundle_reference = OnboardingBundleRef(
        kind="onboarding_bundle_ref",
        schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
        schema_version=ONBOARDING_VERSION,
        canonical_digest=canonical_onboarding_digest(bundle),
    )
    behavior_entities = {entity.id: entity for entity in bundle.behavior.entities}
    inventory_records = {
        record.id: record for record in bundle.inventory.records
    }
    candidates = {
        candidate.id: candidate for candidate in bundle.discovery.candidates
    }
    snapshots = []
    for materialization in bundle.baseline.materializations:
        candidate = candidates.get(materialization.candidate.candidate_id)
        if candidate is None:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "materialization candidate does not exist",
                location="$.baseline.materializations",
            )
        key = BehaviorSubjectKey(
            kind="behavior_subject_key",
            subject_uri=bundle.inventory.subject_uri,
            target_kind=materialization.root.target_kind,
            target_id=materialization.root.target_id,
        )
        semantic_projection = _semantic_projection(
            materialization.entities,
            behavior_entities,
        )
        observed_projection = _observed_projection(
            candidate,
            inventory_records,
        )
        snapshots.append(
            BehaviorSubjectSnapshot(
                kind="behavior_subject_snapshot",
                id=derive_behavior_subject_id(key),
                key=key,
                semantic=SemanticFingerprint(
                    kind="semantic_fingerprint",
                    algorithm_uri=SEMANTIC_FINGERPRINT_ALGORITHM_URI,
                    digest=_digest(semantic_projection),
                ),
                observed=ObservedFingerprint(
                    kind="observed_fingerprint",
                    algorithm_uri=OBSERVED_FINGERPRINT_ALGORITHM_URI,
                    digest=_digest(observed_projection),
                ),
                trace=SubjectTrace(
                    kind="ratchet_subject_trace",
                    onboarding_bundle=bundle_reference,
                    behavior=materialization.root,
                    inventory_source_revision=bundle.inventory.source_revision,
                    candidate=materialization.candidate,
                    decision_id=materialization.decision_id,
                ),
            )
        )
    return tuple(sorted(snapshots, key=_subject_key))


def _semantic_projection(references, entities) -> object:
    projected = []
    for reference in references:
        entity = entities.get(reference.target_id)
        if entity is None:
            raise RatchetValidationError(
                RatchetErrorCode.BROKEN_REFERENCE,
                "materialized behavior entity does not exist",
                location="$.behavior.entities",
            )
        if EntityKind(entity.kind) is not reference.target_kind:
            raise RatchetValidationError(
                RatchetErrorCode.WRONG_TARGET_KIND,
                "materialized behavior reference has the wrong target kind",
                location="$.baseline.materializations",
            )
        if EntityKind(entity.kind) is EntityKind.PROVENANCE:
            continue
        projected.append(
            entity.model_dump(mode="json", exclude={"provenance"})
        )
    return {
        "entities": sorted(
            projected,
            key=lambda value: (value["kind"], value["id"]),
        )
    }


def _observed_projection(candidate, records) -> object:
    return {
        "confidence": candidate.confidence.model_dump(mode="json"),
        "evidence": [
            _normalize_inventory_record(
                _resolve_inventory_record(reference.target_id, records),
                records,
            )
            for reference in candidate.evidence
        ],
        "subject": _normalize_inventory_record(
            _resolve_inventory_record(candidate.subject.target_id, records),
            records,
        ),
    }


def _normalize_inventory_record(record, records) -> object:
    if isinstance(record, InventoryProvenance):
        return {
            "kind": record.kind,
            "content_digest": (
                None
                if record.content_digest is None
                else record.content_digest.model_dump(mode="json")
            ),
        }
    if isinstance(record, RepositoryEntryFact):
        payload = record.model_dump(
            mode="json",
            exclude={"id", "level", "path", "provenance"},
        )
        payload["provenance_content"] = _normalized_provenance(
            record.provenance.target_id,
            records,
        )
        return payload
    if isinstance(record, InventoryFact):
        payload = record.model_dump(
            mode="json",
            exclude={"entry", "id", "level", "provenance"},
        )
        entry = getattr(record, "entry", None)
        if entry is not None:
            payload["entry"] = _normalize_inventory_record(
                _resolve_inventory_record(entry.target_id, records),
                records,
            )
        payload["provenance_content"] = _normalized_provenance(
            record.provenance.target_id,
            records,
        )
        return payload
    if isinstance(record, InventoryDiagnostic):
        payload = record.model_dump(
            mode="json",
            exclude={"evidence", "id", "provenance"},
        )
        if record.evidence is not None:
            payload["evidence"] = _normalize_inventory_record(
                _resolve_inventory_record(record.evidence.target_id, records),
                records,
            )
        if record.provenance is not None:
            payload["provenance_content"] = _normalized_provenance(
                record.provenance.target_id,
                records,
            )
        return payload
    raise RatchetValidationError(
        RatchetErrorCode.WRONG_TARGET_KIND,
        "candidate evidence has an unsupported inventory record kind",
        location="$.inventory.records",
    )


def _normalized_provenance(identifier: str, records) -> object:
    provenance = _resolve_inventory_record(identifier, records)
    if not isinstance(provenance, InventoryProvenance):
        raise RatchetValidationError(
            RatchetErrorCode.WRONG_TARGET_KIND,
            "inventory fact provenance has the wrong target kind",
            location="$.inventory.records",
        )
    return _normalize_inventory_record(provenance, records)


def _resolve_inventory_record(identifier: str, records):
    record = records.get(identifier)
    if record is None:
        raise RatchetValidationError(
            RatchetErrorCode.BROKEN_REFERENCE,
            "candidate evidence does not exist",
            location="$.inventory.records",
        )
    return record


def _digest(value: object) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=derive_projection_digest(value),
    )


def _subject_key(snapshot: BehaviorSubjectSnapshot) -> tuple[str, str, str]:
    return (
        snapshot.key.subject_uri,
        snapshot.key.target_kind.value,
        snapshot.key.target_id,
    )
