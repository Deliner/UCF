from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from tools.package_contract import (
    EXPECTED_SCHEMA_ASSETS,
    EXPECTED_WHEEL_ASSETS,
    INSTALLED_ASSET_SMOKE,
    INSTALLED_CHANGE_GOVERNANCE_ASSERT,
    PackageContractError,
    _assert_go_stdlib_is_external,
    _assert_wheel_assets,
)
from tools.quality_gates import (
    PACKAGING_TOOL_INPUTS,
    PROFILES,
    Gate,
    affected_gates,
    main,
    profile_manifest,
    run_gates,
)

ROOT = Path(__file__).resolve().parents[2]


def test_run_gates_continues_after_failure_and_writes_complete_logs(tmp_path, capsys):
    gates = (
        Gate(
            name="first-pass",
            command=(sys.executable, "-c", "print('first output')"),
        ),
        Gate(
            name="middle-fail",
            command=(
                sys.executable,
                "-c",
                "print('failure output'); raise SystemExit(7)",
            ),
        ),
        Gate(
            name="last-pass",
            command=(sys.executable, "-c", "print('last output')"),
        ),
    )

    results = run_gates(gates, log_dir=tmp_path)

    assert [result.returncode for result in results] == [0, 7, 0]
    assert not all(result.passed for result in results)
    assert "first output" in (tmp_path / "first-pass.log").read_text()
    assert "failure output" in (tmp_path / "middle-fail.log").read_text()
    assert "last output" in (tmp_path / "last-pass.log").read_text()
    terminal_output = capsys.readouterr().out
    assert terminal_output.index("failure output") < terminal_output.index(
        "last output"
    )


@pytest.mark.parametrize("name", ["", "../escape", "not safe", "UPPER_CASE"])
def test_run_gates_rejects_unsafe_identity_before_writing(tmp_path, name):
    with pytest.raises(ValueError, match="gate identity"):
        run_gates(
            (Gate(name=name, command=(sys.executable, "-c", "print('ran')")),),
            log_dir=tmp_path,
        )

    assert list(tmp_path.iterdir()) == []


def test_run_gates_rejects_duplicate_identity_before_writing(tmp_path):
    duplicate = Gate(
        name="same-id",
        command=(sys.executable, "-c", "print('must not run')"),
    )

    with pytest.raises(ValueError, match="duplicate gate identity: same-id"):
        run_gates((duplicate, duplicate), log_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_machine_manifest_is_versioned_and_preserves_token_boundaries(capsys):
    assert main(["--profile", "all", "--list", "--format", "json"]) == 0

    manifest = json.loads(capsys.readouterr().out)
    assert manifest == profile_manifest("all", PROFILES["all"])
    assert manifest["schema_version"] == 1
    assert manifest["profile"] == "all"
    assert manifest["gates"][0] == {
        "id": "automation-tests",
        "command": [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pytest",
            "-q",
            "tests/automation",
            "--no-cov",
        ],
        "cwd": ".",
    }


def test_ci_selects_the_same_canonical_profile_as_local():
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text()
    normalized = " ".join(workflow.split())
    invocations = re.findall(
        r"python3 tools/quality_gates\.py "
        r"--profile ([a-z0-9-]+) "
        r"--log-dir \.artifacts/quality/ci",
        normalized,
    )

    assert invocations == ["all"]
    ci_manifest = profile_manifest(invocations[0], PROFILES[invocations[0]])
    local_manifest = profile_manifest("all", PROFILES["all"])
    assert ci_manifest == local_manifest
    for gate in PROFILES["all"]:
        assert " ".join(gate.command) not in normalized


def test_ci_actions_are_pinned_to_immutable_commits():
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text()
    action_references = re.findall(r"^\s*uses:\s*(\S+)", workflow, re.MULTILINE)

    assert action_references
    for reference in action_references:
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference), reference


