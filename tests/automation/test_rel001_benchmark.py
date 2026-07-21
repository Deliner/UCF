from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "rel001_benchmark.py"


def _load_module():
    specification = importlib.util.spec_from_file_location(
        "rel001_benchmark",
        MODULE_PATH,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _component(
    component_id: str,
    *,
    records: int,
    candidates: int,
    accepted: int,
    edited: int,
    rejected: int,
    uncertain: int,
    eligible: int,
    uncovered: int,
    materializations: int,
    bindings: int,
    tested: int,
    transports: list[str],
) -> dict[str, object]:
    return {
        "id": component_id,
        "source": {
            "file_count": 1,
            "byte_count": 100,
            "manifest_digest": "a" * 64,
        },
        "inventory_record_count": records,
        "candidate_count": candidates,
        "false_candidate_count": edited + rejected,
        "dispositions": {
            "accepted": accepted,
            "edited": edited,
            "rejected": rejected,
            "uncertain": uncertain,
        },
        "coverage": {
            "eligible_interface_count": eligible,
            "uncovered_interface_count": uncovered,
            "unresolved_debt_count": uncovered + uncertain,
        },
        "materialization_count": materializations,
        "mapping_binding_count": bindings,
        "review_actions": {
            "candidate_decision_count": candidates,
            "ambiguity_resolution_count": edited,
            "mapping_approval_count": 0,
        },
        "claims": {
            "observed": materializations,
            "declared": materializations,
            "mapped": 0,
            "tested": tested,
            "verified": 0,
            "fresh_evidence": tested,
            "stale_evidence": 0,
        },
        "ratchet": {
            "baseline_outcome": "pass_with_legacy_coverage_debt",
            "unchanged_outcome": "pass_with_legacy_coverage_debt",
            "coverage_debt_count": uncovered + uncertain,
        },
        "transports": transports,
        "structural_digest": "b" * 64,
    }


def _report_payload(module) -> dict[str, object]:
    components = {
        "python": _component(
            "python_legacy_quote",
            records=24,
            candidates=4,
            accepted=1,
            edited=1,
            rejected=1,
            uncertain=1,
            eligible=4,
            uncovered=0,
            materializations=2,
            bindings=1,
            tested=1,
            transports=[],
        ),
        "typescript": _component(
            "typescript_fastify_legacy_quote",
            records=42,
            candidates=4,
            accepted=1,
            edited=0,
            rejected=3,
            uncertain=0,
            eligible=6,
            uncovered=2,
            materializations=1,
            bindings=1,
            tested=1,
            transports=["http"],
        ),
        "go_http": _component(
            "go_stdlib_legacy_quote",
            records=51,
            candidates=4,
            accepted=1,
            edited=0,
            rejected=2,
            uncertain=1,
            eligible=12,
            uncovered=8,
            materializations=1,
            bindings=1,
            tested=1,
            transports=["http"],
        ),
        "go_platform": _component(
            "go_stdlib_legacy_platforms",
            records=62,
            candidates=1,
            accepted=1,
            edited=0,
            rejected=0,
            uncertain=0,
            eligible=9,
            uncovered=8,
            materializations=1,
            bindings=1,
            tested=2,
            transports=["cli", "event"],
        ),
    }
    structural = {
        "ecosystems": [
            {
                "id": "python",
                "components": [components["python"]],
            },
            {
                "id": "typescript_fastify",
                "components": [components["typescript"]],
            },
            {
                "id": "go",
                "components": [
                    components["go_http"],
                    components["go_platform"],
                ],
            },
        ],
        "totals": {
            "source_file_count": 4,
            "source_byte_count": 400,
            "inventory_record_count": 179,
            "candidate_count": 13,
            "false_candidate_count": 7,
            "candidate_decision_count": 13,
            "ambiguity_resolution_count": 1,
            "mapping_approval_count": 0,
            "change_approval_count": 0,
            "eligible_interface_count": 31,
            "uncovered_interface_count": 18,
            "unresolved_debt_count": 20,
            "materialization_count": 5,
            "mapping_binding_count": 4,
            "tested_claim_count": 5,
            "verified_claim_count": 0,
            "fresh_evidence_count": 5,
            "stale_evidence_count": 0,
        },
        "digest": "0" * 64,
    }
    structural["digest"] = module.derive_structural_digest(structural)
    report = {
        "kind": "rel001_benchmark_report",
        "report_version": "1.0.0",
        "status": "passed",
        "identities": {
            "ucf_version": module.ucf.__version__,
            "python_version": "3.14.1",
            "python_implementation": "CPython",
            "adapter_protocol_version": "1.0.0",
            "adapter_conformance_kit_version": "1.0.0",
            "ratchet_version": "2.0.0",
            "repetitions": 3,
            "wheel_sha256": "d" * 64,
            "runtime_lock_sha256": "5" * 64,
            "installed_environment_sha256": "0" * 64,
            "installed_distributions": {
                "networkx": "3.6.1",
                "pydantic": "2.12.5",
                "ucf": module.ucf.__version__,
            },
            "host_platform": {
                "system": "Linux",
                "architecture": "x86_64",
            },
            "adapters": {
                "python": "org.ucf.inventory-reference-adapter@1.0.0",
                "typescript_fastify": (
                    "org.ucf.adapter.typescript-fastify@1.0.0"
                ),
                "go": "org.ucf.adapter.go-stdlib@1.0.0",
            },
            "adapter_artifact_digests": {
                "python": "e" * 64,
                "typescript_fastify": "f" * 64,
                "go": "1" * 64,
            },
            "driver_artifact_digests": {
                "python": "7" * 64,
                "typescript_fastify": "8" * 64,
                "go_http": "9" * 64,
                "go_platform": "a" * 64,
            },
            "benchmark_tool_digests": {
                "compiler": "b" * 64,
                "scenarios": "c" * 64,
                "go_adapter_contract": "d" * 64,
                "go_platform_contract": "e" * 64,
                "go_toolchain": "f" * 64,
                "typescript_contract": "1" * 64,
            },
            "conformance_report_digests": {
                "python": "2" * 64,
                "typescript_fastify": "3" * 64,
                "go": "4" * 64,
            },
            "toolchains": {
                "node": "v22.22.3",
                "npm": "10.9.8",
                "go": "go1.26.5 linux/amd64",
            },
        },
        "structural": structural,
        "runtime": {
            "unit": "nanoseconds",
            "phases": [
                {
                    "ecosystem": ecosystem,
                    "phase": phase,
                    "samples": [10, 20, 30],
                    "minimum": 10,
                    "median": 20,
                    "maximum": 30,
                }
                for ecosystem in (
                    "go_http",
                    "go_platform",
                    "python",
                    "typescript_fastify",
                )
                for phase in (
                    "copy_source",
                    "manifest_recheck",
                    "native_post",
                    "native_pre",
                    "workflow",
                )
            ],
        },
        "overhead": {
            "accounting_version": "1.0.0",
            "definitions": {
                "authored_bytes": (
                    "Canonical bytes of explicit decisions, policy, and change "
                    "proposal resources."
                ),
                "derived_bytes": (
                    "Canonical bytes of generated UCF resources and evidence."
                ),
                "record_count": "One count per top-level canonical resource.",
                "allocation": (
                    "Fixture resources are allocated to their component; shared "
                    "policy and lifecycle resources remain separate."
                ),
            },
            "components": [
                {
                    "id": component["id"],
                    "legacy_source_bytes": component["source"]["byte_count"],
                    "authored_bytes": 100,
                    "authored_records": 1,
                    "derived_bytes": 1000,
                    "derived_records": 10,
                }
                for component in (
                    components["python"],
                    components["typescript"],
                    components["go_http"],
                    components["go_platform"],
                )
            ],
            "shared_policy": {
                "authored_bytes": 100,
                "authored_records": 1,
                "derived_bytes": 0,
                "derived_records": 0,
            },
            "change_lifecycle": {
                "authored_bytes": 100,
                "authored_records": 1,
                "derived_bytes": 1000,
                "derived_records": 5,
            },
            "totals": {
                "legacy_source_bytes": 400,
                "authored_bytes": 600,
                "authored_records": 6,
                "derived_bytes": 5000,
                "derived_records": 45,
                "authored_to_legacy": {
                    "numerator": 600,
                    "denominator": 400,
                },
                "derived_to_legacy": {
                    "numerator": 5000,
                    "denominator": 400,
                },
            },
        },
        "change_lifecycle": {
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
            "structural_digest": "c" * 64,
        },
        "limitations": [
            {
                "id": "scripted-review-not-human-effort",
                "owner": "UCF maintainers",
                "statement": (
                    "Review actions are counted; no human review duration "
                    "or usability claim is made."
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
        ],
    }
    report["identities"]["installed_environment_sha256"] = module._object_digest(
        report["identities"]["installed_distributions"]
    )
    return report


def test_report_codec_is_closed_canonical_and_contextually_valid() -> None:
    module = _load_module()
    payload = _report_payload(module)

    encoded = module.canonical_report_json(payload)

    assert encoded.endswith(b"\n")
    assert module.parse_report_json(encoded) == payload
    assert module.canonical_report_json(module.parse_report_json(encoded)) == encoded


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda payload: payload.update({"unknown": True}), "unknown_field"),
        (
            lambda payload: payload["structural"]["totals"].update(
                {"verified_claim_count": 1}
            ),
            "summary_mismatch",
        ),
        (
            lambda payload: payload["runtime"]["phases"][0].update({"median": 21}),
            "runtime_summary_mismatch",
        ),
        (
            lambda payload: payload["limitations"][0].update(
                {"owner": "/tmp/benchmark-owner"}
            ),
            "path_leak",
        ),
        (
            lambda payload: payload["limitations"][0].update(
                {"owner": "reviewed at /home/alice/private/report.json"}
            ),
            "path_leak",
        ),
        (
            lambda payload: payload["limitations"][0].update(
                {"owner": r"C:\Users\alice\private\report.json"}
            ),
            "path_leak",
        ),
        (
            lambda payload: payload["identities"].update(
                {"ratchet_version": "999.0.0"}
            ),
            "unsupported_version",
        ),
    ],
)
def test_report_rejects_invalid_claims_summaries_and_path_leaks(
    mutation,
    expected_code: str,
) -> None:
    module = _load_module()
    payload = _report_payload(module)
    mutation(payload)

    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.canonical_report_json(payload)

    assert captured.value.code == expected_code


