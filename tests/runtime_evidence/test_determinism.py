from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from ucf.ir import canonical_trust_ir_json
from ucf.runtime_evidence import (
    canonical_runtime_evidence_json,
    import_runtime_evidence,
    project_runtime_evidence_to_trust,
)

from .test_process_client import (
    RECORDING,
    ROOT,
    TIMEOUTS,
    _command,
    _forbidden_values,
    _request_for_recording,
)


def _canonical_import() -> bytes:
    request, behavior, environment = _request_for_recording()
    result = asyncio.run(
        import_runtime_evidence(
            command=_command(),
            cwd=ROOT,
            recording_path=RECORDING,
            request=request,
            behavior=behavior,
            environment=environment,
            timeouts=TIMEOUTS,
            operation_timeout=1.0,
        )
    )
    trust = project_runtime_evidence_to_trust(
        result,
        behavior=behavior,
        environment=environment,
    )
    return canonical_runtime_evidence_json(result) + (
        canonical_trust_ir_json(trust).encode("ascii")
    )


def _fresh_process(seed: str) -> bytes:
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            "-m",
            "tests.runtime_evidence.test_determinism",
        ),
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONHASHSEED": seed},
        check=True,
        capture_output=True,
    )
    assert completed.stderr == b""
    return completed.stdout


def test_runtime_import_and_projection_are_hash_seed_deterministic() -> None:
    before = RECORDING.read_bytes()
    expected = _canonical_import()

    assert _fresh_process("1") == expected
    assert _fresh_process("777") == expected
    assert RECORDING.read_bytes() == before
    assert all(
        value.encode() not in expected for value in _forbidden_values()
    )


if __name__ == "__main__":
    sys.stdout.buffer.write(_canonical_import())