def test_ci_pins_the_verified_node_runtime_and_caches_all_locked_projects():
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text()

    assert 'node-version: "22.22.3"' in workflow
    cache_paths = re.search(
        r"cache-dependency-path:\s*\|\n"
        r"((?:\s{10}[^\n]+\n)+)",
        workflow,
    )
    assert cache_paths is not None
    assert {
        line.strip()
        for line in cache_paths.group(1).splitlines()
    } == {
        "adapters/typescript-fastify/package-lock.json",
        "tests/fixtures/brownfield/"
        "typescript_fastify_legacy_quote/package-lock.json",
        "web/package-lock.json",
    }


def test_ci_installs_the_checksum_verified_go_runtime():
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text()

    assert 'GO_VERSION: "1.26.5"' in workflow
    assert (
        'GO_ARCHIVE_SHA256: '
        '"5c2c3b16caefa1d968a94c1daca04a7ca301a496d9b086e17ad77bb81393f053"'
        in workflow
    )
    assert (
        "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"
        in workflow
    )
    assert "sha256sum --check --strict" in workflow
    assert "UCF_GO_BIN=" in workflow
    assert "GITHUB_ENV" in workflow


def test_deliberate_failure_has_same_identity_for_local_and_ci(tmp_path):
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text()
    normalized = " ".join(workflow.split())
    [ci_profile] = re.findall(
        r"python3 tools/quality_gates\.py "
        r"--profile ([a-z0-9-]+) "
        r"--log-dir \.artifacts/quality/ci",
        normalized,
    )

    def deliberate_fixture(gate: Gate) -> Gate:
        return replace(
            gate,
            command=(
                sys.executable,
                "-c",
                "raise SystemExit(19)"
                if gate.name == "automation-tests"
                else "raise SystemExit(0)",
            ),
            working_directory=Path("."),
        )

    local = run_gates(
        tuple(deliberate_fixture(gate) for gate in PROFILES["all"]),
        log_dir=tmp_path / "local",
    )
    ci = run_gates(
        tuple(deliberate_fixture(gate) for gate in PROFILES[ci_profile]),
        log_dir=tmp_path / "ci",
    )

    for results in (local, ci):
        assert [result.gate.name for result in results if not result.passed] == [
            "automation-tests"
        ]
        assert [result.returncode for result in results if not result.passed] == [19]
    for selection in ("local", "ci"):
        failed_lines = [
            line
            for line in (tmp_path / selection / "summary.txt")
            .read_text()
            .splitlines()
            if line.startswith("FAIL")
        ]
        assert len(failed_lines) == 1
        assert "automation-tests" in failed_lines[0]
        assert failed_lines[0].endswith("exit=19")


def test_complete_profile_runs_the_packaging_contract():
    packaging_gates = [
        gate for gate in PROFILES["all"] if gate.name == "packaging-contract"
    ]

    assert len(packaging_gates) == 1
    assert packaging_gates[0].command == (
        "uv",
        "run",
        "--locked",
        "python",
        "tools/package_contract.py",
    )
    assert packaging_gates[0].working_directory == Path(".")


def test_complete_profile_keeps_eight_observable_unfiltered_gates():
    assert [gate.name for gate in PROFILES["all"]] == [
        "automation-tests",
        "python-tests",
        "python-lint",
        "spec-validation",
        "rel001-benchmark",
        "packaging-contract",
        "web-build",
        "web-lint",
    ]
    [python_tests] = [
        gate for gate in PROFILES["all"] if gate.name == "python-tests"
    ]
    assert "--capture=tee-sys" in python_tests.command
    for forbidden in ("-k", "--ignore", "--deselect"):
        assert forbidden not in python_tests.command
    assert not any(
        token.startswith("tests/") for token in python_tests.command
    )

    [benchmark] = [
        gate for gate in PROFILES["all"] if gate.name == "rel001-benchmark"
    ]
    assert benchmark.command == (
        "uv",
        "run",
        "--locked",
        "--extra",
        "dev",
        "python",
        "tools/rel001_benchmark.py",
        "verify-published",
        "--report",
        "docs/benchmarks/rel001-report.json",
        "--repetitions",
        "3",
    )


