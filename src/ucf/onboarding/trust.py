from __future__ import annotations

import hashlib

from ucf.ir import (
    CURRENT_TRUST_IR_VERSION,
    canonical_ir_json,
    canonical_trust_ir_json,
    parse_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import (
    BehaviorIR,
    Digest,
    DomainTarget,
    StringValue,
)
from ucf.ir.trust_models import (
    BehaviorCandidate,
    BehaviorDocumentRef,
    Claim,
    ClaimLevel,
    Declaration,
    DeclaredClaimBasis,
    FactAssertion,
    ObservedClaimBasis,
    ObservedFact,
    RecordRef,
    SourceRecord,
    TrustIR,
    TrustMapping,
    TrustRecordKind,
)
from ucf.onboarding.codec import canonical_onboarding_digest
from ucf.onboarding.errors import (
    OnboardingErrorCode,
    OnboardingValidationError,
)
from ucf.onboarding.models import (
    BehaviorMaterialization,
    DecisionSet,
    DiscoveryResult,
)
from ucf.onboarding.reconciliation import materialize_behavior
from ucf.onboarding.validation import validate_decision_set


def build_onboarding_trust(
    discovery: DiscoveryResult,
    decision_set: DecisionSet,
    behavior: BehaviorIR,
    materializations: tuple[BehaviorMaterialization, ...],
) -> TrustIR:
    validate_decision_set(discovery, decision_set)
    expected_behavior, expected_materializations = materialize_behavior(
        discovery,
        decision_set,
    )
    if behavior != expected_behavior:
        raise OnboardingValidationError(
            OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "Behavior IR differs from deterministic decision materialization",
            location="$.behavior",
        )
    if materializations != expected_materializations:
        raise OnboardingValidationError(
            OnboardingErrorCode.ILLEGAL_PROMOTION,
            "materializations must be the exact accepted and edited decisions",
            location="$.materializations",
        )

    behavior_digest = hashlib.sha256(
        canonical_ir_json(behavior).encode("ascii")
    ).hexdigest()
    discovery_digest = canonical_onboarding_digest(discovery)
    decision_digest = canonical_onboarding_digest(decision_set)
    discovery_source = SourceRecord(
        kind=TrustRecordKind.SOURCE_RECORD,
        id="source.discovery",
        source_uri=discovery.schema_uri,
        source_revision=discovery_digest,
        producer=discovery.producer,
        captured_at=decision_set.capture_context.captured_at,
    )
    decision_source = SourceRecord(
        kind=TrustRecordKind.SOURCE_RECORD,
        id="source.decisions",
        source_uri=decision_set.schema_uri,
        source_revision=decision_digest,
        producer=decision_set.reviewer,
        captured_at=decision_set.capture_context.captured_at,
    )
    decision_trace = RecordRef(
        kind="record_ref",
        target_kind=TrustRecordKind.SOURCE_RECORD,
        target_id=decision_source.id,
    )
    records = [discovery_source, decision_source]
    candidates_by_id = {
        candidate.id: candidate for candidate in discovery.candidates
    }
    for link in materializations:
        suffix = link.candidate.candidate_id.removeprefix("candidate.")
        declaration = Declaration(
            kind=TrustRecordKind.DECLARATION,
            id=f"declaration.{suffix}",
            subject=link.root,
            trace=decision_trace,
        )
        observation = ObservedFact(
            kind=TrustRecordKind.OBSERVED_FACT,
            id=f"observed.{suffix}",
            subject=link.root,
            assertion=FactAssertion(
                kind="fact_assertion",
                target=DomainTarget(
                    kind="domain_target",
                    subject="inventory",
                    path=("public-interface-id",),
                ),
                value=StringValue(
                    kind="string",
                    value=candidates_by_id[
                        link.candidate.candidate_id
                    ].subject.target_id,
                ),
            ),
            trace=decision_trace,
        )
        declaration_ref = RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.DECLARATION,
            target_id=declaration.id,
        )
        observation_ref = RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.OBSERVED_FACT,
            target_id=observation.id,
        )
        records.extend(
            (
                declaration,
                observation,
                Claim(
                    kind=TrustRecordKind.CLAIM,
                    id=f"claim.declared.{suffix}",
                    level=ClaimLevel.DECLARED,
                    subject=link.root,
                    basis=DeclaredClaimBasis(
                        kind="declared_claim_basis",
                        declaration=declaration_ref,
                    ),
                    trace=decision_trace,
                ),
                Claim(
                    kind=TrustRecordKind.CLAIM,
                    id=f"claim.observed.{suffix}",
                    level=ClaimLevel.OBSERVED,
                    subject=link.root,
                    basis=ObservedClaimBasis(
                        kind="observed_claim_basis",
                        fact=observation_ref,
                    ),
                    trace=decision_trace,
                ),
            )
        )
    trust = parse_trust_ir_json(
        canonical_trust_ir_json(
            TrustIR(
                kind="trust_ir",
                trust_ir_version=CURRENT_TRUST_IR_VERSION,
                document_id=(
                    "trust."
                    + hashlib.sha256(
                        (
                            behavior_digest + decision_digest.value
                        ).encode("ascii")
                    ).hexdigest()
                ),
                subject_document=BehaviorDocumentRef(
                    kind="behavior_document_ref",
                    document_id=behavior.document_id,
                    ir_version=behavior.ir_version,
                    canonical_digest=Digest(
                        kind="digest",
                        algorithm="sha-256",
                        value=behavior_digest,
                    ),
                ),
                records=tuple(records),
            )
        )
    )
    validate_onboarding_trust(trust, behavior)
    return trust


def validate_onboarding_trust(
    trust: TrustIR,
    behavior: BehaviorIR,
) -> None:
    for position, record in enumerate(trust.records):
        if isinstance(record, (BehaviorCandidate, TrustMapping)):
            raise OnboardingValidationError(
                OnboardingErrorCode.ILLEGAL_PROMOTION,
                "BRN-002 trust cannot contain candidates or mappings",
                location=f"$.records[{position}]",
            )
        if isinstance(record, Claim) and record.level not in {
            ClaimLevel.OBSERVED,
            ClaimLevel.DECLARED,
        }:
            raise OnboardingValidationError(
                OnboardingErrorCode.ILLEGAL_PROMOTION,
                (
                    "BRN-002 trust permits only independently supported "
                    "observed and declared claims"
                ),
                location=f"$.records[{position}].level",
            )
    validate_trust_against_behavior(trust, behavior)
