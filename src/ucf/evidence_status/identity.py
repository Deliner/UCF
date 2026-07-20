from __future__ import annotations

import hashlib
import json

from ucf.evidence_status.models import (
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
)


def derive_verification_evidence_envelope_id(
    envelope: VerificationEvidenceEnvelope,
) -> str:
    return _derive("envelope", envelope)


def derive_verification_evidence_assessment_id(
    assessment: VerificationEvidenceAssessment,
) -> str:
    return _derive("assessment", assessment)


def _derive(prefix: str, document) -> str:
    encoded = (
        json.dumps(
            document.model_dump(mode="json", exclude={"id"}),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return f"{prefix}.{hashlib.sha256(encoded).hexdigest()}"
