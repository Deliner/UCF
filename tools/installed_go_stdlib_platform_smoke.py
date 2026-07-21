#!/usr/bin/env python3
"""Run the installed Go CLI and file-spool platform slice."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import ucf
from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    Method,
    ProcessTimeouts,
    ProtocolCode,
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
    ImplementationMappingResult,
    ImplementationMappingResultRef,
    ImplementationSource,
    OnboardingBundleBinding,
    canonical_implementation_evidence_digest,
    canonical_implementation_evidence_json,
    derive_execution_verification_result_id,
    derive_implementation_mapping_result_id,
    execution_verification_request_to_payload,
    execution_verification_result_from_payload,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    project_execution_verification,
    validate_execution_verification_request,
    validate_execution_verification_result,
    validate_implementation_mapping_request,
    validate_implementation_mapping_result,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    BuildManifestFact,
    FactKind,
    IgnorePolicy,
    InventoryPageRequest,
    InventoryRequest,
    InventorySnapshot,
    PublicInterfaceFact,
    RepositoryEntryFact,
    TestAssetFact,
    canonical_inventory_json,
    collect_inventory_from_process,
)
from ucf.ir import (
    ClaimLevel,
    canonical_ir_json,
    canonical_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import (
    Check,
    Digest,
    EntityRef,
    IntegerValue,
    PortRef,
    Producer,
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
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    DiscoveryRequest,
    InventoryBinding,
    OnboardingBundle,
    OnboardingValidationError,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    canonical_onboarding_json,
    derive_decision_id,
    discovery_request_to_payload,
    discovery_result_from_payload,
    validate_discovery_exchange,
)

_EXPECTED_SOURCE_MANIFEST = {
    ".gitignore": (
        16,
        "154db9363b765d2d2798b27cee79d56070bd201a514d3cf3a066c9920a6e4a1c",
    ),
    "README.md": (
        621,
        "7e7345a5150e0a08289b92b149cc1bf784f2176fa3d338747727dbce2c9fea1c",
    ),
    "cmd/platform/main.go": (
        4_619,
        "1e7faf1267d48b374b59e5ae176b0ff22469d61842e9b7a248e4d844533bdd5b",
    ),
    "cmd/platform/main_test.go": (
        4_231,
        "66404161e1fc9af3eef2dbc9c79f4c2b7a52439c148fa8a5d8261a0938c3956f",
    ),
    "go.mod": (
        66,
        "ccc1bf985b3512984f582de114a38aa1088f011b355c571e4940ad402ac5742f",
    ),
    "quote/service.go": (
        458,
        "1a18934ea9f4bcbe26e19af60b692ae881a11043d59ac1c003350abf18557845",
    ),
    "quote/service_test.go": (
        692,
        "dd65864dd893b2c66a343391ba89cdafd4e408bd048899f90928769a5ecea0e8",
    ),
    "spool/spool.go": (
        8_193,
        "f2656623ed3a78c2e21dd0e5fa73b57d1fb37b476ac321aece228edae4bb96d8",
    ),
    "spool/spool_test.go": (
        1_914,
        "a2617631edfa830a4f6dfa97d8f60e3c9bbca7eaa493b6ae24acfab50161dd18",
    ),
}
_EXPECTED_SOURCE_DIRECTORIES = frozenset({".", "cmd", "cmd/platform", "quote", "spool"})
_EXPECTED_MANIFEST_REVISION = (
    "7b563b0296cb40498b984edc1ea3eb96b9fb8e96c8225aa695bc50b8b0889d2d"
)
_EXPECTED_INVENTORY_SOURCE_REVISION = (
    "f73cb876ca4cfd89fd0abf0a05e36edc7a98b4e0d81ab64c2e6e1c4e6955bc7c"
)
_EXPECTED_PLATFORM_BINARY_DIGEST = (
    "f54ab3d5dfc50b5bf57610da6ec081aa3b4f700a71064fdaf041ebc56ac7cff4"
)
_SUBJECT_URI = "urn:ucf:repository:go-stdlib-legacy-platforms"
_EXPECTED_INVENTORY_RECORD_COUNT = 62
_EXPECTED_REPOSITORY_PATHS = frozenset(
    {
        ".",
        ".gitignore",
        "README.md",
        "cmd",
        "cmd/platform",
        "cmd/platform/main.go",
        "cmd/platform/main_test.go",
        "go.mod",
        "quote",
        "quote/service.go",
        "quote/service_test.go",
        "spool",
        "spool/spool.go",
        "spool/spool_test.go",
    }
)
_EXPECTED_INTERFACE_NAMES = frozenset(
    {
        "DispatchOne",
        "Enqueue",
        "FormatReceipt",
        "Observe",
        "QuoteOrder",
        "event dispatch-once",
        "event enqueue",
        "event observe",
        "quote",
    }
)
_EXPECTED_TEST_NAMES = frozenset(
    {
        "TestCommandProcessesExposeCLIAndTemporallyDecoupledEvent",
        "TestCommandProcessesRejectInvalidAndDuplicateInput",
        "TestEventRemainsUnobservedUntilIndependentDispatch",
        "TestEventSpoolRejectsDuplicatesInvalidIDsAndSymlinks",
        "TestPlatformHelperProcess",
        "TestQuoteOrderRejectsInvalidValues",
        "TestQuoteOrderReturnsTheLegacyTotal",
    }
)
_EXPECTED_QUOTE_EVIDENCE = frozenset(
    {("build_manifest", "go.mod")}
    | {("public_interface", name) for name in _EXPECTED_INTERFACE_NAMES}
)
_QUOTE_ROOT = "use-case.quote-order"
_QUOTE_SEMANTIC_DIGEST = (
    "cd09cf6ac27457ddbd62715ad903b4b3e0217c6b580cbde1d75c8d2c1b17153a"
)
_ADAPTER_NAME = "org.ucf.adapter.go-stdlib"
_ADAPTER_VERSION = "1.0.0"
_DISCOVERY_PROCEDURE_URI = (
    "urn:ucf:onboarding-procedure:go-stdlib-static-discovery:1.0.0"
)
_MAPPING_PROCEDURE_URI = "urn:ucf:adapter:go-stdlib-static-mapping:1.0.0"
_CLI_PROCESS_CAPABILITY = "org.ucf.platform.cli-process"
_EVENT_CAPABILITY = "org.ucf.platform.file-spool-event"
_CLI_PROCEDURE_URI = "urn:ucf:adapter:go-stdlib-real-cli-verification:1.0.0"
_CLI_CHECK_ID = "check.quote-order.real-cli"
_CLI_CHECK_PROCEDURE_URI = (
    "urn:ucf:fixture-check:quote-order-cli-process-contract:1.0.0"
)
_CLI_ENVIRONMENT_URI = (
    "urn:ucf:fixture-environment:go1.26.5-linux-amd64-cgo0-cli-process:1.0.0"
)
_EVENT_PROCEDURE_URI = "urn:ucf:adapter:go-stdlib-file-spool-event-verification:1.0.0"
_EVENT_CHECK_ID = "check.quote-order.file-spool-event"
_EVENT_CHECK_PROCEDURE_URI = (
    "urn:ucf:fixture-check:quote-order-event-enqueue-dispatch-observe:1.0.0"
)
_EVENT_ENVIRONMENT_URI = (
    "urn:ucf:fixture-environment:go1.26.5-linux-amd64-cgo0-file-spool-event:1.0.0"
)
_TIMEOUTS = ProcessTimeouts(
    initialize=5.0,
    operation=30.0,
    write=5.0,
    cancellation=1.0,
    shutdown=2.0,
    terminate=1.0,
    kill=1.0,
)
_EVIDENCE_VERSION = "1.0.0"
_MAX_EVIDENCE_BYTES = 16_777_216


class SmokeFailure(RuntimeError):
    """A stable, path-free installed-smoke failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _Arguments:
    adapter: Path
    fixture: Path
    platform_fixture_executable: Path
    evidence_output: Path | None = None


