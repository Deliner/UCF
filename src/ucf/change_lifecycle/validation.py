from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, cast

from pydantic import BaseModel, Field, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.change_lifecycle.behavior import validate_behavior_document
from ucf.change_lifecycle.codec import (
    behavior_delta_ref,
    canonical_change_lifecycle_json,
    change_proposal_ref,
    implementation_record_ref,
    task_graph_ref,
    verification_record_ref,
)
from ucf.change_lifecycle.errors import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
)
from ucf.change_lifecycle.models import (
    ARCHIVE_RECORD_SCHEMA_URI,
    BEHAVIOR_DELTA_SCHEMA_URI,
    CHANGE_LIFECYCLE_VERSION,
    EVIDENCE_CONTEXT_VALIDATION_PROCEDURE_URI,
    IMPLEMENTATION_RECORD_SCHEMA_URI,
    MAX_CHANGE_TASKS,
    TASK_GRAPH_SCHEMA_URI,
    VERIFICATION_RECORD_SCHEMA_URI,
    AddedBehavior,
    ArchiveRecord,
    BehaviorDelta,
    BehaviorDeltaEntry,
    ChangeProposal,
    ChangeTask,
    DeltaSubjectRef,
    EvidenceContextValidationReceipt,
    ImplementationEvidenceBinding,
    ImplementationRecord,
    ModifiedBehavior,
    OpenSpecArtifactRole,
    RemovedBehavior,
    TaskGraph,
    TaskRef,
    TaskSource,
    TaskStatus,
    VerificationRecord,
)
from ucf.implementation_evidence import (
    ExecutionVerificationResult,
    ImplementationEvidenceValidationError,
    ImplementationMappingResult,
    canonical_implementation_evidence_digest,
    validate_execution_verification_result,
)
from ucf.inventory import (
    InventorySnapshot,
    canonical_inventory_json,
)
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import BehaviorIR, Digest, EntityKind, Identifier, Producer
from ucf.ir.trust_models import BehaviorDocumentRef, BehaviorEntityRef
from ucf.onboarding import (
    OnboardingBundle,
    OnboardingValidationError,
    canonical_onboarding_digest,
)

_OPENSPEC_TASK = re.compile(r"^[-*]\s+\[([ xX])\]\s+([0-9]+(?:\.[0-9]+)*)\s+")
_BEHAVIOR_DELTA_ENTRY_ADAPTER = TypeAdapter(BehaviorDeltaEntry)
_EXECUTION_VERIFICATION_RESULT_ADAPTER = TypeAdapter(ExecutionVerificationResult)
_IMPLEMENTATION_MAPPING_RESULT_ADAPTER = TypeAdapter(ImplementationMappingResult)
_INVENTORY_SNAPSHOT_ADAPTER = TypeAdapter(InventorySnapshot)
_ONBOARDING_BUNDLE_ADAPTER = TypeAdapter(OnboardingBundle)
_PRODUCER_ADAPTER = TypeAdapter(Producer)
_DELTA_SUBJECT_ASSIGNMENT_ADAPTER = TypeAdapter(
    Annotated[
        tuple[DeltaSubjectRef, ...],
        Field(min_length=1),
    ]
)
_DEPENDENCY_IDS_ADAPTER = TypeAdapter(tuple[Identifier, ...])
_MAX_DIRECT_PYTHON_INPUT_DEPTH = 128
_MAX_IMPLEMENTATION_EVIDENCE_CONTEXTS = 256
_MAX_NEGOTIATED_CAPABILITIES = 256


@dataclass(frozen=True)
class ExecutionEvidenceContext:
    """Runtime inputs required to reproduce full execution-result validation."""

    result: ExecutionVerificationResult
    mapping_result: ImplementationMappingResult
    bundle: OnboardingBundle
    current_inventory: InventorySnapshot
    mapping_initialized_adapter: Producer
    initialized_adapter: Producer
    negotiated_capabilities: Mapping[str, str]


def validate_change_proposal(
    proposal: ChangeProposal,
    base_behavior: BehaviorIR,
) -> None:
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    base_behavior = _require_exact_runtime_type(
        base_behavior,
        BehaviorIR,
        location="$.base_behavior",
    )
    canonical_change_lifecycle_json(proposal)
    validate_behavior_document(
        base_behavior,
        location="$.base_behavior",
    )
    expected = _behavior_document_ref(base_behavior)
    if proposal.base_behavior != expected:
        _raise(
            ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "proposal base behavior does not match the supplied document",
            "$.base_behavior",
        )


def derive_behavior_delta(
    proposal: ChangeProposal,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> BehaviorDelta:
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    base_behavior = _require_exact_runtime_type(
        base_behavior,
        BehaviorIR,
        location="$.base_behavior",
    )
    final_behavior = _require_exact_runtime_type(
        final_behavior,
        BehaviorIR,
        location="$.final_behavior",
    )
    validate_change_proposal(proposal, base_behavior)
    _validate_document_pair(base_behavior, final_behavior)
    entries = _derive_entries(base_behavior, final_behavior)
    if not entries:
        _raise(
            ChangeLifecycleErrorCode.INCOMPLETE_DELTA,
            "base and final behavior contain no semantic difference",
            "$.entries",
        )
    return BehaviorDelta(
        kind="behavior_delta",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=BEHAVIOR_DELTA_SCHEMA_URI,
        change_id=proposal.change_id,
        proposal=change_proposal_ref(proposal),
        base_behavior=_behavior_document_ref(base_behavior),
        final_behavior=_behavior_document_ref(final_behavior),
        entries=entries,
    )


def validate_behavior_delta(
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> None:
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    base_behavior = _require_exact_runtime_type(
        base_behavior,
        BehaviorIR,
        location="$.base_behavior",
    )
    final_behavior = _require_exact_runtime_type(
        final_behavior,
        BehaviorIR,
        location="$.final_behavior",
    )
    validate_change_proposal(proposal, base_behavior)
    canonical_change_lifecycle_json(delta)
    _validate_document_pair(base_behavior, final_behavior)
    if delta.change_id != proposal.change_id:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "delta change ID differs from the proposal",
            "$.change_id",
        )
    if delta.proposal != change_proposal_ref(proposal):
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "delta proposal reference is stale or fabricated",
            "$.proposal",
        )
    if delta.base_behavior != _behavior_document_ref(base_behavior):
        _raise(
            ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "delta base behavior does not match the supplied document",
            "$.base_behavior",
        )
    if delta.final_behavior != _behavior_document_ref(final_behavior):
        _raise(
            ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "delta final behavior does not match the supplied document",
            "$.final_behavior",
        )
    expected = _derive_entries(base_behavior, final_behavior)
    if not expected or delta.entries != expected:
        _raise(
            ChangeLifecycleErrorCode.INCOMPLETE_DELTA,
            "delta membership is not the exact exhaustive behavior difference",
            "$.entries",
        )


