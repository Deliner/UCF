from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ChangeProposal,
    canonical_change_lifecycle_json,
    export_openspec_change,
    import_openspec_change,
)

from ._fixture_factory import behavior_pair

ROOT = Path(__file__).resolve().parents[2]
OPENSPEC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "change_lifecycle" / "v1" / "openspec-spec-driven-1"
)
CHANGE_ID = "require-quote-order-total"


def _fixture_proposal(tmp_path: Path) -> ChangeProposal:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(source / "changes" / CHANGE_ID, base)
    return proposal


def test_openspec_export_maps_staged_directory_creation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ucf.change_lifecycle import openspec as openspec_module

    proposal = _fixture_proposal(tmp_path)
    destination = tmp_path / "exported"
    native_mkdir = Path.mkdir

    def fail_staged_directory(
        path: Path,
        *args: object,
        **kwargs: object,
    ) -> None:
        if any(
            part.startswith(f".{destination.name}.ucf-stage-") for part in path.parts
        ):
            raise OSError("injected staged directory failure")
        native_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(openspec_module.Path, "mkdir", fail_staged_directory)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(proposal, destination)

    assert captured.value.code is ChangeLifecycleErrorCode.PUBLISH_FAILED
    assert not destination.exists()
    assert not tuple(tmp_path.glob(f".{destination.name}.ucf-stage-*"))


def test_openspec_export_cleanup_failure_preserves_primary_publish_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ucf.change_lifecycle import openspec as openspec_module

    proposal = _fixture_proposal(tmp_path)
    destination = tmp_path / "exported"
    native_rmtree = shutil.rmtree

    def fail_publish(
        source: str | bytes | os.PathLike[str],
        target: str | bytes | os.PathLike[str],
    ) -> None:
        assert Path(target) == destination
        raise OSError("injected primary publish failure")

    def fail_stage_cleanup(
        path: str | bytes | os.PathLike[str],
        *args: object,
        **kwargs: object,
    ) -> None:
        if Path(path).name.startswith(f".{destination.name}.ucf-stage-"):
            raise OSError("injected stage cleanup failure")
        native_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(openspec_module.os, "replace", fail_publish)
    monkeypatch.setattr(openspec_module.shutil, "rmtree", fail_stage_cleanup)

    try:
        with pytest.raises(ChangeLifecycleValidationError) as captured:
            export_openspec_change(proposal, destination)
    finally:
        for stage in tmp_path.glob(f".{destination.name}.ucf-stage-*"):
            native_rmtree(stage)

    assert captured.value.code is ChangeLifecycleErrorCode.PUBLISH_FAILED
    assert "injected primary publish failure" in str(captured.value)
    assert any(
        "injected stage cleanup failure" in note
        for note in getattr(captured.value, "__notes__", ())
    )
    assert not destination.exists()


def test_openspec_import_deep_empty_tree_preserves_typed_profile_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    change = source / "changes" / CHANGE_ID
    current = change
    directories: list[Path] = []
    for _ in range(1_100):
        current /= "d"
        current.mkdir()
        directories.append(current)
    base, _ = behavior_pair()

    try:
        with pytest.raises(ChangeLifecycleValidationError) as captured:
            import_openspec_change(change, base)
    finally:
        for directory in reversed(directories):
            directory.rmdir()

    assert captured.value.code is ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE


def test_openspec_import_export_round_trip_preserves_128_part_artifact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    change = source / "changes" / CHANGE_ID
    current = change
    relative_parts = ("d",) * 127 + ("artifact.bin",)
    for component in relative_parts[:-1]:
        current /= component
        current.mkdir()
    artifact = current / relative_parts[-1]
    artifact.write_bytes(b"opaque")
    base, _ = behavior_pair()
    proposal = import_openspec_change(change, base)
    expected_path = f"changes/{CHANGE_ID}/{'/'.join(relative_parts)}"
    destination = tmp_path / "exported"

    export_openspec_change(proposal, destination)
    reimported = import_openspec_change(
        destination / "changes" / CHANGE_ID,
        base,
    )

    exported_artifact = destination / expected_path
    assert exported_artifact.read_bytes() == b"opaque"
    assert canonical_change_lifecycle_json(reimported) == (
        canonical_change_lifecycle_json(proposal)
    )