@pytest.mark.parametrize(
    "changed_path",
    [
        "tools/rel001_benchmark.py",
        "tools/rel001_benchmark_scenarios.py",
        "tools/installed_python_legacy_quote_smoke.py",
        "tools/installed_typescript_fastify_smoke.py",
        "tools/installed_go_stdlib_smoke.py",
        "tools/installed_go_stdlib_platform_smoke.py",
        "docs/benchmarks/rel001-report.json",
        "src/ucf/ir/codec.py",
        "adapters/typescript-fastify/src/main.ts",
        "tests/fixtures/brownfield/go_stdlib_legacy_quote/go.mod",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_benchmark_inputs_route_to_rel001_gate(changed_path):
    assert "rel001-benchmark" in {
        gate.name for gate in affected_gates((changed_path,))
    }


def test_packaging_contract_covers_behavior_and_trust_ir_boundaries():
    assert "ucf/schemas/ir/v1/schema.json" in EXPECTED_WHEEL_ASSETS
    assert "ucf/schemas/trust/v1/schema.json" in EXPECTED_WHEEL_ASSETS
    assert "urn:ucf:schema:ir:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:schema:trust-ir:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "parse_trust_ir_json" in INSTALLED_ASSET_SMOKE
    assert "canonical_trust_ir_json" in INSTALLED_ASSET_SMOKE
    assert "validate_trust_against_behavior" in INSTALLED_ASSET_SMOKE


def test_packaging_contract_covers_adapter_protocol_boundary():
    assert (
        "ucf/schemas/adapter_protocol/v1/schema.json"
        in EXPECTED_WHEEL_ASSETS
    )
    assert (
        "urn:ucf:schema:adapter-protocol:1.0.0"
        in INSTALLED_ASSET_SMOKE
    )
    assert "decode_request_frame" in INSTALLED_ASSET_SMOKE
    assert "AdapterDispatcher" in INSTALLED_ASSET_SMOKE
    assert "AdapterProcess" in INSTALLED_ASSET_SMOKE


def test_packaging_contract_covers_adapter_conformance_distribution():
    assert (
        "ucf/schemas/adapter_conformance/v1/schema.json"
        in EXPECTED_WHEEL_ASSETS
    )
    assert (
        "ucf/adapter_conformance/assets/v1/manifest.json"
        in EXPECTED_WHEEL_ASSETS
    )
    assert (
        "ucf/adapter_conformance/assets/v1/samples/reference_adapter.mjs"
        in EXPECTED_WHEEL_ASSETS
    )
    assert "urn:ucf:schema:adapter-conformance:1.0.0" in (
        INSTALLED_ASSET_SMOKE
    )
    assert "conformance_kit_index" in INSTALLED_ASSET_SMOKE
    assert "read_conformance_asset" in INSTALLED_ASSET_SMOKE


def test_packaging_contract_covers_deterministic_generation_distribution():
    generation_schemas = {
        "ucf/schemas/generation/v1/request.schema.json",
        "ucf/schemas/generation/v1/result.schema.json",
    }

    assert generation_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:generation:request:1.0.0",
        "urn:ucf:generation:result:1.0.0",
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_generation_request_json",
        "parse_generation_result_json",
        "canonical_generation_json",
    ):
        assert parser in INSTALLED_ASSET_SMOKE

    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    for required in (
        "_smoke_installed_generation",
        '(str(ucf), "generation", "run", "--help")',
        "adapters/python-pytest/adapter.py",
        "tests/fixtures/generation/v1/positive/request.json",
        "pytest==9.0.2",
        "PYTHONHASHSEED",
        "legacy_inventory.py",
        "generated tree changed across Python hash seeds",
        "dirty generated tree was overwritten",
    ):
        assert required in source


def test_packaging_contract_covers_installed_exact_evidence_loop():
    evidence_schemas = {
        "ucf/schemas/evidence_status/v1/envelope.schema.json",
        "ucf/schemas/evidence_status/v1/assessment.schema.json",
    }

    assert evidence_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:evidence-status:envelope:1.0.0",
        "urn:ucf:evidence-status:assessment:1.0.0",
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_verification_evidence_envelope_json",
        "parse_verification_evidence_assessment_json",
        "canonical_evidence_status_json",
        "validate_verification_evidence_assessment",
    ):
        assert parser in INSTALLED_ASSET_SMOKE

    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    for required in (
        "_smoke_installed_evidence_status",
        '(str(ucf), "evidence", "record", "--help")',
        '(str(ucf), "evidence", "assess", "--help")',
        "tests/fixtures/change_lifecycle/v1/context/execution-result.json",
        "assessment-stale",
        "environment_changed",
        "refreshed-envelope",
        "PYTHONHASHSEED",
        "installed evidence invalid publication changed prior output",
        "installed evidence failed verification publication changed prior output",
        "installed evidence partial current context changed prior output",
        "installed evidence concurrent publication replaced prior output",
        "installed evidence output changed across PYTHONHASHSEED",
    ):
        assert required in source


