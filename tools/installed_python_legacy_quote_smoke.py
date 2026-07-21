#!/usr/bin/env python3
"""Exercise the installed UCF wheel against the frozen Python legacy fixture."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

import ucf
from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    CapabilitySelection,
    Method,
    ProcessTimeouts,
)
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
    ImplementationEvidenceValidationError,
    ImplementationMappingRequest,
    ImplementationMappingResultRef,
    ImplementationSource,
    OnboardingBundleBinding,
    canonical_implementation_evidence_digest,
    canonical_implementation_evidence_json,
    execution_verification_request_to_payload,
    execution_verification_result_from_payload,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    parse_execution_verification_request_json,
    parse_execution_verification_result_json,
    parse_implementation_mapping_result_json,
    project_execution_verification,
    validate_execution_verification_request,
    validate_execution_verification_result,
    validate_implementation_mapping_request,
    validate_implementation_mapping_result,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    IgnorePolicy,
    InventoryPageRequest,
    InventoryRequest,
    RepositoryEntryFact,
    canonical_inventory_json,
    collect_inventory_from_process,
    parse_inventory_snapshot_json,
)
from ucf.ir import (
    ClaimLevel,
    IRValidationError,
    canonical_ir_json,
    canonical_trust_ir_json,
    parse_ir_json,
    parse_trust_ir_json,
    validate_trust_against_behavior,
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
    VerificationEvidence,
)
from ucf.ir.trust_models import BehaviorDocumentRef, Claim, TrustMapping
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    DISCOVERY_CAPABILITY,
    DISCOVERY_REQUEST_SCHEMA_URI,
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateProposal,
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    DiscoveryRequest,
    EditedDecision,
    InventoryBinding,
    OnboardingValidationError,
    ProposalEntityKind,
    ProposalEntityRef,
    ProposalPortRef,
    ProposedAction,
    ProposedBinding,
    ProposedStep,
    ProposedUseCase,
    RejectedDecision,
    UncertainDecision,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    canonical_onboarding_json,
    derive_candidate_semantic_digest,
    derive_decision_id,
    discovery_request_to_payload,
    discovery_result_from_payload,
    parse_decision_set_json,
    parse_discovery_result_json,
    parse_onboarding_bundle_json,
    validate_discovery_exchange,
)

_EVIDENCE_VERSION = "1.0.0"
_SUBJECT_URI = "urn:ucf:repository:python-legacy-quote"
_QUOTE_ROOT = "use-case.quote-order"
_RENDER_ROOT = "use-case.render-receipt"
_EXPECTED_CANDIDATE_ROOTS = frozenset(
    {
        "use-case.format-receipt",
        "use-case.legacy-discount-hint",
        "use-case.normalize-coupon",
        _QUOTE_ROOT,
    }
)
_EXPECTED_SOURCE_MANIFEST = {
    "pyproject.toml": (
        77,
        "d975e9195b7a0eea39db3e3667db49132d91ac46230db21610d4c3a5f141052a",
    ),
    "src/legacy_quote/__init__.py": (
        28,
        "9f42c8a5b12732dd0541fdfdf94db5a5a4bad5035a0ef2cc2cbd5a3420e38f25",
    ),
    "src/legacy_quote/service.py": (
        800,
        "435cdbf737d167db2fc3b0c7a473bbf7b2971451b76627fed26b0f7420768d77",
    ),
    "tests/behavior_checks.py": (
        679,
        "45402e8f23021b3e3ac798f198eb38c1cc816b83435ccbe8c0e5e802c19aaebf",
    ),
}
_EXPECTED_SOURCE_DIRECTORIES = frozenset({".", "src", "src/legacy_quote", "tests"})
_MAPPING_ADAPTER_PROCEDURE_URI = "urn:ucf:adapter:python-reference-static-mapping:1.0.0"
_VERIFICATION_ADAPTER_PROCEDURE_URI = (
    "urn:ucf:adapter:python-reference-native-check-verification:1.0.0"
)
_ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:cpython-linux-native-check-process:1.0.0"
)
_CHECK_ID = "check.quote-order.native-python"
_CHECK_PROCEDURE_URI = "urn:ucf:fixture-check:quote-order-python-native-contract:1.0.0"
_EXECUTION_ARTIFACT_PATHS = (
    "src/legacy_quote/__init__.py",
    "src/legacy_quote/service.py",
    "tests/behavior_checks.py",
)
_MAX_FIXTURE_FILE_BYTES = 4 * 1024 * 1024
_MAX_FIXTURE_BYTES = 16 * 1024 * 1024
_MAX_INTERPRETER_BYTES = 64 * 1024 * 1024
_MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
_TIMEOUTS = ProcessTimeouts(
    initialize=2.0,
    operation=5.0,
    write=1.0,
    cancellation=0.2,
    shutdown=1.0,
    terminate=0.2,
    kill=0.5,
)


class SmokeFailure(RuntimeError):
    """A stable, path-free installed-smoke failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _Arguments:
    adapter: Path
    fixture: Path
    evidence_output: Path | None


