from __future__ import annotations

import hashlib
from collections.abc import Mapping

from ucf.adapter_protocol.versioning import version_at_least
from ucf.ir import canonical_ir_json
from ucf.ir.models import BehaviorIR, Digest, Observation, Producer
from ucf.runtime_evidence.codec import canonical_runtime_evidence_digest
from ucf.runtime_evidence.errors import (
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceValidationError,
)
from ucf.runtime_evidence.identity import (
    derive_runtime_evidence_result_id,
)
from ucf.runtime_evidence.models import (
    RuntimeEnvironment,
    RuntimeEvidenceAcceptedResult,
    RuntimeEvidenceImportRequest,
    RuntimeEvidenceRejectedResult,
    RuntimeEvidenceResult,
)


def validate_runtime_evidence_request(
    request: RuntimeEvidenceImportRequest,
    *,
    behavior: BehaviorIR,
    environment: RuntimeEnvironment,
) -> None:
    _validate_behavior_binding(request, behavior)
    _validate_environment_binding(request, environment)
    index = {entity.id: entity for entity in behavior.entities}
    for position, rule in enumerate(request.policy.rules):
        location = f"$.policy.rules[{position}]"
        subject = rule.subject
        if (
            subject.document_id != request.behavior.document_id
            or subject.ir_version != request.behavior.ir_version
            or subject.canonical_digest
            != request.behavior.canonical_digest
        ):
            _fail(
                RuntimeEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                "policy subject does not bind the request behavior",
                location=f"{location}.subject",
            )
        target = index.get(subject.target_id)
        if target is None:
            _fail(
                RuntimeEvidenceErrorCode.BROKEN_REFERENCE,
                "runtime observation subject does not exist",
                location=f"{location}.subject",
            )
        if not isinstance(target, Observation):
            _fail(
                RuntimeEvidenceErrorCode.WRONG_TARGET_KIND,
                "runtime observation subject does not resolve to observation",
                location=f"{location}.subject.target_kind",
            )
        if (
            rule.assertion.target != target.target
            or rule.assertion.value != target.value
        ):
            _fail(
                RuntimeEvidenceErrorCode.ASSERTION_MISMATCH,
                "runtime observation assertion differs from declared slot",
                location=f"{location}.assertion",
            )


def validate_runtime_evidence_result_structure(
    result: RuntimeEvidenceResult,
) -> None:
    if isinstance(result, RuntimeEvidenceAcceptedResult):
        rule_ids = tuple(
            observation.rule.target_id
            for observation in result.observations
        )
        if len(rule_ids) != len(set(rule_ids)):
            _fail(
                RuntimeEvidenceErrorCode.DUPLICATE_IDENTITY,
                "runtime evidence observations contain duplicate rule refs",
                location="$.observations",
            )
        if rule_ids != tuple(sorted(rule_ids)):
            _fail(
                RuntimeEvidenceErrorCode.NON_CANONICAL_ORDER,
                "runtime evidence observations are not in canonical order",
                location="$.observations",
            )
        if result.sanitization.selected_rule_count != len(
            result.observations
        ):
            _fail(
                RuntimeEvidenceErrorCode.SUMMARY_MISMATCH,
                "selected rule count differs from observations",
                location="$.sanitization.selected_rule_count",
            )
    elif isinstance(result, RuntimeEvidenceRejectedResult):
        reasons = tuple(result.reason_codes)
        if len(reasons) != len(set(reasons)):
            _fail(
                RuntimeEvidenceErrorCode.DUPLICATE_IDENTITY,
                "runtime evidence rejection contains duplicate reason codes",
                location="$.reason_codes",
            )
        if reasons != tuple(sorted(reasons)):
            _fail(
                RuntimeEvidenceErrorCode.NON_CANONICAL_ORDER,
                "runtime evidence rejection reasons are not canonical",
                location="$.reason_codes",
            )
    else:
        raise AssertionError("unhandled runtime evidence result")
    if result.id != derive_runtime_evidence_result_id(result):
        _fail(
            RuntimeEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "runtime evidence result ID is not derived from exact content",
            location="$.id",
        )


