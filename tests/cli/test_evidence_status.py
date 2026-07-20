from __future__ import annotations

import threading
from pathlib import Path

import pytest
from typer.testing import CliRunner

import ucf.cli as cli_module
from tests.evidence_status._support import (
    EvidenceContext,
    baseline_context,
    current_assessment_arguments,
    reason_codes,
    record_arguments,
    recorded_assessment_arguments,
    status_value,
    target_source_context,
)
from ucf.cli import app
from ucf.evidence_status import (
    assess_verification_evidence,
    canonical_evidence_status_json,
    parse_verification_evidence_assessment_json,
    parse_verification_evidence_envelope_json,
    record_verification_evidence,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    canonical_implementation_evidence_json,
    derive_execution_verification_result_id,
)
from ucf.inventory import canonical_inventory_json
from ucf.onboarding import canonical_onboarding_json

runner = CliRunner()


def test_exact_file_publication_never_replaces_a_concurrent_creator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    competitor_started = threading.Event()
    competitor_finished = threading.Event()
    original_exists = cli_module._path_entry_exists
    destination_checks = 0

    def create_competing_output() -> None:
        assert competitor_started.wait(timeout=5)
        output.write_bytes(b"concurrent-winner")
        competitor_finished.set()

    competitor = threading.Thread(target=create_competing_output)
    competitor.start()

    def coordinate_after_last_check(path: Path) -> bool:
        nonlocal destination_checks
        exists = original_exists(path)
        if path == output:
            destination_checks += 1
            if destination_checks == 2:
                competitor_started.set()
                assert competitor_finished.wait(timeout=5)
        return exists

    monkeypatch.setattr(
        cli_module,
        "_path_entry_exists",
        coordinate_after_last_check,
    )
    try:
        with pytest.raises(
            ValueError,
            match="output appeared before publication",
        ):
            cli_module._publish_exact_file(output, b"ucf-output")
    finally:
        competitor_started.set()
        competitor.join(timeout=5)

    assert not competitor.is_alive()
    assert output.read_bytes() == b"concurrent-winner"
    assert not tuple(tmp_path.glob(".evidence.json.*.tmp"))


def test_cli_records_canonical_evidence_deterministically_and_idempotently(
    tmp_path: Path,
) -> None:
    context = baseline_context()
    paths = _write_context(tmp_path, "recorded", context)
    first = tmp_path / "envelope.json"
    second = tmp_path / "envelope-copy.json"

    first_run = runner.invoke(
        app,
        _record_arguments(paths, context, first),
    )
    first_inode = first.stat().st_ino if first.exists() else None
    retry = runner.invoke(
        app,
        _record_arguments(paths, context, first),
    )
    second_run = runner.invoke(
        app,
        _record_arguments(paths, context, second),
    )

    assert first_run.exit_code == 0, first_run.output
    assert retry.exit_code == 0, retry.output
    assert second_run.exit_code == 0, second_run.output
    assert first_run.stdout == first_run.stderr == ""
    assert retry.stdout == retry.stderr == ""
    assert second_run.stdout == second_run.stderr == ""
    assert first.stat().st_ino == first_inode
    assert first.read_bytes() == second.read_bytes()
    envelope = parse_verification_evidence_envelope_json(first.read_bytes())
    expected = record_verification_evidence(
        context.result,
        **record_arguments(context),
    )
    assert envelope == expected
    assert first.read_bytes() == canonical_evidence_status_json(expected)
    assert b'"verified"' not in first.read_bytes()


@pytest.mark.parametrize("outcome", ("failed", "error"))
def test_cli_records_only_passed_verification_without_mutating_output(
    tmp_path: Path,
    outcome: str,
) -> None:
    context = baseline_context()
    paths = _write_context(tmp_path, "recorded", context)
    result = context.result.model_copy(update={"outcome": outcome})
    result = result.model_copy(
        update={"id": derive_execution_verification_result_id(result)}
    )
    paths["result"].write_bytes(
        canonical_implementation_evidence_json(result)
    )
    output = tmp_path / f"envelope-{outcome}.json"
    output.write_bytes(b"preserve-me")

    recorded = runner.invoke(
        app,
        _record_arguments(paths, context, output),
    )

    assert recorded.exit_code == 3
    assert "passed" in recorded.stderr
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))


