from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from ucf.evidence_status.models import (
    EvidenceStatusDocument,
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
)
from ucf.ir import decode_strict_json_object
from ucf.ir.models import Digest


def canonical_evidence_status_json(
    document: EvidenceStatusDocument,
) -> bytes:
    if type(document) is VerificationEvidenceEnvelope:
        model_type = VerificationEvidenceEnvelope
    elif type(document) is VerificationEvidenceAssessment:
        model_type = VerificationEvidenceAssessment
    else:
        raise TypeError(
            "document must use an exact evidence-status document type"
        )
    _reject_unknown_model_state(document, path="$")
    validated = model_type.model_validate_json(
        json.dumps(
            document.model_dump(mode="json", warnings=False),
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    )
    return _canonical_bytes(validated.model_dump(mode="json"))


def parse_verification_evidence_envelope_json(
    payload: str | bytes,
) -> VerificationEvidenceEnvelope:
    return _parse(payload, VerificationEvidenceEnvelope)


def parse_verification_evidence_assessment_json(
    payload: str | bytes,
) -> VerificationEvidenceAssessment:
    return _parse(payload, VerificationEvidenceAssessment)


def canonical_evidence_status_digest(
    document: EvidenceStatusDocument,
) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_evidence_status_json(document)
        ).hexdigest(),
    )


def _parse(payload: str | bytes, model_type):
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model_type.model_validate_json(normalized)


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


def _reject_unknown_model_state(value: object, *, path: str) -> None:
    if isinstance(value, BaseModel):
        fields = type(value).model_fields
        unknown = set(value.__dict__) - set(fields)
        extras = getattr(value, "__pydantic_extra__", None)
        if extras:
            unknown.update(extras)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"{path} contains unknown field(s): {names}")
        for name in fields:
            if name in value.__dict__:
                _reject_unknown_model_state(
                    value.__dict__[name],
                    path=f"{path}.{name}",
                )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_unknown_model_state(item, path=f"{path}[{key!r}]")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_unknown_model_state(item, path=f"{path}[{index}]")
