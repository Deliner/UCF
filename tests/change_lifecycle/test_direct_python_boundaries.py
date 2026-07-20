from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from types import MappingProxyType

import pytest

from tests.onboarding.test_candidates import _candidate
from tests.onboarding.test_codec import (
    _request as onboarding_request,
)
from tests.onboarding.test_codec import (
    _result as discovery_result,
)
from tests.onboarding.test_decisions import (
    _base_decision_set,
    _candidate_ref,
)
from ucf.change_lifecycle import (
    AddedBehavior,
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ExecutionEvidenceContext,
    ModifiedBehavior,
    RemovedBehavior,
    behavior_delta_ref,
    canonical_change_lifecycle_json,
    change_proposal_ref,
    complete_change_task,
    delta_subject_ref,
    derive_archive_record,
    derive_behavior_delta,
    derive_implementation_record,
    derive_task_graph,
    derive_verification_record,
    implementation_record_ref,
    task_graph_ref,
    validate_archive_record,
    validate_behavior_delta,
    validate_change_proposal,
    validate_implementation_record,
    validate_task_graph,
    validate_verification_record,
    verification_record_ref,
)
from ucf.implementation_evidence import (
    ExecutionVerificationResult,
    canonical_implementation_evidence_digest,
    derive_execution_verification_result_id,
    derive_implementation_mapping_result_id,
)
from ucf.ir.models import BehaviorIR, Digest, EntityKind, EntityRef
from ucf.ir.trust_models import BehaviorEntityRef
from ucf.onboarding import (
    AcceptedDecision,
    DiscoveryCandidate,
    OnboardingBundle,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    derive_decision_id,
)

from ._fixture_factory import (
    behavior_pair,
    behavior_ref,
    completed_graph,
    evidence_context,
    lifecycle_chain,
    task_graph,
)


class _ExecutionVerificationResultSubclass(ExecutionVerificationResult):
    pass


class _BehaviorIRSubclass(BehaviorIR):
    pass


_FIXTURE_BASE_BEHAVIOR, _FIXTURE_FINAL_BEHAVIOR = behavior_pair()


def _unique_evidence_context(
    template: ExecutionEvidenceContext,
    bundle: OnboardingBundle,
    candidate: DiscoveryCandidate,
    target: BehaviorEntityRef,
    index: int,
) -> ExecutionEvidenceContext:
    suffix = f"bound-{index:03d}"

    mapping_request = template.mapping_result.request.model_copy(
        update={
            "onboarding": template.mapping_result.request.onboarding.model_copy(
                update={
                    "canonical_digest": canonical_onboarding_digest(bundle),
                }
            ),
            "behavior": bundle.behavior,
            "inventory": bundle.inventory,
            "targets": (target,),
        }
    )
    mapping_binding = template.mapping_result.bindings[0].model_copy(
        update={
            "behavior": target,
            "source_records": candidate.evidence,
        }
    )
    provisional_mapping = template.mapping_result.model_copy(
        update={
            "id": f"mapping.{'0' * 64}",
            "request": mapping_request,
            "bindings": (mapping_binding,),
        }
    )
    mapping = provisional_mapping.model_copy(
        update={
            "id": derive_implementation_mapping_result_id(provisional_mapping),
        }
    )

    owner = EntityRef(
        kind="entity_ref",
        target_kind=target.target_kind,
        target_id=target.target_id,
    )
    request = template.result.request.model_copy(
        update={
            "adapter_procedure_uri": (
                f"urn:ucf:fixture-adapter:execute-{suffix}:1.0.0"
            ),
            "mapping": template.result.request.mapping.model_copy(
                update={
                    "target_id": mapping.id,
                    "canonical_digest": (
                        canonical_implementation_evidence_digest(mapping)
                    ),
                }
            ),
            "base_behavior": (
                template.result.request.base_behavior.model_copy(
                    update={
                        "document_id": target.document_id,
                        "ir_version": target.ir_version,
                        "canonical_digest": target.canonical_digest,
                    }
                )
            ),
            "subject": target,
            "inputs": tuple(
                value.model_copy(
                    update={
                        "port": value.port.model_copy(
                            update={"owner": owner},
                        )
                    }
                )
                for value in template.result.request.inputs
            ),
            "expected_outputs": tuple(
                value.model_copy(
                    update={
                        "port": value.port.model_copy(
                            update={"owner": owner},
                        )
                    }
                )
                for value in template.result.request.expected_outputs
            ),
            "source": template.result.request.source.model_copy(
                update={
                    "subject_uri": bundle.inventory.subject_uri,
                    "source_revision": bundle.inventory.source_revision,
                    "records": candidate.evidence,
                }
            ),
            "environment": template.result.request.environment.model_copy(
                update={
                    "identity_uri": (f"urn:ucf:fixture-environment:{suffix}:1.0.0"),
                    "revision": Digest(
                        kind="digest",
                        algorithm="sha-256",
                        value=f"{index:064x}",
                    ),
                }
            ),
            "check": template.result.request.check.model_copy(
                update={
                    "id": f"check.{suffix}",
                    "procedure_uri": (f"urn:ucf:fixture-check:{suffix}:1.0.0"),
                }
            ),
        }
    )
    provisional_result = template.result.model_copy(
        update={
            "id": f"result.{'0' * 64}",
            "request": request,
            "procedure_uri": request.adapter_procedure_uri,
        }
    )
    result = provisional_result.model_copy(
        update={
            "id": derive_execution_verification_result_id(provisional_result),
        }
    )
    return replace(
        template,
        result=result,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=bundle.inventory,
    )


