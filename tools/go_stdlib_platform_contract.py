"""Closed source and build contract for the Go platform fixture."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from .go_stdlib_adapter_contract import (
        GoBuildReceipt,
        SourceContractError,
        SourceManifest,
        _copy_contract,
        _source_manifest,
    )
else:
    from go_stdlib_adapter_contract import (
        GoBuildReceipt,
        SourceContractError,
        SourceManifest,
        _copy_contract,
        _source_manifest,
    )

GO_STDLIB_PLATFORM_INPUTS = frozenset(
    {
        ".gitignore",
        "README.md",
        "cmd/platform/main.go",
        "cmd/platform/main_test.go",
        "go.mod",
        "quote/service.go",
        "quote/service_test.go",
        "spool/spool.go",
        "spool/spool_test.go",
    }
)
GO_STDLIB_PLATFORM_SOURCE_REVISION = (
    "7b563b0296cb40498b984edc1ea3eb96b9fb8e96c8225aa695bc50b8b0889d2d"
)
GO_STDLIB_PLATFORM_BINARY_SHA256 = (
    "f54ab3d5dfc50b5bf57610da6ec081aa3b4f700a71064fdaf041ebc56ac7cff4"
)
GO_STDLIB_CLI_EXECUTION_ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:"
    "go1.26.5-linux-amd64-cgo0-cli-process:1.0.0"
)
GO_STDLIB_EVENT_EXECUTION_ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:"
    "go1.26.5-linux-amd64-cgo0-file-spool-event:1.0.0"
)
GO_STDLIB_PLATFORM_BUILD_FLAGS = (
    "-mod=readonly",
    "-trimpath",
    "-buildvcs=false",
    "-ldflags=-buildid=",
)
GO_STDLIB_PLATFORM_BUILD_COMMANDS = (
    ("go", "mod", "tidy", "-diff"),
    ("go", "mod", "verify"),
    ("go", "list", "-mod=readonly", "-m", "all"),
    ("go", "vet", "-mod=readonly", "./..."),
    (
        "go",
        "test",
        "-count=1",
        "-mod=readonly",
        "-trimpath",
        "-buildvcs=false",
        "./...",
    ),
    (
        "go",
        "build",
        *GO_STDLIB_PLATFORM_BUILD_FLAGS,
        "./cmd/platform",
    ),
)
GO_STDLIB_PLATFORM_BUILD_METADATA = (
    "path\texample.com/legacyplatforms/cmd/platform",
    "mod\texample.com/legacyplatforms\t(devel)\t",
    "build\t-buildmode=exe",
    "build\t-compiler=gc",
    "build\t-trimpath=true",
    "build\tCGO_ENABLED=0",
    "build\tGOARCH=amd64",
    "build\tGOOS=linux",
    "build\tGOAMD64=v1",
)
_GO_STDLIB_PLATFORM_DIRECTORIES = frozenset(
    {"cmd", "cmd/platform", "quote", "spool"}
)


@dataclass(frozen=True)
class GoStdlibPlatformBuildReceipt:
    """Observable result of two reproducible external platform builds."""

    go_version: str
    environment: tuple[tuple[str, str], ...]
    commands: tuple[tuple[str, ...], ...]
    build_metadata: tuple[str, ...]
    platform_sha256: str
    platform_size: int


@dataclass(frozen=True)
class GoStdlibPlatformTarget:
    """One fresh platform source copy driven by the external Go adapter."""

    adapter_entry: Path
    fixture_entry: Path
    fixture_root: Path
    source_manifest: SourceManifest

    def command(self) -> tuple[str, ...]:
        return (str(self.adapter_entry),)

    def verification_command(self) -> tuple[str, ...]:
        return (
            str(self.adapter_entry),
            "--platform-fixture-executable",
            str(self.fixture_entry),
        )


@dataclass(frozen=True)
class GoStdlibPlatformHarness:
    """Session-scoped reproducible platform build and reusable adapter."""

    adapter_entry: Path
    platform_build_root: Path
    platform_entry: Path
    reproducible_platform_entry: Path
    platform_source_root: Path
    platform_source_manifest: SourceManifest
    build_receipt: GoStdlibPlatformBuildReceipt

    def new_target(self, destination: Path) -> GoStdlibPlatformTarget:
        copied = copy_go_stdlib_platform_fixture(
            self.platform_source_root,
            destination,
        )
        if copied != self.platform_source_manifest:
            raise SourceContractError(
                "platform source changed after the harness was built"
            )
        return GoStdlibPlatformTarget(
            adapter_entry=self.adapter_entry,
            fixture_entry=self.platform_entry,
            fixture_root=destination,
            source_manifest=copied,
        )


def go_stdlib_platform_manifest(root: Path) -> SourceManifest:
    """Return the exact non-following nine-file platform manifest."""

    return _source_manifest(
        root,
        contract_name="platform fixture",
        expected_files=GO_STDLIB_PLATFORM_INPUTS,
        allowed_directories=_GO_STDLIB_PLATFORM_DIRECTORIES,
        ignored_root_directories=frozenset(),
    )


def copy_go_stdlib_platform_fixture(
    source: Path,
    destination: Path,
) -> SourceManifest:
    """Copy only accepted platform source and prove source/copy equality."""

    return _copy_contract(
        source,
        destination,
        manifest_function=go_stdlib_platform_manifest,
    )


def go_stdlib_platform_source_revision(
    manifest: SourceManifest,
) -> str:
    """Return the frozen canonical TSV manifest digest."""

    payload = "".join(
        f"{relative}\t{size}\t{digest}\n"
        for relative, size, digest in manifest
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def validate_go_stdlib_platform_build_metadata(
    output: str,
    *,
    executable: Path,
) -> tuple[str, ...]:
    """Reject build metadata outside the frozen Go execution profile."""

    expected = (
        f"{executable}: go1.26.5",
        *(f"\t{line}" for line in GO_STDLIB_PLATFORM_BUILD_METADATA),
    )
    observed = tuple(output.splitlines())
    if observed != expected:
        raise SourceContractError(
            "Go platform binary build metadata is not exact"
        )
    return GO_STDLIB_PLATFORM_BUILD_METADATA


def go_stdlib_platform_execution_environment_revision(
    adapter_build: GoBuildReceipt,
    platform_build: GoStdlibPlatformBuildReceipt,
    *,
    source_revision: str,
    boundary: str,
) -> str:
    """Derive the exact adapter-side platform execution receipt digest."""

    if boundary not in {"cli-process", "file-spool-event"}:
        raise SourceContractError("Go platform boundary is unsupported")
    adapter_environment = dict(adapter_build.environment)
    platform_environment = dict(platform_build.environment)
    expected_environment = {
        "CGO_ENABLED": "0",
        "GOARCH": "amd64",
        "GOAMD64": "v1",
        "GOOS": "linux",
        "GOTOOLCHAIN": "local",
    }
    if (
        adapter_build.go_version != "go version go1.26.5 linux/amd64"
        or platform_build.go_version
        != "go version go1.26.5 linux/amd64"
        or any(
            adapter_environment.get(name) != value
            or platform_environment.get(name) != value
            for name, value in expected_environment.items()
        )
        or not _is_sha256(adapter_build.adapter_sha256)
        or not _is_sha256(platform_build.platform_sha256)
        or not _is_sha256(source_revision)
        or adapter_build.adapter_size < 1
        or platform_build.platform_size < 1
    ):
        raise SourceContractError(
            "Go platform execution receipt is outside the profile"
        )

    def digest(value: str) -> dict[str, str]:
        return {
            "kind": "digest",
            "algorithm": "sha-256",
            "value": value,
        }

    receipt = {
        "kind": "go_stdlib_execution_receipt",
        "receipt_version": "1.0.0",
        "binaries": [
            {
                "kind": "go_binary",
                "role": "adapter",
                "module_path": "ucf/adapters/go-stdlib",
                "digest": digest(adapter_build.adapter_sha256),
                "size_bytes": adapter_build.adapter_size,
            },
            {
                "kind": "go_binary",
                "role": "fixture",
                "module_path": "example.com/legacyplatforms",
                "digest": digest(platform_build.platform_sha256),
                "size_bytes": platform_build.platform_size,
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
            "network": "disabled",
            "boundary": boundary,
        },
        "source": {
            "kind": "source_identity",
            "subject_uri": (
                "urn:ucf:repository:go-stdlib-legacy-platforms"
            ),
            "source_revision": digest(source_revision),
        },
    }
    payload = (
        json.dumps(
            receipt,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
