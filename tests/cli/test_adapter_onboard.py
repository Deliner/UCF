from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.inventory.reference_adapter_harness import (
    nonfollowing_tree_manifest,
)
from tests.onboarding.test_decisions import _decisions
from ucf.cli import app
from ucf.onboarding import (
    DispositionKind,
    canonical_onboarding_json,
    parse_discovery_result_json,
    parse_onboarding_bundle_json,
    validate_decision_set,
)

from .test_adapter_discover import (
    REFERENCE_ADAPTER,
    _write_policy,
    runner,
)
from .test_adapter_discover import (
    _arguments as _discover_arguments,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "python_legacy_quote"
)


def _arguments(
    repository: Path,
    policy: Path,
    decisions: Path,
    output: Path,
    *,
    page_record_limit: int,
    mode: str = "normal",
) -> list[str]:
    return [
        "adapter",
        "onboard",
        str(repository),
        "--policy",
        str(policy),
        "--decisions",
        str(decisions),
        "--output",
        str(output),
        "--subject-uri",
        "urn:ucf:repository:python-legacy-quote",
        "--page-record-limit",
        str(page_record_limit),
        "--operation-timeout",
        "5",
        "--",
        sys.executable,
        "-B",
        "-X",
        "utf8",
        str(REFERENCE_ADAPTER),
        "--mode",
        mode,
    ]


def _native_behavior(repository: Path) -> bytes:
    completed = subprocess.run(
        (sys.executable, "-B", "tests/behavior_checks.py"),
        cwd=repository,
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    return completed.stdout


def _write_review(
    repository: Path,
    policy: Path,
    discovery_path: Path,
    decisions_path: Path,
):
    result = runner.invoke(
        app,
        _discover_arguments(
            repository,
            policy,
            discovery_path,
            page_record_limit=3,
        ),
    )
    assert result.exit_code == 0, result.output
    discovery = parse_discovery_result_json(discovery_path.read_bytes())
    decisions = _decisions(discovery)
    validate_decision_set(discovery, decisions)
    decisions_path.write_bytes(canonical_onboarding_json(decisions))
    return decisions


def test_adapter_onboard_revalidates_review_and_writes_repeatable_bundle(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    discovery_path = tmp_path / "discovery.json"
    decisions_path = tmp_path / "decisions.json"
    first_output = tmp_path / "onboarding-a.json"
    second_output = tmp_path / "onboarding-b.json"
    _write_policy(policy)
    before_manifest = nonfollowing_tree_manifest(repository)
    before_behavior = _native_behavior(repository)

    _write_review(
        repository,
        policy,
        discovery_path,
        decisions_path,
    )

    first = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            decisions_path,
            first_output,
            page_record_limit=3,
        ),
    )
    second = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            decisions_path,
            second_output,
            page_record_limit=1,
        ),
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.stdout == first.stderr == ""
    assert second.stdout == second.stderr == ""
    assert first_output.read_bytes() == second_output.read_bytes()
    bundle = parse_onboarding_bundle_json(first_output.read_bytes())
    assert first_output.read_bytes() == canonical_onboarding_json(bundle)
    assert {
        summary.disposition for summary in bundle.baseline.dispositions
    } == set(DispositionKind)
    assert nonfollowing_tree_manifest(repository) == before_manifest
    assert _native_behavior(repository) == before_behavior


def test_adapter_onboard_preserves_output_when_review_is_stale(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    discovery_path = tmp_path / "discovery.json"
    decisions_path = tmp_path / "decisions.json"
    output = tmp_path / "onboarding.json"
    _write_policy(policy)
    decisions = _write_review(
        repository,
        policy,
        discovery_path,
        decisions_path,
    )
    stale = decisions.model_copy(
        update={
            "discovery": decisions.discovery.model_copy(
                update={
                    "canonical_digest": (
                        decisions.discovery.canonical_digest.model_copy(
                            update={"value": "f" * 64}
                        )
                    )
                }
            )
        }
    )
    decisions_path.write_bytes(canonical_onboarding_json(stale))
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            decisions_path,
            output,
            page_record_limit=3,
        ),
    )

    assert result.exit_code == 3
    assert "stale_decision" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".onboarding.json.*.tmp"))


def test_adapter_onboard_rejects_duplicate_decision_members_before_spawn(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    decisions_path = tmp_path / "decisions.json"
    output = tmp_path / "onboarding.json"
    _write_policy(policy)
    decisions_path.write_text(
        '{"kind":"decision_set_profile","kind":"decision_set_profile"}',
        encoding="utf-8",
    )
    arguments = _arguments(
        repository,
        policy,
        decisions_path,
        output,
        page_record_limit=3,
    )
    separator = arguments.index("--")
    arguments[separator + 1 :] = ["adapter-that-must-not-be-spawned"]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "onboarding decision set is invalid" in result.stderr
    assert not output.exists()


def test_adapter_onboard_preserves_output_on_adapter_failure(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    discovery_path = tmp_path / "discovery.json"
    decisions_path = tmp_path / "decisions.json"
    output = tmp_path / "onboarding.json"
    _write_policy(policy)
    _write_review(
        repository,
        policy,
        discovery_path,
        decisions_path,
    )
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            decisions_path,
            output,
            page_record_limit=3,
            mode="fail-discovery",
        ),
    )

    assert result.exit_code == 3
    assert "operation_failed" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".onboarding.json.*.tmp"))


def test_adapter_onboard_rejects_output_equal_to_decisions_before_spawn(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    discovery_path = tmp_path / "discovery.json"
    decisions_path = tmp_path / "decisions.json"
    _write_policy(policy)
    _write_review(
        repository,
        policy,
        discovery_path,
        decisions_path,
    )
    original = decisions_path.read_bytes()
    arguments = _arguments(
        repository,
        policy,
        decisions_path,
        decisions_path,
        page_record_limit=3,
    )
    separator = arguments.index("--")
    arguments[separator + 1 :] = ["adapter-that-must-not-be-spawned"]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "output must differ from every input" in result.stderr
    assert decisions_path.read_bytes() == original