@dataclass(frozen=True)
class _FileIdentity:
    size: int
    digest: str
    device: int
    inode: int
    mode: int
    modified_ns: int
    changed_ns: int

    @property
    def content(self) -> tuple[int, str]:
        return (self.size, self.digest)


@dataclass(frozen=True)
class _DeterministicArtifacts:
    inventory: bytes
    discovery: bytes
    decisions: bytes
    bundle: bytes
    mapping: bytes
    cli_request: bytes
    event_request: bytes


@dataclass(frozen=True)
class _RuntimeArtifacts:
    verification_results: tuple[bytes, ...]
    successor_behaviors: tuple[str, ...]
    tested_trust: tuple[str, ...]


@dataclass(frozen=True)
class _WorkflowResult:
    deterministic: _DeterministicArtifacts
    runtime: _RuntimeArtifacts
    bundle: OnboardingBundle
    mapping_id: str
    mapping_source_record_ids: tuple[str, ...]
    verification_outcomes: tuple[str, ...]
    tested_claim_count: int
    verified_claim_count: int
    verification_evidence_count: int
    stderr_bytes: int


@dataclass(frozen=True)
class _RunResult:
    summary: dict[str, object]
    evidence: dict[str, object]


def _parse_arguments(argv: list[str]) -> _Arguments:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise an installed UCF wheel with the external Go "
            "CLI and file-spool event platform profile."
        )
    )
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument(
        "--platform-fixture-executable",
        required=True,
        type=Path,
    )
    parser.add_argument("--evidence-output", type=Path)
    namespace = parser.parse_args(argv)
    fixture = _external_directory(namespace.fixture)
    adapter = _external_file(namespace.adapter, executable=True)
    platform_fixture_executable = _external_file(
        namespace.platform_fixture_executable,
        executable=True,
    )
    if adapter.is_relative_to(fixture) or platform_fixture_executable.is_relative_to(
        fixture
    ):
        raise SmokeFailure("executable_inside_fixture_rejected")
    if adapter == platform_fixture_executable:
        raise SmokeFailure("executable_identity_collision")
    evidence_output = (
        None
        if namespace.evidence_output is None
        else _new_output_file(namespace.evidence_output)
    )
    if evidence_output is not None and evidence_output.is_relative_to(fixture):
        raise SmokeFailure("evidence_output_inside_fixture")
    return _Arguments(
        adapter=adapter,
        fixture=fixture,
        platform_fixture_executable=platform_fixture_executable,
        evidence_output=evidence_output,
    )