def test_packaging_contract_covers_exact_inventory_schema_boundary():
    inventory_schemas = {
        "ucf/schemas/inventory/v1/schema.json",
        "ucf/schemas/inventory/v1/request.schema.json",
        "ucf/schemas/inventory/v1/page.schema.json",
    }

    assert inventory_schemas <= EXPECTED_SCHEMA_ASSETS
    assert {
        path
        for path in EXPECTED_WHEEL_ASSETS
        if path.startswith("ucf/schemas/")
    } == EXPECTED_SCHEMA_ASSETS
    assert "urn:ucf:schema:inventory:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:adapter:inventory-request:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:adapter:inventory-page:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "parse_inventory_request_json" in INSTALLED_ASSET_SMOKE
    assert "canonical_inventory_json" in INSTALLED_ASSET_SMOKE
    assert "inventory_request_profile" in INSTALLED_ASSET_SMOKE
    assert "inventory_page" in INSTALLED_ASSET_SMOKE
    assert "inventory_snapshot" in INSTALLED_ASSET_SMOKE


def test_packaging_contract_covers_exact_onboarding_schema_boundary():
    onboarding_schemas = {
        "ucf/schemas/onboarding/v1/discovery-request.schema.json",
        "ucf/schemas/onboarding/v1/discovery-result.schema.json",
        "ucf/schemas/onboarding/v1/decision-set.schema.json",
        "ucf/schemas/onboarding/v1/bundle.schema.json",
    }

    assert onboarding_schemas <= EXPECTED_SCHEMA_ASSETS
    assert "urn:ucf:adapter:discovery-request:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:adapter:discovery-result:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:onboarding:decision-set:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:onboarding:bundle:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "parse_discovery_request_json" in INSTALLED_ASSET_SMOKE
    assert "parse_discovery_result_json" in INSTALLED_ASSET_SMOKE
    assert "parse_decision_set_json" in INSTALLED_ASSET_SMOKE
    assert "parse_onboarding_bundle_json" in INSTALLED_ASSET_SMOKE


def test_packaging_contract_runs_installed_onboarding_review_flow():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(source.split())

    assert '(str(ucf), "adapter", "discover", "--help")' in normalized
    assert '(str(ucf), "adapter", "onboard", "--help")' in normalized
    assert "INSTALLED_ONBOARDING_REVIEW" in source
    assert "python_legacy_quote" in source
    assert "fail-discovery" in source
    assert "stale_decisions" in source