def test_report_rejects_incomplete_runtime_matrix() -> None:
    module = _load_module()
    payload = _report_payload(module)
    payload["runtime"]["phases"].pop()

    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.canonical_report_json(payload)

    assert captured.value.code == "runtime_matrix_mismatch"


def test_report_rejects_transport_misattribution() -> None:
    module = _load_module()
    payload = _report_payload(module)
    structural = payload["structural"]
    python = structural["ecosystems"][0]["components"][0]
    typescript = structural["ecosystems"][1]["components"][0]
    python["transports"] = ["http"]
    typescript["transports"] = []
    structural["digest"] = module.derive_structural_digest(structural)

    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.canonical_report_json(payload)

    assert captured.value.code == "transport_evidence_mismatch"


def test_report_rejects_unbacked_claim_and_approval_counts() -> None:
    module = _load_module()
    original = _report_payload(module)
    mutations = (
        lambda payload: payload["structural"]["ecosystems"][0]["components"][0][
            "claims"
        ].update({"mapped": 999}),
        lambda payload: payload["structural"]["ecosystems"][0]["components"][0][
            "review_actions"
        ].update({"mapping_approval_count": 1}),
    )

    for mutation in mutations:
        payload = copy.deepcopy(original)
        mutation(payload)
        payload["structural"]["digest"] = module.derive_structural_digest(
            payload["structural"]
        )
        with pytest.raises(module.BenchmarkValidationError):
            module.canonical_report_json(payload)