@dataclass(frozen=True)
class _FileIdentity:
    size: int
    digest: str


@dataclass(frozen=True)
class _FixtureManifest:
    files: dict[str, _FileIdentity]
    directories: frozenset[str]


@dataclass(frozen=True)
class _CanonicalStructure:
    inventory: bytes
    discovery: bytes
    decisions: bytes
    bundle: bytes
    mapping: bytes
    verification_request: bytes


@dataclass(frozen=True)
class _WorkflowResult:
    canonical: _CanonicalStructure
    inventory: object
    discovery: object
    decisions: object
    bundle: object
    mapping: object
    verification_request: object
    verification_result: object | None
    successor_behavior: object | None
    tested_trust: object | None
    tested_claim_count: int
    verified_claim_count: int
    verification_evidence_count: int
    stderr_bytes: int


def _parse_arguments(argv: list[str]) -> _Arguments:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise an installed UCF wheel with the external Python "
            "adapter and frozen legacy quote fixture."
        )
    )
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--evidence-output", type=Path)
    namespace = parser.parse_args(argv)
    evidence_output = (
        None
        if namespace.evidence_output is None
        else _new_output_path(namespace.evidence_output)
    )
    return _Arguments(
        adapter=_external_file(namespace.adapter),
        fixture=_external_directory(namespace.fixture),
        evidence_output=evidence_output,
    )


def _new_output_path(path: Path) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("evidence_output_not_absolute")
    if os.path.lexists(path):
        raise SmokeFailure("evidence_output_exists")
    try:
        parent = path.parent.resolve(strict=True)
        metadata = parent.stat()
    except OSError as error:
        raise SmokeFailure("evidence_output_parent_unavailable") from error
    if parent != path.parent or not stat.S_ISDIR(metadata.st_mode):
        raise SmokeFailure("evidence_output_parent_not_canonical")
    if path.name in {"", ".", ".."}:
        raise SmokeFailure("evidence_output_name_invalid")
    return path


def _external_file(path: Path) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("argument_not_absolute")
    if path.is_symlink():
        raise SmokeFailure("adapter_symlink_rejected")
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise SmokeFailure("adapter_unavailable") from error
    if resolved != path:
        raise SmokeFailure("argument_not_canonical")
    if not stat.S_ISREG(metadata.st_mode):
        raise SmokeFailure("adapter_not_regular_file")
    return resolved


def _external_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("argument_not_absolute")
    if path.is_symlink():
        raise SmokeFailure("fixture_root_is_symlink")
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise SmokeFailure("fixture_root_unavailable") from error
    if resolved != path:
        raise SmokeFailure("argument_not_canonical")
    if not stat.S_ISDIR(metadata.st_mode):
        raise SmokeFailure("fixture_root_not_directory")
    return resolved


def _assert_installed_boundary() -> None:
    module_file = getattr(ucf, "__file__", None)
    if not isinstance(module_file, str):
        raise SmokeFailure("installed_ucf_location_unavailable")
    module_path = Path(module_file).resolve(strict=True)
    environment_prefix = Path(sys.prefix).resolve(strict=True)
    if not module_path.is_relative_to(environment_prefix):
        raise SmokeFailure("installed_ucf_location_mismatch")
    if any(
        name == "tests"
        or name.startswith("tests.")
        or name == "tools"
        or name.startswith("tools.")
        for name in sys.modules
    ):
        raise SmokeFailure("repository_domain_import_rejected")