def delta_subject_ref(entry: BehaviorDeltaEntry) -> DeltaSubjectRef:
    entry = _require_delta_entry_runtime_type(entry)
    entry = _validate_direct_python_input(
        entry,
        _BEHAVIOR_DELTA_ENTRY_ADAPTER,
        location="$.entry",
    )
    if isinstance(entry, AddedBehavior):
        subject = entry.final_subject
        operation = "added"
    elif isinstance(entry, ModifiedBehavior):
        subject = entry.final_subject
        operation = "modified"
    else:
        subject = entry.base_subject
        operation = "removed"
    return DeltaSubjectRef(
        kind="delta_subject_ref",
        operation=operation,
        target_kind=subject.target_kind,
        target_id=subject.target_id,
    )


def derive_task_graph(
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    subject_assignments: Mapping[
        str,
        tuple[DeltaSubjectRef, ...],
    ],
    dependencies: Mapping[str, tuple[str, ...]],
) -> TaskGraph:
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    validated_subject_assignments = _validate_subject_assignment_mapping(
        subject_assignments
    )
    validated_dependencies = _validate_dependency_mapping(dependencies)
    canonical_change_lifecycle_json(proposal)
    canonical_change_lifecycle_json(delta)
    task_artifacts = tuple(
        artifact
        for artifact in proposal.openspec.artifacts
        if artifact.role is OpenSpecArtifactRole.TASKS
    )
    if len(task_artifacts) != 1:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "task derivation requires exactly one OpenSpec tasks artifact",
            "$.openspec.artifacts",
        )
    artifact = task_artifacts[0]
    content = base64.b64decode(artifact.content_base64).decode("utf-8")
    parsed: list[tuple[str, int, TaskStatus]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        match = _OPENSPEC_TASK.match(line)
        if match is None:
            continue
        task_id = f"task.{match.group(2).replace('.', '-')}"
        status = TaskStatus.PENDING if match.group(1) == " " else TaskStatus.COMPLETED
        parsed.append((task_id, line_number, status))
        if len(parsed) > MAX_CHANGE_TASKS:
            _raise(
                ChangeLifecycleErrorCode.INVALID_STRUCTURE,
                (f"OpenSpec tasks artifact exceeds the {MAX_CHANGE_TASKS}-task limit"),
                "$.openspec.artifacts",
            )
    if not parsed:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "OpenSpec tasks artifact has no numbered checkbox tasks",
            "$.openspec.artifacts",
        )
    task_ids = tuple(task_id for task_id, _, _ in parsed)
    if len(task_ids) != len(set(task_ids)):
        _raise(
            ChangeLifecycleErrorCode.DUPLICATE_IDENTITY,
            "OpenSpec tasks artifact contains duplicate task IDs",
            "$.openspec.artifacts",
        )
    if set(validated_subject_assignments) != set(task_ids):
        _raise(
            ChangeLifecycleErrorCode.INCOMPLETE_COVERAGE,
            "subject assignments must name every and only parsed task",
            "$.subject_assignments",
        )
    if not set(validated_dependencies).issubset(task_ids):
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "dependency assignments name an unknown task",
            "$.dependencies",
        )
    try:
        tasks = tuple(
            ChangeTask(
                kind="change_task",
                id=task_id,
                order=order,
                depends_on=tuple(
                    TaskRef(kind="task_ref", target_id=target_id)
                    for target_id in sorted(validated_dependencies.get(task_id, ()))
                ),
                subjects=tuple(
                    sorted(
                        validated_subject_assignments[task_id],
                        key=_delta_subject_key,
                    )
                ),
                status=status,
                source=TaskSource(
                    kind="task_source",
                    artifact_path=artifact.path,
                    artifact_digest=artifact.byte_digest,
                    line=line_number,
                ),
            )
            for order, (task_id, line_number, status) in enumerate(
                parsed,
                start=1,
            )
        )
        graph = TaskGraph(
            kind="task_graph",
            change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
            schema_uri=TASK_GRAPH_SCHEMA_URI,
            change_id=proposal.change_id,
            delta=behavior_delta_ref(delta),
            tasks=tasks,
        )
    except PydanticValidationError as error:
        _raise_pydantic_structure(error, location="$.tasks")
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    return graph


