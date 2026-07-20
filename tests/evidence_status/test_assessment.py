from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

import pytest

from ucf.evidence_status import (
    EvidenceStatus,
    EvidenceStatusErrorCode,
    EvidenceStatusValidationError,
    VerificationEvidenceEnvelope,
    assess_verification_evidence,
    canonical_evidence_status_json,
    record_verification_evidence,
    validate_verification_evidence_assessment,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    derive_execution_verification_result_id,
    derive_implementation_mapping_result_id,
)
from ucf.inventory import canonical_inventory_json
from ucf.ir import canonical_ir_json
from ucf.ir.models import Digest, Producer

from ._support import (
    EvidenceContext,
    baseline_context,
    changed_capability_context,
    changed_check_context,
    changed_environment_context,
    changed_expected_output_context,
    changed_input_context,
    current_assessment_arguments,
    inventory_adapter_context,
    mapping_adapter_context,
    mapping_procedure_context,
    reason_codes,
    record_arguments,
    recorded_assessment_arguments,
    status_value,
    target_behavior_context,
    target_source_context,
    unrelated_behavior_context,
    unrelated_inventory_context,
    verification_adapter_context,
    verification_procedure_context,
)


def test_unchanged_complete_context_is_fresh() -> None:
    recorded = baseline_context()

    assessment = _assess(recorded, recorded)

    assert status_value(assessment.status) == "fresh"
    assert assessment.current is not None
    assert reason_codes(assessment) == ()


@pytest.mark.parametrize(
    "current_factory",
    [
        unrelated_inventory_context,
        unrelated_behavior_context,
    ],
    ids=["unrelated-inventory", "unrelated-behavior-materialization"],
)
def test_unrelated_valid_changes_remain_fresh_despite_whole_document_drift(
    current_factory: Callable[[], EvidenceContext],
) -> None:
    recorded = baseline_context()
    current = current_factory()

    assert canonical_ir_json(current.bundle.behavior) != canonical_ir_json(
        recorded.bundle.behavior
    )
    if current_factory is unrelated_inventory_context:
        assert canonical_inventory_json(
            current.bundle.inventory
        ) != canonical_inventory_json(recorded.bundle.inventory)

    assessment = _assess(recorded, current)

    assert status_value(assessment.status) == "fresh"
    assert reason_codes(assessment) == ()


def test_target_source_change_invalidates_only_source_and_mapping() -> None:
    recorded = baseline_context()
    current = target_source_context()

    assessment = _assess(recorded, current)

    assert status_value(assessment.status) == "stale"
    assert reason_codes(assessment) == (
        "mapping_binding_changed",
        "source_binding_changed",
    )


def test_target_behavior_closure_change_invalidates_only_behavior() -> None:
    recorded = baseline_context()
    current = target_behavior_context()

    assessment = _assess(recorded, current)

    assert status_value(assessment.status) == "stale"
    assert reason_codes(assessment) == ("behavior_subject_changed",)


@pytest.mark.parametrize(
    ("current_factory", "expected_reason"),
    [
        (mapping_adapter_context, "mapping_adapter_changed"),
        (mapping_procedure_context, "procedure_changed"),
        (
            verification_adapter_context,
            "verification_adapter_changed",
        ),
        (verification_procedure_context, "procedure_changed"),
        (changed_environment_context, "environment_changed"),
        (changed_check_context, "check_changed"),
        (changed_input_context, "input_changed"),
        (
            changed_expected_output_context,
            "expected_output_changed",
        ),
    ],
        ids=[
            "mapping-adapter",
            "mapping-procedure",
            "verification-adapter",
            "verification-procedure",
        "environment",
        "check",
        "input",
        "expected-output",
    ],
)
def test_exact_execution_or_mapping_coordinate_change_has_one_reason(
    current_factory: Callable[[], EvidenceContext],
    expected_reason: str,
) -> None:
    recorded = baseline_context()

    assessment = _assess(recorded, current_factory())

    assert status_value(assessment.status) == "stale"
    assert reason_codes(assessment) == (expected_reason,)


