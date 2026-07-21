from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from tests.onboarding.test_bundle import _bundle
from tests.ratchet.test_assessment import _assessment as _v1_assessment
from tests.ratchet.test_touch_projection import _candidate_confidence_change
from tests.ratchet_v2.test_assessment import _assessment, _uncovered_bundle
from tests.ratchet_v2.test_migration import _compatible_target_policy
from tests.ratchet_v2.test_policy import _policy
from ucf.cli import app
from ucf.onboarding import canonical_onboarding_json
from ucf.ratchet import canonical_ratchet_json as canonical_v1_json
from ucf.ratchet import establish_ratchet_baseline as establish_v1_baseline
from ucf.ratchet.v2 import (
    CombinedOutcome,
    RatchetBaselineOrigin,
    build_ratchet_assessment,
    canonical_ratchet_json,
    establish_ratchet_baseline,
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
    policy = _policy()
    bundle = _uncovered_bundle()
    assessment = _assessment(bundle)
    baseline = establish_ratchet_baseline(policy, bundle, assessment)
    paths = {
        "policy": tmp_path / "policy-v2.json",
        "bundle": tmp_path / "bundle.json",
        "assessment": tmp_path / "assessment-v2.json",
        "baseline": tmp_path / "baseline-v2.json",
    }
    _write(paths["policy"], policy)
    _write(paths["bundle"], bundle)
    _write(paths["assessment"], assessment)
    _write(paths["baseline"], baseline)
    return policy, bundle, assessment, baseline, paths


def _common(paths: dict[str, Path]) -> list[str]:
    return [
        "--policy",
        str(paths["policy"]),
        "--onboarding-bundle",
        str(paths["bundle"]),
        "--assessment",
        str(paths["assessment"]),
    ]


def test_v2_establish_is_explicit_and_deterministic(tmp_path: Path) -> None:
    _, _, _, baseline, paths = _fixture_files(tmp_path)
    output = tmp_path / "established-v2.json"
    repeated = tmp_path / "established-v2-repeated.json"

    result = runner.invoke(
        app,
        ["ratchet", "v2", "establish", *_common(paths), "--output", str(output)],
    )
    second = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "establish",
            *_common(paths),
            "--output",
            str(repeated),
        ],
    )

    assert result.exit_code == 0, result.output
    assert second.exit_code == 0, second.output
    assert result.stdout == result.stderr == ""
    assert output.read_bytes() == repeated.read_bytes()
    assert parse_ratchet_baseline_json(output.read_bytes()) == baseline


def test_v2_evaluate_requires_pin_and_preserves_qualified_outcome(
    tmp_path: Path,
) -> None:
    _, _, _, baseline, paths = _fixture_files(tmp_path)
    report_path = tmp_path / "report-v2.json"
    arguments = [
        "ratchet",
        "v2",
        "evaluate",
        *_common(paths),
        "--baseline",
        str(paths["baseline"]),
        "--accepted-baseline-id",
        baseline.id,
        "--output",
        str(report_path),
    ]

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.output
    report = parse_ratchet_evaluation_report_json(report_path.read_bytes())
    assert report.combined_outcome is (
        CombinedOutcome.PASS_WITH_LEGACY_COVERAGE_DEBT
    )

    wrong_path = tmp_path / "wrong.json"
    wrong_path.write_bytes(b"preserve-existing-output\n")
    wrong = runner.invoke(
        app,
        [
            *arguments[:-3],
            f"baseline.{'f' * 64}",
            "--output",
            str(wrong_path),
        ],
    )
    assert wrong.exit_code == 3
    assert "document_identity_mismatch" in wrong.stderr
    assert wrong_path.read_bytes() == b"preserve-existing-output\n"


def test_v2_failing_evaluation_is_published_but_cannot_advance(
    tmp_path: Path,
) -> None:
    policy = _policy()
    initial_bundle = _bundle()
    initial = _assessment(initial_bundle)
    baseline = establish_ratchet_baseline(policy, initial_bundle, initial)
    current_bundle = _candidate_confidence_change(
        initial_bundle,
        "legacy-discount-hint",
    )
    current = _assessment(current_bundle)
    paths = {
        "policy": tmp_path / "policy-v2.json",
        "bundle": tmp_path / "bundle.json",
        "assessment": tmp_path / "assessment-v2.json",
        "baseline": tmp_path / "baseline-v2.json",
    }
    for name, document in (
        ("policy", policy),
        ("bundle", current_bundle),
        ("assessment", current),
        ("baseline", baseline),
    ):
        _write(paths[name], document)
    report_path = tmp_path / "failed-report-v2.json"
    successor_path = tmp_path / "blocked-successor-v2.json"
    successor_path.write_bytes(b"preserve-blocked-successor\n")

    evaluated = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "evaluate",
            *_common(paths),
            "--baseline",
            str(paths["baseline"]),
            "--accepted-baseline-id",
            baseline.id,
            "--output",
            str(report_path),
        ],
    )
    advanced = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "advance",
            *_common(paths),
            "--baseline",
            str(paths["baseline"]),
            "--evaluation",
            str(report_path),
            "--accepted-baseline-id",
            baseline.id,
            "--output",
            str(successor_path),
        ],
    )

    assert evaluated.exit_code == 1, evaluated.output
    assert parse_ratchet_evaluation_report_json(
        report_path.read_bytes()
    ).combined_outcome is CombinedOutcome.FAIL
    assert advanced.exit_code == 1, advanced.output
    assert successor_path.read_bytes() == b"preserve-blocked-successor\n"