def validate_task_graph(
    graph: TaskGraph,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> None:
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    validate_behavior_delta(
        delta,
        proposal,
        base_behavior,
        final_behavior,
    )
    _validate_task_graph_against_delta(graph, delta)
    for index, task in enumerate(graph.tasks):
        _validate_task_source(task, proposal, f"$.tasks[{index}]")


def _validate_task_graph_against_delta(
    graph: TaskGraph,
    delta: BehaviorDelta,
) -> None:
    canonical_change_lifecycle_json(graph)
    canonical_change_lifecycle_json(delta)
    if graph.change_id != delta.change_id:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "task graph change ID differs from the delta",
            "$.change_id",
        )
    if graph.delta != behavior_delta_ref(delta):
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "task graph delta reference is stale or fabricated",
            "$.delta",
        )
    _validate_task_graph_topology(graph)
    expected_subjects = {
        _delta_subject_key(delta_subject_ref(entry)) for entry in delta.entries
    }
    actual_subjects = {
        _delta_subject_key(subject) for task in graph.tasks for subject in task.subjects
    }
    if actual_subjects != expected_subjects:
        missing = expected_subjects - actual_subjects
        extra = actual_subjects - expected_subjects
        code = (
            ChangeLifecycleErrorCode.BROKEN_REFERENCE
            if extra
            else ChangeLifecycleErrorCode.INCOMPLETE_COVERAGE
        )
        _raise(
            code,
            "task subject coverage differs from the delta; "
            f"missing={sorted(missing)!r}, extra={sorted(extra)!r}",
            "$.tasks",
        )


def _validate_task_graph_topology(
    graph: TaskGraph,
) -> dict[str, ChangeTask]:
    canonical_change_lifecycle_json(graph)
    tasks_by_id: dict[str, ChangeTask] = {}
    order_by_id: dict[str, int] = {}
    source_coordinates: set[tuple[str, int]] = set()
    for index, task in enumerate(graph.tasks):
        location = f"$.tasks[{index}]"
        if task.id in tasks_by_id:
            _raise(
                ChangeLifecycleErrorCode.DUPLICATE_IDENTITY,
                f"duplicate task ID {task.id!r}",
                f"{location}.id",
            )
        tasks_by_id[task.id] = task
        order_by_id[task.id] = task.order
        if task.order != index + 1:
            _raise(
                ChangeLifecycleErrorCode.NON_CANONICAL_ORDER,
                "task order is not canonical and contiguous",
                f"{location}.order",
            )
        dependency_ids = tuple(ref.target_id for ref in task.depends_on)
        if len(dependency_ids) != len(set(dependency_ids)) or dependency_ids != tuple(
            sorted(dependency_ids)
        ):
            _raise(
                ChangeLifecycleErrorCode.NON_CANONICAL_ORDER,
                "task dependencies are duplicated or non-canonical",
                f"{location}.depends_on",
            )
        subject_keys = tuple(_delta_subject_key(item) for item in task.subjects)
        if len(subject_keys) != len(set(subject_keys)) or subject_keys != tuple(
            sorted(subject_keys)
        ):
            _raise(
                ChangeLifecycleErrorCode.NON_CANONICAL_ORDER,
                "task subjects are duplicated or non-canonical",
                f"{location}.subjects",
            )
        source_coordinate = (task.source.artifact_path, task.source.line)
        if source_coordinate in source_coordinates:
            _raise(
                ChangeLifecycleErrorCode.DUPLICATE_IDENTITY,
                "tasks share one source coordinate",
                f"{location}.source",
            )
        source_coordinates.add(source_coordinate)
    _validate_task_status_dependencies(graph, tasks_by_id)

    cycle = _find_task_cycle(tasks_by_id)
    if cycle is not None:
        _raise(
            ChangeLifecycleErrorCode.CYCLIC_DEPENDENCY,
            f"task dependency cycle detected: {' -> '.join(cycle)}",
            "$.tasks",
        )

    for index, task in enumerate(graph.tasks):
        for reference in task.depends_on:
            if order_by_id[reference.target_id] >= task.order:
                _raise(
                    ChangeLifecycleErrorCode.NON_CANONICAL_ORDER,
                    "task dependency must precede the dependent task",
                    f"$.tasks[{index}].depends_on",
                )
    return tasks_by_id


def complete_change_task(
    graph: TaskGraph,
    task_id: str,
    *,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> TaskGraph:
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    task_id = _require_exact_runtime_type(
        task_id,
        str,
        location="$.task_id",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    tasks_by_id = {task.id: task for task in graph.tasks}
    task = tasks_by_id.get(task_id)
    if task is None:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            f"task {task_id!r} does not exist",
            "$.tasks",
        )
    incomplete_predecessors = tuple(
        reference.target_id
        for reference in task.depends_on
        if tasks_by_id.get(reference.target_id) is None
        or tasks_by_id[reference.target_id].status is not TaskStatus.COMPLETED
    )
    if incomplete_predecessors:
        _raise(
            ChangeLifecycleErrorCode.INVALID_TRANSITION,
            (
                "task completion requires completed predecessors: "
                f"{incomplete_predecessors!r}"
            ),
            "$.tasks",
        )
    if task.status is TaskStatus.COMPLETED:
        return graph
    tasks = tuple(
        task.model_copy(update={"status": TaskStatus.COMPLETED})
        if task.id == task_id
        else task
        for task in graph.tasks
    )
    successor = TaskGraph(
        kind=graph.kind,
        change_lifecycle_version=graph.change_lifecycle_version,
        schema_uri=graph.schema_uri,
        change_id=graph.change_id,
        delta=graph.delta,
        tasks=tasks,
    )
    validate_task_graph(
        successor,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    return successor


def _validate_task_status_dependencies(
    graph: TaskGraph,
    tasks_by_id: Mapping[str, ChangeTask],
) -> None:
    for index, task in enumerate(graph.tasks):
        missing = tuple(
            reference.target_id
            for reference in task.depends_on
            if reference.target_id not in tasks_by_id
        )
        if missing:
            _raise(
                ChangeLifecycleErrorCode.BROKEN_REFERENCE,
                f"task dependencies do not resolve: {missing!r}",
                f"$.tasks[{index}].depends_on",
            )
        incomplete = tuple(
            reference.target_id
            for reference in task.depends_on
            if tasks_by_id[reference.target_id].status is not TaskStatus.COMPLETED
        )
        if task.status is TaskStatus.COMPLETED and incomplete:
            _raise(
                ChangeLifecycleErrorCode.INVALID_TRANSITION,
                f"completed task has pending predecessors: {incomplete!r}",
                f"$.tasks[{index}].status",
            )


def _validate_task_source(
    task: ChangeTask,
    proposal: ChangeProposal,
    location: str,
) -> None:
    artifact = next(
        (
            candidate
            for candidate in proposal.openspec.artifacts
            if candidate.path == task.source.artifact_path
        ),
        None,
    )
    if artifact is None:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "task source artifact does not resolve",
            f"{location}.source.artifact_path",
        )
    if (
        artifact.role is not OpenSpecArtifactRole.TASKS
        or artifact.byte_digest != task.source.artifact_digest
    ):
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "task source artifact identity does not match the proposal",
            f"{location}.source",
        )
    content = base64.b64decode(artifact.content_base64).decode("utf-8")
    lines = content.splitlines()
    if task.source.line > len(lines):
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "task source line does not exist",
            f"{location}.source.line",
        )
    match = _OPENSPEC_TASK.match(lines[task.source.line - 1])
    expected_id = task.id.removeprefix("task.").replace("-", ".")
    if match is None or match.group(2) != expected_id:
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "task ID does not match its OpenSpec checkbox coordinate",
            f"{location}.source.line",
        )