def test_inventory_adapter_change_invalidates_exact_dependent_coordinates() -> None:
    recorded = baseline_context()

    assessment = _assess(recorded, inventory_adapter_context())

    assert status_value(assessment.status) == "stale"
    assert reason_codes(assessment) == (
        "inventory_adapter_changed",
        "mapping_binding_changed",
        "source_binding_changed",
    )


@pytest.mark.parametrize("outcome", ["failed", "error"])
def test_current_nonpassing_result_invalidates_previous_pass(
    outcome: str,
) -> None:
    recorded = baseline_context()
    current = baseline_context(outcome)

    assessment = _assess(recorded, current)

    assert status_value(assessment.status) == "stale"
    assert reason_codes(assessment) == ("result_changed",)
    assert b'"verified"' not in canonical_evidence_status_json(assessment)


@pytest.mark.parametrize(
    ("capability", "selected_version"),
    [
        (IMPLEMENTATION_MAPPING_CAPABILITY, None),
        (IMPLEMENTATION_MAPPING_CAPABILITY, "2.0.0"),
        (EXECUTION_VERIFICATION_CAPABILITY, None),
        (EXECUTION_VERIFICATION_CAPABILITY, "2.0.0"),
    ],
)
def test_current_context_rejects_unselected_or_unsupported_capability(
    capability: str,
    selected_version: str | None,
) -> None:
    recorded = baseline_context()
    current = changed_capability_context(capability)
    capabilities = dict(current.negotiated_capabilities)
    if selected_version is None:
        del capabilities[capability]
    else:
        capabilities[capability] = selected_version
    arguments = current_assessment_arguments(current)
    arguments["current_negotiated_capabilities"] = capabilities

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        assess_verification_evidence(
            _record(recorded),
            **recorded_assessment_arguments(recorded),
            **arguments,
        )

    assert captured.value.code is (
        ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH
    )


def test_current_result_must_match_exact_current_request_and_context() -> None:
    recorded = baseline_context()
    current = current_assessment_arguments(recorded)
    current["current_result"] = mapping_procedure_context().result

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        assess_verification_evidence(
            _record(recorded),
            **recorded_assessment_arguments(recorded),
            **current,
        )

    assert captured.value.code is (
        ImplementationEvidenceErrorCode.REQUEST_IDENTITY_MISMATCH
    )


def test_context_validator_accepts_exact_recomputed_assessment() -> None:
    context = baseline_context()
    envelope = _record(context)
    assessment = assess_verification_evidence(
        envelope,
        **recorded_assessment_arguments(context),
        **current_assessment_arguments(context),
    )

    validated = validate_verification_evidence_assessment(
        assessment,
        envelope,
        **recorded_assessment_arguments(context),
        **current_assessment_arguments(context),
    )

    assert validated == assessment
    assert validated is not assessment


def test_context_validator_normalizes_known_fields_and_rejects_hidden_fields() -> None:
    context = baseline_context()
    envelope = _record(context)
    assessment = _assess(context, context)
    bypassed_enum = assessment.model_copy(update={"status": "fresh"})
    hidden = assessment.model_copy(update={"transport": "http"})

    validated = validate_verification_evidence_assessment(
        bypassed_enum,
        envelope,
        **recorded_assessment_arguments(context),
        **current_assessment_arguments(context),
    )

    assert validated.status is EvidenceStatus.FRESH
    assert validated is not bypassed_enum
    with pytest.raises(EvidenceStatusValidationError) as captured:
        validate_verification_evidence_assessment(
            hidden,
            envelope,
            **recorded_assessment_arguments(context),
            **current_assessment_arguments(context),
        )
    assert captured.value.code is EvidenceStatusErrorCode.INVALID_STRUCTURE


def test_context_validator_rejects_forged_assessment_envelope_reference() -> None:
    context = baseline_context()
    envelope = _record(context)
    assessment = _assess(context, context)
    forged = assessment.model_copy(
        update={
            "envelope": assessment.envelope.model_copy(
                update={
                    "target_id": f"envelope.{'f' * 64}",
                    "canonical_digest": _filled_digest("f"),
                }
            )
        }
    )
    forged = _reidentify_assessment(forged)

    with pytest.raises(EvidenceStatusValidationError) as captured:
        validate_verification_evidence_assessment(
            forged,
            envelope,
            **recorded_assessment_arguments(context),
            **current_assessment_arguments(context),
        )

    assert captured.value.code is (
        EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH
    )


