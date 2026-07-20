from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schema_and_wire_fixture_rendering_ignore_hash_seed() -> None:
    script = """
import hashlib
from tools.generate_change_lifecycle_schema import render_schemas
from tests.change_lifecycle._fixture_factory import render_wire_fixtures

digest = hashlib.sha256()
for rendered in (render_schemas(), render_wire_fixtures()):
    for path, content in sorted(
        rendered.items(),
        key=lambda item: item[0].as_posix(),
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\\0")
        digest.update(content.encode("utf-8"))
print(digest.hexdigest())
"""
    outputs = []
    for seed in ("1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