def _find_task_cycle(
    tasks_by_id: dict[str, ChangeTask],
) -> tuple[str, ...] | None:
    visited: set[str] = set()
    for root_id in tasks_by_id:
        if root_id in visited:
            continue
        active = [root_id]
        active_index = {root_id: 0}
        stack = [(root_id, 0)]
        while stack:
            task_id, dependency_index = stack[-1]
            dependencies = tasks_by_id[task_id].depends_on
            if dependency_index >= len(dependencies):
                stack.pop()
                active.pop()
                active_index.pop(task_id)
                visited.add(task_id)
                continue
            stack[-1] = (task_id, dependency_index + 1)
            target_id = dependencies[dependency_index].target_id
            if target_id in active_index:
                start = active_index[target_id]
                return (*active[start:], target_id)
            if target_id in visited:
                continue
            active_index[target_id] = len(active)
            active.append(target_id)
            stack.append((target_id, 0))
    return None


def _delta_subject_key(
    subject: DeltaSubjectRef,
) -> tuple[str, str, str]:
    return (
        subject.operation,
        subject.target_kind.value,
        subject.target_id,
    )


def derive_implementation_record(
    graph: TaskGraph,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> ImplementationRecord:
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    evidence_contexts = _validate_evidence_contexts(evidence_contexts)
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    _require_completed_tasks(graph)
    bindings = _bind_implementation_evidence(delta, evidence_contexts)
    record = ImplementationRecord(
        kind="implementation_record",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=IMPLEMENTATION_RECORD_SCHEMA_URI,
        change_id=graph.change_id,
        tasks=task_graph_ref(graph),
        bindings=bindings,
    )
    canonical_change_lifecycle_json(record)
    return record


def validate_implementation_record(
    record: ImplementationRecord,
    graph: TaskGraph,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> None:
    record = _require_exact_runtime_type(
        record,
        ImplementationRecord,
        location="$.record",
    )
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    evidence_contexts = _validate_evidence_contexts(evidence_contexts)
    canonical_change_lifecycle_json(record)
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    _require_completed_tasks(graph)
    if record.change_id != graph.change_id:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "implementation record change ID differs from the task graph",
            "$.change_id",
        )
    if record.tasks != task_graph_ref(graph):
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "implementation task reference is stale or fabricated",
            "$.tasks",
        )
    expected = _bind_implementation_evidence(
        delta,
        evidence_contexts,
    )
    if record.bindings != expected:
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "implementation evidence bindings are not exact",
            "$.bindings",
        )


