from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from typer.testing import CliRunner

from tests.inventory.reference_adapter_harness import (
    nonfollowing_tree_manifest,
)
from ucf.cli import app
from ucf.inventory import IgnorePolicy
from ucf.onboarding import (
    canonical_onboarding_json,
    parse_discovery_result_json,
)

runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "python_legacy_quote"
)
REFERENCE_ADAPTER = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "inventory_reference_adapter.py"
)


def _write_policy(path: Path) -> None:
    policy = IgnorePolicy(
        kind="ignore_policy",
        policy_version="1.0.0",
        rules=(),
    )
    path.write_text(
        json.dumps(
            policy.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _arguments(
    repository: Path,
    policy: Path,
    output: Path,
    *,
    page_record_limit: int,
    mode: str = "normal",
) -> list[str]:
    return [
        "adapter",
        "discover",
        str(repository),
        "--policy",
        str(policy),
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


def test_adapter_discover_exports_repeatable_review_material_without_source_edits(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    first_output = tmp_path / "discovery-a.json"
    second_output = tmp_path / "discovery-b.json"
    _write_policy(policy)
    before = nonfollowing_tree_manifest(repository)

    first = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            first_output,
            page_record_limit=3,
        ),
    )
    second = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            second_output,
            page_record_limit=1,
        ),
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.stdout == first.stderr == ""
    assert second.stdout == second.stderr == ""
    assert first_output.read_bytes() == second_output.read_bytes()
    discovery = parse_discovery_result_json(first_output.read_bytes())
    assert first_output.read_bytes() == canonical_onboarding_json(discovery)
    assert len(discovery.candidates) == 4
    assert nonfollowing_tree_manifest(repository) == before


def test_adapter_discover_rejects_output_equal_to_policy_before_spawn(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    _write_policy(policy)
    original = policy.read_bytes()
    arguments = _arguments(
        repository,
        policy,
        policy,
        page_record_limit=3,
    )
    separator = arguments.index("--")
    arguments[separator + 1 :] = ["adapter-that-must-not-be-spawned"]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "output must differ from every input" in result.stderr
    assert policy.read_bytes() == original


def test_adapter_discover_preserves_existing_output_on_invalid_candidate(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    output = tmp_path / "discovery.json"
    _write_policy(policy)
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _arguments(
            repository,
            policy,
            output,
            page_record_limit=3,
            mode="invalid-candidate",
        ),
    )

    assert result.exit_code == 3
    assert "invalid_adapter_output" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".discovery.json.*.tmp"))


def test_adapter_discover_rejects_output_below_root_before_spawn(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    output = repository / "discovery.json"
    _write_policy(policy)
    arguments = _arguments(
        repository,
        policy,
        output,
        page_record_limit=3,
    )
    separator = arguments.index("--")
    arguments[separator + 1 :] = ["adapter-that-must-not-be-spawned"]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "outside the inventory root" in result.stderr
    assert not output.exists()


def test_adapter_discover_rejects_adapter_option_without_separator(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    output = tmp_path / "discovery.json"
    _write_policy(policy)
    arguments = _arguments(
        repository,
        policy,
        output,
        page_record_limit=3,
    )
    arguments.remove("--")

    result = runner.invoke(app, arguments)

    assert result.exit_code == 2
    assert "No such option" in result.stderr
    assert not output.exists()