def test_context_validator_rejects_replayed_fresh_after_source_drift() -> None:
    recorded = baseline_context()
    current = target_source_context()
    envelope = _record(recorded)
    historical_fresh = _assess(recorded, recorded)

    with pytest.raises(EvidenceStatusValidationError) as captured:
        validate_verification_evidence_assessment(
            historical_fresh,
            envelope,
            **recorded_assessment_arguments(recorded),
            **current_assessment_arguments(current),
        )

    assert captured.value.code is (
        EvidenceStatusErrorCode.CONTENT_IDENTITY_MISMATCH
    )


def test_absent_current_context_is_explicitly_indeterminate() -> None:
    recorded = baseline_context()
    envelope = _record(recorded)

    assessment = assess_verification_evidence(
        envelope,
        **recorded_assessment_arguments(recorded),
    )

    assert status_value(assessment.status) == "indeterminate"
    assert assessment.current is None
    assert reason_codes(assessment) == ("current_context_unavailable",)


@pytest.mark.parametrize(
    "missing",
    tuple(current_assessment_arguments(baseline_context())),
)
def test_partial_current_context_is_a_typed_error(missing: str) -> None:
    recorded = baseline_context()
    current = current_assessment_arguments(recorded)
    current[missing] = None

    with pytest.raises(EvidenceStatusValidationError) as captured:
        assess_verification_evidence(
            _record(recorded),
            **recorded_assessment_arguments(recorded),
            **current,
        )

    assert captured.value.code is (EvidenceStatusErrorCode.CURRENT_CONTEXT_INCOMPLETE)
    assert captured.value.code.value == "current_context_incomplete"


@pytest.mark.parametrize("outcome", ["failed", "error"])
def test_nonpassing_result_cannot_be_recorded(outcome: str) -> None:
    context = baseline_context(outcome)

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _record(context)

    assert captured.value.code is (ImplementationEvidenceErrorCode.EVIDENCE_NOT_PASSED)
    assert captured.value.location == "$.outcome"


def test_refresh_requires_new_passed_result_and_produces_fresh_envelope() -> None:
    recorded = baseline_context()
    current = target_behavior_context()
    old_envelope = _record(recorded)

    stale = assess_verification_evidence(
        old_envelope,
        **recorded_assessment_arguments(recorded),
        **current_assessment_arguments(current),
    )
    refreshed_envelope = _record(current)
    refreshed = assess_verification_evidence(
        refreshed_envelope,
        **recorded_assessment_arguments(current),
        **current_assessment_arguments(current),
    )

    assert status_value(stale.status) == "stale"
    assert refreshed_envelope.id != old_envelope.id
    assert refreshed_envelope.verification_result.target_id == (current.result.id)
    assert status_value(refreshed.status) == "fresh"
    assert reason_codes(refreshed) == ()
    assert b'"verified"' not in canonical_evidence_status_json(refreshed_envelope)
    assert b'"verified"' not in canonical_evidence_status_json(refreshed)


@pytest.mark.parametrize("mutation", ["result", "mapping"])
def test_recorder_revalidates_context_forged_inputs(
    mutation: str,
) -> None:
    context = baseline_context()
    result = context.result
    arguments = record_arguments(context)
    if mutation == "result":
        forged = result.model_copy(
            update={
                "producer": Producer(
                    kind="producer",
                    name="org.ucf.forged-verification-adapter",
                    version="9.9.9",
                )
            }
        )
        result = forged.model_copy(
            update={"id": derive_execution_verification_result_id(forged)}
        )
    else:
        mapping = context.mapping_result.model_copy(
            update={
                "producer": Producer(
                    kind="producer",
                    name="org.ucf.forged-mapping-adapter",
                    version="9.9.9",
                )
            }
        )
        mapping = mapping.model_copy(
            update={"id": derive_implementation_mapping_result_id(mapping)}
        )
        arguments["mapping_result"] = mapping

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        record_verification_evidence(
            result,
            **arguments,
        )

    assert captured.value.code is (
        ImplementationEvidenceErrorCode.PRODUCER_IDENTITY_MISMATCH
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("result", "content_identity_mismatch"),
        ("mapping", "content_identity_mismatch"),
        ("claim", "document_identity_mismatch"),
        ("projection", "content_identity_mismatch"),
        ("subject", "invalid_structure"),
    ],
)
def test_assessor_revalidates_every_envelope_context_reference(
    mutation: str,
    expected_code: str,
) -> None:
    context = baseline_context()
    envelope = _forged_envelope(_record(context), mutation)

    with pytest.raises(EvidenceStatusValidationError) as captured:
        assess_verification_evidence(
            envelope,
            **recorded_assessment_arguments(context),
            **current_assessment_arguments(context),
        )

    assert captured.value.code.value == expected_code


