#!/usr/bin/env python3
"""Run the installed Go standard-library vertical slice outside the checkout."""

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
    DispositionKind,
    InventoryBinding,
    OnboardingValidationError,
    RejectedDecision,
    UncertainDecision,
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
        5,
        "aaccb1a00557171b31d00a99a6a2666856e417964732490685cdcba9f02de491",
    ),
    "README.md": (
        791,
        "c604b3077303764d4804cd25ab1c60d21ef5e8495eeb290e0d22177ba158e8f3",
    ),
    "cmd/server/main.go": (
        1_197,
        "3f321da079270a3de9884112025a1d91de7be0a303134bac024b49bb9dbfd66f",
    ),
    "go.mod": (
        63,
        "22df18de3163ccabe06ed8c4104f01c118d8827970652a65a12e1b5f90357d64",
    ),
    "quote/service.go": (
        2_081,
        "089be784fd41b88ee456e359615fa9d24b573564573321e5a76e836860e3888c",
    ),
    "quote/service_test.go": (
        2_555,
        "dc5494d4c248c8baee44b090dd079b8de4c2dc13b4ccc379244604ce158d7580",
    ),
}
_EXPECTED_SOURCE_DIRECTORIES = frozenset({".", "cmd", "cmd/server", "quote"})
_SUBJECT_URI = "urn:ucf:repository:go-stdlib-legacy-quote"
_SOURCE_REVISION = "8c95d059aef410657d42e4544d34935c5f422efa9394f1242ee858e02a1c3ff8"
_EXPECTED_INVENTORY_RECORD_COUNT = 51
_QUOTE_ROOT = "use-case.quote-order"
_EXPECTED_SEMANTIC_DIGESTS = {
    "use-case.format-receipt": (
        "ba7d915efbc19bff087cee325125b801f64d3d3f932db3df96a87d9dadf4569c"
    ),
    "use-case.legacy-discount-hint": (
        "d0182d40ad306dd41fef8090a3caca94ba491f30a5a1dc83a702dbd5f207f8b8"
    ),
    "use-case.normalize-coupon": (
        "d44419a028758d14eb1dfc5edc5d1c2b8d6fc1f1744fa6b17f063117d409261f"
    ),
    _QUOTE_ROOT: ("cd09cf6ac27457ddbd62715ad903b4b3e0217c6b580cbde1d75c8d2c1b17153a"),
}
_EXPECTED_QUOTE_EVIDENCE = frozenset(
    {
        ("build_manifest", "go.mod"),
        ("public_interface", "POST /quote-order"),
        ("public_interface", "QuoteOrder"),
        ("public_interface", "error"),
        ("public_interface", "http-response-write"),
        ("public_interface", "quantity"),
        ("public_interface", "quote.Handler.func1"),
        ("public_interface", "receipt"),
        ("public_interface", "total_cents"),
        ("public_interface", "unit_price_cents"),
    }
)
_EXPECTED_ELIGIBLE_INTERFACES = frozenset(
    {
        "FormatReceipt",
        "LegacyDiscountHint",
        "NormalizeCoupon",
        "POST /quote-order",
        "QuoteOrder",
        "error",
        "http-response-write",
        "quantity",
        "quote.Handler.func1",
        "receipt",
        "total_cents",
        "unit_price_cents",
    }
)
_EXPECTED_UNCOVERED_INTERFACES = frozenset(
    {
        "POST /quote-order",
        "error",
        "http-response-write",
        "quantity",
        "quote.Handler.func1",
        "receipt",
        "total_cents",
        "unit_price_cents",
    }
)
_EXPECTED_QUOTE_EVIDENCE_IDS = (
    "manifest.acddc0b88e089108d4fe55e43ea640944d76d7fbf8a59cb449333a7ec551f7d9",
    "interface.056d435e0562deb2a67e639c696626a97c18bf53830ab692651bc03d351641dd",
    "interface.4a642d5b9884d7ce0d0f3079c45dbb878e03c95ad9ae1ecf755f7a8d59898c15",
    "interface.55a7c03726f02436453f06448054aaa99d256a8fae66502dfa46bc5833062f19",
    "interface.7e4ec30e9019a778f0733b4aaa2aafff4724b0ee3d6bef2eea71fe969eeecc1b",
    "interface.807104d5a7d9e7372add983d9443a5f2db570edc0d3e59cc1d42a788c9b33ee0",
    "interface.c73d476f403c69a0b63b1ddeda4f3dace2631ea3626c6f5fce94540f83de6547",
    "interface.d165b3cdb55a9d06fc3a7430f8511967ab0f8790f8ae4de275096c3ed318b57f",
    "interface.d8d9c00f91bd132532935b73f374381bd6220d0a3885fffd0738eec3a9d82733",
    "interface.f7e8717de172c119c8c2fc82ecc98eb3f5d766dfb1d8a3f578299f63a7d363e6",
)
_ADAPTER_NAME = "org.ucf.adapter.go-stdlib"
_ADAPTER_VERSION = "1.0.0"
_DISCOVERY_PROCEDURE_URI = (
    "urn:ucf:onboarding-procedure:go-stdlib-static-discovery:1.0.0"
)
_MAPPING_PROCEDURE_URI = "urn:ucf:adapter:go-stdlib-static-mapping:1.0.0"
_EXPECTED_MAPPING_ID = (
    "mapping.1ac553e103d8a887e1fa971788cf6f32784ba81265498de5474353313f3274c6"
)
_VERIFICATION_PROCEDURE_URI = "urn:ucf:adapter:go-stdlib-real-http-verification:1.0.0"
_HTTP_LOOPBACK_CAPABILITY = "org.ucf.platform.http-loopback"
_ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:go1.26.5-linux-amd64-cgo0-loopback:1.0.0"
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
    fixture_executable: Path
    evidence_output: Path | None = None


