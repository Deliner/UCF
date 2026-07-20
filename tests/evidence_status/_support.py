from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any

from tests.onboarding.test_bundle import _bundle
from tests.onboarding.test_candidates import _proposal
from ucf.adapter_protocol import CapabilitySelection
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    EXECUTION_VERIFICATION_PROCEDURE_URI,
    EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    IMPLEMENTATION_MAPPING_PROCEDURE_URI,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
    ExecutionEnvironment,
    ExecutionPortValue,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationBinding,
    ImplementationMappingRequest,
    ImplementationMappingResult,
    ImplementationMappingResultRef,
    ImplementationSource,
    OnboardingBundleBinding,
    canonical_implementation_evidence_digest,
    derive_execution_verification_result_id,
    derive_implementation_mapping_result_id,
)
from ucf.inventory import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    InventoryProvenance,
    InventoryRecordKind,
    InventoryRecordRef,
    InventorySnapshot,
    PublicInterfaceFact,
    RepositoryEntryFact,
    canonical_inventory_json,
    derive_inventory_record_id,
    derive_inventory_source_revision,
)
from ucf.ir.models import (
    Check,
    Digest,
    EntityRef,
    IntegerValue,
    Port,
    PortRef,
    Producer,
    ValueKind,
)
from ucf.ir.trust_models import BehaviorDocumentRef
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateProposal,
    CandidateRef,
    DiscoveryDocumentRef,
    EditedDecision,
    InventoryBinding,
    OnboardingBundle,
    ProposedAction,
    ProposedUseCase,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    derive_candidate_semantic_digest,
    derive_decision_id,
    derive_discovery_candidate_id,
)

_ZERO = "0" * 64
_MAPPING_PROCEDURE = "urn:ucf:fixture-adapter:implementation-mapping:1.0.0"
_VERIFICATION_PROCEDURE = "urn:ucf:fixture-adapter:execute-quote-order:1.0.0"


@dataclass(frozen=True)
class EvidenceContext:
    bundle: OnboardingBundle
    mapping_result: ImplementationMappingResult
    request: ExecutionVerificationRequest
    result: ExecutionVerificationResult
    mapping_initialized_adapter: Producer
    initialized_adapter: Producer
    negotiated_capabilities: dict[str, str]


def baseline_context(
    outcome: str = "passed",
) -> EvidenceContext:
    return context_for_bundle(_bundle(), outcome=outcome)


def context_for_bundle(
    bundle: OnboardingBundle,
    *,
    outcome: str = "passed",
    mapping_producer: Producer | None = None,
    mapping_procedure: str = _MAPPING_PROCEDURE,
    verification_producer: Producer | None = None,
    verification_procedure: str = _VERIFICATION_PROCEDURE,
) -> EvidenceContext:
    mapping_producer = mapping_producer or Producer(
        kind="producer",
        name="org.ucf.fixture-adapter",
        version="1.0.0",
    )
    verification_producer = verification_producer or Producer(
        kind="producer",
        name="org.ucf.fixture-adapter",
        version="1.0.0",
    )
    mapping_result = _mapping_result(
        bundle,
        producer=mapping_producer,
        procedure_uri=mapping_procedure,
    )
    request = _verification_request(
        bundle,
        mapping_result,
        procedure_uri=verification_procedure,
    )
    result = _verification_result(
        request,
        producer=verification_producer,
        outcome=outcome,
    )
    return EvidenceContext(
        bundle=bundle,
        mapping_result=mapping_result,
        request=request,
        result=result,
        mapping_initialized_adapter=mapping_producer,
        initialized_adapter=verification_producer,
        negotiated_capabilities={
            IMPLEMENTATION_MAPPING_CAPABILITY: (IMPLEMENTATION_EVIDENCE_VERSION),
            EXECUTION_VERIFICATION_CAPABILITY: (IMPLEMENTATION_EVIDENCE_VERSION),
        },
    )


def record_arguments(context: EvidenceContext) -> dict[str, Any]:
    return {
        "request": context.request,
        "mapping_result": context.mapping_result,
        "bundle": context.bundle,
        "current_inventory": context.bundle.inventory,
        "mapping_initialized_adapter": (context.mapping_initialized_adapter),
        "initialized_adapter": context.initialized_adapter,
        "negotiated_capabilities": context.negotiated_capabilities,
    }


