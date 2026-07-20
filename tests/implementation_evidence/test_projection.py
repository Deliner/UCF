from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    canonical_execution_environment_digest,
    derive_execution_verification_result_id,
    project_execution_verification,
)
from ucf.ir import (
    IRValidationError,
    canonical_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import (
    Check,
    Digest,
    Producer,
    Provenance,
    VerificationEvidence,
)
from ucf.ir.trust_models import Claim, ClaimLevel, SourceRecord, TrustMapping
from ucf.onboarding import canonical_onboarding_json

from .test_mapping_result_contract import _mapping_result
from .test_verification_result_contract import _verification_result


def test_passed_result_derives_only_an_explicit_successor_and_tested_overlay() -> None:
    bundle = _bundle()
    original_bundle = canonical_onboarding_json(bundle)
    original_behavior = canonical_ir_json(bundle.behavior)

    projection = project_execution_verification(
        _verification_result("passed"),
        **_projection_arguments(),
    )

    assert canonical_onboarding_json(bundle) == original_bundle
    assert canonical_ir_json(bundle.behavior) == original_behavior
    assert projection.successor_behavior.document_id == (
        bundle.behavior.document_id
    )
    assert projection.successor_behavior.roots == bundle.behavior.roots
    originals = {entity.id: entity for entity in bundle.behavior.entities}
    successors = {
        entity.id: entity for entity in projection.successor_behavior.entities
    }
    assert all(successors[identity] == entity for identity, entity in originals.items())
    additions = tuple(
        entity
        for identity, entity in successors.items()
        if identity not in originals
    )
    assert len(additions) == 2
    provenance = next(
        entity for entity in additions if isinstance(entity, Provenance)
    )
    evidence = next(
        entity
        for entity in additions
        if isinstance(entity, VerificationEvidence)
    )
    assert evidence.provenance.target_id == provenance.id
    assert evidence.outcome == "passed"
    assert evidence.environment == canonical_execution_environment_digest(
        _verification_result().request.environment
    )
    assert evidence.check == _verification_result().request.check
    assert evidence.source_revision == (
        _verification_result().request.source.source_revision
    )
    assert canonical_ir_json(projection.successor_behavior) != original_behavior

    validate_trust_against_behavior(
        projection.tested_trust,
        projection.successor_behavior,
    )
    sources = tuple(
        record
        for record in projection.tested_trust.records
        if isinstance(record, SourceRecord)
    )
    claims = tuple(
        record
        for record in projection.tested_trust.records
        if isinstance(record, Claim)
    )
    assert len(sources) == 1
    assert len(claims) == 1
    assert claims[0].level is ClaimLevel.TESTED
    assert not any(
        isinstance(record, TrustMapping)
        for record in projection.tested_trust.records
    )

    with pytest.raises(IRValidationError):
        validate_trust_against_behavior(
            bundle.trust,
            projection.successor_behavior,
        )


def test_projection_is_deterministic_for_the_same_completed_result() -> None:
    result = _verification_result()

    first = project_execution_verification(
        result,
        **_projection_arguments(),
    )
    second = project_execution_verification(
        result,
        **_projection_arguments(),
    )

    assert first == second


@pytest.mark.parametrize(
    "mutation",
    (
        "environment",
        "check",
        "source",
        "mapping",
        "producer",
    ),
)
def test_projection_never_promotes_a_context_forged_result(
    mutation: str,
) -> None:
    result = _verification_result()
    request = result.request
    if mutation == "environment":
        request = request.model_copy(
            update={
                "environment": request.environment.model_copy(
                    update={"revision": _digest("f")}
                )
            }
        )
    elif mutation == "check":
        request = request.model_copy(
            update={
                "check": Check(
                    kind="check",
                    id="check.other",
                    version="1.0.0",
                    procedure_uri="urn:ucf:fixture-check:other:1.0.0",
                )
            }
        )
    elif mutation == "source":
        request = request.model_copy(
            update={
                "source": request.source.model_copy(
                    update={"source_revision": _digest("f")}
                )
            }
        )
    elif mutation == "mapping":
        request = request.model_copy(
            update={
                "mapping": request.mapping.model_copy(
                    update={
                        "target_id": f"mapping.{'f' * 64}",
                        "canonical_digest": _digest("f"),
                    }
                )
            }
        )
    else:
        result = result.model_copy(
            update={
                "producer": Producer(
                    kind="producer",
                    name="org.ucf.uninitialized-adapter",
                    version="9.9.9",
                )
            }
        )
    if mutation != "producer":
        result = result.model_copy(update={"request": request})
    result = result.model_copy(
        update={"id": derive_execution_verification_result_id(result)}
    )

    with pytest.raises(ImplementationEvidenceValidationError):
        project_execution_verification(
            result,
            **_projection_arguments(),
        )


@pytest.mark.parametrize("outcome", ["failed", "error"])
def test_nonpassing_result_never_projects_a_tested_claim(outcome: str) -> None:
    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        project_execution_verification(
            _verification_result(outcome),
            **_projection_arguments(),
        )

    assert captured.value.code is (
        ImplementationEvidenceErrorCode.EVIDENCE_NOT_PASSED
    )
    assert captured.value.location == "$.outcome"


def _digest(value: str) -> Digest:
    return Digest(kind="digest", algorithm="sha-256", value=value * 64)


def _projection_arguments() -> dict[str, object]:
    bundle = _bundle()
    mapping = _mapping_result()
    result = _verification_result()
    return {
        "request": result.request,
        "mapping_result": mapping,
        "bundle": bundle,
        "current_inventory": bundle.inventory,
        "mapping_initialized_adapter": mapping.producer,
        "initialized_adapter": result.producer,
        "negotiated_capabilities": {
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
        },
    }
