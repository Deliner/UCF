from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from ucf.change_lifecycle import (
    ARCHIVE_RECORD_SCHEMA_URI,
    IMPLEMENTATION_RECORD_SCHEMA_URI,
    VERIFICATION_RECORD_SCHEMA_URI,
    ArchiveRecord,
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ImplementationRecord,
    VerificationRecord,
    canonical_change_lifecycle_json,
    delta_subject_ref,
    derive_archive_record,
    derive_behavior_delta,
    derive_implementation_record,
    derive_task_graph,
    derive_verification_record,
    parse_archive_record_json,
    parse_implementation_record_json,
    parse_verification_record_json,
    validate_archive_record,
    validate_implementation_record,
    validate_verification_record,
)
from ucf.implementation_evidence import derive_execution_verification_result_id
from ucf.ir import canonical_ir_json, parse_ir_json

from ._fixture_factory import (
    behavior_pair,
    completed_graph,
    evidence_context,
    lifecycle_chain,
)
from ._fixture_factory import (
    proposal as fixture_proposal,
)
from .test_task_graph_contract import _task_graph

_BASE_BEHAVIOR, _FINAL_BEHAVIOR = behavior_pair()


def _completed_graph(graph, delta, proposal):
    return completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
    )


def test_evidence_verification_and_archive_form_an_exact_immutable_chain() -> None:
    base, final = behavior_pair()
    proposal, delta, graph = _task_graph()
    graph = _completed_graph(graph, delta, proposal)
    contexts = (evidence_context(delta),)

    implementation = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    assert implementation.schema_uri == IMPLEMENTATION_RECORD_SCHEMA_URI
    encoded_implementation = canonical_change_lifecycle_json(implementation)
    assert parse_implementation_record_json(encoded_implementation) == implementation

    verification = derive_verification_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    validate_verification_record(
        verification,
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    assert verification.schema_uri == VERIFICATION_RECORD_SCHEMA_URI
    encoded_verification = canonical_change_lifecycle_json(verification)
    assert parse_verification_record_json(encoded_verification) == verification

    archive = derive_archive_record(
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base,
        final,
        evidence_contexts=contexts,
    )
    validate_archive_record(
        archive,
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base,
        final,
        evidence_contexts=contexts,
    )
    assert archive.schema_uri == ARCHIVE_RECORD_SCHEMA_URI
    assert archive.final_behavior == final
    encoded_archive = canonical_change_lifecycle_json(archive)
    assert parse_archive_record_json(encoded_archive) == archive
    assert isinstance(implementation, ImplementationRecord)
    assert isinstance(verification, VerificationRecord)
    assert isinstance(archive, ArchiveRecord)


def test_implementation_derivation_rejects_stale_task_delta_reference() -> None:
    chain = lifecycle_chain()
    stale_graph = chain.graph.model_copy(
        update={
            "delta": chain.graph.delta.model_copy(
                update={
                    "canonical_digest": chain.graph.delta.canonical_digest.model_copy(
                        update={"value": "f" * 64}
                    )
                }
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            stale_graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
            evidence_contexts=chain.evidence_contexts,
        )

    assert captured.value.code is (ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH)


def test_implementation_derivation_rejects_forged_task_source() -> None:
    chain = lifecycle_chain()
    tasks = list(chain.graph.tasks)
    source = tasks[0].source
    tasks[0] = tasks[0].model_copy(
        update={
            "source": source.model_copy(
                update={
                    "artifact_digest": source.artifact_digest.model_copy(
                        update={"value": "f" * 64}
                    )
                }
            )
        }
    )
    forged_graph = chain.graph.model_copy(update={"tasks": tuple(tasks)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            forged_graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
            evidence_contexts=chain.evidence_contexts,
        )

    assert captured.value.code is (ChangeLifecycleErrorCode.CONTENT_IDENTITY_MISMATCH)


@pytest.mark.parametrize("outcome", ["failed", "error"])
def test_nonpassing_evidence_is_retained_but_cannot_verify_or_archive(
    outcome: str,
) -> None:
    proposal, delta, graph = _task_graph()
    graph = _completed_graph(graph, delta, proposal)
    contexts = (evidence_context(delta, outcome),)
    implementation = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
        evidence_contexts=contexts,
    )
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=_BASE_BEHAVIOR,
        final_behavior=_FINAL_BEHAVIOR,
        evidence_contexts=contexts,
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_verification_record(
            implementation,
            graph,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            evidence_contexts=contexts,
        )
    assert captured.value.code is ChangeLifecycleErrorCode.EVIDENCE_NOT_PASSED


def test_archive_wire_rejects_semantically_invalid_embedded_behavior() -> None:
    archive = lifecycle_chain().archive
    payload = archive.model_dump(mode="json")
    final_behavior = payload["final_behavior"]
    removed_id = final_behavior["roots"][0]["target_id"]
    final_behavior["entities"] = [
        entity for entity in final_behavior["entities"] if entity["id"] != removed_id
    ]

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_archive_record_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.BROKEN_REFERENCE
    assert captured.value.location.startswith("$.final_behavior")


def test_removed_behavior_rejects_old_subject_execution_evidence() -> None:
    _, final = behavior_pair()
    base_payload = json.loads(canonical_ir_json(final))
    legacy = deepcopy(
        next(
            entity
            for entity in base_payload["entities"]
            if entity["kind"] == "provenance"
        )
    )
    legacy["id"] = "provenance.removed-implementation"
    base_payload["entities"].append(legacy)
    base = parse_ir_json(json.dumps(base_payload))
    proposal = fixture_proposal(base)
    delta = derive_behavior_delta(proposal, base, final)
    subject = delta_subject_ref(delta.entries[0])
    assignments = {
        task_id: (subject,) for task_id in ("task.1-1", "task.1-2", "task.1-3")
    }
    graph = derive_task_graph(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
        subject_assignments=assignments,
        dependencies={
            "task.1-2": ("task.1-1",),
            "task.1-3": ("task.1-2",),
        },
    )
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=base,
        final_behavior=final,
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=base,
            final_behavior=final,
            evidence_contexts=(),
        )

    assert captured.value.code is (
        ChangeLifecycleErrorCode.UNSUPPORTED_EVIDENCE_PROFILE
    )
    assert captured.value.location == "$.entries[0]"


def test_implementation_rejects_incomplete_tasks_and_wrong_subject() -> None:
    proposal, delta, graph = _task_graph()
    context = evidence_context(delta)
    with pytest.raises(ChangeLifecycleValidationError) as incomplete:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            evidence_contexts=(context,),
        )
    assert incomplete.value.code is ChangeLifecycleErrorCode.INCOMPLETE_TASKS

    complete = _completed_graph(graph, delta, proposal)
    target_id = "use-case.missing"
    request = context.result.request.model_copy(
        update={
            "subject": context.result.request.subject.model_copy(
                update={"target_id": target_id}
            ),
            "inputs": tuple(
                value.model_copy(
                    update={
                        "port": value.port.model_copy(
                            update={
                                "owner": value.port.owner.model_copy(
                                    update={"target_id": target_id}
                                )
                            }
                        )
                    }
                )
                for value in context.result.request.inputs
            ),
            "expected_outputs": tuple(
                value.model_copy(
                    update={
                        "port": value.port.model_copy(
                            update={
                                "owner": value.port.owner.model_copy(
                                    update={"target_id": target_id}
                                )
                            }
                        )
                    }
                )
                for value in context.result.request.expected_outputs
            ),
        }
    )
    provisional = context.result.model_copy(
        update={
            "request": request,
        }
    )
    wrong_subject = provisional.model_copy(
        update={
            "id": derive_execution_verification_result_id(
                provisional,
            )
        }
    )
    wrong_context = replace(context, result=wrong_subject)
    with pytest.raises(ChangeLifecycleValidationError) as wrong:
        derive_implementation_record(
            complete,
            delta,
            proposal,
            base_behavior=_BASE_BEHAVIOR,
            final_behavior=_FINAL_BEHAVIOR,
            evidence_contexts=(wrong_context,),
        )
    assert wrong.value.code is ChangeLifecycleErrorCode.EVIDENCE_CONTEXT_INVALID
    assert wrong.value.location == "$.evidence_contexts[0]"