def recorded_assessment_arguments(
    context: EvidenceContext,
) -> dict[str, Any]:
    return {
        "recorded_result": context.result,
        "recorded_request": context.request,
        "recorded_mapping_result": context.mapping_result,
        "recorded_bundle": context.bundle,
        "recorded_current_inventory": context.bundle.inventory,
        "recorded_mapping_initialized_adapter": (context.mapping_initialized_adapter),
        "recorded_initialized_adapter": context.initialized_adapter,
        "recorded_negotiated_capabilities": (context.negotiated_capabilities),
    }


def current_assessment_arguments(
    context: EvidenceContext,
) -> dict[str, Any]:
    return {
        "current_result": context.result,
        "current_request": context.request,
        "current_mapping_result": context.mapping_result,
        "current_bundle": context.bundle,
        "current_inventory": context.bundle.inventory,
        "current_mapping_initialized_adapter": (context.mapping_initialized_adapter),
        "current_initialized_adapter": context.initialized_adapter,
        "current_negotiated_capabilities": (context.negotiated_capabilities),
    }


def status_value(value: object) -> str:
    return str(getattr(value, "value", value))


def reason_codes(assessment: object) -> tuple[str, ...]:
    return tuple(status_value(reason.code) for reason in getattr(assessment, "reasons"))


def unrelated_inventory_context() -> EvidenceContext:
    original = _bundle()
    inventory = _inventory_with_unrelated_file(original.inventory)
    return context_for_bundle(_bundle_for_inventory(original, inventory))


def target_source_context() -> EvidenceContext:
    original = _bundle()
    inventory = _inventory_with_target_change(original.inventory)
    return context_for_bundle(_bundle_for_inventory(original, inventory))


def unrelated_behavior_context() -> EvidenceContext:
    original = _bundle()
    candidates = {
        candidate.id: candidate for candidate in original.discovery.candidates
    }

    def replacement(decision: object) -> object:
        candidate = candidates[decision.candidate.candidate_id]
        if candidate.proposal.root.target_id != "use-case.normalize-coupon":
            return decision
        return AcceptedDecision(
            kind="accepted_decision",
            id=f"decision.{_ZERO}",
            candidate=decision.candidate,
            reason="Reviewed as an unrelated user behavior.",
        )

    decisions = _replace_decisions(original, replacement)
    return context_for_bundle(
        build_onboarding_bundle(
            original.inventory,
            original.discovery,
            decisions,
        )
    )


def target_behavior_context() -> EvidenceContext:
    original = _bundle()
    candidates = {
        candidate.id: candidate for candidate in original.discovery.candidates
    }
    changed_proposal = _proposal_with_optional_output("quote-order")

    def replacement(decision: object) -> object:
        candidate = candidates[decision.candidate.candidate_id]
        if candidate.proposal.root.target_id != "use-case.quote-order":
            return decision
        return EditedDecision(
            kind="edited_decision",
            id=f"decision.{_ZERO}",
            candidate=decision.candidate,
            reason="Review establishes an additional optional output.",
            replacement_digest=derive_candidate_semantic_digest(changed_proposal),
            replacement=changed_proposal,
        )

    decisions = _replace_decisions(original, replacement)
    return context_for_bundle(
        build_onboarding_bundle(
            original.inventory,
            original.discovery,
            decisions,
        )
    )


def inventory_adapter_context() -> EvidenceContext:
    original = _bundle()
    snapshot = original.inventory
    producer = Producer(
        kind="producer",
        name="org.ucf.replacement-inventory-adapter",
        version="2.0.0",
    )
    provenance_by_id = {}
    for record in snapshot.records:
        if isinstance(record, InventoryProvenance):
            provenance_by_id[record.id] = _identified(
                record.model_copy(update={"producer": producer})
            )
    entry_by_id = {}
    for record in snapshot.records:
        if isinstance(record, RepositoryEntryFact):
            entry_by_id[record.id] = _identified(
                record.model_copy(
                    update={
                        "provenance": _record_ref(
                            provenance_by_id[record.provenance.target_id]
                        )
                    }
                )
            )
    records = []
    for record in snapshot.records:
        if isinstance(record, InventoryProvenance):
            records.append(provenance_by_id[record.id])
        elif isinstance(record, RepositoryEntryFact):
            records.append(entry_by_id[record.id])
        elif isinstance(record, PublicInterfaceFact):
            records.append(
                _identified(
                    record.model_copy(
                        update={
                            "provenance": _record_ref(
                                provenance_by_id[
                                    record.provenance.target_id
                                ]
                            ),
                            "entry": _record_ref(
                                entry_by_id[record.entry.target_id]
                            ),
                        }
                    )
                )
            )
        else:
            raise AssertionError(
                f"unsupported inventory-adapter fixture record {record.kind}"
            )
    ordered = tuple(
        sorted(records, key=lambda record: (record.kind, record.id))
    )
    inventory = InventorySnapshot(
        kind=snapshot.kind,
        inventory_version=snapshot.inventory_version,
        schema_uri=snapshot.schema_uri,
        subject_uri=snapshot.subject_uri,
        path_identity=snapshot.path_identity,
        source_revision=derive_inventory_source_revision(ordered),
        producer=producer,
        capability=snapshot.capability,
        applied_policy=snapshot.applied_policy,
        coverage=snapshot.coverage,
        records=ordered,
    )
    return context_for_bundle(_bundle_for_inventory(original, inventory))


