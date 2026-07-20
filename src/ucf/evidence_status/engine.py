from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from ucf.evidence_status.codec import (
    canonical_evidence_status_digest,
    canonical_evidence_status_json,
)
from ucf.evidence_status.errors import (
    EvidenceStatusErrorCode,
    EvidenceStatusValidationError,
)
from ucf.evidence_status.models import (
    BEHAVIOR_PROJECTION_PROCEDURE_URI,
    EVIDENCE_ASSESS_PROCEDURE_URI,
    EVIDENCE_RECORD_PROCEDURE_URI,
    EVIDENCE_STATUS_VERSION,
    EXECUTION_PROJECTION_PROCEDURE_URI,
    MAPPING_PROJECTION_PROCEDURE_URI,
    SOURCE_PROJECTION_PROCEDURE_URI,
    VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI,
    VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
    BehaviorEvidenceProjection,
    CurrentEvidenceCoordinates,
    EvidenceProjectionMember,
    EvidenceStatus,
    EvidenceStatusReason,
    EvidenceStatusReasonCode,
    EvidenceTraceCoordinates,
    ExecutionEvidenceProjection,
    ExecutionVerificationResultRef,
    InventorySnapshotRef,
    MappingEvidenceProjection,
    RecordedEvidenceCoordinates,
    SourceEvidenceProjection,
    TrustClaimRef,
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
    VerificationEvidenceEnvelopeRef,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationMappingResult,
    ImplementationMappingResultRef,
    canonical_implementation_evidence_digest,
    project_execution_verification,
    validate_execution_verification_result,
    validate_implementation_mapping_result,
)
from ucf.inventory import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    InventoryRecordRef,
    InventorySnapshot,
    canonical_inventory_json,
)
from ucf.ir import canonical_ir_json, canonical_trust_ir_json
from ucf.ir.models import Digest, EntityKind, Producer
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    Claim,
    ClaimLevel,
)
from ucf.onboarding import (
    OnboardingBundle,
    canonical_onboarding_digest,
)
from ucf.ratchet.models import BehaviorSubjectKey, OnboardingBundleRef


