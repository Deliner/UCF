from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from ucf.evidence_status import (
    EvidenceStatusErrorCode,
    EvidenceStatusValidationError,
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
    assess_verification_evidence,
    canonical_evidence_status_json,
    parse_verification_evidence_assessment_json,
    parse_verification_evidence_envelope_json,
    validate_verification_evidence_assessment,
)

from ._fixture_factory import (
    DEFAULT_OUTPUT_DIRECTORY,
    generated_fixtures,
    main,
)
from ._support import (
    EvidenceContext,
    baseline_context,
    changed_environment_context,
    current_assessment_arguments,
    inventory_adapter_context,
    reason_codes,
    recorded_assessment_arguments,
    status_value,
    target_behavior_context,
    target_source_context,
    unrelated_behavior_context,
    unrelated_inventory_context,
)

_POSITIVE_ASSESSMENTS = {
    "assessment-fresh.json": ("fresh", ()),
    "assessment-indeterminate.json": (
        "indeterminate",
        ("current_context_unavailable",),
    ),
    "assessment-unrelated-inventory-fresh.json": ("fresh", ()),
    "assessment-unrelated-behavior-fresh.json": ("fresh", ()),
    "assessment-stale-target-behavior.json": (
        "stale",
        ("behavior_subject_changed",),
    ),
    "assessment-stale-target-source-mapping.json": (
        "stale",
        ("mapping_binding_changed", "source_binding_changed"),
    ),
    "assessment-stale-environment.json": (
        "stale",
        ("environment_changed",),
    ),
    "assessment-stale-inventory-adapter.json": (
        "stale",
        (
            "inventory_adapter_changed",
            "mapping_binding_changed",
            "source_binding_changed",
        ),
    ),
    "assessment-stale-failed-result.json": (
        "stale",
        ("result_changed",),
    ),
    "refreshed-assessment-fresh.json": ("fresh", ()),
}


def test_positive_wire_fixtures_are_canonical_real_engine_documents() -> None:
    envelope = _parse_envelope("envelope.json")
    refreshed_envelope = _parse_envelope("refreshed-envelope.json")

    assert _fixture_bytes("positive/envelope.json") == canonical_evidence_status_json(
        envelope
    )
    assert _fixture_bytes(
        "positive/refreshed-envelope.json"
    ) == canonical_evidence_status_json(refreshed_envelope)

    for name, (expected_status, expected_reasons) in _POSITIVE_ASSESSMENTS.items():
        assessment = _parse_assessment(name)
        assert _fixture_bytes(f"positive/{name}") == canonical_evidence_status_json(
            assessment
        )
        assert status_value(assessment.status) == expected_status
        assert reason_codes(assessment) == expected_reasons


def test_positive_wire_assessments_match_their_exact_contexts() -> None:
    recorded = baseline_context()
    envelope = _parse_envelope("envelope.json")
    cases = (
        ("assessment-fresh.json", recorded),
        ("assessment-indeterminate.json", None),
        (
            "assessment-unrelated-inventory-fresh.json",
            unrelated_inventory_context(),
        ),
        (
            "assessment-unrelated-behavior-fresh.json",
            unrelated_behavior_context(),
        ),
        (
            "assessment-stale-target-behavior.json",
            target_behavior_context(),
        ),
        (
            "assessment-stale-target-source-mapping.json",
            target_source_context(),
        ),
        (
            "assessment-stale-environment.json",
            changed_environment_context(),
        ),
        (
            "assessment-stale-inventory-adapter.json",
            inventory_adapter_context(),
        ),
        (
            "assessment-stale-failed-result.json",
            baseline_context("failed"),
        ),
    )

    for name, current in cases:
        _validate_assessment(
            _parse_assessment(name),
            envelope,
            recorded,
            current,
        )

    refreshed_context = target_behavior_context()
    _validate_assessment(
        _parse_assessment("refreshed-assessment-fresh.json"),
        _parse_envelope("refreshed-envelope.json"),
        refreshed_context,
        refreshed_context,
    )


def test_positive_wire_fixtures_make_no_verified_claim() -> None:
    for relative_path in generated_fixtures():
        if relative_path.parts[0] == "positive":
            assert b'"verified"' not in _fixture_bytes(str(relative_path))


