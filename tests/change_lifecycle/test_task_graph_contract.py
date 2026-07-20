from __future__ import annotations

import pytest

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    OpenSpecArtifactRole,
    TaskRef,
    TaskStatus,
    canonical_change_lifecycle_json,
    complete_change_task,
    delta_subject_ref,
    derive_behavior_delta,
    derive_task_graph,
    parse_task_graph_json,
    task_graph_ref,
    validate_task_graph,
)

from ._fixture_factory import (
    behavior_pair,
    openspec_artifact,
    task_graph,
)
from ._fixture_factory import (
    proposal as fixture_proposal,
)

_BASE_BEHAVIOR, _FINAL_BEHAVIOR = behavior_pair()


def _task_graph():
    return task_graph()


def _large_task_inputs(task_count: int):
    base, final = behavior_pair()
    proposal = fixture_proposal(base)
    task_path = f"changes/{proposal.change_id}/tasks.md"
    content = b"".join(
        f"- [ ] 1.{index} Task {index}\n".encode() for index in range(1, task_count + 1)
    )
    artifacts = tuple(
        (
            openspec_artifact(
                task_path,
                OpenSpecArtifactRole.TASKS,
                content,
            )
            if artifact.role is OpenSpecArtifactRole.TASKS
            else artifact
        )
        for artifact in proposal.openspec.artifacts
    )
    proposal = proposal.model_copy(
        update={
            "openspec": proposal.openspec.model_copy(update={"artifacts": artifacts})
        }
    )
    delta = derive_behavior_delta(proposal, base, final)
    subject = delta_subject_ref(delta.entries[0])
    assignments = {f"task.1-{index}": (subject,) for index in range(1, task_count + 1)}
    return proposal, delta, assignments


def test_task_graph_is_ordered_closed_and_immutable() -> None:
    proposal, delta, graph = _task_graph()
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )

    encoded = canonical_change_lifecycle_json(graph)
    assert parse_task_graph_json(encoded) == graph
    assert canonical_change_lifecycle_json(parse_task_graph_json(encoded)) == encoded
    assert task_graph_ref(graph).canonical_digest.value

    successor = complete_change_task(
        graph,
        "task.1-1",
        delta=delta,
        proposal=proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    validate_task_graph(
        successor,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    assert graph.tasks[0].status == "pending"
    assert successor.tasks[0].status == "completed"
    assert successor.tasks[1:] == graph.tasks[1:]
    assert task_graph_ref(successor) != task_graph_ref(graph)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing", ChangeLifecycleErrorCode.BROKEN_REFERENCE),
        ("cycle", ChangeLifecycleErrorCode.CYCLIC_DEPENDENCY),
        ("forward", ChangeLifecycleErrorCode.NON_CANONICAL_ORDER),
        ("subject", ChangeLifecycleErrorCode.BROKEN_REFERENCE),
        ("source", ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH),
        ("empty-subjects", ChangeLifecycleErrorCode.INVALID_STRUCTURE),
    ],
)
def test_task_graph_rejects_invalid_graph_or_context(
    mutation: str,
    code: ChangeLifecycleErrorCode,
) -> None:
    proposal, delta, graph = _task_graph()
    tasks = list(graph.tasks)
    if mutation == "missing":
        tasks[1] = tasks[1].model_copy(
            update={"depends_on": (TaskRef(kind="task_ref", target_id="task.missing"),)}
        )
    elif mutation == "cycle":
        tasks[0] = tasks[0].model_copy(
            update={"depends_on": (TaskRef(kind="task_ref", target_id="task.1-3"),)}
        )
    elif mutation == "forward":
        tasks[0] = tasks[0].model_copy(
            update={"depends_on": (TaskRef(kind="task_ref", target_id="task.1-2"),)}
        )
        tasks[1] = tasks[1].model_copy(update={"depends_on": ()})
    elif mutation == "subject":
        tasks[0] = tasks[0].model_copy(
            update={
                "subjects": (
                    tasks[0]
                    .subjects[0]
                    .model_copy(update={"target_id": "use-case.missing"}),
                )
            }
        )
    elif mutation == "source":
        tasks[0] = tasks[0].model_copy(
            update={
                "source": tasks[0].source.model_copy(
                    update={
                        "artifact_digest": tasks[0].source.artifact_digest.model_copy(
                            update={"value": "f" * 64}
                        )
                    }
                )
            }
        )
    else:
        tasks = [task.model_copy(update={"subjects": ()}) for task in tasks]

    changed = graph.model_copy(update={"tasks": tuple(tasks)})
    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_task_graph(
            changed,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )
    assert captured.value.code is code