def record_verification_evidence(
    result: ExecutionVerificationResult,
    *,
    request: ExecutionVerificationRequest,
    mapping_result: ImplementationMappingResult,
    bundle: OnboardingBundle,
    current_inventory: InventorySnapshot,
    mapping_initialized_adapter: Producer,
    initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> VerificationEvidenceEnvelope:
    projection = project_execution_verification(
        result,
        request=request,
        mapping_result=mapping_result,
        bundle=bundle,
        current_inventory=current_inventory,
        mapping_initialized_adapter=mapping_initialized_adapter,
        initialized_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    subject = BehaviorSubjectKey(
        kind="behavior_subject_key",
        subject_uri=current_inventory.subject_uri,
        target_kind=request.subject.target_kind,
        target_id=request.subject.target_id,
    )
    recorded = _derive_coordinates(
        subject=subject,
        result=result,
        request=request,
        mapping_result=mapping_result,
        bundle=bundle,
        inventory=current_inventory,
        verification_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    trace = _derive_trace(bundle, current_inventory, mapping_result)
    claim = next(
        (
            record
            for record in projection.tested_trust.records
            if isinstance(record, Claim)
            and record.level is ClaimLevel.TESTED
        ),
        None,
    )
    if claim is None:
        _fail(
            EvidenceStatusErrorCode.BROKEN_REFERENCE,
            "verification projection did not produce one tested claim",
            location="$.claim",
        )
    trust_digest = _digest_bytes(
        canonical_trust_ir_json(projection.tested_trust).encode("ascii")
    )
    payload = {
        "kind": "verification_evidence_envelope",
        "evidence_status_version": EVIDENCE_STATUS_VERSION,
        "schema_uri": VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
        "id": f"envelope.{'0' * 64}",
        "procedure_uri": EVIDENCE_RECORD_PROCEDURE_URI,
        "verification_result": _verification_result_ref(result).model_dump(
            mode="json"
        ),
        "claim": TrustClaimRef(
            kind="trust_claim_ref",
            trust_ir_version=projection.tested_trust.trust_ir_version,
            document_id=projection.tested_trust.document_id,
            canonical_digest=trust_digest,
            target_id=claim.id,
        ).model_dump(mode="json"),
        "subject": subject.model_dump(mode="json"),
        "recorded": recorded.model_dump(mode="json"),
        "trace": trace.model_dump(mode="json"),
    }
    return _identified_model(
        VerificationEvidenceEnvelope,
        "envelope",
        payload,
    )


def assess_verification_evidence(
    envelope: VerificationEvidenceEnvelope,
    *,
    recorded_result: ExecutionVerificationResult,
    recorded_request: ExecutionVerificationRequest,
    recorded_mapping_result: ImplementationMappingResult,
    recorded_bundle: OnboardingBundle,
    recorded_current_inventory: InventorySnapshot,
    recorded_mapping_initialized_adapter: Producer,
    recorded_initialized_adapter: Producer,
    recorded_negotiated_capabilities: Mapping[str, str],
    current_request: ExecutionVerificationRequest | None = None,
    current_mapping_result: ImplementationMappingResult | None = None,
    current_bundle: OnboardingBundle | None = None,
    current_inventory: InventorySnapshot | None = None,
    current_mapping_initialized_adapter: Producer | None = None,
    current_initialized_adapter: Producer | None = None,
    current_negotiated_capabilities: Mapping[str, str] | None = None,
    current_result: ExecutionVerificationResult | None = None,
) -> VerificationEvidenceAssessment:
    envelope = _revalidate_status_model(
        envelope,
        VerificationEvidenceEnvelope,
        label="verification evidence envelope",
    )
    expected = record_verification_evidence(
        recorded_result,
        request=recorded_request,
        mapping_result=recorded_mapping_result,
        bundle=recorded_bundle,
        current_inventory=recorded_current_inventory,
        mapping_initialized_adapter=recorded_mapping_initialized_adapter,
        initialized_adapter=recorded_initialized_adapter,
        negotiated_capabilities=recorded_negotiated_capabilities,
    )
    _validate_envelope_context(envelope, expected)

    current_values = (
        current_result,
        current_request,
        current_mapping_result,
        current_bundle,
        current_inventory,
        current_mapping_initialized_adapter,
        current_initialized_adapter,
        current_negotiated_capabilities,
    )
    if all(value is None for value in current_values):
        return _assessment(
            envelope,
            status=EvidenceStatus.INDETERMINATE,
            current=None,
            reasons=(
                EvidenceStatusReason(
                    kind="evidence_status_reason",
                    code=(
                        EvidenceStatusReasonCode.CURRENT_CONTEXT_UNAVAILABLE
                    ),
                    recorded=None,
                    current=None,
                ),
            ),
        )
    if any(value is None for value in current_values):
        _fail(
            EvidenceStatusErrorCode.CURRENT_CONTEXT_INCOMPLETE,
            "current evidence context must be supplied completely or omitted",
            location="$.current",
        )
    assert current_request is not None
    assert current_result is not None
    assert current_mapping_result is not None
    assert current_bundle is not None
    assert current_inventory is not None
    assert current_mapping_initialized_adapter is not None
    assert current_initialized_adapter is not None
    assert current_negotiated_capabilities is not None

    _validate_current_context(
        result=current_result,
        request=current_request,
        mapping_result=current_mapping_result,
        bundle=current_bundle,
        inventory=current_inventory,
        mapping_adapter=current_mapping_initialized_adapter,
        verification_adapter=current_initialized_adapter,
        negotiated_capabilities=current_negotiated_capabilities,
    )
    current_subject = BehaviorSubjectKey(
        kind="behavior_subject_key",
        subject_uri=current_inventory.subject_uri,
        target_kind=current_request.subject.target_kind,
        target_id=current_request.subject.target_id,
    )
    if current_subject != envelope.subject:
        _fail(
            EvidenceStatusErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "current context names a different evidence subject",
            location="$.current.subject",
        )
    selective = _derive_coordinates(
        subject=current_subject,
        result=current_result,
        request=current_request,
        mapping_result=current_mapping_result,
        bundle=current_bundle,
        inventory=current_inventory,
        verification_adapter=current_initialized_adapter,
        negotiated_capabilities=current_negotiated_capabilities,
    )
    current = CurrentEvidenceCoordinates(
        kind="current_evidence_coordinates",
        subject=current_subject,
        verification_result=_verification_result_ref(current_result),
        behavior=selective.behavior,
        source=selective.source,
        mapping=selective.mapping,
        execution=selective.execution,
        trace=_derive_trace(
            current_bundle,
            current_inventory,
            current_mapping_result,
        ),
    )
    reasons = _compare_coordinates(envelope.recorded, current)
    return _assessment(
        envelope,
        status=(
            EvidenceStatus.STALE if reasons else EvidenceStatus.FRESH
        ),
        current=current,
        reasons=reasons,
    )


def validate_verification_evidence_assessment(
    assessment: VerificationEvidenceAssessment,
    envelope: VerificationEvidenceEnvelope,
    *,
    recorded_result: ExecutionVerificationResult,
    recorded_request: ExecutionVerificationRequest,
    recorded_mapping_result: ImplementationMappingResult,
    recorded_bundle: OnboardingBundle,
    recorded_current_inventory: InventorySnapshot,
    recorded_mapping_initialized_adapter: Producer,
    recorded_initialized_adapter: Producer,
    recorded_negotiated_capabilities: Mapping[str, str],
    current_request: ExecutionVerificationRequest | None = None,
    current_mapping_result: ImplementationMappingResult | None = None,
    current_bundle: OnboardingBundle | None = None,
    current_inventory: InventorySnapshot | None = None,
    current_mapping_initialized_adapter: Producer | None = None,
    current_initialized_adapter: Producer | None = None,
    current_negotiated_capabilities: Mapping[str, str] | None = None,
    current_result: ExecutionVerificationResult | None = None,
) -> VerificationEvidenceAssessment:
    validated = _revalidate_status_model(
        assessment,
        VerificationEvidenceAssessment,
        label="verification evidence assessment",
    )
    expected = assess_verification_evidence(
        envelope,
        recorded_result=recorded_result,
        recorded_request=recorded_request,
        recorded_mapping_result=recorded_mapping_result,
        recorded_bundle=recorded_bundle,
        recorded_current_inventory=recorded_current_inventory,
        recorded_mapping_initialized_adapter=(
            recorded_mapping_initialized_adapter
        ),
        recorded_initialized_adapter=recorded_initialized_adapter,
        recorded_negotiated_capabilities=(
            recorded_negotiated_capabilities
        ),
        current_result=current_result,
        current_request=current_request,
        current_mapping_result=current_mapping_result,
        current_bundle=current_bundle,
        current_inventory=current_inventory,
        current_mapping_initialized_adapter=(
            current_mapping_initialized_adapter
        ),
        current_initialized_adapter=current_initialized_adapter,
        current_negotiated_capabilities=current_negotiated_capabilities,
    )
    if validated != expected:
        _fail(
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
            "assessment differs from the exact recomputed evidence status",
            location="$",
        )
    return validated


def _derive_coordinates(
    *,
    subject: BehaviorSubjectKey,
    result: ExecutionVerificationResult,
    request: ExecutionVerificationRequest,
    mapping_result: ImplementationMappingResult,
    bundle: OnboardingBundle,
    inventory: InventorySnapshot,
    verification_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> RecordedEvidenceCoordinates:
    binding = _subject_binding(mapping_result, subject)
    behavior = _behavior_projection(bundle, subject)
    source = _source_projection(inventory, binding.source_records)
    mapping = _mapping_projection(subject, binding.source_records)
    execution = _execution_projection(
        result=result,
        request=request,
        inventory=inventory,
        mapping_result=mapping_result,
        verification_adapter=verification_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    return RecordedEvidenceCoordinates(
        kind="recorded_evidence_coordinates",
        behavior=behavior,
        source=source,
        mapping=mapping,
        execution=execution,
    )


def _behavior_projection(
    bundle: OnboardingBundle,
    subject: BehaviorSubjectKey,
) -> BehaviorEvidenceProjection:
    materialization = next(
        (
            item
            for item in bundle.baseline.materializations
            if item.root.target_kind is subject.target_kind
            and item.root.target_id == subject.target_id
        ),
        None,
    )
    if materialization is None:
        _fail(
            EvidenceStatusErrorCode.BROKEN_REFERENCE,
            "evidence subject has no reviewed Behavior materialization",
            location="$.behavior",
        )
    entities = {entity.id: entity for entity in bundle.behavior.entities}
    members = []
    for reference in materialization.entities:
        entity = entities.get(reference.target_id)
        if entity is None:
            _fail(
                EvidenceStatusErrorCode.BROKEN_REFERENCE,
                "Behavior materialization reference does not resolve",
                location="$.behavior",
            )
        if entity.kind is not reference.target_kind:
            _fail(
                EvidenceStatusErrorCode.BROKEN_REFERENCE,
                "Behavior materialization reference has the wrong kind",
                location="$.behavior",
            )
        if entity.kind is EntityKind.PROVENANCE:
            continue
        members.append(
            _projection_member(
                entity.kind.value,
                entity.id,
                entity.model_dump(
                    mode="json",
                    exclude={"provenance"},
                ),
            )
        )
    return _projection(
        BehaviorEvidenceProjection,
        "behavior_evidence_projection",
        BEHAVIOR_PROJECTION_PROCEDURE_URI,
        members,
    )


def _source_projection(
    inventory: InventorySnapshot,
    roots: tuple[InventoryRecordRef, ...],
) -> SourceEvidenceProjection:
    records = {record.id: record for record in inventory.records}
    pending = list(roots)
    resolved = {}
    while pending:
        reference = pending.pop()
        if reference.target_id in resolved:
            continue
        record = records.get(reference.target_id)
        if record is None or str(record.kind) != reference.target_kind.value:
            _fail(
                EvidenceStatusErrorCode.BROKEN_REFERENCE,
                "source dependency reference does not resolve",
                location="$.source",
            )
        resolved[record.id] = record
        pending.extend(_inventory_references(record))
    members = [
        _projection_member(
            str(record.kind),
            record.id,
            record.model_dump(mode="json"),
        )
        for record in resolved.values()
    ]
    return _projection(
        SourceEvidenceProjection,
        "source_evidence_projection",
        SOURCE_PROJECTION_PROCEDURE_URI,
        members,
    )


def _mapping_projection(
    subject: BehaviorSubjectKey,
    records: tuple[InventoryRecordRef, ...],
) -> MappingEvidenceProjection:
    member = _projection_member(
        subject.target_kind.value,
        subject.target_id,
        {
            "kind": "mapping_binding_projection",
            "subject": {
                "target_kind": subject.target_kind.value,
                "target_id": subject.target_id,
            },
            "source_records": [
                {
                    "target_kind": record.target_kind.value,
                    "target_id": record.target_id,
                }
                for record in records
            ],
        },
    )
    return _projection(
        MappingEvidenceProjection,
        "mapping_evidence_projection",
        MAPPING_PROJECTION_PROCEDURE_URI,
        [member],
    )


def _execution_projection(
    *,
    result: ExecutionVerificationResult,
    request: ExecutionVerificationRequest,
    inventory: InventorySnapshot,
    mapping_result: ImplementationMappingResult,
    verification_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> ExecutionEvidenceProjection:
    values = {
        "inventory-adapter": {
            "producer": inventory.producer.model_dump(mode="json"),
            "capability": inventory.capability.model_dump(mode="json"),
        },
        "mapping-adapter": mapping_result.producer.model_dump(mode="json"),
        "verification-adapter": verification_adapter.model_dump(mode="json"),
        "capability": {
            "mapping": {
                "declared": mapping_result.capability.model_dump(mode="json"),
                "selected": negotiated_capabilities.get(
                    IMPLEMENTATION_MAPPING_CAPABILITY
                ),
            },
            "verification": {
                "declared": request.capability.model_dump(mode="json"),
                "selected": negotiated_capabilities.get(
                    EXECUTION_VERIFICATION_CAPABILITY
                ),
            },
        },
        "procedure": {
            "mapping_profile": (
                mapping_result.request.profile_procedure_uri
            ),
            "mapping_adapter": mapping_result.procedure_uri,
            "verification_profile": request.profile_procedure_uri,
            "verification_adapter": request.adapter_procedure_uri,
        },
        "environment": request.environment.model_dump(mode="json"),
        "check": request.check.model_dump(mode="json"),
        "input": [
            item.model_dump(mode="json") for item in request.inputs
        ],
        "expected-output": [
            item.model_dump(mode="json")
            for item in request.expected_outputs
        ],
        "result": {
            "status": result.status,
            "outcome": result.outcome,
            "executed_at": result.executed_at,
        },
    }
    members = [
        _projection_member(
            "execution_coordinate",
            name,
            value,
        )
        for name, value in values.items()
    ]
    return _projection(
        ExecutionEvidenceProjection,
        "execution_evidence_projection",
        EXECUTION_PROJECTION_PROCEDURE_URI,
        members,
    )


def _derive_trace(
    bundle: OnboardingBundle,
    inventory: InventorySnapshot,
    mapping_result: ImplementationMappingResult,
) -> EvidenceTraceCoordinates:
    behavior_digest = _digest_bytes(
        canonical_ir_json(bundle.behavior).encode("ascii")
    )
    inventory_digest = _digest_bytes(canonical_inventory_json(inventory))
    return EvidenceTraceCoordinates(
        kind="evidence_trace_coordinates",
        behavior=BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id=bundle.behavior.document_id,
            ir_version=bundle.behavior.ir_version,
            canonical_digest=behavior_digest,
        ),
        onboarding=OnboardingBundleRef(
            kind="onboarding_bundle_ref",
            schema_uri=bundle.schema_uri,
            schema_version=bundle.onboarding_version,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        inventory=InventorySnapshotRef(
            kind="inventory_snapshot_ref",
            schema_uri=INVENTORY_SCHEMA_URI,
            schema_version=INVENTORY_VERSION,
            subject_uri=inventory.subject_uri,
            source_revision=inventory.source_revision,
            canonical_digest=inventory_digest,
        ),
        mapping=_mapping_ref(mapping_result),
    )


def _mapping_ref(
    mapping_result: ImplementationMappingResult,
) -> ImplementationMappingResultRef:
    return ImplementationMappingResultRef(
        kind="implementation_mapping_result_ref",
        schema_uri=mapping_result.schema_uri,
        schema_version=mapping_result.implementation_evidence_version,
        target_id=mapping_result.id,
        canonical_digest=canonical_implementation_evidence_digest(
            mapping_result
        ),
    )


def _verification_result_ref(
    result: ExecutionVerificationResult,
) -> ExecutionVerificationResultRef:
    return ExecutionVerificationResultRef(
        kind="execution_verification_result_ref",
        schema_uri=result.schema_uri,
        schema_version=result.implementation_evidence_version,
        target_id=result.id,
        canonical_digest=canonical_implementation_evidence_digest(result),
    )


def _validate_current_context(
    *,
    result: ExecutionVerificationResult,
    request: ExecutionVerificationRequest,
    mapping_result: ImplementationMappingResult,
    bundle: OnboardingBundle,
    inventory: InventorySnapshot,
    mapping_adapter: Producer,
    verification_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> None:
    validate_implementation_mapping_result(
        mapping_result,
        request=mapping_result.request,
        bundle=bundle,
        current_inventory=inventory,
        initialized_adapter=mapping_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    validate_execution_verification_result(
        result,
        request=request,
        mapping_result=mapping_result,
        bundle=bundle,
        current_inventory=inventory,
        mapping_initialized_adapter=mapping_adapter,
        initialized_adapter=verification_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    try:
        Producer.model_validate_json(
            json.dumps(
                verification_adapter.model_dump(
                    mode="json",
                    warnings=False,
                ),
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            )
        )
    except (AttributeError, TypeError, ValueError, ValidationError) as error:
        _fail(
            EvidenceStatusErrorCode.INVALID_STRUCTURE,
            "current verification adapter is structurally invalid",
            location="$.current.verification_adapter",
        )
        raise AssertionError("unreachable") from error


def _validate_envelope_context(
    actual: VerificationEvidenceEnvelope,
    expected: VerificationEvidenceEnvelope,
) -> None:
    if actual.verification_result != expected.verification_result:
        _fail(
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
            "envelope verification result reference differs from context",
            location="$.verification_result",
        )
    if actual.trace.mapping != expected.trace.mapping:
        _fail(
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
            "envelope mapping reference differs from context",
            location="$.trace.mapping",
        )
    if actual.claim != expected.claim:
        _fail(
            EvidenceStatusErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "envelope tested claim reference differs from context",
            location="$.claim",
        )
    if actual.subject != expected.subject:
        _fail(
            EvidenceStatusErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "envelope subject differs from context",
            location="$.subject",
        )
    if actual.recorded != expected.recorded:
        _fail(
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
            "envelope selective projections differ from context",
            location="$.recorded",
        )
    if actual.trace != expected.trace:
        _fail(
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
            "envelope trace differs from context",
            location="$.trace",
        )


def _compare_coordinates(
    recorded: RecordedEvidenceCoordinates,
    current: CurrentEvidenceCoordinates,
) -> tuple[EvidenceStatusReason, ...]:
    reasons = []
    if recorded.behavior.digest != current.behavior.digest:
        reasons.append(
            _reason(
                EvidenceStatusReasonCode.BEHAVIOR_SUBJECT_CHANGED,
                recorded.behavior.digest,
                current.behavior.digest,
            )
        )
    if recorded.mapping.digest != current.mapping.digest:
        reasons.append(
            _reason(
                EvidenceStatusReasonCode.MAPPING_BINDING_CHANGED,
                recorded.mapping.digest,
                current.mapping.digest,
            )
        )
    if recorded.source.digest != current.source.digest:
        reasons.append(
            _reason(
                EvidenceStatusReasonCode.SOURCE_BINDING_CHANGED,
                recorded.source.digest,
                current.source.digest,
            )
        )
    recorded_execution = {
        member.target_id: member
        for member in recorded.execution.members
    }
    current_execution = {
        member.target_id: member
        for member in current.execution.members
    }
    reason_by_member = {
        "inventory-adapter": (
            EvidenceStatusReasonCode.INVENTORY_ADAPTER_CHANGED
        ),
        "mapping-adapter": (
            EvidenceStatusReasonCode.MAPPING_ADAPTER_CHANGED
        ),
        "verification-adapter": (
            EvidenceStatusReasonCode.VERIFICATION_ADAPTER_CHANGED
        ),
        "procedure": EvidenceStatusReasonCode.PROCEDURE_CHANGED,
        "result": EvidenceStatusReasonCode.RESULT_CHANGED,
        "environment": EvidenceStatusReasonCode.ENVIRONMENT_CHANGED,
        "check": EvidenceStatusReasonCode.CHECK_CHANGED,
        "input": EvidenceStatusReasonCode.INPUT_CHANGED,
        "expected-output": (
            EvidenceStatusReasonCode.EXPECTED_OUTPUT_CHANGED
        ),
    }
    for member_id, code in reason_by_member.items():
        before = recorded_execution[member_id].digest
        after = current_execution[member_id].digest
        if before != after:
            reasons.append(_reason(code, before, after))
    return tuple(sorted(reasons, key=lambda item: item.code.value))


def _assessment(
    envelope: VerificationEvidenceEnvelope,
    *,
    status: EvidenceStatus,
    current: CurrentEvidenceCoordinates | None,
    reasons: tuple[EvidenceStatusReason, ...],
) -> VerificationEvidenceAssessment:
    payload = {
        "kind": "verification_evidence_assessment",
        "evidence_status_version": EVIDENCE_STATUS_VERSION,
        "schema_uri": VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI,
        "id": f"assessment.{'0' * 64}",
        "procedure_uri": EVIDENCE_ASSESS_PROCEDURE_URI,
        "envelope": VerificationEvidenceEnvelopeRef(
            kind="verification_evidence_envelope_ref",
            schema_uri=VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
            schema_version=EVIDENCE_STATUS_VERSION,
            target_id=envelope.id,
            canonical_digest=canonical_evidence_status_digest(envelope),
        ).model_dump(mode="json"),
        "status": status.value,
        "current": (
            None if current is None else current.model_dump(mode="json")
        ),
        "reasons": tuple(
            reason.model_dump(mode="json") for reason in reasons
        ),
    }
    return _identified_model(
        VerificationEvidenceAssessment,
        "assessment",
        payload,
    )


def _projection(
    model_type,
    kind: str,
    procedure_uri: str,
    members,
):
    ordered = tuple(
        sorted(
            members,
            key=lambda item: (item.target_kind, item.target_id),
        )
    )
    payload = {
        "kind": kind,
        "procedure_uri": procedure_uri,
        "members": tuple(
            member.model_dump(mode="json") for member in ordered
        ),
    }
    payload["digest"] = _digest(payload).model_dump(mode="json")
    return model_type.model_validate_json(_canonical_bytes(payload))


def _projection_member(
    target_kind: str,
    target_id: str,
    value: object,
) -> EvidenceProjectionMember:
    return EvidenceProjectionMember(
        kind="evidence_projection_member",
        target_kind=target_kind,
        target_id=target_id,
        digest=_digest(value),
    )


def _inventory_references(value: object) -> tuple[InventoryRecordRef, ...]:
    found = []

    def visit(item: object) -> None:
        if isinstance(item, InventoryRecordRef):
            found.append(item)
            return
        if isinstance(item, BaseModel):
            for name in type(item).model_fields:
                visit(getattr(item, name))
            return
        if isinstance(item, (tuple, list)):
            for nested in item:
                visit(nested)

    visit(value)
    return tuple(found)


def _subject_binding(
    mapping_result: ImplementationMappingResult,
    subject: BehaviorSubjectKey,
):
    binding = next(
        (
            item
            for item in mapping_result.bindings
            if item.behavior.target_kind is subject.target_kind
            and item.behavior.target_id == subject.target_id
        ),
        None,
    )
    if binding is None:
        _fail(
            EvidenceStatusErrorCode.BROKEN_REFERENCE,
            "evidence subject has no implementation binding",
            location="$.mapping",
        )
    return binding


def _reason(
    code: EvidenceStatusReasonCode,
    recorded: Digest,
    current: Digest,
) -> EvidenceStatusReason:
    return EvidenceStatusReason(
        kind="evidence_status_reason",
        code=code,
        recorded=recorded,
        current=current,
    )


def _identified_model(model_type, prefix: str, payload):
    identity = {
        key: value for key, value in payload.items() if key != "id"
    }
    payload["id"] = (
        f"{prefix}."
        + hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    )
    return model_type.model_validate_json(_canonical_bytes(payload))


def _revalidate_status_model(value, model_type, *, label: str):
    if type(value) is not model_type:
        _fail(
            EvidenceStatusErrorCode.INVALID_STRUCTURE,
            f"{label} must use its exact declared type",
            location="$",
        )
    try:
        return model_type.model_validate_json(
            canonical_evidence_status_json(value)
        )
    except (AttributeError, TypeError, ValueError, ValidationError) as error:
        _fail(
            EvidenceStatusErrorCode.INVALID_STRUCTURE,
            f"{label} is structurally invalid",
            location="$",
        )
        raise AssertionError("unreachable") from error


def _digest(value: object) -> Digest:
    return _digest_bytes(_canonical_bytes(value))


def _digest_bytes(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _fail(
    code: EvidenceStatusErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise EvidenceStatusValidationError(
        code,
        message,
        location=location,
    )
