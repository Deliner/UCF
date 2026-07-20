from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from typer.testing import CliRunner

from ucf.cli import app
from ucf.inventory import (
    INVENTORY_VERSION,
    IgnorePolicy,
    IgnoreRule,
    PathSegmentMatcher,
    canonical_inventory_json,
    parse_inventory_snapshot_json,
)

runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT / "tests" / "fixtures" / "brownfield" / "inventory_mixed"
)
REFERENCE_ADAPTER = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "inventory_reference_adapter.py"
)


def _policy() -> IgnorePolicy:
    return IgnorePolicy(
        kind="ignore_policy",
        policy_version="1.0.0",
        rules=(
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.generated",
                reason="org.ucf.inventory.generated",
                matcher=PathSegmentMatcher(
                    kind="path_segment",
                    segment="generated",
                ),
            ),
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.vendor",
                reason="org.ucf.inventory.vendor",
                matcher=PathSegmentMatcher(
                    kind="path_segment",
                    segment="vendor",
                ),
            ),
        ),
    )


def _write_policy(path: Path) -> None:
    path.write_text(
        json.dumps(
            _policy().model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _arguments(
    repository: Path,
    policy: Path,
    output: Path,
    *adapter_arguments: str,
) -> list[str]:
    return [
        "adapter",
        "inventory",
        str(repository),
        "--policy",
        str(policy),
        "--output",
        str(output),
        "--subject-uri",
        "urn:ucf:repository:cli-fixture",
        "--page-record-limit",
        "3",
        "--operation-timeout",
        "5",
        "--",
        sys.executable,
        str(REFERENCE_ADAPTER),
        *adapter_arguments,
    ]


def test_adapter_inventory_writes_canonical_output_outside_unchanged_root(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    output = tmp_path / "inventory.json"
    _write_policy(policy)

    result = runner.invoke(
        app,
        _arguments(repository, policy, output, "--mode", "normal"),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert result.stderr == ""
    snapshot = parse_inventory_snapshot_json(output.read_bytes())
    assert snapshot.inventory_version == INVENTORY_VERSION
    assert output.read_bytes() == canonical_inventory_json(snapshot)


def test_adapter_inventory_rejects_output_below_root_before_spawn(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    output = repository / "inventory.json"
    _write_policy(policy)
    arguments = _arguments(repository, policy, output)
    arguments[-2:] = ["adapter-that-must-not-be-spawned", "--unused"]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "outside the inventory root" in result.stderr
    assert not output.exists()


def test_adapter_inventory_preserves_existing_output_on_late_failure(tmp_path):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    output = tmp_path / "inventory.json"
    _write_policy(policy)
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _arguments(repository, policy, output, "--mode", "invalid-page"),
    )

    assert result.exit_code == 3
    assert "invalid_adapter_output" in result.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".inventory.json.*.tmp"))


def test_adapter_inventory_rejects_duplicate_policy_members_before_spawn(
    tmp_path,
):
    repository = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT, repository)
    policy = tmp_path / "policy.json"
    policy.write_text(
        '{"kind":"ignore_policy","kind":"ignore_policy",'
        '"policy_version":"1.0.0","rules":[]}',
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"
    arguments = _arguments(repository, policy, output)
    arguments[-2:] = ["adapter-that-must-not-be-spawned", "--unused"]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "inventory policy is invalid" in result.stderr
    assert not output.exists()
