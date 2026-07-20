from __future__ import annotations

import asyncio
import hashlib
import subprocess
import sys
from pathlib import Path

from ucf.generation import (
    PublicationStatus,
    generate_with_adapter,
    publish_generation_result,
)

from ._support import generation_request

REPOSITORY_ROOT = Path(__file__).parents[2]
ADAPTER = REPOSITORY_ROOT / "adapters" / "python-pytest" / "adapter.py"


def _adapter_command() -> tuple[str, ...]:
    return (
        sys.executable,
        "-I",
        "-B",
        "-X",
        "utf8",
        str(ADAPTER),
    )


def _user_implementation(root: Path) -> Path:
    implementation = root / "legacy_inventory.py"
    implementation.write_text(
        """\
def reserve_item(*, item_id: str) -> str:
    if item_id != "sku-123":
        raise ValueError("unexpected item")
    return "reservation-456"
""",
        encoding="utf-8",
    )
    return implementation


def test_client_generates_publishes_and_executes_without_touching_user_code(
    tmp_path: Path,
) -> None:
    implementation = _user_implementation(tmp_path)
    implementation_digest = hashlib.sha256(
        implementation.read_bytes()
    ).hexdigest()
    request = generation_request()

    result = asyncio.run(
        generate_with_adapter(
            command=_adapter_command(),
            cwd=REPOSITORY_ROOT,
            request=request,
            operation_timeout=5.0,
        )
    )
    destination = tmp_path / "generated-contracts"
    assert (
        publish_generation_result(result, destination)
        is PublicationStatus.CREATED
    )

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

    repeated = asyncio.run(
        generate_with_adapter(
            command=_adapter_command(),
            cwd=REPOSITORY_ROOT,
            request=request,
            operation_timeout=5.0,
        )
    )
    assert repeated == result
    assert (
        publish_generation_result(repeated, destination)
        is PublicationStatus.UNCHANGED
    )
    assert hashlib.sha256(implementation.read_bytes()).hexdigest() == (
        implementation_digest
    )