@pytest.mark.parametrize(
    ("name", "parser"),
    [
        (
            "duplicate-json-member-envelope.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "duplicate-json-member-assessment.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "unknown-envelope-root-field.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "unknown-envelope-nested-field.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "unknown-assessment-root-field.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "unknown-assessment-nested-field.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "unsupported-envelope-version.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "wrong-envelope-schema-uri.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "unsupported-result-ref-version.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "wrong-mapping-ref-schema-uri.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "unsupported-assessment-version.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "wrong-assessment-schema-uri.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "unsupported-envelope-ref-version.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "wrong-envelope-ref-schema-uri.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "duplicate-projection-member.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "noncanonical-projection-member-order.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "projection-digest-mismatch.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "envelope-id-mismatch.json",
            parse_verification_evidence_envelope_json,
        ),
        (
            "assessment-id-mismatch.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "duplicate-reason.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "noncanonical-reason-order.json",
            parse_verification_evidence_assessment_json,
        ),
        (
            "reason-shape.json",
            parse_verification_evidence_assessment_json,
        ),
    ],
)
def test_structural_negative_wire_fixtures_are_rejected(
    name: str,
    parser: Callable[[bytes], object],
) -> None:
    with pytest.raises(ValueError):
        parser(_fixture_bytes(f"invalid/{name}"))


@pytest.mark.parametrize(
    ("name", "expected_code"),
    [
        (
            "forged-result-ref.json",
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
        (
            "forged-mapping-ref.json",
            EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
        (
            "forged-claim-ref.json",
            EvidenceStatusErrorCode.DOCUMENT_IDENTITY_MISMATCH,
        ),
    ],
)
def test_contextual_envelope_negatives_are_parseable_but_rejected(
    name: str,
    expected_code: EvidenceStatusErrorCode,
) -> None:
    context = baseline_context()
    envelope = parse_verification_evidence_envelope_json(
        _fixture_bytes(f"invalid-context/{name}")
    )

    with pytest.raises(EvidenceStatusValidationError) as captured:
        assess_verification_evidence(
            envelope,
            **recorded_assessment_arguments(context),
            **current_assessment_arguments(context),
        )

    assert captured.value.code is expected_code


@pytest.mark.parametrize(
    ("name", "current"),
    [
        (
            "forged-assessment-envelope-ref.json",
            baseline_context(),
        ),
        (
            "replayed-fresh-target-source.json",
            target_source_context(),
        ),
    ],
)
def test_contextual_assessment_negatives_are_parseable_but_rejected(
    name: str,
    current: EvidenceContext,
) -> None:
    recorded = baseline_context()
    envelope = _parse_envelope("envelope.json")
    assessment = parse_verification_evidence_assessment_json(
        _fixture_bytes(f"invalid-context/{name}")
    )

    with pytest.raises(EvidenceStatusValidationError) as captured:
        validate_verification_evidence_assessment(
            assessment,
            envelope,
            **recorded_assessment_arguments(recorded),
            **current_assessment_arguments(current),
        )

    assert captured.value.code is (EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH)


def test_wire_fixture_tree_is_exact_fresh_and_symlink_free() -> None:
    expected = {
        DEFAULT_OUTPUT_DIRECTORY / path: content
        for path, content in generated_fixtures().items()
    }
    actual = {
        path
        for path in DEFAULT_OUTPUT_DIRECTORY.rglob("*")
        if path.is_file() or path.is_symlink()
    }

    assert actual == set(expected)
    for path, content in expected.items():
        assert not path.is_symlink()
        assert path.read_bytes() == content


def test_fixture_generation_is_byte_deterministic() -> None:
    first = generated_fixtures()
    second = generated_fixtures()

    assert first == second
    assert all(content.endswith(b"\n") for content in first.values())


def test_fixture_check_accepts_exact_tree_and_rejects_extra_file(
    tmp_path: Path,
) -> None:
    assert main(["--output-directory", str(tmp_path)]) == 0
    assert (
        main(
            [
                "--output-directory",
                str(tmp_path),
                "--check",
            ]
        )
        == 0
    )
    (tmp_path / "extra.json").write_text("{}\n", encoding="utf-8")

    assert (
        main(
            [
                "--output-directory",
                str(tmp_path),
                "--check",
            ]
        )
        == 1
    )


def _fixture_bytes(relative_path: str) -> bytes:
    return (DEFAULT_OUTPUT_DIRECTORY / relative_path).read_bytes()


def _parse_envelope(name: str) -> VerificationEvidenceEnvelope:
    return parse_verification_evidence_envelope_json(_fixture_bytes(f"positive/{name}"))


def _parse_assessment(
    name: str,
) -> VerificationEvidenceAssessment:
    return parse_verification_evidence_assessment_json(
        _fixture_bytes(f"positive/{name}")
    )


def _validate_assessment(
    assessment: VerificationEvidenceAssessment,
    envelope: VerificationEvidenceEnvelope,
    recorded: EvidenceContext,
    current: EvidenceContext | None,
) -> None:
    current_arguments = {} if current is None else current_assessment_arguments(current)
    validated = validate_verification_evidence_assessment(
        assessment,
        envelope,
        **recorded_assessment_arguments(recorded),
        **current_arguments,
    )

    assert validated == assessment
    assert validated is not assessment