def _fixture_manifest(root: Path) -> _FixtureManifest:
    files: dict[str, _FileIdentity] = {}
    directories = {"."}
    pending = [(root, "")]
    total_bytes = 0
    while pending:
        directory, prefix = pending.pop()
        try:
            entries = sorted(
                os.scandir(directory),
                key=lambda entry: os.fsencode(entry.name),
            )
        except OSError as error:
            raise SmokeFailure("fixture_enumeration_failed") from error
        for entry in entries:
            relative = entry.name if not prefix else f"{prefix}/{entry.name}"
            if entry.is_symlink():
                raise SmokeFailure("fixture_symlink_rejected")
            if entry.is_dir(follow_symlinks=False):
                directories.add(relative)
                pending.append((Path(entry.path), relative))
                continue
            if not entry.is_file(follow_symlinks=False):
                raise SmokeFailure("fixture_file_type_rejected")
            identity = _hash_file(
                Path(entry.path),
                limit=_MAX_FIXTURE_FILE_BYTES,
                failure_prefix="fixture_file",
            )
            files[relative] = identity
            total_bytes += identity.size
            if total_bytes > _MAX_FIXTURE_BYTES:
                raise SmokeFailure("fixture_byte_limit_exceeded")
    return _FixtureManifest(files=files, directories=frozenset(directories))


def _source_manifest(manifest: _FixtureManifest) -> dict[str, _FileIdentity]:
    expected = {
        path: _FileIdentity(size=size, digest=digest)
        for path, (size, digest) in _EXPECTED_SOURCE_MANIFEST.items()
    }
    source = {
        path: identity
        for path, identity in manifest.files.items()
        if "__pycache__" not in Path(path).parts
    }
    source_directories = frozenset(
        path for path in manifest.directories if "__pycache__" not in Path(path).parts
    )
    if source != expected or source_directories != _EXPECTED_SOURCE_DIRECTORIES:
        raise SmokeFailure("fixture_source_identity_mismatch")
    return source


def _hash_file(path: Path, *, limit: int, failure_prefix: str) -> _FileIdentity:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise SmokeFailure(f"{failure_prefix}_open_failed") from error
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise SmokeFailure(f"{failure_prefix}_type_or_size_rejected")
        retained = 0
        while True:
            chunk = os.read(descriptor, min(65_536, limit + 1 - retained))
            if not chunk:
                break
            retained += len(chunk)
            if retained > limit:
                raise SmokeFailure(f"{failure_prefix}_size_rejected")
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_identity != after_identity:
        raise SmokeFailure(f"{failure_prefix}_changed_during_hash")
    return _FileIdentity(size=before.st_size, digest=digest.hexdigest())


def _inventory_request(record_limit: int) -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri=_SUBJECT_URI,
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version=INVENTORY_VERSION,
            rules=(),
        ),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=record_limit,
            cursor=None,
        ),
    )


def _discovery_request(inventory) -> DiscoveryRequest:
    inventory_digest = hashlib.sha256(canonical_inventory_json(inventory)).hexdigest()
    return DiscoveryRequest(
        kind="discovery_request_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DISCOVERY_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=DISCOVERY_CAPABILITY,
            version=ONBOARDING_VERSION,
        ),
        inventory_binding=InventoryBinding(
            kind="inventory_binding",
            schema_uri=inventory.schema_uri,
            inventory_version=inventory.inventory_version,
            subject_uri=inventory.subject_uri,
            source_revision=inventory.source_revision,
            canonical_digest=Digest(
                kind="digest",
                algorithm="sha-256",
                value=inventory_digest,
            ),
        ),
        inventory=inventory,
    )


def _reviewed_replacement_proposal() -> CandidateProposal:
    suffix = "render-receipt"
    action_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.ACTION,
        target_id=f"action.{suffix}",
    )
    use_case_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.USE_CASE,
        target_id=f"use-case.{suffix}",
    )
    step_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.STEP,
        target_id=f"step.{suffix}",
    )
    binding_ref = ProposalEntityRef(
        kind="proposal_entity_ref",
        target_kind=ProposalEntityKind.BINDING,
        target_id=f"binding.{suffix}.quantity",
    )
    input_ports = (
        Port(
            kind="port",
            name="quantity",
            value_kind=ValueKind.INTEGER,
            required=True,
        ),
    )
    output_ports = (
        Port(
            kind="port",
            name="total-cents",
            value_kind=ValueKind.INTEGER,
            required=True,
        ),
    )
    entities = (
        ProposedAction(
            kind=ProposalEntityKind.ACTION,
            id=action_ref.target_id,
            input_ports=input_ports,
            output_ports=output_ports,
        ),
        ProposedBinding(
            kind=ProposalEntityKind.BINDING,
            id=binding_ref.target_id,
            target=ProposalPortRef(
                kind="proposal_port_ref",
                owner=step_ref,
                direction="input",
                name="quantity",
            ),
            source=ProposalPortRef(
                kind="proposal_port_ref",
                owner=use_case_ref,
                direction="input",
                name="quantity",
            ),
        ),
        ProposedStep(
            kind=ProposalEntityKind.STEP,
            id=step_ref.target_id,
            action=action_ref,
            bindings=(binding_ref,),
        ),
        ProposedUseCase(
            kind=ProposalEntityKind.USE_CASE,
            id=use_case_ref.target_id,
            input_ports=input_ports,
            output_ports=output_ports,
            steps=(step_ref,),
        ),
    )
    return CandidateProposal(
        kind="candidate_proposal",
        root=use_case_ref,
        entities=tuple(sorted(entities, key=lambda entity: (entity.kind, entity.id))),
    )


