from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.ratchet.test_assessment import _assessment
from tests.ratchet.test_evaluation import _current
from ucf.cli import app
from ucf.onboarding import canonical_onboarding_json
from ucf.ratchet import (
    EvaluationOutcome,
    canonical_ratchet_json,
    establish_ratchet_baseline,
    evaluate_ratchet,
    parse_ratchet_baseline_json,
    parse_ratchet_evaluation_report_json,
)

runner = CliRunner()


def _write(path: Path, document) -> None:
    if document.kind == "onboarding_bundle":
        path.write_bytes(canonical_onboarding_json(document))
    else:
        path.write_bytes(canonical_ratchet_json(document))


def _fixture_files(tmp_path: Path):
    policy, bundle, assessment = _assessment()
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    paths = {
        "policy": tmp_path / "policy.json",
        "bundle": tmp_path / "bundle.json",
        "assessment": tmp_path / "assessment.json",
        "baseline": tmp_path / "baseline.json",
    }
    _write(paths["policy"], policy)
    _write(paths["bundle"], bundle)
    _write(paths["assessment"], assessment)
    _write(paths["baseline"], baseline)
    return policy, bundle, assessment, baseline, paths


def _common(paths: dict[str, Path], assessment: Path) -> list[str]:
    return [
        "--policy",
        str(paths["policy"]),
        "--onboarding-bundle",
        str(paths["bundle"]),
        "--assessment",
        str(assessment),
    ]


def test_ratchet_establish_writes_repeatable_canonical_initial_baseline(
    tmp_path: Path,
) -> None:
    _, _, _, baseline, paths = _fixture_files(tmp_path)
    first = tmp_path / "established-a.json"
    second = tmp_path / "established-b.json"
    arguments = _common(paths, paths["assessment"])

    first_result = runner.invoke(
        app,
        ["ratchet", "establish", *arguments, "--output", str(first)],
    )
    second_result = runner.invoke(
        app,
        ["ratchet", "establish", *arguments, "--output", str(second)],
    )

    assert first_result.exit_code == 0, first_result.output
    assert second_result.exit_code == 0, second_result.output
    assert first_result.stdout == first_result.stderr == ""
    assert second_result.stdout == second_result.stderr == ""
    assert first.read_bytes() == second.read_bytes()
    assert parse_ratchet_baseline_json(first.read_bytes()) == baseline
    assert first.read_bytes() == canonical_ratchet_json(baseline)


def test_ratchet_evaluate_writes_report_before_policy_exit(
    tmp_path: Path,
) -> None:
    policy, bundle, _, baseline, paths = _fixture_files(tmp_path)
    current = _current(
        policy,
        bundle,
        "required-check",
        "second-check",
    )
    current_path = tmp_path / "current.json"
    report_path = tmp_path / "report.json"
    _write(current_path, current)
    baseline_before = paths["baseline"].read_bytes()

    result = runner.invoke(
        app,
        [
            "ratchet",
            "evaluate",
            *_common(paths, current_path),
            "--baseline",
            str(paths["baseline"]),
            "--output",
            str(report_path),
        ],
    )

    assert result.exit_code == 1, result.output
    assert result.stdout == result.stderr == ""
    report = parse_ratchet_evaluation_report_json(
        report_path.read_bytes()
    )
    assert report.outcome is EvaluationOutcome.FAIL
    assert report == evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
    )
    assert paths["baseline"].read_bytes() == baseline_before


def test_ratchet_resolved_debt_advances_and_reintroduction_fails(
    tmp_path: Path,
) -> None:
    policy, bundle, _, baseline, paths = _fixture_files(tmp_path)
    resolved = _current(policy, bundle)
    resolved_path = tmp_path / "resolved.json"
    report_path = tmp_path / "resolved-report.json"
    successor_path = tmp_path / "successor.json"
    _write(resolved_path, resolved)
    common = _common(paths, resolved_path)

    evaluated = runner.invoke(
        app,
        [
            "ratchet",
            "evaluate",
            *common,
            "--baseline",
            str(paths["baseline"]),
            "--output",
            str(report_path),
        ],
    )
    advanced = runner.invoke(
        app,
        [
            "ratchet",
            "advance",
            *common,
            "--baseline",
            str(paths["baseline"]),
            "--evaluation",
            str(report_path),
            "--output",
            str(successor_path),
        ],
    )

    assert evaluated.exit_code == 0, evaluated.output
    assert advanced.exit_code == 0, advanced.output
    successor = parse_ratchet_baseline_json(successor_path.read_bytes())
    assert successor.predecessor is not None
    assert successor.predecessor.target_id == baseline.id
    assert successor.allowances == ()
    assert successor.protected

    reintroduced = _current(policy, bundle, "required-check")
    reintroduced_path = tmp_path / "reintroduced.json"
    reintroduced_report = tmp_path / "reintroduced-report.json"
    _write(reintroduced_path, reintroduced)
    result = runner.invoke(
        app,
        [
            "ratchet",
            "evaluate",
            *_common(paths, reintroduced_path),
            "--baseline",
            str(successor_path),
            "--output",
            str(reintroduced_report),
        ],
    )

    assert result.exit_code == 1
    assert parse_ratchet_evaluation_report_json(
        reintroduced_report.read_bytes()
    ).outcome is EvaluationOutcome.FAIL


