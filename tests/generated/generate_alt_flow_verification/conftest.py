"""Executable inputs for generate-alt-flow-verification generated tests."""

from pathlib import Path

import pytest

from ucf.models.usecase import UseCaseSpec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry


@pytest.fixture
def inputs() -> dict[str, object]:
    specs_dir = Path(__file__).resolve().parents[3] / "specs"
    loader = SpecLoader(specs_dir)
    usecase = loader.load_file(specs_dir / "use-cases/create-short-url.yaml")
    validate_url = loader.load_file(specs_dir / "actions/validate-url.yaml")
    if not isinstance(usecase, UseCaseSpec):
        raise TypeError("create-short-url fixture must be a UseCaseSpec")

    registry = SpecRegistry()
    registry.register(usecase)
    registry.register(validate_url)
    invalid_url = next(
        flow for flow in usecase.alternative_flows if flow.name == "invalid-url"
    )
    return {
        "usecase_spec": usecase,
        "alt_flow": invalid_url,
        "registry": registry,
    }
