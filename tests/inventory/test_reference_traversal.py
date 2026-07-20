from __future__ import annotations

import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "adapters"


def test_reference_traversal_stops_at_explicit_resource_limit(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repository"
    repository.mkdir()
    for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
        (repository / name).write_text(name, encoding="utf-8")

    monkeypatch.syspath_prepend(str(ADAPTER_FIXTURE_ROOT))
    traversal = importlib.import_module("inventory_reference.traversal")
    monkeypatch.setattr(traversal, "MAX_FILESYSTEM_ENTRIES", 3)
    monkeypatch.chdir(repository)
    original_scandir = traversal.os.scandir
    enumerated = 0

    class CountingScandir:
        def __init__(self, directory) -> None:
            self._iterator = original_scandir(directory)

        def __enter__(self):
            self._iterator.__enter__()
            return self

        def __exit__(self, *arguments):
            return self._iterator.__exit__(*arguments)

        def __iter__(self):
            return self

        def __next__(self):
            nonlocal enumerated
            entry = next(self._iterator)
            enumerated += 1
            return entry

    monkeypatch.setattr(traversal.os, "scandir", CountingScandir)

    result = traversal.scan_repository(root_path=".", ignore_rules=())

    assert tuple(entry.path for entry in result.entries) == (".",)
    assert enumerated == 3
    assert [
        (
            diagnostic.code,
            diagnostic.fact_kind,
            diagnostic.path,
            diagnostic.stage,
        )
        for diagnostic in result.diagnostics
    ] == [
        (
            "org.ucf.inventory.resource-limit",
            None,
            None,
            "enumerate",
        )
    ]


def test_reference_traversal_bounds_classification_output_before_profile(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "many.py").write_text(
        "\n".join(f"def public_{index}(): pass" for index in range(20)),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(ADAPTER_FIXTURE_ROOT))
    traversal = importlib.import_module("inventory_reference.traversal")
    monkeypatch.setattr(
        traversal,
        "MAX_OUTPUT_RECORDS",
        8,
        raising=False,
    )
    monkeypatch.chdir(repository)

    result = traversal.scan_repository(root_path=".", ignore_rules=())

    assert result.classifications == ()
    assert [
        (diagnostic.code, diagnostic.fact_kind)
        for diagnostic in result.diagnostics
    ] == [("org.ucf.inventory.resource-limit", None)]
