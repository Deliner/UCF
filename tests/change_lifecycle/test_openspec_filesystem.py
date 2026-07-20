from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from ucf.change_lifecycle import (
    OPENSPEC_INTEROP_PROFILE,
    OPENSPEC_TESTED_AGAINST_VERSION,
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    ChangeProposal,
    canonical_change_lifecycle_json,
    export_openspec_change,
    import_openspec_change,
    parse_change_proposal_json,
)
from ucf.ir import canonical_ir_json
from ucf.ir.models import BehaviorIR

from ._fixture_factory import behavior_pair

ROOT = Path(__file__).resolve().parents[2]
OPENSPEC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "change_lifecycle" / "v1" / "openspec-spec-driven-1"
)
CHANGE_ID = "require-quote-order-total"


class _BehaviorIRSubclass(BehaviorIR):
    pass


class _ChangeProposalSubclass(ChangeProposal):
    pass


def _tree_snapshot(root: Path) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (
            path.relative_to(root).as_posix(),
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _identity_snapshot(root: Path) -> tuple[tuple[object, ...], ...]:
    paths = (root, *sorted(root.rglob("*")))
    snapshot: list[tuple[object, ...]] = []
    for path in paths:
        metadata = path.lstat()
        content_digest = (
            hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file() and not path.is_symlink()
            else None
        )
        snapshot.append(
            (
                "." if path == root else path.relative_to(root).as_posix(),
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
                content_digest,
            )
        )
    return tuple(snapshot)


def _fixture_proposal(tmp_path: Path) -> tuple[Path, BehaviorIR, ChangeProposal]:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    return source, base, proposal


@pytest.mark.parametrize(
    "change_directory",
    ("not-a-path", None, 7, object()),
)
def test_openspec_import_rejects_non_path_source_before_filesystem_access(
    tmp_path: Path,
    change_directory: object,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    before = _identity_snapshot(source)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(change_directory, base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.change_directory"
    assert _identity_snapshot(source) == before


@pytest.mark.parametrize(
    "invalid_kind",
    ("none", "mapping", "subclass"),
)
def test_openspec_import_rejects_nonexact_base_before_filesystem_access(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    before = _identity_snapshot(source)
    base, _ = behavior_pair()
    invalid_base: object
    if invalid_kind == "none":
        invalid_base = None
    elif invalid_kind == "mapping":
        invalid_base = base.model_dump(mode="python")
    else:
        invalid_base = _BehaviorIRSubclass.model_validate(
            base.model_dump(mode="python")
        )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(source / "changes" / CHANGE_ID, invalid_base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.base_behavior"
    assert _identity_snapshot(source) == before


@pytest.mark.parametrize("suffix", (".md", ".yaml", ".txt"))
def test_openspec_import_maps_invalid_utf8_text_artifact_without_mutation(
    tmp_path: Path,
    suffix: str,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    change = source / "changes" / CHANGE_ID
    artifact = {
        ".md": change / "proposal.md",
        ".yaml": change / ".openspec.yaml",
        ".txt": change / "notes.txt",
    }[suffix]
    artifact.write_bytes(b"\xffinvalid-utf8")
    before = _identity_snapshot(source)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(change, base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert _identity_snapshot(source) == before


@pytest.mark.parametrize(
    "destination",
    ("not-a-path", None, 7, object()),
)
def test_openspec_export_rejects_non_path_destination_before_mutation(
    tmp_path: Path,
    destination: object,
) -> None:
    _, _, proposal = _fixture_proposal(tmp_path)
    before = _identity_snapshot(tmp_path)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(proposal, destination)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.destination"
    assert _identity_snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "invalid_kind",
    ("none", "mapping", "subclass"),
)
def test_openspec_export_rejects_invalid_proposal_before_mutation(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    _, _, proposal = _fixture_proposal(tmp_path)
    invalid_proposal: object
    if invalid_kind == "none":
        invalid_proposal = None
    elif invalid_kind == "mapping":
        invalid_proposal = proposal.model_dump(mode="python")
    else:
        invalid_proposal = _ChangeProposalSubclass.model_validate(
            proposal.model_dump(mode="python")
        )
    before = _identity_snapshot(tmp_path)
    destination = tmp_path / "exported"

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(invalid_proposal, destination)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert _identity_snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "before_publish",
    (False, 0, "not-callable", object()),
)
def test_openspec_export_rejects_noncallable_hook_before_mutation(
    tmp_path: Path,
    before_publish: object,
) -> None:
    _, _, proposal = _fixture_proposal(tmp_path)
    before = _identity_snapshot(tmp_path)
    destination = tmp_path / "exported"

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(
            proposal,
            destination,
            before_publish=before_publish,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == "$.before_publish"
    assert _identity_snapshot(tmp_path) == before


def test_openspec_export_maps_stage_creation_failure_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ucf.change_lifecycle import openspec as openspec_module

    _, _, proposal = _fixture_proposal(tmp_path)
    before = _identity_snapshot(tmp_path)
    destination = tmp_path / "exported"

    def fail_stage_creation(*args: object, **kwargs: object) -> str:
        raise OSError("injected staging failure")

    monkeypatch.setattr(openspec_module.tempfile, "mkdtemp", fail_stage_creation)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(proposal, destination)

    assert captured.value.code is ChangeLifecycleErrorCode.PUBLISH_FAILED
    assert _identity_snapshot(tmp_path) == before


def test_openspec_import_is_read_only_repeatable_and_exact(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    shutil.copytree(OPENSPEC_FIXTURE, first_root)
    shutil.copytree(OPENSPEC_FIXTURE, second_root)
    first_before = _tree_snapshot(first_root)
    second_before = _tree_snapshot(second_root)
    base, _ = behavior_pair()

    first = import_openspec_change(
        first_root / "changes" / CHANGE_ID,
        base,
    )
    second = import_openspec_change(
        second_root / "changes" / CHANGE_ID,
        base,
    )

    assert canonical_change_lifecycle_json(first) == (
        canonical_change_lifecycle_json(second)
    )
    assert first.openspec.profile == OPENSPEC_INTEROP_PROFILE
    assert first.openspec.tested_against_version == (OPENSPEC_TESTED_AGAINST_VERSION)
    assert tuple(artifact.path for artifact in first.openspec.artifacts) == (
        "changes/require-quote-order-total/.openspec.yaml",
        "changes/require-quote-order-total/design.md",
        "changes/require-quote-order-total/notes.txt",
        "changes/require-quote-order-total/proposal.md",
        "changes/require-quote-order-total/specs/quote-order/spec.md",
        "changes/require-quote-order-total/tasks.md",
        "config.yaml",
        "specs/quote-order/spec.md",
    )
    assert (
        first.base_behavior.canonical_digest.value
        == hashlib.sha256(canonical_ir_json(base).encode("utf-8")).hexdigest()
    )
    assert _tree_snapshot(first_root) == first_before
    assert _tree_snapshot(second_root) == second_before


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            "custom-profile",
            ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE,
        ),
        ("duplicate-schema", ChangeLifecycleErrorCode.INVALID_STRUCTURE),
        ("leaf-symlink", ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM),
        ("root-symlink", ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM),
        ("hard-link", ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM),
        ("oversize", ChangeLifecycleErrorCode.INVALID_STRUCTURE),
        (
            "nested-delta",
            ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE,
        ),
    ],
)
def test_openspec_import_rejects_lossy_or_unsafe_input_without_mutation(
    tmp_path: Path,
    mutation: str,
    expected_code: ChangeLifecycleErrorCode,
) -> None:
    root = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    change = root / "changes" / CHANGE_ID
    import_path = change
    if mutation == "custom-profile":
        (change / ".openspec.yaml").write_text(
            "schema: custom-workflow\n",
            encoding="utf-8",
        )
    elif mutation == "duplicate-schema":
        (change / ".openspec.yaml").write_text(
            "schema: spec-driven\nschema: custom-workflow\n",
            encoding="utf-8",
        )
    elif mutation == "leaf-symlink":
        note = change / "notes.txt"
        note.unlink()
        note.symlink_to("proposal.md")
    elif mutation == "root-symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        import_path = alias / "changes" / CHANGE_ID
    elif mutation == "hard-link":
        note = change / "notes.txt"
        note.unlink()
        os.link(change / "proposal.md", note)
    elif mutation == "oversize":
        (change / "notes.txt").write_bytes(b"x" * 262_145)
    else:
        source = change / "specs" / "quote-order" / "spec.md"
        target = change / "specs" / "nested" / "quote-order" / "spec.md"
        target.parent.mkdir(parents=True)
        source.rename(target)
        source.parent.rmdir()
    before = _tree_snapshot(root)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(import_path, base)

    assert captured.value.code is expected_code
    assert _tree_snapshot(root) == before


def test_openspec_import_preserves_opaque_binary_artifact(tmp_path: Path) -> None:
    root = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    change = root / "changes" / CHANGE_ID
    opaque = b"\x00\xffopaque\n"
    (change / "fixture.bin").write_bytes(opaque)
    base, _ = behavior_pair()

    proposal = import_openspec_change(change, base)

    artifact = next(
        item
        for item in proposal.openspec.artifacts
        if item.path.endswith("/fixture.bin")
    )
    assert artifact.media_type == "application/octet-stream"
    assert artifact.byte_digest.value == hashlib.sha256(opaque).hexdigest()


@pytest.mark.parametrize(
    "overridden_config",
    (
        b"schema: custom-workflow\n",
        b"schema: spec-driven\nschema: custom-workflow\n",
    ),
)
def test_change_metadata_overrides_and_preserves_project_config(
    tmp_path: Path,
    overridden_config: bytes,
) -> None:
    root = tmp_path / "openspec"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    (root / "config.yaml").write_bytes(overridden_config)
    base, _ = behavior_pair()

    proposal = import_openspec_change(
        root / "changes" / CHANGE_ID,
        base,
    )

    config = next(
        artifact
        for artifact in proposal.openspec.artifacts
        if artifact.role.value == "project_config"
    )
    assert base64.b64decode(config.content_base64) == overridden_config
    assert config.byte_digest.value == hashlib.sha256(overridden_config).hexdigest()


@pytest.mark.parametrize(
    "mutation",
    (
        "nested-delta",
        "orphan-base",
        "custom-profile",
        "missing-profile",
    ),
)
def test_openspec_wire_rejects_importer_incompatible_profile(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    base, _ = behavior_pair()
    proposal = import_openspec_change(root / "changes" / CHANGE_ID, base)
    payload = proposal.model_dump(mode="json")
    artifacts = payload["openspec"]["artifacts"]
    if mutation == "nested-delta":
        artifact = next(item for item in artifacts if item["role"] == "opaque")
        artifact["path"] = f"changes/{CHANGE_ID}/specs/nested/quote-order/spec.md"
        artifact["media_type"] = "text/markdown;charset=utf-8"
    elif mutation == "orphan-base":
        artifact = next(item for item in artifacts if item["role"] == "base_spec")
        orphan = dict(artifact)
        orphan["path"] = "specs/orphan/spec.md"
        artifacts.append(orphan)
    elif mutation == "custom-profile":
        artifact = next(item for item in artifacts if item["role"] == "change_metadata")
        content = b"schema: custom-workflow\n"
        artifact["content_base64"] = base64.b64encode(content).decode("ascii")
        artifact["byte_digest"]["value"] = hashlib.sha256(content).hexdigest()
    else:
        artifacts[:] = [
            item
            for item in artifacts
            if item["role"] not in {"change_metadata", "project_config"}
        ]
    artifacts.sort(key=lambda item: item["path"])

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_change_proposal_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_openspec_wire_rejects_file_directory_prefix_collision(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    base, _ = behavior_pair()
    proposal = import_openspec_change(root / "changes" / CHANGE_ID, base)
    payload = proposal.model_dump(mode="json")
    artifacts = payload["openspec"]["artifacts"]
    opaque = next(item for item in artifacts if item["role"] == "opaque")
    parent = dict(opaque)
    parent.update(
        {
            "path": f"changes/{CHANGE_ID}/opaque",
            "media_type": "application/octet-stream",
        }
    )
    child = dict(opaque)
    child.update(
        {
            "path": f"changes/{CHANGE_ID}/opaque/child.bin",
            "media_type": "application/octet-stream",
        }
    )
    artifacts.extend((parent, child))
    artifacts.sort(key=lambda item: item["path"])

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_change_proposal_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_openspec_wire_maps_deep_profile_yaml_to_lifecycle_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    base, _ = behavior_pair()
    proposal = import_openspec_change(root / "changes" / CHANGE_ID, base)
    payload = proposal.model_dump(mode="json")
    metadata = next(
        artifact
        for artifact in payload["openspec"]["artifacts"]
        if artifact["role"] == "change_metadata"
    )
    content = (
        b"schema: spec-driven\nnested: "
        + (b"[" * 600)
        + b"value"
        + (b"]" * 600)
        + b"\n"
    )
    metadata["content_base64"] = base64.b64encode(content).decode("ascii")
    metadata["byte_digest"]["value"] = hashlib.sha256(content).hexdigest()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        parse_change_proposal_json(json.dumps(payload))

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE


def test_openspec_import_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    real_parent = tmp_path / "real-parent"
    root = real_parent / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    alias = tmp_path / "ancestor-alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    before = _identity_snapshot(root)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(
            alias / "workspace" / "changes" / CHANGE_ID,
            base,
        )

    assert captured.value.code is ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM
    assert _identity_snapshot(root) == before


def test_openspec_import_rejects_junction_during_recursive_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    junction = root / "changes" / CHANGE_ID / "specs"
    native_isjunction = getattr(os.path, "isjunction", lambda path: False)

    def classify_junction(path: str | bytes | os.PathLike[str]) -> bool:
        return Path(path) == junction or bool(native_isjunction(path))

    monkeypatch.setattr(os.path, "isjunction", classify_junction, raising=False)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(root / "changes" / CHANGE_ID, base)

    assert captured.value.code is ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM


def test_openspec_import_revalidates_typed_base_behavior(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    base, _ = behavior_pair()
    removed_id = base.roots[0].target_id
    broken = base.model_copy(
        update={
            "entities": tuple(
                entity for entity in base.entities if entity.id != removed_id
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(root / "changes" / CHANGE_ID, broken)

    assert captured.value.code is ChangeLifecycleErrorCode.BROKEN_REFERENCE


def test_openspec_import_maps_unhashable_yaml_key_to_lifecycle_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    metadata = root / "changes" / CHANGE_ID / ".openspec.yaml"
    metadata.write_text(
        "? [unhashable, key]\n: value\nschema: spec-driven\n",
        encoding="utf-8",
    )
    before = _identity_snapshot(root)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(root / "changes" / CHANGE_ID, base)

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert _identity_snapshot(root) == before


@pytest.mark.parametrize("alias_level", ("specs", "capability"))
def test_openspec_import_rejects_symlinked_base_spec_parent(
    tmp_path: Path,
    alias_level: str,
) -> None:
    root = tmp_path / "workspace"
    shutil.copytree(OPENSPEC_FIXTURE, root)
    external = tmp_path / "external-specs"
    external.mkdir()
    if alias_level == "specs":
        source = root / "specs"
        shutil.move(source, external / "specs")
        source.symlink_to(external / "specs", target_is_directory=True)
    else:
        source = root / "specs" / "quote-order"
        shutil.move(source, external / "quote-order")
        source.symlink_to(external / "quote-order", target_is_directory=True)
    external_before = _identity_snapshot(external)
    base, _ = behavior_pair()

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        import_openspec_change(root / "changes" / CHANGE_ID, base)

    assert captured.value.code is ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM
    assert _identity_snapshot(external) == external_before


def test_openspec_export_publishes_exact_tree_to_absent_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    source_before = _tree_snapshot(source)
    destination = tmp_path / "exported"

    export_openspec_change(proposal, destination)

    assert _tree_snapshot(destination) == source_before
    assert _tree_snapshot(source) == source_before


def test_openspec_wire_export_reimports_exactly(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    imported = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    parsed = parse_change_proposal_json(canonical_change_lifecycle_json(imported))
    destination = tmp_path / "exported"

    export_openspec_change(parsed, destination)
    reimported = import_openspec_change(
        destination / "changes" / CHANGE_ID,
        base,
    )

    assert canonical_change_lifecycle_json(reimported) == (
        canonical_change_lifecycle_json(parsed)
    )


def test_openspec_export_rejects_symlinked_parent_ancestor(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    real_parent = tmp_path / "real-parent"
    export_parent = real_parent / "workspace"
    export_parent.mkdir(parents=True)
    alias = tmp_path / "ancestor-alias"
    alias.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(proposal, alias / "workspace" / "exported")

    assert captured.value.code is ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM
    assert not (export_parent / "exported").exists()


def test_openspec_export_exact_existing_tree_is_identity_noop(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    destination = tmp_path / "exported"
    export_openspec_change(proposal, destination)
    before = _identity_snapshot(destination)

    export_openspec_change(proposal, destination)

    assert _identity_snapshot(destination) == before
    assert not tuple(tmp_path.glob(f".{destination.name}.ucf-stage-*"))


def test_openspec_export_refuses_nonexact_populated_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    destination = tmp_path / "exported"
    export_openspec_change(proposal, destination)
    (destination / "sentinel.txt").write_text("owned\n", encoding="utf-8")
    before = _identity_snapshot(destination)

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(proposal, destination)

    assert captured.value.code is ChangeLifecycleErrorCode.DESTINATION_CONFLICT
    assert _identity_snapshot(destination) == before
    assert not tuple(tmp_path.glob(f".{destination.name}.ucf-stage-*"))


def test_openspec_export_rename_failure_cleans_complete_sibling_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ucf.change_lifecycle import openspec as openspec_module

    source = tmp_path / "source"
    shutil.copytree(OPENSPEC_FIXTURE, source)
    source_before = _tree_snapshot(source)
    base, _ = behavior_pair()
    proposal = import_openspec_change(
        source / "changes" / CHANGE_ID,
        base,
    )
    destination = tmp_path / "exported"
    observed_stage: list[Path] = []

    def fail_rename(stage: str | bytes | Path, target: str | bytes | Path):
        stage_path = Path(stage)
        assert Path(target) == destination
        assert stage_path.parent == destination.parent
        assert _tree_snapshot(stage_path) == source_before
        observed_stage.append(stage_path)
        raise OSError("injected rename failure")

    monkeypatch.setattr(openspec_module.os, "replace", fail_rename)
    with pytest.raises(ChangeLifecycleValidationError) as captured:
        export_openspec_change(proposal, destination)

    assert captured.value.code is ChangeLifecycleErrorCode.PUBLISH_FAILED
    assert observed_stage
    assert not destination.exists()
    assert not observed_stage[0].exists()
    assert _tree_snapshot(source) == source_before
