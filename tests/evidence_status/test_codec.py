from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from ucf.evidence_status import (
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
    canonical_evidence_status_json,
    parse_verification_evidence_assessment_json,
    parse_verification_evidence_envelope_json,
)

from .test_contract import (
    _content_id,
    _digest,
    assessment,
    assessment_payload,
    envelope,
    envelope_payload,
)


def test_envelope_has_one_exact_canonical_round_trip() -> None:
    document = envelope()
    encoded = canonical_evidence_status_json(document)

    assert isinstance(document, VerificationEvidenceEnvelope)
    assert encoded.endswith(b"\n")
    assert parse_verification_evidence_envelope_json(encoded) == document
    assert (
        canonical_evidence_status_json(
            parse_verification_evidence_envelope_json(encoded)
        )
        == encoded
    )
    assert document.id == _content_id(
        "envelope",
        document.model_dump(mode="json"),
    )


def test_assessment_has_one_exact_canonical_round_trip() -> None:
    document = assessment()
    encoded = canonical_evidence_status_json(document)

    assert isinstance(document, VerificationEvidenceAssessment)
    assert encoded.endswith(b"\n")
    assert parse_verification_evidence_assessment_json(encoded) == document
    assert (
        canonical_evidence_status_json(
            parse_verification_evidence_assessment_json(encoded)
        )
        == encoded
    )
    assert document.id == _content_id(
        "assessment",
        document.model_dump(mode="json"),
    )


@pytest.mark.parametrize(
    ("document", "parser", "member"),
    [
        (
            envelope,
            parse_verification_evidence_envelope_json,
            b'"evidence_status_version":"1.0.0",',
        ),
        (
            assessment,
            parse_verification_evidence_assessment_json,
            b'"evidence_status_version":"1.0.0",',
        ),
    ],
)
def test_parsers_reject_duplicate_json_members(
    document,
    parser,
    member: bytes,
) -> None:
    encoded = canonical_evidence_status_json(document())
    duplicate = encoded.replace(member, member + member, 1)

    with pytest.raises(ValueError, match="duplicate"):
        parser(duplicate)


@pytest.mark.parametrize(
    ("document", "parser", "member"),
    [
        (
            envelope,
            parse_verification_evidence_envelope_json,
            b'"target_id":"action.quote-order",',
        ),
        (
            assessment,
            parse_verification_evidence_assessment_json,
            b'"code":"mapping_binding_changed",',
        ),
    ],
)
def test_parsers_reject_duplicate_nested_json_members(
    document,
    parser,
    member: bytes,
) -> None:
    encoded = canonical_evidence_status_json(document())
    assert member in encoded
    duplicate = encoded.replace(member, member + member, 1)

    with pytest.raises(ValueError, match="duplicate"):
        parser(duplicate)


def test_each_parser_rejects_the_other_document_kind() -> None:
    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(
            canonical_evidence_status_json(assessment())
        )
    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(
            canonical_evidence_status_json(envelope())
        )


@pytest.mark.parametrize(
    ("payload_factory", "parser", "prefix"),
    [
        (
            envelope_payload,
            parse_verification_evidence_envelope_json,
            "envelope",
        ),
        (
            assessment_payload,
            parse_verification_evidence_assessment_json,
            "assessment",
        ),
    ],
)
def test_parsers_reject_stale_content_identity(
    payload_factory,
    parser,
    prefix: str,
) -> None:
    payload = payload_factory()
    assert payload["id"] == _content_id(prefix, payload)
    payload["id"] = f"{prefix}.{'f' * 64}"

    with pytest.raises((ValidationError, ValueError)):
        parser(json.dumps(payload))


def test_trace_changes_have_distinct_envelope_identity_without_claiming_stale() -> None:
    first_payload = envelope_payload()
    second_payload = deepcopy(first_payload)
    second_payload["trace"]["behavior"]["canonical_digest"] = _digest("e")
    second_payload["id"] = _content_id("envelope", second_payload)

    first = parse_verification_evidence_envelope_json(json.dumps(first_payload))
    second = parse_verification_evidence_envelope_json(json.dumps(second_payload))

    assert first.id != second.id
    assert canonical_evidence_status_json(first) != (
        canonical_evidence_status_json(second)
    )
    assert first.recorded == second.recorded


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"[]",
        b"\xef\xbb\xbf{}",
        b'{"kind":NaN}',
        b"\xff",
    ),
)
def test_parsers_reject_non_profile_json(payload: bytes) -> None:
    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_envelope_json(payload)
    with pytest.raises((ValidationError, ValueError)):
        parse_verification_evidence_assessment_json(payload)
