from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    validate_implementation_mapping_request,
)
from ucf.ir.models import Digest, EntityKind

from .test_mapping_request_contract import _mapping_request


def test_mapping_request_binds_the_exact_reviewed_bundle_and_roots() -> None:
    bundle = _bundle()

    validate_implementation_mapping_request(
        _mapping_request(),
        bundle=bundle,
    )


@pytest.mark.parametrize("mutation", ("wrong_capability", "duplicate_targets"))
def test_context_validation_reestablishes_mapping_request_structure(
    mutation: str,
) -> None:
    request = _mapping_request()
    if mutation == "wrong_capability":
        request = request.model_copy(
            update={
                "capability": CapabilitySelection(
                    kind="capability",
                    name=EXECUTION_VERIFICATION_CAPABILITY,
                    version="1.0.0",
                )
            }
        )
    else:
        request = request.model_copy(
            update={"targets": (request.targets[0], request.targets[0])}
        )

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        validate_implementation_mapping_request(request, bundle=_bundle())

    assert captured.value.code.value == "invalid_structure"
    assert captured.value.location == "$"


def test_context_validation_normalizes_a_malformed_in_memory_model() -> None:
    request = _mapping_request().model_copy(update={"targets": (None,)})

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        validate_implementation_mapping_request(request, bundle=_bundle())

    assert captured.value.code.value == "invalid_structure"
    assert captured.value.location == "$"


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_location"),
    [
        (
            "onboarding",
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "$.onboarding.canonical_digest",
        ),
        (
            "behavior",
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "$.behavior",
        ),
        (
            "inventory",
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "$.inventory",
        ),
        (
            "stale_target",
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "$.targets[0].canonical_digest",
        ),
        (
            "broken_target",
            ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
            "$.targets[0]",
        ),
        (
            "wrong_kind",
            ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
            "$.targets[0].target_kind",
        ),
        (
            "not_materialized_root",
            ImplementationEvidenceErrorCode.TARGET_NOT_MATERIALIZED,
            "$.targets[0]",
        ),
    ],
)
def test_mapping_request_rejects_every_stale_or_unreviewed_coordinate(
    mutation: str,
    expected_code: ImplementationEvidenceErrorCode,
    expected_location: str,
) -> None:
    request = _mapping_request()
    if mutation == "onboarding":
        request = request.model_copy(
            update={
                "onboarding": request.onboarding.model_copy(
                    update={
                        "canonical_digest": Digest(
                            kind="digest",
                            algorithm="sha-256",
                            value="f" * 64,
                        )
                    }
                )
            }
        )
    elif mutation == "behavior":
        request = request.model_copy(
            update={
                "behavior": request.behavior.model_copy(
                    update={"document_id": "document.changed"}
                )
            }
        )
    elif mutation == "inventory":
        request = request.model_copy(
            update={
                "inventory": request.inventory.model_copy(
                    update={
                        "source_revision": Digest(
                            kind="digest",
                            algorithm="sha-256",
                            value="f" * 64,
                        )
                    }
                )
            }
        )
    else:
        targets = list(request.targets)
        target = targets[0]
        if mutation == "stale_target":
            target = target.model_copy(
                update={
                    "canonical_digest": Digest(
                        kind="digest",
                        algorithm="sha-256",
                        value="f" * 64,
                    )
                }
            )
        elif mutation == "broken_target":
            target = target.model_copy(update={"target_id": "use-case.missing"})
        elif mutation == "wrong_kind":
            target = target.model_copy(
                update={"target_kind": EntityKind.ACTION}
            )
        else:
            target = next(
                materialized_entity
                for materialization in _bundle().baseline.materializations
                for materialized_entity in materialization.entities
                if materialized_entity != materialization.root
            )
        targets[0] = target
        request = request.model_copy(update={"targets": tuple(targets)})

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        validate_implementation_mapping_request(
            request,
            bundle=_bundle(),
        )

    assert captured.value.code is expected_code
    assert captured.value.location == expected_location
