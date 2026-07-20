from __future__ import annotations

import base64
import hashlib
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from pydantic import ValidationError as PydanticValidationError

from ucf.change_lifecycle.behavior import validate_behavior_document
from ucf.change_lifecycle.codec import (
    canonical_change_lifecycle_json,
    parse_change_proposal_json,
)
from ucf.change_lifecycle.errors import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
)
from ucf.change_lifecycle.models import (
    CHANGE_LIFECYCLE_VERSION,
    CHANGE_PROPOSAL_SCHEMA_URI,
    MAX_OPENSPEC_ARTIFACT_BYTES,
    MAX_OPENSPEC_ARTIFACTS,
    OPENSPEC_INTEROP_PROFILE,
    OPENSPEC_TESTED_AGAINST_VERSION,
    ChangeProposal,
    OpenSpecArtifact,
    OpenSpecArtifactRole,
    OpenSpecManifest,
    _artifact_media_type,
    _artifact_metadata,
)
from ucf.change_lifecycle.openspec_profile import (
    InvalidOpenSpecProfileError,
    UnsupportedOpenSpecProfileError,
    validate_spec_driven_profile,
)
from ucf.ir import canonical_ir_json
from ucf.ir.models import BehaviorIR, Digest
from ucf.ir.trust_models import BehaviorDocumentRef


def import_openspec_change(
    change_directory: Path,
    base_behavior: BehaviorIR,
) -> ChangeProposal:
    """Import one supported OpenSpec change without modifying its workspace."""
    change_directory = _require_path(
        change_directory,
        location="$.change_directory",
        label="change_directory",
    )
    if type(base_behavior) is not BehaviorIR:
        _invalid_public_input(
            "base_behavior must be an exact BehaviorIR instance",
            location="$.base_behavior",
        )
    validate_behavior_document(
        base_behavior,
        location="$.base_behavior",
    )
    change_directory = _absolute_without_symlink_resolution(change_directory)
    openspec_root = _validated_openspec_root(change_directory)
    change_id = change_directory.name
    change_prefix = PurePosixPath("changes") / change_id

    change_files = _walk_regular_files(change_directory)
    artifacts: list[OpenSpecArtifact] = []
    delta_capabilities: set[str] = set()
    for relative, content in change_files:
        logical_path = change_prefix / relative
        role, _ = _artifact_metadata(
            logical_path.as_posix(),
            change_path=change_prefix.as_posix(),
        )
        if (
            relative.parts[:1] == ("specs",)
            and relative.suffix == ".md"
            and role is not OpenSpecArtifactRole.DELTA_SPEC
        ):
            _fail(
                ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE,
                "nested or noncanonical delta-spec layout is unsupported",
            )
        if role is OpenSpecArtifactRole.DELTA_SPEC:
            parts = relative.parts
            if len(parts) != 3 or parts[2] != "spec.md":
                _fail(
                    ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE,
                    "nested or noncanonical delta-spec layout is unsupported",
                )
            delta_capabilities.add(parts[1])
        artifacts.append(_artifact(logical_path, role, content))

    config_path = openspec_root / "config.yaml"
    config_content = _read_optional_regular_file(
        config_path,
        boundary=openspec_root,
    )
    if config_content is not None:
        artifacts.append(
            _artifact(
                PurePosixPath("config.yaml"),
                OpenSpecArtifactRole.PROJECT_CONFIG,
                config_content,
            )
        )

    for capability in sorted(delta_capabilities):
        base_path = openspec_root / "specs" / capability / "spec.md"
        content = _read_optional_regular_file(
            base_path,
            boundary=openspec_root,
        )
        if content is not None:
            artifacts.append(
                _artifact(
                    PurePosixPath("specs") / capability / "spec.md",
                    OpenSpecArtifactRole.BASE_SPEC,
                    content,
                )
            )

    if len(artifacts) > MAX_OPENSPEC_ARTIFACTS:
        _fail(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "OpenSpec artifact count exceeds the profile limit",
        )
    artifacts.sort(key=lambda artifact: artifact.path)
    _validate_profile(artifacts, change_prefix)

    try:
        return ChangeProposal(
            kind="change_proposal",
            change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
            schema_uri=CHANGE_PROPOSAL_SCHEMA_URI,
            change_id=change_id,
            base_behavior=_behavior_ref(base_behavior),
            openspec=OpenSpecManifest(
                kind="openspec_manifest",
                profile=OPENSPEC_INTEROP_PROFILE,
                tested_against_version=OPENSPEC_TESTED_AGAINST_VERSION,
                change_path=change_prefix.as_posix(),
                artifacts=tuple(artifacts),
            ),
        )
    except PydanticValidationError as error:
        _fail(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            f"OpenSpec import does not satisfy the closed profile: {error}",
        )
        raise AssertionError("unreachable") from error


