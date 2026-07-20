from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path

import pytest

from ucf.generation import (
    GENERATION_RECEIPT_NAME,
    GenerationPublicationError,
    PublicationStatus,
    canonical_generation_json,
    derive_generation_result_id,
    publish_generation_result,
)
from ucf.ir.models import Digest

from ._support import generation_result


def _changed_result(content: str):
    result = generation_result()
    encoded = content.encode("utf-8")
    changed_file = result.files[0].model_copy(
        update={
            "byte_size": len(encoded),
            "content_digest": Digest(
                kind="digest",
                algorithm="sha-256",
                value=hashlib.sha256(encoded).hexdigest(),
            ),
            "content": content,
        }
    )
    changed = result.model_copy(update={"files": (changed_file,)})
    return changed.model_copy(
        update={"id": derive_generation_result_id(changed)}
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def test_first_publication_and_exact_retry_are_complete_and_idempotent(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "generated"
    result = generation_result()

    assert (
        publish_generation_result(result, destination)
        is PublicationStatus.CREATED
    )
    assert _tree_bytes(destination) == {
        GENERATION_RECEIPT_NAME: canonical_generation_json(result),
        result.files[0].path: result.files[0].content.encode("utf-8"),
    }
    before = _tree_bytes(destination)

    assert (
        publish_generation_result(result, destination)
        is PublicationStatus.UNCHANGED
    )
    assert _tree_bytes(destination) == before


def test_regeneration_replaces_only_an_exact_prior_generated_tree(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "generated"
    user_source = tmp_path / "legacy_inventory.py"
    user_source.write_text("USER IMPLEMENTATION\n", encoding="utf-8")
    original_user = user_source.read_bytes()
    first = generation_result()
    second = _changed_result(
        '"""replacement generated content"""\n'
        "\n"
        "def test_replacement() -> None:\n"
        "    assert True\n"
    )
    publish_generation_result(first, destination)

    assert (
        publish_generation_result(second, destination)
        is PublicationStatus.UPDATED
    )
    assert _tree_bytes(destination) == {
        GENERATION_RECEIPT_NAME: canonical_generation_json(second),
        second.files[0].path: second.files[0].content.encode("utf-8"),
    }
    assert user_source.read_bytes() == original_user


@pytest.mark.parametrize("mutation", ["extra", "edited", "missing"])
def test_regeneration_rejects_a_dirty_or_incomplete_prior_tree(
    tmp_path: Path,
    mutation: str,
) -> None:
    destination = tmp_path / "generated"
    first = generation_result()
    second = _changed_result(
        '"""replacement"""\n'
        "\n"
        "def test_replacement() -> None:\n"
        "    assert True\n"
    )
    publish_generation_result(first, destination)
    generated = destination / first.files[0].path
    if mutation == "extra":
        (destination / "USER.txt").write_text("do not replace\n")
    elif mutation == "edited":
        generated.write_text("user edit\n")
    else:
        generated.unlink()
    before = {
        path.relative_to(tmp_path).as_posix(): (
            b"<symlink>" if path.is_symlink() else path.read_bytes()
        )
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file() or path.is_symlink()
    }

    with pytest.raises(GenerationPublicationError):
        publish_generation_result(second, destination)

    after = {
        path.relative_to(tmp_path).as_posix(): (
            b"<symlink>" if path.is_symlink() else path.read_bytes()
        )
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file() or path.is_symlink()
    }
    assert after == before


@pytest.mark.parametrize("retry_kind", ["unchanged", "updated"])
@pytest.mark.parametrize(
    "extra_directory",
    ["USER-DIRECTORY", "nested/empty"],
)
def test_publication_rejects_unmanifested_empty_directories(
    tmp_path: Path,
    retry_kind: str,
    extra_directory: str,
) -> None:
    destination = tmp_path / "generated"
    first = generation_result()
    publish_generation_result(first, destination)
    unmanifested = destination / extra_directory
    unmanifested.mkdir(parents=True)
    before = _tree_bytes(destination)
    candidate = (
        first
        if retry_kind == "unchanged"
        else _changed_result("replacement\n")
    )

    with pytest.raises(
        GenerationPublicationError,
        match="invalid_prior_tree",
    ):
        publish_generation_result(candidate, destination)

    assert _tree_bytes(destination) == before
    assert unmanifested.is_dir()
    assert not tuple(unmanifested.iterdir())


def test_publication_rejects_destination_and_file_aliases(
    tmp_path: Path,
) -> None:
    result = generation_result()
    outside = tmp_path / "outside"
    outside.mkdir()
    destination = tmp_path / "generated"
    destination.symlink_to(outside, target_is_directory=True)

    with pytest.raises(GenerationPublicationError, match="symbolic"):
        publish_generation_result(result, destination)
    assert list(outside.iterdir()) == []

    destination.unlink()
    publish_generation_result(result, destination)
    generated = destination / result.files[0].path
    outside_file = tmp_path / "outside-user.py"
    outside_file.write_bytes(generated.read_bytes())
    generated.unlink()
    generated.hardlink_to(outside_file)
    before = outside_file.read_bytes()

    with pytest.raises(GenerationPublicationError, match="hard link"):
        publish_generation_result(_changed_result("changed\n"), destination)
    assert outside_file.read_bytes() == before


def test_first_publication_rejects_a_destination_appearing_before_commit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "generated"
    sentinel = b"user destination\n"

    def appear() -> None:
        destination.mkdir()
        (destination / "USER.txt").write_bytes(sentinel)

    with pytest.raises(GenerationPublicationError, match="appeared"):
        publish_generation_result(
            generation_result(),
            destination,
            before_commit=appear,
        )

    assert _tree_bytes(destination) == {"USER.txt": sentinel}
    assert not any(".stage-" in path.name for path in tmp_path.iterdir())


def test_failed_regeneration_preserves_the_exact_prior_tree(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "generated"
    publish_generation_result(generation_result(), destination)
    before = _tree_bytes(destination)

    def fail() -> None:
        raise RuntimeError("deterministic pre-commit failure")

    with pytest.raises(RuntimeError, match="pre-commit"):
        publish_generation_result(
            _changed_result("replacement\n"),
            destination,
            before_commit=fail,
        )

    assert _tree_bytes(destination) == before
    assert not any(".stage-" in path.name for path in tmp_path.iterdir())


def test_publication_rejects_a_symbolic_parent(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(GenerationPublicationError, match="parent"):
        publish_generation_result(
            generation_result(),
            alias_parent / "generated",
        )
    assert list(real_parent.iterdir()) == []


def test_publication_uses_a_recoverable_kernel_owned_parent_lock(
    tmp_path: Path,
) -> None:
    import fcntl

    parent_fd = os.open(tmp_path, os.O_RDONLY)
    fcntl.flock(parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(GenerationPublicationError, match="another"):
            publish_generation_result(
                generation_result(),
                tmp_path / "generated",
            )
    finally:
        os.close(parent_fd)

    assert (
        publish_generation_result(
            generation_result(),
            tmp_path / "generated",
        )
        is PublicationStatus.CREATED
    )
    assert not tuple(tmp_path.glob(".ucf-generation-*.lock"))


def test_staging_cleanup_failure_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ucf.generation.publication as publication

    def fail_cleanup(
        *_arguments: object,
        **_keywords: object,
    ) -> None:
        raise OSError("injected cleanup failure")

    def stop_before_commit() -> None:
        raise ValueError("stop before commit")

    monkeypatch.setattr(publication, "_remove_tree_at", fail_cleanup)

    with pytest.raises(
        GenerationPublicationError,
        match="staging cleanup failed",
    ):
        publish_generation_result(
            generation_result(),
            tmp_path / "generated",
            before_commit=stop_before_commit,
        )


@pytest.mark.parametrize("abort_callback", [False, True])
def test_stage_name_substitution_never_publishes_or_deletes_user_content(
    tmp_path: Path,
    abort_callback: bool,
) -> None:
    destination = tmp_path / "generated"
    moved_stage = tmp_path / "moved-generated-stage"
    user_sentinel = b"user-owned replacement\n"

    def substitute_stage() -> None:
        [stage] = tuple(tmp_path.glob(".ucf-generation-*.stage-*"))
        stage.rename(moved_stage)
        stage.mkdir()
        (stage / "USER.txt").write_bytes(user_sentinel)
        if abort_callback:
            raise RuntimeError("stop after stage substitution")

    with pytest.raises(GenerationPublicationError):
        publish_generation_result(
            generation_result(),
            destination,
            before_commit=substitute_stage,
        )

    assert not destination.exists()
    [substitute] = tuple(tmp_path.glob(".ucf-generation-*.stage-*"))
    assert (substitute / "USER.txt").read_bytes() == user_sentinel
    assert moved_stage.is_dir()
    assert (moved_stage / GENERATION_RECEIPT_NAME).is_file()


@pytest.mark.parametrize("publication_kind", ["created", "updated"])
@pytest.mark.parametrize("mutation", ["edited", "extra"])
def test_stage_content_mutation_never_commits_or_gets_cleaned_as_owned(
    tmp_path: Path,
    publication_kind: str,
    mutation: str,
) -> None:
    destination = tmp_path / "generated"
    candidate = generation_result()
    before: dict[str, bytes] | None = None
    if publication_kind == "updated":
        publish_generation_result(candidate, destination)
        before = _tree_bytes(destination)
        candidate = _changed_result("replacement\n")

    def mutate_stage() -> None:
        [stage] = tuple(tmp_path.glob(".ucf-generation-*.stage-*"))
        if mutation == "edited":
            (stage / candidate.files[0].path).write_bytes(
                b"callback replacement\n"
            )
        else:
            (stage / "USER.txt").write_bytes(b"callback extra entry\n")

    with pytest.raises(GenerationPublicationError):
        publish_generation_result(
            candidate,
            destination,
            before_commit=mutate_stage,
        )

    if before is None:
        assert not destination.exists()
    else:
        assert _tree_bytes(destination) == before
    [retained_stage] = tuple(
        tmp_path.glob(".ucf-generation-*.stage-*")
    )
    if mutation == "edited":
        assert (
            retained_stage / candidate.files[0].path
        ).read_bytes() == b"callback replacement\n"
    else:
        assert (retained_stage / "USER.txt").read_bytes() == (
            b"callback extra entry\n"
        )


def test_abort_cleanup_preserves_unrecognized_content_inside_stage(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "generated"
    user_tree = tmp_path / "user-tree"
    user_tree.mkdir()
    sentinel = user_tree / "USER.txt"
    sentinel.write_bytes(b"user-owned moved content\n")

    def replace_stage_contents_and_abort() -> None:
        [stage] = tuple(tmp_path.glob(".ucf-generation-*.stage-*"))
        for entry in sorted(stage.rglob("*"), reverse=True):
            if entry.is_dir():
                entry.rmdir()
            else:
                entry.unlink()
        sentinel.rename(stage / "USER.txt")
        user_tree.rmdir()
        raise RuntimeError("abort with unrecognized stage contents")

    with pytest.raises(
        GenerationPublicationError,
        match="staging cleanup failed",
    ):
        publish_generation_result(
            generation_result(),
            destination,
            before_commit=replace_stage_contents_and_abort,
        )

    assert not destination.exists()
    [retained_stage] = tuple(
        tmp_path.glob(".ucf-generation-*.stage-*")
    )
    assert (retained_stage / "USER.txt").read_bytes() == (
        b"user-owned moved content\n"
    )


def test_parent_path_substitution_never_publishes_under_the_moved_parent(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    moved_parent = tmp_path / "moved-parent"
    parent.mkdir()
    destination = parent / "generated"

    def substitute_parent() -> None:
        parent.rename(moved_parent)
        parent.mkdir()

    with pytest.raises(GenerationPublicationError, match="parent"):
        publish_generation_result(
            generation_result(),
            destination,
            before_commit=substitute_parent,
        )

    assert not destination.exists()
    assert not (moved_parent / "generated").exists()
    assert list(parent.iterdir()) == []


def test_exact_noop_still_runs_source_revalidation(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "generated"
    result = generation_result()
    publish_generation_result(result, destination)
    before = _tree_bytes(destination)

    def reject_stale_source() -> None:
        raise ValueError("source changed before no-op")

    with pytest.raises(ValueError, match="source changed"):
        publish_generation_result(
            result,
            destination,
            before_commit=reject_stale_source,
        )

    assert _tree_bytes(destination) == before


def test_partial_old_tree_cleanup_failure_never_rolls_damage_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ucf.generation.publication as publication

    destination = tmp_path / "generated"
    first = generation_result()
    second = _changed_result("replacement\n")
    publish_generation_result(first, destination)
    original_fsync = publication.os.fsync
    fsync_after_callback = 0
    fsync_count_at_cleanup = -1
    callback_returned = False

    def track_fsync(descriptor: int) -> None:
        nonlocal fsync_after_callback
        if callback_returned:
            fsync_after_callback += 1
        original_fsync(descriptor)

    def arm_tracking() -> None:
        nonlocal callback_returned
        callback_returned = True

    def delete_then_fail(
        parent_fd: int,
        name: str,
        *_arguments: object,
        **_keywords: object,
    ) -> None:
        nonlocal fsync_count_at_cleanup
        fsync_count_at_cleanup = fsync_after_callback
        directory_fd = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            dir_fd=parent_fd,
        )
        try:
            os.unlink(GENERATION_RECEIPT_NAME, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
        raise OSError("injected partial cleanup failure")

    monkeypatch.setattr(publication, "_remove_tree_at", delete_then_fail)
    monkeypatch.setattr(publication.os, "fsync", track_fsync)

    with pytest.raises(
        GenerationPublicationError,
        match="committed_cleanup_failed",
    ):
        publish_generation_result(
            second,
            destination,
            before_commit=arm_tracking,
        )

    assert _tree_bytes(destination) == {
        GENERATION_RECEIPT_NAME: canonical_generation_json(second),
        second.files[0].path: second.files[0].content.encode("utf-8"),
    }
    assert fsync_count_at_cleanup >= 1
    residues = tuple(tmp_path.glob(".ucf-generation-*.stage-*"))
    assert len(residues) == 1


def test_post_commit_fsync_failure_reports_complete_visible_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ucf.generation.publication as publication

    destination = tmp_path / "generated"
    result = generation_result()

    def arm_fsync_failure() -> None:
        def fail_fsync(_descriptor: int) -> None:
            raise OSError("injected post-commit fsync failure")

        monkeypatch.setattr(publication.os, "fsync", fail_fsync)

    with pytest.raises(
        GenerationPublicationError,
        match="committed_durability_unknown",
    ):
        publish_generation_result(
            result,
            destination,
            before_commit=arm_fsync_failure,
        )

    assert _tree_bytes(destination) == {
        GENERATION_RECEIPT_NAME: canonical_generation_json(result),
        result.files[0].path: result.files[0].content.encode("utf-8"),
    }


def test_update_flush_failure_retains_the_complete_prior_tree_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ucf.generation.publication as publication

    destination = tmp_path / "generated"
    first = generation_result()
    second = _changed_result("replacement\n")
    publish_generation_result(first, destination)

    def arm_fsync_failure() -> None:
        def fail_fsync(_descriptor: int) -> None:
            raise OSError("injected exchange fsync failure")

        monkeypatch.setattr(publication.os, "fsync", fail_fsync)

    with pytest.raises(
        GenerationPublicationError,
        match="committed_durability_unknown",
    ):
        publish_generation_result(
            second,
            destination,
            before_commit=arm_fsync_failure,
        )

    assert _tree_bytes(destination) == {
        GENERATION_RECEIPT_NAME: canonical_generation_json(second),
        second.files[0].path: second.files[0].content.encode("utf-8"),
    }
    [prior_residue] = tuple(
        tmp_path.glob(".ucf-generation-*.stage-*")
    )
    assert _tree_bytes(prior_residue) == {
        GENERATION_RECEIPT_NAME: canonical_generation_json(first),
        first.files[0].path: first.files[0].content.encode("utf-8"),
    }


def test_renameat2_enosys_is_an_explicit_unsupported_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ucf.generation.publication as publication

    class UnsupportedRename:
        argtypes = None
        restype = None

        def __call__(self, *_arguments: object) -> int:
            return -1

    class Library:
        renameat2 = UnsupportedRename()

    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_a, **_k: Library())
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: errno.ENOSYS)

    with pytest.raises(GenerationPublicationError) as captured:
        publish_generation_result(
            generation_result(),
            tmp_path / "generated",
        )

    assert captured.value.code.value == "unsupported_platform"
    assert not (tmp_path / "generated").exists()
