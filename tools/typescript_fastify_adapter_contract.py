"""Exact source-copy contract for the TypeScript/Fastify ecosystem proof."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

type SourceManifestEntry = tuple[str, int, str]
type SourceManifest = tuple[SourceManifestEntry, ...]

_ROOT_INPUTS = frozenset(
    {
        ".gitignore",
        "README.md",
        "package-lock.json",
        "package.json",
        "tsconfig.json",
    }
)
_FIXTURE_INPUTS = frozenset(
    {
        ".gitignore",
        "README.md",
        "package-lock.json",
        "package.json",
        "src/service.test.ts",
        "src/service.ts",
        "tsconfig.json",
    }
)
_GENERATED_DIRECTORIES = frozenset(
    {".artifacts", ".npm", "dist", "node_modules"}
)
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_WRITE_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_NOFOLLOW", 0)
)


class SourceContractError(ValueError):
    """Raised when a source tree is unsafe or outside the closed contract."""


@dataclass(frozen=True)
class AdapterBuildReceipt:
    """Observable result of the one session-scoped external adapter build."""

    node_version: str
    npm_version: str
    commands: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class TypeScriptFastifyTarget:
    """One fresh external legacy fixture driven by one external adapter."""

    adapter_entry: Path
    fixture_root: Path
    source_manifest: SourceManifest

    def command(self, *, hash_seed: int | None = None) -> tuple[str, ...]:
        return _node_command(self.adapter_entry, hash_seed=hash_seed)


@dataclass(frozen=True)
class TypeScriptFastifyHarness:
    """Session-scoped external adapter build and fresh-target factory."""

    adapter_root: Path
    adapter_entry: Path
    adapter_source_manifest: SourceManifest
    fixture_source_root: Path
    fixture_source_manifest: SourceManifest
    build_receipt: AdapterBuildReceipt

    def command(self, *, hash_seed: int | None = None) -> tuple[str, ...]:
        return _node_command(self.adapter_entry, hash_seed=hash_seed)

    def new_target(self, destination: Path) -> TypeScriptFastifyTarget:
        copied = copy_typescript_fastify_fixture(
            self.fixture_source_root,
            destination,
        )
        if copied != self.fixture_source_manifest:
            raise SourceContractError(
                "fixture source changed after the harness was built"
            )
        return TypeScriptFastifyTarget(
            adapter_entry=self.adapter_entry,
            fixture_root=destination,
            source_manifest=copied,
        )


def typescript_fastify_adapter_manifest(root: Path) -> SourceManifest:
    """Return the closed, non-following adapter input manifest."""

    files = _scan_regular_inputs(root, contract="adapter")
    relative_paths = frozenset(files)
    missing_root = _ROOT_INPUTS - relative_paths
    if missing_root:
        raise SourceContractError(
            f"adapter source is missing required inputs: {sorted(missing_root)}"
        )
    if "src/main.ts" not in relative_paths:
        raise SourceContractError(
            "adapter source is missing required input: src/main.ts"
        )
    if not any(
        path.startswith("test/") and path.endswith(".test.mjs")
        for path in relative_paths
    ):
        raise SourceContractError(
            "adapter source has no test/**/*.test.mjs inputs"
        )
    return _manifest(files)


def typescript_fastify_fixture_manifest(root: Path) -> SourceManifest:
    """Return the exact seven-file, non-following fixture manifest."""

    files = _scan_regular_inputs(root, contract="fixture")
    relative_paths = frozenset(files)
    missing = _FIXTURE_INPUTS - relative_paths
    unexpected = relative_paths - _FIXTURE_INPUTS
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if unexpected:
            details.append(f"unexpected={sorted(unexpected)}")
        raise SourceContractError(
            "fixture source inputs are not exact: " + ", ".join(details)
        )
    return _manifest(files)


def copy_typescript_fastify_adapter(
    source: Path,
    destination: Path,
) -> SourceManifest:
    """Copy only the exact adapter inputs and prove source/copy equality."""

    return _copy_contract(
        source,
        destination,
        manifest_function=typescript_fastify_adapter_manifest,
    )


def copy_typescript_fastify_fixture(
    source: Path,
    destination: Path,
) -> SourceManifest:
    """Copy only the seven fixture inputs and prove source/copy equality."""

    return _copy_contract(
        source,
        destination,
        manifest_function=typescript_fastify_fixture_manifest,
    )


def _node_command(
    adapter_entry: Path,
    *,
    hash_seed: int | None,
) -> tuple[str, ...]:
    if hash_seed is None:
        return ("node", str(adapter_entry))
    if isinstance(hash_seed, bool) or hash_seed < 0:
        raise SourceContractError("hash seed must be a non-negative integer")
    return ("node", f"--hash-seed={hash_seed}", str(adapter_entry))


def _copy_contract(
    source: Path,
    destination: Path,
    *,
    manifest_function,
) -> SourceManifest:
    source_root = _require_real_directory(source)
    destination = Path(os.path.abspath(destination))
    if destination.exists() or destination.is_symlink():
        raise SourceContractError(
            f"copy destination already exists: {destination}"
        )
    destination_parent = _require_real_directory(destination.parent)
    if destination.is_relative_to(source_root) or source_root.is_relative_to(
        destination
    ):
        raise SourceContractError(
            "source and destination trees must not contain one another"
        )

    source_before = manifest_function(source_root)
    try:
        destination.mkdir(mode=0o755)
        for relative, expected_size, expected_digest in source_before:
            source_path = source_root.joinpath(*PurePosixPath(relative).parts)
            payload, source_mode = _read_regular_file(source_path)
            if len(payload) != expected_size:
                raise SourceContractError(
                    f"source changed size while copying: {relative}"
                )
            if hashlib.sha256(payload).hexdigest() != expected_digest:
                raise SourceContractError(
                    f"source changed content while copying: {relative}"
                )
            destination_path = destination.joinpath(
                *PurePosixPath(relative).parts
            )
            destination_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            _write_new_regular_file(destination_path, payload, source_mode)

        source_after = manifest_function(source_root)
        copied = manifest_function(destination)
        if source_after != source_before:
            raise SourceContractError("source changed while it was copied")
        if copied != source_before:
            raise SourceContractError("copied source manifest is not exact")
        return copied
    except BaseException:
        if destination.parent == destination_parent:
            shutil.rmtree(destination, ignore_errors=True)
        raise


def _scan_regular_inputs(
    root: Path,
    *,
    contract: str,
) -> dict[str, bytes]:
    root = _require_real_directory(root)
    files: dict[str, bytes] = {}
    pending: list[tuple[Path, PurePosixPath]] = [(root, PurePosixPath())]

    while pending:
        directory, relative_directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise SourceContractError(
                f"cannot enumerate source directory: {directory}"
            ) from error
        for entry in entries:
            relative = relative_directory / entry.name
            relative_text = relative.as_posix()
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise SourceContractError(
                    f"cannot inspect source input: {relative_text}"
                ) from error

            if stat.S_ISLNK(metadata.st_mode):
                raise SourceContractError(
                    f"source input must not be a symlink: {relative_text}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    not relative_directory.parts
                    and entry.name in _GENERATED_DIRECTORIES
                ):
                    continue
                if not _directory_is_allowed(relative, contract=contract):
                    raise SourceContractError(
                        f"unexpected source directory: {relative_text}"
                    )
                pending.append((Path(entry.path), relative))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise SourceContractError(
                    f"source input must be a regular file: {relative_text}"
                )
            if not _file_is_allowed(relative, contract=contract):
                raise SourceContractError(
                    f"unexpected source input: {relative_text}"
                )
            payload, _ = _read_regular_file(Path(entry.path))
            files[relative_text] = payload

    return files


def _directory_is_allowed(path: PurePosixPath, *, contract: str) -> bool:
    if contract == "adapter":
        return path.parts[0] in {"src", "test"}
    if contract == "fixture":
        return path.parts[0] == "src"
    raise SourceContractError(f"unknown source contract: {contract}")


def _file_is_allowed(path: PurePosixPath, *, contract: str) -> bool:
    text = path.as_posix()
    if len(path.parts) == 1:
        return text in _ROOT_INPUTS
    if contract == "adapter":
        return (
            path.parts[0] == "src"
            and path.suffix == ".ts"
            or path.parts[0] == "test"
            and text.endswith(".mjs")
        )
    if contract == "fixture":
        return text in _FIXTURE_INPUTS
    raise SourceContractError(f"unknown source contract: {contract}")


def _manifest(files: dict[str, bytes]) -> SourceManifest:
    return tuple(
        (
            relative,
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        )
        for relative, payload in sorted(files.items())
    )


def _require_real_directory(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    try:
        resolved = absolute.resolve(strict=True)
        metadata = absolute.lstat()
    except OSError as error:
        raise SourceContractError(
            f"source directory is unavailable: {absolute}"
        ) from error
    if absolute != resolved:
        raise SourceContractError(
            f"directory path must not contain symlinks or aliases: {absolute}"
        )
    if not stat.S_ISDIR(metadata.st_mode):
        raise SourceContractError(f"path is not a directory: {absolute}")
    return absolute


def _read_regular_file(path: Path) -> tuple[bytes, int]:
    try:
        before = path.lstat()
        descriptor = os.open(path, _READ_FLAGS)
    except OSError as error:
        raise SourceContractError(
            f"cannot open regular source input: {path}"
        ) from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(opened.st_mode):
            raise SourceContractError(
                f"source input is not a regular file: {path}"
            )
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise SourceContractError(f"source input changed while opening: {path}")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    try:
        after = path.lstat()
    except OSError as error:
        raise SourceContractError(
            f"source input disappeared while reading: {path}"
        ) from error
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(payload) != opened.st_size
    ):
        raise SourceContractError(f"source input changed while reading: {path}")
    return payload, stat.S_IMODE(opened.st_mode)


def _write_new_regular_file(path: Path, payload: bytes, mode: int) -> None:
    try:
        descriptor = os.open(path, _WRITE_FLAGS, mode)
    except OSError as error:
        raise SourceContractError(
            f"cannot create copied source input: {path}"
        ) from error
    try:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise SourceContractError(
                    f"cannot complete copied source input: {path}"
                )
            remaining = remaining[written:]
    finally:
        os.close(descriptor)