def export_openspec_change(
    proposal: ChangeProposal,
    destination: Path,
    *,
    before_publish: Callable[[], None] | None = None,
) -> None:
    """Publish an exact OpenSpec tree without merging user-owned content."""
    destination = _require_path(
        destination,
        location="$.destination",
        label="destination",
    )
    if before_publish is not None and not callable(before_publish):
        _invalid_public_input(
            "before_publish must be callable or None",
            location="$.before_publish",
        )
    proposal = parse_change_proposal_json(canonical_change_lifecycle_json(proposal))
    destination = _absolute_without_symlink_resolution(destination)
    parent = destination.parent
    _validate_export_parent(parent)
    expected = {
        PurePosixPath(artifact.path): base64.b64decode(artifact.content_base64)
        for artifact in proposal.openspec.artifacts
    }
    if before_publish is not None:
        before_publish()
    if _path_exists_without_following(destination):
        if _directory_contents(destination) == expected:
            return
        _fail(
            ChangeLifecycleErrorCode.DESTINATION_CONFLICT,
            "existing export destination is not the exact manifest",
        )

    try:
        stage = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.ucf-stage-",
                dir=parent,
            )
        )
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.PUBLISH_FAILED,
            f"cannot create staged OpenSpec directory: {error}",
        )
        raise AssertionError("unreachable") from error
    published = False
    try:
        _write_staged_tree(stage, expected)
        if _directory_contents(stage) != expected:
            _fail(
                ChangeLifecycleErrorCode.PUBLISH_FAILED,
                "staged OpenSpec tree differs from the proposal manifest",
            )
        if _path_exists_without_following(destination):
            _fail(
                ChangeLifecycleErrorCode.DESTINATION_CONFLICT,
                "export destination appeared before publication",
            )
        if before_publish is not None:
            before_publish()
        try:
            os.replace(stage, destination)
            published = True
            _fsync_directory(parent)
        except OSError as error:
            _fail(
                ChangeLifecycleErrorCode.PUBLISH_FAILED,
                f"cannot publish staged OpenSpec tree: {error}",
            )
    finally:
        primary_error = sys.exception()
        if not published:
            try:
                stage_exists = _path_exists_without_following(stage)
            except ChangeLifecycleValidationError as cleanup_error:
                if primary_error is None:
                    raise
                primary_error.add_note(
                    "also failed to inspect the staged OpenSpec directory "
                    f"during cleanup: {cleanup_error}"
                )
                stage_exists = False
            if stage_exists:
                try:
                    shutil.rmtree(stage)
                except OSError as cleanup_error:
                    message = (
                        "also failed to remove the staged OpenSpec directory: "
                        f"{cleanup_error}"
                    )
                    if primary_error is None:
                        _fail(ChangeLifecycleErrorCode.PUBLISH_FAILED, message)
                    primary_error.add_note(message)


def _absolute_without_symlink_resolution(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_path(value: object, *, location: str, label: str) -> Path:
    if not isinstance(value, Path):
        _invalid_public_input(
            f"{label} must be a pathlib.Path instance",
            location=location,
        )
    return value


def _invalid_public_input(message: str, *, location: str) -> None:
    raise ChangeLifecycleValidationError(
        ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        message,
        location=location,
    )


def _validated_openspec_root(change_directory: Path) -> Path:
    if change_directory.parent.name != "changes" or not change_directory.name:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            "change directory must be <openspec-root>/changes/<change-id>",
        )
    openspec_root = change_directory.parent.parent
    _validate_real_directory_chain(
        change_directory,
        label="OpenSpec change path",
    )
    return openspec_root


