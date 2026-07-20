from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pydantic import ValidationError as PydanticValidationError

from ucf.implementation_evidence.codec import (
    canonical_implementation_evidence_digest,
)
from ucf.implementation_evidence.errors import (
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
)
from ucf.implementation_evidence.identity import (
    derive_execution_verification_result_id,
    derive_implementation_mapping_result_id,
)
from ucf.implementation_evidence.models import (
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationMappingRequest,
    ImplementationMappingResult,
)
from ucf.inventory import InventoryRecordKind, InventorySnapshot
from ucf.ir import canonical_ir_json
from ucf.ir.models import Digest, IRModel, Port, Producer, ValueKind
from ucf.ir.trust_models import BehaviorEntityRef
from ucf.onboarding import (
    OnboardingBundle,
    canonical_onboarding_digest,
    validate_onboarding_bundle,
)


def validate_implementation_mapping_request(
    request: ImplementationMappingRequest,
    *,
    bundle: OnboardingBundle,
) -> None:
    if (
        not isinstance(request.targets, tuple)
        or any(
            not isinstance(target, BehaviorEntityRef)
            for target in request.targets
        )
    ):
        _fail(
            ImplementationEvidenceErrorCode.INVALID_STRUCTURE,
            "mapping request targets are structurally invalid",
            location="$",
        )
    validate_onboarding_bundle(bundle)
    if request.onboarding.canonical_digest != canonical_onboarding_digest(
        bundle
    ):
        _fail(
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "mapping request does not bind the supplied onboarding bundle",
            location="$.onboarding.canonical_digest",
        )
    if request.behavior != bundle.behavior:
        _fail(
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "mapping request Behavior IR differs from the reviewed bundle",
            location="$.behavior",
        )
    if request.inventory != bundle.inventory:
        _fail(
            ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "mapping request inventory differs from the reviewed bundle",
            location="$.inventory",
        )

    behavior_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_ir_json(bundle.behavior).encode("ascii")
        ).hexdigest(),
    )
    entity_index = {entity.id: entity for entity in bundle.behavior.entities}
    materialized_roots = {
        materialization.root
        for materialization in bundle.baseline.materializations
    }
    for position, target in enumerate(request.targets):
        location = f"$.targets[{position}]"
        comparisons = (
            (
                "document_id",
                target.document_id,
                bundle.behavior.document_id,
            ),
            ("ir_version", target.ir_version, bundle.behavior.ir_version),
            ("canonical_digest", target.canonical_digest, behavior_digest),
        )
        for field, actual, expected in comparisons:
            if actual != expected:
                _fail(
                    ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                    f"mapping target {field} differs from the bundle behavior",
                    location=f"{location}.{field}",
                )
        entity = entity_index.get(target.target_id)
        if entity is None:
            _fail(
                ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
                "mapping target does not resolve in the bundle behavior",
                location=location,
            )
        if entity.kind is not target.target_kind:
            _fail(
                ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
                "mapping target kind differs from the resolved behavior entity",
                location=f"{location}.target_kind",
            )
        if target not in materialized_roots:
            _fail(
                ImplementationEvidenceErrorCode.TARGET_NOT_MATERIALIZED,
                "mapping target is not a reviewed materialization root",
                location=location,
            )
    _revalidate_model(request, ImplementationMappingRequest)


def validate_implementation_mapping_result_structure(
    result: ImplementationMappingResult,
) -> None:
    result = _revalidate_model(result, ImplementationMappingResult)
    if result.id != derive_implementation_mapping_result_id(result):
        _fail(
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "mapping result ID is not derived from its exact content",
            location="$.id",
        )


def validate_execution_verification_result_structure(
    result: ExecutionVerificationResult,
) -> None:
    result = _revalidate_model(result, ExecutionVerificationResult)
    if result.id != derive_execution_verification_result_id(result):
        _fail(
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "verification result ID is not derived from its exact content",
            location="$.id",
        )