@dataclass(frozen=True)
class _FileIdentity:
    size: int
    digest: str


@dataclass(frozen=True)
class _DeterministicArtifacts:
    inventory: bytes
    discovery: bytes
    decisions: bytes
    bundle: bytes
    mapping: bytes
    verification_request: bytes


@dataclass(frozen=True)
class _RuntimeArtifacts:
    verification_result: bytes
    successor_behavior: str
    tested_trust: str
    executed_at: str


@dataclass(frozen=True)
class _WorkflowResult:
    deterministic: _DeterministicArtifacts
    runtime: _RuntimeArtifacts
    source_revision: str
    semantic_digest: str
    behavior_root: str
    mapping_id: str
    mapping_source_record_ids: tuple[str, ...]
    verification_outcome: str
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
            "standard-library adapter and frozen legacy fixture."
        )
    )
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--fixture-executable", required=True, type=Path)
    parser.add_argument("--evidence-output", type=Path)
    namespace = parser.parse_args(argv)
    fixture = _external_directory(namespace.fixture)
    adapter = _external_file(namespace.adapter, executable=True)
    fixture_executable = _external_file(
        namespace.fixture_executable,
        executable=True,
    )
    if adapter.is_relative_to(fixture) or fixture_executable.is_relative_to(fixture):
        raise SmokeFailure("executable_inside_fixture_rejected")
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
        fixture_executable=fixture_executable,
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
                    b"ucf-eco002-go-review-policy:1.0.0\n"
                ).hexdigest(),
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
                reason=(
                    "Native Go tests and literal HTTP evidence match the "
                    "reviewed quote-order scope."
                ),
                **common,
            )
        elif candidate.proposal.root.target_id == "use-case.legacy-discount-hint":
            decision = UncertainDecision(
                kind="uncertain_decision",
                reason=(
                    "No executable evidence establishes the legacy hint as "
                    "intended behavior."
                ),
                **common,
            )
        else:
            decision = RejectedDecision(
                kind="rejected_decision",
                reason="Outside the reviewed quote-order acceptance scope.",
                **common,
            )
        decisions.append(
            decision.model_copy(update={"id": derive_decision_id(decision, base)})
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


def _interface_names(
    references,
    *,
    inventory,
) -> frozenset[str]:
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


def _assert_review(bundle, decisions) -> None:
    accepted = tuple(
        decision
        for decision in decisions.decisions
        if isinstance(decision, AcceptedDecision)
    )
    rejected = tuple(
        decision
        for decision in decisions.decisions
        if isinstance(decision, RejectedDecision)
    )
    uncertain = tuple(
        decision
        for decision in decisions.decisions
        if isinstance(decision, UncertainDecision)
    )
    if (
        len(decisions.decisions) != 4
        or len(accepted) != 1
        or len(rejected) != 2
        or len(uncertain) != 1
    ):
        raise SmokeFailure("explicit_review_disposition_mismatch")
    candidates_by_id = {
        candidate.id: candidate for candidate in bundle.discovery.candidates
    }
    roots_by_disposition = {
        DispositionKind.ACCEPTED: {
            candidates_by_id[decision.candidate.candidate_id].proposal.root.target_id
            for decision in accepted
        },
        DispositionKind.REJECTED: {
            candidates_by_id[decision.candidate.candidate_id].proposal.root.target_id
            for decision in rejected
        },
        DispositionKind.UNCERTAIN: {
            candidates_by_id[decision.candidate.candidate_id].proposal.root.target_id
            for decision in uncertain
        },
    }
    if (
        roots_by_disposition
        != {
            DispositionKind.ACCEPTED: {_QUOTE_ROOT},
            DispositionKind.REJECTED: {
                "use-case.format-receipt",
                "use-case.normalize-coupon",
            },
            DispositionKind.UNCERTAIN: {"use-case.legacy-discount-hint"},
        }
        or len(bundle.baseline.materializations) != 1
        or bundle.baseline.materializations[0].root.target_id != _QUOTE_ROOT
        or tuple(root.target_id for root in bundle.behavior.roots) != (_QUOTE_ROOT,)
        or bundle.baseline.discovery_status != "partial"
    ):
        raise SmokeFailure("review_materialization_mismatch")
    baseline_dispositions = {
        summary.disposition: frozenset(summary.candidate_ids)
        for summary in bundle.baseline.dispositions
    }
    if (
        baseline_dispositions[DispositionKind.ACCEPTED]
        != frozenset(decision.candidate.candidate_id for decision in accepted)
        or baseline_dispositions[DispositionKind.REJECTED]
        != frozenset(decision.candidate.candidate_id for decision in rejected)
        or baseline_dispositions[DispositionKind.UNCERTAIN]
        != frozenset(decision.candidate.candidate_id for decision in uncertain)
        or baseline_dispositions[DispositionKind.EDITED] != frozenset()
    ):
        raise SmokeFailure("review_effort_mismatch")
    claims_by_level = {
        summary.level: summary.claim_ids for summary in bundle.baseline.claim_levels
    }
    if (
        len(claims_by_level[ClaimLevel.OBSERVED]) != 1
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


def _execution_environment(arguments: _Arguments) -> ExecutionEnvironment:
    adapter = _hash_file(
        arguments.adapter,
        failure_prefix="adapter_executable",
    )
    fixture = _hash_file(
        arguments.fixture_executable,
        failure_prefix="fixture_executable",
    )

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
                "module_path": "example.com/legacyquotes",
                "digest": digest(fixture.digest),
                "size_bytes": fixture.size,
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
            "network": "loopback-only",
        },
        "source": {
            "kind": "source_identity",
            "subject_uri": _SUBJECT_URI,
            "source_revision": digest(_SOURCE_REVISION),
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
        identity_uri=_ENVIRONMENT_IDENTITY_URI,
        revision=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(encoded).hexdigest(),
        ),
    )