def test_packaging_contract_covers_exact_ratchet_schema_boundary():
    ratchet_schemas = {
        "ucf/schemas/ratchet/v1/policy.schema.json",
        "ucf/schemas/ratchet/v1/assessment.schema.json",
        "ucf/schemas/ratchet/v1/baseline.schema.json",
        "ucf/schemas/ratchet/v1/evaluation-report.schema.json",
    }

    assert ratchet_schemas <= EXPECTED_SCHEMA_ASSETS
    assert "urn:ucf:ratchet:policy:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:ratchet:assessment:1.0.0" in INSTALLED_ASSET_SMOKE
    assert "urn:ucf:ratchet:baseline:1.0.0" in INSTALLED_ASSET_SMOKE
    assert (
        "urn:ucf:ratchet:evaluation-report:1.0.0"
        in INSTALLED_ASSET_SMOKE
    )
    assert "parse_ratchet_policy_json" in INSTALLED_ASSET_SMOKE
    assert "parse_ratchet_assessment_json" in INSTALLED_ASSET_SMOKE
    assert "parse_ratchet_baseline_json" in INSTALLED_ASSET_SMOKE
    assert (
        "parse_ratchet_evaluation_report_json"
        in INSTALLED_ASSET_SMOKE
    )


def test_packaging_contract_covers_parallel_ratchet_v2_schema_boundary():
    ratchet_v1_schemas = {
        "ucf/schemas/ratchet/v1/policy.schema.json",
        "ucf/schemas/ratchet/v1/assessment.schema.json",
        "ucf/schemas/ratchet/v1/baseline.schema.json",
        "ucf/schemas/ratchet/v1/evaluation-report.schema.json",
    }
    ratchet_v2_schemas = {
        "ucf/schemas/ratchet/v2/policy.schema.json",
        "ucf/schemas/ratchet/v2/assessment.schema.json",
        "ucf/schemas/ratchet/v2/baseline.schema.json",
        "ucf/schemas/ratchet/v2/evaluation-report.schema.json",
    }

    assert ratchet_v1_schemas.isdisjoint(ratchet_v2_schemas)
    assert ratchet_v2_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:ratchet:policy:2.0.0",
        "urn:ucf:ratchet:assessment:2.0.0",
        "urn:ucf:ratchet:baseline:2.0.0",
        "urn:ucf:ratchet:evaluation-report:2.0.0",
        '"x-ucf-ratchet-version"',
        '"2.0.0"',
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_ratchet_policy_json_v2",
        "parse_ratchet_assessment_json_v2",
        "parse_ratchet_baseline_json_v2",
        "parse_ratchet_evaluation_report_json_v2",
    ):
        assert parser in INSTALLED_ASSET_SMOKE
    for marker in (
        "from ucf.ratchet.v2 import (",
        "RatchetPolicyV2",
        "RatchetRuleV2",
        "RatchetEvaluatorSelectionV2",
        "canonical_ratchet_json_v2",
        "derive_policy_id_v2",
        "ratchet-v2-schemas=",
    ):
        assert marker in INSTALLED_ASSET_SMOKE


def test_packaging_contract_runs_installed_ratchet_transaction():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(source.split())

    for verb in ("establish", "evaluate", "advance"):
        assert (
            f'(str(ucf), "ratchet", "{verb}", "--help")'
            in normalized
        )
    assert "INSTALLED_RATCHET_AUTHOR" in source
    assert "_smoke_installed_ratchet" in source
    assert "ratchet-regression-report" in source
    assert "ratchet-successor-sentinel" in source
    assert "expected_returncode=1" in source


def test_packaging_contract_runs_installed_ratchet_v2_transaction():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    scripts = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance((target := node.targets[0]), ast.Name)
        and target.id
        in {
            "INSTALLED_RATCHET_V2_AUTHOR",
            "INSTALLED_RATCHET_V2_ASSERT",
        }
    }

    assert set(scripts) == {
        "INSTALLED_RATCHET_V2_AUTHOR",
        "INSTALLED_RATCHET_V2_ASSERT",
    }
    assert all("tests." not in script for script in scripts.values())
    for required in (
        "_smoke_installed_ratchet_v2",
        "_ratchet_v2_cli_command",
        'operation="establish"',
        'operation="evaluate"',
        'operation="advance"',
        '"migrate-from-v1"',
        '"--accepted-baseline-id"',
        '"--accepted-source-baseline-id"',
        "MAX_INSTALLED_RATCHET_DOCUMENT_BYTES",
        "PASS_WITH_LEGACY_COVERAGE_DEBT",
        "MIGRATED_V1",
    ):
        assert required in source


