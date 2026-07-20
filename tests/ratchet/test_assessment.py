from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from tests.onboarding.test_decisions import _decisions
from ucf.ir.models import Digest, EntityKind, Producer
from ucf.onboarding import CaptureContext, build_onboarding_bundle
from ucf.ratchet import (
    OBSERVED_FINGERPRINT_ALGORITHM_URI,
    SEMANTIC_FINGERPRINT_ALGORITHM_URI,
    BehaviorSubjectKey,
    RatchetErrorCode,
    RatchetValidationError,
    ViolationInput,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_assessment_id,
    parse_ratchet_assessment_json,
    validate_ratchet_assessment,
)

from .test_policy import _policy


def _capture_context() -> CaptureContext:
    return CaptureContext(
        kind="capture_context",
        captured_at="2026-07-19T13:00:00Z",
        environment=Digest(
            kind="digest",
            algorithm="sha-256",
            value="c" * 64,
        ),
    )


def _assessment(*, violations: bool = True):
    policy = _policy()
    bundle = _bundle()
    inputs = ()
    if violations:
        inputs = (
            ViolationInput(
                kind="ratchet_violation_input",
                rule_id=policy.rules[0].id,
                subject=BehaviorSubjectKey(
                    kind="behavior_subject_key",
                    subject_uri=bundle.inventory.subject_uri,
                    target_kind=EntityKind.USE_CASE,
                    target_id="use-case.quote-order",
                ),
                slot="required-check",
                message="No current tested claim is attached.",
            ),
        )
    assessment = build_ratchet_assessment(
        policy,
        bundle,
        producer=Producer(
            kind="producer",
            name="org.ucf.fixture-assessor",
            version="1.0.0",
        ),
        procedure_uri="urn:ucf:ratchet-assessment:fixture:1.0.0",
        capture_context=_capture_context(),
        violations=inputs,
    )
    return policy, bundle, assessment


def _partial_bundle():
    bundle = _bundle()
    discovery = bundle.discovery.model_copy(
        update={
            "coverage": bundle.discovery.coverage.model_copy(
                update={
                    "status": "partial",
                    "uncovered_subjects": (
                        bundle.discovery.coverage.eligible_subjects
                    ),
                }
            ),
            "candidates": (),
        }
    )
    return build_onboarding_bundle(
        bundle.inventory,
        discovery,
        _decisions(discovery),
    )


def test_assessment_derives_scoped_subjects_and_exact_trace() -> None:
    policy, bundle, assessment = _assessment()

    validate_ratchet_assessment(policy, bundle, assessment)
    assert [subject.key.target_id for subject in assessment.subjects] == [
        "use-case.quote-order",
        "use-case.render-receipt",
    ]
    assert {
        subject.key.subject_uri for subject in assessment.subjects
    } == {bundle.inventory.subject_uri}
    assert {
        subject.semantic.algorithm_uri for subject in assessment.subjects
    } == {SEMANTIC_FINGERPRINT_ALGORITHM_URI}
    assert {
        subject.observed.algorithm_uri for subject in assessment.subjects
    } == {OBSERVED_FINGERPRINT_ALGORITHM_URI}
    assert all(
        subject.trace.behavior.target_id == subject.key.target_id
        for subject in assessment.subjects
    )
    assert len(assessment.violations) == 1
    assert assessment.violations[0].key.slot == "required-check"
    assert assessment.coverage[0].status == "complete"
    assert len(assessment.coverage[0].subjects) == len(assessment.subjects)


def test_assessment_round_trip_is_deterministic_and_contextually_valid() -> None:
    policy, bundle, first = _assessment()
    _, _, second = _assessment()
    encoded = canonical_ratchet_json(first)

    assert first == second
    assert canonical_ratchet_json(second) == encoded
    parsed = parse_ratchet_assessment_json(encoded)
    assert parsed == first
    validate_ratchet_assessment(policy, bundle, parsed)


def test_assessment_cannot_escalate_partial_discovery_coverage() -> None:
    policy = _policy()
    bundle = _partial_bundle()
    assessment = build_ratchet_assessment(
        policy,
        bundle,
        producer=_assessment()[2].producer,
        procedure_uri="urn:ucf:ratchet-assessment:fixture:1.0.0",
        capture_context=_capture_context(),
    )
    forged = assessment.model_copy(
        update={"subject_coverage": "complete"}
    )
    forged = forged.model_copy(
        update={"id": derive_assessment_id(forged)}
    )

    assert assessment.subject_coverage == "partial"
    with pytest.raises(RatchetValidationError) as captured:
        validate_ratchet_assessment(policy, bundle, forged)

    assert captured.value.code is RatchetErrorCode.SUMMARY_MISMATCH
    assert captured.value.location == "$.subject_coverage"


@pytest.mark.parametrize("mutation", ["semantic", "observed", "source"])
def test_assessment_rejects_forged_bundle_projection(mutation: str) -> None:
    policy, bundle, assessment = _assessment()
    if mutation == "source":
        source = assessment.source.model_copy(
            update={
                "canonical_digest": assessment.source.canonical_digest.model_copy(
                    update={"value": "f" * 64}
                )
            }
        )
        forged = assessment.model_copy(update={"source": source})
        location = "$.source"
    else:
        subjects = list(assessment.subjects)
        fingerprint = getattr(subjects[0], mutation)
        subjects[0] = subjects[0].model_copy(
            update={
                mutation: fingerprint.model_copy(
                    update={
                        "digest": fingerprint.digest.model_copy(
                            update={"value": "f" * 64}
                        )
                    }
                )
            }
        )
        forged = assessment.model_copy(update={"subjects": tuple(subjects)})
        location = "$.subjects"
    forged = forged.model_copy(
        update={"id": derive_assessment_id(forged)}
    )

    with pytest.raises(RatchetValidationError) as captured:
        validate_ratchet_assessment(policy, bundle, forged)

    assert captured.value.code is (
        RatchetErrorCode.DOCUMENT_IDENTITY_MISMATCH
    )
    assert captured.value.location == location
