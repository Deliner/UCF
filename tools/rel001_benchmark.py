"""Compile and validate the non-normative REL-001 release benchmark report."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import statistics
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn

import ucf
from ucf.adapter_conformance import CONFORMANCE_KIT_VERSION
from ucf.adapter_protocol import ADAPTER_PROTOCOL_VERSION, CapabilitySelection
from ucf.change_lifecycle import (
    CHANGE_LIFECYCLE_VERSION,
    CHANGE_PROPOSAL_SCHEMA_URI,
    OPENSPEC_INTEROP_PROFILE,
    OPENSPEC_TESTED_AGAINST_VERSION,
    ChangeProposal,
    ExecutionEvidenceContext,
    OpenSpecArtifact,
    OpenSpecArtifactRole,
    OpenSpecManifest,
    canonical_change_lifecycle_json,
    complete_change_task,
    delta_subject_ref,
    derive_archive_record,
    derive_behavior_delta,
    derive_implementation_record,
    derive_task_graph,
    derive_verification_record,
    validate_archive_record,
    validate_behavior_delta,
    validate_change_proposal,
    validate_implementation_record,
    validate_task_graph,
    validate_verification_record,
)
from ucf.evidence_status import (
    EvidenceStatus,
    assess_verification_evidence,
    canonical_evidence_status_json,
    record_verification_evidence,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    canonical_implementation_evidence_json,
    parse_execution_verification_request_json,
    parse_execution_verification_result_json,
    parse_implementation_mapping_result_json,
    project_execution_verification,
    validate_execution_verification_result,
    validate_implementation_mapping_result,
)
from ucf.inventory import (
    canonical_inventory_json,
    parse_inventory_snapshot_json,
)
from ucf.ir import (
    canonical_ir_json,
    canonical_trust_ir_json,
    parse_ir_json,
    parse_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import Digest, Producer
from ucf.ir.trust_models import BehaviorDocumentRef, Claim, ClaimLevel
from ucf.onboarding import (
    canonical_onboarding_json,
    parse_decision_set_json,
    parse_discovery_result_json,
    parse_onboarding_bundle_json,
    validate_onboarding_bundle,
)
from ucf.ratchet.v2 import (
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetPolicy,
    RatchetRule,
    build_ratchet_assessment,
    canonical_ratchet_json,
    derive_policy_id,
    establish_ratchet_baseline,
    evaluate_ratchet,
)

REPORT_VERSION = "1.0.0"
_REPORT_KEYS = frozenset(
    {
        "kind",
        "report_version",
        "status",
        "identities",
        "structural",
        "runtime",
        "overhead",
        "change_lifecycle",
        "limitations",
    }
)
_IDENTITY_KEYS = frozenset(
    {
        "ucf_version",
        "python_version",
        "python_implementation",
        "adapter_protocol_version",
        "adapter_conformance_kit_version",
        "ratchet_version",
        "repetitions",
        "wheel_sha256",
        "runtime_lock_sha256",
        "installed_environment_sha256",
        "installed_distributions",
        "host_platform",
        "adapters",
        "adapter_artifact_digests",
        "driver_artifact_digests",
        "benchmark_tool_digests",
        "conformance_report_digests",
        "toolchains",
    }
)
_SOURCE_KEYS = frozenset({"file_count", "byte_count", "manifest_digest"})
_DISPOSITION_KEYS = frozenset({"accepted", "edited", "rejected", "uncertain"})
_COVERAGE_KEYS = frozenset(
    {
        "eligible_interface_count",
        "uncovered_interface_count",
        "unresolved_debt_count",
    }
)
_CLAIM_KEYS = frozenset(
    {
        "observed",
        "declared",
        "mapped",
        "tested",
        "verified",
        "fresh_evidence",
        "stale_evidence",
    }
)
_RATCHET_KEYS = frozenset(
    {"baseline_outcome", "unchanged_outcome", "coverage_debt_count"}
)
_COMPONENT_KEYS = frozenset(
    {
        "id",
        "source",
        "inventory_record_count",
        "candidate_count",
        "false_candidate_count",
        "dispositions",
        "coverage",
        "materialization_count",
        "mapping_binding_count",
        "review_actions",
        "claims",
        "ratchet",
        "transports",
        "structural_digest",
    }
)
_TOTAL_KEYS = frozenset(
    {
        "source_file_count",
        "source_byte_count",
        "inventory_record_count",
        "candidate_count",
        "false_candidate_count",
        "candidate_decision_count",
        "ambiguity_resolution_count",
        "mapping_approval_count",
        "change_approval_count",
        "eligible_interface_count",
        "uncovered_interface_count",
        "unresolved_debt_count",
        "materialization_count",
        "mapping_binding_count",
        "tested_claim_count",
        "verified_claim_count",
        "fresh_evidence_count",
        "stale_evidence_count",
    }
)
_LIFECYCLE_KEYS = frozenset(
    {
        "ecosystem",
        "change_id",
        "delta_entry_count",
        "scripted_task_completion_count",
        "implementation_evidence_count",
        "verification_evidence_count",
        "tested_claim_count",
        "verified_claim_count",
        "change_approval_count",
        "status",
        "structural_digest",
    }
)
_EXPECTED_COMPONENTS = {
    "python": ("python_legacy_quote",),
    "typescript_fastify": ("typescript_fastify_legacy_quote",),
    "go": ("go_stdlib_legacy_quote", "go_stdlib_legacy_platforms"),
}
_EXPECTED_COMPONENT_TRANSPORTS = {
    "python_legacy_quote": (),
    "typescript_fastify_legacy_quote": ("http",),
    "go_stdlib_legacy_quote": ("http",),
    "go_stdlib_legacy_platforms": ("cli", "event"),
}
_EXPECTED_ADAPTERS = {
    "python": "org.ucf.inventory-reference-adapter@1.0.0",
    "typescript_fastify": "org.ucf.adapter.typescript-fastify@1.0.0",
    "go": "org.ucf.adapter.go-stdlib@1.0.0",
}
_EXPECTED_TOOLCHAINS = {
    "node": "v22.22.3",
    "npm": "10.9.8",
    "go": "go1.26.5 linux/amd64",
}
_EXPECTED_HOST_PLATFORM = {"system": "Linux", "architecture": "x86_64"}
_RUNTIME_PHASE_NAMES = (
    "copy_source",
    "manifest_recheck",
    "native_post",
    "native_pre",
    "workflow",
)
_EXPECTED_RUNTIME_PHASES = tuple(
    (lane, phase)
    for lane in ("go_http", "go_platform", "python", "typescript_fastify")
    for phase in _RUNTIME_PHASE_NAMES
)
_PROCEDURE_TRANSPORTS = {
    "urn:ucf:adapter:python-reference-native-check-verification:1.0.0": None,
    "urn:ucf:adapter:typescript-fastify-real-http-verification:1.0.0": "http",
    "urn:ucf:adapter:go-stdlib-real-http-verification:1.0.0": "http",
    "urn:ucf:adapter:go-stdlib-real-cli-verification:1.0.0": "cli",
    "urn:ucf:adapter:go-stdlib-file-spool-event-verification:1.0.0": "event",
}
_OVERHEAD_ACCOUNTING_VERSION = "1.0.0"
_OVERHEAD_DEFINITIONS = {
    "authored_bytes": (
        "Canonical bytes of explicit decisions, policy, and change proposal "
        "resources."
    ),
    "derived_bytes": "Canonical bytes of generated UCF resources and evidence.",
    "record_count": "One count per top-level canonical resource.",
    "allocation": (
        "Fixture resources are allocated to their component; shared policy and "
        "lifecycle resources remain separate."
    ),
}
_ALLOWED_TRANSPORTS = frozenset({"http", "cli", "event"})
_HEX_DIGITS = frozenset("0123456789abcdef")
_POSIX_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9:])/(?!/)[^\s,;]+")
_WINDOWS_PATH_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:[\\/]|\\\\)[^\s,;]+"
)


class BenchmarkValidationError(ValueError):
    """One closed benchmark report contract violation."""

    def __init__(self, code: str, message: str, *, location: str) -> None:
        super().__init__(f"{message} at {location}")
        self.code = code
        self.location = location


def _fail(code: str, message: str, *, location: str) -> NoReturn:
    raise BenchmarkValidationError(code, message, location=location)


def _canonical_json_bytes(value: object) -> bytes:
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


def derive_structural_digest(structural: Mapping[str, object]) -> str:
    """Return the digest of the deterministic section excluding its digest."""

    projected = dict(structural)
    projected.pop("digest", None)
    return hashlib.sha256(_canonical_json_bytes(projected)).hexdigest()


def canonical_report_json(payload: Mapping[str, object]) -> bytes:
    """Validate and encode one exact canonical REL-001 report."""

    normalized = dict(payload)
    _validate_report(normalized)
    return _canonical_json_bytes(normalized)


def parse_report_json(content: str | bytes) -> dict[str, object]:
    """Parse an exact canonical report while rejecting duplicate fields."""

    try:
        text = content.decode("ascii") if isinstance(content, bytes) else content
    except UnicodeDecodeError:
        _fail("invalid_json", "report must be canonical ASCII JSON", location="$")
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except BenchmarkValidationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError):
        _fail("invalid_json", "report is not valid JSON", location="$")
    if not isinstance(payload, dict):
        _fail("invalid_type", "report root must be an object", location="$")
    _validate_report(payload)
    if text.encode("ascii") != _canonical_json_bytes(payload):
        _fail(
            "noncanonical_json",
            "report bytes are not exact canonical JSON",
            location="$",
        )
    return payload


def verify_published_report(
    accepted: Mapping[str, object],
    fresh: Mapping[str, object],
) -> None:
    """Require exact replay of every non-duration release-evidence section."""

    accepted_report = dict(accepted)
    fresh_report = dict(fresh)
    _validate_report(accepted_report)
    _validate_report(fresh_report)
    accepted_projection = {
        key: value for key, value in accepted_report.items() if key != "runtime"
    }
    fresh_projection = {
        key: value for key, value in fresh_report.items() if key != "runtime"
    }
    if fresh_projection != accepted_projection:
        _fail(
            "published_report_drift",
            "fresh installed replay differs from checked release evidence",
            location="$",
        )


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(
                "duplicate_field",
                "report contains a duplicate object field",
                location=f"$.{key}",
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    _fail(
        "invalid_json",
        f"non-finite JSON number is forbidden: {value}",
        location="$",
    )


def _validate_report(report: dict[str, object]) -> None:
    _exact_keys(report, _REPORT_KEYS, location="$")
    if report["kind"] != "rel001_benchmark_report":
        _fail("unsupported_kind", "unexpected report kind", location="$.kind")
    if report["report_version"] != REPORT_VERSION:
        _fail(
            "unsupported_version",
            "unexpected report version",
            location="$.report_version",
        )
    if report["status"] != "passed":
        _fail("invalid_status", "accepted report must pass", location="$.status")
    _reject_path_leaks(report, location="$")

    identities = _object(report["identities"], location="$.identities")
    repetitions = _validate_identities(identities)
    structural = _object(report["structural"], location="$.structural")
    components = _validate_structural(structural)
    _validate_runtime(report["runtime"], repetitions=repetitions)
    _validate_overhead(report["overhead"], components=components)
    _validate_lifecycle(report["change_lifecycle"])
    _validate_limitations(report["limitations"])

    transports = {
        transport for component in components for transport in component["transports"]
    }
    if transports != _ALLOWED_TRANSPORTS:
        _fail(
            "summary_mismatch",
            "HTTP, CLI, and event evidence must all be present",
            location="$.structural.ecosystems",
        )


def _validate_identities(identities: dict[str, object]) -> int:
    _exact_keys(identities, _IDENTITY_KEYS, location="$.identities")
    for key in ("ucf_version", "python_version", "python_implementation"):
        _nonempty_string(identities[key], location=f"$.identities.{key}")
    expected_versions = {
        "ucf_version": ucf.__version__,
        "python_implementation": "CPython",
        "adapter_protocol_version": ADAPTER_PROTOCOL_VERSION,
        "adapter_conformance_kit_version": CONFORMANCE_KIT_VERSION,
        "ratchet_version": RATCHET_VERSION,
    }
    for key, expected in expected_versions.items():
        if identities[key] != expected:
            _fail(
                "unsupported_version",
                f"benchmark requires {key} {expected!r}",
                location=f"$.identities.{key}",
            )
    repetitions = _nonnegative_integer(
        identities["repetitions"],
        location="$.identities.repetitions",
    )
    if repetitions < 3:
        _fail(
            "insufficient_repetitions",
            "benchmark requires at least three repetitions",
            location="$.identities.repetitions",
        )
    _sha256(identities["wheel_sha256"], location="$.identities.wheel_sha256")
    _sha256(
        identities["runtime_lock_sha256"],
        location="$.identities.runtime_lock_sha256",
    )
    installed_environment_sha256 = _sha256(
        identities["installed_environment_sha256"],
        location="$.identities.installed_environment_sha256",
    )
    distributions = _object(
        identities["installed_distributions"],
        location="$.identities.installed_distributions",
    )
    if not distributions:
        _fail(
            "missing_field",
            "installed distribution identities are required",
            location="$.identities.installed_distributions",
        )
    normalized_distributions: dict[str, str] = {}
    for name, version in distributions.items():
        normalized_name = _nonempty_string(
            name,
            location="$.identities.installed_distributions",
        )
        normalized_distributions[normalized_name] = _nonempty_string(
            version,
            location=f"$.identities.installed_distributions.{name}",
        )
    if normalized_distributions.get("ucf") != identities["ucf_version"]:
        _fail(
            "identity_mismatch",
            "installed UCF distribution differs from the report version",
            location="$.identities.installed_distributions.ucf",
        )
    if installed_environment_sha256 != _object_digest(normalized_distributions):
        _fail(
            "identity_mismatch",
            "installed distribution digest differs from its exact coordinates",
            location="$.identities.installed_environment_sha256",
        )
    host_platform = _object(
        identities["host_platform"],
        location="$.identities.host_platform",
    )
    _exact_keys(
        host_platform,
        frozenset(_EXPECTED_HOST_PLATFORM),
        location="$.identities.host_platform",
    )
    if host_platform != _EXPECTED_HOST_PLATFORM:
        _fail(
            "unsupported_platform",
            "REL-001 release evidence requires exact Linux/x86_64",
            location="$.identities.host_platform",
        )
    adapters = _object(identities["adapters"], location="$.identities.adapters")
    _exact_keys(
        adapters,
        frozenset({"python", "typescript_fastify", "go"}),
        location="$.identities.adapters",
    )
    if adapters != _EXPECTED_ADAPTERS:
        _fail(
            "identity_mismatch",
            "adapter coordinates differ from the accepted benchmark lanes",
            location="$.identities.adapters",
        )
    for field in (
        "adapter_artifact_digests",
        "conformance_report_digests",
    ):
        digests = _object(identities[field], location=f"$.identities.{field}")
        _exact_keys(
            digests,
            frozenset({"python", "typescript_fastify", "go"}),
            location=f"$.identities.{field}",
        )
        for key, value in digests.items():
            _sha256(value, location=f"$.identities.{field}.{key}")
    driver_digests = _object(
        identities["driver_artifact_digests"],
        location="$.identities.driver_artifact_digests",
    )
    _exact_keys(
        driver_digests,
        frozenset(_LANE_COMPONENTS),
        location="$.identities.driver_artifact_digests",
    )
    for key, value in driver_digests.items():
        _sha256(value, location=f"$.identities.driver_artifact_digests.{key}")
    tool_digests = _object(
        identities["benchmark_tool_digests"],
        location="$.identities.benchmark_tool_digests",
    )
    _exact_keys(
        tool_digests,
        frozenset(
            {
                "compiler",
                "scenarios",
                "go_adapter_contract",
                "go_platform_contract",
                "go_toolchain",
                "typescript_contract",
            }
        ),
        location="$.identities.benchmark_tool_digests",
    )
    for key, value in tool_digests.items():
        _sha256(value, location=f"$.identities.benchmark_tool_digests.{key}")
    toolchains = _object(identities["toolchains"], location="$.identities.toolchains")
    _exact_keys(
        toolchains,
        frozenset({"node", "npm", "go"}),
        location="$.identities.toolchains",
    )
    if toolchains != _EXPECTED_TOOLCHAINS:
        _fail(
            "unsupported_version",
            "benchmark toolchains differ from the accepted release profile",
            location="$.identities.toolchains",
        )
    return repetitions


def _validate_structural(
    structural: dict[str, object],
) -> list[dict[str, object]]:
    _exact_keys(
        structural,
        frozenset({"ecosystems", "totals", "digest"}),
        location="$.structural",
    )
    ecosystems = _array(structural["ecosystems"], location="$.structural.ecosystems")
    if len(ecosystems) != len(_EXPECTED_COMPONENTS):
        _fail(
            "summary_mismatch",
            "report must contain exactly three ecosystems",
            location="$.structural.ecosystems",
        )
    components: list[dict[str, object]] = []
    for index, (ecosystem_value, expected) in enumerate(
        zip(ecosystems, _EXPECTED_COMPONENTS.items(), strict=True)
    ):
        ecosystem = _object(
            ecosystem_value,
            location=f"$.structural.ecosystems[{index}]",
        )
        location = f"$.structural.ecosystems[{index}]"
        _exact_keys(
            ecosystem,
            frozenset({"id", "components"}),
            location=location,
        )
        expected_ecosystem, expected_components = expected
        if ecosystem["id"] != expected_ecosystem:
            _fail(
                "summary_mismatch",
                "ecosystem order or identity differs",
                location=f"{location}.id",
            )
        values = _array(ecosystem["components"], location=f"{location}.components")
        if len(values) != len(expected_components):
            _fail(
                "summary_mismatch",
                "ecosystem component count differs",
                location=f"{location}.components",
            )
        for component_index, (value, component_id) in enumerate(
            zip(values, expected_components, strict=True)
        ):
            component = _object(
                value,
                location=f"{location}.components[{component_index}]",
            )
            _validate_component(
                component,
                expected_id=component_id,
                location=f"{location}.components[{component_index}]",
            )
            components.append(component)
    totals = _object(structural["totals"], location="$.structural.totals")
    _validate_totals(totals, components)
    digest = _sha256(structural["digest"], location="$.structural.digest")
    if digest != derive_structural_digest(structural):
        _fail(
            "structural_digest_mismatch",
            "structural digest does not match deterministic content",
            location="$.structural.digest",
        )
    return components


def _validate_component(
    component: dict[str, object],
    *,
    expected_id: str,
    location: str,
) -> None:
    _exact_keys(component, _COMPONENT_KEYS, location=location)
    if component["id"] != expected_id:
        _fail(
            "summary_mismatch",
            "component identity differs",
            location=f"{location}.id",
        )
    source = _object(component["source"], location=f"{location}.source")
    _exact_keys(source, _SOURCE_KEYS, location=f"{location}.source")
    _positive_integer(source["file_count"], location=f"{location}.source.file_count")
    _positive_integer(source["byte_count"], location=f"{location}.source.byte_count")
    _sha256(source["manifest_digest"], location=f"{location}.source.manifest_digest")

    counts = {}
    for key in (
        "inventory_record_count",
        "candidate_count",
        "false_candidate_count",
        "materialization_count",
        "mapping_binding_count",
    ):
        counts[key] = _nonnegative_integer(component[key], location=f"{location}.{key}")
    dispositions = _object(
        component["dispositions"], location=f"{location}.dispositions"
    )
    _exact_keys(dispositions, _DISPOSITION_KEYS, location=f"{location}.dispositions")
    disposition_counts = {
        key: _nonnegative_integer(value, location=f"{location}.dispositions.{key}")
        for key, value in dispositions.items()
    }
    if counts["candidate_count"] != sum(disposition_counts.values()):
        _fail(
            "summary_mismatch",
            "candidate dispositions do not cover every candidate",
            location=f"{location}.dispositions",
        )
    if counts["false_candidate_count"] != (
        disposition_counts["edited"] + disposition_counts["rejected"]
    ):
        _fail(
            "summary_mismatch",
            "false candidate count differs from edited plus rejected",
            location=f"{location}.false_candidate_count",
        )
    if counts["materialization_count"] != (
        disposition_counts["accepted"] + disposition_counts["edited"]
    ):
        _fail(
            "summary_mismatch",
            "materializations differ from accepted plus edited decisions",
            location=f"{location}.materialization_count",
        )

    review_actions = _object(
        component["review_actions"],
        location=f"{location}.review_actions",
    )
    _exact_keys(
        review_actions,
        frozenset(
            {
                "candidate_decision_count",
                "ambiguity_resolution_count",
                "mapping_approval_count",
            }
        ),
        location=f"{location}.review_actions",
    )
    observed_review_actions = {
        key: _nonnegative_integer(value, location=f"{location}.review_actions.{key}")
        for key, value in review_actions.items()
    }
    expected_review_actions = {
        "candidate_decision_count": counts["candidate_count"],
        "ambiguity_resolution_count": disposition_counts["edited"],
        "mapping_approval_count": 0,
    }
    if observed_review_actions != expected_review_actions:
        _fail(
            "review_evidence_mismatch",
            "review action counts differ from explicit decision/approval artifacts",
            location=f"{location}.review_actions",
        )

    coverage = _object(component["coverage"], location=f"{location}.coverage")
    _exact_keys(coverage, _COVERAGE_KEYS, location=f"{location}.coverage")
    coverage_counts = {
        key: _nonnegative_integer(value, location=f"{location}.coverage.{key}")
        for key, value in coverage.items()
    }
    if (
        coverage_counts["uncovered_interface_count"]
        > coverage_counts["eligible_interface_count"]
    ):
        _fail(
            "summary_mismatch",
            "uncovered interfaces exceed the eligible domain",
            location=f"{location}.coverage",
        )
    expected_debt = (
        coverage_counts["uncovered_interface_count"] + disposition_counts["uncertain"]
    )
    if coverage_counts["unresolved_debt_count"] != expected_debt:
        _fail(
            "summary_mismatch",
            "coverage debt differs from uncovered plus uncertain state",
            location=f"{location}.coverage.unresolved_debt_count",
        )

    claims = _object(component["claims"], location=f"{location}.claims")
    _exact_keys(claims, _CLAIM_KEYS, location=f"{location}.claims")
    claim_counts = {
        key: _nonnegative_integer(value, location=f"{location}.claims.{key}")
        for key, value in claims.items()
    }
    if (
        claim_counts["verified"] != 0
        or claim_counts["mapped"] != 0
        or claim_counts["observed"] != counts["materialization_count"]
        or claim_counts["declared"] != counts["materialization_count"]
        or claim_counts["tested"] != claim_counts["fresh_evidence"]
        or claim_counts["stale_evidence"] != 0
        or claim_counts["tested"] < 1
        or counts["mapping_binding_count"] < 1
    ):
        _fail(
            "claim_promotion",
            "component claims exceed reproducible fresh tested evidence",
            location=f"{location}.claims",
        )

    ratchet = _object(component["ratchet"], location=f"{location}.ratchet")
    _exact_keys(ratchet, _RATCHET_KEYS, location=f"{location}.ratchet")
    debt = _nonnegative_integer(
        ratchet["coverage_debt_count"],
        location=f"{location}.ratchet.coverage_debt_count",
    )
    expected_outcome = "pass_with_legacy_coverage_debt" if debt else "pass"
    if (
        debt != expected_debt
        or ratchet["baseline_outcome"] != expected_outcome
        or ratchet["unchanged_outcome"] != expected_outcome
    ):
        _fail(
            "summary_mismatch",
            "ratchet outcome does not match unresolved coverage debt",
            location=f"{location}.ratchet",
        )
    transports = _array(component["transports"], location=f"{location}.transports")
    if (
        any(not isinstance(item, str) for item in transports)
        or len(transports) != len(set(transports))
        or not set(transports) <= _ALLOWED_TRANSPORTS
    ):
        _fail(
            "summary_mismatch",
            "component transports are invalid",
            location=f"{location}.transports",
        )
    if tuple(transports) != _EXPECTED_COMPONENT_TRANSPORTS[expected_id]:
        _fail(
            "transport_evidence_mismatch",
            "component transports differ from exact verification procedures",
            location=f"{location}.transports",
        )
    _sha256(component["structural_digest"], location=f"{location}.structural_digest")


def _validate_totals(
    totals: dict[str, object], components: Sequence[dict[str, object]]
) -> None:
    _exact_keys(totals, _TOTAL_KEYS, location="$.structural.totals")
    observed = {
        key: _nonnegative_integer(value, location=f"$.structural.totals.{key}")
        for key, value in totals.items()
    }
    expected = {
        "source_file_count": sum(item["source"]["file_count"] for item in components),
        "source_byte_count": sum(item["source"]["byte_count"] for item in components),
        "inventory_record_count": sum(
            item["inventory_record_count"] for item in components
        ),
        "candidate_count": sum(item["candidate_count"] for item in components),
        "false_candidate_count": sum(
            item["false_candidate_count"] for item in components
        ),
        "candidate_decision_count": sum(
            item["review_actions"]["candidate_decision_count"] for item in components
        ),
        "ambiguity_resolution_count": sum(
            item["review_actions"]["ambiguity_resolution_count"]
            for item in components
        ),
        "mapping_approval_count": sum(
            item["review_actions"]["mapping_approval_count"] for item in components
        ),
        "change_approval_count": 0,
        "eligible_interface_count": sum(
            item["coverage"]["eligible_interface_count"] for item in components
        ),
        "uncovered_interface_count": sum(
            item["coverage"]["uncovered_interface_count"] for item in components
        ),
        "unresolved_debt_count": sum(
            item["coverage"]["unresolved_debt_count"] for item in components
        ),
        "materialization_count": sum(
            item["materialization_count"] for item in components
        ),
        "mapping_binding_count": sum(
            item["mapping_binding_count"] for item in components
        ),
        "tested_claim_count": sum(item["claims"]["tested"] for item in components),
        "verified_claim_count": sum(item["claims"]["verified"] for item in components),
        "fresh_evidence_count": sum(
            item["claims"]["fresh_evidence"] for item in components
        ),
        "stale_evidence_count": sum(
            item["claims"]["stale_evidence"] for item in components
        ),
    }
    if observed != expected:
        _fail(
            "summary_mismatch",
            "structural totals do not match component evidence",
            location="$.structural.totals",
        )


def _validate_runtime(value: object, *, repetitions: int) -> None:
    runtime = _object(value, location="$.runtime")
    _exact_keys(runtime, frozenset({"unit", "phases"}), location="$.runtime")
    if runtime["unit"] != "nanoseconds":
        _fail(
            "invalid_unit",
            "runtime unit must be nanoseconds",
            location="$.runtime.unit",
        )
    phases = _array(runtime["phases"], location="$.runtime.phases")
    if not phases:
        _fail(
            "missing_field",
            "runtime phases are required",
            location="$.runtime.phases",
        )
    identities: list[tuple[str, str]] = []
    for index, item in enumerate(phases):
        location = f"$.runtime.phases[{index}]"
        phase = _object(item, location=location)
        _exact_keys(
            phase,
            frozenset(
                {
                    "ecosystem",
                    "phase",
                    "samples",
                    "minimum",
                    "median",
                    "maximum",
                }
            ),
            location=location,
        )
        ecosystem = _nonempty_string(
            phase["ecosystem"], location=f"{location}.ecosystem"
        )
        name = _nonempty_string(phase["phase"], location=f"{location}.phase")
        identities.append((ecosystem, name))
        sample_values = _array(phase["samples"], location=f"{location}.samples")
        samples = [
            _positive_integer(sample, location=f"{location}.samples[{sample_index}]")
            for sample_index, sample in enumerate(sample_values)
        ]
        if len(samples) != repetitions:
            _fail(
                "runtime_summary_mismatch",
                "runtime sample count differs from repetitions",
                location=f"{location}.samples",
            )
        expected = (min(samples), int(statistics.median(samples)), max(samples))
        observed = tuple(
            _positive_integer(phase[key], location=f"{location}.{key}")
            for key in ("minimum", "median", "maximum")
        )
        if observed != expected:
            _fail(
                "runtime_summary_mismatch",
                "runtime statistics do not match samples",
                location=location,
            )
    if len(identities) != len(set(identities)):
        _fail(
            "duplicate_field",
            "runtime phase identity is duplicated",
            location="$.runtime.phases",
        )
    if tuple(identities) != _EXPECTED_RUNTIME_PHASES:
        _fail(
            "runtime_matrix_mismatch",
            "runtime phases must match the exact four-lane by five-phase matrix",
            location="$.runtime.phases",
        )


def _validate_overhead(
    value: object,
    *,
    components: Sequence[dict[str, object]],
) -> None:
    overhead = _object(value, location="$.overhead")
    _exact_keys(
        overhead,
        frozenset(
            {
                "accounting_version",
                "definitions",
                "components",
                "shared_policy",
                "change_lifecycle",
                "totals",
            }
        ),
        location="$.overhead",
    )
    if overhead["accounting_version"] != _OVERHEAD_ACCOUNTING_VERSION:
        _fail(
            "unsupported_version",
            "overhead accounting version is unsupported",
            location="$.overhead.accounting_version",
        )
    definitions = _object(overhead["definitions"], location="$.overhead.definitions")
    _exact_keys(
        definitions,
        frozenset(_OVERHEAD_DEFINITIONS),
        location="$.overhead.definitions",
    )
    if definitions != _OVERHEAD_DEFINITIONS:
        _fail(
            "accounting_definition_mismatch",
            "overhead accounting definitions differ",
            location="$.overhead.definitions",
        )

    component_values = _array(
        overhead["components"],
        location="$.overhead.components",
    )
    if len(component_values) != len(components):
        _fail(
            "overhead_summary_mismatch",
            "overhead must contain one bucket per component",
            location="$.overhead.components",
        )
    component_buckets: list[dict[str, int | str]] = []
    for index, (value_item, component) in enumerate(
        zip(component_values, components, strict=True)
    ):
        location = f"$.overhead.components[{index}]"
        item = _object(value_item, location=location)
        _exact_keys(
            item,
            frozenset(
                {
                    "id",
                    "legacy_source_bytes",
                    "authored_bytes",
                    "authored_records",
                    "derived_bytes",
                    "derived_records",
                }
            ),
            location=location,
        )
        observed = {
            "id": _nonempty_string(item["id"], location=f"{location}.id"),
            "legacy_source_bytes": _positive_integer(
                item["legacy_source_bytes"],
                location=f"{location}.legacy_source_bytes",
            ),
            **{
                key: _nonnegative_integer(item[key], location=f"{location}.{key}")
                for key in (
                    "authored_bytes",
                    "authored_records",
                    "derived_bytes",
                    "derived_records",
                )
            },
        }
        if (
            observed["id"] != component["id"]
            or observed["legacy_source_bytes"] != component["source"]["byte_count"]
        ):
            _fail(
                "overhead_summary_mismatch",
                "component overhead differs from its exact fixture source",
                location=location,
            )
        component_buckets.append(observed)

    bucket_keys = frozenset(
        {"authored_bytes", "authored_records", "derived_bytes", "derived_records"}
    )

    def validate_shared_bucket(name: str) -> dict[str, int]:
        location = f"$.overhead.{name}"
        bucket = _object(overhead[name], location=location)
        _exact_keys(bucket, bucket_keys, location=location)
        return {
            key: _nonnegative_integer(value_item, location=f"{location}.{key}")
            for key, value_item in bucket.items()
        }

    shared_policy = validate_shared_bucket("shared_policy")
    lifecycle = validate_shared_bucket("change_lifecycle")
    totals = _object(overhead["totals"], location="$.overhead.totals")
    _exact_keys(
        totals,
        frozenset(
            {
                "legacy_source_bytes",
                "authored_bytes",
                "authored_records",
                "derived_bytes",
                "derived_records",
                "authored_to_legacy",
                "derived_to_legacy",
            }
        ),
        location="$.overhead.totals",
    )
    observed_totals = {
        key: _positive_integer(totals[key], location=f"$.overhead.totals.{key}")
        for key in (
            "legacy_source_bytes",
            "authored_bytes",
            "authored_records",
            "derived_bytes",
            "derived_records",
        )
    }
    expected_totals = {
        "legacy_source_bytes": sum(
            int(item["legacy_source_bytes"]) for item in component_buckets
        ),
        **{
            key: sum(int(item[key]) for item in component_buckets)
            + shared_policy[key]
            + lifecycle[key]
            for key in (
                "authored_bytes",
                "authored_records",
                "derived_bytes",
                "derived_records",
            )
        },
    }
    if observed_totals != expected_totals:
        _fail(
            "overhead_summary_mismatch",
            "overhead totals differ from component/shared allocation",
            location="$.overhead.totals",
        )
    for name, numerator in (
        ("authored_to_legacy", observed_totals["authored_bytes"]),
        ("derived_to_legacy", observed_totals["derived_bytes"]),
    ):
        location = f"$.overhead.totals.{name}"
        ratio = _object(totals[name], location=location)
        _exact_keys(ratio, frozenset({"numerator", "denominator"}), location=location)
        if (
            ratio["numerator"] != numerator
            or ratio["denominator"] != observed_totals["legacy_source_bytes"]
        ):
            _fail(
                "overhead_summary_mismatch",
                "overhead ratio does not preserve exact integer inputs",
                location=location,
            )


def _validate_lifecycle(value: object) -> None:
    lifecycle = _object(value, location="$.change_lifecycle")
    _exact_keys(lifecycle, _LIFECYCLE_KEYS, location="$.change_lifecycle")
    expected = {
        "ecosystem": "python",
        "change_id": "require-quote-order-total",
        "delta_entry_count": 1,
        "scripted_task_completion_count": 3,
        "implementation_evidence_count": 1,
        "verification_evidence_count": 1,
        "tested_claim_count": 1,
        "verified_claim_count": 0,
        "change_approval_count": 0,
        "status": "archived",
    }
    if any(
        lifecycle[key] != expected_value for key, expected_value in expected.items()
    ):
        _fail(
            "summary_mismatch",
            "change lifecycle does not prove the exact archived tested flow",
            location="$.change_lifecycle",
        )
    _sha256(
        lifecycle["structural_digest"],
        location="$.change_lifecycle.structural_digest",
    )


def _validate_limitations(value: object) -> None:
    limitations = _array(value, location="$.limitations")
    identities: list[str] = []
    for index, item in enumerate(limitations):
        location = f"$.limitations[{index}]"
        limitation = _object(item, location=location)
        _exact_keys(
            limitation,
            frozenset({"id", "owner", "statement"}),
            location=location,
        )
        identities.append(_nonempty_string(limitation["id"], location=f"{location}.id"))
        _nonempty_string(limitation["owner"], location=f"{location}.owner")
        _nonempty_string(limitation["statement"], location=f"{location}.statement")
    if len(identities) != len(set(identities)) or not {
        "scripted-review-not-human-effort",
        "no-formal-verification",
        "no-separate-approval-artifacts",
    } <= set(identities):
        _fail(
            "summary_mismatch",
            "mandatory benchmark limitations are missing or duplicated",
            location="$.limitations",
        )


def _reject_path_leaks(value: object, *, location: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_path_leaks(child, location=f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_path_leaks(child, location=f"{location}[{index}]")
        return
    if isinstance(value, str) and (
        _POSIX_PATH_PATTERN.search(value) is not None
        or _WINDOWS_PATH_PATTERN.search(value) is not None
    ):
        _fail(
            "path_leak",
            "report contains an absolute or temporary path",
            location=location,
        )


def _exact_keys(
    value: dict[str, object], expected: frozenset[str], *, location: str
) -> None:
    observed = frozenset(value)
    unexpected = observed - expected
    if unexpected:
        _fail(
            "unknown_field",
            f"unexpected fields: {sorted(unexpected)}",
            location=location,
        )
    missing = expected - observed
    if missing:
        _fail(
            "missing_field",
            f"missing fields: {sorted(missing)}",
            location=location,
        )


def _object(value: object, *, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail("invalid_type", "expected an object", location=location)
    return value


def _array(value: object, *, location: str) -> list[object]:
    if not isinstance(value, list):
        _fail("invalid_type", "expected an array", location=location)
    return value


def _nonempty_string(value: object, *, location: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("invalid_type", "expected a non-empty string", location=location)
    return value


def _nonnegative_integer(value: object, *, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("invalid_type", "expected a non-negative integer", location=location)
    return value


def _positive_integer(value: object, *, location: str) -> int:
    result = _nonnegative_integer(value, location=location)
    if result == 0:
        _fail("invalid_type", "expected a positive integer", location=location)
    return result


def _sha256(value: object, *, location: str) -> str:
    text = _nonempty_string(value, location=location)
    if len(text) != 64 or not set(text) <= _HEX_DIGITS:
        _fail("invalid_digest", "expected a lowercase SHA-256", location=location)
    return text


_LANE_COMPONENTS = {
    "python": "python_legacy_quote",
    "typescript_fastify": "typescript_fastify_legacy_quote",
    "go_http": "go_stdlib_legacy_quote",
    "go_platform": "go_stdlib_legacy_platforms",
}
_LANE_EVIDENCE_KEYS = frozenset(
    {
        "kind",
        "evidence_version",
        "lane",
        "status",
        "source",
        "deterministic",
        "runtime",
        "metrics",
    }
)
_LANE_DETERMINISTIC_KEYS = frozenset(
    {
        "inventory",
        "discovery",
        "decisions",
        "bundle",
        "mapping",
        "verification_requests",
    }
)
_LANE_METRIC_KEYS = frozenset(
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
_BENCHMARK_PRODUCER = Producer(
    kind="producer",
    name="org.ucf.rel001-benchmark",
    version=REPORT_VERSION,
)
_RATCHET_PROCEDURE_URI = "urn:ucf:benchmark:ratchet-assessment:2.0.0"
_TASK_IDS = ("task.1-1", "task.1-2", "task.1-3")
_COMPILATION_INPUT_KEYS = frozenset(
    {
        "kind",
        "input_version",
        "lane_runs",
        "runtime_samples",
        "wheel_sha256",
        "runtime_lock_sha256",
        "installed_distributions",
        "host_platform",
        "adapter_artifact_digests",
        "driver_artifact_digests",
        "benchmark_tool_digests",
        "conformance_report_digests",
        "toolchains",
    }
)


def canonical_compilation_input_json(payload: Mapping[str, object]) -> bytes:
    """Validate and encode the private installed-compiler input."""

    normalized = dict(payload)
    _validate_compilation_input(normalized)
    return _canonical_json_bytes(normalized)


def parse_compilation_input_json(content: str | bytes) -> dict[str, object]:
    """Parse one exact canonical installed-compiler input."""

    try:
        text = content.decode("ascii") if isinstance(content, bytes) else content
    except UnicodeDecodeError:
        _fail("invalid_json", "compiler input must be ASCII JSON", location="$")
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except BenchmarkValidationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError):
        _fail("invalid_json", "compiler input is not valid JSON", location="$")
    if not isinstance(payload, dict):
        _fail("invalid_type", "compiler input root must be an object", location="$")
    _validate_compilation_input(payload)
    if text.encode("ascii") != _canonical_json_bytes(payload):
        _fail(
            "noncanonical_json",
            "compiler input bytes are not exact canonical JSON",
            location="$",
        )
    return payload


def _validate_compilation_input(payload: dict[str, object]) -> None:
    _exact_keys(payload, _COMPILATION_INPUT_KEYS, location="$")
    if (
        payload["kind"] != "rel001_benchmark_compilation_input"
        or payload["input_version"] != REPORT_VERSION
    ):
        _fail(
            "unsupported_version",
            "compiler input coordinates are unsupported",
            location="$",
        )
    lane_runs = _object(payload["lane_runs"], location="$.lane_runs")
    _exact_keys(lane_runs, frozenset(_LANE_COMPONENTS), location="$.lane_runs")
    for lane, runs in lane_runs.items():
        _array(runs, location=f"$.lane_runs.{lane}")
    runtime = _array(payload["runtime_samples"], location="$.runtime_samples")
    runtime_identities: list[tuple[str, str]] = []
    for index, value in enumerate(runtime):
        location = f"$.runtime_samples[{index}]"
        record = _object(value, location=location)
        _exact_keys(
            record,
            frozenset({"lane", "phase", "samples"}),
            location=location,
        )
        identity = (
            _nonempty_string(record["lane"], location=f"{location}.lane"),
            _nonempty_string(record["phase"], location=f"{location}.phase"),
        )
        runtime_identities.append(identity)
        _array(record["samples"], location=f"{location}.samples")
    if len(runtime_identities) != len(set(runtime_identities)):
        _fail(
            "duplicate_field",
            "compiler runtime identity is duplicated",
            location="$.runtime_samples",
        )
    for key in (
        "installed_distributions",
        "host_platform",
        "adapter_artifact_digests",
        "driver_artifact_digests",
        "benchmark_tool_digests",
        "conformance_report_digests",
        "toolchains",
    ):
        _object(payload[key], location=f"$.{key}")
    _sha256(payload["wheel_sha256"], location="$.wheel_sha256")
    _sha256(payload["runtime_lock_sha256"], location="$.runtime_lock_sha256")


def compile_report_from_input(payload: Mapping[str, object]) -> dict[str, object]:
    """Compile a validated serialized input under the current installed UCF."""

    normalized = dict(payload)
    _validate_compilation_input(normalized)
    runtime_samples = {
        (record["lane"], record["phase"]): record["samples"]
        for record in normalized["runtime_samples"]
    }
    return compile_report(
        normalized["lane_runs"],
        runtime_samples=runtime_samples,
        wheel_sha256=normalized["wheel_sha256"],
        runtime_lock_sha256=normalized["runtime_lock_sha256"],
        installed_distributions=normalized["installed_distributions"],
        host_platform=normalized["host_platform"],
        adapter_artifact_digests=normalized["adapter_artifact_digests"],
        driver_artifact_digests=normalized["driver_artifact_digests"],
        benchmark_tool_digests=normalized["benchmark_tool_digests"],
        conformance_report_digests=normalized["conformance_report_digests"],
        toolchains=normalized["toolchains"],
    )


def parse_lane_evidence_json(content: str | bytes) -> dict[str, object]:
    """Parse one canonical private lane envelope for report compilation."""

    try:
        text = content.decode("ascii") if isinstance(content, bytes) else content
        payload = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except BenchmarkValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        _fail(
            "invalid_lane_evidence",
            "lane evidence is not canonical ASCII JSON",
            location="$",
        )
    if not isinstance(payload, dict):
        _fail(
            "invalid_lane_evidence",
            "lane evidence root must be an object",
            location="$",
        )
    _validate_lane_envelope_shape(payload)
    if text.encode("ascii") != _canonical_json_bytes(payload):
        _fail(
            "noncanonical_json",
            "lane evidence bytes are not canonical JSON",
            location="$",
        )
    return payload


def publish_report(
    destination: Path,
    payload: Mapping[str, object],
) -> None:
    """Publish one accepted report without replacing any existing entry."""

    content = canonical_report_json(payload)
    path = Path(destination)
    if not path.is_absolute():
        _fail(
            "output_not_absolute",
            "report output must be absolute",
            location="$.output",
        )
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    else:
        _fail(
            "output_exists",
            "report output already exists",
            location="$.output",
        )
    try:
        parent = path.parent.resolve(strict=True)
        path.parent.lstat()
    except OSError:
        _fail(
            "output_parent_unavailable",
            "report output parent is unavailable",
            location="$.output",
        )
    if parent != path.parent or not path.parent.is_dir():
        _fail(
            "output_parent_unsafe",
            "report output parent must be one canonical directory",
            location="$.output",
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            _fail(
                "output_exists",
                "report output appeared during publication",
                location="$.output",
            )
        temporary.unlink()
        parent_descriptor = os.open(
            parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def compile_report(
    lane_runs: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    runtime_samples: Mapping[tuple[str, str], Sequence[int]],
    wheel_sha256: str,
    runtime_lock_sha256: str,
    installed_distributions: Mapping[str, str],
    host_platform: Mapping[str, str],
    adapter_artifact_digests: Mapping[str, str],
    driver_artifact_digests: Mapping[str, str],
    benchmark_tool_digests: Mapping[str, str],
    conformance_report_digests: Mapping[str, str],
    toolchains: Mapping[str, str],
) -> dict[str, object]:
    """Compile validated repeated lane evidence into one closed report."""

    if set(lane_runs) != set(_LANE_COMPONENTS):
        _fail(
            "incomplete_lane_set",
            "all four benchmark components are required",
            location="$.lane_runs",
        )
    repetitions = {len(runs) for runs in lane_runs.values()}
    if len(repetitions) != 1:
        _fail(
            "summary_mismatch",
            "all lanes require the same repetition count",
            location="$.lane_runs",
        )
    [repetition_count] = repetitions
    if repetition_count < 3:
        _fail(
            "insufficient_repetitions",
            "benchmark requires at least three lane repetitions",
            location="$.lane_runs",
        )

    policy = _benchmark_ratchet_policy()
    components: dict[str, dict[str, object]] = {}
    component_accounting: dict[str, dict[str, int]] = {}
    first_contexts: dict[str, dict[str, object]] = {}
    policy_accounting = {
        "authored_bytes": len(canonical_ratchet_json(policy)),
        "authored_records": 1,
        "derived_bytes": 0,
        "derived_records": 0,
    }
    adapter_identities: dict[str, str] = {}
    for lane in _LANE_COMPONENTS:
        products = [
            _compile_component(envelope, expected_lane=lane, policy=policy)
            for envelope in lane_runs[lane]
        ]
        structural_digests = {
            product["component"]["structural_digest"] for product in products
        }
        if len(structural_digests) != 1:
            _fail(
                "nondeterministic_structure",
                "repeated lane structure differs",
                location=f"$.lane_runs.{lane}",
            )
        first = products[0]
        components[lane] = first["component"]
        first_contexts[lane] = first["context"]
        if any(product["component"] != first["component"] for product in products[1:]):
            _fail(
                "nondeterministic_structure",
                "repeated lane metrics or identities differ",
                location=f"$.lane_runs.{lane}",
            )
        component_accounting[lane] = first["accounting"]
        adapter_identities[lane] = first["adapter_identity"]

    if adapter_identities["go_http"] != adapter_identities["go_platform"]:
        _fail(
            "adapter_identity_mismatch",
            "Go components used different adapters",
            location="$.lane_runs.go_platform",
        )

    lifecycle, lifecycle_accounting = _compile_python_lifecycle(
        first_contexts["python"]
    )
    ecosystems = [
        {"id": "python", "components": [components["python"]]},
        {
            "id": "typescript_fastify",
            "components": [components["typescript_fastify"]],
        },
        {
            "id": "go",
            "components": [components["go_http"], components["go_platform"]],
        },
    ]
    all_components = [components[lane] for lane in _LANE_COMPONENTS]
    structural: dict[str, object] = {
        "ecosystems": ecosystems,
        "totals": _component_totals(all_components),
        "digest": "0" * 64,
    }
    structural["digest"] = derive_structural_digest(structural)
    legacy_bytes = structural["totals"]["source_byte_count"]
    distribution_coordinates = dict(sorted(installed_distributions.items()))
    identities = {
        "ucf_version": ucf.__version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "adapter_protocol_version": ADAPTER_PROTOCOL_VERSION,
        "adapter_conformance_kit_version": CONFORMANCE_KIT_VERSION,
        "ratchet_version": RATCHET_VERSION,
        "repetitions": repetition_count,
        "wheel_sha256": wheel_sha256,
        "runtime_lock_sha256": runtime_lock_sha256,
        "installed_environment_sha256": _object_digest(distribution_coordinates),
        "installed_distributions": distribution_coordinates,
        "host_platform": dict(host_platform),
        "adapters": {
            "python": adapter_identities["python"],
            "typescript_fastify": adapter_identities["typescript_fastify"],
            "go": adapter_identities["go_http"],
        },
        "adapter_artifact_digests": dict(adapter_artifact_digests),
        "driver_artifact_digests": dict(driver_artifact_digests),
        "benchmark_tool_digests": dict(benchmark_tool_digests),
        "conformance_report_digests": dict(conformance_report_digests),
        "toolchains": dict(toolchains),
    }
    report = {
        "kind": "rel001_benchmark_report",
        "report_version": REPORT_VERSION,
        "status": "passed",
        "identities": identities,
        "structural": structural,
        "runtime": {
            "unit": "nanoseconds",
            "phases": _runtime_phase_reports(
                runtime_samples,
                repetitions=repetition_count,
            ),
        },
        "overhead": _compile_overhead(
            components=components,
            component_accounting=component_accounting,
            policy_accounting=policy_accounting,
            lifecycle_accounting=lifecycle_accounting,
            legacy_bytes=legacy_bytes,
        ),
        "change_lifecycle": lifecycle,
        "limitations": [
            {
                "id": "scripted-review-not-human-effort",
                "owner": "UCF maintainers",
                "statement": (
                    "Review actions are counted; no human review duration or "
                    "usability claim is made."
                ),
            },
            {
                "id": "no-formal-verification",
                "owner": "UCF maintainers",
                "statement": (
                    "The benchmark records tested claims and zero formally "
                    "verified claims."
                ),
            },
            {
                "id": "no-separate-approval-artifacts",
                "owner": "UCF maintainers",
                "statement": (
                    "The benchmark records zero mapping and change approvals; "
                    "results and scripted tasks are not approval artifacts."
                ),
            },
            {
                "id": "frozen-fixture-scope",
                "owner": "UCF maintainers",
                "statement": (
                    "Measurements describe the four frozen component roots in "
                    "three ecosystem lanes; they are not a population estimate."
                ),
            },
            {
                "id": "go-platform-component",
                "owner": "UCF maintainers",
                "statement": (
                    "The Go CLI and event root is an auxiliary component of the "
                    "compiled Go ecosystem proof, not a fourth ecosystem claim."
                ),
            },
        ],
    }
    canonical_report_json(report)
    return report


def _compile_overhead(
    *,
    components: Mapping[str, Mapping[str, object]],
    component_accounting: Mapping[str, Mapping[str, int]],
    policy_accounting: Mapping[str, int],
    lifecycle_accounting: Mapping[str, int],
    legacy_bytes: int,
) -> dict[str, object]:
    component_buckets = []
    for lane in _LANE_COMPONENTS:
        component = components[lane]
        component_buckets.append(
            {
                "id": component["id"],
                "legacy_source_bytes": component["source"]["byte_count"],
                **dict(component_accounting[lane]),
            }
        )
    total_legacy = sum(item["legacy_source_bytes"] for item in component_buckets)
    if total_legacy != legacy_bytes:
        _fail(
            "overhead_summary_mismatch",
            "component source accounting differs from structural totals",
            location="$.overhead.components",
        )
    totals = {
        "legacy_source_bytes": total_legacy,
        **{
            key: sum(item[key] for item in component_buckets)
            + policy_accounting[key]
            + lifecycle_accounting[key]
            for key in (
                "authored_bytes",
                "authored_records",
                "derived_bytes",
                "derived_records",
            )
        },
    }
    totals["authored_to_legacy"] = {
        "numerator": totals["authored_bytes"],
        "denominator": total_legacy,
    }
    totals["derived_to_legacy"] = {
        "numerator": totals["derived_bytes"],
        "denominator": total_legacy,
    }
    return {
        "accounting_version": _OVERHEAD_ACCOUNTING_VERSION,
        "definitions": dict(_OVERHEAD_DEFINITIONS),
        "components": component_buckets,
        "shared_policy": dict(policy_accounting),
        "change_lifecycle": dict(lifecycle_accounting),
        "totals": totals,
    }


def _validate_lane_envelope_shape(envelope: dict[str, object]) -> None:
    _exact_keys(envelope, _LANE_EVIDENCE_KEYS, location="$")
    if (
        envelope["kind"] != "rel001_lane_evidence"
        or envelope["evidence_version"] != "1.0.0"
        or envelope["status"] != "passed"
        or envelope["lane"] not in _LANE_COMPONENTS
    ):
        _fail(
            "invalid_lane_evidence",
            "lane evidence coordinates are unsupported",
            location="$",
        )
    source = _object(envelope["source"], location="$.source")
    _exact_keys(source, _SOURCE_KEYS, location="$.source")
    _positive_integer(source["file_count"], location="$.source.file_count")
    _positive_integer(source["byte_count"], location="$.source.byte_count")
    _sha256(source["manifest_digest"], location="$.source.manifest_digest")
    deterministic = _object(envelope["deterministic"], location="$.deterministic")
    _exact_keys(
        deterministic,
        _LANE_DETERMINISTIC_KEYS,
        location="$.deterministic",
    )
    runtime = _object(envelope["runtime"], location="$.runtime")
    _exact_keys(
        runtime,
        frozenset({"verification_results", "successor_behaviors", "tested_trust"}),
        location="$.runtime",
    )
    metrics = _object(envelope["metrics"], location="$.metrics")
    _exact_keys(metrics, _LANE_METRIC_KEYS, location="$.metrics")
    dispositions = _object(metrics["dispositions"], location="$.metrics.dispositions")
    _exact_keys(
        dispositions,
        _DISPOSITION_KEYS,
        location="$.metrics.dispositions",
    )
    for key, value in metrics.items():
        if key not in {"dispositions", "transports"}:
            _nonnegative_integer(value, location=f"$.metrics.{key}")
    for key, value in dispositions.items():
        _nonnegative_integer(value, location=f"$.metrics.dispositions.{key}")
    _array(
        deterministic["verification_requests"],
        location="$.deterministic.verification_requests",
    )
    for key in ("verification_results", "successor_behaviors", "tested_trust"):
        _array(runtime[key], location=f"$.runtime.{key}")
    _array(metrics["transports"], location="$.metrics.transports")


def _compile_component(
    envelope_value: Mapping[str, object],
    *,
    expected_lane: str,
    policy: RatchetPolicy,
) -> dict[str, object]:
    envelope = dict(envelope_value)
    _validate_lane_envelope_shape(envelope)
    if envelope["lane"] != expected_lane:
        _fail(
            "lane_identity_mismatch",
            "lane evidence appears under the wrong run key",
            location=f"$.lane_runs.{expected_lane}",
        )
    deterministic = envelope["deterministic"]
    runtime = envelope["runtime"]
    metrics = envelope["metrics"]
    inventory = parse_inventory_snapshot_json(
        _canonical_json_bytes(deterministic["inventory"])
    )
    discovery = parse_discovery_result_json(
        _canonical_json_bytes(deterministic["discovery"])
    )
    decisions = parse_decision_set_json(
        _canonical_json_bytes(deterministic["decisions"])
    )
    bundle = parse_onboarding_bundle_json(
        _canonical_json_bytes(deterministic["bundle"])
    )
    mapping = parse_implementation_mapping_result_json(
        _canonical_json_bytes(deterministic["mapping"])
    )
    _require_canonical(canonical_inventory_json(inventory), deterministic["inventory"])
    for model, payload in (
        (discovery, deterministic["discovery"]),
        (decisions, deterministic["decisions"]),
        (bundle, deterministic["bundle"]),
    ):
        _require_canonical(canonical_onboarding_json(model), payload)
    _require_canonical(
        canonical_implementation_evidence_json(mapping),
        deterministic["mapping"],
    )
    validate_onboarding_bundle(bundle)
    if (
        bundle.inventory != inventory
        or bundle.discovery != discovery
        or bundle.decisions != decisions
    ):
        _fail(
            "resource_identity_mismatch",
            "lane onboarding resources do not form one exact bundle",
            location="$.deterministic.bundle",
        )
    capabilities = {
        IMPLEMENTATION_MAPPING_CAPABILITY: IMPLEMENTATION_EVIDENCE_VERSION,
        EXECUTION_VERIFICATION_CAPABILITY: IMPLEMENTATION_EVIDENCE_VERSION,
    }
    validate_implementation_mapping_result(
        mapping,
        request=mapping.request,
        bundle=bundle,
        current_inventory=inventory,
        initialized_adapter=mapping.producer,
        negotiated_capabilities=capabilities,
    )

    request_payloads = deterministic["verification_requests"]
    result_payloads = runtime["verification_results"]
    behavior_payloads = runtime["successor_behaviors"]
    trust_payloads = runtime["tested_trust"]
    lengths = {
        len(request_payloads),
        len(result_payloads),
        len(behavior_payloads),
        len(trust_payloads),
    }
    if lengths != {metrics["verification_evidence_count"]}:
        _fail(
            "summary_mismatch",
            "runtime-bound resource counts differ from evidence metrics",
            location="$.deterministic.verification_requests",
        )
    requests = []
    results = []
    successors = []
    trusts = []
    tested_count = 0
    verified_count = 0
    fresh_count = 0
    status_bytes = 0
    for index, (
        request_payload,
        result_payload,
        behavior_payload,
        trust_payload,
    ) in enumerate(
        zip(
            request_payloads,
            result_payloads,
            behavior_payloads,
            trust_payloads,
            strict=True,
        )
    ):
        request = parse_execution_verification_request_json(
            _canonical_json_bytes(request_payload)
        )
        result = parse_execution_verification_result_json(
            _canonical_json_bytes(result_payload)
        )
        successor = parse_ir_json(_canonical_json_bytes(behavior_payload))
        trust = parse_trust_ir_json(_canonical_json_bytes(trust_payload))
        _require_canonical(
            canonical_implementation_evidence_json(request), request_payload
        )
        _require_canonical(
            canonical_implementation_evidence_json(result), result_payload
        )
        _require_canonical(canonical_ir_json(successor), behavior_payload)
        _require_canonical(canonical_trust_ir_json(trust), trust_payload)
        validate_execution_verification_result(
            result,
            request=request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=mapping.producer,
            initialized_adapter=result.producer,
            negotiated_capabilities=capabilities,
        )
        projection = project_execution_verification(
            result,
            request=request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=mapping.producer,
            initialized_adapter=result.producer,
            negotiated_capabilities=capabilities,
        )
        if canonical_ir_json(projection.successor_behavior) != canonical_ir_json(
            successor
        ):
            _fail(
                "successor_identity_mismatch",
                "published successor Behavior differs from replay",
                location=f"$.runtime.successor_behaviors[{index}]",
            )
        if canonical_trust_ir_json(
            projection.tested_trust
        ) != canonical_trust_ir_json(trust):
            _fail(
                "trust_identity_mismatch",
                "published tested Trust differs from replay",
                location=f"$.runtime.tested_trust[{index}]",
            )
        validate_trust_against_behavior(trust, successor)
        claims = tuple(record for record in trust.records if isinstance(record, Claim))
        tested_count += sum(claim.level is ClaimLevel.TESTED for claim in claims)
        verified_count += sum(claim.level is ClaimLevel.VERIFIED for claim in claims)
        envelope_status = record_verification_evidence(
            result,
            request=request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=mapping.producer,
            initialized_adapter=result.producer,
            negotiated_capabilities=capabilities,
        )
        assessment = assess_verification_evidence(
            envelope_status,
            recorded_result=result,
            recorded_request=request,
            recorded_mapping_result=mapping,
            recorded_bundle=bundle,
            recorded_current_inventory=inventory,
            recorded_mapping_initialized_adapter=mapping.producer,
            recorded_initialized_adapter=result.producer,
            recorded_negotiated_capabilities=capabilities,
            current_result=result,
            current_request=request,
            current_mapping_result=mapping,
            current_bundle=bundle,
            current_inventory=inventory,
            current_mapping_initialized_adapter=mapping.producer,
            current_initialized_adapter=result.producer,
            current_negotiated_capabilities=capabilities,
        )
        if assessment.status is not EvidenceStatus.FRESH or assessment.reasons:
            _fail(
                "stale_evidence",
                "unchanged lane evidence did not remain fresh",
                location=f"$.runtime.verification_results[{index}]",
            )
        fresh_count += 1
        status_bytes += len(canonical_evidence_status_json(envelope_status))
        status_bytes += len(canonical_evidence_status_json(assessment))
        requests.append(request)
        results.append(result)
        successors.append(successor)
        trusts.append(trust)

    disposition_counts = {
        summary.disposition.value: len(summary.candidate_ids)
        for summary in bundle.baseline.dispositions
    }
    observed_claims = next(
        summary.claim_ids
        for summary in bundle.baseline.claim_levels
        if summary.level is ClaimLevel.OBSERVED
    )
    declared_claims = next(
        summary.claim_ids
        for summary in bundle.baseline.claim_levels
        if summary.level is ClaimLevel.DECLARED
    )
    derived_transports: list[str] = []
    for index, result in enumerate(results):
        if result.procedure_uri not in _PROCEDURE_TRANSPORTS:
            _fail(
                "unsupported_procedure",
                "verification procedure has no benchmark transport classification",
                location=f"$.runtime.verification_results[{index}].procedure_uri",
            )
        transport = _PROCEDURE_TRANSPORTS[result.procedure_uri]
        if transport is not None and transport not in derived_transports:
            derived_transports.append(transport)
    derived_transports.sort()
    expected_metrics = {
        "inventory_record_count": len(inventory.records),
        "candidate_count": len(discovery.candidates),
        "dispositions": disposition_counts,
        "eligible_interface_count": len(discovery.coverage.eligible_subjects),
        "uncovered_interface_count": len(discovery.coverage.uncovered_subjects),
        "materialization_count": len(bundle.baseline.materializations),
        "mapping_binding_count": len(mapping.bindings),
        "tested_claim_count": tested_count,
        "verified_claim_count": verified_count,
        "verification_evidence_count": len(results),
        "transports": derived_transports,
    }
    if metrics != expected_metrics:
        _fail(
            "summary_mismatch",
            "lane metrics differ from parsed resources",
            location="$.metrics",
        )

    assessment = build_ratchet_assessment(
        policy,
        bundle,
        producer=_BENCHMARK_PRODUCER,
        procedure_uri=_RATCHET_PROCEDURE_URI,
        capture_context=bundle.capture_context,
    )
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    unchanged = build_ratchet_assessment(
        policy,
        bundle,
        producer=_BENCHMARK_PRODUCER,
        procedure_uri=_RATCHET_PROCEDURE_URI,
        capture_context=bundle.capture_context,
    )
    evaluation = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        unchanged,
        accepted_baseline_id=baseline.id,
    )
    debt_count = len(baseline.coverage.allowances)
    baseline_outcome = "pass_with_legacy_coverage_debt" if debt_count else "pass"
    structural_projection = {
        "source": envelope["source"],
        "metrics": metrics,
        "resources": {
            "inventory": _object_digest(deterministic["inventory"]),
            "discovery": _object_digest(deterministic["discovery"]),
            "decisions": _object_digest(deterministic["decisions"]),
            "bundle": _object_digest(deterministic["bundle"]),
            "mapping": _object_digest(deterministic["mapping"]),
            "verification_requests": [
                _object_digest(payload) for payload in request_payloads
            ],
            "verification_results_stable": [
                _stable_verification_result_digest(result) for result in results
            ],
            "successor_behaviors": [
                _stable_successor_digest(successor) for successor in successors
            ],
            "tested_trust": [_stable_trust_digest(trust) for trust in trusts],
            "runtime_projection_version": "1.0.0",
        },
        "ratchet": {
            "assessment": hashlib.sha256(
                canonical_ratchet_json(assessment)
            ).hexdigest(),
            "baseline": hashlib.sha256(canonical_ratchet_json(baseline)).hexdigest(),
            "evaluation": hashlib.sha256(
                canonical_ratchet_json(evaluation)
            ).hexdigest(),
        },
    }
    component = {
        "id": _LANE_COMPONENTS[expected_lane],
        "source": envelope["source"],
        "inventory_record_count": metrics["inventory_record_count"],
        "candidate_count": metrics["candidate_count"],
        "false_candidate_count": (
            disposition_counts["edited"] + disposition_counts["rejected"]
        ),
        "dispositions": disposition_counts,
        "coverage": {
            "eligible_interface_count": metrics["eligible_interface_count"],
            "uncovered_interface_count": metrics["uncovered_interface_count"],
            "unresolved_debt_count": debt_count,
        },
        "materialization_count": metrics["materialization_count"],
        "mapping_binding_count": metrics["mapping_binding_count"],
        "review_actions": {
            "candidate_decision_count": metrics["candidate_count"],
            "ambiguity_resolution_count": disposition_counts["edited"],
            "mapping_approval_count": 0,
        },
        "claims": {
            "observed": len(observed_claims),
            "declared": len(declared_claims),
            "mapped": 0,
            "tested": tested_count,
            "verified": verified_count,
            "fresh_evidence": fresh_count,
            "stale_evidence": 0,
        },
        "ratchet": {
            "baseline_outcome": baseline_outcome,
            "unchanged_outcome": evaluation.combined_outcome.value,
            "coverage_debt_count": debt_count,
        },
        "transports": derived_transports,
        "structural_digest": hashlib.sha256(
            _canonical_json_bytes(structural_projection)
        ).hexdigest(),
    }
    deterministic_values = [
        deterministic[key] for key in ("inventory", "discovery", "bundle", "mapping")
    ]
    deterministic_values.extend(request_payloads)
    runtime_values = [*result_payloads, *behavior_payloads, *trust_payloads]
    derived_size = sum(
        len(_canonical_json_bytes(value)) for value in deterministic_values
    )
    derived_size += sum(len(_canonical_json_bytes(value)) for value in runtime_values)
    derived_size += sum(
        len(canonical_ratchet_json(value))
        for value in (assessment, baseline, evaluation)
    )
    derived_size += status_bytes
    return {
        "component": component,
        "context": {
            "bundle": bundle,
            "inventory": inventory,
            "mapping": mapping,
            "requests": tuple(requests),
            "results": tuple(results),
            "capabilities": capabilities,
            "tested_count": tested_count,
            "verified_count": verified_count,
        },
        "accounting": {
            "authored_bytes": len(canonical_onboarding_json(decisions)),
            "authored_records": 1,
            "derived_bytes": derived_size,
            "derived_records": len(deterministic_values)
            + len(runtime_values)
            + 3
            + 2 * len(results),
        },
        "adapter_identity": f"{mapping.producer.name}@{mapping.producer.version}",
    }


def _benchmark_ratchet_policy() -> RatchetPolicy:
    rule = RatchetRule(
        kind="ratchet_rule",
        id="required-benchmark-check",
        version=REPORT_VERSION,
        procedure_uri="urn:ucf:benchmark:required-check:1.0.0",
        producer=_BENCHMARK_PRODUCER,
        summary="Require every selected benchmark verification check.",
    )
    provisional = RatchetPolicy(
        kind="ratchet_policy",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_POLICY_SCHEMA_URI,
        id=f"policy.{'0' * 64}",
        evaluator=CapabilitySelection(
            kind="capability",
            name=RATCHET_EVALUATOR_CAPABILITY,
            version=RATCHET_VERSION,
        ),
        rules=(rule,),
    )
    return provisional.model_copy(update={"id": derive_policy_id(provisional)})


def _compile_python_lifecycle(
    context: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, int]]:
    bundle = context["bundle"]
    mapping = context["mapping"]
    inventory = context["inventory"]
    result = context["results"][0]
    capabilities = context["capabilities"]
    final_behavior = bundle.behavior
    base_payload = json.loads(canonical_ir_json(final_behavior))
    quote_order = next(
        entity
        for entity in base_payload["entities"]
        if entity["kind"] == "use_case" and entity["id"] == "use-case.quote-order"
    )
    total = next(
        port for port in quote_order["output_ports"] if port["name"] == "total-cents"
    )
    if total["required"] is not True:
        _fail(
            "lifecycle_mismatch",
            "reviewed Python final behavior lacks the required total",
            location="$.change_lifecycle",
        )
    total["required"] = False
    base_behavior = parse_ir_json(json.dumps(base_payload))
    proposal = _change_proposal(base_behavior)
    validate_change_proposal(proposal, base_behavior)
    delta = derive_behavior_delta(proposal, base_behavior, final_behavior)
    validate_behavior_delta(delta, proposal, base_behavior, final_behavior)
    if len(delta.entries) != 1:
        _fail(
            "lifecycle_mismatch",
            "benchmark lifecycle must contain one behavior delta",
            location="$.change_lifecycle",
        )
    subject = delta_subject_ref(delta.entries[0])
    graph = derive_task_graph(
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        subject_assignments={task_id: (subject,) for task_id in _TASK_IDS},
        dependencies={
            "task.1-1": (),
            "task.1-2": ("task.1-1",),
            "task.1-3": ("task.1-2",),
        },
    )
    for task_id in _TASK_IDS:
        graph = complete_change_task(
            graph,
            task_id,
            delta=delta,
            proposal=proposal,
            base_behavior=base_behavior,
            final_behavior=final_behavior,
        )
    validate_task_graph(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    evidence_contexts = (
        ExecutionEvidenceContext(
            result=result,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=mapping.producer,
            initialized_adapter=result.producer,
            negotiated_capabilities=capabilities,
        ),
    )
    implementation = derive_implementation_record(
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    validate_implementation_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    verification = derive_verification_record(
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    validate_verification_record(
        verification,
        implementation,
        graph,
        delta,
        proposal,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
        evidence_contexts=evidence_contexts,
    )
    archive = derive_archive_record(
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base_behavior,
        final_behavior,
        evidence_contexts=evidence_contexts,
    )
    validate_archive_record(
        archive,
        proposal,
        delta,
        graph,
        implementation,
        verification,
        base_behavior,
        final_behavior,
        evidence_contexts=evidence_contexts,
    )
    derived = (delta, graph, implementation, verification, archive)
    structural_digest = _stable_lifecycle_digest(proposal, *derived)
    lifecycle = {
        "ecosystem": "python",
        "change_id": proposal.change_id,
        "delta_entry_count": len(delta.entries),
        "scripted_task_completion_count": len(graph.tasks),
        "implementation_evidence_count": len(implementation.bindings),
        "verification_evidence_count": len(verification.subjects),
        "tested_claim_count": context["tested_count"],
        "verified_claim_count": context["verified_count"],
        "change_approval_count": 0,
        "status": archive.status,
        "structural_digest": structural_digest,
    }
    return lifecycle, {
        "authored_bytes": len(canonical_change_lifecycle_json(proposal)),
        "authored_records": 1,
        "derived_bytes": sum(
            len(canonical_change_lifecycle_json(item)) for item in derived
        ),
        "derived_records": len(derived),
    }


def _change_proposal(base_behavior) -> ChangeProposal:
    change_id = "require-quote-order-total"
    change_path = f"changes/{change_id}"
    artifacts = (
        _openspec_artifact(
            f"{change_path}/.openspec.yaml",
            OpenSpecArtifactRole.CHANGE_METADATA,
            b"schema: spec-driven\n",
            media_type="application/yaml;charset=utf-8",
        ),
        _openspec_artifact(
            f"{change_path}/proposal.md",
            OpenSpecArtifactRole.PROPOSAL,
            b"## Why\n\nQuote totals must always be returned.\n",
        ),
        _openspec_artifact(
            f"{change_path}/tasks.md",
            OpenSpecArtifactRole.TASKS,
            (
                b"## 1. Contract\n\n"
                b"- [ ] 1.1 Review the behavior delta\n"
                b"- [ ] 1.2 Implement the change\n"
                b"- [ ] 1.3 Run verification\n"
            ),
        ),
    )
    return ChangeProposal(
        kind="change_proposal",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=CHANGE_PROPOSAL_SCHEMA_URI,
        change_id=change_id,
        base_behavior=_behavior_ref(base_behavior),
        openspec=OpenSpecManifest(
            kind="openspec_manifest",
            profile=OPENSPEC_INTEROP_PROFILE,
            tested_against_version=OPENSPEC_TESTED_AGAINST_VERSION,
            change_path=change_path,
            artifacts=artifacts,
        ),
    )


def _openspec_artifact(
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
        byte_digest=_digest_bytes(content),
    )


def _behavior_ref(document) -> BehaviorDocumentRef:
    return BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=_digest_bytes(canonical_ir_json(document).encode("ascii")),
    )


def _digest_bytes(content: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(content).hexdigest(),
    )


def _component_totals(
    components: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    return {
        "source_file_count": sum(item["source"]["file_count"] for item in components),
        "source_byte_count": sum(item["source"]["byte_count"] for item in components),
        "inventory_record_count": sum(
            item["inventory_record_count"] for item in components
        ),
        "candidate_count": sum(item["candidate_count"] for item in components),
        "false_candidate_count": sum(
            item["false_candidate_count"] for item in components
        ),
        "candidate_decision_count": sum(
            item["review_actions"]["candidate_decision_count"] for item in components
        ),
        "ambiguity_resolution_count": sum(
            item["review_actions"]["ambiguity_resolution_count"]
            for item in components
        ),
        "mapping_approval_count": sum(
            item["review_actions"]["mapping_approval_count"] for item in components
        ),
        "change_approval_count": 0,
        "eligible_interface_count": sum(
            item["coverage"]["eligible_interface_count"] for item in components
        ),
        "uncovered_interface_count": sum(
            item["coverage"]["uncovered_interface_count"] for item in components
        ),
        "unresolved_debt_count": sum(
            item["coverage"]["unresolved_debt_count"] for item in components
        ),
        "materialization_count": sum(
            item["materialization_count"] for item in components
        ),
        "mapping_binding_count": sum(
            item["mapping_binding_count"] for item in components
        ),
        "tested_claim_count": sum(item["claims"]["tested"] for item in components),
        "verified_claim_count": sum(item["claims"]["verified"] for item in components),
        "fresh_evidence_count": sum(
            item["claims"]["fresh_evidence"] for item in components
        ),
        "stale_evidence_count": sum(
            item["claims"]["stale_evidence"] for item in components
        ),
    }


def _runtime_phase_reports(
    runtime_samples: Mapping[tuple[str, str], Sequence[int]],
    *,
    repetitions: int,
) -> list[dict[str, object]]:
    if not runtime_samples:
        _fail(
            "missing_runtime",
            "benchmark runtime samples are required",
            location="$.runtime_samples",
        )
    reports = []
    for ecosystem, phase in sorted(runtime_samples):
        samples = list(runtime_samples[(ecosystem, phase)])
        if len(samples) != repetitions or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in samples
        ):
            _fail(
                "runtime_summary_mismatch",
                "runtime samples must be positive and complete",
                location=f"$.runtime_samples.{ecosystem}.{phase}",
            )
        reports.append(
            {
                "ecosystem": ecosystem,
                "phase": phase,
                "samples": samples,
                "minimum": min(samples),
                "median": int(statistics.median(samples)),
                "maximum": max(samples),
            }
        )
    return reports


def _object_digest(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _stable_verification_result_digest(result) -> str:
    projection = _stable_verification_result_projection(result)
    return _object_digest(projection["result"])


def _stable_verification_result_projection(result) -> dict[str, object]:
    if isinstance(result, Mapping):
        payload = json.loads(_canonical_json_bytes(result))
    else:
        payload = result.model_dump(mode="json")
    payload.pop("id")
    payload.pop("executed_at")
    return {
        "projection_version": "1.0.0",
        "result": payload,
    }


def _stable_lifecycle_digest(
    proposal,
    delta,
    tasks,
    implementation,
    verification,
    archive,
) -> str:
    resources = {
        "proposal": _lifecycle_payload(proposal),
        "delta": _lifecycle_payload(delta),
        "tasks": _lifecycle_payload(tasks),
        "implementation": _lifecycle_payload(implementation),
        "verification": _lifecycle_payload(verification),
        "archive": _lifecycle_payload(archive),
    }
    stable_implementation = resources["implementation"]
    for binding in stable_implementation["bindings"]:
        result_projection = _stable_verification_result_projection(
            binding["result"]
        )
        binding["result"] = result_projection
        binding["validation"]["result_digest"]["value"] = _object_digest(
            result_projection
        )
    implementation_digest = _object_digest(
        {
            "projection_version": "1.0.0",
            "implementation": stable_implementation,
        }
    )
    stable_verification = resources["verification"]
    stable_verification["implementation"]["canonical_digest"][
        "value"
    ] = implementation_digest
    verification_digest = _object_digest(
        {
            "projection_version": "1.0.0",
            "verification": stable_verification,
        }
    )
    stable_archive = resources["archive"]
    stable_archive["implementation"]["canonical_digest"][
        "value"
    ] = implementation_digest
    stable_archive["verification"]["canonical_digest"][
        "value"
    ] = verification_digest
    return _object_digest(
        {
            "projection_version": "1.0.0",
            "resources": resources,
        }
    )


def _lifecycle_payload(resource) -> dict[str, object]:
    if isinstance(resource, Mapping):
        return json.loads(_canonical_json_bytes(resource))
    return json.loads(canonical_change_lifecycle_json(resource))


def _stable_successor_digest(successor) -> str:
    payload = successor.model_dump(mode="json")
    entities = payload["entities"]
    runtime_provenance_ids = {
        entity["provenance"]["target_id"]
        for entity in entities
        if entity["kind"] == "verification_evidence"
    }
    payload["entities"] = [
        entity
        for entity in entities
        if entity["kind"] != "verification_evidence"
        and entity.get("id") not in runtime_provenance_ids
    ]
    return _object_digest(
        {
            "projection_version": "1.0.0",
            "behavior": payload,
        }
    )


def _stable_trust_digest(trust) -> str:
    payload = trust.model_dump(mode="json")
    subject_document = dict(payload["subject_document"])
    subject_document.pop("canonical_digest")
    claims = []
    for record in payload["records"]:
        if record["kind"] != "claim":
            continue
        subject = dict(record["subject"])
        subject.pop("canonical_digest")
        evidence = dict(record["basis"]["evidence"])
        evidence.pop("canonical_digest")
        evidence.pop("target_id")
        claims.append(
            {
                "kind": record["kind"],
                "level": record["level"],
                "subject": subject,
                "basis": {
                    "kind": record["basis"]["kind"],
                    "check": record["basis"]["check"],
                    "environment": record["basis"]["environment"],
                    "producer": record["basis"]["producer"],
                    "evidence": evidence,
                },
            }
        )
    return _object_digest(
        {
            "projection_version": "1.0.0",
            "trust_ir_version": payload["trust_ir_version"],
            "subject_document": subject_document,
            "claims": claims,
        }
    )


def _require_canonical(actual: str | bytes, payload: object) -> None:
    actual_bytes = actual.encode("ascii") if isinstance(actual, str) else actual
    if actual_bytes != _canonical_json_bytes(payload):
        _fail(
            "noncanonical_resource",
            "lane resource is not exact canonical UCF JSON",
            location="$.deterministic",
        )


def _parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or validate the REL-001 release benchmark."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="execute all external scenarios")
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--repetitions", type=int, default=3)
    run.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    check = commands.add_parser("check", help="validate a checked report")
    check.add_argument("--report", required=True, type=Path)
    verify = commands.add_parser(
        "verify-published",
        help="rerun all installed scenarios and compare checked evidence",
    )
    verify.add_argument("--report", required=True, type=Path)
    verify.add_argument("--repetitions", type=int, default=3)
    verify.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    compile_evidence = commands.add_parser(
        "compile-evidence",
        help="compile canonical lane evidence under the installed wheel",
    )
    compile_evidence.add_argument("--input", required=True, type=Path)
    compile_evidence.add_argument("--output", required=True, type=Path)
    return parser.parse_args(list(argv))


def _emit(payload: Mapping[str, object], *, stream) -> None:
    stream.write(_canonical_json_bytes(dict(payload)).decode("ascii"))
    stream.flush()


def _failure_receipt(
    *,
    phase: str,
    code: str,
    location: str = "$",
) -> dict[str, object]:
    return {
        "kind": "rel001_benchmark_failure",
        "report_version": REPORT_VERSION,
        "status": "failed",
        "phase": phase,
        "code": code,
        "location": location,
    }


def main(argv: Sequence[str] | None = None) -> int:
    phase = "argument_parsing"
    try:
        arguments = _parse_arguments(sys.argv[1:] if argv is None else argv)
        phase = arguments.command
        if arguments.command == "check":
            report = parse_report_json(arguments.report.read_bytes())
        elif arguments.command == "verify-published":
            accepted = parse_report_json(arguments.report.read_bytes())
            if __package__:
                from .rel001_benchmark_scenarios import collect_benchmark_report
            else:
                from rel001_benchmark_scenarios import collect_benchmark_report

            fresh = collect_benchmark_report(
                arguments.repository_root,
                repetitions=arguments.repetitions,
            )
            verify_published_report(accepted, fresh)
            report = accepted
        elif arguments.command == "compile-evidence":
            compiler_input = parse_compilation_input_json(arguments.input.read_bytes())
            report = compile_report_from_input(compiler_input)
            publish_report(arguments.output, report)
        else:
            if __package__:
                from .rel001_benchmark_scenarios import (
                    collect_benchmark_report,
                )
            else:
                from rel001_benchmark_scenarios import (
                    collect_benchmark_report,
                )

            report = collect_benchmark_report(
                arguments.repository_root,
                repetitions=arguments.repetitions,
            )
            publish_report(arguments.output, report)
    except BenchmarkValidationError as error:
        _emit(
            _failure_receipt(
                phase=phase,
                code=error.code,
                location=error.location,
            ),
            stream=sys.stderr,
        )
        return 3
    except OSError:
        _emit(
            _failure_receipt(phase=phase, code="os_error"),
            stream=sys.stderr,
        )
        return 3
    except ValueError:
        _emit(
            _failure_receipt(phase=phase, code="scenario_failure"),
            stream=sys.stderr,
        )
        return 3
    _emit(
        {
            "status": "PASS",
            "structural_digest": report["structural"]["digest"],
        },
        stream=sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