def test_packaging_contract_covers_exact_runtime_evidence_schemas():
    runtime_evidence_schemas = {
        "ucf/schemas/runtime_evidence/v1/policy.schema.json",
        "ucf/schemas/runtime_evidence/v1/environment.schema.json",
        "ucf/schemas/runtime_evidence/v1/request.schema.json",
        "ucf/schemas/runtime_evidence/v1/result.schema.json",
    }

    assert runtime_evidence_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:runtime-evidence:policy:1.0.0",
        "urn:ucf:runtime-evidence:environment:1.0.0",
        "urn:ucf:adapter:runtime-evidence-request:1.0.0",
        "urn:ucf:adapter:runtime-evidence-result:1.0.0",
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_runtime_evidence_policy_json",
        "parse_runtime_environment_json",
        "parse_runtime_evidence_request_json",
        "parse_runtime_evidence_result_json",
    ):
        assert parser in INSTALLED_ASSET_SMOKE


def test_packaging_contract_covers_exact_implementation_evidence_schemas():
    implementation_evidence_schemas = {
        "ucf/schemas/implementation_evidence/v1/mapping-request.schema.json",
        "ucf/schemas/implementation_evidence/v1/mapping-result.schema.json",
        "ucf/schemas/implementation_evidence/v1/verification-request.schema.json",
        "ucf/schemas/implementation_evidence/v1/verification-result.schema.json",
    }

    assert implementation_evidence_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:adapter:implementation-mapping-request:1.0.0",
        "urn:ucf:adapter:implementation-mapping-result:1.0.0",
        "urn:ucf:adapter:execution-verification-request:1.0.0",
        "urn:ucf:adapter:execution-verification-result:1.0.0",
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_implementation_mapping_request_json",
        "parse_implementation_mapping_result_json",
        "parse_execution_verification_request_json",
        "parse_execution_verification_result_json",
    ):
        assert parser in INSTALLED_ASSET_SMOKE


def test_packaging_contract_covers_and_runs_change_lifecycle():
    lifecycle_schemas = {
        "ucf/schemas/change_lifecycle/v1/proposal.schema.json",
        "ucf/schemas/change_lifecycle/v1/behavior-delta.schema.json",
        "ucf/schemas/change_lifecycle/v1/task-graph.schema.json",
        "ucf/schemas/change_lifecycle/v1/implementation-record.schema.json",
        "ucf/schemas/change_lifecycle/v1/verification-record.schema.json",
        "ucf/schemas/change_lifecycle/v1/archive-record.schema.json",
    }

    assert lifecycle_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:change-lifecycle:proposal:1.0.0",
        "urn:ucf:change-lifecycle:behavior-delta:1.0.0",
        "urn:ucf:change-lifecycle:task-graph:1.0.0",
        "urn:ucf:change-lifecycle:implementation-record:1.0.0",
        "urn:ucf:change-lifecycle:verification-record:1.0.0",
        "urn:ucf:change-lifecycle:archive-record:1.0.0",
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_change_proposal_json",
        "parse_behavior_delta_json",
        "parse_task_graph_json",
        "parse_implementation_record_json",
        "parse_verification_record_json",
        "parse_archive_record_json",
    ):
        assert parser in INSTALLED_ASSET_SMOKE

    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(source.split())
    for verb in (
        "import-openspec",
        "export-openspec",
        "derive-delta",
        "derive-tasks",
        "complete-task",
        "record-implementation",
        "verify",
        "archive",
    ):
        assert (
            f'(str(ucf), "change", "{verb}", "--help")'
            in normalized
        )
    for required in (
        "_smoke_installed_change",
        "openspec-spec-driven-1",
        "PYTHONHASHSEED",
        "change-archive.json",
    ):
        assert required in source