def test_cli_assesses_fresh_stale_and_indeterminate_with_gate_exit_codes(
    tmp_path: Path,
) -> None:
    recorded = baseline_context()
    recorded_paths = _write_context(tmp_path, "recorded", recorded)
    envelope_path = tmp_path / "envelope.json"
    recorded_run = runner.invoke(
        app,
        _record_arguments(recorded_paths, recorded, envelope_path),
    )
    assert recorded_run.exit_code == 0, recorded_run.output

    cases = (
        ("fresh", recorded, 0, ()),
        (
            "stale",
            target_source_context(),
            1,
            ("mapping_binding_changed", "source_binding_changed"),
        ),
        ("indeterminate", None, 1, ("current_context_unavailable",)),
    )
    for name, current, exit_code, expected_reasons in cases:
        current_paths = (
            None
            if current is None
            else _write_context(tmp_path, f"current-{name}", current)
        )
        output = tmp_path / f"assessment-{name}.json"

        result = runner.invoke(
            app,
            _assess_arguments(
                envelope_path,
                recorded_paths,
                recorded,
                output,
                current_paths=current_paths,
                current=current,
            ),
        )

        assert result.exit_code == exit_code, result.output
        assert result.stdout == result.stderr == ""
        assessment = parse_verification_evidence_assessment_json(
            output.read_bytes()
        )
        assert status_value(assessment.status) == name
        assert reason_codes(assessment) == expected_reasons
        expected = assess_verification_evidence(
            parse_verification_evidence_envelope_json(
                envelope_path.read_bytes()
            ),
            **recorded_assessment_arguments(recorded),
            **(
                {}
                if current is None
                else current_assessment_arguments(current)
            ),
        )
        assert assessment == expected
        assert output.read_bytes() == canonical_evidence_status_json(expected)
        assert b'"verified"' not in output.read_bytes()


@pytest.mark.parametrize(
    "missing_option",
    (
        "--current-result",
        "--current-mapping-result",
        "--current-onboarding-bundle",
        "--current-inventory",
        "--current-mapping-adapter-name",
        "--current-mapping-adapter-version",
        "--current-verification-adapter-name",
        "--current-verification-adapter-version",
        "--current-mapping-capability-version",
        "--current-verification-capability-version",
    ),
)
def test_cli_rejects_partial_current_context_without_mutating_output(
    tmp_path: Path,
    missing_option: str,
) -> None:
    context = baseline_context()
    paths = _write_context(tmp_path, "recorded", context)
    envelope_path = tmp_path / "envelope.json"
    assert (
        runner.invoke(
            app,
            _record_arguments(paths, context, envelope_path),
        ).exit_code
        == 0
    )
    output = tmp_path / "assessment.json"
    output.write_bytes(b"preserve-me")
    arguments = _assess_arguments(
        envelope_path,
        paths,
        context,
        output,
        current_paths=paths,
        current=context,
    )
    missing_index = arguments.index(missing_option)
    del arguments[missing_index : missing_index + 2]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 3
    assert "current evidence context must be supplied completely or omitted" in (
        result.stderr
    )
    assert output.read_bytes() == b"preserve-me"
    assert not tuple(tmp_path.glob(".assessment.json.*.tmp"))


