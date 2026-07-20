from __future__ import annotations

import hashlib
import json

from ucf.ir import validate_trust_against_behavior
from ucf.ir.models import BehaviorIR
from ucf.ir.trust_models import (
    CURRENT_TRUST_IR_VERSION,
    ObservedFact,
    RecordRef,
    SourceRecord,
    TrustIR,
    TrustRecordKind,
)
from ucf.runtime_evidence.codec import canonical_runtime_evidence_digest
from ucf.runtime_evidence.errors import (
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceValidationError,
)
from ucf.runtime_evidence.models import (
    RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
    RuntimeEnvironment,
    RuntimeEvidenceAcceptedResult,
    RuntimeEvidenceResult,
)
from ucf.runtime_evidence.validation import (
    validate_runtime_evidence_request,
    validate_runtime_evidence_result_structure,
    validate_runtime_observation_refs,
)


def project_runtime_evidence_to_trust(
    result: RuntimeEvidenceResult,
    *,
    behavior: BehaviorIR,
    environment: RuntimeEnvironment,
) -> TrustIR:
    validate_runtime_evidence_result_structure(result)
    if not isinstance(result, RuntimeEvidenceAcceptedResult):
        raise RuntimeEvidenceValidationError(
            RuntimeEvidenceErrorCode.RESULT_STATUS_MISMATCH,
            "rejected runtime evidence cannot be projected",
            location="$.status",
        )
    validate_runtime_evidence_request(
        result.request,
        behavior=behavior,
        environment=environment,
    )
    validate_runtime_observation_refs(result)
    result_digest = canonical_runtime_evidence_digest(result)
    source_id = f"source.runtime-evidence.{result_digest.value}"
    source = SourceRecord(
        kind=TrustRecordKind.SOURCE_RECORD,
        id=source_id,
        source_uri=RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
        source_revision=result_digest,
        producer=result.producer,
        captured_at=result.request.source.captured_at,
    )
    rules = {rule.id: rule for rule in result.request.policy.rules}
    facts = tuple(
        _project_observation(
            result_digest=result_digest.value,
            source_id=source_id,
            rule=rules[observation.rule.target_id],
        )
        for observation in result.observations
    )
    trust = TrustIR(
        kind="trust_ir",
        trust_ir_version=CURRENT_TRUST_IR_VERSION,
        document_id=f"document.runtime-evidence.{result_digest.value}",
        subject_document=result.request.behavior,
        records=(source, *facts),
    )
    validate_trust_against_behavior(trust, behavior)
    return trust


def _project_observation(
    *,
    result_digest: str,
    source_id: str,
    rule,
) -> ObservedFact:
    identity = _digest_identity(
        {
            "result_revision": result_digest,
            "rule_id": rule.id,
        }
    )
    return ObservedFact(
        kind=TrustRecordKind.OBSERVED_FACT,
        id=f"observed.runtime-evidence.{identity}",
        subject=rule.subject,
        assertion=rule.assertion,
        trace=RecordRef(
            kind="record_ref",
            target_kind=TrustRecordKind.SOURCE_RECORD,
            target_id=source_id,
        ),
    )


def _digest_identity(value: object) -> str:
    encoded = (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