def mapping_adapter_context() -> EvidenceContext:
    return context_for_bundle(
        _bundle(),
        mapping_producer=Producer(
            kind="producer",
            name="org.ucf.replacement-mapping-adapter",
            version="2.0.0",
        ),
    )


def mapping_procedure_context() -> EvidenceContext:
    return context_for_bundle(
        _bundle(),
        mapping_procedure=("urn:ucf:replacement-adapter:implementation-mapping:2.0.0"),
    )


def verification_adapter_context() -> EvidenceContext:
    return context_for_bundle(
        _bundle(),
        verification_producer=Producer(
            kind="producer",
            name="org.ucf.replacement-verification-adapter",
            version="2.0.0",
        ),
    )


def verification_procedure_context() -> EvidenceContext:
    return context_for_bundle(
        _bundle(),
        verification_procedure=(
            "urn:ucf:replacement-adapter:execute-quote-order:2.0.0"
        ),
    )


def changed_capability_context(
    capability: str,
) -> EvidenceContext:
    context = baseline_context()
    capabilities = dict(context.negotiated_capabilities)
    capabilities[capability] = "2.0.0"
    return replace(
        context,
        negotiated_capabilities=capabilities,
    )


def changed_environment_context() -> EvidenceContext:
    context = baseline_context()
    request = context.request.model_copy(
        update={
            "environment": ExecutionEnvironment(
                kind="execution_environment",
                identity_uri=(
                    "urn:ucf:fixture-environment:node24-linux-loopback:2.0.0"
                ),
                revision=_filled_digest("f"),
            )
        }
    )
    return _context_with_request(context, request)


def changed_check_context() -> EvidenceContext:
    context = baseline_context()
    request = context.request.model_copy(
        update={
            "check": Check(
                kind="check",
                id="check.quote-order.replacement",
                version="2.0.0",
                procedure_uri=("urn:ucf:fixture-check:quote-order-replacement:2.0.0"),
            )
        }
    )
    return _context_with_request(context, request)


def changed_input_context() -> EvidenceContext:
    context = baseline_context()
    first = context.request.inputs[0]
    request = context.request.model_copy(
        update={
            "inputs": (
                first.model_copy(
                    update={
                        "value": IntegerValue(
                            kind="integer",
                            value=3,
                        )
                    }
                ),
                *context.request.inputs[1:],
            )
        }
    )
    return _context_with_request(context, request)


def changed_expected_output_context() -> EvidenceContext:
    context = baseline_context()
    first = context.request.expected_outputs[0]
    request = context.request.model_copy(
        update={
            "expected_outputs": (
                first.model_copy(
                    update={
                        "value": IntegerValue(
                            kind="integer",
                            value=2501,
                        )
                    }
                ),
                *context.request.expected_outputs[1:],
            )
        }
    )
    return _context_with_request(context, request)


def _context_with_request(
    context: EvidenceContext,
    request: ExecutionVerificationRequest,
) -> EvidenceContext:
    result = _verification_result(
        request,
        producer=context.initialized_adapter,
        outcome=context.result.outcome,
    )
    return replace(context, request=request, result=result)


