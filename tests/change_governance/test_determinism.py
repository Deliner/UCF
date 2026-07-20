from __future__ import annotations

import os
import subprocess
import sys

from tests.change_governance._fixture_factory import (
    governance_fixtures,
    render_wire_fixtures,
)
from ucf.change_governance import canonical_change_governance_json

_SUBPROCESS = """
import hashlib
from tests.change_governance._fixture_factory import render_wire_fixtures
for path, content in sorted(
    render_wire_fixtures().items(),
    key=lambda item: item[0].as_posix(),
):
    print(path.name, hashlib.sha256(content.encode("utf-8")).hexdigest())
"""


def test_all_governance_resources_are_byte_repeatable() -> None:
    fixtures = governance_fixtures()
    documents = (
        fixtures.compatible.impact,
        fixtures.compatible.assessment,
        fixtures.compatible.gate,
        fixtures.breaking_required.impact,
        fixtures.breaking_required.assessment,
        fixtures.breaking_required.gate,
        fixtures.breaking_approved.declaration,
        fixtures.breaking_approved.gate,
        fixtures.breaking_rejected.declaration,
        fixtures.breaking_rejected.gate,
    )

    for document in documents:
        assert document is not None
        assert canonical_change_governance_json(
            document
        ) == canonical_change_governance_json(document)

    assert render_wire_fixtures() == render_wire_fixtures()


def test_fixture_and_graph_output_ignore_python_hash_seed() -> None:
    outputs = []
    for seed in ("1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS],
            cwd=os.getcwd(),
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    assert outputs[0] == outputs[1]
