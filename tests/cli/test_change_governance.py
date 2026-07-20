from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.change_governance._fixture_factory import (
    DEFAULT_FIXTURE_DIRECTORY,
)
from ucf.change_governance import (
    GateStatus,
    parse_decision_assessment_json,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
    parse_impact_report_json,
)
from ucf.cli import app

runner = CliRunner()


def _inputs(tmp_path: Path, *, profile: str) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    names = {
        "base": "context/base-behavior.json",
        "final": f"context/{profile}-final-behavior.json",
        "proposal": "context/proposal.json",
        "delta": f"context/{profile}-delta.json",
        "impact": f"positive/{profile}-impact-report.json",
        "assessment": f"positive/{profile}-assessment.json",
    }
    if profile == "breaking":
        names.update(
            {
                "approved": ("positive/breaking-approved-declaration.json"),
                "rejected": ("positive/breaking-rejected-declaration.json"),
            }
        )
    paths = {}
    for name, relative_path in names.items():
        destination = tmp_path / f"{name}.json"
        shutil.copyfile(DEFAULT_FIXTURE_DIRECTORY / relative_path, destination)
        paths[name] = destination
    return paths


def _context_arguments(paths: dict[str, Path]) -> list[str]:
    return [
        "--proposal",
        str(paths["proposal"]),
        "--delta",
        str(paths["delta"]),
        "--base-behavior",
        str(paths["base"]),
        "--final-behavior",
        str(paths["final"]),
    ]


def test_change_help_exposes_governance_overlay() -> None:
    result = runner.invoke(app, ["change", "--help"])

    assert result.exit_code == 0
    for command in ("impact", "assess", "decide", "gate"):
        assert command in result.stdout


def test_impact_and_assessment_commands_publish_exact_immutable_resources(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path, profile="compatible")
    impact_output = tmp_path / "derived-impact.json"
    impact = runner.invoke(
        app,
        [
            "change",
            "impact",
            *_context_arguments(paths),
            "--output",
            str(impact_output),
        ],
    )

    assert impact.exit_code == 0, impact.output
    assert impact.stdout == impact.stderr == ""
    assert parse_impact_report_json(impact_output.read_bytes()) == (
        parse_impact_report_json(paths["impact"].read_bytes())
    )
    assessment_output = tmp_path / "accepted-assessment.json"
    assessment = runner.invoke(
        app,
        [
            "change",
            "assess",
            *_context_arguments(paths),
            "--impact",
            str(impact_output),
            "--assessment",
            str(paths["assessment"]),
            "--output",
            str(assessment_output),
        ],
    )

    assert assessment.exit_code == 0, assessment.output
    assert assessment.stdout == assessment.stderr == ""
    assert parse_decision_assessment_json(
        assessment_output.read_bytes()
    ) == parse_decision_assessment_json(paths["assessment"].read_bytes())
    assert (
        runner.invoke(
            app,
            [
                "change",
                "assess",
                *_context_arguments(paths),
                "--impact",
                str(impact_output),
                "--assessment",
                str(paths["assessment"]),
                "--output",
                str(assessment_output),
            ],
        ).exit_code
        == 0
    )


def test_compatible_gate_passes_without_declaration_and_breaking_gate_blocks(
    tmp_path: Path,
) -> None:
    compatible = _inputs(tmp_path / "compatible", profile="compatible")
    compatible_output = tmp_path / "compatible-gate.json"
    passed = runner.invoke(
        app,
        [
            "change",
            "gate",
            *_context_arguments(compatible),
            "--impact",
            str(compatible["impact"]),
            "--assessment",
            str(compatible["assessment"]),
            "--output",
            str(compatible_output),
        ],
    )

    assert passed.exit_code == 0, passed.output
    assert passed.stdout == passed.stderr == ""
    assert (
        parse_gate_evaluation_json(compatible_output.read_bytes()).status
        is GateStatus.PASS_NO_DECISION
    )

    breaking = _inputs(tmp_path / "breaking", profile="breaking")
    blocked_output = tmp_path / "blocked-gate.json"
    blocked_output.write_bytes(b"preserve-blocked")
    blocked = runner.invoke(
        app,
        [
            "change",
            "gate",
            *_context_arguments(breaking),
            "--impact",
            str(breaking["impact"]),
            "--assessment",
            str(breaking["assessment"]),
            "--output",
            str(blocked_output),
        ],
    )

    assert blocked.exit_code == 1
    assert blocked.stdout == ""
    assert GateStatus.BLOCK_DECISION_REQUIRED.value in blocked.stderr
    assert blocked_output.read_bytes() == b"preserve-blocked"