def derive_verification_record(
    implementation: ImplementationRecord,
    graph: TaskGraph,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> VerificationRecord:
    implementation = _require_exact_runtime_type(
        implementation,
        ImplementationRecord,
        location="$.implementation",
    )
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    evidence_contexts = _validate_evidence_contexts(evidence_contexts)
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    _require_passing_evidence(implementation)
    return VerificationRecord(
        kind="verification_record",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=VERIFICATION_RECORD_SCHEMA_URI,
        change_id=implementation.change_id,
        implementation=implementation_record_ref(implementation),
        outcome="accepted",
        subjects=tuple(binding.subject for binding in implementation.bindings),
    )


def validate_verification_record(
    verification: VerificationRecord,
    implementation: ImplementationRecord,
    graph: TaskGraph,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> None:
    verification = _require_exact_runtime_type(
        verification,
        VerificationRecord,
        location="$.verification",
    )
    implementation = _require_exact_runtime_type(
        implementation,
        ImplementationRecord,
        location="$.implementation",
    )
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    evidence_contexts = _validate_evidence_contexts(evidence_contexts)
    canonical_change_lifecycle_json(verification)
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    _require_passing_evidence(implementation)
    if verification.change_id != implementation.change_id:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "verification change ID differs from implementation",
            "$.change_id",
        )
    if verification.implementation != implementation_record_ref(implementation):
        _raise(
            ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
            "verification implementation reference is stale or fabricated",
            "$.implementation",
        )
    expected_subjects = tuple(binding.subject for binding in implementation.bindings)
    if verification.subjects != expected_subjects:
        _raise(
            ChangeLifecycleErrorCode.INCOMPLETE_COVERAGE,
            "verification subjects differ from accepted evidence",
            "$.subjects",
        )


def derive_archive_record(
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    graph: TaskGraph,
    implementation: ImplementationRecord,
    verification: VerificationRecord,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    *,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> ArchiveRecord:
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    implementation = _require_exact_runtime_type(
        implementation,
        ImplementationRecord,
        location="$.implementation",
    )
    verification = _require_exact_runtime_type(
        verification,
        VerificationRecord,
        location="$.verification",
    )
    base_behavior = _require_exact_runtime_type(
        base_behavior,
        BehaviorIR,
        location="$.base_behavior",
    )
    final_behavior = _require_exact_runtime_type(
        final_behavior,
        BehaviorIR,
        location="$.final_behavior",
    )
    evidence_contexts = _validate_evidence_contexts(evidence_contexts)
    validate_behavior_delta(delta, proposal, base_behavior, final_behavior)
    validate_verification_record(
        verification,
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    canonical_final_behavior = parse_ir_json(canonical_ir_json(final_behavior))
    archive = ArchiveRecord(
        kind="archive_record",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=ARCHIVE_RECORD_SCHEMA_URI,
        change_id=proposal.change_id,
        status="archived",
        proposal=change_proposal_ref(proposal),
        delta=behavior_delta_ref(delta),
        tasks=task_graph_ref(graph),
        implementation=implementation_record_ref(implementation),
        verification=verification_record_ref(verification),
        final_behavior=canonical_final_behavior,
    )
    canonical_change_lifecycle_json(archive)
    return archive


def validate_archive_record(
    archive: ArchiveRecord,
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    graph: TaskGraph,
    implementation: ImplementationRecord,
    verification: VerificationRecord,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    *,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> None:
    archive = _require_exact_runtime_type(
        archive,
        ArchiveRecord,
        location="$.archive",
    )
    proposal = _require_exact_runtime_type(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    delta = _require_exact_runtime_type(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    graph = _require_exact_runtime_type(
        graph,
        TaskGraph,
        location="$.graph",
    )
    implementation = _require_exact_runtime_type(
        implementation,
        ImplementationRecord,
        location="$.implementation",
    )
    verification = _require_exact_runtime_type(
        verification,
        VerificationRecord,
        location="$.verification",
    )
    base_behavior = _require_exact_runtime_type(
        base_behavior,
        BehaviorIR,
        location="$.base_behavior",
    )
    final_behavior = _require_exact_runtime_type(
        final_behavior,
        BehaviorIR,
        location="$.final_behavior",
    )
    evidence_contexts = _validate_evidence_contexts(evidence_contexts)
    canonical_change_lifecycle_json(archive)
    validate_behavior_delta(delta, proposal, base_behavior, final_behavior)
    validate_verification_record(
        verification,
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    expected_references = (
        ("proposal", change_proposal_ref(proposal)),
        ("delta", behavior_delta_ref(delta)),
        ("tasks", task_graph_ref(graph)),
        ("implementation", implementation_record_ref(implementation)),
        ("verification", verification_record_ref(verification)),
    )
    for field, expected in expected_references:
        if getattr(archive, field) != expected:
            _raise(
                ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH,
                f"archive {field} reference is stale or fabricated",
                f"$.{field}",
            )
    if archive.change_id != proposal.change_id:
        _raise(
            ChangeLifecycleErrorCode.BROKEN_REFERENCE,
            "archive change ID differs from the proposal",
            "$.change_id",
        )
    if (
        canonical_ir_json(archive.final_behavior) != canonical_ir_json(final_behavior)
        or _behavior_document_ref(archive.final_behavior) != delta.final_behavior
    ):
        _raise(
            ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "archive final behavior is not the exact accepted delta target",
            "$.final_behavior",
        )


def _require_completed_tasks(graph: TaskGraph) -> None:
    incomplete = tuple(
        task.id for task in graph.tasks if task.status is not TaskStatus.COMPLETED
    )
    if incomplete:
        _raise(
            ChangeLifecycleErrorCode.INCOMPLETE_TASKS,
            f"implementation requires completed tasks: {incomplete!r}",
            "$.tasks",
        )


def _bind_implementation_evidence(
    delta: BehaviorDelta,
    evidence_contexts: tuple[ExecutionEvidenceContext, ...],
) -> tuple[ImplementationEvidenceBinding, ...]:
    for index, entry in enumerate(delta.entries):
        if isinstance(entry, RemovedBehavior):
            _raise(
                ChangeLifecycleErrorCode.UNSUPPORTED_EVIDENCE_PROFILE,
                (
                    "removed behavior requires final-state absence evidence; "
                    "base-subject execution evidence is not accepted"
                ),
                f"$.entries[{index}]",
            )
    expected = {
        _delta_subject_key(delta_subject_ref(entry)): (
            delta_subject_ref(entry),
            _evidence_subject(entry),
        )
        for entry in delta.entries
    }
    bindings: list[ImplementationEvidenceBinding] = []
    used: set[tuple[str, str, str]] = set()
    for index, context in enumerate(evidence_contexts):
        result = context.result
        if type(result) is not ExecutionVerificationResult:
            _raise(
                ChangeLifecycleErrorCode.INVALID_STRUCTURE,
                (
                    "execution evidence result must use the exact "
                    "ExecutionVerificationResult runtime type"
                ),
                f"$.evidence_contexts[{index}].result",
            )
        try:
            validate_execution_verification_result(
                result,
                request=result.request,
                mapping_result=context.mapping_result,
                bundle=context.bundle,
                current_inventory=context.current_inventory,
                mapping_initialized_adapter=(context.mapping_initialized_adapter),
                initialized_adapter=context.initialized_adapter,
                negotiated_capabilities=context.negotiated_capabilities,
            )
        except (
            ImplementationEvidenceValidationError,
            OnboardingValidationError,
        ) as error:
            _raise(
                ChangeLifecycleErrorCode.EVIDENCE_CONTEXT_INVALID,
                f"execution evidence context is not valid: {error}",
                f"$.evidence_contexts[{index}]",
            )
        matching = tuple(
            (key, subject_ref, behavior_subject)
            for key, (subject_ref, behavior_subject) in expected.items()
            if result.request.subject == behavior_subject
        )
        if len(matching) != 1:
            _raise(
                ChangeLifecycleErrorCode.BROKEN_REFERENCE,
                "execution evidence subject does not resolve to one delta entry",
                f"$.evidence_contexts[{index}].result.request.subject",
            )
        key, subject_ref, behavior_subject = matching[0]
        expected_document = BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id=behavior_subject.document_id,
            ir_version=behavior_subject.ir_version,
            canonical_digest=behavior_subject.canonical_digest,
        )
        if result.request.base_behavior != expected_document:
            _raise(
                ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH,
                "execution evidence binds the wrong behavior document",
                (f"$.evidence_contexts[{index}].result.request.base_behavior"),
            )
        if key in used:
            _raise(
                ChangeLifecycleErrorCode.DUPLICATE_IDENTITY,
                "multiple evidence results bind one delta subject",
                f"$.evidence_contexts[{index}]",
            )
        used.add(key)
        bindings.append(
            ImplementationEvidenceBinding(
                kind="implementation_evidence_binding",
                subject=subject_ref,
                result=result,
                validation=_context_validation_receipt(context),
            )
        )
    if used != set(expected):
        _raise(
            ChangeLifecycleErrorCode.INCOMPLETE_COVERAGE,
            "implementation evidence does not cover every delta subject",
            "$.evidence_contexts",
        )
    return tuple(
        sorted(bindings, key=lambda binding: _delta_subject_key(binding.subject))
    )


def _evidence_subject(entry: BehaviorDeltaEntry) -> BehaviorEntityRef:
    if isinstance(entry, RemovedBehavior):
        raise AssertionError(
            "removed behavior must be rejected before evidence binding"
        )
    return entry.final_subject


def _context_validation_receipt(
    context: ExecutionEvidenceContext,
) -> EvidenceContextValidationReceipt:
    inventory_payload = canonical_inventory_json(context.current_inventory)
    return EvidenceContextValidationReceipt(
        kind="evidence_context_validation_receipt",
        assurance="context_validated_import",
        procedure_uri=EVIDENCE_CONTEXT_VALIDATION_PROCEDURE_URI,
        result_digest=canonical_implementation_evidence_digest(context.result),
        mapping_result_digest=canonical_implementation_evidence_digest(
            context.mapping_result
        ),
        onboarding_bundle_digest=canonical_onboarding_digest(context.bundle),
        current_inventory_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=_sha256(inventory_payload),
        ),
        mapping_initialized_adapter=context.mapping_initialized_adapter,
        verification_initialized_adapter=context.initialized_adapter,
        negotiated_capabilities=tuple(
            CapabilitySelection(
                kind="capability",
                name=name,
                version=version,
            )
            for name, version in sorted(context.negotiated_capabilities.items())
        ),
    )


def _require_passing_evidence(
    implementation: ImplementationRecord,
) -> None:
    nonpassing = tuple(
        binding.subject.target_id
        for binding in implementation.bindings
        if binding.result.outcome != "passed"
    )
    if nonpassing:
        _raise(
            ChangeLifecycleErrorCode.EVIDENCE_NOT_PASSED,
            f"verification requires passing evidence: {nonpassing!r}",
            "$.bindings",
        )


def _validate_document_pair(
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> None:
    validate_behavior_document(
        base_behavior,
        location="$.base_behavior",
    )
    validate_behavior_document(
        final_behavior,
        location="$.final_behavior",
    )
    if (
        base_behavior.document_id != final_behavior.document_id
        or base_behavior.ir_version != final_behavior.ir_version
    ):
        _raise(
            ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "base and final behavior must retain document identity and version",
            "$.final_behavior",
        )


def _derive_entries(
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> tuple[BehaviorDeltaEntry, ...]:
    base_entities, base_roots = _canonical_entities_and_roots(base_behavior)
    final_entities, final_roots = _canonical_entities_and_roots(final_behavior)
    base_ref = _behavior_document_ref(base_behavior)
    final_ref = _behavior_document_ref(final_behavior)
    entries: list[BehaviorDeltaEntry] = []

    for key in sorted(final_entities.keys() - base_entities.keys()):
        entries.append(
            AddedBehavior(
                kind="added_behavior",
                final_subject=_entity_ref(final_ref, key),
                final_is_root=key in final_roots,
            )
        )
    for key in sorted(base_entities.keys() & final_entities.keys()):
        definition_changed = base_entities[key] != final_entities[key]
        root_changed = (key in base_roots) != (key in final_roots)
        if not definition_changed and not root_changed:
            continue
        aspects = tuple(
            aspect
            for aspect, changed in (
                ("definition", definition_changed),
                ("root_membership", root_changed),
            )
            if changed
        )
        entries.append(
            ModifiedBehavior(
                kind="modified_behavior",
                base_subject=_entity_ref(base_ref, key),
                final_subject=_entity_ref(final_ref, key),
                aspects=aspects,
                base_is_root=key in base_roots,
                final_is_root=key in final_roots,
            )
        )
    for key in sorted(base_entities.keys() - final_entities.keys()):
        entries.append(
            RemovedBehavior(
                kind="removed_behavior",
                base_subject=_entity_ref(base_ref, key),
                base_is_root=key in base_roots,
            )
        )
    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                entry.kind,
                (
                    entry.final_subject.target_kind.value
                    if isinstance(entry, AddedBehavior)
                    else entry.base_subject.target_kind.value
                ),
                (
                    entry.final_subject.target_id
                    if isinstance(entry, AddedBehavior)
                    else entry.base_subject.target_id
                ),
            ),
        )
    )


def _canonical_entities_and_roots(
    document: BehaviorIR,
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    set[tuple[str, str]],
]:
    canonical = json.loads(canonical_ir_json(document))
    entities = {
        (entity["kind"], entity["id"]): entity for entity in canonical["entities"]
    }
    roots = {(root["target_kind"], root["target_id"]) for root in canonical["roots"]}
    return entities, roots


def _behavior_document_ref(document: BehaviorIR) -> BehaviorDocumentRef:
    return BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=_sha256(canonical_ir_json(document).encode("utf-8")),
        ),
    )


def _entity_ref(
    document: BehaviorDocumentRef,
    key: tuple[str, str],
) -> BehaviorEntityRef:
    return BehaviorEntityRef(
        kind="behavior_entity_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=document.canonical_digest,
        target_kind=EntityKind(key[0]),
        target_id=key[1],
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_exact_runtime_type[RuntimeType](
    value: object,
    expected: type[RuntimeType],
    *,
    location: str,
) -> RuntimeType:
    if type(value) is not expected:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            f"expected exact runtime type {expected.__name__}",
            location,
        )
    return cast(RuntimeType, value)


def _require_delta_entry_runtime_type(
    value: object,
) -> BehaviorDeltaEntry:
    expected = (AddedBehavior, ModifiedBehavior, RemovedBehavior)
    if type(value) not in expected:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "expected an exact behavior delta entry runtime type",
            "$.entry",
        )
    return cast(BehaviorDeltaEntry, value)


def _require_mapping(
    value: object,
    *,
    location: str,
) -> Mapping[Any, Any]:
    if not isinstance(value, Mapping):
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "expected a Mapping runtime value",
            location,
        )
    return value


