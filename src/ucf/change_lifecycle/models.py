from __future__ import annotations

import base64
import binascii
import hashlib
import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from ucf.adapter_protocol import CapabilitySelection
from ucf.change_lifecycle.openspec_profile import (
    validate_spec_driven_profile,
)
from ucf.implementation_evidence import ExecutionVerificationResult
from ucf.ir.codec import MAX_SAFE_INTEGER
from ucf.ir.models import (
    BehaviorIR,
    Digest,
    EntityKind,
    Identifier,
    IRModel,
    Producer,
)
from ucf.ir.trust_models import BehaviorDocumentRef, BehaviorEntityRef

CHANGE_LIFECYCLE_VERSION = "1.0.0"
CHANGE_PROPOSAL_SCHEMA_URI = "urn:ucf:change-lifecycle:proposal:1.0.0"
BEHAVIOR_DELTA_SCHEMA_URI = "urn:ucf:change-lifecycle:behavior-delta:1.0.0"
TASK_GRAPH_SCHEMA_URI = "urn:ucf:change-lifecycle:task-graph:1.0.0"
IMPLEMENTATION_RECORD_SCHEMA_URI = (
    "urn:ucf:change-lifecycle:implementation-record:1.0.0"
)
VERIFICATION_RECORD_SCHEMA_URI = "urn:ucf:change-lifecycle:verification-record:1.0.0"
ARCHIVE_RECORD_SCHEMA_URI = "urn:ucf:change-lifecycle:archive-record:1.0.0"
OPENSPEC_INTEROP_PROFILE = "fission-ai.openspec/spec-driven@1"
OPENSPEC_TESTED_AGAINST_VERSION = "1.6.0"
EVIDENCE_CONTEXT_VALIDATION_PROCEDURE_URI = (
    "urn:ucf:change-lifecycle:evidence-context-validation:1.0.0"
)

MAX_OPENSPEC_ARTIFACTS = 256
MAX_OPENSPEC_ARTIFACT_BYTES = 262_144
MAX_CHANGE_TASKS = 1024
MAX_OPENSPEC_ARTIFACT_BASE64 = ((MAX_OPENSPEC_ARTIFACT_BYTES + 2) // 3) * 4

type OpenSpecChangeId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    ),
]
type RelativeArtifactPath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=1024),
]
type Base64ArtifactContent = Annotated[
    str,
    StringConstraints(max_length=MAX_OPENSPEC_ARTIFACT_BASE64),
]


class OpenSpecArtifactRole(StrEnum):
    PROJECT_CONFIG = "project_config"
    CHANGE_METADATA = "change_metadata"
    PROPOSAL = "proposal"
    DESIGN = "design"
    TASKS = "tasks"
    DELTA_SPEC = "delta_spec"
    BASE_SPEC = "base_spec"
    OPAQUE = "opaque"


class OpenSpecArtifact(IRModel):
    kind: Literal["openspec_artifact"]
    path: RelativeArtifactPath
    role: OpenSpecArtifactRole
    media_type: Literal[
        "application/octet-stream",
        "application/yaml;charset=utf-8",
        "text/markdown;charset=utf-8",
        "text/plain;charset=utf-8",
    ]
    content_base64: Base64ArtifactContent
    byte_digest: Digest

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        _validate_relative_path(value)
        return value

    @model_validator(mode="after")
    def validate_content(self) -> OpenSpecArtifact:
        try:
            content = base64.b64decode(
                self.content_base64.encode("ascii"),
                validate=True,
            )
        except (UnicodeEncodeError, binascii.Error) as error:
            raise ValueError(
                "artifact content is not canonical RFC 4648 base64"
            ) from error
        if base64.b64encode(content).decode("ascii") != self.content_base64:
            raise ValueError("artifact content is not in canonical base64 form")
        if len(content) > MAX_OPENSPEC_ARTIFACT_BYTES:
            raise ValueError("artifact content exceeds the byte limit")
        if self.media_type != "application/octet-stream":
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError("artifact content is not valid UTF-8") from error
        actual = hashlib.sha256(content).hexdigest()
        if self.byte_digest.value != actual:
            raise ValueError("artifact byte digest does not match its content")
        return self


