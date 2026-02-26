"""Shared fixtures for generated UCF tests."""

from __future__ import annotations

from pathlib import Path

import pytest

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs"
EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples" / "specs"


@pytest.fixture
def specs_dir() -> Path:
    return SPECS_DIR


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES_DIR
