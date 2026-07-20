from __future__ import annotations

from collections.abc import Callable

import pytest

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    behavior_delta_ref,
    complete_change_task,
    delta_subject_ref,
    derive_implementation_record,
    derive_task_graph,
    derive_verification_record,
    validate_implementation_record,
    validate_task_graph,
    validate_verification_record,
)

from ._fixture_factory import lifecycle_chain


def test_task_validation_rejects_subject_absent_from_exact_behavior_pair() -> None:
    chain = lifecycle_chain()
    entry = chain.delta.entries[0]
    fabricated_entry = entry.model_copy(
        update={
            "base_subject": entry.base_subject.model_copy(
                update={"target_id": "use-case.fabricated"}
            ),
            "final_subject": entry.final_subject.model_copy(
                update={"target_id": "use-case.fabricated"}
            ),
        }
    )
    fabricated_delta = chain.delta.model_copy(update={"entries": (fabricated_entry,)})
    fabricated_subject = delta_subject_ref(fabricated_entry)
    fabricated_graph = chain.graph.model_copy(
        update={
            "delta": behavior_delta_ref(fabricated_delta),
            "tasks": tuple(
                task.model_copy(update={"subjects": (fabricated_subject,)})
                for task in chain.graph.tasks
            ),
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_task_graph(
            fabricated_graph,
            fabricated_delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INCOMPLETE_DELTA
    assert captured.value.location == "$.entries"


@pytest.mark.parametrize(
    "operation",
    (
        "derive_task_graph",
        "validate_task_graph",
        "complete_change_task",
        "derive_implementation_record",
        "validate_implementation_record",
        "derive_verification_record",
        "validate_verification_record",
    ),
)
def test_downstream_transitions_reject_wrong_final_behavior_context(
    operation: str,
) -> None:
    chain = lifecycle_chain()
    wrong_final = chain.base
    assignments = {task.id: task.subjects for task in chain.graph.tasks}
    dependencies = {
        task.id: tuple(reference.target_id for reference in task.depends_on)
        for task in chain.graph.tasks
        if task.depends_on
    }
    calls: dict[str, Callable[[], object]] = {
        "derive_task_graph": lambda: derive_task_graph(
            chain.proposal,
            chain.delta,
            base_behavior=chain.base,
            final_behavior=wrong_final,
            subject_assignments=assignments,
            dependencies=dependencies,
        ),
        "validate_task_graph": lambda: validate_task_graph(
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=wrong_final,
        ),
        "complete_change_task": lambda: complete_change_task(
            chain.graph,
            chain.graph.tasks[0].id,
            delta=chain.delta,
            proposal=chain.proposal,
            base_behavior=chain.base,
            final_behavior=wrong_final,
        ),
        "derive_implementation_record": lambda: derive_implementation_record(
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=wrong_final,
            evidence_contexts=chain.evidence_contexts,
        ),
        "validate_implementation_record": lambda: validate_implementation_record(
            chain.implementation,
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=wrong_final,
            evidence_contexts=chain.evidence_contexts,
        ),
        "derive_verification_record": lambda: derive_verification_record(
            chain.implementation,
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=wrong_final,
            evidence_contexts=chain.evidence_contexts,
        ),
        "validate_verification_record": lambda: validate_verification_record(
            chain.verification,
            chain.implementation,
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=wrong_final,
            evidence_contexts=chain.evidence_contexts,
        ),
    }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        calls[operation]()

    assert captured.value.code is (ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH)
    assert captured.value.location == "$.final_behavior"
