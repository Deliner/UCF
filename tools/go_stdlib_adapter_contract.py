"""Closed source-copy contract for the Go standard-library ecosystem proof."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

type SourceManifestEntry = tuple[str, int, str]
type SourceManifest = tuple[SourceManifestEntry, ...]

GO_STDLIB_EXECUTION_ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:"
    "go1.26.5-linux-amd64-cgo0-loopback:1.0.0"
)
GO_STDLIB_EXECUTION_RECEIPT_VERSION = "1.0.0"
GO_STDLIB_UPSTREAM_NOTICE_DIGESTS = {
    "third_party/go/LICENSE": (
        "911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad"
    ),
    "third_party/go/PATENTS": (
        "96f408bfae65bf137fc2525d3ecb030271c50c1e90799f87abf8846d8dd505cc"
    ),
}

GO_STDLIB_ADAPTER_INPUTS = frozenset(
    {
        "README.md",
        "cmd/adapter/classification.go",
        "cmd/adapter/discovery.go",
        "cmd/adapter/executable_snapshot.go",
        "cmd/adapter/inventory.go",
        "cmd/adapter/main.go",
        "cmd/adapter/main_test.go",
        "cmd/adapter/mapping.go",
        "cmd/adapter/platform_classification.go",
        "cmd/adapter/platform_verification.go",
        "cmd/adapter/process_ownership.go",
        "cmd/adapter/runner.go",
        "cmd/adapter/verification.go",
        "go.mod",
        "third_party/go/LICENSE",
        "third_party/go/PATENTS",
    }
)
GO_STDLIB_FIXTURE_INPUTS = frozenset(
    {
        ".gitignore",
        "README.md",
        "cmd/server/main.go",
        "go.mod",
        "quote/service.go",
        "quote/service_test.go",
    }
)
_ADAPTER_DIRECTORIES = frozenset(
    {"cmd", "cmd/adapter", "third_party", "third_party/go"}
)
_FIXTURE_DIRECTORIES = frozenset({"cmd", "cmd/server", "quote"})
_ADAPTER_GENERATED_ROOTS = frozenset(
    {".artifacts", ".cache", "bin", "out"}
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
class GoBuildReceipt:
    """Observable result of two reproducible external Go builds."""

    go_version: str
    environment: tuple[tuple[str, str], ...]
    commands: tuple[tuple[str, ...], ...]
    adapter_sha256: str
    adapter_size: int
    fixture_sha256: str
    fixture_size: int


@dataclass(frozen=True)
class GoStdlibTarget:
    """One fresh legacy source copy driven by the external compiled adapter."""

    adapter_entry: Path
    fixture_entry: Path
    fixture_root: Path
    source_manifest: SourceManifest

    def command(self) -> tuple[str, ...]:
        return (str(self.adapter_entry),)

    def verification_command(self) -> tuple[str, ...]:
        return (
            str(self.adapter_entry),
            "--fixture-executable",
            str(self.fixture_entry),
        )


@dataclass(frozen=True)
class GoStdlibHarness:
    """Session-scoped reproducible adapter and fixture build."""

    adapter_root: Path
    adapter_entry: Path
    adapter_source_manifest: SourceManifest
    fixture_build_root: Path
    fixture_entry: Path
    fixture_source_root: Path
    fixture_source_manifest: SourceManifest
    build_receipt: GoBuildReceipt

    def command(self) -> tuple[str, ...]:
        return (str(self.adapter_entry),)

    def new_target(self, destination: Path) -> GoStdlibTarget:
        copied = copy_go_stdlib_fixture(
            self.fixture_source_root,
            destination,
        )
        if copied != self.fixture_source_manifest:
            raise SourceContractError(
                "fixture source changed after the harness was built"
            )
        return GoStdlibTarget(
            adapter_entry=self.adapter_entry,
            fixture_entry=self.fixture_entry,
            fixture_root=destination,
            source_manifest=copied,
        )


def go_stdlib_adapter_manifest(root: Path) -> SourceManifest:
    """Return the exact non-following Go adapter input manifest."""

    manifest = _source_manifest(
        root,
        contract_name="adapter",
        expected_files=GO_STDLIB_ADAPTER_INPUTS,
        allowed_directories=_ADAPTER_DIRECTORIES,
        ignored_root_directories=_ADAPTER_GENERATED_ROOTS,
    )
    digests = {relative: digest for relative, _, digest in manifest}
    if any(
        digests.get(relative) != expected
        for relative, expected in GO_STDLIB_UPSTREAM_NOTICE_DIGESTS.items()
    ):
        raise SourceContractError("Go upstream notice is not exact")
    return manifest


def go_stdlib_fixture_manifest(root: Path) -> SourceManifest:
    """Return the exact non-following six-file legacy fixture manifest."""

    return _source_manifest(
        root,
        contract_name="fixture",
        expected_files=GO_STDLIB_FIXTURE_INPUTS,
        allowed_directories=_FIXTURE_DIRECTORIES,
        ignored_root_directories=frozenset(),
    )


def go_stdlib_execution_receipt(
    build: GoBuildReceipt,
    *,
    source_revision: str,
) -> dict[str, object]:
    """Return the exact receipt derivable by both harness and adapter."""

    environment = dict(build.environment)
    expected_environment = {
        "CGO_ENABLED": "0",
        "GOARCH": "amd64",
        "GOAMD64": "v1",
        "GOOS": "linux",
        "GOTOOLCHAIN": "local",
    }
    if (
        build.go_version != "go version go1.26.5 linux/amd64"
        or any(
            environment.get(name) != value
            for name, value in expected_environment.items()
        )
        or not _is_sha256(build.adapter_sha256)
        or not _is_sha256(build.fixture_sha256)
        or not _is_sha256(source_revision)
        or build.adapter_size < 1
        or build.fixture_size < 1
    ):
        raise SourceContractError(
            "Go build receipt is outside the execution profile"
        )
    def digest(value: str) -> dict[str, str]:
        return {
            "kind": "digest",
            "algorithm": "sha-256",
            "value": value,
        }

    return {
        "kind": "go_stdlib_execution_receipt",
        "receipt_version": GO_STDLIB_EXECUTION_RECEIPT_VERSION,
        "binaries": [
            {
                "kind": "go_binary",
                "role": "adapter",
                "module_path": "ucf/adapters/go-stdlib",
                "digest": digest(build.adapter_sha256),
                "size_bytes": build.adapter_size,
            },
            {
                "kind": "go_binary",
                "role": "fixture",
                "module_path": "example.com/legacyquotes",
                "digest": digest(build.fixture_sha256),
                "size_bytes": build.fixture_size,
            },
        ],
        "toolchain": {
            "kind": "go_toolchain",
            "version": "go1.26.5",
            "mode": "local",
        },
        "build": {
            "kind": "go_build_coordinates",
            "build_mode": "exe",
            "compiler": "gc",
            "trimpath": True,
            "cgo_enabled": False,
            "goos": "linux",
            "goarch": "amd64",
            "goamd64": "v1",
            "external_modules": [],
        },
        "runtime": {
            "kind": "go_runtime_coordinates",
            "version": "go1.26.5",
            "goos": "linux",
            "goarch": "amd64",
            "network": "loopback-only",
        },
        "source": {
            "kind": "source_identity",
            "subject_uri": (
                "urn:ucf:repository:go-stdlib-legacy-quote"
            ),
            "source_revision": digest(source_revision),
        },
    }


def canonical_go_stdlib_execution_receipt(
    build: GoBuildReceipt,
    *,
    source_revision: str,
) -> bytes:
    receipt = go_stdlib_execution_receipt(
        build,
        source_revision=source_revision,
    )
    return (
        json.dumps(
            receipt,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def go_stdlib_execution_environment_revision(
    build: GoBuildReceipt,
    *,
    source_revision: str,
) -> str:
    return hashlib.sha256(
        canonical_go_stdlib_execution_receipt(
            build,
            source_revision=source_revision,
        )
    ).hexdigest()


def copy_go_stdlib_adapter(
    source: Path,
    destination: Path,
) -> SourceManifest:
    """Copy only accepted adapter source and prove source/copy equality."""

    return _copy_contract(
        source,
        destination,
        manifest_function=go_stdlib_adapter_manifest,
    )


def copy_go_stdlib_fixture(
    source: Path,
    destination: Path,
) -> SourceManifest:
    """Copy only the frozen fixture and prove source/copy equality."""

    return _copy_contract(
        source,
        destination,
        manifest_function=go_stdlib_fixture_manifest,
    )


def _source_manifest(
    root: Path,
    *,
    contract_name: str,
    expected_files: frozenset[str],
    allowed_directories: frozenset[str],
    ignored_root_directories: frozenset[str],
) -> SourceManifest:
    root = _require_real_directory(root)
    files: dict[str, bytes] = {}
    pending: list[tuple[Path, PurePosixPath]] = [(root, PurePosixPath())]

    while pending:
        directory, relative_directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise SourceContractError(
                f"cannot enumerate {contract_name} source: {directory}"
            ) from error
        for entry in entries:
            relative = relative_directory / entry.name
            relative_text = relative.as_posix()
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise SourceContractError(
                    f"cannot inspect {contract_name} input: {relative_text}"
                ) from error

            if stat.S_ISLNK(metadata.st_mode):
                raise SourceContractError(
                    f"{contract_name} input must not be a symlink: "
                    f"{relative_text}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    not relative_directory.parts
                    and entry.name in ignored_root_directories
                ):
                    continue
                if relative_text not in allowed_directories:
                    raise SourceContractError(
                        f"unexpected {contract_name} directory: "
                        f"{relative_text}"
                    )
                pending.append((Path(entry.path), relative))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise SourceContractError(
                    f"{contract_name} input must be regular: {relative_text}"
                )
            if relative_text not in expected_files:
                raise SourceContractError(
                    f"unexpected {contract_name} input: {relative_text}"
                )
            payload, _ = _read_regular_file(Path(entry.path))
            files[relative_text] = payload

    missing = expected_files - frozenset(files)
    if missing:
        raise SourceContractError(
            f"missing {contract_name} input: {sorted(missing)}"
        )
    return _manifest(files)


def _copy_contract(
    source: Path,
    destination: Path,
    *,
    manifest_function: Callable[[Path], SourceManifest],
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
            source_path = source_root.joinpath(
                *PurePosixPath(relative).parts
            )
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
            destination_path.parent.mkdir(
                mode=0o755,
                parents=True,
                exist_ok=True,
            )
            _write_new_regular_file(
                destination_path,
                payload,
                source_mode,
            )

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


def _manifest(files: dict[str, bytes]) -> SourceManifest:
    return tuple(
        (
            relative,
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        )
        for relative, payload in sorted(files.items())
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
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
        if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(
            opened.st_mode
        ):
            raise SourceContractError(
                f"source input is not a regular file: {path}"
            )
        if (before.st_dev, before.st_ino) != (
            opened.st_dev,
            opened.st_ino,
        ):
            raise SourceContractError(
                f"source input changed while opening: {path}"
            )
        chunks: list[bytes] = []
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
        raise SourceContractError(
            f"source input changed while reading: {path}"
        )
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