def test_cli_record_rejects_invalid_capability_and_output_alias(
    tmp_path: Path,
) -> None:
    context = baseline_context()
    paths = _write_context(tmp_path, "recorded", context)
    sentinel = tmp_path / "envelope.json"
    sentinel.write_bytes(b"preserve-me")
    invalid_arguments = _record_arguments(paths, context, sentinel)
    capability_index = invalid_arguments.index(
        "--verification-capability-version"
    )
    invalid_arguments[capability_index + 1] = "2.0.0"

    invalid = runner.invoke(app, invalid_arguments)
    alias = runner.invoke(
        app,
        _record_arguments(paths, context, paths["result"]),
    )

    assert invalid.exit_code == 3
    assert "capability_mismatch" in invalid.stderr
    assert sentinel.read_bytes() == b"preserve-me"
    assert alias.exit_code == 3
    assert "output must differ from every input" in alias.stderr
    assert paths["result"].read_bytes() == (
        canonical_implementation_evidence_json(context.result)
    )


def _write_context(
    directory: Path,
    prefix: str,
    context: EvidenceContext,
) -> dict[str, Path]:
    paths = {
        "result": directory / f"{prefix}-result.json",
        "mapping": directory / f"{prefix}-mapping.json",
        "bundle": directory / f"{prefix}-bundle.json",
        "inventory": directory / f"{prefix}-inventory.json",
    }
    paths["result"].write_bytes(
        canonical_implementation_evidence_json(context.result)
    )
    paths["mapping"].write_bytes(
        canonical_implementation_evidence_json(context.mapping_result)
    )
    paths["bundle"].write_bytes(canonical_onboarding_json(context.bundle))
    paths["inventory"].write_bytes(
        canonical_inventory_json(context.bundle.inventory)
    )
    return paths


def _record_arguments(
    paths: dict[str, Path],
    context: EvidenceContext,
    output: Path,
) -> list[str]:
    return [
        "evidence",
        "record",
        "--result",
        str(paths["result"]),
        "--mapping-result",
        str(paths["mapping"]),
        "--onboarding-bundle",
        str(paths["bundle"]),
        "--inventory",
        str(paths["inventory"]),
        "--mapping-adapter-name",
        context.mapping_initialized_adapter.name,
        "--mapping-adapter-version",
        context.mapping_initialized_adapter.version,
        "--verification-adapter-name",
        context.initialized_adapter.name,
        "--verification-adapter-version",
        context.initialized_adapter.version,
        "--mapping-capability-version",
        context.negotiated_capabilities[IMPLEMENTATION_MAPPING_CAPABILITY],
        "--verification-capability-version",
        context.negotiated_capabilities[EXECUTION_VERIFICATION_CAPABILITY],
        "--output",
        str(output),
    ]


def _assess_arguments(
    envelope: Path,
    recorded_paths: dict[str, Path],
    recorded: EvidenceContext,
    output: Path,
    *,
    current_paths: dict[str, Path] | None = None,
    current: EvidenceContext | None = None,
) -> list[str]:
    arguments = [
        "evidence",
        "assess",
        "--envelope",
        str(envelope),
        *_context_arguments("recorded", recorded_paths, recorded),
        "--output",
        str(output),
    ]
    if current_paths is not None and current is not None:
        arguments.extend(
            _context_arguments("current", current_paths, current)
        )
    return arguments


def _context_arguments(
    prefix: str,
    paths: dict[str, Path],
    context: EvidenceContext,
) -> list[str]:
    return [
        f"--{prefix}-result",
        str(paths["result"]),
        f"--{prefix}-mapping-result",
        str(paths["mapping"]),
        f"--{prefix}-onboarding-bundle",
        str(paths["bundle"]),
        f"--{prefix}-inventory",
        str(paths["inventory"]),
        f"--{prefix}-mapping-adapter-name",
        context.mapping_initialized_adapter.name,
        f"--{prefix}-mapping-adapter-version",
        context.mapping_initialized_adapter.version,
        f"--{prefix}-verification-adapter-name",
        context.initialized_adapter.name,
        f"--{prefix}-verification-adapter-version",
        context.initialized_adapter.version,
        f"--{prefix}-mapping-capability-version",
        context.negotiated_capabilities[IMPLEMENTATION_MAPPING_CAPABILITY],
        f"--{prefix}-verification-capability-version",
        context.negotiated_capabilities[EXECUTION_VERIFICATION_CAPABILITY],
    ]
