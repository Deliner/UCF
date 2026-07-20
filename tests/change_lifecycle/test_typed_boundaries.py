from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import Field

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ChangeProposal,
    OpenSpecArtifact,
    OpenSpecArtifactRole,
    TaskStatus,
    canonical_change_lifecycle_json,
    complete_change_task,
    derive_task_graph,
    parse_archive_record_json,
    parse_behavior_delta_json,
    parse_change_proposal_json,
    parse_implementation_record_json,
    parse_task_graph_json,
    parse_verification_record_json,
    validate_archive_record,
    validate_behavior_delta,
    validate_change_proposal,
    validate_implementation_record,
    validate_task_graph,
    validate_verification_record,
)

from ._fixture_factory import behavior_pair, lifecycle_chain, task_graph

_BASE_BEHAVIOR, _FINAL_BEHAVIOR = behavior_pair()


class _ExtendedProposal(ChangeProposal):
    verified: bool


class _ExtendedArtifact(OpenSpecArtifact):
    executable: bool


class _ExcludedExtendedArtifact(OpenSpecArtifact):
    executable: bool = Field(exclude=True)


class _EmptyExtendedArtifact(OpenSpecArtifact):
    pass


class _HiddenTuple(tuple):
    executable: bool


class _HiddenString(str):
    executable: bool


class _HiddenInt(int):
    executable: bool