def _review_decisions(discovery) -> DecisionSet:
    discovery_digest = canonical_onboarding_digest(discovery)
    base = DecisionSet(
        kind="decision_set_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DECISION_SET_SCHEMA_URI,
        discovery=DiscoveryDocumentRef(
            kind="discovery_document_ref",
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=discovery_digest,
        ),
        inventory_binding=discovery.inventory_binding,
        reviewer=Producer(
            kind="producer",
            name="org.ucf.fixture-reviewer",
            version="1.0.0",
        ),
        capture_context=CaptureContext(
            kind="capture_context",
            captured_at="2026-07-19T12:00:00Z",
            environment=Digest(
                kind="digest",
                algorithm="sha-256",
                value="a" * 64,
            ),
        ),
        decisions=(),
    )
    provisional = []
    for candidate in discovery.candidates:
        candidate_ref = CandidateRef(
            kind="candidate_ref",
            discovery_digest=discovery_digest,
            candidate_id=candidate.id,
            semantic_digest=candidate.semantic_digest,
        )
        common = {
            "id": f"decision.{'0' * 64}",
            "candidate": candidate_ref,
        }
        root = candidate.proposal.root.target_id
        if root == _QUOTE_ROOT:
            decision = AcceptedDecision(
                kind="accepted_decision",
                reason="Matches the existing native behavior checks.",
                **common,
            )
        elif root == "use-case.format-receipt":
            replacement = _reviewed_replacement_proposal()
            decision = EditedDecision(
                kind="edited_decision",
                reason="Use the reviewed product vocabulary.",
                replacement_digest=derive_candidate_semantic_digest(replacement),
                replacement=replacement,
                **common,
            )
        elif root == "use-case.normalize-coupon":
            decision = RejectedDecision(
                kind="rejected_decision",
                reason="Internal lookup helper, not a user behavior.",
                **common,
            )
        elif root == "use-case.legacy-discount-hint":
            decision = UncertainDecision(
                kind="uncertain_decision",
                reason="No executable check establishes intended semantics.",
                **common,
            )
        else:
            raise SmokeFailure("unexpected_candidate_root")
        provisional.append(
            decision.model_copy(update={"id": derive_decision_id(decision, base)})
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    provisional,
                    key=lambda decision: decision.candidate.candidate_id,
                )
            )
        }
    )