def test_blocked_advance_preserves_existing_output(tmp_path: Path) -> None:
    policy, bundle, _, _, paths = _fixture_files(tmp_path)
    current = _current(
        policy,
        bundle,
        "required-check",
        "second-check",
    )
    current_path = tmp_path / "regression.json"
    report_path = tmp_path / "regression-report.json"
    successor_path = tmp_path / "successor.json"
    _write(current_path, current)
    report = evaluate_ratchet(
        policy,
        parse_ratchet_baseline_json(paths["baseline"].read_bytes()),
        bundle,
        current,
    )
    _write(report_path, report)
    successor_path.write_bytes(b"preserve-me")

    result = runner.invoke(
        app,
        [
            "ratchet",
            "advance",
            *_common(paths, current_path),
            "--baseline",
            str(paths["baseline"]),
            "--evaluation",
            str(report_path),
            "--output",
            str(successor_path),
        ],
    )

    assert result.exit_code == 1, result.output
    assert result.stdout == result.stderr == ""
    assert successor_path.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".successor.json.*.tmp"))


def test_invalid_ratchet_input_preserves_output_and_temporary_cleanup(
    tmp_path: Path,
) -> None:
    _, _, _, _, paths = _fixture_files(tmp_path)
    output = tmp_path / "output.json"
    output.write_bytes(b"preserve-me")
    encoded = paths["policy"].read_text(encoding="utf-8")
    paths["policy"].write_text(
        encoded.replace(
            '"kind":"ratchet_policy"',
            '"kind":"ratchet_policy","kind":"ratchet_policy"',
            1,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "ratchet",
            "establish",
            *_common(paths, paths["assessment"]),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".output.json.*.tmp"))


@pytest.mark.parametrize(
    "input_name",
    ["policy", "bundle", "assessment", "baseline"],
)
def test_ratchet_rejects_output_equal_to_every_input(
    tmp_path: Path,
    input_name: str,
) -> None:
    _, _, _, _, paths = _fixture_files(tmp_path)
    target = paths[input_name]
    before = target.read_bytes()

    result = runner.invoke(
        app,
        [
            "ratchet",
            "evaluate",
            *_common(paths, paths["assessment"]),
            "--baseline",
            str(paths["baseline"]),
            "--output",
            str(target),
        ],
    )

    assert result.exit_code == 3
    assert "output must differ from every input" in result.stderr
    assert target.read_bytes() == before


def test_ratchet_rejects_output_hard_linked_to_input(
    tmp_path: Path,
) -> None:
    _, _, _, _, paths = _fixture_files(tmp_path)
    target = paths["policy"]
    before = target.read_bytes()
    output = tmp_path / "policy-hard-link.json"
    output.hardlink_to(target)

    result = runner.invoke(
        app,
        [
            "ratchet",
            "establish",
            *_common(paths, paths["assessment"]),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
    assert "output must differ from every input" in result.stderr
    assert target.read_bytes() == before
    assert output.read_bytes() == before


@pytest.mark.parametrize("destination", ["symlink", "directory", "missing"])
def test_ratchet_rejects_unsafe_output_destination(
    tmp_path: Path,
    destination: str,
) -> None:
    _, _, _, _, paths = _fixture_files(tmp_path)
    if destination == "symlink":
        target = tmp_path / "target.json"
        target.write_bytes(b"preserve-me")
        output = tmp_path / "output.json"
        output.symlink_to(target)
    elif destination == "directory":
        output = tmp_path / "output"
        output.mkdir()
    else:
        output = tmp_path / "missing" / "output.json"

    result = runner.invoke(
        app,
        [
            "ratchet",
            "establish",
            *_common(paths, paths["assessment"]),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 3