def _new_output_file(path: Path) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("evidence_output_not_absolute")
    if path.is_symlink():
        raise SmokeFailure("evidence_output_is_symlink")
    if path.exists():
        raise SmokeFailure("evidence_output_exists")
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise SmokeFailure("evidence_output_parent_missing") from error
    if parent != path.parent or not parent.is_dir():
        raise SmokeFailure("evidence_output_parent_not_directory")
    return path


def _external_file(path: Path, *, executable: bool) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("argument_not_absolute")
    if path.is_symlink():
        raise SmokeFailure("argument_symlink_rejected")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise SmokeFailure("argument_not_canonical")
    metadata = resolved.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise SmokeFailure("argument_not_regular_file")
    if executable and not os.access(resolved, os.X_OK):
        raise SmokeFailure("argument_not_executable")
    return resolved


def _external_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("argument_not_absolute")
    if path.is_symlink():
        raise SmokeFailure("fixture_root_is_symlink")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise SmokeFailure("argument_not_canonical")
    if not resolved.is_dir():
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


def _source_manifest(root: Path) -> dict[str, _FileIdentity]:
    files: dict[str, _FileIdentity] = {}
    directories = {"."}
    pending = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        try:
            entries = sorted(
                os.scandir(directory),
                key=lambda item: os.fsencode(item.name),
            )
        except OSError as error:
            raise SmokeFailure("fixture_enumeration_failed") from error
        for entry in entries:
            relative = entry.name if not prefix else f"{prefix}/{entry.name}"
            if entry.is_symlink():
                raise SmokeFailure("fixture_source_symlink_rejected")
            if entry.is_dir(follow_symlinks=False):
                directories.add(relative)
                pending.append((Path(entry.path), relative))
                continue
            if not entry.is_file(follow_symlinks=False):
                raise SmokeFailure("fixture_source_type_rejected")
            files[relative] = _hash_file(
                Path(entry.path),
                failure_prefix="fixture_source",
            )
    if frozenset(files) != frozenset(_EXPECTED_SOURCE_MANIFEST):
        raise SmokeFailure("fixture_source_files_mismatch")
    if frozenset(directories) != _EXPECTED_SOURCE_DIRECTORIES:
        raise SmokeFailure("fixture_source_directories_mismatch")
    return files


def _hash_file(path: Path, *, failure_prefix: str) -> _FileIdentity:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise SmokeFailure(f"{failure_prefix}_open_failed") from error
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SmokeFailure(f"{failure_prefix}_type_rejected")
        while chunk := os.read(descriptor, 65_536):
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = _metadata_identity(before)
    if before_identity != _metadata_identity(after):
        raise SmokeFailure(f"{failure_prefix}_changed_during_hash")
    return _FileIdentity(
        size=before.st_size,
        digest=digest.hexdigest(),
        device=before.st_dev,
        inode=before.st_ino,
        mode=before.st_mode,
        modified_ns=before.st_mtime_ns,
        changed_ns=before.st_ctime_ns,
    )