def _mapping_request(bundle) -> ImplementationMappingRequest:
    quote_materializations = tuple(
        materialization
        for materialization in bundle.baseline.materializations
        if materialization.root.target_id == _QUOTE_ROOT
    )
    if len(quote_materializations) != 1:
        raise SmokeFailure("quote_materialization_mismatch")
    return ImplementationMappingRequest(
        kind="implementation_mapping_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=IMPLEMENTATION_MAPPING_PROCEDURE_URI,
        adapter_procedure_uri=_MAPPING_ADAPTER_PROCEDURE_URI,
        onboarding=OnboardingBundleBinding(
            kind="onboarding_bundle_binding",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        behavior=bundle.behavior,
        inventory=bundle.inventory,
        targets=(quote_materializations[0].root,),
    )


def _execution_environment(
    fixture: Path,
    inventory,
    producer: Producer,
) -> ExecutionEnvironment:
    records_by_path = {
        record.path: record
        for record in inventory.records
        if isinstance(record, RepositoryEntryFact)
    }
    artifacts = []
    for relative in _EXECUTION_ARTIFACT_PATHS:
        identity = _hash_file(
            fixture / relative,
            limit=_MAX_FIXTURE_FILE_BYTES,
            failure_prefix="execution_artifact",
        )
        record = records_by_path.get(relative)
        if (
            record is None
            or record.entry_kind != "file"
            or record.size_bytes != identity.size
            or record.content_digest.value != identity.digest
        ):
            raise SmokeFailure("execution_artifact_inventory_mismatch")
        artifacts.append(
            {
                "kind": "execution_artifact",
                "path": relative,
                "size_bytes": identity.size,
                "content_digest": _digest(identity.digest),
            }
        )
    interpreter = Path(sys.executable).resolve(strict=True)
    interpreter_identity = _hash_file(
        interpreter,
        limit=_MAX_INTERPRETER_BYTES,
        failure_prefix="interpreter",
    )
    version = sys.version_info
    receipt = {
        "kind": "python_native_execution_receipt",
        "receipt_version": IMPLEMENTATION_EVIDENCE_VERSION,
        "producer": producer.model_dump(mode="json"),
        "procedure_uri": _VERIFICATION_ADAPTER_PROCEDURE_URI,
        "runtime": {
            "kind": "python_runtime_coordinates",
            "implementation": sys.implementation.name,
            "version": f"{version.major}.{version.minor}.{version.micro}",
            "cache_tag": sys.implementation.cache_tag,
            "platform": sys.platform,
            "machine": platform.machine(),
            "executable": {
                "kind": "executable_identity",
                "logical_name": "python",
                "resolved_name": interpreter.name,
                "size_bytes": interpreter_identity.size,
                "content_digest": _digest(interpreter_identity.digest),
            },
        },
        "argv": ["python", "-P", "-B", "-S", "tests/behavior_checks.py"],
        "environment": [
            ["PYTHONHASHSEED", "0"],
            ["PYTHONIOENCODING", "utf-8"],
            ["PYTHONPATH", "src"],
            ["PYTHONUTF8", "1"],
        ],
        "artifacts": artifacts,
    }
    return ExecutionEnvironment(
        kind="execution_environment",
        identity_uri=_ENVIRONMENT_IDENTITY_URI,
        revision=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(_canonical_json(receipt)).hexdigest(),
        ),
    )


def _verification_request(mapping, *, environment: ExecutionEnvironment):
    if len(mapping.bindings) != 1:
        raise SmokeFailure("mapping_binding_count_mismatch")
    binding = mapping.bindings[0]
    subjects = tuple(
        entity
        for entity in mapping.request.behavior.entities
        if entity.id == binding.behavior.target_id
    )
    if len(subjects) != 1:
        raise SmokeFailure("mapped_subject_mismatch")
    subject = subjects[0]
    owner = EntityRef(
        kind="entity_ref",
        target_kind=binding.behavior.target_kind,
        target_id=binding.behavior.target_id,
    )
    input_values = {"quantity": 2, "unit-price-cents": 1250}
    output_values = {"total-cents": 2500}
    if frozenset(port.name for port in subject.input_ports) != frozenset(
        input_values
    ) or frozenset(port.name for port in subject.output_ports) != frozenset(
        output_values
    ):
        raise SmokeFailure("verification_port_contract_mismatch")
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
        adapter_procedure_uri=_VERIFICATION_ADAPTER_PROCEDURE_URI,
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
            ExecutionPortValue(
                kind="execution_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=owner,
                    direction="input",
                    name=port.name,
                ),
                value=IntegerValue(kind="integer", value=input_values[port.name]),
            )
            for port in subject.input_ports
        ),
        expected_outputs=tuple(
            ExecutionPortValue(
                kind="execution_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=owner,
                    direction="output",
                    name=port.name,
                ),
                value=IntegerValue(kind="integer", value=output_values[port.name]),
            )
            for port in subject.output_ports
        ),
        source=ImplementationSource(
            kind="implementation_source",
            subject_uri=mapping.request.inventory.subject_uri,
            source_revision=mapping.request.inventory.source_revision,
            records=binding.source_records,
        ),
        environment=environment,
        check=Check(
            kind="check",
            id=_CHECK_ID,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
            procedure_uri=_CHECK_PROCEDURE_URI,
        ),
    )