def _verification_request(
    mapping,
    *,
    environment: ExecutionEnvironment,
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
        environment=environment,
        check=Check(
            kind="check",
            id="check.quote-order.real-http",
            version="1.0.0",
            procedure_uri=("urn:ucf:fixture-check:quote-order-http-contract:1.0.0"),
        ),
    )


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
        CapabilityRequest(
            kind="capability_request",
            name=_HTTP_LOOPBACK_CAPABILITY,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        ),
    )
    adapter = AdapterProcess(
        command=(
            str(arguments.adapter),
            "--fixture-executable",
            str(arguments.fixture_executable),
        ),
        cwd=arguments.fixture,
        requested_capabilities=capabilities,
        timeouts=_TIMEOUTS,
    )
    try:
        initialized = await adapter.start()
        if (
            initialized.adapter.name != _ADAPTER_NAME
            or initialized.adapter.version != _ADAPTER_VERSION
        ):
            raise SmokeFailure("adapter_identity_mismatch")
        if adapter.negotiated_capabilities != {
            capability.name: capability.minimum_version for capability in capabilities
        }:
            raise SmokeFailure("adapter_capabilities_mismatch")

        inventory = await collect_inventory_from_process(
            adapter,
            request=_inventory_request(record_limit),
            operation_timeout=30.0,
        )
        if (
            inventory.inventory_version != INVENTORY_VERSION
            or inventory.schema_uri != INVENTORY_SCHEMA_URI
            or inventory.subject_uri != _SUBJECT_URI
            or inventory.source_revision.value != _SOURCE_REVISION
            or inventory.producer != initialized.adapter
            or len(inventory.records) != _EXPECTED_INVENTORY_RECORD_COUNT
        ):
            raise SmokeFailure("inventory_identity_mismatch")

        discovery_request = _discovery_request(inventory)
        discovery = discovery_result_from_payload(
            await adapter.call(
                Method.DISCOVER,
                discovery_request_to_payload(discovery_request),
                timeout=30.0,
            )
        )
        validate_discovery_exchange(discovery_request, discovery)
        candidates_by_root = {
            candidate.proposal.root.target_id: candidate
            for candidate in discovery.candidates
        }
        if (
            discovery.producer != initialized.adapter
            or discovery.procedure_uri != _DISCOVERY_PROCEDURE_URI
            or discovery.coverage.status != "partial"
            or len(discovery.candidates) != 4
            or {
                root: candidate.semantic_digest.value
                for root, candidate in candidates_by_root.items()
            }
            != _EXPECTED_SEMANTIC_DIGESTS
        ):
            raise SmokeFailure("discovery_identity_mismatch")
        if (
            _interface_names(
                discovery.coverage.eligible_subjects,
                inventory=inventory,
            )
            != _EXPECTED_ELIGIBLE_INTERFACES
            or _interface_names(
                discovery.coverage.uncovered_subjects,
                inventory=inventory,
            )
            != _EXPECTED_UNCOVERED_INTERFACES
            or len(discovery.coverage.eligible_subjects) != 12
            or len(discovery.coverage.uncovered_subjects) != 8
        ):
            raise SmokeFailure("discovery_coverage_mismatch")
        quote = candidates_by_root[_QUOTE_ROOT]
        if (
            len(quote.evidence) != 10
            or tuple(reference.target_id for reference in quote.evidence)
            != _EXPECTED_QUOTE_EVIDENCE_IDS
            or _evidence_descriptors(quote.evidence, inventory=inventory)
            != _EXPECTED_QUOTE_EVIDENCE
        ):
            raise SmokeFailure("quote_candidate_identity_mismatch")

        decisions = _quote_order_decisions(discovery)
        bundle = build_onboarding_bundle(
            inventory,
            discovery,
            decisions,
        )
        _assert_review(bundle, decisions)

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
            or mapping.id != _EXPECTED_MAPPING_ID
            or mapping.producer != initialized.adapter
            or mapping.procedure_uri != _MAPPING_PROCEDURE_URI
            or len(mapping.bindings) != 1
            or mapping.bindings[0].behavior.target_id != _QUOTE_ROOT
            or mapping.bindings[0].source_records != quote.evidence
            or len(mapping.bindings[0].source_records) != 10
        ):
            raise SmokeFailure("mapping_identity_mismatch")

        verification_request = _verification_request(
            mapping,
            environment=_execution_environment(arguments),
        )
        validate_execution_verification_request(
            verification_request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=initialized.adapter,
            negotiated_capabilities=adapter.negotiated_capabilities,
        )
        verification = execution_verification_result_from_payload(
            await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(verification_request),
                timeout=30.0,
            )
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
            verification.status != "completed"
            or verification.outcome != "passed"
            or verification.producer != initialized.adapter
            or verification.procedure_uri != _VERIFICATION_PROCEDURE_URI
            or not _is_whole_second_timestamp(verification.executed_at)
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
        tested_claims = tuple(
            claim for claim in claims if claim.level is ClaimLevel.TESTED
        )
        verified_claims = tuple(
            claim for claim in claims if claim.level is ClaimLevel.VERIFIED
        )
        if (
            len(tested_claims) != 1
            or verified_claims
            or any(
                isinstance(record, TrustMapping)
                or isinstance(record, Claim)
                and record.level is ClaimLevel.MAPPED
                for record in projection.tested_trust.records
            )
        ):
            raise SmokeFailure("claim_projection_mismatch")
        evidence = tuple(
            entity
            for entity in projection.successor_behavior.entities
            if isinstance(entity, VerificationEvidence)
        )
        if len(evidence) != 1 or evidence[0].outcome != "passed":
            raise SmokeFailure("verification_evidence_mismatch")
        validate_trust_against_behavior(
            projection.tested_trust,
            projection.successor_behavior,
        )
        canonical_ir_json(projection.successor_behavior)
        canonical_trust_ir_json(projection.tested_trust)
    finally:
        await adapter.close()
    return _WorkflowResult(
        deterministic=_DeterministicArtifacts(
            inventory=canonical_inventory_json(inventory),
            discovery=canonical_onboarding_json(discovery),
            decisions=canonical_onboarding_json(decisions),
            bundle=canonical_onboarding_json(bundle),
            mapping=canonical_implementation_evidence_json(mapping),
            verification_request=canonical_implementation_evidence_json(
                verification_request
            ),
        ),
        runtime=_RuntimeArtifacts(
            verification_result=canonical_implementation_evidence_json(verification),
            successor_behavior=canonical_ir_json(projection.successor_behavior),
            tested_trust=canonical_trust_ir_json(projection.tested_trust),
            executed_at=verification.executed_at,
        ),
        source_revision=inventory.source_revision.value,
        semantic_digest=quote.semantic_digest.value,
        behavior_root=mapping.bindings[0].behavior.target_id,
        mapping_id=mapping.id,
        mapping_source_record_ids=tuple(
            reference.target_id for reference in mapping.bindings[0].source_records
        ),
        verification_outcome=verification.outcome,
        tested_claim_count=len(tested_claims),
        verified_claim_count=len(verified_claims),
        verification_evidence_count=len(evidence),
        stderr_bytes=adapter.stderr_total_bytes,
    )