def _metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _source_revision(manifest: dict[str, _FileIdentity]) -> str:
    payload = "".join(
        f"{relative}\t{identity.size}\t{identity.digest}\n"
        for relative, identity in sorted(manifest.items())
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _manifest_digest(manifest: dict[str, _FileIdentity]) -> str:
    records = [
        {
            "path": relative,
            "size": identity.size,
            "digest": identity.digest,
        }
        for relative, identity in sorted(manifest.items())
    ]
    return hashlib.sha256(_canonical_json_bytes(records)).hexdigest()


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


def _discovery_request(inventory: InventorySnapshot) -> DiscoveryRequest:
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


def _accepted_decision(discovery) -> DecisionSet:
    base = DecisionSet(
        kind="decision_set_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DECISION_SET_SCHEMA_URI,
        discovery=DiscoveryDocumentRef(
            kind="discovery_document_ref",
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=canonical_onboarding_digest(discovery),
        ),
        inventory_binding=discovery.inventory_binding,
        reviewer=Producer(
            kind="producer",
            name="org.ucf.ecosystem-reviewer",
            version="1.0.0",
        ),
        capture_context=CaptureContext(
            kind="capture_context",
            captured_at="2026-07-19T12:00:00Z",
            environment=Digest(
                kind="digest",
                algorithm="sha-256",
                value=hashlib.sha256(
                    b"ucf-eco003-go-platform-review-policy:1.0.0\n"
                ).hexdigest(),
            ),
        ),
        decisions=(),
    )
    candidate = discovery.candidates[0]
    decision = AcceptedDecision(
        kind="accepted_decision",
        id=f"decision.{'0' * 64}",
        candidate=CandidateRef(
            kind="candidate_ref",
            discovery_digest=canonical_onboarding_digest(discovery),
            candidate_id=candidate.id,
            semantic_digest=candidate.semantic_digest,
        ),
        reason=(
            "Native process evidence matches the reviewed quote-order "
            "CLI and file-spool event scope."
        ),
    )
    return base.model_copy(
        update={
            "decisions": (
                decision.model_copy(update={"id": derive_decision_id(decision, base)}),
            )
        }
    )


def _mapping_request(bundle: OnboardingBundle) -> ImplementationMappingRequest:
    materialization = bundle.baseline.materializations[0]
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
        adapter_procedure_uri=_MAPPING_PROCEDURE_URI,
        onboarding=OnboardingBundleBinding(
            kind="onboarding_bundle_binding",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        behavior=bundle.behavior,
        inventory=bundle.inventory,
        targets=(materialization.root,),
    )


def _execution_environment(
    arguments: _Arguments,
    *,
    source_revision: str,
    boundary: str,
) -> ExecutionEnvironment:
    adapter = _hash_file(
        arguments.adapter,
        failure_prefix="adapter_executable",
    )
    platform = _hash_file(
        arguments.platform_fixture_executable,
        failure_prefix="platform_fixture_executable",
    )
    if platform.digest != _EXPECTED_PLATFORM_BINARY_DIGEST:
        raise SmokeFailure("platform_fixture_executable_identity_mismatch")
    coordinates = {
        "cli-process": (_CLI_ENVIRONMENT_URI, _CLI_PROCESS_CAPABILITY),
        "file-spool-event": (_EVENT_ENVIRONMENT_URI, _EVENT_CAPABILITY),
    }
    if boundary not in coordinates:
        raise SmokeFailure("execution_boundary_unsupported")
    identity_uri, _ = coordinates[boundary]

    def digest(value: str) -> dict[str, str]:
        return {
            "kind": "digest",
            "algorithm": "sha-256",
            "value": value,
        }

    receipt = {
        "kind": "go_stdlib_execution_receipt",
        "receipt_version": "1.0.0",
        "binaries": [
            {
                "kind": "go_binary",
                "role": "adapter",
                "module_path": "ucf/adapters/go-stdlib",
                "digest": digest(adapter.digest),
                "size_bytes": adapter.size,
            },
            {
                "kind": "go_binary",
                "role": "fixture",
                "module_path": "example.com/legacyplatforms",
                "digest": digest(platform.digest),
                "size_bytes": platform.size,
            },
        ],
        "toolchain": {
            "kind": "go_toolchain",
            "version": "go1.26.5",
            "mode": "local",
        },
        "build": {
            "kind": "go_build_coordinates",
            "build_mode": "exe",
            "compiler": "gc",
            "trimpath": True,
            "cgo_enabled": False,
            "goos": "linux",
            "goarch": "amd64",
            "goamd64": "v1",
            "external_modules": [],
        },
        "runtime": {
            "kind": "go_runtime_coordinates",
            "version": "go1.26.5",
            "goos": "linux",
            "goarch": "amd64",
            "network": "disabled",
            "boundary": boundary,
        },
        "source": {
            "kind": "source_identity",
            "subject_uri": _SUBJECT_URI,
            "source_revision": digest(source_revision),
        },
    }
    encoded = (
        json.dumps(
            receipt,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    return ExecutionEnvironment(
        kind="execution_environment",
        identity_uri=identity_uri,
        revision=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(encoded).hexdigest(),
        ),
    )


def _verification_request(
    mapping: ImplementationMappingResult,
    *,
    environment: ExecutionEnvironment,
    procedure_uri: str,
    check_id: str,
    check_procedure_uri: str,
) -> ExecutionVerificationRequest:
    binding = mapping.bindings[0]
    subject = next(
        entity
        for entity in mapping.request.behavior.entities
        if entity.id == binding.behavior.target_id
    )
    owner = EntityRef(
        kind="entity_ref",
        target_kind=binding.behavior.target_kind,
        target_id=binding.behavior.target_id,
    )
    inputs = {"quantity": 2, "unit-price-cents": 1250}
    expected_outputs = {"total-cents": 2500}
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
        adapter_procedure_uri=procedure_uri,
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
                value=IntegerValue(
                    kind="integer",
                    value=inputs[port.name],
                ),
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
                value=IntegerValue(
                    kind="integer",
                    value=expected_outputs[port.name],
                ),
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
            id=check_id,
            version="1.0.0",
            procedure_uri=check_procedure_uri,
        ),
    )


def _required(name: str) -> CapabilityRequest:
    return CapabilityRequest(
        kind="capability_request",
        name=name,
        minimum_version="1.0.0",
        required=True,
    )


def _adapter(
    arguments: _Arguments,
    *,
    platform_capabilities: tuple[str, ...],
    include_discovery: bool,
) -> AdapterProcess:
    capability_names = [
        INVENTORY_CAPABILITY,
        IMPLEMENTATION_MAPPING_CAPABILITY,
        EXECUTION_VERIFICATION_CAPABILITY,
    ]
    if include_discovery:
        capability_names.insert(1, DISCOVERY_CAPABILITY)
    capability_names.extend(platform_capabilities)
    return AdapterProcess(
        command=(
            str(arguments.adapter),
            "--platform-fixture-executable",
            str(arguments.platform_fixture_executable),
        ),
        cwd=arguments.fixture,
        requested_capabilities=tuple(_required(name) for name in capability_names),
        timeouts=_TIMEOUTS,
    )


