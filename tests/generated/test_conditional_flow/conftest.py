"""Test fixtures for test-conditional-flow use case."""

import pytest


@pytest.fixture(autouse=True)
def _inject_inputs():
    """Inject inputs into test module so generated orchestrator can use inputs.get()."""
    from . import test_orchestrator
    test_orchestrator.inputs = {"threshold": 11}
