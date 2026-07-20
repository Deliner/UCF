"""Build deterministic positive and negative change-lifecycle wire fixtures."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tests.implementation_evidence.test_mapping_result_contract import (
    _mapping_result,
)
from tests.implementation_evidence.test_verification_result_contract import (
    _verification_result,
)
from tests.onboarding.test_bundle import _bundle
from ucf.change_lifecycle import (
    CHANGE_LIFECYCLE_VERSION,
    CHANGE_PROPOSAL_SCHEMA_URI,
    OPENSPEC_INTEROP_PROFILE,
    OPENSPEC_TESTED_AGAINST_VERSION,
    TASK_GRAPH_SCHEMA_URI,
    ArchiveRecord,
    BehaviorDelta,
    ChangeProposal,
    ChangeTask,
    ExecutionEvidenceContext,
    ImplementationRecord,
    OpenSpecArtifact,
    OpenSpecArtifactRole,
    OpenSpecManifest,
    TaskGraph,
    TaskRef,
    TaskSource,
    TaskStatus,
    VerificationRecord,
    behavior_delta_ref,
    canonical_change_lifecycle_json,
    complete_change_task,
    delta_subject_ref,
    derive_archive_record,
    derive_behavior_delta,
    derive_implementation_record,
    derive_verification_record,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ExecutionVerificationResult,
    canonical_implementation_evidence_json,
)
from ucf.inventory import canonical_inventory_json
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import BehaviorIR, Digest
from ucf.ir.trust_models import BehaviorDocumentRef
from ucf.onboarding import canonical_onboarding_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIRECTORY = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "change_lifecycle" / "v1"
)


@dataclass(frozen=True)
class LifecycleFixtureChain:
    base: BehaviorIR
    final: BehaviorIR
    proposal: ChangeProposal
    delta: BehaviorDelta
    graph: TaskGraph
    implementation: ImplementationRecord
    verification: VerificationRecord
    archive: ArchiveRecord
    evidence_contexts: tuple[ExecutionEvidenceContext, ...]


def digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def behavior_ref(document: BehaviorIR) -> BehaviorDocumentRef:
    return BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=digest(canonical_ir_json(document).encode("utf-8")),
    )


def behavior_pair() -> tuple[BehaviorIR, BehaviorIR]:
    final = _bundle().behavior
    base_payload = json.loads(canonical_ir_json(final))
    use_case = next(
        entity
        for entity in base_payload["entities"]
        if entity["kind"] == "use_case" and entity["id"] == "use-case.quote-order"
    )
    use_case["output_ports"][0]["required"] = False
    return parse_ir_json(json.dumps(base_payload)), final


def openspec_artifact(
    path: str,
    role: OpenSpecArtifactRole,
    content: bytes,
    *,
    media_type: str = "text/markdown;charset=utf-8",
) -> OpenSpecArtifact:
    return OpenSpecArtifact(
        kind="openspec_artifact",
        path=path,
        role=role,
        media_type=media_type,
        content_base64=base64.b64encode(content).decode("ascii"),
        byte_digest=digest(content),
    )


def proposal(base: BehaviorIR) -> ChangeProposal:
    change_id = "require-quote-order-total"
    return ChangeProposal(
        kind="change_proposal",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=CHANGE_PROPOSAL_SCHEMA_URI,
        change_id=change_id,
        base_behavior=behavior_ref(base),
        openspec=OpenSpecManifest(
            kind="openspec_manifest",
            profile=OPENSPEC_INTEROP_PROFILE,
            tested_against_version=OPENSPEC_TESTED_AGAINST_VERSION,
            change_path=f"changes/{change_id}",
            artifacts=(
                openspec_artifact(
                    f"changes/{change_id}/.openspec.yaml",
                    OpenSpecArtifactRole.CHANGE_METADATA,
                    b"schema: spec-driven\n",
                    media_type="application/yaml;charset=utf-8",
                ),
                openspec_artifact(
                    f"changes/{change_id}/proposal.md",
                    OpenSpecArtifactRole.PROPOSAL,
                    b"## Why\n\nQuote totals must always be returned.\n",
                ),
                openspec_artifact(
                    f"changes/{change_id}/tasks.md",
                    OpenSpecArtifactRole.TASKS,
                    (
                        b"## 1. Contract\n\n"
                        b"- [ ] 1.1 Review the behavior delta\n"
                        b"- [ ] 1.2 Implement the change\n"
                        b"- [ ] 1.3 Run verification\n"
                    ),
                ),
            ),
        ),
    )


def task_graph() -> tuple[ChangeProposal, BehaviorDelta, TaskGraph]:
    base, final = behavior_pair()
    change_proposal = proposal(base)
    delta = derive_behavior_delta(change_proposal, base, final)
    subject = delta_subject_ref(delta.entries[0])
    task_path = f"changes/{change_proposal.change_id}/tasks.md"
    task_digest = next(
        artifact.byte_digest
        for artifact in change_proposal.openspec.artifacts
        if artifact.path == task_path
    )
    tasks = tuple(
        ChangeTask(
            kind="change_task",
            id=f"task.1-{order}",
            order=order,
            depends_on=(
                ()
                if order == 1
                else (
                    TaskRef(
                        kind="task_ref",
                        target_id=f"task.1-{order - 1}",
                    ),
                )
            ),
            subjects=(subject,),
            status=TaskStatus.PENDING,
            source=TaskSource(
                kind="task_source",
                artifact_path=task_path,
                artifact_digest=task_digest,
                line=order + 2,
            ),
        )
        for order in range(1, 4)
    )
    graph = TaskGraph(
        kind="task_graph",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=TASK_GRAPH_SCHEMA_URI,
        change_id=change_proposal.change_id,
        delta=behavior_delta_ref(delta),
        tasks=tasks,
    )
    return change_proposal, delta, graph


def verification_result(
    delta: BehaviorDelta,
    outcome: Literal["passed", "failed", "error"] = "passed",
) -> ExecutionVerificationResult:
    result = _verification_result(outcome)
    expected_subject = delta.entries[0].final_subject
    if (
        result.request.subject != expected_subject
        or result.request.base_behavior != delta.final_behavior
    ):
        raise AssertionError(
            "upstream execution fixture differs from lifecycle delta target"
        )
    return result


def evidence_context(
    delta: BehaviorDelta,
    outcome: Literal["passed", "failed", "error"] = "passed",
) -> ExecutionEvidenceContext:
    bundle = _bundle()
    mapping = _mapping_result()
    result = verification_result(delta, outcome)
    return ExecutionEvidenceContext(
        result=result,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=bundle.inventory,
        mapping_initialized_adapter=mapping.producer,
        initialized_adapter=result.producer,
        negotiated_capabilities={
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
        },
    )


def completed_graph(
    graph: TaskGraph,
    delta: BehaviorDelta,
    proposal: ChangeProposal,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> TaskGraph:
    for task in graph.tasks:
        graph = complete_change_task(
            graph,
            task.id,
            delta=delta,
            proposal=proposal,
            base_behavior=base_behavior,
            final_behavior=final_behavior,
        )
    return graph


def lifecycle_chain() -> LifecycleFixtureChain:
    base, final = behavior_pair()
    change_proposal, delta, graph = task_graph()
    graph = completed_graph(
        graph,
        delta,
        change_proposal,
        base_behavior=base,
        final_behavior=final,
    )
    contexts = (evidence_context(delta),)
    implementation = derive_implementation_record(
        graph,
        delta,
        change_proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    verification = derive_verification_record(
        implementation,
        graph,
        delta,
        change_proposal,
        base_behavior=base,
        final_behavior=final,
        evidence_contexts=contexts,
    )
    archive = derive_archive_record(
        change_proposal,
        delta,
        graph,
        implementation,
        verification,
        base,
        final,
        evidence_contexts=contexts,
    )
    return LifecycleFixtureChain(
        base=base,
        final=final,
        proposal=change_proposal,
        delta=delta,
        graph=graph,
        implementation=implementation,
        verification=verification,
        archive=archive,
        evidence_contexts=contexts,
    )


def _json_payload(value: object) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _mutated_payload(document: object, mutate: object) -> str:
    payload = document.model_dump(mode="json")  # type: ignore[union-attr]
    mutate(payload)  # type: ignore[operator]
    return _json_payload(payload)


def render_wire_fixtures() -> dict[Path, str]:
    chain = lifecycle_chain()
    context = chain.evidence_contexts[0]
    positive = {
        "positive/proposal.json": chain.proposal,
        "positive/behavior-delta.json": chain.delta,
        "positive/task-graph.json": chain.graph,
        "positive/implementation-record.json": chain.implementation,
        "positive/verification-record.json": chain.verification,
        "positive/archive-record.json": chain.archive,
    }
    rendered = {
        DEFAULT_FIXTURE_DIRECTORY / relative_path: (
            canonical_change_lifecycle_json(document).decode("utf-8")
        )
        for relative_path, document in positive.items()
    }
    rendered.update(
        {
            DEFAULT_FIXTURE_DIRECTORY / "context/base-behavior.json": (
                canonical_ir_json(chain.base)
            ),
            DEFAULT_FIXTURE_DIRECTORY / "context/final-behavior.json": (
                canonical_ir_json(chain.final)
            ),
            DEFAULT_FIXTURE_DIRECTORY / "context/execution-result.json": (
                canonical_implementation_evidence_json(context.result).decode("utf-8")
            ),
            DEFAULT_FIXTURE_DIRECTORY / "context/mapping-result.json": (
                canonical_implementation_evidence_json(context.mapping_result).decode(
                    "utf-8"
                )
            ),
            DEFAULT_FIXTURE_DIRECTORY / "context/onboarding-bundle.json": (
                canonical_onboarding_json(context.bundle).decode("utf-8")
            ),
            DEFAULT_FIXTURE_DIRECTORY / "context/current-inventory.json": (
                canonical_inventory_json(context.current_inventory).decode("utf-8")
            ),
        }
    )

    proposal_payload = chain.proposal.model_dump(mode="json")
    unknown = deepcopy(proposal_payload)
    unknown["verified"] = True
    unknown_nested = deepcopy(proposal_payload)
    unknown_nested["openspec"]["artifacts"][0]["executable"] = True
    unsupported_version = deepcopy(proposal_payload)
    unsupported_version["change_lifecycle_version"] = "2.0.0"
    unsupported_profile = deepcopy(proposal_payload)
    unsupported_profile["openspec"]["profile"] = "custom/profile@1"
    invalid_utf8 = deepcopy(proposal_payload)
    invalid_bytes = b"\xff"
    invalid_utf8["openspec"]["artifacts"][0]["content_base64"] = base64.b64encode(
        invalid_bytes
    ).decode("ascii")
    invalid_utf8["openspec"]["artifacts"][0]["byte_digest"]["value"] = hashlib.sha256(
        invalid_bytes
    ).hexdigest()
    noncanonical_base64 = deepcopy(proposal_payload)
    noncanonical_base64["openspec"]["artifacts"][0]["content_base64"] = "*"
    mismatched_artifact_digest = deepcopy(proposal_payload)
    mismatched_artifact_digest["openspec"]["artifacts"][0]["byte_digest"]["value"] = (
        "0" * 64
    )
    unsafe_artifact_path = deepcopy(proposal_payload)
    unsafe_artifact_path["openspec"]["artifacts"][0]["path"] = (
        f"changes/{chain.proposal.change_id}/../.openspec.yaml"
    )
    unsafe_artifact_path["openspec"]["artifacts"].sort(
        key=lambda artifact: artifact["path"]
    )
    role_path_mismatch = deepcopy(proposal_payload)
    mismatched_task = next(
        artifact
        for artifact in role_path_mismatch["openspec"]["artifacts"]
        if artifact["role"] == "tasks"
    )
    mismatched_task["path"] = f"changes/{chain.proposal.change_id}/notes.txt"
    mismatched_task["media_type"] = "text/plain;charset=utf-8"
    role_path_mismatch["openspec"]["artifacts"].sort(
        key=lambda artifact: artifact["path"]
    )
    binary_tasks = deepcopy(proposal_payload)
    binary_task = next(
        artifact
        for artifact in binary_tasks["openspec"]["artifacts"]
        if artifact["role"] == "tasks"
    )
    binary_content = b"\xffbinary-task"
    binary_task["media_type"] = "application/octet-stream"
    binary_task["content_base64"] = base64.b64encode(binary_content).decode("ascii")
    binary_task["byte_digest"]["value"] = hashlib.sha256(binary_content).hexdigest()
    noncanonical_delta_spec = deepcopy(proposal_payload)
    nested_delta_artifact = deepcopy(
        next(
            artifact
            for artifact in noncanonical_delta_spec["openspec"]["artifacts"]
            if artifact["role"] == "proposal"
        )
    )
    nested_delta_artifact.update(
        {
            "path": (
                f"changes/{chain.proposal.change_id}/specs/nested/quote-order/spec.md"
            ),
            "role": "opaque",
        }
    )
    noncanonical_delta_spec["openspec"]["artifacts"].append(nested_delta_artifact)
    noncanonical_delta_spec["openspec"]["artifacts"].sort(
        key=lambda artifact: artifact["path"]
    )
    orphan_base_spec = deepcopy(proposal_payload)
    orphan_artifact = deepcopy(
        next(
            artifact
            for artifact in orphan_base_spec["openspec"]["artifacts"]
            if artifact["role"] == "proposal"
        )
    )
    orphan_artifact.update(
        {
            "path": "specs/orphan/spec.md",
            "role": "base_spec",
        }
    )
    orphan_base_spec["openspec"]["artifacts"].append(orphan_artifact)
    orphan_base_spec["openspec"]["artifacts"].sort(
        key=lambda artifact: artifact["path"]
    )
    unsupported_profile_metadata = deepcopy(proposal_payload)
    profile_artifact = next(
        artifact
        for artifact in unsupported_profile_metadata["openspec"]["artifacts"]
        if artifact["role"] == "change_metadata"
    )
    unsupported_profile_content = b"schema: custom-workflow\n"
    profile_artifact["content_base64"] = base64.b64encode(
        unsupported_profile_content
    ).decode("ascii")
    profile_artifact["byte_digest"]["value"] = hashlib.sha256(
        unsupported_profile_content
    ).hexdigest()
    missing_profile_declaration = deepcopy(proposal_payload)
    missing_profile_declaration["openspec"]["artifacts"] = [
        artifact
        for artifact in missing_profile_declaration["openspec"]["artifacts"]
        if artifact["role"] not in {"change_metadata", "project_config"}
    ]
    excessive_profile_nesting = deepcopy(proposal_payload)
    deeply_nested_profile = next(
        artifact
        for artifact in excessive_profile_nesting["openspec"]["artifacts"]
        if artifact["role"] == "change_metadata"
    )
    deeply_nested_profile_content = (
        b"schema: spec-driven\nnested: "
        + (b"[" * 600)
        + b"value"
        + (b"]" * 600)
        + b"\n"
    )
    deeply_nested_profile["content_base64"] = base64.b64encode(
        deeply_nested_profile_content
    ).decode("ascii")
    deeply_nested_profile["byte_digest"]["value"] = hashlib.sha256(
        deeply_nested_profile_content
    ).hexdigest()
    file_directory_prefix_collision = deepcopy(proposal_payload)
    collision_source = next(
        artifact
        for artifact in file_directory_prefix_collision["openspec"]["artifacts"]
        if artifact["role"] == "proposal"
    )
    collision_artifacts = []
    for path in (
        f"changes/{chain.proposal.change_id}/opaque",
        f"changes/{chain.proposal.change_id}/opaque/child.bin",
    ):
        artifact = deepcopy(collision_source)
        artifact.update(
            {
                "path": path,
                "role": "opaque",
                "media_type": "application/octet-stream",
            }
        )
        collision_artifacts.append(artifact)
    file_directory_prefix_collision["openspec"]["artifacts"].extend(collision_artifacts)
    file_directory_prefix_collision["openspec"]["artifacts"].sort(
        key=lambda artifact: artifact["path"]
    )

    stale_delta = chain.delta.model_dump(mode="json")
    stale_delta["proposal"]["canonical_digest"]["value"] = "f" * 64

    cyclic_graph = chain.graph.model_dump(mode="json")
    cyclic_graph["tasks"][0]["depends_on"] = [
        {"kind": "task_ref", "target_id": "task.1-3"}
    ]

    nonpassing_contexts = (evidence_context(chain.delta, "failed"),)
    nonpassing = derive_implementation_record(
        chain.graph,
        chain.delta,
        chain.proposal,
        base_behavior=chain.base,
        final_behavior=chain.final,
        evidence_contexts=nonpassing_contexts,
    )
    unsupported_capability = chain.implementation.model_dump(mode="json")
    unsupported_capability["bindings"][0]["result"]["capability"]["name"] = (
        "org.example.unsupported"
    )
    unsupported_capability["bindings"][0]["result"]["request"]["capability"]["name"] = (
        "org.example.unsupported"
    )
    stale_validation_receipt = chain.implementation.model_dump(mode="json")
    stale_validation_receipt["bindings"][0]["validation"]["result_digest"]["value"] = (
        "0" * 64
    )

    stale_verification = chain.verification.model_dump(mode="json")
    stale_verification["implementation"]["canonical_digest"]["value"] = "f" * 64

    missing_verification = chain.archive.model_dump(mode="json")
    missing_verification.pop("verification")
    stale_archive = chain.archive.model_dump(mode="json")
    stale_archive["verification"]["canonical_digest"]["value"] = "f" * 64

    proposal_json = canonical_change_lifecycle_json(chain.proposal).decode("utf-8")
    invalid = {
        "invalid/duplicate-json-member.json": (
            '{"kind":"duplicate",' + proposal_json[1:]
        ),
        "invalid/unknown-root-field.json": _json_payload(unknown),
        "invalid/unknown-nested-field.json": _json_payload(unknown_nested),
        "invalid/unsupported-version.json": _json_payload(unsupported_version),
        "invalid/unsupported-openspec-profile.json": _json_payload(unsupported_profile),
        "invalid/invalid-artifact-utf8.json": _json_payload(invalid_utf8),
        "invalid/noncanonical-artifact-base64.json": _json_payload(noncanonical_base64),
        "invalid/mismatched-artifact-digest.json": _json_payload(
            mismatched_artifact_digest
        ),
        "invalid/unsafe-artifact-path.json": _json_payload(unsafe_artifact_path),
        "invalid/artifact-role-path-mismatch.json": _json_payload(role_path_mismatch),
        "invalid/binary-tasks-media-mismatch.json": _json_payload(binary_tasks),
        "invalid/noncanonical-delta-spec-layout.json": _json_payload(
            noncanonical_delta_spec
        ),
        "invalid/orphan-base-spec.json": _json_payload(orphan_base_spec),
        "invalid/unsupported-profile-metadata.json": _json_payload(
            unsupported_profile_metadata
        ),
        "invalid/missing-profile-declaration.json": _json_payload(
            missing_profile_declaration
        ),
        "invalid/excessive-profile-nesting.json": _json_payload(
            excessive_profile_nesting
        ),
        "invalid/file-directory-prefix-collision.json": _json_payload(
            file_directory_prefix_collision
        ),
        "invalid/archive-missing-verification.json": _json_payload(
            missing_verification
        ),
        "invalid/stale-delta-proposal-reference.json": _json_payload(stale_delta),
        "invalid/cyclic-task-dependency.json": _json_payload(cyclic_graph),
        "invalid/nonpassing-implementation.json": (
            canonical_change_lifecycle_json(nonpassing).decode("utf-8")
        ),
        "invalid/unsupported-evidence-capability.json": _json_payload(
            unsupported_capability
        ),
        "invalid/stale-validation-receipt.json": _json_payload(
            stale_validation_receipt
        ),
        "invalid/stale-verification-reference.json": _json_payload(stale_verification),
        "invalid/stale-archive-reference.json": _json_payload(stale_archive),
    }
    rendered.update(
        {
            DEFAULT_FIXTURE_DIRECTORY / relative_path: content
            for relative_path, content in invalid.items()
        }
    )
    return rendered


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check change-lifecycle wire fixtures."
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = _parse_args(arguments)
    fixtures = render_wire_fixtures()
    if options.check:
        stale = [
            path
            for path, content in fixtures.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0
    for path, content in fixtures.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