def _validate_real_directory_chain(path: Path, *, label: str) -> None:
    if not path.is_absolute():
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            f"{label} must be absolute",
        )
    current = Path(path.anchor)
    components = path.parts[1:]
    for component in components:
        current /= component
        try:
            metadata = current.lstat()
        except OSError as error:
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                f"{label} component is not safely accessible: {error}",
            )
        if _is_filesystem_alias(current, metadata) or not stat.S_ISDIR(
            metadata.st_mode
        ):
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                f"{label} must contain only real directories, not aliases",
            )


def _validate_export_parent(parent: Path) -> None:
    _validate_real_directory_chain(parent, label="export parent path")


def _path_exists_without_following(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            f"cannot inspect filesystem path: {error}",
        )
    return True


def _directory_contents(
    directory: Path,
) -> dict[PurePosixPath, bytes]:
    try:
        metadata = directory.lstat()
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            f"cannot inspect export directory: {error}",
        )
    if _is_filesystem_alias(directory, metadata):
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            "export destination is a filesystem alias",
        )
    if not stat.S_ISDIR(metadata.st_mode):
        _fail(
            ChangeLifecycleErrorCode.DESTINATION_CONFLICT,
            "export destination is not a real directory",
        )
    return dict(_walk_regular_files(directory))


def _write_staged_tree(
    stage: Path,
    expected: dict[PurePosixPath, bytes],
) -> None:
    directories = {
        parent for relative in expected for parent in relative.parents if parent.parts
    }
    for relative in sorted(directories, key=lambda item: item.parts):
        try:
            (stage / relative.as_posix()).mkdir(mode=0o700)
        except OSError as error:
            _fail(
                ChangeLifecycleErrorCode.PUBLISH_FAILED,
                f"cannot create staged OpenSpec directory: {error}",
            )
    for relative, content in sorted(
        expected.items(),
        key=lambda item: item[0].as_posix(),
    ):
        path = stage / relative.as_posix()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
            try:
                remaining = memoryview(content)
                while remaining:
                    written = os.write(descriptor, remaining)
                    if written <= 0:
                        raise OSError("zero-byte staged write")
                    remaining = remaining[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as error:
            _fail(
                ChangeLifecycleErrorCode.PUBLISH_FAILED,
                f"cannot write staged OpenSpec artifact: {error}",
            )
    for relative in sorted(
        directories,
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        _fsync_directory(stage / relative.as_posix())
    _fsync_directory(stage)


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.PUBLISH_FAILED,
            f"cannot sync OpenSpec directory: {error}",
        )


def _walk_regular_files(
    root: Path,
) -> tuple[tuple[PurePosixPath, bytes], ...]:
    files: list[tuple[PurePosixPath, bytes]] = []
    pending: list[tuple[bool, Path, PurePosixPath]] = [(True, root, PurePosixPath())]
    while pending:
        scan_directory, path, relative = pending.pop()
        if scan_directory:
            try:
                entries = sorted(
                    os.scandir(path),
                    key=lambda entry: entry.name,
                )
            except OSError as error:
                _fail(
                    ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                    f"cannot enumerate OpenSpec directory: {error}",
                )
            if relative.parts and not entries:
                _fail(
                    ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE,
                    "empty OpenSpec directories cannot be preserved",
                )
            pending.extend(
                (False, Path(entry.path), relative / entry.name)
                for entry in reversed(entries)
            )
            continue
        try:
            metadata = path.lstat()
        except OSError as error:
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                f"cannot inspect OpenSpec entry: {error}",
            )
        if _is_filesystem_alias(path, metadata):
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                "OpenSpec tree contains a filesystem alias",
            )
        if stat.S_ISDIR(metadata.st_mode):
            pending.append((True, path, relative))
            continue
        if not stat.S_ISREG(metadata.st_mode):
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                "OpenSpec tree contains a non-regular entry",
            )
        files.append(
            (
                relative,
                _read_stable_regular_file(path, metadata),
            )
        )
        if len(files) > MAX_OPENSPEC_ARTIFACTS:
            _fail(
                ChangeLifecycleErrorCode.INVALID_STRUCTURE,
                "OpenSpec artifact count exceeds the profile limit",
            )
    return tuple(files)