def _validate_subject_assignment_mapping(
    value: object,
) -> dict[str, tuple[DeltaSubjectRef, ...]]:
    mapping = _require_mapping(value, location="$.subject_assignments")
    validated: dict[str, tuple[DeltaSubjectRef, ...]] = {}
    for key, subjects_value in mapping.items():
        task_id = _require_exact_runtime_type(
            key,
            str,
            location="$.subject_assignments",
        )
        subjects = _require_exact_runtime_type(
            subjects_value,
            tuple,
            location=f"$.subject_assignments[{task_id!r}]",
        )
        for index, subject in enumerate(subjects):
            _require_exact_runtime_type(
                subject,
                DeltaSubjectRef,
                location=(f"$.subject_assignments[{task_id!r}][{index}]"),
            )
        validated[task_id] = cast(
            tuple[DeltaSubjectRef, ...],
            _validate_direct_python_input(
                subjects,
                _DELTA_SUBJECT_ASSIGNMENT_ADAPTER,
                location=f"$.subject_assignments[{task_id!r}]",
            ),
        )
    return validated


def _validate_dependency_mapping(
    value: object,
) -> dict[str, tuple[str, ...]]:
    mapping = _require_mapping(value, location="$.dependencies")
    validated: dict[str, tuple[str, ...]] = {}
    for key, targets_value in mapping.items():
        task_id = _require_exact_runtime_type(
            key,
            str,
            location="$.dependencies",
        )
        targets = _require_exact_runtime_type(
            targets_value,
            tuple,
            location=f"$.dependencies[{task_id!r}]",
        )
        for index, target in enumerate(targets):
            _require_exact_runtime_type(
                target,
                str,
                location=f"$.dependencies[{task_id!r}][{index}]",
            )
        validated[task_id] = cast(
            tuple[str, ...],
            _validate_direct_python_input(
                targets,
                _DEPENDENCY_IDS_ADAPTER,
                location=f"$.dependencies[{task_id!r}]",
            ),
        )
    return validated