def test_packaging_contract_covers_and_runs_change_governance():
    governance_schemas = {
        "ucf/schemas/change_governance/v1/impact-report.schema.json",
        "ucf/schemas/change_governance/v1/decision-assessment.schema.json",
        "ucf/schemas/change_governance/v1/decision-declaration.schema.json",
        "ucf/schemas/change_governance/v1/gate-evaluation.schema.json",
    }

    assert governance_schemas <= EXPECTED_SCHEMA_ASSETS
    for coordinate in (
        "urn:ucf:change-governance:impact-report:1.0.0",
        "urn:ucf:change-governance:decision-assessment:1.0.0",
        "urn:ucf:change-governance:decision-declaration:1.0.0",
        "urn:ucf:change-governance:gate-evaluation:1.0.0",
    ):
        assert coordinate in INSTALLED_ASSET_SMOKE
    for parser in (
        "parse_impact_report_json",
        "parse_decision_assessment_json",
        "parse_decision_declaration_json",
        "parse_gate_evaluation_json",
    ):
        assert parser in INSTALLED_ASSET_SMOKE

    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    for required in (
        "_smoke_installed_change_governance",
        "PYTHONHASHSEED",
        "blocked-gate-sentinel.json",
        "expected_returncode=1",
    ):
        assert required in source
    for expected in (
        "CompatibilityOutcome.COMPATIBLE",
        "GateStatus.PASS_NO_DECISION",
        "CompatibilityOutcome.BREAKING",
        "GateStatus.PASS_APPROVED",
    ):
        assert expected in INSTALLED_CHANGE_GOVERNANCE_ASSERT


def test_change_governance_generator_routes_to_packaging_contract():
    generator = "tools/generate_change_governance_schema.py"

    assert generator in PACKAGING_TOOL_INPUTS
    assert "packaging-contract" in {
        gate.name for gate in affected_gates((generator,))
    }


def test_generation_contract_generators_route_to_packaging_contract():
    generators = (
        "tools/generate_generation_schema.py",
        "tests/generation/_fixture_factory.py",
    )

    assert set(generators) <= PACKAGING_TOOL_INPUTS
    for generator in generators:
        assert "packaging-contract" in {
            gate.name for gate in affected_gates((generator,))
        }


def test_ratchet_v2_schema_generator_routes_to_packaging_contract():
    generator = "tools/generate_ratchet_v2_schema.py"

    assert generator in PACKAGING_TOOL_INPUTS
    assert "packaging-contract" in {
        gate.name for gate in affected_gates((generator,))
    }


def test_packaging_contract_runs_installed_runtime_evidence_transaction():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(source.split())

    assert (
        '(str(ucf), "adapter", "import-runtime-evidence", "--help")'
        in normalized
    )
    for required in (
        "INSTALLED_RUNTIME_EVIDENCE_ASSERT",
        "_smoke_installed_runtime_evidence",
        "runtime_evidence_reference_adapter.py",
        "recorded_trace_v1",
        "PYTHONHASHSEED",
        "selected-secret",
        "project_runtime_evidence_to_trust",
    ):
        assert required in source


def test_private_typescript_adapter_has_a_closed_local_tarball_contract():
    package = json.loads(
        (
            ROOT
            / "adapters"
            / "typescript-fastify"
            / "package.json"
        ).read_text(encoding="utf-8")
    )

    assert package["name"] == "@ucf/typescript-fastify-adapter"
    assert package["version"] == "1.0.0"
    assert package["private"] is True
    assert package["files"] == ["dist"]
    assert package["bin"] == {
        "ucf-typescript-fastify-adapter": "dist/main.js"
    }
    assert package["engines"] == {"node": "22.x", "npm": "10.x"}
    assert package["packageManager"] == "npm@10.9.8"
    for runtime_dependencies in (
        "dependencies",
        "optionalDependencies",
        "peerDependencies",
        "bundledDependencies",
    ):
        assert not package.get(runtime_dependencies)


def test_packaging_contract_runs_installed_wheel_with_local_adapter_tarball():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )

    for required in (
        "typescript_fastify_adapter_contract",
        "npm pack",
        "--ignore-scripts",
        "--offline",
        "installed_typescript_fastify_smoke.py",
        "UCF_TYPESCRIPT_FASTIFY_FIXTURE_ROOT",
    ):
        assert required in source