def _assert_inventory(
    inventory: InventorySnapshot,
    *,
    producer: Producer,
) -> None:
    repository_entries = tuple(
        record
        for record in inventory.records
        if isinstance(record, RepositoryEntryFact)
    )
    manifests = tuple(
        record for record in inventory.records if isinstance(record, BuildManifestFact)
    )
    interfaces = tuple(
        record
        for record in inventory.records
        if isinstance(record, PublicInterfaceFact)
    )
    tests = tuple(
        record for record in inventory.records if isinstance(record, TestAssetFact)
    )
    records_by_id = {record.id: record for record in inventory.records}
    if (
        inventory.inventory_version != INVENTORY_VERSION
        or inventory.schema_uri != INVENTORY_SCHEMA_URI
        or inventory.subject_uri != _SUBJECT_URI
        or inventory.source_revision.value != _EXPECTED_INVENTORY_SOURCE_REVISION
        or inventory.producer != producer
    ):
        raise SmokeFailure("inventory_coordinates_mismatch")
    if len(inventory.records) != _EXPECTED_INVENTORY_RECORD_COUNT:
        raise SmokeFailure("inventory_record_count_mismatch")
    if (
        frozenset(entry.path for entry in repository_entries)
        != _EXPECTED_REPOSITORY_PATHS
    ):
        raise SmokeFailure("inventory_repository_paths_mismatch")
    if len(manifests) != 1 or _referenced_path(manifests[0], records_by_id) != "go.mod":
        raise SmokeFailure("inventory_manifest_mismatch")
    if (
        frozenset(interface.name for interface in interfaces)
        != _EXPECTED_INTERFACE_NAMES
    ):
        raise SmokeFailure("inventory_interfaces_mismatch")
    if frozenset(test.name for test in tests) != _EXPECTED_TEST_NAMES:
        raise SmokeFailure("inventory_tests_mismatch")


def _referenced_path(record, records_by_id: dict[str, object]) -> str:
    entry = records_by_id.get(record.entry.target_id)
    if not isinstance(entry, RepositoryEntryFact):
        raise SmokeFailure("inventory_entry_reference_mismatch")
    return entry.path


def _interface_names(references, *, inventory: InventorySnapshot) -> frozenset[str]:
    records_by_id = {record.id: record for record in inventory.records}
    names: set[str] = set()
    for reference in references:
        record = records_by_id.get(reference.target_id)
        if not isinstance(record, PublicInterfaceFact):
            raise SmokeFailure("discovery_coverage_kind_mismatch")
        names.add(record.name)
    if len(names) != len(references):
        raise SmokeFailure("discovery_coverage_duplicate")
    return frozenset(names)


def _evidence_descriptors(
    references,
    *,
    inventory: InventorySnapshot,
) -> frozenset[tuple[str, str]]:
    records_by_id = {record.id: record for record in inventory.records}
    descriptors: set[tuple[str, str]] = set()
    for reference in references:
        record = records_by_id.get(reference.target_id)
        if isinstance(record, BuildManifestFact):
            descriptor = (
                "build_manifest",
                _referenced_path(record, records_by_id),
            )
        elif isinstance(record, PublicInterfaceFact):
            descriptor = ("public_interface", record.name)
        else:
            raise SmokeFailure("quote_evidence_kind_mismatch")
        descriptors.add(descriptor)
    if len(descriptors) != len(references):
        raise SmokeFailure("quote_evidence_duplicate")
    return frozenset(descriptors)


def _assert_bundle(bundle: OnboardingBundle) -> None:
    claims_by_level = {
        summary.level: summary.claim_ids for summary in bundle.baseline.claim_levels
    }
    if (
        len(bundle.decisions.decisions) != 1
        or not isinstance(bundle.decisions.decisions[0], AcceptedDecision)
        or len(bundle.baseline.materializations) != 1
        or bundle.baseline.materializations[0].root.target_id != _QUOTE_ROOT
        or tuple(root.target_id for root in bundle.behavior.roots) != (_QUOTE_ROOT,)
        or bundle.baseline.discovery_status != "partial"
        or len(claims_by_level[ClaimLevel.OBSERVED]) != 1
        or len(claims_by_level[ClaimLevel.DECLARED]) != 1
        or any(
            claims_by_level[level]
            for level in (
                ClaimLevel.MAPPED,
                ClaimLevel.TESTED,
                ClaimLevel.VERIFIED,
            )
        )
    ):
        raise SmokeFailure("review_materialization_mismatch")


def _is_whole_second_timestamp(value: str) -> bool:
    if len(value) != 20:
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.microsecond == 0 and parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


