from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import secrets
import stat
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from ucf.generation.codec import (
    canonical_generation_json,
    parse_generation_result_json,
)
from ucf.generation.errors import (
    GenerationPublicationError,
    GenerationPublicationErrorCode,
)
from ucf.generation.models import GenerationResult
from ucf.generation.validation import validate_generation_result_structure

GENERATION_RECEIPT_NAME = ".ucf-generation-result.json"
_RENAME_NOREPLACE = 1
_RENAME_EXCHANGE = 2
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_FILE_WRITE_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_NOFOLLOW", 0)
)


class PublicationStatus(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    UPDATED = "updated"


def publish_generation_result(
    result: GenerationResult,
    destination: Path,
    *,
    before_commit: Callable[[], None] | None = None,
) -> PublicationStatus:
    validate_generation_result_structure(result)
    if not isinstance(destination, Path):
        _fail(
            GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
            "generation destination must be a pathlib.Path",
            location="$destination",
        )
    absolute = destination.absolute()
    parent = absolute.parent
    name = absolute.name
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\0" in name
    ):
        _fail(
            GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
            "generation destination name is unsafe",
            location="$destination",
        )
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as error:
        _fail(
            GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
            "generation destination parent must be an existing directory",
            location="$destination.parent",
        )
        raise AssertionError("unreachable") from error
    if resolved_parent != parent:
        _fail(
            GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
            "generation destination parent or ancestor must not be symbolic",
            location="$destination.parent",
        )
    try:
        parent_fd = os.open(parent, _DIRECTORY_FLAGS)
    except OSError as error:
        _fail(
            GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
            "generation destination parent must be a stable real directory",
            location="$destination.parent",
        )
        raise AssertionError("unreachable") from error

    parent_identity = _inode_identity(os.fstat(parent_fd))
    stage_name: str | None = None
    stage_identity: tuple[int, int, int] | None = None
    try:
        _validate_parent_path(parent, parent_fd, parent_identity)
        _acquire_parent_lock(parent_fd)
        initial = _destination_metadata(parent_fd, name)
        prior: GenerationResult | None = None
        if initial is not None:
            _validate_destination_type(initial)
            prior = _read_existing_tree(parent_fd, name, initial)
            if prior == result:
                if before_commit is not None:
                    before_commit()
                _validate_parent_path(parent, parent_fd, parent_identity)
                current = _destination_metadata(parent_fd, name)
                if (
                    current is None
                    or _metadata_identity(current)
                    != _metadata_identity(initial)
                    or _read_existing_tree(parent_fd, name, current)
                    != result
                ):
                    _fail(
                        GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                        "generation destination changed before no-op",
                        location="$destination",
                    )
                return PublicationStatus.UNCHANGED

        stage_name, stage_identity = _create_stage(parent_fd, name)
        _write_staged_tree(
            parent_fd,
            stage_name,
            stage_identity,
            result,
        )
        if before_commit is not None:
            before_commit()
        _validate_parent_path(parent, parent_fd, parent_identity)
        _validate_staged_tree(
            parent_fd,
            stage_name,
            stage_identity,
            result,
        )

        if initial is None:
            if _destination_metadata(parent_fd, name) is not None:
                _fail(
                    GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                    "generation destination appeared before publication",
                    location="$destination",
                )
            _rename_at(
                parent_fd,
                stage_name,
                name,
                flags=_RENAME_NOREPLACE,
            )
            stage_name = None
            stage_identity = None
            try:
                os.fsync(parent_fd)
            except OSError as error:
                _fail(
                    GenerationPublicationErrorCode.COMMITTED_DURABILITY_UNKNOWN,
                    (
                        "generation destination is complete and visible but "
                        "its directory durability could not be confirmed"
                    ),
                    location="$destination",
                )
                raise AssertionError("unreachable") from error
            return PublicationStatus.CREATED

        current = _destination_metadata(parent_fd, name)
        if current is None or _metadata_identity(current) != _metadata_identity(
            initial
        ):
            _fail(
                GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                "generation destination changed before publication",
                location="$destination",
            )
        _validate_destination_type(current)
        current_prior = _read_existing_tree(parent_fd, name, current)
        if current_prior != prior:
            _fail(
                GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                "generation destination content changed before publication",
                location="$destination",
            )
        _validate_parent_path(parent, parent_fd, parent_identity)
        _validate_staged_tree(
            parent_fd,
            stage_name,
            stage_identity,
            result,
        )
        _rename_at(
            parent_fd,
            stage_name,
            name,
            flags=_RENAME_EXCHANGE,
        )
        stage_identity = _inode_identity(initial)
        try:
            os.fsync(parent_fd)
        except OSError as error:
            residue_name = stage_name
            stage_name = None
            stage_identity = None
            _fail(
                GenerationPublicationErrorCode.COMMITTED_DURABILITY_UNKNOWN,
                (
                    "generation destination is complete and visible but "
                    "its directory durability could not be confirmed; "
                    f"the complete prior tree remains at {residue_name!r}"
                ),
                location="$destination",
            )
            raise AssertionError("unreachable") from error
        try:
            _remove_tree_at(
                parent_fd,
                stage_name,
                expected_identity=stage_identity,
                sync_parent=False,
            )
        except OSError as cleanup_error:
            residue_name = stage_name
            stage_name = None
            stage_identity = None
            _fail(
                GenerationPublicationErrorCode.COMMITTED_CLEANUP_FAILED,
                (
                    "new generation destination is complete and visible; "
                    "the prior generated tree cleanup failed at "
                    f"{residue_name!r}"
                ),
                location="$destination",
            )
            raise AssertionError("unreachable") from cleanup_error
        stage_name = None
        stage_identity = None
        try:
            os.fsync(parent_fd)
        except OSError as error:
            _fail(
                GenerationPublicationErrorCode.COMMITTED_DURABILITY_UNKNOWN,
                (
                    "generation destination is complete and visible but "
                    "its directory durability could not be confirmed"
                ),
                location="$destination",
            )
            raise AssertionError("unreachable") from error
        return PublicationStatus.UPDATED
    except GenerationPublicationError:
        raise
    except OSError as error:
        _fail(
            GenerationPublicationErrorCode.PUBLISH_FAILED,
            "generation result could not be published",
            location="$destination",
        )
        raise AssertionError("unreachable") from error
    finally:
        cleanup_error: Exception | None = None
        if stage_name is not None:
            try:
                if stage_identity is None:
                    raise OSError(
                        errno.ESTALE,
                        "generation staging identity is unavailable",
                        stage_name,
                    )
                _validate_staged_tree(
                    parent_fd,
                    stage_name,
                    stage_identity,
                    result,
                )
                _remove_tree_at(
                    parent_fd,
                    stage_name,
                    expected_identity=stage_identity,
                )
            except (GenerationPublicationError, OSError) as error:
                cleanup_error = error
        os.close(parent_fd)
        if cleanup_error is not None:
            _fail(
                GenerationPublicationErrorCode.PUBLISH_FAILED,
                (
                    "generation staging cleanup failed without removing "
                    "content whose exact generated ownership could not be "
                    "verified"
                ),
                location="$destination",
            )