def test_exact_decision_passes_or_preserves_rejection_without_overwrite(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path, profile="breaking")
    accepted_declaration = tmp_path / "accepted-declaration.json"
    decide = runner.invoke(
        app,
        [
            "change",
            "decide",
            *_context_arguments(paths),
            "--impact",
            str(paths["impact"]),
            "--assessment",
            str(paths["assessment"]),
            "--declaration",
            str(paths["approved"]),
            "--output",
            str(accepted_declaration),
        ],
    )

    assert decide.exit_code == 0, decide.output
    assert decide.stdout == decide.stderr == ""
    assert parse_decision_declaration_json(
        accepted_declaration.read_bytes()
    ) == parse_decision_declaration_json(paths["approved"].read_bytes())

    approved_output = tmp_path / "approved-gate.json"
    approved = runner.invoke(
        app,
        [
            "change",
            "gate",
            *_context_arguments(paths),
            "--impact",
            str(paths["impact"]),
            "--assessment",
            str(paths["assessment"]),
            "--declaration",
            str(accepted_declaration),
            "--output",
            str(approved_output),
        ],
    )
    assert approved.exit_code == 0, approved.output
    assert (
        parse_gate_evaluation_json(approved_output.read_bytes()).status
        is GateStatus.PASS_APPROVED
    )

    rejected_output = tmp_path / "rejected-gate.json"
    rejected_output.write_bytes(b"preserve-rejected")
    rejected = runner.invoke(
        app,
        [
            "change",
            "gate",
            *_context_arguments(paths),
            "--impact",
            str(paths["impact"]),
            "--assessment",
            str(paths["assessment"]),
            "--declaration",
            str(paths["rejected"]),
            "--output",
            str(rejected_output),
        ],
    )
    assert rejected.exit_code == 1
    assert GateStatus.BLOCK_REJECTED.value in rejected.stderr
    assert rejected_output.read_bytes() == b"preserve-rejected"


def test_stale_authored_assessment_is_invalid_and_preserves_output(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path, profile="compatible")
    stale = tmp_path / "stale-assessment.json"
    shutil.copyfile(
        DEFAULT_FIXTURE_DIRECTORY / "invalid" / "stale-impact-assessment.json",
        stale,
    )
    output = tmp_path / "assessment-output.json"
    output.write_bytes(b"preserve-invalid")

    result = runner.invoke(
        app,
        [
            "change",
            "assess",
            *_context_arguments(paths),
            "--impact",
            str(paths["impact"]),
            "--assessment",
            str(stale),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "content_identity_mismatch" in result.stderr
    assert output.read_bytes() == b"preserve-invalid"
    assert not tuple(tmp_path.glob(".assessment-output.json.*.tmp"))


def test_governance_output_cannot_alias_an_input(tmp_path: Path) -> None:
    paths = _inputs(tmp_path, profile="compatible")
    before = paths["delta"].read_bytes()

    result = runner.invoke(
        app,
        [
            "change",
            "impact",
            *_context_arguments(paths),
            "--output",
            str(paths["delta"]),
        ],
    )

    assert result.exit_code == 3
    assert result.stdout == ""
    assert "must differ from every input" in result.stderr
    assert paths["delta"].read_bytes() == before


def test_assessment_source_drift_prevents_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import ucf.cli as cli_module

    paths = _inputs(tmp_path, profile="compatible")
    output = tmp_path / "assessment-output.json"
    output.write_bytes(b"preserve-drift")
    original_publish = cli_module._publish_exact_file

    def mutate_before_publish(
        destination: Path,
        content: bytes,
        *,
        before_publish=None,
    ) -> None:
        paths["impact"].write_bytes(paths["impact"].read_bytes() + b" ")
        original_publish(
            destination,
            content,
            before_publish=before_publish,
        )

    monkeypatch.setattr(
        cli_module,
        "_publish_exact_file",
        mutate_before_publish,
    )
    result = runner.invoke(
        app,
        [
            "change",
            "assess",
            *_context_arguments(paths),
            "--impact",
            str(paths["impact"]),
            "--assessment",
            str(paths["assessment"]),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert "decision assessment input changed" in result.stderr
    assert output.read_bytes() == b"preserve-drift"
    assert not tuple(tmp_path.glob(".assessment-output.json.*.tmp"))


@pytest.mark.parametrize("alias_kind", ("hardlink", "symlink"))
def test_assessment_rejects_an_input_alias_appearing_during_publication(
    tmp_path: Path,
    monkeypatch,
    alias_kind: str,
) -> None:
    import ucf.cli as cli_module

    paths = _inputs(tmp_path, profile="compatible")
    output = tmp_path / "assessment-output.json"
    assessment_before = paths["assessment"].read_bytes()
    original_validate = cli_module._validate_change_input_snapshots
    injected = False

    def validate_then_inject_alias(inputs, *, label: str) -> None:
        nonlocal injected
        original_validate(inputs, label=label)
        if injected:
            return
        injected = True
        if alias_kind == "hardlink":
            output.hardlink_to(paths["assessment"])
        else:
            output.symlink_to(paths["assessment"])

    monkeypatch.setattr(
        cli_module,
        "_validate_change_input_snapshots",
        validate_then_inject_alias,
    )
    result = runner.invoke(
        app,
        [
            "change",
            "assess",
            *_context_arguments(paths),
            "--impact",
            str(paths["impact"]),
            "--assessment",
            str(paths["assessment"]),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert "output" in result.stderr
    assert paths["assessment"].read_bytes() == assessment_before
    assert output.samefile(paths["assessment"])
    assert not tuple(tmp_path.glob(".assessment-output.json.*.tmp"))