def _validate_evidence_contexts(
    value: object,
) -> tuple[ExecutionEvidenceContext, ...]:
    contexts = _require_exact_runtime_type(
        value,
        tuple,
        location="$.evidence_contexts",
    )
    if len(contexts) > _MAX_IMPLEMENTATION_EVIDENCE_CONTEXTS:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            (
                "evidence contexts exceed the "
                f"{_MAX_IMPLEMENTATION_EVIDENCE_CONTEXTS}-binding limit"
            ),
            "$.evidence_contexts",
        )
    normalized: list[ExecutionEvidenceContext] = []
    for index, context_value in enumerate(contexts):
        location = f"$.evidence_contexts[{index}]"
        context = _require_exact_runtime_type(
            context_value,
            ExecutionEvidenceContext,
            location=location,
        )
        result = _require_exact_runtime_type(
            context.result,
            ExecutionVerificationResult,
            location=f"{location}.result",
        )
        result = cast(
            ExecutionVerificationResult,
            _validate_direct_python_input(
                result,
                _EXECUTION_VERIFICATION_RESULT_ADAPTER,
                location=f"{location}.result",
            ),
        )
        mapping_result = _require_exact_runtime_type(
            context.mapping_result,
            ImplementationMappingResult,
            location=f"{location}.mapping_result",
        )
        mapping_result = cast(
            ImplementationMappingResult,
            _validate_direct_python_input(
                mapping_result,
                _IMPLEMENTATION_MAPPING_RESULT_ADAPTER,
                location=f"{location}.mapping_result",
            ),
        )
        bundle = _require_exact_runtime_type(
            context.bundle,
            OnboardingBundle,
            location=f"{location}.bundle",
        )
        bundle = cast(
            OnboardingBundle,
            _validate_direct_python_input(
                bundle,
                _ONBOARDING_BUNDLE_ADAPTER,
                location=f"{location}.bundle",
            ),
        )
        current_inventory = _require_exact_runtime_type(
            context.current_inventory,
            InventorySnapshot,
            location=f"{location}.current_inventory",
        )
        current_inventory = cast(
            InventorySnapshot,
            _validate_direct_python_input(
                current_inventory,
                _INVENTORY_SNAPSHOT_ADAPTER,
                location=f"{location}.current_inventory",
            ),
        )
        mapping_initialized_adapter = _require_exact_runtime_type(
            context.mapping_initialized_adapter,
            Producer,
            location=f"{location}.mapping_initialized_adapter",
        )
        mapping_initialized_adapter = cast(
            Producer,
            _validate_direct_python_input(
                mapping_initialized_adapter,
                _PRODUCER_ADAPTER,
                location=f"{location}.mapping_initialized_adapter",
            ),
        )
        initialized_adapter = _require_exact_runtime_type(
            context.initialized_adapter,
            Producer,
            location=f"{location}.initialized_adapter",
        )
        initialized_adapter = cast(
            Producer,
            _validate_direct_python_input(
                initialized_adapter,
                _PRODUCER_ADAPTER,
                location=f"{location}.initialized_adapter",
            ),
        )
        capabilities_location = f"{location}.negotiated_capabilities"
        capabilities = _require_mapping(
            context.negotiated_capabilities,
            location=capabilities_location,
        )
        if len(capabilities) > _MAX_NEGOTIATED_CAPABILITIES:
            _raise(
                ChangeLifecycleErrorCode.INVALID_STRUCTURE,
                (
                    "negotiated capabilities exceed the "
                    f"{_MAX_NEGOTIATED_CAPABILITIES}-selection limit"
                ),
                capabilities_location,
            )
        normalized_capabilities: dict[str, str] = {}
        for capability, version in capabilities.items():
            _require_exact_runtime_type(
                capability,
                str,
                location=capabilities_location,
            )
            _require_exact_runtime_type(
                version,
                str,
                location=f"{capabilities_location}[{capability!r}]",
            )
            try:
                CapabilitySelection(
                    kind="capability",
                    name=capability,
                    version=version,
                )
            except PydanticValidationError as error:
                _raise_pydantic_structure(
                    error,
                    location=f"{capabilities_location}[{capability!r}]",
                )
            normalized_capabilities[capability] = version
        normalized.append(
            ExecutionEvidenceContext(
                result=result,
                mapping_result=mapping_result,
                bundle=bundle,
                current_inventory=current_inventory,
                mapping_initialized_adapter=mapping_initialized_adapter,
                initialized_adapter=initialized_adapter,
                negotiated_capabilities=normalized_capabilities,
            )
        )
    return tuple(normalized)


