from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.generation._support import generation_request
from ucf.cli import app
from ucf.generation import canonical_generation_json

runner = CliRunner()
REPOSITORY_ROOT = Path(__file__).parents[2]
ADAPTER = REPOSITORY_ROOT / "adapters" / "python-pytest" / "adapter.py"


def _arguments(
    request_path: Path,
    destination: Path,
) -> list[str]:
    return [
        "generation",
        "run",
        str(request_path),
        "--destination",
        str(destination),
        "--adapter-cwd",
        str(REPOSITORY_ROOT),
        "--operation-timeout",
        "5",
        "--",
        sys.executable,
        "-I",
        "-B",
        "-X",
        "utf8",
        str(ADAPTER),
    ]


def test_generation_run_is_executable_idempotent_and_preserves_user_code(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_bytes(canonical_generation_json(generation_request()))
    implementation = tmp_path / "legacy_inventory.py"
    implementation.write_text(
        """\
def reserve_item(*, item_id: str) -> str:
    assert item_id == "sku-123"
    return "reservation-456"
""",
        encoding="utf-8",
    )
    implementation_digest = hashlib.sha256(
        implementation.read_bytes()
    ).hexdigest()
    destination = tmp_path / "generated"

    first = runner.invoke(app, _arguments(request_path, destination))
    assert first.exit_code == 0, first.output
    assert "created" in first.output
    second = runner.invoke(app, _arguments(request_path, destination))
    assert second.exit_code == 0, second.output
    assert "unchanged" in second.output

    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            str(destination),
        ),
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "1 passed" in completed.stdout
    assert hashlib.sha256(implementation.read_bytes()).hexdigest() == (
        implementation_digest
    )


def test_generation_run_rejects_invalid_request_without_output(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text('{"kind":"generation_request"}\n')
    destination = tmp_path / "generated"

    result = runner.invoke(app, _arguments(request_path, destination))

    assert result.exit_code == 3
    assert "Traceback" not in result.output
    assert not destination.exists()


def test_generation_noop_rejects_a_request_changed_by_the_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ucf.generation

    request_path = tmp_path / "request.json"
    request_path.write_bytes(canonical_generation_json(generation_request()))
    (tmp_path / "legacy_inventory.py").write_text(
        """\
def reserve_item(*, item_id: str) -> str:
    return "reservation-456"
""",
        encoding="utf-8",
    )
    destination = tmp_path / "generated"
    first = runner.invoke(app, _arguments(request_path, destination))
    assert first.exit_code == 0, first.output
    before = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }

    original_generate = ucf.generation.generate_with_adapter

    async def change_request_after_generation(**arguments):
        result = await original_generate(**arguments)
        request_path.write_bytes(request_path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(
        ucf.generation,
        "generate_with_adapter",
        change_request_after_generation,
    )

    repeated = runner.invoke(app, _arguments(request_path, destination))

    assert repeated.exit_code == 3
    assert "changed before publication" in repeated.output
    assert {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    } == before
