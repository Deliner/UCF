from __future__ import annotations

import asyncio
import base64
import json
import sys

from tests.change_lifecycle._fixture_factory import (
    proposal as lifecycle_proposal,
)
from tests.ecosystems.test_python_legacy_quote_mapping import (
    _mapping_request,
    _reviewed_bundle,
)
from tests.ecosystems.test_python_legacy_quote_verification import (
    _verification_request,
)
from tests.inventory.reference_adapter_harness import (
    nonfollowing_tree_manifest,
)
from tests.onboarding.test_process_client import (
    FIXTURE_ROOT,
    REFERENCE_ADAPTER,
)
from tests.onboarding.test_process_client import (
    _request as _inventory_request,
)
from ucf.adapter_protocol import (
    AdapterProcess,
    CapabilityRequest,
    Method,
)
from ucf.change_lifecycle import (
    ExecutionEvidenceContext,
    ModifiedBehavior,
    OpenSpecArtifactRole,
    TaskStatus,
    canonical_change_lifecycle_json,
    complete_change_task,
    delta_subject_ref,
    derive_archive_record,
    derive_behavior_delta,
    derive_implementation_record,
    derive_task_graph,
    derive_verification_record,
    validate_archive_record,
    validate_behavior_delta,
    validate_change_proposal,
    validate_implementation_record,
    validate_task_graph,
    validate_verification_record,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    execution_verification_request_to_payload,
    execution_verification_result_from_payload,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    project_execution_verification,
    validate_execution_verification_result,
    validate_implementation_mapping_result,
)
from ucf.inventory import INVENTORY_CAPABILITY, collect_inventory_from_process
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.trust_models import Claim, ClaimLevel

_SCRIPTED_TASK_IDS = ("task.1-1", "task.1-2", "task.1-3")


def _authored_base_with_optional_total(final_behavior):
    payload = json.loads(canonical_ir_json(final_behavior))
    quote_order = next(
        entity
        for entity in payload["entities"]
        if entity["kind"] == "use_case"
        and entity["id"] == "use-case.quote-order"
    )
    total = next(
        port
        for port in quote_order["output_ports"]
        if port["name"] == "total-cents"
    )
    if total["required"] is not True:
        raise AssertionError("reviewed quote-order total must be required")
    total["required"] = False
    return parse_ir_json(json.dumps(payload))


def _required_total(payload: dict) -> bool:
    quote_order = next(
        entity
        for entity in payload["entities"]
        if entity["kind"] == "use_case"
        and entity["id"] == "use-case.quote-order"
    )
    return next(
        port["required"]
        for port in quote_order["output_ports"]
        if port["name"] == "total-cents"
    )


async def _run_real_python_evidence(bundle, mapping_request):
    adapter = AdapterProcess(
        command=(
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(REFERENCE_ADAPTER),
        ),
        cwd=FIXTURE_ROOT,
        requested_capabilities=tuple(
            CapabilityRequest(
                kind="capability_request",
                name=name,
                minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                required=True,
            )
            for name in (
                INVENTORY_CAPABILITY,
                IMPLEMENTATION_MAPPING_CAPABILITY,
                EXECUTION_VERIFICATION_CAPABILITY,
            )
        ),
    )
    try:
        initialized = await adapter.start()
        inventory = await collect_inventory_from_process(
            adapter,
            request=_inventory_request(7),
            operation_timeout=5.0,
        )
        mapping = implementation_mapping_result_from_payload(
            await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=5.0,
            )
        )
        verification_request = _verification_request(
            root_path=FIXTURE_ROOT,
            inventory=inventory.model_dump(mode="json"),
            bundle=bundle,
            mapping=mapping,
        )
        result = execution_verification_result_from_payload(
            await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(
                    verification_request
                ),
                timeout=10.0,
            )
        )
        negotiated_capabilities = dict(adapter.negotiated_capabilities)
        stderr_total_bytes = adapter.stderr_total_bytes
    finally:
        await adapter.close()
    return (
        initialized.adapter,
        negotiated_capabilities,
        inventory,
        mapping,
        verification_request,
        result,
        stderr_total_bytes,
    )


def _derive_scripted_lifecycle(base_behavior, final_behavior, context):
    proposal = lifecycle_proposal(base_behavior)
    validate_change_proposal(proposal, base_behavior)
    delta = derive_behavior_delta(proposal, base_behavior, final_behavior)
    validate_behavior_delta(delta, proposal, base_behavior, final_behavior)
    subject = delta_subject_ref(delta.entries[0])
    graph = derive_task_graph(
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        subject_assignments={task_id: (subject,) for task_id in _SCRIPTED_TASK_IDS},
        dependencies={
            "task.1-1": (),
            "task.1-2": ("task.1-1",),
            "task.1-3": ("task.1-2",),
        },
    )
    transitions = [graph]
    for task_id in _SCRIPTED_TASK_IDS:
        graph = complete_change_task(
            graph,
            task_id,
            delta=delta,
            proposal=proposal,
            base_behavior=base_behavior,
            final_behavior=final_behavior,
        )
        transitions.append(graph)
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    contexts = (context,)
    implementation = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=contexts,
    )
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=contexts,
    )
    verification = derive_verification_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=contexts,
    )
    validate_verification_record(
        verification,
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=contexts,
    )
    archive = derive_archive_record(
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base_behavior,
        final_behavior,
        evidence_contexts=contexts,
    )
    validate_archive_record(
        archive,
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base_behavior,
        final_behavior,
        evidence_contexts=contexts,
    )
    return (
        proposal,
        delta,
        graph,
        implementation,
        verification,
        archive,
    ), tuple(transitions)


