"""CLI generation capability-boundary tests."""

from __future__ import annotations

from click import unstyle
from rich.console import Console
from typer.testing import CliRunner

import ucf.cli as cli_module
from ucf.cli import app

runner = CliRunner()


def _write_minimal_supported_specs(specs_dir) -> None:
    (specs_dir / "actions").mkdir(parents=True)
    (specs_dir / "use-cases").mkdir()
    (specs_dir / "actions" / "work.yaml").write_text(
        """\
kind: action
metadata:
  name: work
""",
        encoding="utf-8",
    )
    (specs_dir / "use-cases" / "work.yaml").write_text(
        """\
kind: usecase
metadata:
  name: work
steps:
  - id: work
    use: actions/work
""",
        encoding="utf-8",
    )


def test_generate_rejects_retry_without_partial_output(tmp_path) -> None:
    specs_dir = tmp_path / "specs"
    output_dir = tmp_path / "generated"
    (specs_dir / "actions").mkdir(parents=True)
    (specs_dir / "use-cases").mkdir()
    (specs_dir / "actions" / "work.yaml").write_text(
        """\
kind: action
metadata:
  name: work
""",
        encoding="utf-8",
    )
    (specs_dir / "use-cases" / "retry.yaml").write_text(
        """\
kind: usecase
metadata:
  name: retry-flow
steps:
  - id: attempt
    use: actions/work
    retry:
      max_attempts: 3
      on_error: temporary-failure
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["generate", str(specs_dir), "--output", str(output_dir)],
    )

    assert result.exit_code == 1
    assert "unsupported" in result.output.lower()
    assert "steps.attempt.retry" in result.output
    assert "Traceback" not in result.output
    assert not output_dir.exists()


def test_generate_rejects_mixed_parse_errors_before_writing(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(cli_module, "console", Console(width=10))
    specs_dir = tmp_path / "specs"
    output_dir = tmp_path / "generated"
    _write_minimal_supported_specs(specs_dir)
    (specs_dir / "actions" / "invalid.yaml").write_text(
        """\
kind: action
metadata:
  name: invalid
unknown_field: silently-dropped
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["generate", str(specs_dir), "--output", str(output_dir)],
    )

    assert result.exit_code == 1
    terminal_text = unstyle(result.output).replace("\n", "")
    assert "Parse errors" in terminal_text
    assert "invalid.yaml" in terminal_text
    assert not output_dir.exists()


def test_generate_rejects_reference_errors_before_writing(tmp_path) -> None:
    specs_dir = tmp_path / "specs"
    output_dir = tmp_path / "generated"
    (specs_dir / "use-cases").mkdir(parents=True)
    (specs_dir / "use-cases" / "broken.yaml").write_text(
        """\
kind: usecase
metadata:
  name: broken
steps:
  - id: missing
    use: actions/missing
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["generate", str(specs_dir), "--output", str(output_dir)],
    )

    assert result.exit_code == 1
    assert "Validation errors" in result.output
    assert "step reference 'actions/missing'" in result.output
    assert not output_dir.exists()
