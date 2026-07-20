from __future__ import annotations

import hashlib
from collections.abc import Sequence

from ucf.ir.codec import canonical_ir_json
from ucf.ir.errors import IRErrorCode, IRValidationError
from ucf.ir.models import (
    BehaviorIR,
    Effect,
    Entity,
    EntityKind,
    Provenance,
    VerificationEvidence,
)
from ucf.ir.trust_models import (
    BehaviorCandidate,
    BehaviorDocumentRef,
    BehaviorEntityRef,
    Claim,
    ClaimLevel,
    Declaration,
    DeclaredClaimBasis,
    MappedClaimBasis,
    ObservedClaimBasis,
    ObservedFact,
    RecordRef,
    SourceRecord,
    TestedClaimBasis,
    TrustIR,
    TrustMapping,
    TrustRecord,
    TrustRecordKind,
    VerifiedClaimBasis,
)
from ucf.ir.validation import validate_ir_semantics

type TrustRecordIndex = dict[str, TrustRecord]
type BehaviorEntityIndex = dict[str, Entity]


def _fail(
    code: IRErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise IRValidationError(code, message, location=location)


def _build_index(document: TrustIR) -> TrustRecordIndex:
    index: TrustRecordIndex = {}
    for position, record in enumerate(document.records):
        previous = index.get(record.id)
        if previous is not None:
            _fail(
                IRErrorCode.DUPLICATE_IDENTITY,
                (
                    f"trust record id {record.id!r} is used by both "
                    f"{previous.kind.value!r} and {record.kind.value!r}"
                ),
                location=f"$.records[{position}].id",
            )
        index[record.id] = record
    return index


def _resolve_record(
    ref: RecordRef,
    index: TrustRecordIndex,
    *,
    location: str,
    expected: set[TrustRecordKind] | None = None,
) -> TrustRecord:
    target = index.get(ref.target_id)
    if target is None:
        _fail(
            IRErrorCode.BROKEN_REFERENCE,
            f"trust record target {ref.target_id!r} does not exist",
            location=location,
        )
    if target.kind is not ref.target_kind:
        _fail(
            IRErrorCode.WRONG_TARGET_KIND,
            (
                f"reference declares {ref.target_kind.value!r}, but "
                f"{ref.target_id!r} is {target.kind.value!r}"
            ),
            location=f"{location}.target_kind",
        )
    if expected is not None and target.kind not in expected:
        allowed = ", ".join(sorted(kind.value for kind in expected))
        _fail(
            IRErrorCode.WRONG_TARGET_KIND,
            (
                f"{ref.target_id!r} has kind {target.kind.value!r}; "
                f"expected one of: {allowed}"
            ),
            location=f"{location}.target_kind",
        )
    return target


def _validate_record_refs(
    refs: Sequence[RecordRef],
    index: TrustRecordIndex,
    *,
    location: str,
    expected: set[TrustRecordKind],
) -> None:
    seen: set[tuple[TrustRecordKind, str]] = set()
    for position, ref in enumerate(refs):
        identity = (ref.target_kind, ref.target_id)
        if identity in seen:
            _fail(
                IRErrorCode.DUPLICATE_REFERENCE,
                (
                    f"reference to {ref.target_kind.value!r} "
                    f"{ref.target_id!r} is duplicated"
                ),
                location=f"{location}[{position}]",
            )
        seen.add(identity)
        _resolve_record(
            ref,
            index,
            location=f"{location}[{position}]",
            expected=expected,
        )


def _validate_behavior_ref(
    ref: BehaviorEntityRef,
    document: TrustIR,
    *,
    location: str,
) -> None:
    subject = document.subject_document
    comparisons = (
        ("document_id", ref.document_id, subject.document_id),
        ("ir_version", ref.ir_version, subject.ir_version),
        ("canonical_digest", ref.canonical_digest, subject.canonical_digest),
    )
    for field, actual, expected in comparisons:
        if actual != expected:
            _fail(
                IRErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                f"behavior reference {field} does not match subject_document",
                location=f"{location}.{field}",
            )


def _validate_trace(
    ref: RecordRef,
    index: TrustRecordIndex,
    *,
    location: str,
) -> None:
    _resolve_record(
        ref,
        index,
        location=location,
        expected={TrustRecordKind.SOURCE_RECORD},
    )


_CLAIM_BASIS_TYPES = {
    ClaimLevel.OBSERVED: ObservedClaimBasis,
    ClaimLevel.DECLARED: DeclaredClaimBasis,
    ClaimLevel.MAPPED: MappedClaimBasis,
    ClaimLevel.TESTED: TestedClaimBasis,
    ClaimLevel.VERIFIED: VerifiedClaimBasis,
}


def _validate_claim_basis(
    claim: Claim,
    index: TrustRecordIndex,
    document: TrustIR,
    *,
    location: str,
) -> None:
    expected_type = _CLAIM_BASIS_TYPES[claim.level]
    if not isinstance(claim.basis, expected_type):
        _fail(
            IRErrorCode.MISSING_CLAIM_BASIS,
            f"{claim.level.value!r} claim requires {expected_type.__name__}",
            location=f"{location}.basis",
        )

    if isinstance(claim.basis, ObservedClaimBasis):
        _resolve_record(
            claim.basis.fact,
            index,
            location=f"{location}.basis.fact",
            expected={TrustRecordKind.OBSERVED_FACT},
        )
    elif isinstance(claim.basis, DeclaredClaimBasis):
        _resolve_record(
            claim.basis.declaration,
            index,
            location=f"{location}.basis.declaration",
            expected={TrustRecordKind.DECLARATION},
        )
    elif isinstance(claim.basis, MappedClaimBasis):
        _resolve_record(
            claim.basis.mapping,
            index,
            location=f"{location}.basis.mapping",
            expected={TrustRecordKind.MAPPING},
        )
    elif isinstance(claim.basis, TestedClaimBasis):
        _resolve_record(
            claim.basis.artifact,
            index,
            location=f"{location}.basis.artifact",
            expected={TrustRecordKind.SOURCE_RECORD},
        )
        if isinstance(claim.basis.evidence, BehaviorEntityRef):
            _validate_behavior_ref(
                claim.basis.evidence,
                document,
                location=f"{location}.basis.evidence",
            )
        else:
            _resolve_record(
                claim.basis.evidence,
                index,
                location=f"{location}.basis.evidence",
            )


def _validate_claim_cycles(
    claims: Sequence[Claim],
    *,
    location_by_id: dict[str, str],
) -> None:
    edges: dict[str, str] = {}
    for claim in claims:
        basis = claim.basis
        if (
            isinstance(basis, TestedClaimBasis)
            and isinstance(basis.evidence, RecordRef)
            and basis.evidence.target_kind is TrustRecordKind.CLAIM
        ):
            edges[claim.id] = basis.evidence.target_id

    state: dict[str, int] = {}

    def visit(claim_id: str) -> None:
        current_state = state.get(claim_id, 0)
        if current_state == 1:
            _fail(
                IRErrorCode.CIRCULAR_CLAIM_BASIS,
                f"claim basis contains a cycle through {claim_id!r}",
                location=location_by_id[claim_id],
            )
        if current_state == 2:
            return
        state[claim_id] = 1
        target = edges.get(claim_id)
        if target is not None:
            visit(target)
        state[claim_id] = 2

    for claim in claims:
        visit(claim.id)


def validate_trust_semantics(document: TrustIR) -> None:
    index = _build_index(document)
    claims: list[Claim] = []
    location_by_claim_id: dict[str, str] = {}

    for position, record in enumerate(document.records):
        location = f"$.records[{position}]"
        if isinstance(record, SourceRecord):
            continue

        _validate_trace(record.trace, index, location=f"{location}.trace")

        if isinstance(record, Declaration):
            _validate_behavior_ref(
                record.subject,
                document,
                location=f"{location}.subject",
            )
        elif isinstance(record, ObservedFact):
            _validate_behavior_ref(
                record.subject,
                document,
                location=f"{location}.subject",
            )
        elif isinstance(record, BehaviorCandidate):
            _validate_record_refs(
                record.subjects,
                index,
                location=f"{location}.subjects",
                expected={
                    TrustRecordKind.DECLARATION,
                    TrustRecordKind.OBSERVED_FACT,
                },
            )
            actual_kinds = {ref.target_kind for ref in record.subjects}
            expected_kinds = {
                TrustRecordKind.DECLARATION,
                TrustRecordKind.OBSERVED_FACT,
            }
            if actual_kinds != expected_kinds or len(record.subjects) != 2:
                _fail(
                    IRErrorCode.INVALID_STRUCTURE,
                    (
                        "mapping candidate requires exactly one declaration "
                        "and one observed_fact"
                    ),
                    location=f"{location}.subjects",
                )
        elif isinstance(record, TrustMapping):
            _resolve_record(
                record.declaration,
                index,
                location=f"{location}.declaration",
                expected={TrustRecordKind.DECLARATION},
            )
            _resolve_record(
                record.observation,
                index,
                location=f"{location}.observation",
                expected={TrustRecordKind.OBSERVED_FACT},
            )
        elif isinstance(record, Claim):
            _validate_behavior_ref(
                record.subject,
                document,
                location=f"{location}.subject",
            )
            _validate_claim_basis(
                record,
                index,
                document,
                location=location,
            )
            claims.append(record)
            location_by_claim_id[record.id] = f"{location}.basis.evidence"
        else:
            raise AssertionError("unhandled trust record kind")

    _validate_claim_cycles(claims, location_by_id=location_by_claim_id)

    for claim in claims:
        basis = claim.basis
        if not isinstance(basis, TestedClaimBasis) or not isinstance(
            basis.evidence, RecordRef
        ):
            continue
        if basis.evidence.target_kind is TrustRecordKind.BEHAVIOR_CANDIDATE:
            _fail(
                IRErrorCode.CANDIDATE_IS_NOT_EVIDENCE,
                "behavior candidates are review metadata, not test evidence",
                location=location_by_claim_id[claim.id],
            )
        _fail(
            IRErrorCode.MISSING_CLAIM_BASIS,
            "tested claim requires verification_evidence from behavior IR",
            location=location_by_claim_id[claim.id],
        )


def _canonical_behavior_digest(document: BehaviorIR) -> str:
    return hashlib.sha256(canonical_ir_json(document).encode("ascii")).hexdigest()


def _validate_document_binding(
    ref: BehaviorDocumentRef,
    behavior: BehaviorIR,
    *,
    location: str,
) -> None:
    comparisons = (
        ("document_id", ref.document_id, behavior.document_id),
        ("ir_version", ref.ir_version, behavior.ir_version),
        (
            "canonical_digest",
            ref.canonical_digest.value,
            _canonical_behavior_digest(behavior),
        ),
    )
    for field, actual, expected in comparisons:
        if actual != expected:
            _fail(
                IRErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                f"subject_document {field} does not match supplied behavior IR",
                location=f"{location}.{field}",
            )


def _build_behavior_index(document: BehaviorIR) -> BehaviorEntityIndex:
    return {entity.id: entity for entity in document.entities}


def _resolve_behavior_ref(
    ref: BehaviorEntityRef,
    index: BehaviorEntityIndex,
    *,
    location: str,
    expected: set[EntityKind] | None = None,
) -> Entity:
    target = index.get(ref.target_id)
    if target is None:
        _fail(
            IRErrorCode.BROKEN_REFERENCE,
            f"behavior entity target {ref.target_id!r} does not exist",
            location=location,
        )
    if target.kind is not ref.target_kind:
        _fail(
            IRErrorCode.WRONG_TARGET_KIND,
            (
                f"reference declares {ref.target_kind.value!r}, but "
                f"{ref.target_id!r} is {target.kind.value!r}"
            ),
            location=f"{location}.target_kind",
        )
    if expected is not None and target.kind not in expected:
        allowed = ", ".join(sorted(kind.value for kind in expected))
        _fail(
            IRErrorCode.WRONG_TARGET_KIND,
            (
                f"{ref.target_id!r} has kind {target.kind.value!r}; "
                f"expected one of: {allowed}"
            ),
            location=f"{location}.target_kind",
        )
    return target


def _validate_external_refs(
    document: TrustIR,
    index: BehaviorEntityIndex,
) -> None:
    for position, record in enumerate(document.records):
        location = f"$.records[{position}]"
        if isinstance(record, (Declaration, ObservedFact, Claim)):
            _resolve_behavior_ref(
                record.subject,
                index,
                location=f"{location}.subject",
            )
        if (
            isinstance(record, Claim)
            and isinstance(record.basis, TestedClaimBasis)
            and isinstance(record.basis.evidence, BehaviorEntityRef)
        ):
            _resolve_behavior_ref(
                record.basis.evidence,
                index,
                location=f"{location}.basis.evidence",
                expected={EntityKind.VERIFICATION_EVIDENCE},
            )


def _derive_mapping_disposition(
    declaration: Declaration,
    observation: ObservedFact,
    behavior_index: BehaviorEntityIndex,
    *,
    location: str,
) -> str:
    if declaration.subject != observation.subject:
        _fail(
            IRErrorCode.MAPPING_BASIS_MISMATCH,
            "mapping declaration and observation subjects differ",
            location=f"{location}.observation",
        )
    declared_entity = _resolve_behavior_ref(
        declaration.subject,
        behavior_index,
        location=f"{location}.declaration",
    )
    if not isinstance(declared_entity, Effect):
        _fail(
            IRErrorCode.MAPPING_BASIS_MISMATCH,
            "same-behavior-slot requires a declaration that references an effect",
            location=f"{location}.declaration",
        )
    if declared_entity.target != observation.assertion.target:
        _fail(
            IRErrorCode.MAPPING_BASIS_MISMATCH,
            "observed assertion targets a different behavior slot",
            location=f"{location}.observation",
        )
    return (
        "match"
        if declared_entity.value == observation.assertion.value
        else "conflict"
    )


def _validate_mapping_disposition(
    mapping: TrustMapping,
    declaration: Declaration,
    observation: ObservedFact,
    behavior_index: BehaviorEntityIndex,
    *,
    location: str,
) -> None:
    expected = _derive_mapping_disposition(
        declaration,
        observation,
        behavior_index,
        location=location,
    )
    if mapping.disposition != expected:
        _fail(
            IRErrorCode.MAPPING_BASIS_MISMATCH,
            (
                f"mapping disposition {mapping.disposition!r} does not match "
                f"the immutable inputs; expected {expected!r}"
            ),
            location=f"{location}.disposition",
        )


def _claim_basis_mismatch(
    field: str,
    *,
    location: str,
) -> None:
    _fail(
        IRErrorCode.CLAIM_BASIS_MISMATCH,
        f"claim {field} does not match its exact basis",
        location=f"{location}.{field}",
    )


def _evaluate_tested_claim(
    claim: Claim,
    basis: TestedClaimBasis,
    trust_index: TrustRecordIndex,
    behavior_index: BehaviorEntityIndex,
    *,
    location: str,
) -> None:
    if not isinstance(basis.evidence, BehaviorEntityRef):
        raise AssertionError("internal trust validation accepted non-IR evidence")
    evidence = _resolve_behavior_ref(
        basis.evidence,
        behavior_index,
        location=f"{location}.basis.evidence",
        expected={EntityKind.VERIFICATION_EVIDENCE},
    )
    if not isinstance(evidence, VerificationEvidence):
        raise AssertionError("kind-discriminated behavior index is inconsistent")
    if evidence.outcome != "passed":
        _fail(
            IRErrorCode.EVIDENCE_NOT_PASSED,
            f"verification evidence outcome is {evidence.outcome!r}",
            location=f"{location}.basis.evidence.outcome",
        )
    artifact = _resolve_record(
        basis.artifact,
        trust_index,
        location=f"{location}.basis.artifact",
        expected={TrustRecordKind.SOURCE_RECORD},
    )
    if not isinstance(artifact, SourceRecord):
        raise AssertionError("kind-discriminated trust index is inconsistent")
    if evidence.source_revision != artifact.source_revision:
        _fail(
            IRErrorCode.STALE_EVIDENCE,
            "evidence source revision differs from the current artifact revision",
            location=f"{location}.basis.artifact.source_revision",
        )
    if not any(
        subject.target_kind is claim.subject.target_kind
        and subject.target_id == claim.subject.target_id
        for subject in evidence.subjects
    ):
        _claim_basis_mismatch("subject", location=f"{location}.basis")
    if evidence.check != basis.check:
        _claim_basis_mismatch("check", location=f"{location}.basis")
    if evidence.environment != basis.environment:
        _claim_basis_mismatch("environment", location=f"{location}.basis")
    provenance = _resolve_behavior_ref(
        BehaviorEntityRef(
            kind="behavior_entity_ref",
            document_id=claim.subject.document_id,
            ir_version=claim.subject.ir_version,
            canonical_digest=claim.subject.canonical_digest,
            target_kind=evidence.provenance.target_kind,
            target_id=evidence.provenance.target_id,
        ),
        behavior_index,
        location=f"{location}.basis.evidence.provenance",
        expected={EntityKind.PROVENANCE},
    )
    if not isinstance(provenance, Provenance):
        raise AssertionError("kind-discriminated behavior index is inconsistent")
    if provenance.producer != basis.producer:
        _claim_basis_mismatch("producer", location=f"{location}.basis")


def _evaluate_claim(
    claim: Claim,
    trust_index: TrustRecordIndex,
    behavior_index: BehaviorEntityIndex,
    *,
    location: str,
) -> ClaimLevel:
    if claim.level is ClaimLevel.VERIFIED:
        _fail(
            IRErrorCode.VERIFIED_UNAVAILABLE,
            (
                "verified claims are unavailable until a versioned property, "
                "assumptions, and proof or exhaustive procedure are represented"
            ),
            location=f"{location}.level",
        )
    if isinstance(claim.basis, ObservedClaimBasis):
        fact = _resolve_record(
            claim.basis.fact,
            trust_index,
            location=f"{location}.basis.fact",
            expected={TrustRecordKind.OBSERVED_FACT},
        )
        if not isinstance(fact, ObservedFact):
            raise AssertionError("kind-discriminated trust index is inconsistent")
        if fact.subject != claim.subject:
            _claim_basis_mismatch("subject", location=f"{location}.basis")
    elif isinstance(claim.basis, DeclaredClaimBasis):
        declaration = _resolve_record(
            claim.basis.declaration,
            trust_index,
            location=f"{location}.basis.declaration",
            expected={TrustRecordKind.DECLARATION},
        )
        if not isinstance(declaration, Declaration):
            raise AssertionError("kind-discriminated trust index is inconsistent")
        if declaration.subject != claim.subject:
            _claim_basis_mismatch("subject", location=f"{location}.basis")
    elif isinstance(claim.basis, MappedClaimBasis):
        mapping = _resolve_record(
            claim.basis.mapping,
            trust_index,
            location=f"{location}.basis.mapping",
            expected={TrustRecordKind.MAPPING},
        )
        if not isinstance(mapping, TrustMapping):
            raise AssertionError("kind-discriminated trust index is inconsistent")
        declaration = _resolve_record(
            mapping.declaration,
            trust_index,
            location=f"{location}.basis.mapping.declaration",
            expected={TrustRecordKind.DECLARATION},
        )
        observation = _resolve_record(
            mapping.observation,
            trust_index,
            location=f"{location}.basis.mapping.observation",
            expected={TrustRecordKind.OBSERVED_FACT},
        )
        if not isinstance(declaration, Declaration) or not isinstance(
            observation, ObservedFact
        ):
            raise AssertionError("kind-discriminated trust index is inconsistent")
        if (
            declaration.subject != claim.subject
            or observation.subject != claim.subject
        ):
            _claim_basis_mismatch("mapping_pair", location=f"{location}.basis")
    elif isinstance(claim.basis, TestedClaimBasis):
        _evaluate_tested_claim(
            claim,
            claim.basis,
            trust_index,
            behavior_index,
            location=location,
        )
    else:
        raise AssertionError("unhandled claim basis")
    return claim.level


def validate_trust_against_behavior(
    document: TrustIR,
    behavior: BehaviorIR,
) -> None:
    validate_trust_semantics(document)
    validate_ir_semantics(behavior)
    _validate_document_binding(
        document.subject_document,
        behavior,
        location="$.subject_document",
    )
    behavior_index = _build_behavior_index(behavior)
    _validate_external_refs(document, behavior_index)
    trust_index = _build_index(document)

    for position, record in enumerate(document.records):
        if not isinstance(record, TrustMapping):
            continue
        declaration = _resolve_record(
            record.declaration,
            trust_index,
            location=f"$.records[{position}].declaration",
            expected={TrustRecordKind.DECLARATION},
        )
        observation = _resolve_record(
            record.observation,
            trust_index,
            location=f"$.records[{position}].observation",
            expected={TrustRecordKind.OBSERVED_FACT},
        )
        if not isinstance(declaration, Declaration) or not isinstance(
            observation, ObservedFact
        ):
            raise AssertionError("kind-discriminated trust index is inconsistent")
        _validate_mapping_disposition(
            record,
            declaration,
            observation,
            behavior_index,
            location=f"$.records[{position}]",
        )

    for position, record in enumerate(document.records):
        if isinstance(record, Claim):
            _evaluate_claim(
                record,
                trust_index,
                behavior_index,
                location=f"$.records[{position}]",
            )


def supported_claim_levels(
    document: TrustIR,
    behavior: BehaviorIR,
) -> frozenset[ClaimLevel]:
    validate_trust_against_behavior(document, behavior)
    return frozenset(
        record.level for record in document.records if isinstance(record, Claim)
    )


def reconcile_mapping(
    document: TrustIR,
    behavior: BehaviorIR,
    *,
    mapping_id: str,
    declaration_id: str,
    observation_id: str,
    trace: RecordRef,
) -> TrustMapping:
    validate_trust_against_behavior(document, behavior)
    trust_index = _build_index(document)
    if mapping_id in trust_index:
        _fail(
            IRErrorCode.DUPLICATE_IDENTITY,
            f"trust record id {mapping_id!r} already exists",
            location="$.mapping_id",
        )
    declaration = _resolve_record(
        RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.DECLARATION,
            target_id=declaration_id,
        ),
        trust_index,
        location="$.declaration_id",
        expected={TrustRecordKind.DECLARATION},
    )
    observation = _resolve_record(
        RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.OBSERVED_FACT,
            target_id=observation_id,
        ),
        trust_index,
        location="$.observation_id",
        expected={TrustRecordKind.OBSERVED_FACT},
    )
    _validate_trace(trace, trust_index, location="$.trace")
    if not isinstance(declaration, Declaration) or not isinstance(
        observation, ObservedFact
    ):
        raise AssertionError("kind-discriminated trust index is inconsistent")
    behavior_index = _build_behavior_index(behavior)
    disposition = _derive_mapping_disposition(
        declaration,
        observation,
        behavior_index,
        location="$",
    )
    return TrustMapping(
        kind=TrustRecordKind.MAPPING,
        id=mapping_id,
        declaration=RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.DECLARATION,
            target_id=declaration_id,
        ),
        observation=RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.OBSERVED_FACT,
            target_id=observation_id,
        ),
        relationship="same-behavior-slot",
        disposition=disposition,
        trace=trace,
    )