def _mapping_result(
    bundle: OnboardingBundle,
    *,
    producer: Producer,
    procedure_uri: str,
) -> ImplementationMappingResult:
    request = ImplementationMappingRequest(
        kind="implementation_mapping_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=IMPLEMENTATION_MAPPING_PROCEDURE_URI,
        adapter_procedure_uri=procedure_uri,
        onboarding=OnboardingBundleBinding(
            kind="onboarding_bundle_binding",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        behavior=bundle.behavior,
        inventory=bundle.inventory,
        targets=tuple(
            sorted(
                (
                    materialization.root
                    for materialization in bundle.baseline.materializations
                ),
                key=_behavior_ref_key,
            )
        ),
    )
    materializations = {
        materialization.root: materialization
        for materialization in bundle.baseline.materializations
    }
    candidates = {candidate.id: candidate for candidate in bundle.discovery.candidates}
    bindings = tuple(
        ImplementationBinding(
            kind="implementation_binding",
            behavior=target,
            source_records=candidates[
                materializations[target].candidate.candidate_id
            ].evidence,
        )
        for target in request.targets
    )
    provisional = ImplementationMappingResult(
        kind="implementation_mapping_result",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
        id=f"mapping.{_ZERO}",
        status="complete",
        request=request,
        producer=producer,
        capability=request.capability,
        procedure_uri=procedure_uri,
        bindings=bindings,
    )
    return provisional.model_copy(
        update={"id": derive_implementation_mapping_result_id(provisional)}
    )


def _verification_request(
    bundle: OnboardingBundle,
    mapping: ImplementationMappingResult,
    *,
    procedure_uri: str,
) -> ExecutionVerificationRequest:
    binding = next(
        binding
        for binding in mapping.bindings
        if binding.behavior.target_id == "use-case.quote-order"
    )
    subject = next(
        entity
        for entity in bundle.behavior.entities
        if entity.id == binding.behavior.target_id
    )
    owner = EntityRef(
        kind="entity_ref",
        target_kind=binding.behavior.target_kind,
        target_id=binding.behavior.target_id,
    )
    return ExecutionVerificationRequest(
        kind="execution_verification_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=EXECUTION_VERIFICATION_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=EXECUTION_VERIFICATION_PROCEDURE_URI,
        adapter_procedure_uri=procedure_uri,
        mapping=ImplementationMappingResultRef(
            kind="implementation_mapping_result_ref",
            schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
            schema_version=IMPLEMENTATION_EVIDENCE_VERSION,
            target_id=mapping.id,
            canonical_digest=canonical_implementation_evidence_digest(mapping),
        ),
        base_behavior=BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id=binding.behavior.document_id,
            ir_version=binding.behavior.ir_version,
            canonical_digest=binding.behavior.canonical_digest,
        ),
        subject=binding.behavior,
        inputs=tuple(
            _integer_port_value(
                owner,
                port,
                direction="input",
                value=2,
            )
            for port in subject.input_ports
            if port.required
        ),
        expected_outputs=tuple(
            _integer_port_value(
                owner,
                port,
                direction="output",
                value=2500,
            )
            for port in subject.output_ports
            if port.required
        ),
        source=ImplementationSource(
            kind="implementation_source",
            subject_uri=mapping.request.inventory.subject_uri,
            source_revision=mapping.request.inventory.source_revision,
            records=binding.source_records,
        ),
        environment=ExecutionEnvironment(
            kind="execution_environment",
            identity_uri=("urn:ucf:fixture-environment:node22-linux-loopback:1.0.0"),
            revision=_filled_digest("e"),
        ),
        check=Check(
            kind="check",
            id="check.quote-order.real-http",
            version="1.0.0",
            procedure_uri=("urn:ucf:fixture-check:quote-order-http-contract:1.0.0"),
        ),
    )


def _verification_result(
    request: ExecutionVerificationRequest,
    *,
    producer: Producer,
    outcome: str,
) -> ExecutionVerificationResult:
    provisional = ExecutionVerificationResult(
        kind="execution_verification_result",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=("urn:ucf:adapter:execution-verification-result:1.0.0"),
        id=f"result.{_ZERO}",
        status="completed",
        request=request,
        outcome=outcome,
        executed_at="2026-07-19T15:00:00Z",
        producer=producer,
        capability=request.capability,
        procedure_uri=request.adapter_procedure_uri,
    )
    return provisional.model_copy(
        update={"id": derive_execution_verification_result_id(provisional)}
    )


def _integer_port_value(
    owner: EntityRef,
    port: Port,
    *,
    direction: str,
    value: int,
) -> ExecutionPortValue:
    if port.value_kind is not ValueKind.INTEGER:
        raise AssertionError(f"fixture port {port.name!r} is not integer-valued")
    return ExecutionPortValue(
        kind="execution_port_value",
        port=PortRef(
            kind="port_ref",
            owner=owner,
            direction=direction,
            name=port.name,
        ),
        value=IntegerValue(kind="integer", value=value),
    )


