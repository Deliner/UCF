from __future__ import annotations

import pytest

from ucf.ir.models import Digest, Producer
from ucf.runtime_evidence import (
    RuntimeEvidenceErrorCode,
    RuntimeEvidenceValidationError,
    RuntimeObservation,
    RuntimeObservationRuleRef,
    derive_runtime_evidence_result_id,
    validate_runtime_evidence_result,
)

from .test_result_contract import _accepted, _rejected
from .test_validation import _bound_request


def _bound_result(*, rejected: bool = False):
    request, behavior, environment = _bound_request()
    original = _rejected() if rejected else _accepted()
    provisional = original.model_copy(
        update={
            "id": f"result.{'0' * 64}",
            "request": request,
            "procedure_uri": request.adapter_procedure_uri,
        }
    )
    result = provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )
    return result, request, behavior, environment


def _validate(
    result,
    request,
    behavior,
    environment,
    *,
    producer: Producer | None = None,
    capabilities: dict[str, str] | None = None,
    source_revision: Digest | None = None,
) -> None:
    validate_runtime_evidence_result(
        result,
        request=request,
        behavior=behavior,
        environment=environment,
        initialized_adapter=producer or result.producer,
        negotiated_capabilities=capabilities
        or {
            "org.ucf.adapter.verification": "1.0.0",
            "org.ucf.adapter.runtime-evidence": "1.0.0",
        },
        source_revision=source_revision or request.source.source_revision,
    )


@pytest.mark.parametrize("rejected", [False, True])
def test_result_context_binds_exact_request_adapter_and_capabilities(
    rejected: bool,
) -> None:
    result, request, behavior, environment = _bound_result(
        rejected=rejected
    )

    _validate(result, request, behavior, environment)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("request", RuntimeEvidenceErrorCode.REQUEST_IDENTITY_MISMATCH),
        ("producer", RuntimeEvidenceErrorCode.PRODUCER_IDENTITY_MISMATCH),
        ("missing_verification", RuntimeEvidenceErrorCode.CAPABILITY_MISMATCH),
        ("runtime_version", RuntimeEvidenceErrorCode.CAPABILITY_MISMATCH),
        ("source", RuntimeEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH),
        ("rule", RuntimeEvidenceErrorCode.BROKEN_REFERENCE),
    ],
)
def test_result_context_rejects_every_forged_coordinate(
    mutation: str,
    expected_code: RuntimeEvidenceErrorCode,
) -> None:
    result, request, behavior, environment = _bound_result()
    producer = result.producer
    capabilities = {
        "org.ucf.adapter.verification": "1.0.0",
        "org.ucf.adapter.runtime-evidence": "1.0.0",
    }
    source_revision = request.source.source_revision
    if mutation == "request":
        changed_source = result.request.source.model_copy(
            update={
                "source_revision": Digest(
                    kind="digest",
                    algorithm="sha-256",
                    value="f" * 64,
                )
            }
        )
        changed_request = result.request.model_copy(
            update={"source": changed_source}
        )
        result = _reidentify(result.model_copy(update={"request": changed_request}))
    elif mutation == "producer":
        producer = Producer(
            kind="producer",
            name="org.ucf.another-adapter",
            version="1.0.0",
        )
    elif mutation == "missing_verification":
        capabilities.pop("org.ucf.adapter.verification")
    elif mutation == "runtime_version":
        capabilities["org.ucf.adapter.runtime-evidence"] = "1.1.0"
    elif mutation == "source":
        source_revision = Digest(
            kind="digest",
            algorithm="sha-256",
            value="f" * 64,
        )
    else:
        changed_observation = RuntimeObservation(
            kind="runtime_observation",
            rule=RuntimeObservationRuleRef(
                kind="runtime_observation_rule_ref",
                target_id="rule.unknown",
            ),
        )
        result = _reidentify(
            result.model_copy(
                update={"observations": (changed_observation,)}
            )
        )

    with pytest.raises(RuntimeEvidenceValidationError) as captured:
        _validate(
            result,
            request,
            behavior,
            environment,
            producer=producer,
            capabilities=capabilities,
            source_revision=source_revision,
        )

    assert captured.value.code is expected_code


def _reidentify(result):
    provisional = result.model_copy(update={"id": f"result.{'0' * 64}"})
    return provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )
