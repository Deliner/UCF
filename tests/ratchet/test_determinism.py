from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ucf.ratchet import (
    advance_ratchet_baseline,
    canonical_ratchet_json,
    evaluate_ratchet,
)

from .test_evaluation import _accepted, _current

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _canonical_flow() -> bytes:
    policy, bundle, baseline = _accepted()
    current = _current(policy, bundle)
    report = evaluate_ratchet(
        policy,
        baseline,
        bundle,
        current,
    )
    successor = advance_ratchet_baseline(
        policy,
        baseline,
        bundle,
        current,
        report,
    )
    return b"".join(
        canonical_ratchet_json(document)
        for document in (
            policy,
            current,
            baseline,
            report,
            successor,
        )
    )


def _fresh_process(seed: str) -> bytes:
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            "-m",
            "tests.ratchet.test_determinism",
        ),
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed},
        check=True,
        capture_output=True,
    )
    assert completed.stderr == b""
    return completed.stdout


def test_complete_ratchet_flow_is_hash_seed_deterministic() -> None:
    expected = _canonical_flow()

    assert _fresh_process("1") == expected
    assert _fresh_process("777") == expected


if __name__ == "__main__":
    sys.stdout.buffer.write(_canonical_flow())