def _assert_workflow_acceptance(result: _WorkflowResult) -> None:
    if (
        result.source_revision != _SOURCE_REVISION
        or result.semantic_digest != _EXPECTED_SEMANTIC_DIGESTS[_QUOTE_ROOT]
        or result.behavior_root != _QUOTE_ROOT
        or result.mapping_id != _EXPECTED_MAPPING_ID
        or result.mapping_source_record_ids != _EXPECTED_QUOTE_EVIDENCE_IDS
        or result.verification_outcome != "passed"
        or result.tested_claim_count != 1
        or result.verified_claim_count != 0
        or result.verification_evidence_count != 1
        or result.stderr_bytes != 0
        or not result.runtime.verification_result
        or not result.runtime.successor_behavior
        or not result.runtime.tested_trust
        or not _is_whole_second_timestamp(result.runtime.executed_at)
    ):
        raise SmokeFailure("workflow_acceptance_mismatch")


def _run(arguments: _Arguments) -> _RunResult:
    _assert_installed_boundary()
    expected = {
        path: _FileIdentity(size=size, digest=digest)
        for path, (size, digest) in _EXPECTED_SOURCE_MANIFEST.items()
    }
    before_source = _source_manifest(arguments.fixture)
    if before_source != expected:
        raise SmokeFailure("fixture_source_identity_mismatch")
    before_adapter = _hash_file(
        arguments.adapter,
        failure_prefix="adapter_executable",
    )
    before_fixture_executable = _hash_file(
        arguments.fixture_executable,
        failure_prefix="fixture_executable",
    )
    try:
        first = asyncio.run(_run_workflow(arguments, record_limit=7))
        _assert_workflow_acceptance(first)
        if _source_manifest(arguments.fixture) != before_source:
            raise SmokeFailure("fixture_source_changed_by_first_workflow")
        second = asyncio.run(_run_workflow(arguments, record_limit=1))
        _assert_workflow_acceptance(second)
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
                arguments.fixture_executable,
                failure_prefix="fixture_executable",
            )
            != before_fixture_executable
        ):
            raise SmokeFailure("external_executable_changed_by_workflow")
    if (
        first.deterministic != second.deterministic
        or first.mapping_id != second.mapping_id
        or first.mapping_source_record_ids != second.mapping_source_record_ids
        or first.verification_outcome != second.verification_outcome
        or first.tested_claim_count != second.tested_claim_count
        or first.verified_claim_count != second.verified_claim_count
        or first.verification_evidence_count != second.verification_evidence_count
    ):
        raise SmokeFailure("workflow_not_deterministic")
    return _RunResult(
        summary={"status": "PASS"},
        evidence=_build_evidence(before_source, first),
    )


def _build_evidence(
    source_manifest: dict[str, _FileIdentity],
    result: _WorkflowResult,
) -> dict[str, object]:
    return {
        "kind": "rel001_lane_evidence",
        "evidence_version": _EVIDENCE_VERSION,
        "lane": "go_http",
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
                _parsed_resource(result.deterministic.verification_request)
            ],
        },
        "runtime": {
            "verification_results": [
                _parsed_resource(result.runtime.verification_result)
            ],
            "successor_behaviors": [
                _parsed_resource(result.runtime.successor_behavior)
            ],
            "tested_trust": [_parsed_resource(result.runtime.tested_trust)],
        },
        "metrics": {
            "inventory_record_count": _EXPECTED_INVENTORY_RECORD_COUNT,
            "candidate_count": 4,
            "dispositions": {
                "accepted": 1,
                "edited": 0,
                "rejected": 2,
                "uncertain": 1,
            },
            "eligible_interface_count": 12,
            "uncovered_interface_count": 8,
            "materialization_count": 1,
            "mapping_binding_count": 1,
            "tested_claim_count": result.tested_claim_count,
            "verified_claim_count": result.verified_claim_count,
            "verification_evidence_count": result.verification_evidence_count,
            "transports": ["http"],
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
