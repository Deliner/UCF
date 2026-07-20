"""CLI validation boundary tests."""

from __future__ import annotations

from typer.testing import CliRunner

from ucf.cli import app

runner = CliRunner()


def test_validate_reports_duplicate_identity_without_traceback(tmp_path) -> None:
    action = """\
kind: action
metadata:
  name: duplicate
"""
    (tmp_path / "first.yaml").write_text(action, encoding="utf-8")
    (tmp_path / "second.yaml").write_text(action, encoding="utf-8")

    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "Duplicate spec 'action/duplicate'" in result.output
    assert "first.yaml" in result.output
    assert "second.yaml" in result.output
    assert "Traceback" not in result.output