@pytest.mark.parametrize(
    "resource_name",
    (
        "proposal",
        "delta",
        "task_graph",
        "implementation",
        "verification",
        "archive",
    ),
)
def test_contextual_validators_reparse_typed_lifecycle_resources(
    resource_name: str,
) -> None:
    chain = lifecycle_chain()
    validators: dict[str, tuple[object, Callable[[object], None]]] = {
        "proposal": (
            chain.proposal.model_copy(update={"change_lifecycle_version": "9.9.9"}),
            lambda resource: validate_change_proposal(resource, chain.base),
        ),
        "delta": (
            chain.delta.model_copy(update={"change_lifecycle_version": "9.9.9"}),
            lambda resource: validate_behavior_delta(
                resource,
                chain.proposal,
                chain.base,
                chain.final,
            ),
        ),
        "task_graph": (
            chain.graph.model_copy(update={"change_lifecycle_version": "9.9.9"}),
            lambda resource: validate_task_graph(
                resource,
                chain.delta,
                chain.proposal,
                base_behavior=chain.base,
                final_behavior=chain.final,
            ),
        ),
        "implementation": (
            chain.implementation.model_copy(
                update={"change_lifecycle_version": "9.9.9"}
            ),
            lambda resource: validate_implementation_record(
                resource,
                chain.graph,
                chain.delta,
                chain.proposal,
                base_behavior=chain.base,
                final_behavior=chain.final,
                evidence_contexts=chain.evidence_contexts,
            ),
        ),
        "verification": (
            chain.verification.model_copy(update={"outcome": "rejected"}),
            lambda resource: validate_verification_record(
                resource,
                chain.implementation,
                chain.graph,
                chain.delta,
                chain.proposal,
                base_behavior=chain.base,
                final_behavior=chain.final,
                evidence_contexts=chain.evidence_contexts,
            ),
        ),
        "archive": (
            chain.archive.model_copy(
                update={
                    "status": "not-archived",
                    "change_lifecycle_version": "9.9.9",
                }
            ),
            lambda resource: validate_archive_record(
                resource,
                chain.proposal,
                chain.delta,
                chain.graph,
                chain.implementation,
                chain.verification,
                chain.base,
                chain.final,
                evidence_contexts=chain.evidence_contexts,
            ),
        ),
    }
    resource, validate = validators[resource_name]

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate(resource)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_typed_lifecycle_boundary_rejects_hidden_unknown_field() -> None:
    chain = lifecycle_chain()
    proposal = chain.proposal.model_copy(update={"verified": True})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_change_proposal(proposal, chain.base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_typed_lifecycle_boundary_rejects_resource_subclass() -> None:
    chain = lifecycle_chain()
    payload = chain.proposal.model_dump(mode="python")
    payload["verified"] = True
    proposal = _ExtendedProposal.model_validate(payload)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_change_proposal(proposal, chain.base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_typed_lifecycle_boundary_rejects_nested_resource_subclass() -> None:
    chain = lifecycle_chain()
    artifact = chain.proposal.openspec.artifacts[0]
    payload = artifact.model_dump(mode="python")
    payload["executable"] = True
    extended = _ExtendedArtifact.model_validate(payload)
    artifacts = (extended, *chain.proposal.openspec.artifacts[1:])
    proposal = chain.proposal.model_copy(
        update={
            "openspec": chain.proposal.openspec.model_copy(
                update={"artifacts": artifacts}
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_change_proposal(proposal, chain.base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize(
    "artifact_type",
    (
        _ExcludedExtendedArtifact,
        _EmptyExtendedArtifact,
    ),
)
def test_canonical_boundary_rejects_invisible_nested_runtime_subclass(
    artifact_type: type[OpenSpecArtifact],
) -> None:
    chain = lifecycle_chain()
    artifact = chain.proposal.openspec.artifacts[0]
    payload = artifact.model_dump(mode="python")
    if "executable" in artifact_type.model_fields:
        payload["executable"] = True
    extended = artifact_type.model_validate(payload)
    proposal = chain.proposal.model_copy(
        update={
            "openspec": chain.proposal.openspec.model_copy(
                update={
                    "artifacts": (
                        extended,
                        *chain.proposal.openspec.artifacts[1:],
                    )
                }
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(proposal)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.openspec.artifacts[0]"


def test_canonical_boundary_rejects_nested_runtime_tuple_subclass() -> None:
    chain = lifecycle_chain()
    artifacts = _HiddenTuple(chain.proposal.openspec.artifacts)
    artifacts.executable = True
    proposal = chain.proposal.model_copy(
        update={
            "openspec": chain.proposal.openspec.model_copy(
                update={"artifacts": artifacts}
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(proposal)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.openspec.artifacts"


@pytest.mark.parametrize(
    ("field", "value", "location"),
    (
        ("kind", _HiddenString("change_proposal"), "$.kind"),
        ("change_id", _HiddenString("require-quote-order-total"), "$.change_id"),
    ),
)
def test_canonical_boundary_rejects_hidden_string_subclass(
    field: str,
    value: _HiddenString,
    location: str,
) -> None:
    value.executable = True
    proposal = lifecycle_chain().proposal.model_copy(update={field: value})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(proposal)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == location


def test_canonical_boundary_rejects_hidden_integer_subclass() -> None:
    _, _, graph = task_graph()
    order = _HiddenInt(graph.tasks[0].order)
    order.executable = True
    first = graph.tasks[0].model_copy(update={"order": order})
    graph = graph.model_copy(update={"tasks": (first, *graph.tasks[1:])})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(graph)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.tasks[0].order"


def test_plain_string_artifact_role_cannot_change_next_transition() -> None:
    proposal, delta, expected = task_graph()
    task_index = next(
        index
        for index, artifact in enumerate(proposal.openspec.artifacts)
        if artifact.role is OpenSpecArtifactRole.TASKS
    )
    artifacts = list(proposal.openspec.artifacts)
    artifacts[task_index] = artifacts[task_index].model_copy(update={"role": "tasks"})
    raw = proposal.model_copy(
        update={
            "openspec": proposal.openspec.model_copy(
                update={"artifacts": tuple(artifacts)}
            )
        }
    )
    reparsed = parse_change_proposal_json(_unsafe_model_json(raw))
    assignments = {task.id: task.subjects for task in expected.tasks}
    dependencies = {
        task.id: tuple(reference.target_id for reference in task.depends_on)
        for task in expected.tasks
    }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_task_graph(
            raw,
            delta,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies=dependencies,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == f"$.openspec.artifacts[{task_index}].role"
    assert (
        derive_task_graph(
            reparsed,
            delta,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies=dependencies,
        )
        == expected
    )


def test_plain_mapping_cannot_replace_declared_model_in_next_transition() -> None:
    proposal, delta, expected = task_graph()
    raw = proposal.model_copy(
        update={"openspec": proposal.openspec.model_dump(mode="python")}
    )
    reparsed = parse_change_proposal_json(_unsafe_model_json(raw))
    assignments = {task.id: task.subjects for task in expected.tasks}
    dependencies = {
        task.id: tuple(reference.target_id for reference in task.depends_on)
        for task in expected.tasks
    }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_task_graph(
            raw,
            delta,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies=dependencies,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.openspec"
    assert (
        derive_task_graph(
            reparsed,
            delta,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies=dependencies,
        )
        == expected
    )


@pytest.mark.parametrize(
    "status",
    (
        "completed",
        _HiddenString("completed"),
    ),
)
def test_string_task_status_cannot_change_next_transition(
    status: str,
) -> None:
    proposal, delta, graph = task_graph()
    if isinstance(status, _HiddenString):
        status.executable = True
    first = graph.tasks[0].model_copy(update={"status": status})
    raw = graph.model_copy(update={"tasks": (first, *graph.tasks[1:])})
    reparsed = parse_task_graph_json(_unsafe_model_json(raw))

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        complete_change_task(
            raw,
            "task.1-2",
            delta=delta,
            proposal=proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.tasks[0].status"
    successor = complete_change_task(
        reparsed,
        "task.1-2",
        delta=delta,
        proposal=proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )
    assert successor.tasks[1].status is TaskStatus.COMPLETED


@pytest.mark.parametrize(
    ("resource_name", "parser"),
    (
        ("proposal", parse_change_proposal_json),
        ("delta", parse_behavior_delta_json),
        ("graph", parse_task_graph_json),
        ("implementation", parse_implementation_record_json),
        ("verification", parse_verification_record_json),
        ("archive", parse_archive_record_json),
    ),
)
def test_exact_nested_lifecycle_models_round_trip_byte_stably(
    resource_name: str,
    parser: Callable[[bytes], object],
) -> None:
    resource = getattr(lifecycle_chain(), resource_name)

    encoded = canonical_change_lifecycle_json(resource)

    assert canonical_change_lifecycle_json(parser(encoded)) == encoded


@pytest.mark.parametrize(
    ("resource_name", "parser"),
    (
        ("proposal", parse_change_proposal_json),
        ("delta", parse_behavior_delta_json),
        ("graph", parse_task_graph_json),
        ("implementation", parse_implementation_record_json),
        ("verification", parse_verification_record_json),
        ("archive", parse_archive_record_json),
    ),
)
@pytest.mark.parametrize(
    "payload_kind",
    ("none", "integer", "bytearray"),
)
def test_wire_parser_rejects_non_string_or_bytes_runtime_payload(
    resource_name: str,
    parser: Callable[[object], object],
    payload_kind: str,
) -> None:
    resource = getattr(lifecycle_chain(), resource_name)
    valid = canonical_change_lifecycle_json(resource)
    invalid: object = {
        "none": None,
        "integer": 1,
        "bytearray": bytearray(valid),
    }[payload_kind]

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parser(invalid)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_JSON
    assert captured.value.location == "$"


def _unsafe_model_json(document: object) -> bytes:
    return (
        json.dumps(
            document.model_dump(
                mode="json",
                serialize_as_any=True,
            ),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