def test_v2_inconclusive_evaluation_is_published_and_returns_one(
    tmp_path: Path,
) -> None:
    policy, bundle, source, baseline, paths = _fixture_files(tmp_path)
    partial = build_ratchet_assessment(
        policy,
        bundle,
        producer=source.producer,
        procedure_uri=source.procedure_uri,
        capture_context=source.capture_context,
        partial_rule_ids={policy.rules[0].id},
    )
    _write(paths["assessment"], partial)
    report_path = tmp_path / "inconclusive-report-v2.json"

    evaluated = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "evaluate",
            *_common(paths),
            "--baseline",
            str(paths["baseline"]),
            "--accepted-baseline-id",
            baseline.id,
            "--output",
            str(report_path),
        ],
    )

    assert evaluated.exit_code == 1, evaluated.output
    assert parse_ratchet_evaluation_report_json(
        report_path.read_bytes()
    ).combined_outcome is CombinedOutcome.INCONCLUSIVE


def test_v2_advance_keeps_qualified_debt_visible(tmp_path: Path) -> None:
    _, _, _, baseline, paths = _fixture_files(tmp_path)
    report_path = tmp_path / "report-v2.json"
    successor_path = tmp_path / "successor-v2.json"
    common = _common(paths)
    evaluated = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "evaluate",
            *common,
            "--baseline",
            str(paths["baseline"]),
            "--accepted-baseline-id",
            baseline.id,
            "--output",
            str(report_path),
        ],
    )
    advanced = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "advance",
            *common,
            "--baseline",
            str(paths["baseline"]),
            "--accepted-baseline-id",
            baseline.id,
            "--evaluation",
            str(report_path),
            "--output",
            str(successor_path),
        ],
    )

    assert evaluated.exit_code == 0, evaluated.output
    assert advanced.exit_code == 0, advanced.output
    successor = parse_ratchet_baseline_json(successor_path.read_bytes())
    assert successor.generation == 1
    assert successor.coverage.allowances == baseline.coverage.allowances


def test_v2_migration_requires_all_v1_sources_and_accepted_tip(
    tmp_path: Path,
) -> None:
    source_policy, bundle, source_assessment = _v1_assessment()
    source_baseline = establish_v1_baseline(
        source_policy,
        bundle,
        source_assessment,
    )
    target_policy = _compatible_target_policy(source_policy)
    paths = {
        "target": tmp_path / "target-v2-policy.json",
        "policy": tmp_path / "source-v1-policy.json",
        "baseline": tmp_path / "source-v1-baseline.json",
        "assessment": tmp_path / "source-v1-assessment.json",
        "bundle": tmp_path / "bundle.json",
        "output": tmp_path / "migrated-v2.json",
    }
    paths["target"].write_bytes(canonical_ratchet_json(target_policy))
    paths["policy"].write_bytes(canonical_v1_json(source_policy))
    paths["baseline"].write_bytes(canonical_v1_json(source_baseline))
    paths["assessment"].write_bytes(canonical_v1_json(source_assessment))
    paths["bundle"].write_bytes(canonical_onboarding_json(bundle))

    result = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "migrate-from-v1",
            "--target-policy",
            str(paths["target"]),
            "--source-policy",
            str(paths["policy"]),
            "--source-baseline",
            str(paths["baseline"]),
            "--source-assessment",
            str(paths["assessment"]),
            "--onboarding-bundle",
            str(paths["bundle"]),
            "--accepted-source-baseline-id",
            source_baseline.id,
            "--output",
            str(paths["output"]),
        ],
    )

    assert result.exit_code == 0, result.output
    migrated = parse_ratchet_baseline_json(paths["output"].read_bytes())
    assert migrated.origin is RatchetBaselineOrigin.MIGRATED_V1
    assert migrated.migrated_from is not None
    assert migrated.migrated_from.baseline.target_id == source_baseline.id

    paths["output"].write_bytes(b"preserve-migration-output\n")
    wrong = runner.invoke(
        app,
        [
            "ratchet",
            "v2",
            "migrate-from-v1",
            "--target-policy",
            str(paths["target"]),
            "--source-policy",
            str(paths["policy"]),
            "--source-baseline",
            str(paths["baseline"]),
            "--source-assessment",
            str(paths["assessment"]),
            "--onboarding-bundle",
            str(paths["bundle"]),
            "--accepted-source-baseline-id",
            f"baseline.{'f' * 64}",
            "--output",
            str(paths["output"]),
        ],
    )
    assert wrong.exit_code == 3
    assert "migration_source_mismatch" in wrong.stderr
    assert paths["output"].read_bytes() == b"preserve-migration-output\n"