def test_report_rejects_arbitrary_per_fixture_overhead() -> None:
    module = _load_module()
    payload = _report_payload(module)
    payload["overhead"]["components"][0]["legacy_source_bytes"] = 101

    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.canonical_report_json(payload)

    assert captured.value.code == "overhead_summary_mismatch"


def test_published_replay_ignores_only_runtime_samples() -> None:
    module = _load_module()
    accepted = _report_payload(module)
    fresh = copy.deepcopy(accepted)
    fresh["runtime"]["phases"][0]["samples"] = [11, 21, 31]
    fresh["runtime"]["phases"][0].update(
        {"minimum": 11, "median": 21, "maximum": 31}
    )

    module.verify_published_report(accepted, fresh)

    fresh["identities"]["driver_artifact_digests"]["python"] = "f" * 64
    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.verify_published_report(accepted, fresh)
    assert captured.value.code == "published_report_drift"


def test_lifecycle_projection_ignores_runtime_identity_not_semantics() -> None:
    module = _load_module()
    fixture = ROOT / "tests" / "fixtures" / "change_lifecycle" / "v1"
    names = (
        "proposal.json",
        "behavior-delta.json",
        "task-graph.json",
        "implementation-record.json",
        "verification-record.json",
        "archive-record.json",
    )
    resources = tuple(
        json.loads((fixture / "positive" / name).read_text(encoding="utf-8"))
        for name in names
    )
    runtime_variant = copy.deepcopy(resources)
    implementation = runtime_variant[3]
    verification = runtime_variant[4]
    archive = runtime_variant[5]
    result = implementation["bindings"][0]["result"]
    result["id"] = "result." + ("f" * 64)
    result["executed_at"] = "2026-07-21T12:34:56Z"
    implementation["bindings"][0]["validation"]["result_digest"][
        "value"
    ] = "1" * 64
    verification["implementation"]["canonical_digest"]["value"] = "2" * 64
    archive["implementation"]["canonical_digest"]["value"] = "3" * 64
    archive["verification"]["canonical_digest"]["value"] = "4" * 64

    accepted = module._stable_lifecycle_digest(*resources)
    assert module._stable_lifecycle_digest(*runtime_variant) == accepted

    semantic_variant = copy.deepcopy(runtime_variant)
    semantic_variant[3]["bindings"][0]["result"]["outcome"] = "failed"
    assert module._stable_lifecycle_digest(*semantic_variant) != accepted