async def _run_workflow(
    arguments: _Arguments,
    *,
    record_limit: int,
    execute_verification: bool,
) -> _WorkflowResult:
    requested_capabilities = tuple(
        CapabilityRequest(
            kind="capability_request",
            name=name,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        )
        for name in (
            INVENTORY_CAPABILITY,
            DISCOVERY_CAPABILITY,
            IMPLEMENTATION_MAPPING_CAPABILITY,
            EXECUTION_VERIFICATION_CAPABILITY,
        )
    )
    adapter = AdapterProcess(
        command=(
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(arguments.adapter),
        ),
        cwd=arguments.fixture,
        requested_capabilities=requested_capabilities,
        timeouts=_TIMEOUTS,
    )
    verification_result = None
    successor_behavior = None
    tested_trust = None
    tested_claim_count = 0
    verified_claim_count = 0
    verification_evidence_count = 0
    try:
        initialized = await adapter.start()
        inventory = await collect_inventory_from_process(
            adapter,
            request=_inventory_request(record_limit),
            operation_timeout=5.0,
        )
        discovery_request = _discovery_request(inventory)
        discovery = discovery_result_from_payload(
            await adapter.call(
                Method.DISCOVER,
                discovery_request_to_payload(discovery_request),
                timeout=5.0,
            )
        )
        validate_discovery_exchange(discovery_request, discovery)
        decisions = _review_decisions(discovery)
        bundle = build_onboarding_bundle(inventory, discovery, decisions)
        mapping_request = _mapping_request(bundle)
        validate_implementation_mapping_request(mapping_request, bundle=bundle)
        mapping = implementation_mapping_result_from_payload(
            await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=5.0,
            )
        )
        validate_implementation_mapping_result(
            mapping,
            request=mapping_request,
            bundle=bundle,
            current_inventory=inventory,
            initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        verification_request = _verification_request(
            mapping,
            environment=_execution_environment(
                arguments.fixture,
                inventory,
                initialized.adapter,
            ),
        )
        validate_execution_verification_request(
            verification_request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        if execute_verification:
            verification_result = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(verification_request),
                    timeout=10.0,
                )
            )
            validate_execution_verification_result(
                verification_result,
                request=verification_request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            if verification_result.outcome != "passed":
                raise SmokeFailure("verification_not_passed")
            projection = project_execution_verification(
                verification_result,
                request=verification_request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            successor_behavior = projection.successor_behavior
            tested_trust = projection.tested_trust
            claims = tuple(
                record for record in tested_trust.records if isinstance(record, Claim)
            )
            tested_claim_count = sum(
                claim.level is ClaimLevel.TESTED for claim in claims
            )
            verified_claim_count = sum(
                claim.level is ClaimLevel.VERIFIED for claim in claims
            )
            if any(
                isinstance(record, TrustMapping)
                or isinstance(record, Claim)
                and record.level is ClaimLevel.MAPPED
                for record in tested_trust.records
            ):
                raise SmokeFailure("claim_projection_overpromoted")
            evidence = tuple(
                entity
                for entity in successor_behavior.entities
                if isinstance(entity, VerificationEvidence)
            )
            verification_evidence_count = len(evidence)
            if (
                tested_claim_count != 1
                or verified_claim_count != 0
                or verification_evidence_count != 1
                or evidence[0].outcome != "passed"
            ):
                raise SmokeFailure("verification_projection_mismatch")
            validate_trust_against_behavior(tested_trust, successor_behavior)
    finally:
        await adapter.close()
    canonical = _CanonicalStructure(
        inventory=_validated_inventory_bytes(inventory),
        discovery=_validated_discovery_bytes(discovery),
        decisions=_validated_decisions_bytes(decisions),
        bundle=_validated_bundle_bytes(bundle),
        mapping=_validated_mapping_bytes(mapping),
        verification_request=_validated_verification_request_bytes(
            verification_request
        ),
    )
    return _WorkflowResult(
        canonical=canonical,
        inventory=inventory,
        discovery=discovery,
        decisions=decisions,
        bundle=bundle,
        mapping=mapping,
        verification_request=verification_request,
        verification_result=verification_result,
        successor_behavior=successor_behavior,
        tested_trust=tested_trust,
        tested_claim_count=tested_claim_count,
        verified_claim_count=verified_claim_count,
        verification_evidence_count=verification_evidence_count,
        stderr_bytes=adapter.stderr_total_bytes,
    )


def _validated_inventory_bytes(document) -> bytes:
    encoded = canonical_inventory_json(document)
    if canonical_inventory_json(parse_inventory_snapshot_json(encoded)) != encoded:
        raise SmokeFailure("inventory_not_canonical")
    return encoded


def _validated_discovery_bytes(document) -> bytes:
    encoded = canonical_onboarding_json(document)
    if canonical_onboarding_json(parse_discovery_result_json(encoded)) != encoded:
        raise SmokeFailure("discovery_not_canonical")
    return encoded


def _validated_decisions_bytes(document) -> bytes:
    encoded = canonical_onboarding_json(document)
    if canonical_onboarding_json(parse_decision_set_json(encoded)) != encoded:
        raise SmokeFailure("decisions_not_canonical")
    return encoded


def _validated_bundle_bytes(document) -> bytes:
    encoded = canonical_onboarding_json(document)
    if canonical_onboarding_json(parse_onboarding_bundle_json(encoded)) != encoded:
        raise SmokeFailure("bundle_not_canonical")
    return encoded


def _validated_mapping_bytes(document) -> bytes:
    encoded = canonical_implementation_evidence_json(document)
    if (
        canonical_implementation_evidence_json(
            parse_implementation_mapping_result_json(encoded)
        )
        != encoded
    ):
        raise SmokeFailure("mapping_not_canonical")
    return encoded


def _validated_verification_request_bytes(document) -> bytes:
    encoded = canonical_implementation_evidence_json(document)
    if (
        canonical_implementation_evidence_json(
            parse_execution_verification_request_json(encoded)
        )
        != encoded
    ):
        raise SmokeFailure("verification_request_not_canonical")
    return encoded


def _validated_verification_result(document) -> dict[str, object]:
    encoded = canonical_implementation_evidence_json(document)
    if (
        canonical_implementation_evidence_json(
            parse_execution_verification_result_json(encoded)
        )
        != encoded
    ):
        raise SmokeFailure("verification_result_not_canonical")
    return json.loads(encoded)


def _validated_behavior(document) -> dict[str, object]:
    encoded = canonical_ir_json(document)
    if canonical_ir_json(parse_ir_json(encoded)) != encoded:
        raise SmokeFailure("successor_behavior_not_canonical")
    return json.loads(encoded)


def _validated_trust(document) -> dict[str, object]:
    encoded = canonical_trust_ir_json(document)
    if canonical_trust_ir_json(parse_trust_ir_json(encoded)) != encoded:
        raise SmokeFailure("tested_trust_not_canonical")
    return json.loads(encoded)


def _assert_workflow(first: _WorkflowResult, second: _WorkflowResult) -> None:
    if first.canonical != second.canonical:
        raise SmokeFailure("structural_artifacts_not_deterministic")
    for result in (first, second):
        roots = frozenset(
            candidate.proposal.root.target_id
            for candidate in result.discovery.candidates
        )
        disposition_counts = {
            disposition.value: len(summary.candidate_ids)
            for summary in result.bundle.baseline.dispositions
            for disposition in (summary.disposition,)
        }
        materialization_roots = frozenset(
            materialization.root.target_id
            for materialization in result.bundle.baseline.materializations
        )
        if (
            len(result.inventory.records) != 24
            or result.inventory.subject_uri != _SUBJECT_URI
            or len(result.discovery.candidates) != 4
            or roots != _EXPECTED_CANDIDATE_ROOTS
            or result.discovery.coverage.status != "complete"
            or len(result.discovery.coverage.eligible_subjects) != 4
            or result.discovery.coverage.uncovered_subjects
            or disposition_counts
            != {"accepted": 1, "edited": 1, "rejected": 1, "uncertain": 1}
            or materialization_roots != {_QUOTE_ROOT, _RENDER_ROOT}
            or len(result.mapping.bindings) != 1
            or result.mapping.bindings[0].behavior.target_id != _QUOTE_ROOT
            or result.stderr_bytes != 0
        ):
            raise SmokeFailure("workflow_acceptance_mismatch")
    if (
        first.verification_result is None
        or first.successor_behavior is None
        or first.tested_trust is None
        or first.tested_claim_count != 1
        or first.verified_claim_count != 0
        or first.verification_evidence_count != 1
        or second.verification_result is not None
        or second.successor_behavior is not None
        or second.tested_trust is not None
    ):
        raise SmokeFailure("verification_execution_count_mismatch")


def _source_evidence(source: dict[str, _FileIdentity]) -> dict[str, object]:
    manifest = [
        {"path": path, "size": identity.size, "digest": identity.digest}
        for path, identity in sorted(source.items())
    ]
    return {
        "file_count": len(manifest),
        "byte_count": sum(entry["size"] for entry in manifest),
        "manifest_digest": hashlib.sha256(_canonical_json(manifest)).hexdigest(),
    }


def _evidence_document(
    result: _WorkflowResult,
    *,
    source: dict[str, _FileIdentity],
) -> dict[str, object]:
    if (
        result.verification_result is None
        or result.successor_behavior is None
        or result.tested_trust is None
    ):
        raise SmokeFailure("verification_evidence_unavailable")
    dispositions = {
        summary.disposition.value: len(summary.candidate_ids)
        for summary in result.bundle.baseline.dispositions
    }
    return {
        "kind": "rel001_lane_evidence",
        "evidence_version": _EVIDENCE_VERSION,
        "lane": "python",
        "status": "passed",
        "source": _source_evidence(source),
        "deterministic": {
            "inventory": json.loads(result.canonical.inventory),
            "discovery": json.loads(result.canonical.discovery),
            "decisions": json.loads(result.canonical.decisions),
            "bundle": json.loads(result.canonical.bundle),
            "mapping": json.loads(result.canonical.mapping),
            "verification_requests": [
                json.loads(result.canonical.verification_request)
            ],
        },
        "runtime": {
            "verification_results": [
                _validated_verification_result(result.verification_result)
            ],
            "successor_behaviors": [_validated_behavior(result.successor_behavior)],
            "tested_trust": [_validated_trust(result.tested_trust)],
        },
        "metrics": {
            "inventory_record_count": len(result.inventory.records),
            "candidate_count": len(result.discovery.candidates),
            "dispositions": dispositions,
            "eligible_interface_count": len(
                result.discovery.coverage.eligible_subjects
            ),
            "uncovered_interface_count": len(
                result.discovery.coverage.uncovered_subjects
            ),
            "materialization_count": len(result.bundle.baseline.materializations),
            "mapping_binding_count": len(result.mapping.bindings),
            "tested_claim_count": result.tested_claim_count,
            "verified_claim_count": result.verified_claim_count,
            "verification_evidence_count": result.verification_evidence_count,
            "transports": [],
        },
    }


def _publish_evidence(path: Path, document: dict[str, object]) -> None:
    payload = _canonical_json(document)
    if len(payload) > _MAX_EVIDENCE_BYTES:
        raise SmokeFailure("evidence_output_size_exceeded")
    if os.path.lexists(path):
        raise SmokeFailure("evidence_output_exists")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        view = memoryview(payload)
        written = 0
        while written < len(view):
            written += os.write(descriptor, view[written:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as error:
            raise SmokeFailure("evidence_output_exists") from error
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _digest(value: str) -> dict[str, str]:
    return {"kind": "digest", "algorithm": "sha-256", "value": value}


def _run(arguments: _Arguments) -> None:
    _assert_installed_boundary()
    before = _fixture_manifest(arguments.fixture)
    source = _source_manifest(before)
    try:
        first = asyncio.run(
            _run_workflow(
                arguments,
                record_limit=7,
                execute_verification=True,
            )
        )
        if _fixture_manifest(arguments.fixture) != before:
            raise SmokeFailure("fixture_changed_by_first_workflow")
        second = asyncio.run(
            _run_workflow(
                arguments,
                record_limit=1,
                execute_verification=False,
            )
        )
        _assert_workflow(first, second)
    finally:
        if _fixture_manifest(arguments.fixture) != before:
            raise SmokeFailure("fixture_changed_by_workflow")
    if arguments.evidence_output is not None:
        _publish_evidence(
            arguments.evidence_output,
            _evidence_document(first, source=source),
        )


def _emit(payload: dict[str, str], *, stream) -> None:
    stream.write(_canonical_json(payload).decode("ascii"))
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parse_arguments(sys.argv[1:] if argv is None else argv)
        _run(arguments)
    except SmokeFailure as error:
        _emit({"code": error.code, "status": "FAIL"}, stream=sys.stderr)
        return 3
    except AdapterProtocolError:
        _emit(
            {"code": "adapter_protocol_failure", "status": "FAIL"},
            stream=sys.stderr,
        )
        return 3
    except (
        ImplementationEvidenceValidationError,
        IRValidationError,
        OnboardingValidationError,
        ValidationError,
    ):
        _emit(
            {"code": "validation_failure", "status": "FAIL"},
            stream=sys.stderr,
        )
        return 3
    except OSError:
        _emit(
            {"code": "operating_system_failure", "status": "FAIL"},
            stream=sys.stderr,
        )
        return 3
    _emit({"status": "PASS"}, stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
