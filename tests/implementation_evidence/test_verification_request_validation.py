from __future__ import annotations

import pytest

from tests.onboarding.test_bundle import _bundle
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    validate_execution_verification_request,
)
from ucf.inventory import InventoryRecordKind, InventoryRecordRef
from ucf.ir.models import Digest, EntityKind, EntityRef, StringValue

from .test_mapping_result_contract import _mapping_result
from .test_verification_request_contract import _verification_request


def _validate(request, **overrides) -> None:
    bundle = _bundle()
    mapping = _mapping_result()
    arguments = {
        "mapping_result": mapping,
        "bundle": bundle,
        "current_inventory": bundle.inventory,
        "mapping_initialized_adapter": mapping.producer,
        "negotiated_capabilities": {
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
        },
    }
    arguments.update(overrides)
    validate_execution_verification_request(request, **arguments)


def test_verification_request_binds_an_accepted_mapping_and_current_source() -> None:
    _validate(_verification_request())


@pytest.mark.parametrize(
    "mutation",
    ("duplicate_port", "wrong_direction", "wrong_owner"),
)
def test_context_validation_reestablishes_verification_request_structure(
    mutation: str,
) -> None:
    request = _verification_request()
    first = request.inputs[0]
    if mutation == "duplicate_port":
        inputs = (first, *request.inputs)
    else:
        port = first.port
        if mutation == "wrong_direction":
            port = port.model_copy(update={"direction": "output"})
        else:
            port = port.model_copy(
                update={
                    "owner": EntityRef(
                        kind="entity_ref",
                        target_kind=EntityKind.USE_CASE,
                        target_id="use-case.other",
                    )
                }
            )
        inputs = (first.model_copy(update={"port": port}), *request.inputs[1:])
    request = request.model_copy(update={"inputs": inputs})

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _validate(request)

    assert captured.value.code.value == "invalid_structure"
    assert captured.value.location == "$"


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_location"),
    [
        (
            "mapping_id",
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "$.mapping.target_id",
        ),
        (
            "mapping_digest",
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "$.mapping.canonical_digest",
        ),
        (
            "base_behavior",
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "$.base_behavior.canonical_digest",
        ),
        (
            "broken_subject",
            ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
            "$.subject",
        ),
        (
            "wrong_subject_kind",
            ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
            "$.subject.target_kind",
        ),
        (
            "unmapped_subject",
            ImplementationEvidenceErrorCode.TARGET_NOT_MAPPED,
            "$.subject",
        ),
        (
            "source_uri",
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "$.source.subject_uri",
        ),
        (
            "source_revision",
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "$.source.source_revision",
        ),
        (
            "source_records",
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "$.source.records",
        ),
        (
            "current_inventory",
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "$.source.source_revision",
        ),
        (
            "capability",
            ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH,
            "$.capability",
        ),
    ],
)
def test_verification_request_rejects_replay_or_stale_coordinates(
    mutation: str,
    expected_code: ImplementationEvidenceErrorCode,
    expected_location: str,
) -> None:
    request = _verification_request()
    overrides = {}
    if mutation in {"mapping_id", "mapping_digest"}:
        mapping_ref = request.mapping
        if mutation == "mapping_id":
            mapping_ref = mapping_ref.model_copy(
                update={"target_id": f"mapping.{'f' * 64}"}
            )
        else:
            mapping_ref = mapping_ref.model_copy(
                update={"canonical_digest": _digest("f")}
            )
        request = request.model_copy(update={"mapping": mapping_ref})
    elif mutation == "base_behavior":
        request = request.model_copy(
            update={
                "base_behavior": request.base_behavior.model_copy(
                    update={"canonical_digest": _digest("f")}
                )
            }
        )
    elif mutation in {
        "broken_subject",
        "wrong_subject_kind",
        "unmapped_subject",
    }:
        subject = request.subject
        if mutation == "broken_subject":
            subject = subject.model_copy(
                update={"target_id": "use-case.missing"}
            )
        elif mutation == "wrong_subject_kind":
            subject = subject.model_copy(
                update={"target_kind": EntityKind.ACTION}
            )
        else:
            mapped_ids = {
                binding.behavior.target_id
                for binding in _mapping_result().bindings
            }
            subject = next(
                reference
                for materialization in _bundle().baseline.materializations
                for reference in materialization.entities
                if reference.target_id not in mapped_ids
            )
        request = request.model_copy(update={"subject": subject})
    elif mutation == "source_uri":
        request = request.model_copy(
            update={
                "source": request.source.model_copy(
                    update={"subject_uri": "urn:ucf:repository:other"}
                )
            }
        )
    elif mutation == "source_revision":
        request = request.model_copy(
            update={
                "source": request.source.model_copy(
                    update={"source_revision": _digest("f")}
                )
            }
        )
    elif mutation == "source_records":
        bound_ids = {
            reference.target_id for reference in request.source.records
        }
        record = next(
            record
            for record in _bundle().inventory.records
            if record.id not in bound_ids
        )
        request = request.model_copy(
            update={
                "source": request.source.model_copy(
                    update={
                        "records": (
                            InventoryRecordRef(
                                kind="inventory_record_ref",
                                target_kind=InventoryRecordKind(record.kind),
                                target_id=record.id,
                            ),
                        )
                    }
                )
            }
        )
    elif mutation == "current_inventory":
        inventory = _bundle().inventory
        overrides["current_inventory"] = inventory.model_copy(
            update={"source_revision": _digest("f")}
        )
    else:
        overrides["negotiated_capabilities"] = {
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0"
        }

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _validate(request, **overrides)

    assert captured.value.code is expected_code
    assert captured.value.location == expected_location


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expected_location"),
    [
        (
            "missing_input",
            ImplementationEvidenceErrorCode.INCOMPLETE_BINDING,
            "$.inputs",
        ),
        (
            "missing_output",
            ImplementationEvidenceErrorCode.INCOMPLETE_BINDING,
            "$.expected_outputs",
        ),
        (
            "unknown_port",
            ImplementationEvidenceErrorCode.UNKNOWN_PORT,
            "$.inputs[0].port.name",
        ),
        (
            "wrong_value_kind",
            ImplementationEvidenceErrorCode.VALUE_KIND_MISMATCH,
            "$.inputs[0].value",
        ),
    ],
)
def test_verification_request_requires_exact_typed_behavior_port_values(
    mutation: str,
    expected_code: ImplementationEvidenceErrorCode,
    expected_location: str,
) -> None:
    request = _verification_request()
    if mutation == "missing_input":
        request = request.model_copy(update={"inputs": ()})
    elif mutation == "missing_output":
        request = request.model_copy(update={"expected_outputs": ()})
    else:
        values = list(request.inputs)
        if mutation == "unknown_port":
            values[0] = values[0].model_copy(
                update={
                    "port": values[0].port.model_copy(
                        update={"name": "missing-port"}
                    )
                }
            )
        else:
            values[0] = values[0].model_copy(
                update={
                    "value": StringValue(
                        kind="string",
                        value="wrong",
                    )
                }
            )
        request = request.model_copy(update={"inputs": tuple(values)})

    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        _validate(request)

    assert captured.value.code is expected_code
    assert captured.value.location == expected_location


def _digest(value: str) -> Digest:
    return Digest(kind="digest", algorithm="sha-256", value=value * 64)