def _validate_direct_python_input(
    value: Any,
    adapter: TypeAdapter[Any],
    *,
    location: str,
) -> Any:
    try:
        return adapter.validate_python(
            _direct_python_validation_input(
                value,
                location=location,
            )
        )
    except PydanticValidationError as error:
        _raise_pydantic_structure(error, location=location)


def _direct_python_validation_input(
    value: Any,
    *,
    location: str,
    active_ids: set[int] | None = None,
    depth: int = 0,
) -> Any:
    if depth > _MAX_DIRECT_PYTHON_INPUT_DEPTH:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            (
                "direct Python input exceeds the "
                f"{_MAX_DIRECT_PYTHON_INPUT_DEPTH}-level nesting limit"
            ),
            location,
        )
    if not isinstance(value, (BaseModel, Mapping, tuple, list)):
        return value

    active_ids = set() if active_ids is None else active_ids
    identity = id(value)
    if identity in active_ids:
        _raise(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "direct Python input contains a cyclic container",
            location,
        )
    active_ids.add(identity)
    try:
        if isinstance(value, BaseModel):
            result = {
                field: _direct_python_validation_input(
                    item,
                    location=f"{location}.{field}",
                    active_ids=active_ids,
                    depth=depth + 1,
                )
                for field, item in value.__dict__.items()
            }
            if value.__pydantic_extra__:
                result.update(
                    {
                        field: _direct_python_validation_input(
                            item,
                            location=f"{location}.{field}",
                            active_ids=active_ids,
                            depth=depth + 1,
                        )
                        for field, item in value.__pydantic_extra__.items()
                    }
                )
            return result
        if isinstance(value, Mapping):
            return {
                key: _direct_python_validation_input(
                    item,
                    location=f"{location}[{key!r}]",
                    active_ids=active_ids,
                    depth=depth + 1,
                )
                for key, item in value.items()
            }
        return tuple(
            _direct_python_validation_input(
                item,
                location=f"{location}[{index}]",
                active_ids=active_ids,
                depth=depth + 1,
            )
            for index, item in enumerate(value)
        )
    finally:
        active_ids.remove(identity)


def _raise_pydantic_structure(
    error: PydanticValidationError,
    *,
    location: str,
) -> None:
    detail = error.errors(
        include_context=False,
        include_input=False,
        include_url=False,
    )[0]
    for component in detail["loc"]:
        if isinstance(component, int):
            location += f"[{component}]"
        else:
            location += f".{component}"
    _raise(
        ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        detail["msg"],
        location,
    )


def _raise(
    code: ChangeLifecycleErrorCode,
    message: str,
    location: str,
) -> None:
    raise ChangeLifecycleValidationError(code, message, location=location)