def _acquire_parent_lock(parent_fd: int) -> None:
    try:
        import fcntl
    except ImportError:
        _fail(
            GenerationPublicationErrorCode.UNSUPPORTED_PLATFORM,
            "safe generation publication requires POSIX advisory locks",
            location="$destination",
        )
    try:
        fcntl.flock(
            parent_fd,
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )
    except OSError as error:
        if error.errno not in {errno.EACCES, errno.EAGAIN}:
            raise
        _fail(
            GenerationPublicationErrorCode.DESTINATION_CONFLICT,
            "another generation publication owns the parent lock",
            location="$destination",
        )
        raise AssertionError("unreachable") from error


def _destination_metadata(
    parent_fd: int,
    name: str,
) -> os.stat_result | None:
    try:
        return os.stat(
            name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return None


def _validate_destination_type(metadata: os.stat_result) -> None:
    if stat.S_ISLNK(metadata.st_mode):
        _fail(
            GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
            "generation destination must not be a symbolic link",
            location="$destination",
        )
    if not stat.S_ISDIR(metadata.st_mode):
        _fail(
            GenerationPublicationErrorCode.DESTINATION_CONFLICT,
            "generation destination must be a directory",
            location="$destination",
        )


def _read_existing_tree(
    parent_fd: int,
    name: str,
    expected_root: os.stat_result,
) -> GenerationResult:
    root_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    try:
        opened = os.fstat(root_fd)
        if _metadata_identity(opened) != _metadata_identity(expected_root):
            _fail(
                GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                "generation destination changed while opening",
                location="$destination",
            )
        actual = _scan_tree(root_fd)
        if GENERATION_RECEIPT_NAME not in actual:
            _fail(
                GenerationPublicationErrorCode.INVALID_PRIOR_TREE,
                "generation destination has no exact UCF receipt",
                location="$destination",
            )
        try:
            receipt = parse_generation_result_json(
                _read_regular_file(root_fd, GENERATION_RECEIPT_NAME)
            )
        except ValueError as error:
            _fail(
                GenerationPublicationErrorCode.INVALID_PRIOR_TREE,
                "generation destination receipt is invalid",
                location=f"$destination/{GENERATION_RECEIPT_NAME}",
            )
            raise AssertionError("unreachable") from error
        expected = _receipt_tree_entries(receipt)
        if actual != expected:
            _fail(
                GenerationPublicationErrorCode.INVALID_PRIOR_TREE,
                "generation destination differs from its complete receipt",
                location="$destination",
            )
        for item in receipt.files:
            if _read_regular_file(root_fd, item.path) != item.content.encode(
                "utf-8"
            ):
                _fail(
                    GenerationPublicationErrorCode.INVALID_PRIOR_TREE,
                    "generated file differs from its receipt",
                    location=f"$destination/{item.path}",
                )
        finished = os.fstat(root_fd)
        current = _destination_metadata(parent_fd, name)
        if (
            _metadata_identity(finished) != _metadata_identity(opened)
            or current is None
            or _metadata_identity(current) != _metadata_identity(finished)
        ):
            _fail(
                GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                "generation destination changed while validating",
                location="$destination",
            )
        return receipt
    finally:
        os.close(root_fd)


def _scan_tree(root_fd: int, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    with os.scandir(root_fd) as entries:
        ordered = sorted(entries, key=lambda entry: entry.name)
    for entry in ordered:
        relative = f"{prefix}/{entry.name}" if prefix else entry.name
        metadata = entry.stat(follow_symlinks=False)
        if entry.is_symlink():
            _fail(
                GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
                "generation destination contains a symbolic link",
                location=f"$destination/{relative}",
            )
        if stat.S_ISDIR(metadata.st_mode):
            paths.add(relative)
            child_fd = os.open(
                entry.name,
                _DIRECTORY_FLAGS,
                dir_fd=root_fd,
            )
            try:
                paths.update(_scan_tree(child_fd, relative))
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(metadata.st_mode):
            _fail(
                GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
                "generation destination contains a non-regular entry",
                location=f"$destination/{relative}",
            )
        if metadata.st_nlink != 1:
            _fail(
                GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
                "generation destination file has more than one hard link",
                location=f"$destination/{relative}",
            )
        paths.add(relative)
    return paths


def _receipt_tree_entries(receipt: GenerationResult) -> set[str]:
    entries = {GENERATION_RECEIPT_NAME}
    for item in receipt.files:
        entries.add(item.path)
        segments = item.path.split("/")
        entries.update(
            "/".join(segments[:position])
            for position in range(1, len(segments))
        )
    return entries


def _read_regular_file(root_fd: int, relative: str) -> bytes:
    segments = relative.split("/")
    current_fd = os.dup(root_fd)
    try:
        for segment in segments[:-1]:
            next_fd = os.open(
                segment,
                _DIRECTORY_FLAGS,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(
            segments[-1],
            _FILE_READ_FLAGS,
            dir_fd=current_fd,
        )
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                _fail(
                    GenerationPublicationErrorCode.UNSAFE_FILESYSTEM,
                    "generation destination file is not a single-link regular file",
                    location=f"$destination/{relative}",
                )
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                chunks.append(chunk)
            finished = os.fstat(descriptor)
            current = os.stat(
                segments[-1],
                dir_fd=current_fd,
                follow_symlinks=False,
            )
            if (
                _metadata_identity(finished) != _metadata_identity(opened)
                or _metadata_identity(current) != _metadata_identity(finished)
            ):
                _fail(
                    GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                    "generation destination file changed while reading",
                    location=f"$destination/{relative}",
                )
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    finally:
        os.close(current_fd)


def _create_stage(
    parent_fd: int,
    destination_name: str,
) -> tuple[str, tuple[int, int, int]]:
    prefix = hashlib.sha256(
        destination_name.encode("utf-8")
    ).hexdigest()[:12]
    for _ in range(64):
        name = f".ucf-generation-{prefix}.stage-{secrets.token_hex(8)}"
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            metadata = os.stat(
                name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            return name, _inode_identity(metadata)
        except FileExistsError:
            continue
    _fail(
        GenerationPublicationErrorCode.PUBLISH_FAILED,
        "generation staging directory could not be allocated",
        location="$destination",
    )
    raise AssertionError("unreachable")


def _write_staged_tree(
    parent_fd: int,
    stage_name: str,
    stage_identity: tuple[int, int, int],
    result: GenerationResult,
) -> None:
    stage_fd = os.open(stage_name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    try:
        if _inode_identity(os.fstat(stage_fd)) != stage_identity:
            raise OSError(
                errno.ESTALE,
                "generation staging directory identity changed",
                stage_name,
            )
        for item in result.files:
            _write_relative_file(
                stage_fd,
                item.path,
                item.content.encode("utf-8"),
            )
        _write_relative_file(
            stage_fd,
            GENERATION_RECEIPT_NAME,
            canonical_generation_json(result),
        )
        os.fsync(stage_fd)
    finally:
        os.close(stage_fd)


def _write_relative_file(
    root_fd: int,
    relative: str,
    content: bytes,
) -> None:
    segments = relative.split("/")
    current_fd = os.dup(root_fd)
    try:
        for segment in segments[:-1]:
            try:
                os.mkdir(segment, 0o755, dir_fd=current_fd)
                os.fsync(current_fd)
            except FileExistsError:
                pass
            next_fd = os.open(
                segment,
                _DIRECTORY_FLAGS,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(
            segments[-1],
            _FILE_WRITE_FLAGS,
            0o644,
            dir_fd=current_fd,
        )
        try:
            view = memoryview(content)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(current_fd)
    finally:
        os.close(current_fd)


def _rename_at(
    parent_fd: int,
    source: str,
    destination: str,
    *,
    flags: int,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    rename_at = getattr(library, "renameat2", None)
    if rename_at is None:
        _fail(
            GenerationPublicationErrorCode.UNSUPPORTED_PLATFORM,
            "safe generation publication requires renameat2",
            location="$destination",
        )
    rename_at.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename_at.restype = ctypes.c_int
    result = rename_at(
        parent_fd,
        os.fsencode(source),
        parent_fd,
        os.fsencode(destination),
        flags,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {
            errno.ENOSYS,
            errno.EOPNOTSUPP,
            getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
            errno.EINVAL,
        }:
            _fail(
                GenerationPublicationErrorCode.UNSUPPORTED_PLATFORM,
                "safe generation publication requires renameat2 support",
                location="$destination",
            )
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            _fail(
                GenerationPublicationErrorCode.DESTINATION_CONFLICT,
                "generation destination appeared or changed before publication",
                location="$destination",
            )
        raise OSError(
            error_number,
            os.strerror(error_number),
            destination,
        )


def _validate_parent_path(
    parent: Path,
    parent_fd: int,
    expected_identity: tuple[int, int, int],
) -> None:
    try:
        path_metadata = os.stat(parent, follow_symlinks=False)
        opened_metadata = os.fstat(parent_fd)
    except OSError:
        _fail(
            GenerationPublicationErrorCode.DESTINATION_CONFLICT,
            "generation destination parent changed before publication",
            location="$destination.parent",
        )
    if (
        not stat.S_ISDIR(path_metadata.st_mode)
        or _inode_identity(path_metadata) != expected_identity
        or _inode_identity(opened_metadata) != expected_identity
    ):
        _fail(
            GenerationPublicationErrorCode.DESTINATION_CONFLICT,
            "generation destination parent changed before publication",
            location="$destination.parent",
        )


def _validate_staged_tree(
    parent_fd: int,
    name: str,
    expected_identity: tuple[int, int, int],
    expected_result: GenerationResult,
) -> None:
    try:
        metadata = _require_directory_identity(
            parent_fd,
            name,
            expected_identity,
        )
        actual_result = _read_existing_tree(
            parent_fd,
            name,
            metadata,
        )
    except (GenerationPublicationError, OSError):
        _fail(
            GenerationPublicationErrorCode.DESTINATION_CONFLICT,
            "generation staging tree changed before publication",
            location="$destination",
        )
    if actual_result != expected_result:
        _fail(
            GenerationPublicationErrorCode.DESTINATION_CONFLICT,
            "generation staging receipt changed before publication",
            location="$destination",
        )


def _require_directory_identity(
    parent_fd: int,
    name: str,
    expected_identity: tuple[int, int, int],
) -> os.stat_result:
    metadata = os.stat(
        name,
        dir_fd=parent_fd,
        follow_symlinks=False,
    )
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or _inode_identity(metadata) != expected_identity
    ):
        raise OSError(
            errno.ESTALE,
            "directory identity changed",
            name,
        )
    return metadata


def _remove_tree_at(
    parent_fd: int,
    name: str,
    *,
    expected_identity: tuple[int, int, int] | None = None,
    sync_parent: bool = True,
) -> None:
    try:
        directory_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        if expected_identity is not None:
            raise OSError(
                errno.ESTALE,
                "directory disappeared before cleanup",
                name,
            )
        return
    try:
        opened = os.fstat(directory_fd)
        if (
            expected_identity is not None
            and _inode_identity(opened) != expected_identity
        ):
            raise OSError(
                errno.ESTALE,
                "directory identity changed before cleanup",
                name,
            )
        _clear_directory(directory_fd)
    finally:
        os.close(directory_fd)
    current = os.stat(
        name,
        dir_fd=parent_fd,
        follow_symlinks=False,
    )
    if _inode_identity(current) != _inode_identity(opened):
        raise OSError(
            errno.ESTALE,
            "directory identity changed during cleanup",
            name,
        )
    os.rmdir(name, dir_fd=parent_fd)
    if sync_parent:
        os.fsync(parent_fd)


def _clear_directory(directory_fd: int) -> None:
    with os.scandir(directory_fd) as entries:
        ordered = sorted(entries, key=lambda entry: entry.name)
    for entry in ordered:
        metadata = entry.stat(follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode) and not entry.is_symlink():
            child_fd = os.open(
                entry.name,
                _DIRECTORY_FLAGS,
                dir_fd=directory_fd,
            )
            try:
                _clear_directory(child_fd)
            finally:
                os.close(child_fd)
            os.rmdir(entry.name, dir_fd=directory_fd)
        else:
            os.unlink(entry.name, dir_fd=directory_fd)
    os.fsync(directory_fd)


def _metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _inode_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
    )


def _fail(
    code: GenerationPublicationErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise GenerationPublicationError(code, message, location=location)