def _bundle_for_inventory(
    original: OnboardingBundle,
    inventory: InventorySnapshot,
) -> OnboardingBundle:
    binding = InventoryBinding(
        kind="inventory_binding",
        schema_uri=INVENTORY_SCHEMA_URI,
        inventory_version=INVENTORY_VERSION,
        subject_uri=inventory.subject_uri,
        source_revision=inventory.source_revision,
        canonical_digest=_digest_bytes(canonical_inventory_json(inventory)),
    )
    old_interface = next(
        record
        for record in original.inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    new_interface = next(
        record
        for record in inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    old_ref = _record_ref(old_interface)
    new_ref = _record_ref(new_interface)
    discovery_shell = original.discovery.model_copy(
        update={
            "inventory_binding": binding,
            "candidates": (),
        }
    )
    candidates = []
    for candidate in original.discovery.candidates:
        subject = new_ref if candidate.subject == old_ref else candidate.subject
        evidence = tuple(
            new_ref if reference == old_ref else reference
            for reference in candidate.evidence
        )
        provisional = candidate.model_copy(
            update={
                "id": f"candidate.{_ZERO}",
                "subject": subject,
                "evidence": evidence,
            }
        )
        candidates.append(
            provisional.model_copy(
                update={
                    "id": derive_discovery_candidate_id(
                        provisional,
                        discovery_shell,
                    )
                }
            )
        )
    coverage = original.discovery.coverage.model_copy(
        update={
            "eligible_subjects": tuple(
                new_ref if reference == old_ref else reference
                for reference in (original.discovery.coverage.eligible_subjects)
            ),
            "uncovered_subjects": tuple(
                new_ref if reference == old_ref else reference
                for reference in (original.discovery.coverage.uncovered_subjects)
            ),
        }
    )
    discovery = discovery_shell.model_copy(
        update={
            "coverage": coverage,
            "candidates": tuple(sorted(candidates, key=lambda candidate: candidate.id)),
        }
    )
    decisions = _rebind_decisions(
        original,
        discovery,
        binding,
    )
    return build_onboarding_bundle(inventory, discovery, decisions)


def _rebind_decisions(
    original: OnboardingBundle,
    discovery: object,
    binding: InventoryBinding,
) -> object:
    discovery_digest = canonical_onboarding_digest(discovery)
    base = original.decisions.model_copy(
        update={
            "discovery": DiscoveryDocumentRef(
                kind="discovery_document_ref",
                schema_uri=discovery.schema_uri,
                schema_version=discovery.onboarding_version,
                canonical_digest=discovery_digest,
            ),
            "inventory_binding": binding,
            "decisions": (),
        }
    )
    original_candidates = {
        candidate.id: candidate for candidate in original.discovery.candidates
    }
    current_candidates = {
        candidate.proposal.root.target_id: candidate
        for candidate in discovery.candidates
    }
    decisions = []
    for decision in original.decisions.decisions:
        root_id = original_candidates[
            decision.candidate.candidate_id
        ].proposal.root.target_id
        candidate = current_candidates[root_id]
        changed = decision.model_copy(
            update={
                "id": f"decision.{_ZERO}",
                "candidate": CandidateRef(
                    kind="candidate_ref",
                    discovery_digest=discovery_digest,
                    candidate_id=candidate.id,
                    semantic_digest=candidate.semantic_digest,
                ),
            }
        )
        decisions.append(
            changed.model_copy(update={"id": derive_decision_id(changed, base)})
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    decisions,
                    key=lambda decision: decision.candidate.candidate_id,
                )
            )
        }
    )


def _replace_decisions(
    original: OnboardingBundle,
    transform: object,
) -> object:
    base = original.decisions.model_copy(update={"decisions": ()})
    decisions = []
    for decision in original.decisions.decisions:
        changed = transform(decision)
        changed = changed.model_copy(update={"id": f"decision.{_ZERO}"})
        decisions.append(
            changed.model_copy(update={"id": derive_decision_id(changed, base)})
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    decisions,
                    key=lambda decision: decision.candidate.candidate_id,
                )
            )
        }
    )


