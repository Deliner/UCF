#!/usr/bin/env python3
"""Run the installed TypeScript/Fastify vertical slice outside the checkout."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

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
    canonical_execution_environment_digest,
    canonical_implementation_evidence_digest,
    canonical_implementation_evidence_json,
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
    IgnoreRule,
    InventoryPageRequest,
    InventoryRequest,
    PathSegmentMatcher,
    PublicInterfaceFact,
    RepositoryEntryFact,
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
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    Claim,
    TrustMapping,
)
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
    OnboardingValidationError,
    RejectedDecision,
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
        20,
        "58aea3d6b4b0f8799c1e00c3b023898516997f6369ee8e13d8d4b4215f70a62b",
    ),
    "README.md": (
        273,
        "a0ae43b15b5d77a7c96ebca7cd7c1a3c6d9a2dc2646a2416a6205b3da9a81067",
    ),
    "package-lock.json": (
        36_351,
        "45a07317fb5d806f665bf679a3c36fc88baeb2c0526391bb2f4186e1c5d88437",
    ),
    "package.json": (
        427,
        "b3695b7cf8f9c0d8a3214afdc6a4ba4ab91ac3085ae3258125c73e62e52c08f2",
    ),
    "src/service.test.ts": (
        1_749,
        "d100ffae4b66af1ac79955d90b1543828fc8339a457901ac6df2b66f05552ad2",
    ),
    "src/service.ts": (
        1_739,
        "508c7e86b39282b74514a55ffd1cd7854cfeb9653e0f062985d8a5b2008dadca",
    ),
    "tsconfig.json": (
        396,
        "d2c47f62b1f65baa2e79426368e8f330387504ed208ce7ecf7de75a851450586",
    ),
}
_EXPECTED_SOURCE_DIRECTORIES = frozenset({".", "src"})
_GENERATED_DIRECTORIES = frozenset({"dist", "node_modules"})
_SUBJECT_URI = "urn:ucf:repository:typescript-fastify-legacy-quote"
_SOURCE_REVISION = (
    "3edbe720c9cc3f47b2dfdd2283c94c13a954931c6d3cde7fdb95ec48b0646e9e"
)
_INVENTORY_DIGEST = (
    "a49ccfbef04fb96cefc2d5f91f3e584a752a675706e0ad6677dec9570cf4ad83"
)
_EXPECTED_INVENTORY_RECORD_COUNT = 42
_QUOTE_ROOT = "use-case.quote-order"
_QUOTE_SEMANTIC_DIGEST = (
    "cd09cf6ac27457ddbd62715ad903b4b3e0217c6b580cbde1d75c8d2c1b17153a"
)
_EXPECTED_CANDIDATE_ROOTS = frozenset(
    {
        "use-case.format-receipt",
        "use-case.legacy-discount-hint",
        "use-case.normalize-coupon",
        _QUOTE_ROOT,
    }
)
_EXPECTED_QUOTE_EVIDENCE = frozenset(
    {
        ("build_manifest", "package-lock.json"),
        ("build_manifest", "package.json"),
        ("build_manifest", "tsconfig.json"),
        ("public_interface", "POST /quote-order"),
        ("public_interface", "quoteOrder"),
    }
)
_ADAPTER_NAME = "org.ucf.adapter.typescript-fastify"
_ADAPTER_VERSION = "1.0.0"
_DISCOVERY_PROCEDURE_URI = (
    "urn:ucf:onboarding-procedure:"
    "typescript-fastify-static-discovery:1.0.0"
)
_MAPPING_PROCEDURE_URI = (
    "urn:ucf:adapter:typescript-fastify-static-mapping:1.0.0"
)
_VERIFICATION_PROCEDURE_URI = (
    "urn:ucf:adapter:"
    "typescript-fastify-real-http-verification:1.0.0"
)
_ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:node22-linux-loopback:1.0.0"
)
_ENVIRONMENT_REVISION = (
    "5c1cb86c391a5942088462fa2fe4e8a4deec768f6b37fd69027e37729555ce02"
)
_ENVIRONMENT_DIGEST = (
    "0d7174c8c09882285d8942bb93fe9c6623dc39affc1ce797a473b5a88f94f927"
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
_MAX_EVIDENCE_OUTPUT_BYTES = 16 * 1024 * 1024
_DETERMINISTIC_EVIDENCE_KEYS = frozenset(
    {
        "inventory",
        "discovery",
        "decisions",
        "bundle",
        "mapping",
        "verification_requests",
    }
)
_RUNTIME_EVIDENCE_KEYS = frozenset(
    {"verification_results", "successor_behaviors", "tested_trust"}
)
_METRIC_KEYS = frozenset(
    {
        "inventory_record_count",
        "candidate_count",
        "dispositions",
        "eligible_interface_count",
        "uncovered_interface_count",
        "materialization_count",
        "mapping_binding_count",
        "tested_claim_count",
        "verified_claim_count",
        "verification_evidence_count",
        "transports",
    }
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
    evidence_output: Path | None = None


@dataclass(frozen=True)
class _SourceFile:
    size: int
    digest: str


@dataclass(frozen=True)
class _WorkflowEvidence:
    deterministic: dict[str, object]
    runtime: dict[str, object]
    metrics: dict[str, object]


@dataclass(frozen=True)
class _WorkflowResult:
    source_revision: str
    semantic_digest: str
    behavior_root: str
    verification_outcome: str
    claim_level: str
    stderr_bytes: int
    evidence: _WorkflowEvidence | None = None


def _parse_arguments(argv: list[str]) -> _Arguments:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise an npm-installed TypeScript/Fastify adapter against "
            "a fresh external fixture."
        )
    )
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--evidence-output", type=Path)
    namespace = parser.parse_args(argv)
    evidence_output = (
        None
        if namespace.evidence_output is None
        else _new_evidence_output(namespace.evidence_output)
    )
    fixture = _external_directory(namespace.fixture)
    if (
        evidence_output is not None
        and evidence_output.parent.resolve(strict=True).is_relative_to(fixture)
    ):
        raise SmokeFailure("evidence_output_inside_fixture")
    return _Arguments(
        adapter=_external_file(namespace.adapter, executable=True),
        fixture=fixture,
        evidence_output=evidence_output,
    )


def _new_evidence_output(path: Path) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("evidence_output_not_absolute")
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(metadata.st_mode):
            raise SmokeFailure("evidence_output_is_symlink")
        raise SmokeFailure("evidence_output_exists")
    try:
        parent = path.parent.stat()
    except FileNotFoundError as error:
        raise SmokeFailure("evidence_output_parent_missing") from error
    if not stat.S_ISDIR(parent.st_mode):
        raise SmokeFailure("evidence_output_parent_not_directory")
    return path


def _external_file(path: Path, *, executable: bool) -> Path:
    if not path.is_absolute():
        raise SmokeFailure("argument_not_absolute")
    resolved = path.resolve(strict=True)
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


def _source_manifest(
    root: Path,
) -> dict[str, _SourceFile]:
    files: dict[str, _SourceFile] = {}
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
            relative = (
                entry.name if not prefix else f"{prefix}/{entry.name}"
            )
            if not prefix and entry.name in _GENERATED_DIRECTORIES:
                if not entry.is_dir(follow_symlinks=False):
                    raise SmokeFailure("generated_path_not_directory")
                continue
            if entry.is_symlink():
                raise SmokeFailure("fixture_source_symlink_rejected")
            if entry.is_dir(follow_symlinks=False):
                directories.add(relative)
                pending.append((Path(entry.path), relative))
                continue
            if not entry.is_file(follow_symlinks=False):
                raise SmokeFailure("fixture_source_type_rejected")
            files[relative] = _hash_source_file(Path(entry.path))
    if frozenset(files) != frozenset(_EXPECTED_SOURCE_MANIFEST):
        raise SmokeFailure("fixture_source_files_mismatch")
    if frozenset(directories) != _EXPECTED_SOURCE_DIRECTORIES:
        raise SmokeFailure("fixture_source_directories_mismatch")
    return files


def _hash_source_file(path: Path) -> _SourceFile:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise SmokeFailure("fixture_source_open_failed") from error
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SmokeFailure("fixture_source_type_rejected")
        while chunk := os.read(descriptor, 65_536):
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after:
        raise SmokeFailure("fixture_source_changed_during_hash")
    return _SourceFile(size=before.st_size, digest=digest.hexdigest())


def _canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _parsed_canonical_json(payload: str | bytes) -> object:
    return json.loads(payload)


def _lane_evidence(
    source_manifest: dict[str, _SourceFile],
    workflow: _WorkflowEvidence,
) -> dict[str, object]:
    if frozenset(workflow.deterministic) != _DETERMINISTIC_EVIDENCE_KEYS:
        raise SmokeFailure("deterministic_evidence_shape_mismatch")
    if frozenset(workflow.runtime) != _RUNTIME_EVIDENCE_KEYS:
        raise SmokeFailure("runtime_evidence_shape_mismatch")
    if frozenset(workflow.metrics) != _METRIC_KEYS:
        raise SmokeFailure("evidence_metrics_shape_mismatch")
    requests = workflow.deterministic["verification_requests"]
    if not isinstance(requests, list) or len(requests) != 1:
        raise SmokeFailure("deterministic_evidence_shape_mismatch")
    if any(
        not isinstance(items, list) or len(items) != 1
        for items in workflow.runtime.values()
    ):
        raise SmokeFailure("runtime_evidence_shape_mismatch")
    manifest_records = [
        {
            "path": path,
            "size": source_manifest[path].size,
            "digest": source_manifest[path].digest,
        }
        for path in sorted(source_manifest)
    ]
    source = {
        "file_count": len(manifest_records),
        "byte_count": sum(item.size for item in source_manifest.values()),
        "manifest_digest": hashlib.sha256(
            _canonical_json_bytes(manifest_records)
        ).hexdigest(),
    }
    return {
        "kind": "rel001_lane_evidence",
        "evidence_version": "1.0.0",
        "lane": "typescript_fastify",
        "status": "passed",
        "source": source,
        "deterministic": workflow.deterministic,
        "runtime": workflow.runtime,
        "metrics": workflow.metrics,
    }


def _assert_fixture_is_fresh(root: Path) -> None:
    if any(
        (root / name).exists() or (root / name).is_symlink()
        for name in _GENERATED_DIRECTORIES
    ):
        raise SmokeFailure("fixture_not_fresh")


def _build_fixture(root: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "npm_config_audit": "false",
            "npm_config_fund": "false",
            "npm_config_offline": "false",
            "npm_config_update_notifier": "false",
        }
    )
    for command, failure_code in (
        (
            (
                "npm",
                "ci",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ),
            "fixture_install_failed",
        ),
        (
            ("npm", "run", "build"),
            "fixture_build_failed",
        ),
        (
            ("npm", "test"),
            "fixture_test_failed",
        ),
    ):
        print(f"+ {shlex.join(command)}", flush=True)
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                start_new_session=os.name == "posix",
            )
        except OSError as error:
            raise SmokeFailure("fixture_build_start_failed") from error
        try:
            returncode = process.wait(timeout=120.0)
        except subprocess.TimeoutExpired as error:
            _terminate_build_process(process)
            raise SmokeFailure("fixture_build_timeout") from error
        except BaseException:
            _terminate_build_process(process)
            raise
        if returncode != 0:
            raise SmokeFailure(failure_code)


def _terminate_build_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        process.terminate()
    try:
        process.wait(timeout=1.0)
        return
    except subprocess.TimeoutExpired:
        pass
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()
    process.wait()


def _inventory_request() -> InventoryRequest:
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
            rules=(
                IgnoreRule(
                    kind="ignore_rule",
                    id="ignore.dist",
                    reason="org.ucf.inventory.generated",
                    matcher=PathSegmentMatcher(
                        kind="path_segment",
                        segment="dist",
                    ),
                ),
                IgnoreRule(
                    kind="ignore_rule",
                    id="ignore.node-modules",
                    reason="org.ucf.inventory.generated",
                    matcher=PathSegmentMatcher(
                        kind="path_segment",
                        segment="node_modules",
                    ),
                ),
            ),
        ),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=7,
            cursor=None,
        ),
    )


def _discovery_request(inventory) -> DiscoveryRequest:
    inventory_digest = hashlib.sha256(
        canonical_inventory_json(inventory)
    ).hexdigest()
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


def _quote_order_decisions(discovery) -> DecisionSet:
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
            name="org.ucf.installed-smoke-reviewer",
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
    decisions = []
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
        if candidate.proposal.root.target_id == _QUOTE_ROOT:
            decision = AcceptedDecision(
                kind="accepted_decision",
                reason="Accepted by the installed quote-order smoke.",
                **common,
            )
        else:
            decision = RejectedDecision(
                kind="rejected_decision",
                reason="Outside the installed quote-order smoke scope.",
                **common,
            )
        decisions.append(
            decision.model_copy(
                update={"id": derive_decision_id(decision, base)}
            )
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    decisions,
                    key=lambda item: item.candidate.candidate_id,
                )
            )
        }
    )


def _evidence_descriptors(
    references,
    *,
    inventory,
) -> frozenset[tuple[str, str]]:
    records_by_id = {record.id: record for record in inventory.records}
    descriptors: set[tuple[str, str]] = set()
    for reference in references:
        record = records_by_id.get(reference.target_id)
        if isinstance(record, BuildManifestFact):
            descriptor_kind = "build_manifest"
            name = _entry_path(record, records_by_id)
        elif isinstance(record, PublicInterfaceFact):
            descriptor_kind = "public_interface"
            name = record.name
        else:
            raise SmokeFailure("quote_evidence_kind_mismatch")
        descriptors.add((descriptor_kind, name))
    if len(descriptors) != len(references):
        raise SmokeFailure("quote_evidence_duplicate")
    return frozenset(descriptors)


def _entry_path(
    record: BuildManifestFact,
    records_by_id: dict[str, object],
) -> str:
    entry = records_by_id.get(record.entry.target_id)
    if not isinstance(entry, RepositoryEntryFact):
        raise SmokeFailure("quote_evidence_entry_mismatch")
    return entry.path


def _assert_baseline_has_no_promoted_claim(bundle) -> None:
    claims_by_level = {
        summary.level: summary.claim_ids
        for summary in bundle.baseline.claim_levels
    }
    if any(
        claims_by_level[level]
        for level in (
            ClaimLevel.MAPPED,
            ClaimLevel.TESTED,
            ClaimLevel.VERIFIED,
        )
    ):
        raise SmokeFailure("onboarding_claim_overpromoted")


def _mapping_request(bundle) -> ImplementationMappingRequest:
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


def _verification_request(mapping) -> ExecutionVerificationRequest:
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
        adapter_procedure_uri=_VERIFICATION_PROCEDURE_URI,
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
        environment=ExecutionEnvironment(
            kind="execution_environment",
            identity_uri=_ENVIRONMENT_IDENTITY_URI,
            revision=Digest(
                kind="digest",
                algorithm="sha-256",
                value=_ENVIRONMENT_REVISION,
            ),
        ),
        check=Check(
            kind="check",
            id="check.quote-order.real-http",
            version="1.0.0",
            procedure_uri=(
                "urn:ucf:fixture-check:"
                "quote-order-http-contract:1.0.0"
            ),
        ),
    )


async def _run_workflow(arguments: _Arguments) -> _WorkflowResult:
    capabilities = (
        CapabilityRequest(
            kind="capability_request",
            name=INVENTORY_CAPABILITY,
            minimum_version=INVENTORY_VERSION,
            required=True,
        ),
        CapabilityRequest(
            kind="capability_request",
            name=DISCOVERY_CAPABILITY,
            minimum_version=ONBOARDING_VERSION,
            required=True,
        ),
        CapabilityRequest(
            kind="capability_request",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        ),
        CapabilityRequest(
            kind="capability_request",
            name=EXECUTION_VERIFICATION_CAPABILITY,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        ),
    )
    adapter = AdapterProcess(
        command=(str(arguments.adapter),),
        cwd=arguments.fixture,
        requested_capabilities=capabilities,
        timeouts=_TIMEOUTS,
    )
    workflow_evidence = None
    try:
        initialized = await adapter.start()
        if (
            initialized.adapter.name != _ADAPTER_NAME
            or initialized.adapter.version != _ADAPTER_VERSION
        ):
            raise SmokeFailure("adapter_identity_mismatch")
        if adapter.negotiated_capabilities != {
            capability.name: capability.minimum_version
            for capability in capabilities
        }:
            raise SmokeFailure("adapter_capabilities_mismatch")

        inventory = await collect_inventory_from_process(
            adapter,
            request=_inventory_request(),
            operation_timeout=30.0,
        )
        if (
            inventory.inventory_version != INVENTORY_VERSION
            or inventory.schema_uri != INVENTORY_SCHEMA_URI
            or inventory.subject_uri != _SUBJECT_URI
            or inventory.source_revision.value != _SOURCE_REVISION
            or inventory.producer != initialized.adapter
            or len(inventory.records) != _EXPECTED_INVENTORY_RECORD_COUNT
            or hashlib.sha256(canonical_inventory_json(inventory)).hexdigest()
            != _INVENTORY_DIGEST
        ):
            raise SmokeFailure("inventory_identity_mismatch")

        discovery_request = _discovery_request(inventory)
        discovery_payload = await adapter.call(
            Method.DISCOVER,
            discovery_request_to_payload(discovery_request),
            timeout=30.0,
        )
        discovery = discovery_result_from_payload(discovery_payload)
        validate_discovery_exchange(discovery_request, discovery)
        if (
            discovery.producer != initialized.adapter
            or discovery.procedure_uri != _DISCOVERY_PROCEDURE_URI
            or len(discovery.candidates) != 4
            or {
                candidate.proposal.root.target_id
                for candidate in discovery.candidates
            }
            != _EXPECTED_CANDIDATE_ROOTS
        ):
            raise SmokeFailure("discovery_identity_mismatch")
        quote = [
            candidate
            for candidate in discovery.candidates
            if candidate.proposal.root.target_id == _QUOTE_ROOT
        ]
        if (
            len(quote) != 1
            or quote[0].semantic_digest.value != _QUOTE_SEMANTIC_DIGEST
            or _evidence_descriptors(
                quote[0].evidence,
                inventory=inventory,
            )
            != _EXPECTED_QUOTE_EVIDENCE
        ):
            raise SmokeFailure("quote_candidate_identity_mismatch")

        decisions = _quote_order_decisions(discovery)
        bundle = build_onboarding_bundle(
            inventory,
            discovery,
            decisions,
        )
        if (
            len(bundle.baseline.materializations) != 1
            or bundle.baseline.materializations[0].root.target_id
            != _QUOTE_ROOT
        ):
            raise SmokeFailure("review_materialization_mismatch")
        _assert_baseline_has_no_promoted_claim(bundle)

        mapping_request = _mapping_request(bundle)
        validate_implementation_mapping_request(
            mapping_request,
            bundle=bundle,
        )
        mapping_payload = await adapter.call(
            Method.MAP,
            implementation_mapping_request_to_payload(mapping_request),
            timeout=30.0,
        )
        mapping = implementation_mapping_result_from_payload(mapping_payload)
        validate_implementation_mapping_result(
            mapping,
            request=mapping_request,
            bundle=bundle,
            current_inventory=inventory,
            initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        if (
            mapping.producer != initialized.adapter
            or mapping.procedure_uri != _MAPPING_PROCEDURE_URI
            or len(mapping.bindings) != 1
            or mapping.bindings[0].behavior.target_id != _QUOTE_ROOT
            or mapping.bindings[0].source_records != quote[0].evidence
        ):
            raise SmokeFailure("mapping_identity_mismatch")

        await asyncio.to_thread(_build_fixture, arguments.fixture)
        verification_request = _verification_request(mapping)
        validate_execution_verification_request(
            verification_request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        verification_payload = await adapter.call(
            Method.VERIFY,
            execution_verification_request_to_payload(
                verification_request
            ),
            timeout=30.0,
        )
        verification = execution_verification_result_from_payload(
            verification_payload
        )
        validate_execution_verification_result(
            verification,
            request=verification_request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=initialized.adapter,
            initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        if (
            verification.outcome != "passed"
            or verification.producer != initialized.adapter
            or verification.procedure_uri != _VERIFICATION_PROCEDURE_URI
        ):
            raise SmokeFailure("verification_not_passed")

        projection = project_execution_verification(
            verification,
            request=verification_request,
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
        if len(claims) != 1 or claims[0].level is not ClaimLevel.TESTED:
            raise SmokeFailure("tested_claim_missing")
        if any(
            isinstance(record, TrustMapping)
            or isinstance(record, Claim)
            and record.level
            in {
                ClaimLevel.MAPPED,
                ClaimLevel.VERIFIED,
            }
            for record in projection.tested_trust.records
        ):
            raise SmokeFailure("claim_overpromoted")
        evidence = tuple(
            entity
            for entity in projection.successor_behavior.entities
            if isinstance(entity, VerificationEvidence)
        )
        if (
            len(evidence) != 1
            or evidence[0].outcome != "passed"
            or canonical_execution_environment_digest(
                verification_request.environment
            ).value
            != _ENVIRONMENT_DIGEST
        ):
            raise SmokeFailure("verification_evidence_mismatch")
        validate_trust_against_behavior(
            projection.tested_trust,
            projection.successor_behavior,
        )
        successor_behavior_json = canonical_ir_json(
            projection.successor_behavior
        )
        tested_trust_json = canonical_trust_ir_json(
            projection.tested_trust
        )
        if arguments.evidence_output is not None:
            dispositions = {
                summary.disposition.value: len(summary.candidate_ids)
                for summary in bundle.baseline.dispositions
            }
            workflow_evidence = _WorkflowEvidence(
                deterministic={
                    "inventory": _parsed_canonical_json(
                        canonical_inventory_json(inventory)
                    ),
                    "discovery": _parsed_canonical_json(
                        canonical_onboarding_json(discovery)
                    ),
                    "decisions": _parsed_canonical_json(
                        canonical_onboarding_json(decisions)
                    ),
                    "bundle": _parsed_canonical_json(
                        canonical_onboarding_json(bundle)
                    ),
                    "mapping": _parsed_canonical_json(
                        canonical_implementation_evidence_json(mapping)
                    ),
                    "verification_requests": [
                        _parsed_canonical_json(
                            canonical_implementation_evidence_json(
                                verification_request
                            )
                        )
                    ],
                },
                runtime={
                    "verification_results": [
                        _parsed_canonical_json(
                            canonical_implementation_evidence_json(
                                verification
                            )
                        )
                    ],
                    "successor_behaviors": [
                        _parsed_canonical_json(successor_behavior_json)
                    ],
                    "tested_trust": [
                        _parsed_canonical_json(tested_trust_json)
                    ],
                },
                metrics={
                    "inventory_record_count": len(inventory.records),
                    "candidate_count": len(discovery.candidates),
                    "dispositions": dispositions,
                    "eligible_interface_count": len(
                        discovery.coverage.eligible_subjects
                    ),
                    "uncovered_interface_count": len(
                        discovery.coverage.uncovered_subjects
                    ),
                    "materialization_count": len(
                        bundle.baseline.materializations
                    ),
                    "mapping_binding_count": len(mapping.bindings),
                    "tested_claim_count": sum(
                        claim.level is ClaimLevel.TESTED for claim in claims
                    ),
                    "verified_claim_count": sum(
                        claim.level is ClaimLevel.VERIFIED for claim in claims
                    ),
                    "verification_evidence_count": len(evidence),
                    "transports": ["http"],
                },
            )
    finally:
        await adapter.close()
    return _WorkflowResult(
        source_revision=inventory.source_revision.value,
        semantic_digest=quote[0].semantic_digest.value,
        behavior_root=mapping.bindings[0].behavior.target_id,
        verification_outcome=verification.outcome,
        claim_level=claims[0].level.value,
        stderr_bytes=adapter.stderr_total_bytes,
        evidence=workflow_evidence,
    )


def _run(arguments: _Arguments) -> dict[str, object] | None:
    _assert_installed_boundary()
    _assert_fixture_is_fresh(arguments.fixture)
    before = _source_manifest(arguments.fixture)
    expected = {
        path: _SourceFile(size=size, digest=digest)
        for path, (size, digest) in _EXPECTED_SOURCE_MANIFEST.items()
    }
    if before != expected:
        raise SmokeFailure("fixture_source_identity_mismatch")
    try:
        result = asyncio.run(_run_workflow(arguments))
    finally:
        if _source_manifest(arguments.fixture) != before:
            raise SmokeFailure("fixture_source_changed_by_workflow")
    if (
        result.source_revision != _SOURCE_REVISION
        or result.semantic_digest != _QUOTE_SEMANTIC_DIGEST
        or result.behavior_root != _QUOTE_ROOT
        or result.verification_outcome != "passed"
        or result.claim_level != ClaimLevel.TESTED.value
        or result.stderr_bytes != 0
    ):
        raise SmokeFailure("workflow_acceptance_mismatch")
    if arguments.evidence_output is None:
        return None
    if result.evidence is None:
        raise SmokeFailure("workflow_evidence_missing")
    return _lane_evidence(before, result.evidence)


def _path_entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _publish_evidence(
    destination: Path,
    evidence: dict[str, object],
) -> None:
    content = _canonical_json_bytes(evidence)
    if len(content) > _MAX_EVIDENCE_OUTPUT_BYTES:
        raise SmokeFailure("evidence_output_too_large")
    if _path_entry_exists(destination):
        raise SmokeFailure("evidence_output_appeared")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as error:
            raise SmokeFailure("evidence_output_appeared") from error
        temporary.unlink()
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        parent_descriptor = os.open(destination.parent, directory_flags)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


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
        arguments = _parse_arguments(
            sys.argv[1:] if argv is None else argv
        )
        evidence = _run(arguments)
        if arguments.evidence_output is not None:
            if evidence is None:
                raise SmokeFailure("workflow_evidence_missing")
            _publish_evidence(arguments.evidence_output, evidence)
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
    _emit({"status": "PASS"}, stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