def _read_optional_regular_file(
    path: Path,
    *,
    boundary: Path,
) -> bytes | None:
    try:
        relative_parent = path.parent.relative_to(boundary)
    except ValueError:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            "optional OpenSpec artifact escapes its workspace boundary",
        )
    current = boundary
    for component in relative_parent.parts:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                f"cannot inspect OpenSpec artifact parent: {error}",
            )
        if _is_filesystem_alias(current, metadata) or not stat.S_ISDIR(
            metadata.st_mode
        ):
            _fail(
                ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                "OpenSpec artifact parent must be a real directory",
            )
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            f"cannot inspect OpenSpec artifact: {error}",
        )
    if _is_filesystem_alias(path, metadata) or not stat.S_ISREG(metadata.st_mode):
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            "OpenSpec artifact must be a real regular file",
        )
    return _read_stable_regular_file(path, metadata)


def _is_filesystem_alias(path: Path, metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    is_junction = getattr(os.path, "isjunction", None)
    if is_junction is None:
        return False
    try:
        return bool(is_junction(path))
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            f"cannot classify filesystem alias: {error}",
        )
        raise AssertionError("unreachable") from error


def _read_stable_regular_file(path: Path, before: os.stat_result) -> bytes:
    if before.st_nlink != 1:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            "hard-linked OpenSpec artifacts are not accepted",
        )
    if before.st_size > MAX_OPENSPEC_ARTIFACT_BYTES:
        _fail(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "OpenSpec artifact exceeds the byte limit",
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                _fail(
                    ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
                    "OpenSpec artifact changed type or alias count",
                )
            content = os.read(descriptor, MAX_OPENSPEC_ARTIFACT_BYTES + 1)
            if os.read(descriptor, 1):
                content += b"x"
            after_open = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after_path = path.lstat()
    except OSError as error:
        _fail(
            ChangeLifecycleErrorCode.UNSAFE_FILESYSTEM,
            f"cannot read OpenSpec artifact safely: {error}",
        )
    if len(content) > MAX_OPENSPEC_ARTIFACT_BYTES:
        _fail(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "OpenSpec artifact exceeds the byte limit",
        )
    if (
        _stable_identity(before) != _stable_identity(opened)
        or _stable_identity(opened) != _stable_identity(after_open)
        or _stable_identity(after_open) != _stable_identity(after_path)
        or len(content) != after_open.st_size
    ):
        _fail(
            ChangeLifecycleErrorCode.SOURCE_CHANGED,
            "OpenSpec artifact changed while it was imported",
        )
    return content


def _stable_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _artifact(
    path: PurePosixPath,
    role: OpenSpecArtifactRole,
    content: bytes,
) -> OpenSpecArtifact:
    try:
        return OpenSpecArtifact(
            kind="openspec_artifact",
            path=path.as_posix(),
            role=role,
            media_type=_artifact_media_type(path),
            content_base64=base64.b64encode(content).decode("ascii"),
            byte_digest=Digest(
                kind="digest",
                algorithm="sha-256",
                value=hashlib.sha256(content).hexdigest(),
            ),
        )
    except PydanticValidationError as error:
        _fail(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            f"OpenSpec artifact does not satisfy the closed profile: {error}",
        )
        raise AssertionError("unreachable") from error


def _validate_profile(
    artifacts: list[OpenSpecArtifact],
    change_prefix: PurePosixPath,
) -> None:
    try:
        validate_spec_driven_profile(
            ((artifact.path, artifact.content_base64) for artifact in artifacts),
            change_path=change_prefix.as_posix(),
        )
    except InvalidOpenSpecProfileError as error:
        _fail(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            str(error),
        )
    except UnsupportedOpenSpecProfileError as error:
        _fail(
            ChangeLifecycleErrorCode.UNSUPPORTED_OPENSPEC_PROFILE,
            str(error),
        )


def _behavior_ref(document: BehaviorIR) -> BehaviorDocumentRef:
    return BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(
                canonical_ir_json(document).encode("utf-8")
            ).hexdigest(),
        ),
    )


def _fail(code: ChangeLifecycleErrorCode, message: str) -> None:
    raise ChangeLifecycleValidationError(
        code,
        message,
        location="$filesystem",
    )


__all__ = ["export_openspec_change", "import_openspec_change"]