def _oversized_onboarding_bundle() -> OnboardingBundle:
    candidates = tuple(
        sorted(
            (_candidate(f"bound-{index:03d}") for index in range(257)),
            key=lambda candidate: candidate.id,
        )
    )
    discovery = discovery_result().model_copy(
        update={"candidates": candidates},
    )
    decision_context = _base_decision_set(discovery)
    decisions = []
    for candidate in candidates:
        provisional = AcceptedDecision(
            kind="accepted_decision",
            id=f"decision.{'0' * 64}",
            candidate=_candidate_ref(discovery, candidate),
            reason="Accepted for bounded-input regression coverage.",
        )
        decisions.append(
            provisional.model_copy(
                update={
                    "id": derive_decision_id(
                        provisional,
                        decision_context,
                    ),
                }
            )
        )
    return build_onboarding_bundle(
        onboarding_request().inventory,
        discovery,
        decision_context.model_copy(
            update={
                "decisions": tuple(
                    sorted(
                        decisions,
                        key=lambda decision: decision.candidate.candidate_id,
                    )
                )
            }
        ),
    )


def _oversized_evidence_input():
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    template = evidence_context(delta)
    bundle = _oversized_onboarding_bundle()
    materializations = {
        materialization.candidate.candidate_id: materialization.root
        for materialization in bundle.baseline.materializations
    }
    candidates_and_targets = tuple(
        sorted(
            (
                (candidate, materializations[candidate.id])
                for candidate in bundle.discovery.candidates
            ),
            key=lambda item: item[1].target_id,
        )
    )
    contexts = tuple(
        _unique_evidence_context(
            template,
            bundle,
            candidate,
            target,
            index,
        )
        for index, (candidate, target) in enumerate(candidates_and_targets)
    )
    final_behavior = bundle.behavior
    base_behavior = final_behavior.model_copy(
        update={
            "entities": tuple(
                entity.model_copy(
                    update={
                        "output_ports": tuple(
                            port.model_copy(update={"required": False})
                            for port in entity.output_ports
                        )
                    }
                )
                if entity.kind is EntityKind.USE_CASE
                else entity
                for entity in final_behavior.entities
            )
        },
    )
    proposal = proposal.model_copy(
        update={"base_behavior": behavior_ref(base_behavior)}
    )
    delta = derive_behavior_delta(
        proposal,
        base_behavior,
        final_behavior,
    )
    entries = delta.entries
    subjects = tuple(delta_subject_ref(entry) for entry in entries)
    graph = graph.model_copy(
        update={
            "delta": behavior_delta_ref(delta),
            "tasks": tuple(
                task.model_copy(update={"subjects": subjects}) for task in graph.tasks
            ),
        }
    )
    return proposal, delta, graph, contexts, base_behavior, final_behavior


def test_delta_subject_ref_rejects_corrupted_typed_discriminator() -> None:
    _, delta, _ = task_graph()
    corrupted = delta.entries[0].model_copy(update={"kind": "removed_behavior"})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        delta_subject_ref(corrupted)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith("$.entry")