def test_python_quote_order_runs_an_evidence_backed_scripted_lifecycle() -> None:
    fixture_manifest = nonfollowing_tree_manifest(FIXTURE_ROOT)
    bundle = _reviewed_bundle()
    final_behavior = bundle.behavior
    base_behavior = _authored_base_with_optional_total(final_behavior)

    base_payload = json.loads(canonical_ir_json(base_behavior))
    final_payload = json.loads(canonical_ir_json(final_behavior))
    assert _required_total(base_payload) is False
    assert _required_total(final_payload) is True
    quote_order = next(
        entity
        for entity in base_payload["entities"]
        if entity["kind"] == "use_case"
        and entity["id"] == "use-case.quote-order"
    )
    next(
        port
        for port in quote_order["output_ports"]
        if port["name"] == "total-cents"
    )["required"] = True
    assert base_payload == final_payload

    mapping_request = _mapping_request(bundle)
    (
        initialized_adapter,
        negotiated_capabilities,
        inventory,
        mapping,
        verification_request,
        result,
        stderr_total_bytes,
    ) = asyncio.run(_run_real_python_evidence(bundle, mapping_request))
    assert inventory == bundle.inventory
    assert mapping.request == mapping_request
    assert result.request == verification_request
    assert result.outcome == "passed"
    assert stderr_total_bytes == 0
    validate_implementation_mapping_result(
        mapping,
        request=mapping_request,
        bundle=bundle,
        current_inventory=inventory,
        initialized_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    validate_execution_verification_result(
        result,
        request=verification_request,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=inventory,
        mapping_initialized_adapter=initialized_adapter,
        initialized_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    projection = project_execution_verification(
        result,
        request=verification_request,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=inventory,
        mapping_initialized_adapter=initialized_adapter,
        initialized_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    claims = tuple(
        record
        for record in projection.tested_trust.records
        if isinstance(record, Claim)
    )
    assert sum(claim.level is ClaimLevel.TESTED for claim in claims) == 1
    assert sum(claim.level is ClaimLevel.VERIFIED for claim in claims) == 0

    context = ExecutionEvidenceContext(
        result=result,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=inventory,
        mapping_initialized_adapter=initialized_adapter,
        initialized_adapter=initialized_adapter,
        negotiated_capabilities=negotiated_capabilities,
    )
    first_resources, first_transitions = _derive_scripted_lifecycle(
        base_behavior,
        final_behavior,
        context,
    )
    second_resources, second_transitions = _derive_scripted_lifecycle(
        base_behavior,
        final_behavior,
        context,
    )
    proposal, delta, graph, implementation, verification, archive = (
        first_resources
    )

    assert len(delta.entries) == 1
    modified = delta.entries[0]
    assert isinstance(modified, ModifiedBehavior)
    assert modified.base_subject.target_id == "use-case.quote-order"
    assert modified.final_subject.target_id == "use-case.quote-order"
    assert modified.aspects == ("definition",)
    assert [
        (
            task.id,
            task.order,
            tuple(item.target_id for item in task.depends_on),
        )
        for task in first_transitions[0].tasks
    ] == [
        ("task.1-1", 1, ()),
        ("task.1-2", 2, ("task.1-1",)),
        ("task.1-3", 3, ("task.1-2",)),
    ]
    assert tuple(
        tuple(task.status for task in transition.tasks)
        for transition in first_transitions
    ) == (
        (TaskStatus.PENDING, TaskStatus.PENDING, TaskStatus.PENDING),
        (TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.PENDING),
        (TaskStatus.COMPLETED, TaskStatus.COMPLETED, TaskStatus.PENDING),
        (TaskStatus.COMPLETED, TaskStatus.COMPLETED, TaskStatus.COMPLETED),
    )
    tasks_artifact = next(
        artifact
        for artifact in proposal.openspec.artifacts
        if artifact.role is OpenSpecArtifactRole.TASKS
    )
    scripted_task_text = base64.b64decode(tasks_artifact.content_base64).decode(
        "utf-8"
    )
    assert "human approval" not in scripted_task_text.casefold()
    assert implementation.bindings[0].result == result
    assert implementation.bindings[0].validation.assurance == (
        "context_validated_import"
    )
    assert verification.outcome == "accepted"
    assert archive.status == "archived"
    assert archive.final_behavior == final_behavior
    assert all(task.status is TaskStatus.COMPLETED for task in graph.tasks)

    assert tuple(
        canonical_change_lifecycle_json(resource)
        for resource in first_resources
    ) == tuple(
        canonical_change_lifecycle_json(resource)
        for resource in second_resources
    )
    assert tuple(
        canonical_change_lifecycle_json(graph_version)
        for graph_version in first_transitions
    ) == tuple(
        canonical_change_lifecycle_json(graph_version)
        for graph_version in second_transitions
    )
    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == fixture_manifest
