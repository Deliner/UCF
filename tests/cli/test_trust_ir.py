"""CLI tests for the complete trust IR validation boundary."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ucf.cli import app

runner = CliRunner()
IR_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ir"
BEHAVIOR = IR_FIXTURES / "v1" / "complete.json"
TRUST = IR_FIXTURES / "trust" / "v1" / "complete.json"


def test_trust_validate_accepts_exact_overlay_and_behavior_document():
    result = runner.invoke(
        app,
        [
            "trust",
            "validate",
            str(TRUST),
            "--behavior-ir",
            str(BEHAVIOR),
        ],
    )

    assert result.exit_code == 0
    assert "Trust IR 1.0.0 valid" in result.output
    assert "document.trust-reservation-review" in result.output
    assert "document.checkout-reservation" in result.output


def test_trust_validate_requires_the_referenced_behavior_document():
    result = runner.invoke(app, ["trust", "validate", str(TRUST)])

    assert result.exit_code != 0
    assert "--behavior-ir" in result.output
    assert "Trust IR 1.0.0 valid" not in result.output


def test_trust_validate_reports_internal_error_without_traceback(tmp_path):
    payload = json.loads(TRUST.read_text())
    mapping = next(
        record for record in payload["records"] if record["kind"] == "mapping"
    )
    mapping["observation"]["target_id"] = "observed.missing"
    invalid = tmp_path / "invalid-trust.json"
    invalid.write_text(json.dumps(payload))

    result = runner.invoke(
        app,
        [
            "trust",
            "validate",
            str(invalid),
            "--behavior-ir",
            str(BEHAVIOR),
        ],
    )

    assert result.exit_code == 1
    assert "broken_reference" in result.output
    assert "observed.missing" in result.output
    assert "Traceback" not in result.output


def test_trust_validate_reports_document_digest_mismatch_without_traceback(
    tmp_path,
):
    payload = json.loads(BEHAVIOR.read_text())
    effect = next(
        entity for entity in payload["entities"] if entity["kind"] == "effect"
    )
    effect["value"]["value"] = "changed"
    changed_behavior = tmp_path / "changed-behavior.json"
    changed_behavior.write_text(json.dumps(payload))

    result = runner.invoke(
        app,
        [
            "trust",
            "validate",
            str(TRUST),
            "--behavior-ir",
            str(changed_behavior),
        ],
    )

    assert result.exit_code == 1
    assert "document_identity_mismatch" in result.output
    assert "canonical_digest" in result.output
    assert "Traceback" not in result.output