def test_failure_receipt_is_closed_versioned_and_path_free(tmp_path, capsys) -> None:
    module = _load_module()
    missing = tmp_path / "private" / "missing-report.json"

    assert module.main(["check", "--report", str(missing)]) == 3

    receipt = json.loads(capsys.readouterr().err)
    assert receipt == {
        "code": "os_error",
        "kind": "rel001_benchmark_failure",
        "location": "$",
        "phase": "check",
        "report_version": "1.0.0",
        "status": "failed",
    }
    assert str(tmp_path) not in json.dumps(receipt)


def test_report_parser_rejects_duplicate_keys() -> None:
    module = _load_module()
    payload = _report_payload(module)
    encoded = module.canonical_report_json(payload)
    duplicate = encoded.replace(
        b'"kind":"rel001_benchmark_report"',
        b'"kind":"rel001_benchmark_report","kind":"rel001_benchmark_report"',
        1,
    )

    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.parse_report_json(duplicate)

    assert captured.value.code == "duplicate_field"


def test_report_publication_is_no_replace_and_cleans_temporary_files(
    tmp_path: Path,
) -> None:
    module = _load_module()
    payload = _report_payload(module)
    output = tmp_path / "report.json"

    module.publish_report(output, payload)
    accepted = output.read_bytes()

    with pytest.raises(module.BenchmarkValidationError) as captured:
        module.publish_report(output, payload)

    assert captured.value.code == "output_exists"
    assert output.read_bytes() == accepted
    assert list(tmp_path.glob(".report.json.*.tmp")) == []


def test_checked_report_is_exactly_canonical_when_published() -> None:
    module = _load_module()
    report = ROOT / "docs" / "benchmarks" / "rel001-report.json"
    if not report.exists():
        pytest.fail("REL-001 checked benchmark report has not been published")

    payload = module.parse_report_json(report.read_bytes())

    assert report.read_bytes() == module.canonical_report_json(payload)
    assert payload["status"] == "passed"
    assert payload["structural"]["totals"]["verified_claim_count"] == 0
    assert {
        transport
        for ecosystem in payload["structural"]["ecosystems"]
        for component in ecosystem["components"]
        for transport in component["transports"]
    } == {"http", "cli", "event"}