@pytest.mark.parametrize(
    ("operation", "input_kind", "location"),
    (
        ("change_proposal_ref", "none", "$.proposal"),
        ("change_proposal_ref", "wrong-kind", "$.proposal"),
        ("behavior_delta_ref", "none", "$.delta"),
        ("behavior_delta_ref", "wrong-kind", "$.delta"),
        ("task_graph_ref", "none", "$.tasks"),
        ("task_graph_ref", "wrong-kind", "$.tasks"),
        ("implementation_record_ref", "none", "$.implementation"),
        ("implementation_record_ref", "wrong-kind", "$.implementation"),
        ("verification_record_ref", "none", "$.verification"),
        ("verification_record_ref", "wrong-kind", "$.verification"),
    ),
)
def test_exported_reference_helpers_reject_nonexact_document_types(
    operation: str,
    input_kind: str,
    location: str,
) -> None:
    chain = lifecycle_chain()
    wrong_kind = {
        "change_proposal_ref": chain.delta,
        "behavior_delta_ref": chain.proposal,
        "task_graph_ref": chain.delta,
        "implementation_record_ref": chain.graph,
        "verification_record_ref": chain.implementation,
    }
    value = None if input_kind == "none" else wrong_kind[operation]
    calls: dict[str, Callable[[], object]] = {
        "change_proposal_ref": lambda: change_proposal_ref(value),  # type: ignore[arg-type]
        "behavior_delta_ref": lambda: behavior_delta_ref(value),  # type: ignore[arg-type]
        "task_graph_ref": lambda: task_graph_ref(value),  # type: ignore[arg-type]
        "implementation_record_ref": lambda: implementation_record_ref(value),  # type: ignore[arg-type]
        "verification_record_ref": lambda: verification_record_ref(value),  # type: ignore[arg-type]
    }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        calls[operation]()

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == location


