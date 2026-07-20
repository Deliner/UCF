from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ucf.adapter_conformance import (
    ConformanceReport,
    canonical_conformance_json,
    conformance_assets,
    conformance_kit_index,
    load_conformance_manifest,
)
from ucf.cli import app

runner = CliRunner()


def _node_command(name: str, *arguments: str) -> list[str]:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node is required by the adapter conformance contract")
    logical_name = name if "/" in name else f"samples/{name}"
    sample = conformance_assets()
    for segment in logical_name.split("/"):
        sample = sample.joinpath(segment)
    assert sample.is_file()
    return [node, str(sample), *arguments]


def test_adapter_kit_prints_index_and_extracts_exact_assets(tmp_path: Path):
    expected = canonical_conformance_json(conformance_kit_index()).decode()

    shown = runner.invoke(app, ["adapter", "kit"])
    assert shown.exit_code == 0, shown.output
    assert shown.stdout == expected
    assert shown.stderr == ""

    destination = tmp_path / "kit"
    extracted = runner.invoke(
        app,
        ["adapter", "kit", "--extract", str(destination)],
    )
    assert extracted.exit_code == 0, extracted.output
    assert extracted.stdout == expected
    assert extracted.stderr == ""
    assert (destination / "manifest.json").is_file()
    assert (destination / "samples" / "reference_adapter.mjs").is_file()

    preserved = destination / "preserved"
    preserved.write_text("mine", encoding="utf-8")
    rejected = runner.invoke(
        app,
        ["adapter", "kit", "--extract", str(destination)],
    )
    assert rejected.exit_code == 3
    assert "empty" in rejected.stderr
    assert preserved.read_text(encoding="utf-8") == "mine"


def test_adapter_conformance_stdout_and_report_file_are_byte_identical(
    tmp_path: Path,
):
    command = _node_command("reference_adapter.mjs")
    arguments = [
        "adapter",
        "conformance",
        "--cwd",
        str(tmp_path),
        "--",
        *command,
    ]

    stdout_run = runner.invoke(app, arguments)
    assert stdout_run.exit_code == 0, stdout_run.output
    report = ConformanceReport.model_validate_json(stdout_run.stdout)
    expected = canonical_conformance_json(report).decode()
    assert stdout_run.stdout == expected
    assert stdout_run.stderr == ""

    report_path = tmp_path / "report.json"
    file_run = runner.invoke(
        app,
        [
            "adapter",
            "conformance",
            "--cwd",
            str(tmp_path),
            "--report",
            str(report_path),
            "--",
            *command,
        ],
    )
    assert file_run.exit_code == 0, file_run.output
    assert file_run.stdout == ""
    assert file_run.stderr == ""
    assert report_path.read_text(encoding="utf-8") == expected


def test_adapter_conformance_preserves_argv_and_exit_classes(tmp_path: Path):
    nonconformant = runner.invoke(
        app,
        [
            "adapter",
            "conformance",
            "--cwd",
            str(tmp_path),
            "--",
            *_node_command(
                load_conformance_manifest().fault_adapter,
                "--fault",
                "accepts-unnegotiated",
            ),
        ],
    )
    assert nonconformant.exit_code == 1
    assert json.loads(nonconformant.stdout)["status"] == "non_conformant"
    assert nonconformant.stderr == ""

    runner_error = runner.invoke(
        app,
        [
            "adapter",
            "conformance",
            "--cwd",
            str(tmp_path),
            "--",
            "ucf-adapter-command-that-does-not-exist",
        ],
    )
    assert runner_error.exit_code == 3
    assert json.loads(runner_error.stdout)["status"] == "runner_error"
    assert runner_error.stderr == ""
