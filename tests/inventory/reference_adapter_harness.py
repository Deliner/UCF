from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

type ManifestEntry = tuple[
    bytes,
    str,
    int,
    int,
    int,
    bytes | None,
    str | None,
]


def nonfollowing_tree_manifest(root: Path) -> tuple[ManifestEntry, ...]:
    """Measure a tree without traversing links or changing its contents."""

    if not root.is_dir():
        raise ValueError("manifest root must be a directory")
    records: list[ManifestEntry] = []

    def visit(path: Path, relative: bytes) -> None:
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        kind = _entry_kind(metadata.st_mode)
        target = (
            os.fsencode(os.readlink(path))
            if kind == "symlink"
            else None
        )
        digest = _file_digest(path) if kind == "file" else None
        records.append(
            (
                relative,
                kind,
                mode,
                metadata.st_size,
                metadata.st_mtime_ns,
                target,
                digest,
            )
        )
        if kind != "directory":
            return
        with os.scandir(path) as iterator:
            children = sorted(
                iterator,
                key=lambda entry: os.fsencode(entry.name),
            )
        for child in children:
            child_name = os.fsencode(child.name)
            child_relative = (
                child_name
                if relative == b"."
                else relative + b"/" + child_name
            )
            visit(path / child.name, child_relative)

    visit(root, b".")
    return tuple(records)


def _entry_kind(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "unknown"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()