def _proposal_with_optional_output(
    suffix: str,
) -> CandidateProposal:
    original = _proposal(suffix)
    output = Port(
        kind="port",
        name="probe-output",
        value_kind=ValueKind.STRING,
        required=False,
    )
    entities = []
    for entity in original.entities:
        if isinstance(entity, (ProposedAction, ProposedUseCase)):
            entity = entity.model_copy(
                update={
                    "output_ports": tuple(
                        sorted(
                            (*entity.output_ports, output),
                            key=lambda port: port.name,
                        )
                    )
                }
            )
        entities.append(entity)
    return original.model_copy(update={"entities": tuple(entities)})


def _inventory_with_unrelated_file(
    snapshot: InventorySnapshot,
) -> InventorySnapshot:
    payload = b"def unrelated() -> int:\n    return 2\n"
    content_digest = _digest_bytes(payload)
    template_provenance = next(
        record
        for record in snapshot.records
        if isinstance(record, InventoryProvenance)
        and record.source_path == "src/service.py"
    )
    provenance = _identified(
        template_provenance.model_copy(
            update={
                "source_path": "src/unrelated.py",
                "content_digest": content_digest,
                "source_span": None,
            }
        )
    )
    template_entry = next(
        record
        for record in snapshot.records
        if isinstance(record, RepositoryEntryFact) and record.path == "src/service.py"
    )
    entry = _identified(
        template_entry.model_copy(
            update={
                "provenance": _record_ref(provenance),
                "path": "src/unrelated.py",
                "size_bytes": len(payload),
                "content_digest": content_digest,
            }
        )
    )
    return _rebuild_snapshot(
        snapshot,
        (*snapshot.records, provenance, entry),
        repository_entry_delta=1,
    )


def _inventory_with_target_change(
    snapshot: InventorySnapshot,
) -> InventorySnapshot:
    payload = b"def shorten(value: str) -> str:\n    return value + '!'\n"
    content_digest = _digest_bytes(payload)
    old_provenance = next(
        record
        for record in snapshot.records
        if isinstance(record, InventoryProvenance)
        and record.source_path == "src/service.py"
    )
    old_entry = next(
        record
        for record in snapshot.records
        if isinstance(record, RepositoryEntryFact) and record.path == "src/service.py"
    )
    old_interface = next(
        record
        for record in snapshot.records
        if isinstance(record, PublicInterfaceFact)
        and record.entry.target_id == old_entry.id
    )
    provenance = _identified(
        old_provenance.model_copy(
            update={
                "content_digest": content_digest,
                "source_span": None,
            }
        )
    )
    entry = _identified(
        old_entry.model_copy(
            update={
                "provenance": _record_ref(provenance),
                "size_bytes": len(payload),
                "content_digest": content_digest,
            }
        )
    )
    interface = _identified(
        old_interface.model_copy(
            update={
                "provenance": _record_ref(provenance),
                "entry": _record_ref(entry),
            }
        )
    )
    replacements = {
        old_provenance.id: provenance,
        old_entry.id: entry,
        old_interface.id: interface,
    }
    records = tuple(replacements.get(record.id, record) for record in snapshot.records)
    return _rebuild_snapshot(
        snapshot,
        records,
        repository_entry_delta=0,
    )


def _rebuild_snapshot(
    snapshot: InventorySnapshot,
    records: tuple[object, ...],
    *,
    repository_entry_delta: int,
) -> InventorySnapshot:
    ordered = tuple(sorted(records, key=lambda record: (record.kind, record.id)))
    coverage = tuple(
        item.model_copy(
            update={"record_count": (item.record_count + repository_entry_delta)}
        )
        if item.fact_kind is FactKind.REPOSITORY_ENTRY
        else item
        for item in snapshot.coverage
    )
    return InventorySnapshot(
        kind=snapshot.kind,
        inventory_version=snapshot.inventory_version,
        schema_uri=snapshot.schema_uri,
        subject_uri=snapshot.subject_uri,
        path_identity=snapshot.path_identity,
        source_revision=derive_inventory_source_revision(ordered),
        producer=snapshot.producer,
        capability=snapshot.capability,
        applied_policy=snapshot.applied_policy,
        coverage=coverage,
        records=ordered,
    )


def _identified(record: object) -> object:
    return record.model_copy(update={"id": derive_inventory_record_id(record)})


def _record_ref(record: object) -> InventoryRecordRef:
    return InventoryRecordRef(
        kind="inventory_record_ref",
        target_kind=InventoryRecordKind(record.kind),
        target_id=record.id,
    )


def _behavior_ref_key(reference: object) -> tuple[str, str]:
    return reference.target_kind.value, reference.target_id


def _filled_digest(fill: str) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=fill * 64,
    )


def _digest_bytes(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )
