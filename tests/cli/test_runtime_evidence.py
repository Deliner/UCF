from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ucf.cli import app
from ucf.ir import parse_ir_json
from ucf.runtime_evidence import (
    RuntimeEvidenceAcceptedResult,
    canonical_runtime_evidence_json,
    parse_runtime_environment_json,
    parse_runtime_evidence_result_json,
    project_runtime_evidence_to_trust,
)

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "runtime_evidence"
    / "recorded_trace_v1"
)
BEHAVIOR = ROOT / "tests" / "fixtures" / "ir" / "v1" / "complete.json"
ADAPTER = (
    ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "runtime_evidence_reference_adapter.py"
)


def _inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "recording": tmp_path / "recording.json",
        "policy": tmp_path / "policy.json",
        "environment": tmp_path / "environment.json",
        "behavior": tmp_path / "behavior.json",
    }
    shutil.copy2(FIXTURE / "recording.json", paths["recording"])
    shutil.copy2(FIXTURE / "policy.json", paths["policy"])
    shutil.copy2(FIXTURE / "environment.json", paths["environment"])
    shutil.copy2(BEHAVIOR, paths["behavior"])
    return paths


def _arguments(
    paths: dict[str, Path],
    output: Path,
    *,
    mode: str = "normal",
    operation_timeout: str = "2",
) -> list[str]:
    return [
        "adapter",
        "import-runtime-evidence",
        "--recording",
        str(paths["recording"]),
        "--policy",
        str(paths["policy"]),
        "--environment",
        str(paths["environment"]),
        "--behavior-ir",
        str(paths["behavior"]),
        "--source-uri",
        "urn:ucf:runtime-recording:fixture-v1",
        "--captured-at",
        "2026-07-19T08:30:00Z",
        "--sampling-procedure-uri",
        "urn:ucf:runtime-sampling:recorded-partial:1.0.0",
        "--adapter-procedure-uri",
        "urn:ucf:fixture-adapter:runtime-evidence:1.0.0",
        "--adapter-cwd",
        str(output.parent),
        "--output",
        str(output),
        "--operation-timeout",
        operation_timeout,
        "--",
        sys.executable,
        str(ADAPTER),
        str(paths["recording"]),
        "--mode",
        mode,
    ]


def test_cli_writes_repeatable_authoritative_result_and_projection(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path)
    before = {name: path.read_bytes() for name, path in paths.items()}
    first = tmp_path / "result-a.json"
    second = tmp_path / "result-b.json"

    first_run = runner.invoke(app, _arguments(paths, first))
    second_run = runner.invoke(app, _arguments(paths, second))

    assert first_run.exit_code == 0, first_run.output
    assert second_run.exit_code == 0, second_run.output
    assert first_run.stdout == first_run.stderr == ""
    assert second_run.stdout == second_run.stderr == ""
    assert first.read_bytes() == second.read_bytes()
    result = parse_runtime_evidence_result_json(first.read_bytes())
    assert isinstance(result, RuntimeEvidenceAcceptedResult)
    assert first.read_bytes() == canonical_runtime_evidence_json(result)
    behavior = parse_ir_json(paths["behavior"].read_bytes())
    environment = parse_runtime_environment_json(
        paths["environment"].read_bytes()
    )
    trust = project_runtime_evidence_to_trust(
        result,
        behavior=behavior,
        environment=environment,
    )
    assert len(trust.records) == 2
    assert {name: path.read_bytes() for name, path in paths.items()} == before
    forbidden = _forbidden_values(paths["recording"])
    checked = (
        first.read_bytes(),
        first_run.stdout.encode(),
        first_run.stderr.encode(),
    )
    assert all(value not in payload for value in forbidden for payload in checked)


def test_cli_typed_rejection_preserves_existing_output(tmp_path: Path) -> None:
    paths = _inputs(tmp_path)
    output = tmp_path / "result.json"
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _arguments(paths, output, mode="rejected"),
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "runtime_evidence/policy_rejected/"
        "selected_value_not_allowed\n"
    )
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".result.json.*.tmp"))


@pytest.mark.parametrize(
    ("selector_uri", "reason"),
    [
        (
            "urn:ucf:fixture-selector:selected-secret:1.0.0",
            "selected_secret",
        ),
        (
            "urn:ucf:fixture-selector:selected-personal-data:1.0.0",
            "selected_personal_data",
        ),
    ],
)
def test_cli_rejects_selected_unsafe_values_without_echoing_them(
    tmp_path: Path,
    selector_uri: str,
    reason: str,
) -> None:
    paths = _inputs(tmp_path)
    policy = json.loads(paths["policy"].read_text(encoding="utf-8"))
    policy["rules"][0]["selector_uri"] = selector_uri
    paths["policy"].write_text(
        json.dumps(
            policy,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    before = {name: path.read_bytes() for name, path in paths.items()}
    output = tmp_path / "result.json"
    output.write_bytes(b"preserve-me")

    result = runner.invoke(app, _arguments(paths, output))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        f"runtime_evidence/policy_rejected/{reason}\n"
    )
    assert output.read_bytes() == b"preserve-me"
    assert {name: path.read_bytes() for name, path in paths.items()} == before
    forbidden = _forbidden_values(paths["recording"])
    assert all(value not in result.output.encode() for value in forbidden)
    assert not tuple(tmp_path.glob(".result.json.*.tmp"))


def test_cli_sanitizes_peer_and_stderr_failures(tmp_path: Path) -> None:
    paths = _inputs(tmp_path)
    forbidden = _forbidden_values(paths["recording"])
    for mode, diagnostic in (
        ("peer-error", "adapter_failure/operation_failed"),
        ("stderr", "process_failure/invalid_adapter_output"),
    ):
        output = tmp_path / f"{mode}.json"
        output.write_bytes(b"preserve-me")

        result = runner.invoke(
            app,
            _arguments(paths, output, mode=mode),
        )

        assert result.exit_code == 3
        assert result.stdout == ""
        assert result.stderr == f"runtime_evidence/{diagnostic}\n"
        assert output.read_bytes() == b"preserve-me"
        assert all(
            value not in result.output.encode() for value in forbidden
        )
        assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))


def test_cli_sanitizes_timeout_and_preserves_existing_output(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path)
    output = tmp_path / "result.json"
    output.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        _arguments(
            paths,
            output,
            mode="hang",
            operation_timeout="0.05",
        ),
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == (
        "runtime_evidence/timeout/operation_timeout\n"
    )
    assert output.read_bytes() == b"preserve-me"
    assert all(
        value not in result.output.encode()
        for value in _forbidden_values(paths["recording"])
    )
    assert not tuple(tmp_path.glob(".result.json.*.tmp"))


def test_cli_rejects_alias_and_symlink_inputs_before_spawn(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path)
    alias_arguments = _arguments(paths, paths["policy"])
    separator = alias_arguments.index("--")
    alias_arguments[separator + 1 :] = ["adapter-that-must-not-run"]

    alias = runner.invoke(app, alias_arguments)

    assert alias.exit_code == 3
    assert alias.stderr == "runtime_evidence/invalid_input\n"

    hard_link_output = tmp_path / "policy-output-hard-link.json"
    hard_link_output.hardlink_to(paths["policy"])
    hard_link_arguments = _arguments(paths, hard_link_output)
    separator = hard_link_arguments.index("--")
    hard_link_arguments[separator + 1 :] = ["adapter-that-must-not-run"]

    hard_link = runner.invoke(app, hard_link_arguments)

    assert hard_link.exit_code == 3
    assert hard_link.stderr == "runtime_evidence/invalid_input\n"

    linked_recording = tmp_path / "linked-recording.json"
    linked_recording.symlink_to(paths["recording"])
    linked_paths = {**paths, "recording": linked_recording}
    output = tmp_path / "result.json"
    symlink_arguments = _arguments(linked_paths, output)
    separator = symlink_arguments.index("--")
    symlink_arguments[separator + 1 :] = ["adapter-that-must-not-run"]

    symlink = runner.invoke(app, symlink_arguments)

    assert symlink.exit_code == 3
    assert symlink.stderr == "runtime_evidence/invalid_input\n"
    assert not output.exists()

    recording_directory = tmp_path / "recording-directory"
    recording_directory.mkdir()
    directory_paths = {**paths, "recording": recording_directory}
    directory_arguments = _arguments(directory_paths, output)
    separator = directory_arguments.index("--")
    directory_arguments[separator + 1 :] = ["adapter-that-must-not-run"]

    directory = runner.invoke(app, directory_arguments)

    assert directory.exit_code == 3
    assert directory.stderr == "runtime_evidence/invalid_input\n"
    assert not output.exists()


def test_cli_requires_adapter_separator_and_stays_off_for_help(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path)
    output = tmp_path / "result.json"
    arguments = _arguments(paths, output)
    arguments.remove("--")

    missing_separator = runner.invoke(app, arguments)
    help_result = runner.invoke(
        app,
        ["adapter", "import-runtime-evidence", "--help"],
    )

    assert missing_separator.exit_code == 2
    assert "No such option" in missing_separator.stderr
    assert help_result.exit_code == 0
    assert not output.exists()


def _forbidden_values(recording_path: Path) -> tuple[bytes, bytes]:
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    attributes = recording["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
        "attributes"
    ]
    values = {
        item["key"]: item["value"]["stringValue"].encode()
        for item in attributes
    }
    return values["fixture.secret"], values["fixture.personal"]
