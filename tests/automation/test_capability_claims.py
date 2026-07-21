"""Executable checks for the public capability/status contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs" / "CAPABILITIES.md"
BACKLOG_PATH = ROOT / "docs" / "automation" / "BACKLOG.md"
ADAPTER_CONFORMANCE_PATH = ROOT / "docs" / "ADAPTER_CONFORMANCE.md"
INVENTORY_PATH = ROOT / "docs" / "INVENTORY.md"
ONBOARDING_PATH = ROOT / "docs" / "ONBOARDING.md"
RATCHET_PATH = ROOT / "docs" / "RATCHET.md"
RUNTIME_EVIDENCE_PATH = ROOT / "docs" / "RUNTIME_EVIDENCE.md"
EVIDENCE_STATUS_PATH = ROOT / "docs" / "EVIDENCE_STATUS.md"
CHANGE_LIFECYCLE_PATH = ROOT / "docs" / "CHANGE_LIFECYCLE.md"
GENERATION_PATH = ROOT / "docs" / "GENERATION.md"
REL001_BENCHMARK_PATH = ROOT / "docs" / "benchmarks" / "REL-001.md"
TYPESCRIPT_FASTIFY_ADAPTER_PATH = (
    ROOT / "adapters" / "typescript-fastify" / "README.md"
)
GO_STDLIB_ADAPTER_PATH = ROOT / "adapters" / "go-stdlib" / "README.md"

CURRENT_CLAIM_DOCS = (
    "README.md",
    "SPEC_LANGUAGE.md",
    "GENERATORS.md",
    "DEPENDENCY_GRAPH.md",
    "CONTEXT_TRACER.md",
    "INVARIANTS.md",
    "docs/ADAPTER_PROTOCOL.md",
    "docs/ADAPTER_CONFORMANCE.md",
    "docs/INVENTORY.md",
    "docs/ONBOARDING.md",
    "docs/RATCHET.md",
    "docs/RUNTIME_EVIDENCE.md",
    "docs/EVIDENCE_STATUS.md",
    "docs/CHANGE_LIFECYCLE.md",
    "docs/GENERATION.md",
    "adapters/python-pytest/README.md",
    "adapters/typescript-fastify/README.md",
    "adapters/go-stdlib/README.md",
)
HISTORICAL_OR_PROPOSAL_DOCS = (
    "BOTTLE_NECKS.md",
    "CRITIQUE.md",
    "CURSOR_HOOKS.md",
    "FRAMEWORK_STRESS_TEST_SESSION_2.md",
    "IMPLEMENTATION_ROADMAP.md",
    "STRESS_TEST_REPORT.md",
    "UCF_FRAMEWORK_GUIDE.md",
)
VALID_STATUSES = {"implemented", "experimental", "planned"}


def _capability_rows() -> list[dict[str, str]]:
    text = MATRIX_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- capability-matrix:start -->\n(.*?)"
        r"<!-- capability-matrix:end -->",
        text,
        flags=re.DOTALL,
    )
    assert match is not None, "capability matrix markers are missing"

    lines = [
        line
        for line in match.group(1).splitlines()
        if line.startswith("| CAP-")
    ]
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 6, f"malformed capability row: {line}"
        rows.append(
            dict(
                zip(
                    ("id", "capability", "status", "scope", "evidence", "limits"),
                    cells,
                    strict=True,
                )
            )
        )
    return rows


def test_capability_matrix_has_one_evidence_linked_status_per_row() -> None:
    rows = _capability_rows()
    assert rows
    assert len({row["id"] for row in rows}) == len(rows)

    for row in rows:
        assert row["status"] in VALID_STATUSES, row
        assert row["scope"] not in {"", "-"}, row
        assert row["evidence"] not in {"", "-"}, row
        assert row["limits"] not in {"", "-"}, row


def test_implemented_claims_link_to_executable_repository_commands() -> None:
    implemented = [
        row for row in _capability_rows() if row["status"] == "implemented"
    ]
    assert implemented

    for row in implemented:
        assert "pytest" in row["evidence"] or "quality_gates.py" in row["evidence"], row
        referenced_tests = re.findall(r"tests/[A-Za-z0-9_./-]+\.py", row["evidence"])
        assert referenced_tests, row
        for relative_path in referenced_tests:
            assert (ROOT / relative_path).is_file(), (row, relative_path)


def test_planned_claims_have_dependency_ordered_backlog_owners() -> None:
    backlog_ids = set(
        re.findall(
            r"^### ([A-Z]+-\d+) —",
            BACKLOG_PATH.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )
    planned = [row for row in _capability_rows() if row["status"] == "planned"]
    assert planned

    for row in planned:
        owners = set(re.findall(r"\b[A-Z]+-\d+\b", row["evidence"]))
        assert owners, row
        assert owners <= backlog_ids, (row, owners - backlog_ids)


def test_rel001_benchmark_claim_is_experimental_replayable_and_bounded() -> None:
    rows = {row["id"]: row for row in _capability_rows()}
    benchmark = rows["CAP-213"]

    assert benchmark["status"] == "experimental"
    for exact_scope in (
        "three ecosystem",
        "four frozen component",
        "13 candidates",
        "5 tested",
        "zero verified",
        "http, cli, and event",
    ):
        assert exact_scope in benchmark["scope"].lower()
    for evidence_path in (
        "docs/benchmarks/rel001-report.json",
        "tools/rel001_benchmark.py",
        "tests/automation/test_rel001_benchmark.py",
        "quality_gates.py --profile all",
    ):
        assert evidence_path in benchmark["evidence"]
    for boundary in (
        "linux/x86_64",
        "scripted",
        "not human",
        "not a population",
        "not stable",
    ):
        assert boundary in benchmark["limits"].lower()

    guide = REL001_BENCHMARK_PATH.read_text(encoding="utf-8")
    for exact_claim in (
        "c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a",
        "pass_with_legacy_coverage_debt",
        "verified: 0",
        "verify-published",
        "Linux/x86_64",
    ):
        assert exact_claim in guide


def test_change_lifecycle_claim_is_experimental_and_bounded() -> None:
    rows = {row["id"]: row for row in _capability_rows()}
    lifecycle = rows["CAP-210"]

    assert lifecycle["status"] == "experimental"
    for exact_scope in (
        "1.0.0",
        "six",
        "eight",
        "fission-ai.openspec/spec-driven@1",
        "OpenSpec 1.6.0",
        "context-validated",
    ):
        assert exact_scope.lower() in lifecycle["scope"].lower()
    for evidence_path in (
        "tests/change_lifecycle",
        "tests/cli/test_change_lifecycle.py",
        "tests/automation/test_quality_gates.py",
        "tools/package_contract.py",
    ):
        assert evidence_path in lifecycle["evidence"]
    for boundary in (
        "removed",
        "absence",
        "not authenticated",
        "tested",
        "verified",
        "impact",
        "approval",
        "chg-002",
        "not stable",
    ):
        assert boundary in lifecycle["limits"].lower()

    guide = CHANGE_LIFECYCLE_PATH.read_text(encoding="utf-8")
    for exact_claim in (
        "docs/CAPABILITIES.md",
        "fission-ai.openspec/spec-driven@1",
        "tested against OpenSpec 1.6.0",
        "context_validated_import",
        "unsupported_evidence_profile",
        "proposal → delta → tasks → implementation → verification → archive",
        "exit 1",
        "exit 3",
        "CHG-002",
        "VER-002",
    ):
        assert exact_claim in guide


def test_change_governance_claim_is_experimental_and_bounded() -> None:
    rows = {row["id"]: row for row in _capability_rows()}
    governance = rows["CAP-216"]

    assert governance["status"] == "experimental"
    for exact_scope in (
        "1.0.0",
        "four",
        "ImpactReport",
        "DecisionAssessment",
        "DecisionDeclaration",
        "GateEvaluation",
        "pass_no_decision",
        "pass_approved",
    ):
        assert exact_scope.lower() in governance["scope"].lower()
    for evidence_path in (
        "tests/change_governance",
        "tests/cli/test_change_governance.py",
        "tests/automation/test_quality_gates.py",
        "tools/package_contract.py",
    ):
        assert evidence_path in governance["evidence"]
    for boundary in (
        "language",
        "framework",
        "transport",
        "prose",
        "unresolved",
        "authenticated",
        "trust",
        "verified",
        "not stable",
    ):
        assert boundary in governance["limits"].lower()

    guide = CHANGE_LIFECYCLE_PATH.read_text(encoding="utf-8")
    for exact_claim in (
        "urn:ucf:change-governance:impact-report:1.0.0",
        "urn:ucf:change-governance:decision-assessment:1.0.0",
        "urn:ucf:change-governance:decision-declaration:1.0.0",
        "urn:ucf:change-governance:gate-evaluation:1.0.0",
        "ucf change impact",
        "ucf change assess",
        "ucf change decide",
        "ucf change gate",
        "backward_compatible_graph_extension",
        "breaking_base_root_contract",
        "breaking_required_capability",
        "compatibility_unresolved",
        "pass_no_decision",
        "pass_approved",
        "block_unresolved",
        "block_decision_required",
        "block_rejected",
        "exit `0`",
        "exit `1`",
        "exit `3`",
    ):
        assert exact_claim in guide
    for decision_class in (
        "public_contract_or_serialized_boundary",
        "production_dependency_license_or_hosted_service",
        "destructive_or_irreversible_migration",
        "security_privacy_correctness_or_gate_weakening",
        "material_product_semantics",
        "scope_expansion_for_preexisting_failure",
    ):
        assert decision_class in guide


def test_generation_claim_is_experimental_executable_and_bounded() -> None:
    rows = {row["id"]: row for row in _capability_rows()}
    generation = rows["CAP-211"]

    assert generation["status"] == "experimental"
    for exact_scope in (
        "1.0.0",
        "org.ucf.adapter.generation.python-pytest",
        "one Behavior IR action",
        "two Python hash seeds",
        "pytest 9.0.2",
        "receipt-backed",
        "generated-only",
    ):
        assert exact_scope.lower() in generation["scope"].lower()
    for evidence_path in (
        "tests/generation",
        "tests/cli/test_generation.py",
        "tests/automation/test_quality_gates.py",
        "tools/package_contract.py",
    ):
        assert evidence_path in generation["evidence"]
    for boundary in (
        "linux",
        "renameat2",
        "posix",
        "one direct expected output",
        "json-compatible",
        "not typescript",
        "not go",
        "current user",
        "no sandbox",
        "same-uid",
        "not verification evidence",
        "trust claim",
        "not stable",
    ):
        assert boundary in generation["limits"].lower()

    guide = GENERATION_PATH.read_text(encoding="utf-8")
    adapter_readme = (
        ROOT / "adapters" / "python-pytest" / "README.md"
    ).read_text(encoding="utf-8")
    project_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for exact_claim in (
        "urn:ucf:generation:request:1.0.0",
        "urn:ucf:generation:result:1.0.0",
        "org.ucf.adapter.generation@1.0.0",
        "org.ucf.adapter.generation.python-pytest@1.0.0",
        "ucf generation run",
        "created",
        "unchanged",
        "updated",
        "pytest==9.0.2",
        "renameat2",
        "POSIX",
        "exit `3`",
        "committed_cleanup_failed",
        "committed_durability_unknown",
        "possibly partial residue",
        "flushes the committed exchange before cleanup",
        "exact staged tree",
        "does not create",
        "Trust claim",
        "docs/CAPABILITIES.md",
    ):
        assert exact_claim in guide
    for exact_claim in (
        "one direct expected output",
        "JSON-compatible",
        "current OS user",
        "not a sandbox",
        "does not create verification evidence",
        "Linux",
        "docs/CAPABILITIES.md",
    ):
        assert exact_claim in adapter_readme
    assert "docs/GENERATION.md" in project_readme


def test_claim_bearing_documents_defer_to_the_capability_matrix() -> None:
    for relative_path in (*CURRENT_CLAIM_DOCS, *HISTORICAL_OR_PROPOSAL_DOCS):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "docs/CAPABILITIES.md" in text, relative_path

    for relative_path in HISTORICAL_OR_PROPOSAL_DOCS:
        first_lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()[
            :12
        ]
        assert any("Status:" in line for line in first_lines), relative_path


def test_fnd003_delivery_claim_names_its_executable_boundaries() -> None:
    rows = {row["id"]: row for row in _capability_rows()}
    delivery = rows["CAP-201"]
    automation_readme = (
        ROOT / "docs" / "automation" / "README.md"
    ).read_text(encoding="utf-8")
    project_readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert delivery["status"] == "implemented"
    assert "tests/automation/test_quality_gates.py" in delivery["evidence"]
    assert "tests/automation/test_stop_hook.py" in delivery["evidence"]
    assert "--profile affected" in automation_readme
    assert "--profile all" in automation_readme
    assert "--format json" in automation_readme
    assert ".codex/hooks.json" in automation_readme
    assert ".codex/hooks.json" in project_readme


def test_behavior_and_trust_ir_claims_name_their_exact_boundaries():
    rows = {row["id"]: row for row in _capability_rows()}
    ir = rows["CAP-108"]
    promotion = rows["CAP-202"]

    assert ir["status"] == "implemented"
    assert "tests/ir/test_schema.py" in ir["evidence"]
    assert "tests/ir/test_semantic_validation.py" in ir["evidence"]
    assert "claim promotion" in ir["limits"].lower()
    assert "adapter" in ir["limits"].lower()
    assert promotion["status"] == "implemented"
    assert "tests/ir/test_trust_reconciliation.py" in promotion["evidence"]
    assert "tests/ir/test_claim_evaluation.py" in promotion["evidence"]
    assert "tests/ir/test_trust_schema.py" in promotion["evidence"]
    assert "tests/cli/test_trust_ir.py" in promotion["evidence"]
    assert "independent" in promotion["scope"].lower()
    assert "verified" in promotion["limits"].lower()
    assert "unavailable" in promotion["limits"].lower()
    assert "formal verification" not in promotion["scope"].lower()


def test_adapter_conformance_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-203"]

    assert row["status"] == "experimental"
    assert "1.0.0" in row["scope"]
    assert "org.ucf.adapter-conformance.full" in row["scope"]
    for relative_path in (
        "tests/adapters/test_conformance_models.py",
        "tests/adapters/test_conformance_resources.py",
        "tests/adapters/test_conformance_schema.py",
        "tests/adapters/test_conformance_runner.py",
        "tests/cli/test_adapter_conformance.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for required in (
        "sandbox",
        "posix",
        "windows",
        "ecosystem",
        "brownfield",
        "node",
    ):
        assert required in limits


def test_adapter_conformance_document_binds_cli_and_security_boundary():
    text = ADAPTER_CONFORMANCE_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    protocol = (
        ROOT / "docs" / "ADAPTER_PROTOCOL.md"
    ).read_text(encoding="utf-8")

    for command in (
        "ucf adapter kit",
        "ucf adapter kit --extract",
        "ucf adapter conformance --cwd",
        "--report",
    ):
        assert command in text
    for coordinate in (
        "org.ucf.adapter-conformance.full",
        "urn:ucf:adapter-conformance:control:1.0.0",
        "kit version `1.0.0`",
        "protocol version `1.0.0`",
    ):
        assert coordinate.lower() in text.lower()
    for exit_code in ("Exit `0`", "Exit `1`", "Exit `3`"):
        assert exit_code in text
    for boundary in (
        "not a sandbox",
        "current OS user",
        "POSIX",
        "Windows",
        "TypeScript",
        "brownfield",
    ):
        assert boundary in normalized

    assert "docs/ADAPTER_CONFORMANCE.md" in readme
    assert "ADAPTER_CONFORMANCE.md" in protocol
    assert "not yet a public conformance kit" not in readme
    assert "not yet the ADP-002 public conformance command" not in protocol


def test_inventory_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-204"]

    assert row["status"] == "experimental"
    for coordinate in (
        "org.ucf.adapter.inventory",
        "1.0.0",
        "observed",
    ):
        assert coordinate in row["scope"]
    for relative_path in (
        "tests/inventory/test_models.py",
        "tests/inventory/test_process_client.py",
        "tests/inventory/test_schema.py",
        "tests/cli/test_adapter_inventory.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for required in (
        "candidate",
        "reconciliation",
        "baseline",
        "sandbox",
        "posix",
        "ecosystem",
    ):
        assert required in limits


def test_inventory_document_binds_cli_profiles_and_read_boundary():
    text = INVENTORY_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for coordinate in (
        "org.ucf.adapter.inventory",
        "urn:ucf:adapter:inventory-request:1.0.0",
        "urn:ucf:adapter:inventory-page:1.0.0",
        "urn:ucf:schema:inventory:1.0.0",
    ):
        assert coordinate in text
    for command_fragment in (
        "ucf adapter inventory",
        "--policy",
        "--output",
        "--subject-uri",
    ):
        assert command_fragment in text
    for boundary in (
        "not a sandbox",
        "current OS user",
        "POSIX",
        "never follows symbolic links",
        "non-atomic",
        "candidate generation",
        "reconciliation",
        "baseline",
    ):
        assert boundary.lower() in normalized.lower()
    assert "docs/CAPABILITIES.md" in text
    assert "docs/INVENTORY.md" in readme


def test_python_onboarding_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-215"]

    assert row["status"] == "experimental"
    for coordinate in (
        "org.ucf.adapter.discovery",
        "1.0.0",
        "accepted",
        "rejected",
        "uncertain",
    ):
        assert coordinate in row["scope"]
    for relative_path in (
        "tests/onboarding/test_process_client.py",
        "tests/onboarding/test_bundle.py",
        "tests/cli/test_adapter_discover.py",
        "tests/cli/test_adapter_onboard.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for required in (
        "one fixture",
        "framework",
        "ratchet",
        "runtime",
        "sandbox",
        "human",
    ):
        assert required in limits


def test_onboarding_document_binds_review_profiles_and_security_boundary():
    text = ONBOARDING_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for coordinate in (
        "org.ucf.adapter.discovery",
        "urn:ucf:adapter:discovery-request:1.0.0",
        "urn:ucf:adapter:discovery-result:1.0.0",
        "urn:ucf:onboarding:decision-set:1.0.0",
        "urn:ucf:onboarding:bundle:1.0.0",
    ):
        assert coordinate in text
    for command_fragment in (
        "ucf adapter discover",
        "ucf adapter onboard",
        "--policy",
        "--decisions",
        "--output",
        "--subject-uri",
    ):
        assert command_fragment in text
    for boundary in (
        "not a sandbox",
        "current os user",
        "human review",
        "not verified",
        "baseline does not enforce",
        "one checked python fixture",
    ):
        assert boundary in normalized
    assert "docs/CAPABILITIES.md" in text
    assert "docs/ONBOARDING.md" in readme


def test_ratchet_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-205"]

    assert row["status"] == "experimental"
    for coordinate in (
        "1.0.0",
        "unchanged",
        "touched",
        "protected",
    ):
        assert coordinate in row["scope"].lower()
    for relative_path in (
        "tests/ratchet/test_evaluation.py",
        "tests/ratchet/test_successor.py",
        "tests/ratchet/test_touch_projection.py",
        "tests/ratchet/test_schema.py",
        "tests/cli/test_ratchet.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for required in (
        "one fixture",
        "runtime",
        "verified",
        "authoritative",
        "weakening",
    ):
        assert required in limits


def test_ratchet_document_binds_profiles_transaction_and_limits():
    text = RATCHET_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for coordinate in (
        "urn:ucf:ratchet:policy:1.0.0",
        "urn:ucf:ratchet:assessment:1.0.0",
        "urn:ucf:ratchet:baseline:1.0.0",
        "urn:ucf:ratchet:evaluation-report:1.0.0",
        "org.ucf.ratchet.baseline",
    ):
        assert coordinate in text
    for command_fragment in (
        "ucf ratchet establish",
        "ucf ratchet evaluate",
        "ucf ratchet advance",
        "--onboarding-bundle",
        "--assessment",
        "--baseline",
        "--evaluation",
        "--output",
    ):
        assert command_fragment in text
    for boundary in (
        "exit `0`",
        "exit `1`",
        "exit `3`",
        "does not create verified evidence",
        "authoritative baseline tip",
        "one checked python fixture",
        "never accepts weakening",
        "any partial subject or rule coverage",
        "hard links to inputs",
        "concurrently replaced",
    ):
        assert boundary in normalized
    assert "docs/CAPABILITIES.md" in text
    assert "docs/RATCHET.md" in readme


def test_runtime_evidence_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-206"]

    assert row["status"] == "experimental"
    for coordinate in (
        "1.0.0",
        "org.ucf.adapter.verification",
        "org.ucf.adapter.runtime-evidence",
        "recorded",
        "partial",
        "observed",
    ):
        assert coordinate in row["scope"].lower()
    for relative_path in (
        "tests/runtime_evidence/test_process_client.py",
        "tests/runtime_evidence/test_projection.py",
        "tests/runtime_evidence/test_schema.py",
        "tests/cli/test_runtime_evidence.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for required in (
        "one bounded synthetic",
        "live collection",
        "current os user",
        "sandbox",
        "universally detect",
        "absence",
        "declared",
        "mapped",
        "tested",
        "verified",
        "authenticity",
    ):
        assert required in limits


def test_runtime_evidence_document_binds_cli_privacy_and_trust_boundary():
    text = RUNTIME_EVIDENCE_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for coordinate in (
        "org.ucf.adapter.verification",
        "org.ucf.adapter.runtime-evidence",
        "urn:ucf:runtime-evidence:policy:1.0.0",
        "urn:ucf:runtime-evidence:environment:1.0.0",
        "urn:ucf:adapter:runtime-evidence-request:1.0.0",
        "urn:ucf:adapter:runtime-evidence-result:1.0.0",
        "urn:ucf:runtime-evidence:recorded-import:1.0.0",
    ):
        assert coordinate.lower() in normalized
    for command_fragment in (
        "ucf adapter import-runtime-evidence",
        "--recording",
        "--policy",
        "--environment",
        "--behavior-ir",
        "--sampling-procedure-uri",
        "--adapter-procedure-uri",
        "--adapter-cwd",
        "--output",
    ):
        assert command_fragment in text
    for boundary in (
        "exit `0`",
        "exit `1`",
        "exit `3`",
        "off by default",
        "recorded-only",
        "not a sandbox",
        "current os user",
        "does not retain, persist, or emit",
        "does not universally detect",
        "partial sampling",
        "absence",
        "observed only",
        "declared",
        "mapped",
        "tested",
        "verified",
        "traceability, not authenticity",
    ):
        assert boundary in normalized
    assert "docs/CAPABILITIES.md" in text
    assert "docs/RUNTIME_EVIDENCE.md" in readme


def test_evidence_status_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-212"]

    assert row["status"] == "experimental"
    for coordinate in (
        "1.0.0",
        "fresh",
        "stale",
        "indeterminate",
        "selective",
        "passed",
    ):
        assert coordinate in row["scope"].lower()
    for relative_path in (
        "tests/evidence_status/test_contract.py",
        "tests/evidence_status/test_recording.py",
        "tests/evidence_status/test_assessment.py",
        "tests/evidence_status/test_schema.py",
        "tests/evidence_status/test_wire_fixtures.py",
        "tests/cli/test_evidence_status.py",
        "tests/automation/test_quality_gates.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for required in (
        "caller-supplied",
        "one bounded fixture",
        "do not execute",
        "authentication",
        "signing",
        "formal proof",
        "traceability, not authenticity",
        "current user",
        "historical stale",
        "verified",
        "stable",
    ):
        assert required in limits


def test_evidence_status_document_binds_cli_exit_publication_and_trust_boundary():
    text = EVIDENCE_STATUS_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for coordinate in (
        "urn:ucf:evidence-status:envelope:1.0.0",
        "urn:ucf:evidence-status:assessment:1.0.0",
    ):
        assert coordinate in text
    for command_fragment in (
        "ucf evidence record",
        "ucf evidence assess",
        "--result",
        "--mapping-result",
        "--onboarding-bundle",
        "--inventory",
        "--recorded-result",
        "--current-result",
        "--output",
    ):
        assert command_fragment in text
    for boundary in (
        "exit `0`",
        "exit `1`",
        "exit `3`",
        "all-or-none",
        "create-only",
        "idempotent",
        "passed",
        "historical stale evidence is retained",
        "selective invalidation",
        "refresh",
        "does not create a `verified` claim",
        "traceability, not authenticity",
        "not formal verification",
    ):
        assert boundary in normalized
    assert "docs/CAPABILITIES.md" in text
    assert "docs/EVIDENCE_STATUS.md" in readme


def test_typescript_fastify_claim_names_exact_evidence_and_limits():
    row = {item["id"]: item for item in _capability_rows()}["CAP-207"]
    adapter_readme = TYPESCRIPT_FASTIFY_ADAPTER_PATH.read_text(
        encoding="utf-8"
    )
    project_readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert row["status"] == "experimental"
    for coordinate in (
        "TypeScript `7.0.2`",
        "Fastify `5.10.0`",
        "Node `22.22.3`",
        "inventory",
        "discovery",
        "mapping",
        "tested",
    ):
        assert coordinate in row["scope"]
    for relative_path in (
        "tests/ecosystems/test_typescript_fastify_inventory.py",
        "tests/ecosystems/test_typescript_fastify_discovery.py",
        "tests/ecosystems/test_typescript_fastify_mapping.py",
        "tests/ecosystems/test_typescript_fastify_verification.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    for boundary in (
        "one frozen fixture",
        "linux/x64",
        "private local npm tarball",
        "adapter-attested",
        "not general",
        "verified",
        "formal",
        "sandbox",
    ):
        assert boundary in row["limits"].lower()
    for exact_claim in (
        "Node 22.22.3/Linux/x64",
        "Fastify 5.10.0",
        "adapter-attested",
        "not independent attestation",
        "not general Fastify support",
        "docs/CAPABILITIES.md",
    ):
        assert exact_claim in adapter_readme
    assert "adapters/typescript-fastify/README.md" in project_readme


def test_go_stdlib_claim_names_exact_evidence_and_limits():
    rows = {item["id"]: item for item in _capability_rows()}
    row = rows["CAP-208"]
    adapter_readme = GO_STDLIB_ADAPTER_PATH.read_text(encoding="utf-8")
    normalized_adapter_readme = " ".join(adapter_readme.split())
    project_readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert row["status"] == "experimental"
    for coordinate in (
        "Go directive `1.26.0`",
        "`go1.26.5`",
        "`net/http`",
        "Linux/amd64",
        "`GOAMD64=v1`",
        "`CGO_ENABLED=0`",
        "protocol and conformance `1.0.0`",
        "51 inventory records",
        "four candidates",
        "one accepted, two rejected, and one uncertain",
        "exact implementation mapping",
        "`POST /quote-order`",
        "exactly one `tested` claim",
    ):
        assert coordinate in row["scope"]
    for relative_path in (
        "tests/ecosystems/test_go_stdlib_fixture.py",
        "tests/ecosystems/test_go_stdlib_conformance.py",
        "tests/ecosystems/test_go_stdlib_inventory.py",
        "tests/ecosystems/test_go_stdlib_discovery.py",
        "tests/ecosystems/test_go_stdlib_mapping.py",
        "tests/ecosystems/test_go_stdlib_verification.py",
        "tools/package_contract.py",
    ):
        assert relative_path in row["evidence"]
    limits = row["limits"].lower()
    for boundary in (
        "one unchanged six-file fixture",
        "not broad go",
        "literal returned `servemux`",
        "no cgo",
        "windows",
        "build tags",
        "workspaces",
        "monorepos",
        "generated",
        "dynamic",
        "custom routing",
        "adapter-attested",
        "not independent",
        "formal",
        "sandbox",
        "current user",
        "filesystem",
        "process access",
        "secret",
        "personal data",
        "traceability, not signing",
        "exact pin",
        "requalification",
        "sla",
        "deprecation",
        "verified",
    ):
        assert boundary in limits
    assert "cap-209 and cap-214 remain planned" not in limits

    for exact_claim in (
        "Go directive 1.26.0",
        "go1.26.5",
        "Linux/amd64",
        "GOAMD64=v1",
        "CGO_ENABLED=0",
        "51 inventory records",
        "four deterministic candidates",
        "one accepted, two rejected, and one uncertain",
        "POST /quote-order",
        "exactly one tested claim",
        "normal product mode",
        "--conformance",
        "zero external Go modules",
        "Go runtime",
        "GOROOT-vendored",
        "LICENSE",
        "PATENTS",
        "Project-wide licensing",
        "REL-002",
        "docs/CAPABILITIES.md",
    ):
        assert exact_claim in adapter_readme
    assert "`ServeMux` returned by its `Handler` function" in normalized_adapter_readme
    assert "`Routes` function" not in adapter_readme
    assert "accepted by eco-003" not in adapter_readme.lower()

    assert rows["CAP-209"]["status"] == "experimental"
    platform_scope = rows["CAP-209"]["scope"].lower()
    platform_evidence = rows["CAP-209"]["evidence"]
    platform_limits = rows["CAP-209"]["limits"].lower()
    for exact_scope in (
        "go1.26.5",
        "linux/amd64",
        "org.ucf.platform.http-loopback",
        "org.ucf.platform.cli-process",
        "org.ucf.platform.file-spool-event",
        "14 exact",
        "four separate",
        "tested",
        "never `verified`",
    ):
        assert exact_scope.lower() in platform_scope
    for evidence_path in (
        "tests/ecosystems/test_go_stdlib_verification.py",
        "tests/ecosystems/test_platform_neutrality.py",
        "tests/ecosystems/test_go_stdlib_platform_fixture.py",
        "tests/ecosystems/test_go_stdlib_platform_adapter.py",
        "tools/package_contract.py",
    ):
        assert evidence_path in platform_evidence
    for boundary in (
        "one frozen",
        "local file-spool",
        "not a hosted broker",
        "ordering",
        "durability",
        "exactly-once",
        "adapter-attested",
        "no sandbox",
        "same-uid",
        "external daemon",
        "formal verification",
    ):
        assert boundary in platform_limits
    for adapter_claim in (
        "--platform-fixture-executable",
        "org.ucf.platform.http-loopback",
        "org.ucf.platform.cli-process",
        "org.ucf.platform.file-spool-event",
        "14 exact filesystem entries",
        "four separate bounded processes",
        "adapter-attested",
        "never creates a `verified` claim",
    ):
        assert adapter_claim in normalized_adapter_readme
    assert rows["CAP-214"]["status"] == "planned"
    assert "Compiled ecosystems, broader platforms" not in project_readme
    assert "adapters/go-stdlib/README.md" in project_readme