async def _run_workflow(
    arguments: _Arguments,
    *,
    record_limit: int,
) -> _WorkflowResult:
    adapter = _adapter(
        arguments,
        platform_capabilities=(
            _CLI_PROCESS_CAPABILITY,
            _EVENT_CAPABILITY,
        ),
        include_discovery=True,
    )
    try:
        initialized = await adapter.start()
        expected_capabilities = {
            INVENTORY_CAPABILITY: "1.0.0",
            DISCOVERY_CAPABILITY: "1.0.0",
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
            _CLI_PROCESS_CAPABILITY: "1.0.0",
            _EVENT_CAPABILITY: "1.0.0",
        }
        if (
            initialized.adapter.name != _ADAPTER_NAME
            or initialized.adapter.version != _ADAPTER_VERSION
            or adapter.negotiated_capabilities != expected_capabilities
        ):
            raise SmokeFailure("adapter_identity_mismatch")

        inventory = await collect_inventory_from_process(
            adapter,
            request=_inventory_request(record_limit),
            operation_timeout=30.0,
        )
        _assert_inventory(inventory, producer=initialized.adapter)

        discovery_request = _discovery_request(inventory)
        discovery = discovery_result_from_payload(
            await adapter.call(
                Method.DISCOVER,
                discovery_request_to_payload(discovery_request),
                timeout=30.0,
            )
        )
        validate_discovery_exchange(discovery_request, discovery)
        if (
            discovery.producer != initialized.adapter
            or discovery.procedure_uri != _DISCOVERY_PROCEDURE_URI
            or discovery.coverage.status != "partial"
            or len(discovery.candidates) != 1
            or len(discovery.coverage.eligible_subjects) != 9
            or len(discovery.coverage.uncovered_subjects) != 8
            or _interface_names(
                discovery.coverage.eligible_subjects,
                inventory=inventory,
            )
            != _EXPECTED_INTERFACE_NAMES
            or _interface_names(
                discovery.coverage.uncovered_subjects,
                inventory=inventory,
            )
            != _EXPECTED_INTERFACE_NAMES - {"QuoteOrder"}
        ):
            raise SmokeFailure("discovery_identity_mismatch")
        quote = discovery.candidates[0]
        if (
            quote.proposal.root.target_id != _QUOTE_ROOT
            or quote.semantic_digest.value != _QUOTE_SEMANTIC_DIGEST
            or len(quote.evidence) != 10
            or _evidence_descriptors(quote.evidence, inventory=inventory)
            != _EXPECTED_QUOTE_EVIDENCE
        ):
            raise SmokeFailure("quote_candidate_identity_mismatch")

        decisions = _accepted_decision(discovery)
        bundle = build_onboarding_bundle(inventory, discovery, decisions)
        _assert_bundle(bundle)

        mapping_request = _mapping_request(bundle)
        validate_implementation_mapping_request(
            mapping_request,
            bundle=bundle,
        )
        mapping = implementation_mapping_result_from_payload(
            await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=30.0,
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
        if (
            mapping.id != derive_implementation_mapping_result_id(mapping)
            or mapping.producer != initialized.adapter
            or mapping.procedure_uri != _MAPPING_PROCEDURE_URI
            or len(mapping.bindings) != 1
            or mapping.bindings[0].behavior.target_id != _QUOTE_ROOT
            or mapping.bindings[0].source_records != quote.evidence
            or len(mapping.bindings[0].source_records) != 10
        ):
            raise SmokeFailure("mapping_identity_mismatch")

        requests = (
            _verification_request(
                mapping,
                environment=_execution_environment(
                    arguments,
                    source_revision=inventory.source_revision.value,
                    boundary="cli-process",
                ),
                procedure_uri=_CLI_PROCEDURE_URI,
                check_id=_CLI_CHECK_ID,
                check_procedure_uri=_CLI_CHECK_PROCEDURE_URI,
            ),
            _verification_request(
                mapping,
                environment=_execution_environment(
                    arguments,
                    source_revision=inventory.source_revision.value,
                    boundary="file-spool-event",
                ),
                procedure_uri=_EVENT_PROCEDURE_URI,
                check_id=_EVENT_CHECK_ID,
                check_procedure_uri=_EVENT_CHECK_PROCEDURE_URI,
            ),
        )
        if (
            requests[0].mapping != requests[1].mapping
            or requests[0].subject != requests[1].subject
            or requests[0].source != requests[1].source
        ):
            raise SmokeFailure("platform_requests_do_not_share_mapping")

        results = []
        successor_behaviors = []
        tested_trust = []
        tested_claim_count = 0
        verified_claim_count = 0
        verification_evidence_count = 0
        for request in requests:
            validate_execution_verification_request(
                request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            result = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=30.0,
                )
            )
            validate_execution_verification_result(
                result,
                request=request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            if (
                result.id != derive_execution_verification_result_id(result)
                or result.request != request
                or result.status != "completed"
                or result.outcome != "passed"
                or result.producer != initialized.adapter
                or result.procedure_uri != request.adapter_procedure_uri
                or not _is_whole_second_timestamp(result.executed_at)
            ):
                raise SmokeFailure("verification_not_passed")
            projection = project_execution_verification(
                result,
                request=request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            claims = tuple(
                record
                for record in projection.tested_trust.records
                if isinstance(record, Claim)
            )
            tested = tuple(
                claim for claim in claims if claim.level is ClaimLevel.TESTED
            )
            verified = tuple(
                claim for claim in claims if claim.level is ClaimLevel.VERIFIED
            )
            evidence = tuple(
                entity
                for entity in projection.successor_behavior.entities
                if isinstance(entity, VerificationEvidence)
            )
            if (
                len(tested) != 1
                or verified
                or any(
                    isinstance(record, TrustMapping)
                    or isinstance(record, Claim)
                    and record.level is ClaimLevel.MAPPED
                    for record in projection.tested_trust.records
                )
                or len(evidence) != 1
                or evidence[0].outcome != "passed"
                or evidence[0].check != request.check
            ):
                raise SmokeFailure("claim_projection_mismatch")
            validate_trust_against_behavior(
                projection.tested_trust,
                projection.successor_behavior,
            )
            successor_behaviors.append(
                canonical_ir_json(projection.successor_behavior)
            )
            tested_trust.append(
                canonical_trust_ir_json(projection.tested_trust)
            )
            tested_claim_count += len(tested)
            verified_claim_count += len(verified)
            verification_evidence_count += len(evidence)
            results.append(result)
        if results[0].id == results[1].id:
            raise SmokeFailure("platform_verification_identity_collision")
    finally:
        await adapter.close()
    return _WorkflowResult(
        deterministic=_DeterministicArtifacts(
            inventory=canonical_inventory_json(inventory),
            discovery=canonical_onboarding_json(discovery),
            decisions=canonical_onboarding_json(decisions),
            bundle=canonical_onboarding_json(bundle),
            mapping=canonical_implementation_evidence_json(mapping),
            cli_request=canonical_implementation_evidence_json(requests[0]),
            event_request=canonical_implementation_evidence_json(requests[1]),
        ),
        runtime=_RuntimeArtifacts(
            verification_results=tuple(
                canonical_implementation_evidence_json(result)
                for result in results
            ),
            successor_behaviors=tuple(successor_behaviors),
            tested_trust=tuple(tested_trust),
        ),
        bundle=bundle,
        mapping_id=mapping.id,
        mapping_source_record_ids=tuple(
            reference.target_id for reference in mapping.bindings[0].source_records
        ),
        verification_outcomes=tuple(result.outcome for result in results),
        tested_claim_count=tested_claim_count,
        verified_claim_count=verified_claim_count,
        verification_evidence_count=verification_evidence_count,
        stderr_bytes=adapter.stderr_total_bytes,
    )


async def _assert_capability_procedure_mismatch(
    arguments: _Arguments,
    *,
    bundle: OnboardingBundle,
    negotiated_platform_capability: str,
    rejected_boundary: str,
) -> int:
    adapter = _adapter(
        arguments,
        platform_capabilities=(negotiated_platform_capability,),
        include_discovery=False,
    )
    try:
        initialized = await adapter.start()
        inventory = await collect_inventory_from_process(
            adapter,
            request=_inventory_request(3),
            operation_timeout=30.0,
        )
        _assert_inventory(inventory, producer=initialized.adapter)
        if canonical_inventory_json(inventory) != canonical_inventory_json(
            bundle.inventory
        ):
            raise SmokeFailure("mismatch_session_inventory_changed")
        mapping_request = _mapping_request(bundle)
        mapping = implementation_mapping_result_from_payload(
            await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=30.0,
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
        if rejected_boundary == "file-spool-event":
            procedure_uri = _EVENT_PROCEDURE_URI
            check_id = _EVENT_CHECK_ID
            check_procedure_uri = _EVENT_CHECK_PROCEDURE_URI
        elif rejected_boundary == "cli-process":
            procedure_uri = _CLI_PROCEDURE_URI
            check_id = _CLI_CHECK_ID
            check_procedure_uri = _CLI_CHECK_PROCEDURE_URI
        else:
            raise SmokeFailure("mismatch_boundary_unsupported")
        request = _verification_request(
            mapping,
            environment=_execution_environment(
                arguments,
                source_revision=inventory.source_revision.value,
                boundary=rejected_boundary,
            ),
            procedure_uri=procedure_uri,
            check_id=check_id,
            check_procedure_uri=check_procedure_uri,
        )
        validate_execution_verification_request(
            request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        try:
            await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
                timeout=30.0,
            )
        except AdapterProtocolError as error:
            if (
                error.category is not ErrorCategory.PROTOCOL_FAILURE
                or error.code is not ProtocolCode.CAPABILITY_NOT_NEGOTIATED
            ):
                raise SmokeFailure(
                    "platform_mismatch_error_identity_mismatch"
                ) from error
        else:
            raise SmokeFailure("platform_mismatch_was_accepted")
        if adapter.stderr_total_bytes != 0:
            raise SmokeFailure("platform_mismatch_stderr_not_empty")
        return adapter.stderr_total_bytes
    finally:
        await adapter.close()


def _assert_workflow_acceptance(result: _WorkflowResult) -> None:
    if (
        result.verification_outcomes != ("passed", "passed")
        or result.tested_claim_count != 2
        or result.verified_claim_count != 0
        or result.verification_evidence_count != 2
        or result.stderr_bytes != 0
        or len(result.mapping_source_record_ids) != 10
        or not result.mapping_id.startswith("mapping.")
        or len(result.runtime.verification_results) != 2
        or len(result.runtime.successor_behaviors) != 2
        or len(result.runtime.tested_trust) != 2
    ):
        raise SmokeFailure("workflow_acceptance_mismatch")


def _run(arguments: _Arguments) -> _RunResult:
    _assert_installed_boundary()
    before_source = _source_manifest(arguments.fixture)
    expected_content = {
        path: value for path, value in _EXPECTED_SOURCE_MANIFEST.items()
    }
    observed_content = {
        path: identity.content for path, identity in before_source.items()
    }
    if (
        observed_content != expected_content
        or _source_revision(before_source) != _EXPECTED_MANIFEST_REVISION
    ):
        raise SmokeFailure("fixture_source_identity_mismatch")
    before_adapter = _hash_file(
        arguments.adapter,
        failure_prefix="adapter_executable",
    )
    before_platform = _hash_file(
        arguments.platform_fixture_executable,
        failure_prefix="platform_fixture_executable",
    )
    if before_platform.digest != _EXPECTED_PLATFORM_BINARY_DIGEST:
        raise SmokeFailure("platform_fixture_executable_identity_mismatch")
    mismatch_rejections = 0
    try:
        first = asyncio.run(_run_workflow(arguments, record_limit=7))
        _assert_workflow_acceptance(first)
        if _source_manifest(arguments.fixture) != before_source:
            raise SmokeFailure("fixture_source_changed_by_first_workflow")
        second = asyncio.run(_run_workflow(arguments, record_limit=1))
        _assert_workflow_acceptance(second)
        if (
            first.deterministic != second.deterministic
            or first.mapping_id != second.mapping_id
            or first.mapping_source_record_ids != second.mapping_source_record_ids
            or first.verification_outcomes != second.verification_outcomes
            or first.tested_claim_count != second.tested_claim_count
            or first.verified_claim_count != second.verified_claim_count
            or first.verification_evidence_count != second.verification_evidence_count
        ):
            raise SmokeFailure("workflow_not_deterministic")
        mismatch_rejections += int(
            asyncio.run(
                _assert_capability_procedure_mismatch(
                    arguments,
                    bundle=first.bundle,
                    negotiated_platform_capability=_CLI_PROCESS_CAPABILITY,
                    rejected_boundary="file-spool-event",
                )
            )
            == 0
        )
        mismatch_rejections += int(
            asyncio.run(
                _assert_capability_procedure_mismatch(
                    arguments,
                    bundle=first.bundle,
                    negotiated_platform_capability=_EVENT_CAPABILITY,
                    rejected_boundary="cli-process",
                )
            )
            == 0
        )
        if mismatch_rejections != 2:
            raise SmokeFailure("platform_mismatch_matrix_incomplete")
    finally:
        if _source_manifest(arguments.fixture) != before_source:
            raise SmokeFailure("fixture_source_changed_by_workflow")
        if (
            _hash_file(
                arguments.adapter,
                failure_prefix="adapter_executable",
            )
            != before_adapter
            or _hash_file(
                arguments.platform_fixture_executable,
                failure_prefix="platform_fixture_executable",
            )
            != before_platform
        ):
            raise SmokeFailure("external_executable_changed_by_workflow")
    return _RunResult(
        summary={
            "candidate_count": 1,
            "deterministic_sessions": 2,
            "mismatch_rejections": mismatch_rejections,
            "status": "PASS",
            "tested_claim_count": first.tested_claim_count,
            "verified_claim_count": first.verified_claim_count,
        },
        evidence=_build_evidence(before_source, first),
    )


def _build_evidence(
    source_manifest: dict[str, _FileIdentity],
    result: _WorkflowResult,
) -> dict[str, object]:
    return {
        "kind": "rel001_lane_evidence",
        "evidence_version": _EVIDENCE_VERSION,
        "lane": "go_platform",
        "status": "passed",
        "source": {
            "file_count": len(source_manifest),
            "byte_count": sum(
                identity.size for identity in source_manifest.values()
            ),
            "manifest_digest": _manifest_digest(source_manifest),
        },
        "deterministic": {
            "inventory": _parsed_resource(result.deterministic.inventory),
            "discovery": _parsed_resource(result.deterministic.discovery),
            "decisions": _parsed_resource(result.deterministic.decisions),
            "bundle": _parsed_resource(result.deterministic.bundle),
            "mapping": _parsed_resource(result.deterministic.mapping),
            "verification_requests": [
                _parsed_resource(result.deterministic.cli_request),
                _parsed_resource(result.deterministic.event_request),
            ],
        },
        "runtime": {
            "verification_results": [
                _parsed_resource(payload)
                for payload in result.runtime.verification_results
            ],
            "successor_behaviors": [
                _parsed_resource(payload)
                for payload in result.runtime.successor_behaviors
            ],
            "tested_trust": [
                _parsed_resource(payload) for payload in result.runtime.tested_trust
            ],
        },
        "metrics": {
            "inventory_record_count": _EXPECTED_INVENTORY_RECORD_COUNT,
            "candidate_count": 1,
            "dispositions": {
                "accepted": 1,
                "edited": 0,
                "rejected": 0,
                "uncertain": 0,
            },
            "eligible_interface_count": 9,
            "uncovered_interface_count": 8,
            "materialization_count": 1,
            "mapping_binding_count": 1,
            "tested_claim_count": result.tested_claim_count,
            "verified_claim_count": result.verified_claim_count,
            "verification_evidence_count": result.verification_evidence_count,
            "transports": ["cli", "event"],
        },
    }


def _parsed_resource(payload: bytes | str) -> dict[str, object]:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise SmokeFailure("evidence_resource_invalid") from error
    if type(parsed) is not dict:
        raise SmokeFailure("evidence_resource_invalid")
    return parsed


def _canonical_json_bytes(payload: object) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise SmokeFailure("evidence_serialization_failed") from error
    return (encoded + "\n").encode("ascii")


def _publish_evidence(path: Path, evidence: dict[str, object]) -> None:
    payload = _canonical_json_bytes(evidence)
    if len(payload) > _MAX_EVIDENCE_BYTES:
        raise SmokeFailure("evidence_output_too_large")
    if path.exists() or path.is_symlink():
        raise SmokeFailure("evidence_output_appeared")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise SmokeFailure("evidence_output_write_failed")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as error:
            raise SmokeFailure("evidence_output_appeared") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _emit(payload: dict[str, object], *, stream) -> None:
    stream.write(
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parse_arguments(sys.argv[1:] if argv is None else argv)
        result = _run(arguments)
        if arguments.evidence_output is not None:
            _publish_evidence(arguments.evidence_output, result.evidence)
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
        OnboardingValidationError,
        ValueError,
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
    _emit(result.summary, stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