class OpenSpecManifest(IRModel):
    kind: Literal["openspec_manifest"]
    profile: Literal[OPENSPEC_INTEROP_PROFILE]
    tested_against_version: Literal[OPENSPEC_TESTED_AGAINST_VERSION]
    change_path: RelativeArtifactPath
    artifacts: Annotated[
        tuple[OpenSpecArtifact, ...],
        Field(min_length=1, max_length=MAX_OPENSPEC_ARTIFACTS),
    ]

    @field_validator("change_path")
    @classmethod
    def validate_change_path(cls, value: str) -> str:
        _validate_relative_path(value)
        return value

    @model_validator(mode="after")
    def validate_artifact_manifest(self) -> OpenSpecManifest:
        paths = tuple(artifact.path for artifact in self.artifacts)
        if len(paths) != len(set(paths)):
            raise ValueError("OpenSpec manifest contains duplicate paths")
        path_set = set(paths)
        if any(
            parent.as_posix() in path_set
            for path in paths
            for parent in PurePosixPath(path).parents
        ):
            raise ValueError(
                "OpenSpec manifest contains a file/directory path collision"
            )
        if paths != tuple(sorted(paths)):
            raise ValueError(
                "OpenSpec manifest artifacts are not in canonical path order"
            )
        return self


class ChangeProposal(IRModel):
    kind: Literal["change_proposal"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[CHANGE_PROPOSAL_SCHEMA_URI]
    change_id: OpenSpecChangeId
    base_behavior: BehaviorDocumentRef
    openspec: OpenSpecManifest

    @model_validator(mode="after")
    def validate_openspec_identity(self) -> ChangeProposal:
        expected_path = f"changes/{self.change_id}"
        if self.openspec.change_path != expected_path:
            raise ValueError("OpenSpec change path does not match the stable change ID")
        proposal_path = f"{expected_path}/proposal.md"
        matching = tuple(
            artifact
            for artifact in self.openspec.artifacts
            if artifact.role is OpenSpecArtifactRole.PROPOSAL
        )
        if len(matching) != 1 or matching[0].path != proposal_path:
            raise ValueError(
                "OpenSpec manifest must contain exactly the change proposal"
            )
        for artifact in self.openspec.artifacts:
            expected_role, expected_media_type = _artifact_metadata(
                artifact.path,
                change_path=expected_path,
            )
            if (
                artifact.path != "config.yaml"
                and expected_role is not OpenSpecArtifactRole.BASE_SPEC
                and not artifact.path.startswith(f"{expected_path}/")
            ):
                raise ValueError(
                    "OpenSpec artifact is outside the bounded profile paths"
                )
            if (
                artifact.role is not expected_role
                or artifact.media_type != expected_media_type
            ):
                raise ValueError(
                    "OpenSpec artifact role, path, and media type do not "
                    f"match the closed profile: {artifact.path!r}"
                )
        validate_spec_driven_profile(
            (
                (artifact.path, artifact.content_base64)
                for artifact in self.openspec.artifacts
            ),
            change_path=expected_path,
        )
        return self


class ChangeProposalRef(IRModel):
    kind: Literal["change_proposal_ref"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[CHANGE_PROPOSAL_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class BehaviorChangeAspect(StrEnum):
    DEFINITION = "definition"
    ROOT_MEMBERSHIP = "root_membership"


class AddedBehavior(IRModel):
    kind: Literal["added_behavior"]
    final_subject: BehaviorEntityRef
    final_is_root: bool


class ModifiedBehavior(IRModel):
    kind: Literal["modified_behavior"]
    base_subject: BehaviorEntityRef
    final_subject: BehaviorEntityRef
    aspects: Annotated[
        tuple[Literal["definition", "root_membership"], ...],
        Field(min_length=1, max_length=2),
    ]
    base_is_root: bool
    final_is_root: bool

    @model_validator(mode="after")
    def validate_subject_pair(self) -> ModifiedBehavior:
        if (
            self.base_subject.target_kind is not self.final_subject.target_kind
            or self.base_subject.target_id != self.final_subject.target_id
        ):
            raise ValueError("modified behavior must retain its subject kind and ID")
        canonical = tuple(
            aspect.value
            for aspect in (
                BehaviorChangeAspect.DEFINITION,
                BehaviorChangeAspect.ROOT_MEMBERSHIP,
            )
            if aspect.value in self.aspects
        )
        if self.aspects != canonical:
            raise ValueError("modified behavior aspects are not in canonical order")
        definition_changed = BehaviorChangeAspect.DEFINITION.value in self.aspects
        root_changed = BehaviorChangeAspect.ROOT_MEMBERSHIP.value in self.aspects
        if not definition_changed and not root_changed:
            raise ValueError("modified behavior must name a changed aspect")
        if root_changed != (self.base_is_root != self.final_is_root):
            raise ValueError("root membership aspect does not match the root flags")
        return self


class RemovedBehavior(IRModel):
    kind: Literal["removed_behavior"]
    base_subject: BehaviorEntityRef
    base_is_root: bool


type BehaviorDeltaEntry = Annotated[
    AddedBehavior | ModifiedBehavior | RemovedBehavior,
    Field(discriminator="kind"),
]


class BehaviorDelta(IRModel):
    kind: Literal["behavior_delta"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[BEHAVIOR_DELTA_SCHEMA_URI]
    change_id: OpenSpecChangeId
    proposal: ChangeProposalRef
    base_behavior: BehaviorDocumentRef
    final_behavior: BehaviorDocumentRef
    entries: Annotated[
        tuple[BehaviorDeltaEntry, ...],
        Field(min_length=1),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> BehaviorDelta:
        if self.proposal.change_id != self.change_id:
            raise ValueError("delta change ID differs from its proposal")
        if (
            self.base_behavior.document_id != self.final_behavior.document_id
            or self.base_behavior.ir_version != self.final_behavior.ir_version
        ):
            raise ValueError(
                "behavior delta must retain document identity and IR version"
            )
        if self.base_behavior.canonical_digest == self.final_behavior.canonical_digest:
            raise ValueError(
                "behavior delta base and final behavior digests must differ"
            )
        for index, entry in enumerate(self.entries):
            for field, subject, document in _delta_entry_document_subjects(
                entry,
                base=self.base_behavior,
                final=self.final_behavior,
            ):
                if not _subject_binds_document(subject, document):
                    raise ValueError(
                        f"behavior delta entry {index} {field} "
                        "does not bind its top-level behavior document"
                    )
        keys = tuple(_delta_entry_key(entry) for entry in self.entries)
        identities = tuple(key[1:] for key in keys)
        if len(identities) != len(set(identities)):
            raise ValueError("behavior delta contains duplicate subjects")
        if keys != tuple(sorted(keys)):
            raise ValueError("behavior delta entries are not in canonical order")
        return self


class BehaviorDeltaRef(IRModel):
    kind: Literal["behavior_delta_ref"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[BEHAVIOR_DELTA_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class DeltaSubjectRef(IRModel):
    kind: Literal["delta_subject_ref"]
    operation: Literal["added", "modified", "removed"]
    target_kind: EntityKind
    target_id: Identifier


class TaskRef(IRModel):
    kind: Literal["task_ref"]
    target_id: Identifier


class TaskSource(IRModel):
    kind: Literal["task_source"]
    artifact_path: RelativeArtifactPath
    artifact_digest: Digest
    line: Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]

    @field_validator("artifact_path")
    @classmethod
    def validate_artifact_path(cls, value: str) -> str:
        _validate_relative_path(value)
        return value


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class ChangeTask(IRModel):
    kind: Literal["change_task"]
    id: Identifier
    order: Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]
    depends_on: tuple[TaskRef, ...]
    subjects: Annotated[
        tuple[DeltaSubjectRef, ...],
        Field(min_length=1),
    ]
    status: TaskStatus
    source: TaskSource


class TaskGraph(IRModel):
    kind: Literal["task_graph"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[TASK_GRAPH_SCHEMA_URI]
    change_id: OpenSpecChangeId
    delta: BehaviorDeltaRef
    tasks: Annotated[
        tuple[ChangeTask, ...],
        Field(min_length=1, max_length=MAX_CHANGE_TASKS),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> TaskGraph:
        if self.delta.change_id != self.change_id:
            raise ValueError("task graph change ID differs from its delta")
        identities = tuple(task.id for task in self.tasks)
        if len(identities) != len(set(identities)):
            raise ValueError("task graph contains duplicate task IDs")
        orders = tuple(task.order for task in self.tasks)
        if orders != tuple(range(1, len(self.tasks) + 1)):
            raise ValueError("task graph order is not canonical and contiguous")
        return self


class TaskGraphRef(IRModel):
    kind: Literal["task_graph_ref"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[TASK_GRAPH_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class EvidenceContextValidationReceipt(IRModel):
    kind: Literal["evidence_context_validation_receipt"]
    assurance: Literal["context_validated_import"]
    procedure_uri: Literal[EVIDENCE_CONTEXT_VALIDATION_PROCEDURE_URI]
    result_digest: Digest
    mapping_result_digest: Digest
    onboarding_bundle_digest: Digest
    current_inventory_digest: Digest
    mapping_initialized_adapter: Producer
    verification_initialized_adapter: Producer
    negotiated_capabilities: Annotated[
        tuple[CapabilitySelection, ...],
        Field(min_length=2, max_length=256),
    ]

    @model_validator(mode="after")
    def validate_capabilities(self) -> EvidenceContextValidationReceipt:
        identities = tuple(
            capability.name for capability in self.negotiated_capabilities
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "context validation receipt contains duplicate capabilities"
            )
        if identities != tuple(sorted(identities)):
            raise ValueError(
                "context validation receipt capabilities are not canonical"
            )
        return self


class ImplementationEvidenceBinding(IRModel):
    kind: Literal["implementation_evidence_binding"]
    subject: DeltaSubjectRef
    result: ExecutionVerificationResult
    validation: EvidenceContextValidationReceipt

    @model_validator(mode="after")
    def validate_receipt(self) -> ImplementationEvidenceBinding:
        encoded = (
            json.dumps(
                self.result.model_dump(mode="json"),
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if self.validation.result_digest.value != hashlib.sha256(encoded).hexdigest():
            raise ValueError(
                "context validation receipt does not bind its evidence result"
            )
        return self


class ImplementationRecord(IRModel):
    kind: Literal["implementation_record"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[IMPLEMENTATION_RECORD_SCHEMA_URI]
    change_id: OpenSpecChangeId
    tasks: TaskGraphRef
    bindings: Annotated[
        tuple[ImplementationEvidenceBinding, ...],
        Field(min_length=1, max_length=256),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> ImplementationRecord:
        if self.tasks.change_id != self.change_id:
            raise ValueError("implementation record change ID differs from its tasks")
        keys = tuple(
            _delta_subject_ref_key(binding.subject) for binding in self.bindings
        )
        if len(keys) != len(set(keys)):
            raise ValueError("implementation record contains duplicate delta subjects")
        if keys != tuple(sorted(keys)):
            raise ValueError("implementation bindings are not in canonical order")
        return self


class ImplementationRecordRef(IRModel):
    kind: Literal["implementation_record_ref"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[IMPLEMENTATION_RECORD_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class VerificationRecord(IRModel):
    kind: Literal["verification_record"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[VERIFICATION_RECORD_SCHEMA_URI]
    change_id: OpenSpecChangeId
    implementation: ImplementationRecordRef
    outcome: Literal["accepted"]
    subjects: Annotated[
        tuple[DeltaSubjectRef, ...],
        Field(min_length=1, max_length=256),
    ]

    @model_validator(mode="after")
    def validate_shape(self) -> VerificationRecord:
        if self.implementation.change_id != self.change_id:
            raise ValueError(
                "verification record change ID differs from implementation"
            )
        keys = tuple(_delta_subject_ref_key(subject) for subject in self.subjects)
        if len(keys) != len(set(keys)):
            raise ValueError("verification record contains duplicate subjects")
        if keys != tuple(sorted(keys)):
            raise ValueError("verification subjects are not in canonical order")
        return self


class VerificationRecordRef(IRModel):
    kind: Literal["verification_record_ref"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[VERIFICATION_RECORD_SCHEMA_URI]
    change_id: OpenSpecChangeId
    canonical_digest: Digest


class ArchiveRecord(IRModel):
    kind: Literal["archive_record"]
    change_lifecycle_version: Literal[CHANGE_LIFECYCLE_VERSION]
    schema_uri: Literal[ARCHIVE_RECORD_SCHEMA_URI]
    change_id: OpenSpecChangeId
    status: Literal["archived"]
    proposal: ChangeProposalRef
    delta: BehaviorDeltaRef
    tasks: TaskGraphRef
    implementation: ImplementationRecordRef
    verification: VerificationRecordRef
    final_behavior: BehaviorIR

    @model_validator(mode="after")
    def validate_shape(self) -> ArchiveRecord:
        references = (
            self.proposal,
            self.delta,
            self.tasks,
            self.implementation,
            self.verification,
        )
        if any(reference.change_id != self.change_id for reference in references):
            raise ValueError("archive predecessor change IDs are not identical")
        return self


def _validate_relative_path(value: str) -> None:
    if "\x00" in value or "\\" in value or value.startswith("/"):
        raise ValueError("artifact path must be a relative POSIX path")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("artifact path contains an unsafe segment")


def _artifact_metadata(
    path: str,
    *,
    change_path: str,
) -> tuple[OpenSpecArtifactRole, str]:
    artifact_path = PurePosixPath(path)
    change = PurePosixPath(change_path)
    role = OpenSpecArtifactRole.OPAQUE
    if artifact_path == PurePosixPath("config.yaml"):
        role = OpenSpecArtifactRole.PROJECT_CONFIG
    elif artifact_path == change / ".openspec.yaml":
        role = OpenSpecArtifactRole.CHANGE_METADATA
    elif artifact_path == change / "proposal.md":
        role = OpenSpecArtifactRole.PROPOSAL
    elif artifact_path == change / "design.md":
        role = OpenSpecArtifactRole.DESIGN
    elif artifact_path == change / "tasks.md":
        role = OpenSpecArtifactRole.TASKS
    elif (
        len(artifact_path.parts) == len(change.parts) + 3
        and artifact_path.parts[: len(change.parts)] == change.parts
        and artifact_path.parts[-3] == "specs"
        and artifact_path.parts[-1] == "spec.md"
    ):
        role = OpenSpecArtifactRole.DELTA_SPEC
    elif (
        len(artifact_path.parts) == 3
        and artifact_path.parts[0] == "specs"
        and artifact_path.parts[-1] == "spec.md"
    ):
        role = OpenSpecArtifactRole.BASE_SPEC
    return role, _artifact_media_type(artifact_path)


def _artifact_media_type(path: PurePosixPath) -> str:
    if path.suffix in {".yaml", ".yml"}:
        return "application/yaml;charset=utf-8"
    if path.suffix == ".md":
        return "text/markdown;charset=utf-8"
    if path.suffix == ".txt":
        return "text/plain;charset=utf-8"
    return "application/octet-stream"


def _delta_entry_key(
    entry: BehaviorDeltaEntry,
) -> tuple[str, str, str]:
    if isinstance(entry, AddedBehavior):
        subject = entry.final_subject
    else:
        subject = entry.base_subject
    return (entry.kind, subject.target_kind.value, subject.target_id)


def _subject_binds_document(
    subject: BehaviorEntityRef,
    document: BehaviorDocumentRef,
) -> bool:
    return (
        subject.document_id == document.document_id
        and subject.ir_version == document.ir_version
        and subject.canonical_digest == document.canonical_digest
    )


def _delta_entry_document_subjects(
    entry: BehaviorDeltaEntry,
    *,
    base: BehaviorDocumentRef,
    final: BehaviorDocumentRef,
) -> tuple[tuple[str, BehaviorEntityRef, BehaviorDocumentRef], ...]:
    if isinstance(entry, AddedBehavior):
        return (("final_subject", entry.final_subject, final),)
    if isinstance(entry, RemovedBehavior):
        return (("base_subject", entry.base_subject, base),)
    return (
        ("base_subject", entry.base_subject, base),
        ("final_subject", entry.final_subject, final),
    )


def _delta_subject_ref_key(
    subject: DeltaSubjectRef,
) -> tuple[str, str, str]:
    return (
        subject.operation,
        subject.target_kind.value,
        subject.target_id,
    )
