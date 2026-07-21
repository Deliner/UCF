"""Executable governance checks for the dependency-ordered delivery backlog."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG_PATH = ROOT / "docs" / "automation" / "BACKLOG.md"
STATE_PATH = ROOT / "docs" / "automation" / "STATE.md"
PLANS_PATH = ROOT / "docs" / "plans"

EXPECTED_PACKAGES = (
    ("FND-001", "FND-001-green-baseline.md"),
    ("FND-002", "FND-002-strict-parser-and-claims.md"),
    ("FND-003", "FND-003-deterministic-gates-and-packaging.md"),
    ("IR-001", "IR-001-versioned-behavior-ir.md"),
    ("IR-002", "IR-002-intent-evidence-claims.md"),
    ("ADP-001", "ADP-001-out-of-process-adapter-protocol.md"),
    ("ADP-002", "ADP-002-adapter-conformance-kit.md"),
    ("BRN-001", "BRN-001-read-only-inventory.md"),
    ("BRN-002", "BRN-002-python-brownfield-vertical-slice.md"),
    ("BRN-003", "BRN-003-baseline-and-ratchet.md"),
    ("BRN-004", "BRN-004-optional-runtime-evidence.md"),
    ("ECO-001", "ECO-001-typescript-framework-adapter.md"),
    ("ECO-002", "ECO-002-compiled-ecosystem-spike-and-selection.md"),
    ("ECO-003", "ECO-003-non-http-platform-proof.md"),
    ("CHG-001", "CHG-001-openspec-change-envelope.md"),
    ("CHG-002", "CHG-002-impact-approval-gates.md"),
    ("VER-001", "VER-001-deterministic-executable-generation.md"),
    ("VER-002", "VER-002-evidence-loop.md"),
    ("REL-001", "REL-001-end-to-end-adoption-benchmark.md"),
    ("REL-002", "REL-002-stable-release-readiness.md"),
)

REQUIRED_PLAN_SECTIONS = (
    "Purpose / Big Picture",
    "Foundational Assumption",
    "Progress",
    "Surprises & Discoveries",
    "Decision Log",
    "Outcomes & Retrospective",
    "Context and Orientation",
    "Plan of Work",
    "Concrete Steps",
    "Validation and Acceptance",
    "Idempotence and Recovery",
    "Artifacts and Notes",
    "Interfaces and Dependencies",
)


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    block = text.split("---\n", 2)[1]
    return {
        key: value
        for key, value in re.findall(r"^([a-z_]+):\s*(.*?)\s*$", block, re.MULTILINE)
    }


def _status_rows() -> list[tuple[str, str, str]]:
    backlog = BACKLOG_PATH.read_text(encoding="utf-8")
    marker = re.search(
        r"<!-- work-package-status:start -->\n(?P<table>.*?)"
        r"<!-- work-package-status:end -->",
        backlog,
        flags=re.DOTALL,
    )
    assert marker, "BACKLOG.md must contain the canonical work-package status table"
    return re.findall(
        r"^\|\s*\d+\s*\|\s*([A-Z]+-\d+)\s*\|\s*"
        r"(verified|in_progress)\s*\|\s*"
        r"\[[^]]+\]\(\.\./plans/([A-Za-z0-9-]+\.md)\)\s*\|$",
        marker.group("table"),
        flags=re.MULTILINE,
    )


def test_dependency_backlog_has_one_canonical_execplan_per_package() -> None:
    backlog = BACKLOG_PATH.read_text(encoding="utf-8")
    heading_ids = tuple(
        re.findall(r"^### ([A-Z]+-\d+) —", backlog, flags=re.MULTILINE)
    )
    assert heading_ids == tuple(package_id for package_id, _ in EXPECTED_PACKAGES)

    rows = _status_rows()
    assert (
        tuple((package_id, plan) for package_id, _, plan in rows)
        == EXPECTED_PACKAGES
    )
    assert {path.name for path in PLANS_PATH.glob("*.md")} == {
        plan for _, plan in EXPECTED_PACKAGES
    }


def test_work_package_status_matches_state_and_completed_execplans() -> None:
    rows = _status_rows()
    state = _frontmatter(STATE_PATH)
    active = [package_id for package_id, status, _ in rows if status == "in_progress"]

    if active:
        assert active == [state["active_work_package"]]
        assert state["status"] == "in_progress"
        active_plan = dict((package_id, plan) for package_id, _, plan in rows)[
            active[0]
        ]
        assert state["active_exec_plan"] == f"docs/plans/{active_plan}"
    else:
        assert state["status"] == "complete"
        assert state["active_work_package"] == "null"
        assert state["active_exec_plan"] == "null"

    for package_id, status, plan_name in rows:
        plan = (PLANS_PATH / plan_name).read_text(encoding="utf-8")
        section_positions = [
            plan.index(f"## {section}") for section in REQUIRED_PLAN_SECTIONS
        ]
        assert section_positions == sorted(section_positions), (
            package_id,
            section_positions,
        )

        outcomes = plan.split("## Outcomes & Retrospective", 1)[1].split(
            "## Context and Orientation", 1
        )[0]
        assert outcomes.strip(), package_id

        progress = plan.split("## Progress", 1)[1].split(
            "## Surprises & Discoveries", 1
        )[0]
        checkbox_lines = re.findall(r"^- \[[ xX]\].*$", progress, flags=re.MULTILINE)
        assert checkbox_lines, package_id
        for line in checkbox_lines:
            assert re.match(
                r"^- \[[ xX]\] (?:\(\d{4}-\d{2}-\d{2}\)|\d{4}-\d{2}-\d{2}:)",
                line,
            ), (package_id, line)

        if status == "verified":
            assert "- [ ]" not in plan, package_id


def test_dependency_ordered_backlog_is_fully_verified() -> None:
    rows = _status_rows()
    assert rows
    assert {status for _, status, _ in rows} == {"verified"}

    state = _frontmatter(STATE_PATH)
    assert state["status"] == "complete"
    assert state["active_work_package"] == "null"
    assert state["active_exec_plan"] == "null"
