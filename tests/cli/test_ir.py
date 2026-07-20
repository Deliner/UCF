"""CLI tests for the installed behavior IR validation boundary."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ucf.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ir" / "v1"


def test_ir_validate_accepts_the_complete_v1_fixture():
    result = runner.invoke(
        app,
        ["ir", "validate", str(FIXTURES / "complete.json")],
    )

    assert result.exit_code == 0
    assert "IR 1.0.0 valid" in result.output
    assert "document.checkout-reservation" in result.output


def test_ir_validate_reports_stable_semantic_error_without_traceback():
    result = runner.invoke(
        app,
        [
            "ir",
            "validate",
            str(FIXTURES / "invalid" / "broken-reference.json"),
        ],
    )

    assert result.exit_code == 1
    assert "broken_reference" in result.output
    assert "use-case.missing" in result.output
    assert "Traceback" not in result.output
