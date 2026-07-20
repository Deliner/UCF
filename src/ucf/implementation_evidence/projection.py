from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass

from ucf.implementation_evidence.codec import (
    canonical_execution_environment_digest,
    canonical_implementation_evidence_digest,
)
from ucf.implementation_evidence.errors import (
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
)
from ucf.implementation_evidence.models import (
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationMappingResult,
)
from ucf.implementation_evidence.validation import (
    validate_execution_verification_result,
)
from ucf.inventory import InventorySnapshot
from ucf.ir import (
    CURRENT_IR_VERSION,
    canonical_ir_json,
    parse_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import (
    ArtifactSource,
    BehaviorIR,
    Digest,
    EntityKind,
    EntityRef,
    Producer,
    Provenance,
    VerificationEvidence,
)
from ucf.ir.trust_models import (
    CURRENT_TRUST_IR_VERSION,
    BehaviorDocumentRef,
    BehaviorEntityRef,
    Claim,
    ClaimLevel,
    RecordRef,
    SourceRecord,
    TestedClaimBasis,
    TrustIR,
    TrustRecordKind,
)
from ucf.onboarding import OnboardingBundle


@dataclass(frozen=True)
class ExecutionVerificationProjection:
    successor_behavior: BehaviorIR
    tested_trust: TrustIR


def project_execution_verification(
    result: ExecutionVerificationResult,
    *,
    request: ExecutionVerificationRequest,
    mapping_result: ImplementationMappingResult,
    bundle: OnboardingBundle,
    current_inventory: InventorySnapshot,
    mapping_initialized_adapter: Producer,
    initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> ExecutionVerificationProjection:
    validate_execution_verification_result(
        result,
        request=request,
        mapping_result=mapping_result,
        bundle=bundle,
        current_inventory=current_inventory,
        mapping_initialized_adapter=mapping_initialized_adapter,
        initialized_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    if result.outcome != "passed":
        _fail(
            ImplementationEvidenceErrorCode.EVIDENCE_NOT_PASSED,
            "only passed execution evidence can project a tested claim",
            location="$.outcome",
        )
    behavior = bundle.behavior
    behavior_digest = _behavior_digest(behavior)
    behavior_comparisons = (
        (
            "document_id",
            result.request.base_behavior.document_id,
            behavior.document_id,
        ),
        (
            "ir_version",
            result.request.base_behavior.ir_version,
            behavior.ir_version,
        ),
        (
            "canonical_digest",
            result.request.base_behavior.canonical_digest,
            behavior_digest,
        ),
    )
    for field, actual, expected in behavior_comparisons:
        if actual != expected:
            _fail(
                ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                f"verification base Behavior {field} differs from input",
                location=f"$.request.base_behavior.{field}",
            )
    entities = {entity.id: entity for entity in behavior.entities}
    subject = entities.get(result.request.subject.target_id)
    if subject is None:
        _fail(
            ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
            "verification subject does not exist in the base behavior",
            location="$.request.subject",
        )
    if subject.kind is not result.request.subject.target_kind:
        _fail(
            ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
            "verification subject kind differs from the base behavior",
            location="$.request.subject.target_kind",
        )

    result_digest = canonical_implementation_evidence_digest(result)
    provenance_id = f"provenance.execution.{result_digest.value}"
    evidence_id = f"evidence.execution.{result_digest.value}"
    for entity_id in (provenance_id, evidence_id):
        if entity_id in entities:
            _fail(
                ImplementationEvidenceErrorCode.DUPLICATE_IDENTITY,
                "derived execution evidence ID collides with base behavior",
                location="$.entities",
            )
    provenance_ref = EntityRef(
        kind="entity_ref",
        target_kind=EntityKind.PROVENANCE,
        target_id=provenance_id,
    )
    provenance = Provenance(
        kind=EntityKind.PROVENANCE,
        id=provenance_id,
        source=ArtifactSource(
            kind="artifact_source",
            uri=result.request.source.subject_uri,
            revision=result.request.source.source_revision,
        ),
        producer=result.producer,
        captured_at=result.executed_at,
    )
    environment_digest = canonical_execution_environment_digest(
        result.request.environment
    )
    evidence = VerificationEvidence(
        kind=EntityKind.VERIFICATION_EVIDENCE,
        id=evidence_id,
        subjects=(
            EntityRef(
                kind="entity_ref",
                target_kind=result.request.subject.target_kind,
                target_id=result.request.subject.target_id,
            ),
        ),
        check=result.request.check,
        outcome=result.outcome,
        executed_at=result.executed_at,
        source_revision=result.request.source.source_revision,
        environment=environment_digest,
        provenance=provenance_ref,
    )
    successor = parse_ir_json(
        canonical_ir_json(
            BehaviorIR(
                kind="behavior_ir",
                ir_version=CURRENT_IR_VERSION,
                document_id=behavior.document_id,
                roots=behavior.roots,
                entities=(*behavior.entities, provenance, evidence),
            )
        )
    )
    successor_digest = _behavior_digest(successor)
    successor_document = BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=successor.document_id,
        ir_version=successor.ir_version,
        canonical_digest=successor_digest,
    )
    source_id = f"source.execution.{result_digest.value}"
    claim_id = f"claim.tested.{result_digest.value}"
    source_record = SourceRecord(
        kind=TrustRecordKind.SOURCE_RECORD,
        id=source_id,
        source_uri=result.request.source.subject_uri,
        source_revision=result.request.source.source_revision,
        producer=result.producer,
        captured_at=result.executed_at,
    )
    trace_ref = RecordRef(
        kind="record_ref",
        target_kind=TrustRecordKind.SOURCE_RECORD,
        target_id=source_id,
    )
    tested_claim = Claim(
        kind=TrustRecordKind.CLAIM,
        id=claim_id,
        level=ClaimLevel.TESTED,
        subject=BehaviorEntityRef(
            kind="behavior_entity_ref",
            document_id=successor.document_id,
            ir_version=successor.ir_version,
            canonical_digest=successor_digest,
            target_kind=result.request.subject.target_kind,
            target_id=result.request.subject.target_id,
        ),
        basis=TestedClaimBasis(
            kind="tested_claim_basis",
            evidence=BehaviorEntityRef(
                kind="behavior_entity_ref",
                document_id=successor.document_id,
                ir_version=successor.ir_version,
                canonical_digest=successor_digest,
                target_kind=EntityKind.VERIFICATION_EVIDENCE,
                target_id=evidence_id,
            ),
            artifact=trace_ref,
            check=result.request.check,
            environment=environment_digest,
            producer=result.producer,
        ),
        trace=trace_ref,
    )
    trust = TrustIR(
        kind="trust_ir",
        trust_ir_version=CURRENT_TRUST_IR_VERSION,
        document_id=(
            f"document.execution-verification.{result_digest.value}"
        ),
        subject_document=successor_document,
        records=(source_record, tested_claim),
    )
    validate_trust_against_behavior(trust, successor)
    return ExecutionVerificationProjection(
        successor_behavior=successor,
        tested_trust=trust,
    )


def _behavior_digest(behavior: BehaviorIR) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_ir_json(behavior).encode("ascii")
        ).hexdigest(),
    )


def _fail(
    code: ImplementationEvidenceErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise ImplementationEvidenceValidationError(
        code,
        message,
        location=location,
    )
