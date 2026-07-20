from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from ucf.implementation_evidence import (
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    derive_implementation_mapping_result_id,
    validate_implementation_mapping_result,
)
from ucf.inventory import InventoryRecordKind, InventoryRecordRef
from ucf.ir.models import Digest, Producer

from .test_mapping_result_contract import _mapping_result


def _identified(result):
    return result.model_copy(
        update={"id": derive_implementation_mapping_result_id(result)}
    )


def _validate(result, **overrides) -> None:
    bundle = _bundle()
    arguments = {
        "request": _mapping_result().request,
        "bundle": bundle,
        "current_inventory": bundle.inventory,
        "initialized_adapter": _mapping_result().producer,
        "negotiated_capabilities": {
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0"
        },
    }
    arguments.update(overrides)
    validate_implementation_mapping_result(result, **arguments)


def test_complete_mapping_result_binds_every_reviewed_target_to_evidence() -> None:
    _validate(_mapping_result())


def test_context_validation_reestablishes_mapping_result_structure() -> None:
    result = _mapping_result()
    first = result.bindings[0]
    changed = first.model_copy(
        update={
            "source_records": (
                first.source_records[0],
                *first.source_records,
            )
        }
    )
    result = _identified(
        result.model_copy(
            update={"bindings": (changed, *result.bindings[1:])}
        )
    )

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _validate(result)

    assert captured.value.code.value == "invalid_structure"
    assert captured.value.location == "$"


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
            "current_inventory",
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "$.request.inventory",
        ),
        (
            "missing_binding",
            ImplementationEvidenceErrorCode.INCOMPLETE_BINDING,
            "$.bindings",
        ),
        (
            "extra_binding",
            ImplementationEvidenceErrorCode.INCOMPLETE_BINDING,
            "$.bindings",
        ),
        (
            "broken_source",
            ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
            "$.bindings[0].source_records[0]",
        ),
        (
            "wrong_source_kind",
            ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
            "$.bindings[0].source_records[0].target_kind",
        ),
        (
            "non_candidate_source",
            ImplementationEvidenceErrorCode.SOURCE_NOT_CANDIDATE_EVIDENCE,
            "$.bindings[0].source_records[0]",
        ),
    ],
)
def test_mapping_result_rejects_forged_context_or_incomplete_evidence(
    mutation: str,
    expected_code: ImplementationEvidenceErrorCode,
    expected_location: str,
) -> None:
    result = _mapping_result()
    overrides = {}
    if mutation == "request":
        changed_request = result.request.model_copy(
            update={
                "adapter_procedure_uri": (
                    "urn:ucf:fixture-adapter:changed-mapping:1.0.0"
                )
            }
        )
        result = _identified(result.model_copy(update={"request": changed_request}))
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
        overrides["negotiated_capabilities"] = {}
    elif mutation == "current_inventory":
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
    elif mutation == "missing_binding":
        result = _identified(
            result.model_copy(update={"bindings": result.bindings[:-1]})
        )
    elif mutation == "extra_binding":
        root_ids = {target.target_id for target in result.request.targets}
        extra_target = next(
            reference
            for materialization in _bundle().baseline.materializations
            for reference in materialization.entities
            if reference.target_id not in root_ids
        )
        extra = result.bindings[0].model_copy(
            update={"behavior": extra_target}
        )
        result = _identified(
            result.model_copy(
                update={
                    "bindings": tuple(
                        sorted(
                            (*result.bindings, extra),
                            key=lambda binding: (
                                binding.behavior.target_kind.value,
                                binding.behavior.target_id,
                            ),
                        )
                    )
                }
            )
        )
    else:
        bindings = list(result.bindings)
        source_records = list(bindings[0].source_records)
        if mutation == "broken_source":
            source_records[0] = source_records[0].model_copy(
                update={"target_id": f"interface.{'f' * 64}"}
            )
        elif mutation == "wrong_source_kind":
            source_records[0] = source_records[0].model_copy(
                update={"target_kind": InventoryRecordKind.TEST_ASSET}
            )
        else:
            candidate_refs = {
                reference.target_id
                for candidate in _bundle().discovery.candidates
                for reference in candidate.evidence
            }
            record = next(
                record
                for record in _bundle().inventory.records
                if record.id not in candidate_refs
            )
            source_records[0] = InventoryRecordRef(
                kind="inventory_record_ref",
                target_kind=InventoryRecordKind(record.kind),
                target_id=record.id,
            )
        bindings[0] = bindings[0].model_copy(
            update={"source_records": tuple(source_records)}
        )
        result = _identified(
            result.model_copy(update={"bindings": tuple(bindings)})
        )

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _validate(result, **overrides)

    assert captured.value.code is expected_code
    assert captured.value.location == expected_location
