from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    derive_execution_verification_result_id,
    validate_execution_verification_result,
)
from ucf.ir.models import Digest, Producer

from .test_mapping_result_contract import _mapping_result
from .test_verification_request_contract import _verification_request
from .test_verification_result_contract import _verification_result


def _identified(result):
    return result.model_copy(
        update={"id": derive_execution_verification_result_id(result)}
    )


def _validate(result, **overrides) -> None:
    bundle = _bundle()
    mapping = _mapping_result()
    arguments = {
        "request": _verification_request(),
        "mapping_result": mapping,
        "bundle": bundle,
        "current_inventory": bundle.inventory,
        "mapping_initialized_adapter": mapping.producer,
        "initialized_adapter": _verification_result().producer,
        "negotiated_capabilities": {
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
        },
    }
    arguments.update(overrides)
    validate_execution_verification_result(result, **arguments)


@pytest.mark.parametrize("outcome", ["passed", "failed", "error"])
def test_completed_verification_result_is_valid_contextual_evidence(
    outcome: str,
) -> None:
    _validate(_verification_result(outcome))


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_location"),
    [
        (
            "request",
            ImplementationEvidenceErrorCode.REQUEST_IDENTITY_MISMATCH,
            "$.request",
        ),
        (
            "producer",
            ImplementationEvidenceErrorCode.PRODUCER_IDENTITY_MISMATCH,
            "$.producer",
        ),
        (
            "capability",
            ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH,
            "$.capability",
        ),
        (
            "unselected",
            ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH,
            "$.capability",
        ),
        (
            "procedure",
            ImplementationEvidenceErrorCode.PROCEDURE_MISMATCH,
            "$.procedure_uri",
        ),
        (
            "source_mutation",
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "$.source.source_revision",
        ),
    ],
)
def test_verification_result_rejects_forged_context_or_source_mutation(
    mutation: str,
    expected_code: ImplementationEvidenceErrorCode,
    expected_location: str,
) -> None:
    result = _verification_result()
    overrides = {}
    if mutation == "request":
        request = result.request.model_copy(
            update={
                "environment": result.request.environment.model_copy(
                    update={
                        "revision": Digest(
                            kind="digest",
                            algorithm="sha-256",
                            value="f" * 64,
                        )
                    }
                )
            }
        )
        result = _identified(result.model_copy(update={"request": request}))
    elif mutation == "producer":
        result = _identified(
            result.model_copy(
                update={
                    "producer": Producer(
                        kind="producer",
                        name="org.ucf.other-adapter",
                        version="1.0.0",
                    )
                }
            )
        )
    elif mutation == "capability":
        result = _identified(
            result.model_copy(
                update={
                    "capability": CapabilitySelection(
                        kind="capability",
                        name=IMPLEMENTATION_MAPPING_CAPABILITY,
                        version="1.0.0",
                    )
                }
            )
        )
    elif mutation == "unselected":
        overrides["negotiated_capabilities"] = {
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0"
        }
    elif mutation == "procedure":
        result = _identified(
            result.model_copy(
                update={
                    "procedure_uri": (
                        "urn:ucf:fixture-adapter:other-verification:1.0.0"
                    )
                }
            )
        )
    else:
        inventory = _bundle().inventory
        overrides["current_inventory"] = inventory.model_copy(
            update={
                "source_revision": Digest(
                    kind="digest",
                    algorithm="sha-256",
                    value="f" * 64,
                )
            }
        )

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _validate(result, **overrides)

    assert captured.value.code is expected_code
    assert captured.value.location == expected_location