def validate_runtime_evidence_result(
    result: RuntimeEvidenceResult,
    *,
    request: RuntimeEvidenceImportRequest,
    behavior: BehaviorIR,
    environment: RuntimeEnvironment,
    initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
    source_revision: Digest,
) -> None:
    validate_runtime_evidence_result_structure(result)
    if result.request != request:
        _fail(
            RuntimeEvidenceErrorCode.REQUEST_IDENTITY_MISMATCH,
            "runtime evidence result does not echo the exact request",
            location="$.request",
        )
    validate_runtime_evidence_request(
        request,
        behavior=behavior,
        environment=environment,
    )
    if result.producer != initialized_adapter:
        _fail(
            RuntimeEvidenceErrorCode.PRODUCER_IDENTITY_MISMATCH,
            "runtime evidence producer differs from initialized adapter",
            location="$.producer",
        )
    verification_version = negotiated_capabilities.get(
        "org.ucf.adapter.verification"
    )
    runtime_version = negotiated_capabilities.get(
        "org.ucf.adapter.runtime-evidence"
    )
    if (
        verification_version is None
        or not version_at_least(verification_version, "1.0.0")
        or runtime_version != "1.0.0"
    ):
        _fail(
            RuntimeEvidenceErrorCode.CAPABILITY_MISMATCH,
            "required runtime evidence capabilities were not selected",
            location="$.capability",
        )
    if source_revision != request.source.source_revision:
        _fail(
            RuntimeEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "runtime evidence source revision differs from local input",
            location="$.request.source.source_revision",
        )
    if isinstance(result, RuntimeEvidenceAcceptedResult):
        validate_runtime_observation_refs(result)


def validate_runtime_observation_refs(
    result: RuntimeEvidenceAcceptedResult,
) -> None:
    rule_ids = {rule.id for rule in result.request.policy.rules}
    for position, observation in enumerate(result.observations):
        if observation.rule.target_id not in rule_ids:
            _fail(
                RuntimeEvidenceErrorCode.BROKEN_REFERENCE,
                "runtime observation names an unknown policy rule",
                location=f"$.observations[{position}].rule",
            )


def _validate_behavior_binding(
    request: RuntimeEvidenceImportRequest,
    behavior: BehaviorIR,
) -> None:
    expected_digest = hashlib.sha256(
        canonical_ir_json(behavior).encode("ascii")
    ).hexdigest()
    comparisons = (
        (
            "document_id",
            request.behavior.document_id,
            behavior.document_id,
        ),
        (
            "ir_version",
            request.behavior.ir_version,
            behavior.ir_version,
        ),
        (
            "canonical_digest",
            request.behavior.canonical_digest.value,
            expected_digest,
        ),
    )
    for field, actual, expected in comparisons:
        if actual != expected:
            _fail(
                RuntimeEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                f"request behavior {field} differs from supplied behavior",
                location=f"$.behavior.{field}",
            )


def _validate_environment_binding(
    request: RuntimeEvidenceImportRequest,
    environment: RuntimeEnvironment,
) -> None:
    comparisons = (
        (
            "environment_uri",
            request.environment.environment_uri,
            environment.environment_uri,
        ),
        (
            "revision",
            request.environment.revision,
            environment.revision,
        ),
        (
            "canonical_digest",
            request.environment.canonical_digest,
            canonical_runtime_evidence_digest(environment),
        ),
    )
    for field, actual, expected in comparisons:
        if actual != expected:
            _fail(
                RuntimeEvidenceErrorCode.ENVIRONMENT_IDENTITY_MISMATCH,
                (
                    f"request environment {field} differs from supplied "
                    "environment"
                ),
                location=f"$.environment.{field}",
            )


def _fail(
    code: RuntimeEvidenceErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise RuntimeEvidenceValidationError(
        code,
        message,
        location=location,
    )