def test_task_completion_rejects_unknown_task_without_mutation() -> None:
    proposal, delta, graph = _task_graph()
    with pytest.raises(ChangeLifecycleValidationError) as captured:
        complete_change_task(
            graph,
            "task.unknown",
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )
    assert captured.value.code is ChangeLifecycleErrorCode.BROKEN_REFERENCE
    assert all(task.status == "pending" for task in graph.tasks)


def test_task_completion_requires_completed_predecessors() -> None:
    proposal, delta, graph = _task_graph()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        complete_change_task(
            graph,
            "task.1-2",
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )
    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_TRANSITION
    assert all(task.status == "pending" for task in graph.tasks)

    first = complete_change_task(
        graph,
        "task.1-1",
        delta=delta,
        proposal=proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    second = complete_change_task(
        first,
        "task.1-2",
        delta=delta,
        proposal=proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    assert second.tasks[0].status == "completed"
    assert second.tasks[1].status == "completed"
    assert second.tasks[2].status == "pending"


def test_task_graph_rejects_completed_task_with_pending_predecessor() -> None:
    proposal, delta, graph = _task_graph()
    tasks = list(graph.tasks)
    tasks[1] = tasks[1].model_copy(update={"status": TaskStatus.COMPLETED})
    impossible = graph.model_copy(update={"tasks": tuple(tasks)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_task_graph(
            impossible,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_TRANSITION

    with pytest.raises(ChangeLifecycleValidationError) as transition:
        complete_change_task(
            impossible,
            "task.1-1",
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )

    assert transition.value.code is ChangeLifecycleErrorCode.INVALID_TRANSITION


def test_task_derivation_rejects_more_than_the_wire_limit_cleanly() -> None:
    proposal, delta, assignments = _large_task_inputs(1025)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_task_graph(
            proposal,
            delta,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies={},
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_task_cycle_detection_handles_the_full_wire_depth() -> None:
    task_count = 1024
    proposal, delta, assignments = _large_task_inputs(task_count)
    dependencies = {
        "task.1-1": (f"task.1-{task_count}",),
        **{
            f"task.1-{index}": (f"task.1-{index - 1}",)
            for index in range(2, task_count + 1)
        },
    }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_task_graph(
            proposal,
            delta,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies=dependencies,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.CYCLIC_DEPENDENCY


def test_task_completion_rejects_cyclic_predecessor_graph() -> None:
    proposal, delta, graph = _task_graph()
    for task in graph.tasks:
        graph = complete_change_task(
            graph,
            task.id,
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )
    tasks = list(graph.tasks)
    tasks[0] = tasks[0].model_copy(
        update={"depends_on": (TaskRef(kind="task_ref", target_id=tasks[-1].id),)}
    )
    cyclic = graph.model_copy(update={"tasks": tuple(tasks)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        complete_change_task(
            cyclic,
            tasks[0].id,
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.CYCLIC_DEPENDENCY


def test_task_completion_rejects_stale_subject_before_transition() -> None:
    proposal, delta, graph = _task_graph()
    tasks = list(graph.tasks)
    tasks[0] = tasks[0].model_copy(
        update={
            "subjects": (
                tasks[0].subjects[0].model_copy(update={"target_id": "use-case.stale"}),
            )
        }
    )
    stale = graph.model_copy(update={"tasks": tuple(tasks)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        complete_change_task(
            stale,
            tasks[0].id,
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.BROKEN_REFERENCE
    assert all(task.status is TaskStatus.PENDING for task in stale.tasks)