def validate_implementation_mapping_result(
    result: ImplementationMappingResult,
    *,
    request: ImplementationMappingRequest,
    bundle: OnboardingBundle,
    current_inventory: InventorySnapshot,
    initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> None:
    request = _revalidate_model(request, ImplementationMappingRequest)
    if result.id != derive_implementation_mapping_result_id(result):
        _fail(
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "mapping result ID is not derived from its exact content",
            location="$.id",
        )
    if result.request != request:
        _fail(
            ImplementationEvidenceErrorCode.REQUEST_IDENTITY_MISMATCH,
            "mapping result does not echo the exact request",
            location="$.request",
        )
    validate_implementation_mapping_request(request, bundle=bundle)
    if result.producer != initialized_adapter:
        _fail(
            ImplementationEvidenceErrorCode.PRODUCER_IDENTITY_MISMATCH,
            "mapping result producer differs from the initialized adapter",
            location="$.producer",
        )
    selected_version = negotiated_capabilities.get(
        request.capability.name
    )
    if (
        result.capability != request.capability
        or selected_version != request.capability.version
    ):
        _fail(
            ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH,
            "the exact mapping capability was not selected",
            location="$.capability",
        )
    if result.procedure_uri != request.adapter_procedure_uri:
        _fail(
            ImplementationEvidenceErrorCode.PROCEDURE_MISMATCH,
            "mapping result procedure differs from the request",
            location="$.procedure_uri",
        )
    if current_inventory != request.inventory:
        _fail(
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "current inventory differs from the mapped source snapshot",
            location="$.request.inventory",
        )

    expected_targets = set(request.targets)
    actual_targets = {binding.behavior for binding in result.bindings}
    if (
        len(actual_targets) != len(result.bindings)
        or actual_targets != expected_targets
    ):
        _fail(
            ImplementationEvidenceErrorCode.INCOMPLETE_BINDING,
            "mapping result must contain exactly one binding per target",
            location="$.bindings",
        )

    records = {record.id: record for record in request.inventory.records}
    materializations = {
        materialization.root: materialization
        for materialization in bundle.baseline.materializations
    }
    candidates = {
        candidate.id: candidate for candidate in bundle.discovery.candidates
    }
    for binding_position, binding in enumerate(result.bindings):
        candidate = candidates[
            materializations[binding.behavior].candidate.candidate_id
        ]
        candidate_evidence = set(candidate.evidence)
        for source_position, reference in enumerate(binding.source_records):
            location = (
                f"$.bindings[{binding_position}]"
                f".source_records[{source_position}]"
            )
            record = records.get(reference.target_id)
            if record is None:
                _fail(
                    ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
                    "implementation source record does not exist",
                    location=location,
                )
            if InventoryRecordKind(record.kind) is not reference.target_kind:
                _fail(
                    ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
                    "implementation source record kind differs from inventory",
                    location=f"{location}.target_kind",
                )
            if reference not in candidate_evidence:
                _fail(
                    ImplementationEvidenceErrorCode.SOURCE_NOT_CANDIDATE_EVIDENCE,
                    "implementation source is not reviewed candidate evidence",
                    location=location,
                )
        if candidate.subject not in binding.source_records:
            _fail(
                ImplementationEvidenceErrorCode.SOURCE_NOT_CANDIDATE_EVIDENCE,
                "implementation binding omits the candidate public interface",
                location=f"$.bindings[{binding_position}].source_records",
            )
    _revalidate_model(result, ImplementationMappingResult)


def validate_execution_verification_request(
    request: ExecutionVerificationRequest,
    *,
    mapping_result: ImplementationMappingResult,
    bundle: OnboardingBundle,
    current_inventory: InventorySnapshot,
    mapping_initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> None:
    current_source_coordinates = (
        (
            "subject_uri",
            current_inventory.subject_uri,
            request.source.subject_uri,
        ),
        (
            "source_revision",
            current_inventory.source_revision,
            request.source.source_revision,
        ),
    )
    for field, actual, expected in current_source_coordinates:
        if actual != expected:
            _fail(
                ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
                (
                    "current inventory coordinates differ from the "
                    "verification source"
                ),
                location=f"$.source.{field}",
            )
    validate_implementation_mapping_result(
        mapping_result,
        request=mapping_result.request,
        bundle=bundle,
        current_inventory=current_inventory,
        initialized_adapter=mapping_initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    mapping_comparisons = (
        ("target_id", request.mapping.target_id, mapping_result.id),
        (
            "canonical_digest",
            request.mapping.canonical_digest,
            canonical_implementation_evidence_digest(mapping_result),
        ),
    )
    for field, actual, expected in mapping_comparisons:
        if actual != expected:
            _fail(
                ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
                (
                    f"verification mapping {field} differs from the "
                    "accepted result"
                ),
                location=f"$.mapping.{field}",
            )

    behavior_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_ir_json(bundle.behavior).encode("ascii")
        ).hexdigest(),
    )
    behavior_comparisons = (
        (
            "document_id",
            request.base_behavior.document_id,
            bundle.behavior.document_id,
        ),
        (
            "ir_version",
            request.base_behavior.ir_version,
            bundle.behavior.ir_version,
        ),
        (
            "canonical_digest",
            request.base_behavior.canonical_digest,
            behavior_digest,
        ),
    )
    for field, actual, expected in behavior_comparisons:
        if actual != expected:
            _fail(
                ImplementationEvidenceErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                f"verification base Behavior {field} differs from the bundle",
                location=f"$.base_behavior.{field}",
            )

    entities = {entity.id: entity for entity in bundle.behavior.entities}
    subject_entity = entities.get(request.subject.target_id)
    if subject_entity is None:
        _fail(
            ImplementationEvidenceErrorCode.BROKEN_REFERENCE,
            "verification subject does not resolve in the base behavior",
            location="$.subject",
        )
    if subject_entity.kind is not request.subject.target_kind:
        _fail(
            ImplementationEvidenceErrorCode.WRONG_TARGET_KIND,
            "verification subject kind differs from the resolved entity",
            location="$.subject.target_kind",
        )
    binding = next(
        (
            candidate
            for candidate in mapping_result.bindings
            if candidate.behavior == request.subject
        ),
        None,
    )
    if binding is None:
        _fail(
            ImplementationEvidenceErrorCode.TARGET_NOT_MAPPED,
            "verification subject has no accepted implementation binding",
            location="$.subject",
        )
    _validate_port_values(
        request.inputs,
        ports=subject_entity.input_ports,
        location="$.inputs",
    )
    _validate_port_values(
        request.expected_outputs,
        ports=subject_entity.output_ports,
        location="$.expected_outputs",
    )

    source_comparisons = (
        (
            "subject_uri",
            request.source.subject_uri,
            mapping_result.request.inventory.subject_uri,
        ),
        (
            "source_revision",
            request.source.source_revision,
            mapping_result.request.inventory.source_revision,
        ),
        ("records", request.source.records, binding.source_records),
    )
    for field, actual, expected in source_comparisons:
        if actual != expected:
            _fail(
                ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
                f"verification source {field} differs from its mapping",
                location=f"$.source.{field}",
            )
    if (
        current_inventory.subject_uri != request.source.subject_uri
        or current_inventory.source_revision
        != request.source.source_revision
        or current_inventory != mapping_result.request.inventory
    ):
        _fail(
            ImplementationEvidenceErrorCode.SOURCE_IDENTITY_MISMATCH,
            "current inventory differs from the verification source",
            location="$.source.source_revision",
        )
    selected_version = negotiated_capabilities.get(
        request.capability.name
    )
    if selected_version != request.capability.version:
        _fail(
            ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH,
            "the exact verification capability was not selected",
            location="$.capability",
        )
    _revalidate_model(request, ExecutionVerificationRequest)


def validate_execution_verification_result(
    result: ExecutionVerificationResult,
    *,
    request: ExecutionVerificationRequest,
    mapping_result: ImplementationMappingResult,
    bundle: OnboardingBundle,
    current_inventory: InventorySnapshot,
    mapping_initialized_adapter: Producer,
    initialized_adapter: Producer,
    negotiated_capabilities: Mapping[str, str],
) -> None:
    if result.id != derive_execution_verification_result_id(result):
        _fail(
            ImplementationEvidenceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "verification result ID is not derived from its exact content",
            location="$.id",
        )
    if result.request != request:
        _fail(
            ImplementationEvidenceErrorCode.REQUEST_IDENTITY_MISMATCH,
            "verification result does not echo the exact request",
            location="$.request",
        )
    validate_execution_verification_request(
        request,
        mapping_result=mapping_result,
        bundle=bundle,
        current_inventory=current_inventory,
        mapping_initialized_adapter=mapping_initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    if result.producer != initialized_adapter:
        _fail(
            ImplementationEvidenceErrorCode.PRODUCER_IDENTITY_MISMATCH,
            "verification result producer differs from the initialized adapter",
            location="$.producer",
        )
    selected_version = negotiated_capabilities.get(
        request.capability.name
    )
    if (
        result.capability != request.capability
        or selected_version != request.capability.version
    ):
        _fail(
            ImplementationEvidenceErrorCode.CAPABILITY_MISMATCH,
            "the exact verification capability was not selected",
            location="$.capability",
        )
    if result.procedure_uri != request.adapter_procedure_uri:
        _fail(
            ImplementationEvidenceErrorCode.PROCEDURE_MISMATCH,
            "verification result procedure differs from the request",
            location="$.procedure_uri",
        )
    _revalidate_model(result, ExecutionVerificationResult)


def _validate_port_values(
    values,
    *,
    ports: tuple[Port, ...],
    location: str,
) -> None:
    port_index = {port.name: port for port in ports}
    supplied_names = {item.port.name for item in values}
    required_names = {port.name for port in ports if port.required}
    for position, item in enumerate(values):
        item_location = f"{location}[{position}]"
        port = port_index.get(item.port.name)
        if port is None:
            _fail(
                ImplementationEvidenceErrorCode.UNKNOWN_PORT,
                "verification value names an unknown behavior port",
                location=f"{item_location}.port.name",
            )
        actual_kind = ValueKind(item.value.kind)
        if (
            actual_kind is ValueKind.NULL
            and port.required
            or actual_kind is not ValueKind.NULL
            and actual_kind is not port.value_kind
        ):
            _fail(
                ImplementationEvidenceErrorCode.VALUE_KIND_MISMATCH,
                "verification value kind differs from the behavior port",
                location=f"{item_location}.value",
            )
    if not required_names.issubset(supplied_names):
        _fail(
            ImplementationEvidenceErrorCode.INCOMPLETE_BINDING,
            "verification values omit a required behavior port",
            location=location,
        )


def _revalidate_model[ModelT: IRModel](
    value: ModelT,
    model_type: type[ModelT],
) -> ModelT:
    try:
        return model_type.model_validate_json(
            json.dumps(
                value.model_dump(mode="json", warnings=False),
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            )
        )
    except (AttributeError, PydanticValidationError, TypeError, ValueError) as error:
        _fail(
            ImplementationEvidenceErrorCode.INVALID_STRUCTURE,
            "document does not satisfy its closed structural profile",
            location="$",
        )
        raise AssertionError("unreachable") from error


def _fail(
    code: ImplementationEvidenceErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise ImplementationEvidenceValidationError(
        code,
        message,
        location=location,
    )