@pytest.mark.parametrize(
    ("mutation", "location"),
    [
        ("subject-kind", "$.subject_assignments"),
        ("dependency-id", "$.dependencies"),
    ],
)
def test_task_derivation_rejects_malformed_direct_python_inputs(
    mutation: str,
    location: str,
) -> None:
    proposal, delta, graph = task_graph()
    assignments = {task.id: task.subjects for task in graph.tasks}
    dependencies = {
        task.id: tuple(reference.target_id for reference in task.depends_on)
        for task in graph.tasks
        if task.depends_on
    }
    if mutation == "subject-kind":
        first = graph.tasks[0]
        assignments[first.id] = (
            first.subjects[0].model_copy(update={"target_kind": "bogus"}),
        )
    else:
        dependencies[graph.tasks[1].id] = ("bad id",)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_task_graph(
            proposal,
            delta,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            subject_assignments=assignments,
            dependencies=dependencies,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith(location)


def test_task_validation_rejects_delta_with_forged_base_behavior() -> None:
    proposal, delta, graph = task_graph()
    entry = delta.entries[0]
    assert isinstance(entry, ModifiedBehavior)
    forged_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value="f" * 64,
    )
    delta = delta.model_copy(
        update={
            "base_behavior": delta.base_behavior.model_copy(
                update={"canonical_digest": forged_digest},
            ),
            "entries": (
                entry.model_copy(
                    update={
                        "base_subject": entry.base_subject.model_copy(
                            update={"canonical_digest": forged_digest},
                        )
                    }
                ),
            ),
        }
    )
    graph = graph.model_copy(update={"delta": behavior_delta_ref(delta)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        validate_task_graph(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
        )

    assert captured.value.code is (ChangeLifecycleErrorCode.DOCUMENT_IDENTITY_MISMATCH)
    assert captured.value.location == "$.base_behavior"


@pytest.mark.parametrize(
    ("entry_kind", "field"),
    (
        ("added", "final_subject"),
        ("modified-base", "base_subject"),
        ("modified-final", "final_subject"),
        ("removed", "base_subject"),
    ),
)
def test_delta_rejects_entry_document_mismatch(
    entry_kind: str,
    field: str,
) -> None:
    _, delta, _ = task_graph()
    original = delta.entries[0]
    assert isinstance(original, ModifiedBehavior)
    forged_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value="f" * 64,
    )
    if entry_kind == "added":
        entry = AddedBehavior(
            kind="added_behavior",
            final_subject=original.final_subject.model_copy(
                update={"canonical_digest": forged_digest},
            ),
            final_is_root=True,
        )
    elif entry_kind == "removed":
        entry = RemovedBehavior(
            kind="removed_behavior",
            base_subject=original.base_subject.model_copy(
                update={"canonical_digest": forged_digest},
            ),
            base_is_root=True,
        )
    else:
        field = entry_kind.removeprefix("modified-") + "_subject"
        entry = original.model_copy(
            update={
                field: getattr(original, field).model_copy(
                    update={"canonical_digest": forged_digest},
                )
            }
        )
    delta = delta.model_copy(update={"entries": (entry,)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(delta)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$"
    assert field in str(captured.value)


def test_delta_rejects_identical_base_and_final_behavior_digests() -> None:
    _, delta, _ = task_graph()
    delta = delta.model_copy(
        update={
            "final_behavior": delta.final_behavior.model_copy(
                update={
                    "canonical_digest": delta.base_behavior.canonical_digest,
                }
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(delta)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$"


def test_implementation_derivation_rejects_result_runtime_subclass() -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    subclass_result = _ExecutionVerificationResultSubclass.model_validate(
        context.result.model_dump(mode="python")
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=(replace(context, result=subclass_result),),
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.evidence_contexts[0].result"

    exact = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
        evidence_contexts=(context,),
    )
    assert canonical_change_lifecycle_json(exact)


def test_archive_derivation_rejects_final_behavior_runtime_subclass() -> None:
    chain = lifecycle_chain()
    subclass_final = _BehaviorIRSubclass.model_validate(
        chain.final.model_dump(mode="python")
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_archive_record(
            chain.proposal,
            chain.delta,
            chain.graph,
            chain.implementation,
            chain.verification,
            chain.base,
            subclass_final,
            evidence_contexts=chain.evidence_contexts,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.final_behavior"

    exact = derive_archive_record(
        chain.proposal,
        chain.delta,
        chain.graph,
        chain.implementation,
        chain.verification,
        chain.base,
        chain.final,
        evidence_contexts=chain.evidence_contexts,
    )
    assert canonical_change_lifecycle_json(exact)


@pytest.mark.parametrize(
    "operation",
    (
        "validate_change_proposal",
        "derive_behavior_delta",
        "validate_behavior_delta",
        "delta_subject_ref",
        "derive_task_graph",
        "validate_task_graph",
        "complete_change_task",
        "derive_implementation_record",
        "validate_implementation_record",
        "derive_verification_record",
        "validate_verification_record",
        "derive_archive_record",
        "validate_archive_record",
    ),
)
def test_exported_transitions_reject_invalid_declared_root_types(
    operation: str,
) -> None:
    chain = lifecycle_chain()
    context = chain.evidence_contexts
    calls: dict[str, Callable[[], object]] = {
        "validate_change_proposal": lambda: validate_change_proposal(
            None,
            chain.base,  # type: ignore[arg-type]
        ),
        "derive_behavior_delta": lambda: derive_behavior_delta(
            chain.proposal,
            chain.base,
            None,  # type: ignore[arg-type]
        ),
        "validate_behavior_delta": lambda: validate_behavior_delta(
            None,  # type: ignore[arg-type]
            chain.proposal,
            chain.base,
            chain.final,
        ),
        "delta_subject_ref": lambda: delta_subject_ref(
            None  # type: ignore[arg-type]
        ),
        "derive_task_graph": lambda: derive_task_graph(
            chain.proposal,
            chain.delta,
            base_behavior=chain.base,
            final_behavior=chain.final,
            subject_assignments=None,  # type: ignore[arg-type]
            dependencies={},
        ),
        "validate_task_graph": lambda: validate_task_graph(
            None,
            chain.delta,
            chain.proposal,  # type: ignore[arg-type]
            base_behavior=chain.base,
            final_behavior=chain.final,
        ),
        "complete_change_task": lambda: complete_change_task(
            chain.graph,
            None,  # type: ignore[arg-type]
            delta=chain.delta,
            proposal=chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
        ),
        "derive_implementation_record": lambda: derive_implementation_record(
            None,  # type: ignore[arg-type]
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
            evidence_contexts=context,
        ),
        "validate_implementation_record": lambda: validate_implementation_record(
            None,  # type: ignore[arg-type]
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
            evidence_contexts=context,
        ),
        "derive_verification_record": lambda: derive_verification_record(
            None,  # type: ignore[arg-type]
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
            evidence_contexts=context,
        ),
        "validate_verification_record": lambda: validate_verification_record(
            None,  # type: ignore[arg-type]
            chain.implementation,
            chain.graph,
            chain.delta,
            chain.proposal,
            base_behavior=chain.base,
            final_behavior=chain.final,
            evidence_contexts=context,
        ),
        "derive_archive_record": lambda: derive_archive_record(
            None,  # type: ignore[arg-type]
            chain.delta,
            chain.graph,
            chain.implementation,
            chain.verification,
            chain.base,
            chain.final,
            evidence_contexts=context,
        ),
        "validate_archive_record": lambda: validate_archive_record(
            None,  # type: ignore[arg-type]
            chain.proposal,
            chain.delta,
            chain.graph,
            chain.implementation,
            chain.verification,
            chain.base,
            chain.final,
            evidence_contexts=context,
        ),
    }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        calls[operation]()

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize(
    ("mutation", "location"),
    (
        ("subject-assignments-none", "$.subject_assignments"),
        ("dependencies-none", "$.dependencies"),
        ("subject-assignment-list", "$.subject_assignments"),
        ("dependency-list", "$.dependencies"),
    ),
)
def test_task_derivation_rejects_invalid_mapping_boundaries(
    mutation: str,
    location: str,
) -> None:
    proposal, delta, graph = task_graph()
    assignments = {task.id: task.subjects for task in graph.tasks}
    dependencies = {
        task.id: tuple(reference.target_id for reference in task.depends_on)
        for task in graph.tasks
        if task.depends_on
    }
    subject_input: object = assignments
    dependency_input: object = dependencies
    if mutation == "subject-assignments-none":
        subject_input = None
    elif mutation == "dependencies-none":
        dependency_input = None
    elif mutation == "subject-assignment-list":
        subject_input = {
            **assignments,
            graph.tasks[0].id: list(graph.tasks[0].subjects),
        }
    else:
        dependency_input = {
            **dependencies,
            graph.tasks[1].id: [
                reference.target_id for reference in graph.tasks[1].depends_on
            ],
        }

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_task_graph(
            proposal,
            delta,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            subject_assignments=subject_input,  # type: ignore[arg-type]
            dependencies=dependency_input,  # type: ignore[arg-type]
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith(location)


@pytest.mark.parametrize(
    ("mutation", "location"),
    (
        ("contexts-list", "$.evidence_contexts"),
        ("context-object", "$.evidence_contexts[0]"),
        ("result", "$.evidence_contexts[0].result"),
        ("mapping-result", "$.evidence_contexts[0].mapping_result"),
        ("bundle", "$.evidence_contexts[0].bundle"),
        ("inventory", "$.evidence_contexts[0].current_inventory"),
        (
            "mapping-adapter",
            "$.evidence_contexts[0].mapping_initialized_adapter",
        ),
        (
            "verification-adapter",
            "$.evidence_contexts[0].initialized_adapter",
        ),
        ("capabilities", "$.evidence_contexts[0].negotiated_capabilities"),
    ),
)
def test_implementation_derivation_rejects_invalid_evidence_context_types(
    mutation: str,
    location: str,
) -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    contexts: object = (context,)
    if mutation == "contexts-list":
        contexts = [context]
    elif mutation == "context-object":
        contexts = (object(),)
    else:
        field = {
            "result": "result",
            "mapping-result": "mapping_result",
            "bundle": "bundle",
            "inventory": "current_inventory",
            "mapping-adapter": "mapping_initialized_adapter",
            "verification-adapter": "initialized_adapter",
            "capabilities": "negotiated_capabilities",
        }[mutation]
        contexts = (replace(context, **{field: None}),)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=contexts,  # type: ignore[arg-type]
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith(location)


def test_task_derivation_accepts_mapping_implementations() -> None:
    proposal, delta, graph = task_graph()
    assignments = MappingProxyType({task.id: task.subjects for task in graph.tasks})
    dependencies = MappingProxyType(
        {
            task.id: tuple(reference.target_id for reference in task.depends_on)
            for task in graph.tasks
            if task.depends_on
        }
    )

    derived = derive_task_graph(
        proposal,
        delta,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
        subject_assignments=assignments,
        dependencies=dependencies,
    )

    assert derived == graph


def test_implementation_derivation_rejects_excess_evidence_contexts() -> None:
    (
        proposal,
        delta,
        graph,
        contexts,
        base_behavior,
        final_behavior,
    ) = _oversized_evidence_input()
    assert len({context.result.id for context in contexts}) == 257
    assert len({context.result.request.subject for context in contexts}) == 257

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=base_behavior,
            final_behavior=final_behavior,
            evidence_contexts=contexts,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.evidence_contexts"


@pytest.mark.parametrize(
    "mutation",
    ("too-many", "invalid-name", "invalid-version"),
)
def test_implementation_derivation_rejects_invalid_capability_selections(
    mutation: str,
) -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    capabilities = dict(context.negotiated_capabilities)
    if mutation == "too-many":
        capabilities.update(
            {f"capability.extra-{index}": "1.0.0" for index in range(255)}
        )
    elif mutation == "invalid-name":
        capabilities["bad capability"] = "1.0.0"
    else:
        capabilities["capability.extra"] = "not-semver"

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=(
                replace(
                    context,
                    negotiated_capabilities=capabilities,
                ),
            ),
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith(
        "$.evidence_contexts[0].negotiated_capabilities"
    )


@pytest.mark.parametrize(
    ("mutation", "location"),
    (
        ("mapping-request", "$.evidence_contexts[0].mapping_result"),
        ("result-request", "$.evidence_contexts[0].result"),
    ),
)
def test_implementation_derivation_rejects_corrupted_nested_evidence_models(
    mutation: str,
    location: str,
) -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    if mutation == "mapping-request":
        provisional = context.mapping_result.model_copy(
            update={"request": None},
        )
        corrupted = provisional.model_copy(
            update={
                "id": derive_implementation_mapping_result_id(provisional),
            }
        )
        context = replace(context, mapping_result=corrupted)
    else:
        provisional = context.result.model_copy(update={"request": None})
        corrupted = provisional.model_copy(
            update={
                "id": derive_execution_verification_result_id(provisional),
            }
        )
        context = replace(context, result=corrupted)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=(context,),
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith(location)


@pytest.mark.parametrize(
    ("mutation", "location"),
    (
        ("bundle", "$.evidence_contexts[0].bundle"),
        ("inventory", "$.evidence_contexts[0].current_inventory"),
        (
            "mapping-adapter",
            "$.evidence_contexts[0].mapping_initialized_adapter",
        ),
        (
            "verification-adapter",
            "$.evidence_contexts[0].initialized_adapter",
        ),
    ),
)
def test_implementation_derivation_rejects_corrupted_context_models(
    mutation: str,
    location: str,
) -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    if mutation == "bundle":
        context = replace(
            context,
            bundle=context.bundle.model_copy(update={"behavior": None}),
        )
    elif mutation == "inventory":
        context = replace(
            context,
            current_inventory=context.current_inventory.model_copy(
                update={"records": None},
            ),
        )
    elif mutation == "mapping-adapter":
        context = replace(
            context,
            mapping_initialized_adapter=(
                context.mapping_initialized_adapter.model_copy(
                    update={"name": None},
                )
            ),
        )
    else:
        context = replace(
            context,
            initialized_adapter=context.initialized_adapter.model_copy(
                update={"version": None},
            ),
        )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=(context,),
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith(location)


def test_implementation_derivation_maps_invalid_onboarding_context() -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    context = replace(
        context,
        bundle=context.bundle.model_copy(
            update={
                "capture_context": context.bundle.capture_context.model_copy(
                    update={"captured_at": "2026-07-19T12:00:01Z"},
                )
            }
        ),
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=(context,),
        )

    assert captured.value.code is (ChangeLifecycleErrorCode.EVIDENCE_CONTEXT_INVALID)
    assert captured.value.location == "$.evidence_contexts[0]"


def test_implementation_derivation_accepts_capability_mapping() -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)

    record = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
        evidence_contexts=(
            replace(
                context,
                negotiated_capabilities=MappingProxyType(
                    dict(context.negotiated_capabilities)
                ),
            ),
        ),
    )

    assert record.bindings[0].result == context.result


def test_implementation_derivation_rejects_cyclic_nested_input() -> None:
    proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        proposal,
        base_behavior=_FIXTURE_BASE_BEHAVIOR,
        final_behavior=_FIXTURE_FINAL_BEHAVIOR,
    )
    context = evidence_context(delta)
    cyclic: list[object] = []
    cyclic.append(cyclic)
    context = replace(
        context,
        result=context.result.model_copy(update={"request": cyclic}),
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_implementation_record(
            graph,
            delta,
            proposal,
            base_behavior=_FIXTURE_BASE_BEHAVIOR,
            final_behavior=_FIXTURE_FINAL_BEHAVIOR,
            evidence_contexts=(context,),
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location.startswith("$.evidence_contexts[0].result.request")