def test_packaging_contract_runs_reproducible_external_go_distribution():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )

    for required in (
        "go_stdlib_adapter_contract",
        "_prepare_installed_go_stdlib_adapter",
        "_smoke_installed_go_stdlib",
        "ucf-go-stdlib-adapter",
        "legacy-quote-server",
        "-ldflags=-buildid=",
        "go version -m",
        "--conformance",
    ):
        assert required in source


def test_packaging_contract_closes_and_runs_the_external_go_platform():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    required_contract_calls = {
        "copy_go_stdlib_platform_fixture",
        "go_stdlib_platform_manifest",
    }
    imported_contract_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "go_stdlib_platform_contract"
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }

    assert required_contract_calls <= imported_contract_names
    assert required_contract_calls <= called_names

    platform_smokes = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        constants = {
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant)
            and isinstance(child.value, str)
        }
        if "installed_go_stdlib_platform_smoke.py" in constants:
            platform_smokes.append(node)

    assert len(platform_smokes) == 1
    [platform_smoke] = platform_smokes
    platform_smoke_calls = [
        node
        for node in ast.walk(platform_smoke)
        if isinstance(node, ast.Call)
    ]
    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "_copy_stable_driver"
        for call in platform_smoke_calls
    )
    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "_run"
        and "--platform-fixture-executable"
        in {
            child.value
            for child in ast.walk(call)
            if isinstance(child, ast.Constant)
            and isinstance(child.value, str)
        }
        for call in platform_smoke_calls
    )


def test_packaging_contract_requires_clean_installed_rel001_lane_evidence():
    source = (ROOT / "tools" / "package_contract.py").read_text(
        encoding="utf-8"
    )

    for required in (
        "_smoke_installed_python_legacy_quote",
        "installed_python_legacy_quote_smoke.py",
        "_read_installed_rel001_lane_evidence",
        '"--evidence-output"',
        'expected_lane="python"',
        'expected_lane="typescript_fastify"',
        'expected_lane="go_http"',
        'expected_lane="go_platform"',
        'expected_transports=()',
        'expected_transports=("http",)',
        'expected_transports=("cli", "event")',
        'metrics["verified_claim_count"] != 0',
    ):
        assert required in source


@pytest.mark.parametrize(
    "binary_name",
    [
        "ucf-go-stdlib-adapter",
        "legacy-quote-server",
        "legacy-platforms",
    ],
)
def test_wheel_rejects_root_level_external_go_binary(
    tmp_path: Path,
    binary_name: str,
) -> None:
    wheel = tmp_path / "leaking.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(binary_name, b"external binary")

    with pytest.raises(PackageContractError, match="leaked"):
        _assert_go_stdlib_is_external(wheel)


def test_wheel_rejects_unexpected_evidence_fixture_asset(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "leaking.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for asset in EXPECTED_WHEEL_ASSETS:
            archive.writestr(asset, b"expected")
        archive.writestr(
            "ucf/hidden-fixtures/evidence-context.json",
            b'{"kind":"hidden-evidence-context"}',
        )

    with pytest.raises(PackageContractError, match="asset inventory"):
        _assert_wheel_assets(wheel)


def test_python_lint_covers_the_project_hook_source():
    [python_lint] = [
        gate for gate in PROFILES["all"] if gate.name == "python-lint"
    ]

    assert python_lint.command[-1] == ".codex/hooks/stop_quality.py"


def test_project_environment_gates_require_the_checked_lockfile():
    project_gates = [
        gate for gate in PROFILES["all"] if gate.command[:2] == ("uv", "run")
    ]

    assert project_gates
    for gate in project_gates:
        assert gate.command[2] == "--locked", gate.name


def test_build_backend_version_is_an_exact_reviewable_input():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert configuration["build-system"]["requires"] == ["hatchling==1.31.0"]