def test_projection_members_are_derived_internally_not_caller_selected() -> None:
    context = baseline_context()

    with pytest.raises(TypeError, match="unexpected keyword"):
        record_verification_evidence(
            context.result,
            **record_arguments(context),
            dependency_members=(),
        )


def _record(context: EvidenceContext) -> VerificationEvidenceEnvelope:
    return record_verification_evidence(
        context.result,
        **record_arguments(context),
    )


def _assess(
    recorded: EvidenceContext,
    current: EvidenceContext,
) -> object:
    return assess_verification_evidence(
        _record(recorded),
        **recorded_assessment_arguments(recorded),
        **current_assessment_arguments(current),
    )


def _forged_envelope(
    envelope: VerificationEvidenceEnvelope,
    mutation: str,
) -> VerificationEvidenceEnvelope:
    digest = _filled_digest("f")
    if mutation == "result":
        envelope = envelope.model_copy(
            update={
                "verification_result": (
                    envelope.verification_result.model_copy(
                        update={
                            "target_id": f"result.{'f' * 64}",
                            "canonical_digest": digest,
                        }
                    )
                )
            }
        )
    elif mutation == "mapping":
        envelope = envelope.model_copy(
            update={
                "trace": envelope.trace.model_copy(
                    update={
                        "mapping": envelope.trace.mapping.model_copy(
                            update={
                                "target_id": f"mapping.{'f' * 64}",
                                "canonical_digest": digest,
                            }
                        )
                    }
                )
            }
        )
    elif mutation == "claim":
        envelope = envelope.model_copy(
            update={
                "claim": envelope.claim.model_copy(
                    update={
                        "target_id": f"claim.tested.{'f' * 64}",
                        "canonical_digest": digest,
                    }
                )
            }
        )
    elif mutation == "projection":
        behavior = envelope.recorded.behavior
        first = behavior.members[0].model_copy(update={"digest": digest})
        changed = behavior.model_copy(
            update={"members": (first, *behavior.members[1:])}
        )
        changed = _reidentify_projection(changed)
        envelope = envelope.model_copy(
            update={
                "recorded": envelope.recorded.model_copy(update={"behavior": changed})
            }
        )
    else:
        return envelope.model_copy(
            update={
                "subject": envelope.subject.model_copy(
                    update={"target_id": "use-case.render-receipt"}
                )
            }
        )
    return _reidentify_envelope(envelope)


def _reidentify_projection(projection: object) -> object:
    payload = projection.model_dump(mode="json")
    payload["digest"] = _content_digest(
        {key: value for key, value in payload.items() if key != "digest"}
    )
    return type(projection).model_validate_json(
        json.dumps(payload, separators=(",", ":"))
    )


def _reidentify_envelope(
    envelope: VerificationEvidenceEnvelope,
) -> VerificationEvidenceEnvelope:
    payload = envelope.model_dump(mode="json")
    identity = {key: value for key, value in payload.items() if key != "id"}
    payload["id"] = "envelope." + hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    return VerificationEvidenceEnvelope.model_validate_json(
        json.dumps(payload, separators=(",", ":"))
    )


def _reidentify_assessment(assessment: object) -> object:
    payload = assessment.model_dump(mode="json")
    identity = {key: value for key, value in payload.items() if key != "id"}
    payload["id"] = (
        "assessment." + hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    )
    return type(assessment).model_validate_json(
        json.dumps(payload, separators=(",", ":"))
    )


def _content_digest(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
    }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _filled_digest(fill: str) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=fill * 64,
    )
