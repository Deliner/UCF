from __future__ import annotations

import hashlib
import os
import shlex
import stat
import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GoBuildReceipt,
    GoStdlibHarness,
    copy_go_stdlib_adapter,
    copy_go_stdlib_fixture,
    go_stdlib_adapter_manifest,
    go_stdlib_fixture_manifest,
)
from tools.go_stdlib_platform_contract import (
    GO_STDLIB_PLATFORM_BINARY_SHA256,
    GO_STDLIB_PLATFORM_BUILD_COMMANDS,
    GO_STDLIB_PLATFORM_BUILD_FLAGS,
    GO_STDLIB_PLATFORM_SOURCE_REVISION,
    GoStdlibPlatformBuildReceipt,
    GoStdlibPlatformHarness,
    copy_go_stdlib_platform_fixture,
    go_stdlib_platform_manifest,
    go_stdlib_platform_source_revision,
    validate_go_stdlib_platform_build_metadata,
)
from tools.go_stdlib_toolchain import (
    GO_STDLIB_VERSION_OUTPUT,
    resolve_go_stdlib_binary,
)
from tools.typescript_fastify_adapter_contract import (
    AdapterBuildReceipt,
    TypeScriptFastifyHarness,
    copy_typescript_fastify_adapter,
    copy_typescript_fastify_fixture,
    typescript_fastify_adapter_manifest,
    typescript_fastify_fixture_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_SOURCE_ROOT = PROJECT_ROOT / "adapters" / "typescript-fastify"
FIXTURE_SOURCE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "typescript_fastify_legacy_quote"
)
GO_ADAPTER_SOURCE_ROOT = PROJECT_ROOT / "adapters" / "go-stdlib"
GO_FIXTURE_SOURCE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "go_stdlib_legacy_quote"
)
GO_PLATFORM_SOURCE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "go_stdlib_legacy_platforms"
)
_BUILD_COMMANDS = (
    ("node", "--version"),
    ("npm", "--version"),
    ("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"),
    ("npm", "run", "build"),
    ("npm", "test"),
)
_GO_BUILD_FLAGS = (
    "-mod=readonly",
    "-trimpath",
    "-buildvcs=false",
    "-ldflags=-buildid=",
)
_GO_RECEIPT_COMMANDS = (
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
    ("go", "build", *_GO_BUILD_FLAGS, "./cmd/adapter"),
    ("go", "build", *_GO_BUILD_FLAGS, "./cmd/server"),
)


@pytest.fixture(scope="session")
def typescript_fastify_harness() -> Iterator[TypeScriptFastifyHarness]:
    adapter_source_before = typescript_fastify_adapter_manifest(
        ADAPTER_SOURCE_ROOT
    )
    fixture_source_before = typescript_fastify_fixture_manifest(
        FIXTURE_SOURCE_ROOT
    )
    with tempfile.TemporaryDirectory(
        prefix="ucf-typescript-fastify-harness-"
    ) as temporary:
        workspace = Path(temporary).resolve(strict=True)
        if workspace.is_relative_to(PROJECT_ROOT):
            pytest.fail("TypeScript adapter build workspace is inside checkout")
        adapter_root = workspace / "adapter"
        package_test_fixture = workspace / "package-test-fixture"
        copied_adapter = copy_typescript_fastify_adapter(
            ADAPTER_SOURCE_ROOT,
            adapter_root,
        )
        copied_fixture = copy_typescript_fastify_fixture(
            FIXTURE_SOURCE_ROOT,
            package_test_fixture,
        )

        node_version = _run_observable(
            _BUILD_COMMANDS[0],
            cwd=adapter_root,
        ).strip()
        npm_version = _run_observable(
            _BUILD_COMMANDS[1],
            cwd=adapter_root,
        ).strip()
        if node_version != "v22.22.3":
            pytest.fail(
                "TypeScript adapter verification requires Node 22.22.3, "
                f"got {node_version!r}"
            )
        if npm_version != "10.9.8":
            pytest.fail(
                "TypeScript adapter requires npm 10.9.8, "
                f"got {npm_version!r}"
            )

        _run_observable(_BUILD_COMMANDS[2], cwd=adapter_root)
        _run_observable(_BUILD_COMMANDS[3], cwd=adapter_root)
        _run_observable(
            _BUILD_COMMANDS[4],
            cwd=adapter_root,
            environment={
                "UCF_TYPESCRIPT_FASTIFY_FIXTURE_ROOT": str(
                    package_test_fixture
                )
            },
        )

        adapter_entry = adapter_root / "dist" / "main.js"
        _require_adapter_entry(adapter_entry, adapter_root=adapter_root)
        assert typescript_fastify_adapter_manifest(
            ADAPTER_SOURCE_ROOT
        ) == adapter_source_before
        assert typescript_fastify_adapter_manifest(
            adapter_root
        ) == copied_adapter
        assert typescript_fastify_fixture_manifest(
            FIXTURE_SOURCE_ROOT
        ) == fixture_source_before
        assert typescript_fastify_fixture_manifest(
            package_test_fixture
        ) == copied_fixture

        yield TypeScriptFastifyHarness(
            adapter_root=adapter_root,
            adapter_entry=adapter_entry,
            adapter_source_manifest=copied_adapter,
            fixture_source_root=FIXTURE_SOURCE_ROOT,
            fixture_source_manifest=fixture_source_before,
            build_receipt=AdapterBuildReceipt(
                node_version=node_version,
                npm_version=npm_version,
                commands=_BUILD_COMMANDS,
            ),
        )

        assert typescript_fastify_adapter_manifest(
            ADAPTER_SOURCE_ROOT
        ) == adapter_source_before
        assert typescript_fastify_adapter_manifest(
            adapter_root
        ) == copied_adapter
        assert typescript_fastify_fixture_manifest(
            FIXTURE_SOURCE_ROOT
        ) == fixture_source_before
        assert typescript_fastify_fixture_manifest(
            package_test_fixture
        ) == copied_fixture


@pytest.fixture(scope="session")
def go_stdlib_harness() -> Iterator[GoStdlibHarness]:
    adapter_source_before = go_stdlib_adapter_manifest(
        GO_ADAPTER_SOURCE_ROOT
    )
    fixture_source_before = go_stdlib_fixture_manifest(
        GO_FIXTURE_SOURCE_ROOT
    )
    go_bin = resolve_go_stdlib_binary()

    with tempfile.TemporaryDirectory(
        prefix="ucf-go-stdlib-harness-"
    ) as temporary:
        workspace = Path(temporary).resolve(strict=True)
        if workspace.is_relative_to(PROJECT_ROOT):
            pytest.fail("Go adapter build workspace is inside checkout")

        adapter_a = workspace / "adapter-a"
        adapter_b = workspace / "adapter-b"
        fixture_a = workspace / "fixture-a"
        fixture_b = workspace / "fixture-b"
        copied_adapter = copy_go_stdlib_adapter(
            GO_ADAPTER_SOURCE_ROOT,
            adapter_a,
        )
        assert (
            copy_go_stdlib_adapter(GO_ADAPTER_SOURCE_ROOT, adapter_b)
            == copied_adapter
        )
        copied_fixture = copy_go_stdlib_fixture(
            GO_FIXTURE_SOURCE_ROOT,
            fixture_a,
        )
        assert (
            copy_go_stdlib_fixture(GO_FIXTURE_SOURCE_ROOT, fixture_b)
            == copied_fixture
        )

        environment_a = _go_environment(workspace / "go-work-a")
        environment_b = _go_environment(workspace / "go-work-b")
        go_version = GO_STDLIB_VERSION_OUTPUT

        for module_root in (adapter_a, fixture_a):
            _run_observable(
                (str(go_bin), "mod", "tidy", "-diff"),
                cwd=module_root,
                environment=environment_a,
            )
            _run_observable(
                (str(go_bin), "mod", "verify"),
                cwd=module_root,
                environment=environment_a,
            )
            _run_observable(
                (
                    str(go_bin),
                    "list",
                    "-mod=readonly",
                    "-m",
                    "all",
                ),
                cwd=module_root,
                environment=environment_a,
            )
            _run_observable(
                (str(go_bin), "vet", "-mod=readonly", "./..."),
                cwd=module_root,
                environment=environment_a,
            )
            _run_observable(
                (
                    str(go_bin),
                    "test",
                    "-count=1",
                    "-mod=readonly",
                    "-trimpath",
                    "-buildvcs=false",
                    "./...",
                ),
                cwd=module_root,
                environment=environment_a,
            )

        output_a = workspace / "out-a"
        output_b = workspace / "out-b"
        output_a.mkdir()
        output_b.mkdir()
        adapter_entry_a = output_a / "ucf-go-stdlib-adapter"
        adapter_entry_b = output_b / "ucf-go-stdlib-adapter"
        fixture_entry_a = output_a / "legacy-quote-server"
        fixture_entry_b = output_b / "legacy-quote-server"
        _build_go_binary(
            go_bin,
            module_root=adapter_a,
            target="./cmd/adapter",
            output=adapter_entry_a,
            environment=environment_a,
        )
        _build_go_binary(
            go_bin,
            module_root=adapter_b,
            target="./cmd/adapter",
            output=adapter_entry_b,
            environment=environment_b,
        )
        _build_go_binary(
            go_bin,
            module_root=fixture_a,
            target="./cmd/server",
            output=fixture_entry_a,
            environment=environment_a,
        )
        _build_go_binary(
            go_bin,
            module_root=fixture_b,
            target="./cmd/server",
            output=fixture_entry_b,
            environment=environment_b,
        )
        if adapter_entry_a.read_bytes() != adapter_entry_b.read_bytes():
            pytest.fail("Go adapter builds are not byte-identical")
        if fixture_entry_a.read_bytes() != fixture_entry_b.read_bytes():
            pytest.fail("Go fixture builds are not byte-identical")

        for entry in (
            adapter_entry_a,
            adapter_entry_b,
            fixture_entry_a,
            fixture_entry_b,
        ):
            _require_regular_executable(entry, root=workspace)
            _run_observable(
                (str(go_bin), "version", "-m", str(entry)),
                cwd=workspace,
                environment=environment_a,
            )

        assert go_stdlib_adapter_manifest(
            GO_ADAPTER_SOURCE_ROOT
        ) == adapter_source_before
        assert go_stdlib_adapter_manifest(adapter_a) == copied_adapter
        assert go_stdlib_adapter_manifest(adapter_b) == copied_adapter
        assert go_stdlib_fixture_manifest(
            GO_FIXTURE_SOURCE_ROOT
        ) == fixture_source_before
        assert go_stdlib_fixture_manifest(fixture_a) == copied_fixture
        assert go_stdlib_fixture_manifest(fixture_b) == copied_fixture

        yield GoStdlibHarness(
            adapter_root=adapter_a,
            adapter_entry=adapter_entry_a,
            adapter_source_manifest=copied_adapter,
            fixture_build_root=fixture_a,
            fixture_entry=fixture_entry_a,
            fixture_source_root=GO_FIXTURE_SOURCE_ROOT,
            fixture_source_manifest=fixture_source_before,
            build_receipt=GoBuildReceipt(
                go_version=go_version.strip(),
                environment=tuple(
                    sorted(
                        (
                            key,
                            environment_a[key],
                        )
                        for key in (
                            "CGO_ENABLED",
                            "GOARCH",
                            "GOAMD64",
                            "GOENV",
                            "GOOS",
                            "GOTOOLCHAIN",
                            "GOWORK",
                            "GOPROXY",
                            "GOSUMDB",
                            "GOTELEMETRY",
                        )
                    )
                ),
                commands=_GO_RECEIPT_COMMANDS,
                adapter_sha256=_sha256(adapter_entry_a),
                adapter_size=adapter_entry_a.stat().st_size,
                fixture_sha256=_sha256(fixture_entry_a),
                fixture_size=fixture_entry_a.stat().st_size,
            ),
        )

        assert go_stdlib_adapter_manifest(
            GO_ADAPTER_SOURCE_ROOT
        ) == adapter_source_before
        assert go_stdlib_adapter_manifest(adapter_a) == copied_adapter
        assert go_stdlib_adapter_manifest(adapter_b) == copied_adapter
        assert go_stdlib_fixture_manifest(
            GO_FIXTURE_SOURCE_ROOT
        ) == fixture_source_before
        assert go_stdlib_fixture_manifest(fixture_a) == copied_fixture
        assert go_stdlib_fixture_manifest(fixture_b) == copied_fixture


@pytest.fixture(scope="session")
def go_stdlib_platform_harness(
    go_stdlib_harness: GoStdlibHarness,
) -> Iterator[GoStdlibPlatformHarness]:
    source_before = go_stdlib_platform_manifest(GO_PLATFORM_SOURCE_ROOT)
    if (
        go_stdlib_platform_source_revision(source_before)
        != GO_STDLIB_PLATFORM_SOURCE_REVISION
    ):
        pytest.fail("Go platform fixture source revision is not exact")
    go_bin = resolve_go_stdlib_binary()

    with tempfile.TemporaryDirectory(
        prefix="ucf-go-stdlib-platform-harness-"
    ) as temporary:
        workspace = Path(temporary).resolve(strict=True)
        if workspace.is_relative_to(PROJECT_ROOT):
            pytest.fail("Go platform build workspace is inside checkout")

        platform_a = workspace / "platform-a"
        platform_b = workspace / "platform-b"
        copied = copy_go_stdlib_platform_fixture(
            GO_PLATFORM_SOURCE_ROOT,
            platform_a,
        )
        assert (
            copy_go_stdlib_platform_fixture(
                GO_PLATFORM_SOURCE_ROOT,
                platform_b,
            )
            == copied
        )

        environment_a = _go_environment(workspace / "go-work-a")
        environment_b = _go_environment(workspace / "go-work-b")
        commands = GO_STDLIB_PLATFORM_BUILD_COMMANDS
        for command in commands[:5]:
            output = _run_observable(
                (str(go_bin), *command[1:]),
                cwd=platform_a,
                environment=environment_a,
            )
            if command[1:4] == ("list", "-mod=readonly", "-m") and (
                output != "example.com/legacyplatforms\n"
            ):
                pytest.fail("Go platform module list is not exact")

        output_a = workspace / "out-a"
        output_b = workspace / "out-b"
        output_a.mkdir()
        output_b.mkdir()
        platform_entry_a = output_a / "legacy-platforms"
        platform_entry_b = output_b / "legacy-platforms"
        if GO_STDLIB_PLATFORM_BUILD_FLAGS != _GO_BUILD_FLAGS:
            pytest.fail("Go platform build flags differ from the Go harness")
        _build_go_binary(
            go_bin,
            module_root=platform_a,
            target="./cmd/platform",
            output=platform_entry_a,
            environment=environment_a,
        )
        _build_go_binary(
            go_bin,
            module_root=platform_b,
            target="./cmd/platform",
            output=platform_entry_b,
            environment=environment_b,
        )
        if platform_entry_a.read_bytes() != platform_entry_b.read_bytes():
            pytest.fail("Go platform builds are not byte-identical")
        if _sha256(platform_entry_a) != GO_STDLIB_PLATFORM_BINARY_SHA256:
            pytest.fail("Go platform binary digest is not exact")

        metadata_a = _run_observable(
            (str(go_bin), "version", "-m", str(platform_entry_a)),
            cwd=workspace,
            environment=environment_a,
        )
        metadata_b = _run_observable(
            (str(go_bin), "version", "-m", str(platform_entry_b)),
            cwd=workspace,
            environment=environment_b,
        )
        build_metadata = validate_go_stdlib_platform_build_metadata(
            metadata_a,
            executable=platform_entry_a,
        )
        if (
            validate_go_stdlib_platform_build_metadata(
                metadata_b,
                executable=platform_entry_b,
            )
            != build_metadata
        ):
            pytest.fail("Go platform build metadata is not reproducible")

        for entry in (platform_entry_a, platform_entry_b):
            _require_regular_executable(entry, root=workspace)

        assert (
            go_stdlib_platform_manifest(GO_PLATFORM_SOURCE_ROOT)
            == source_before
        )
        assert go_stdlib_platform_manifest(platform_a) == copied
        assert go_stdlib_platform_manifest(platform_b) == copied

        yield GoStdlibPlatformHarness(
            adapter_entry=go_stdlib_harness.adapter_entry,
            platform_build_root=platform_a,
            platform_entry=platform_entry_a,
            reproducible_platform_entry=platform_entry_b,
            platform_source_root=GO_PLATFORM_SOURCE_ROOT,
            platform_source_manifest=source_before,
            build_receipt=GoStdlibPlatformBuildReceipt(
                go_version=GO_STDLIB_VERSION_OUTPUT.strip(),
                environment=tuple(
                    sorted(
                        (key, environment_a[key])
                        for key in (
                            "CGO_ENABLED",
                            "GOARCH",
                            "GOAMD64",
                            "GOENV",
                            "GOOS",
                            "GOTOOLCHAIN",
                            "GOWORK",
                            "GOPROXY",
                            "GOSUMDB",
                            "GOTELEMETRY",
                        )
                    )
                ),
                commands=commands,
                build_metadata=build_metadata,
                platform_sha256=_sha256(platform_entry_a),
                platform_size=platform_entry_a.stat().st_size,
            ),
        )

        assert (
            go_stdlib_platform_manifest(GO_PLATFORM_SOURCE_ROOT)
            == source_before
        )
        assert go_stdlib_platform_manifest(platform_a) == copied
        assert go_stdlib_platform_manifest(platform_b) == copied


def _run_observable(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> str:
    print(f"$ {cwd} $ {shlex.join(command)}", flush=True)
    child_environment = os.environ.copy()
    if environment is not None:
        child_environment.update(environment)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=child_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    output = []
    for line in process.stdout:
        print(line, end="", flush=True)
        output.append(line)
    return_code = process.wait()
    if return_code != 0:
        pytest.fail(
            f"external adapter command failed with exit {return_code}: "
            f"{shlex.join(command)}"
        )
    return "".join(output)


def _require_adapter_entry(entry: Path, *, adapter_root: Path) -> None:
    try:
        metadata = entry.lstat()
        resolved = entry.resolve(strict=True)
    except OSError as error:
        pytest.fail(f"external adapter entry is unavailable: {error}")
    if not stat.S_ISREG(metadata.st_mode):
        pytest.fail("external adapter entry must be one regular file")
    if not resolved.is_relative_to(adapter_root.resolve(strict=True)):
        pytest.fail("external adapter entry escaped the build root")
    if not entry.read_bytes().startswith(b"#!/usr/bin/env node\n"):
        pytest.fail("external adapter entry is missing the Node shebang")


def _go_environment(workspace: Path) -> dict[str, str]:
    paths = {
        "GOCACHE": workspace / "cache",
        "GOMODCACHE": workspace / "modcache",
        "GOPATH": workspace / "gopath",
        "GOTMPDIR": workspace / "tmp",
    }
    for path in paths.values():
        path.mkdir(parents=True)
    environment = os.environ.copy()
    environment.update(
        {
            "CGO_ENABLED": "0",
            "GOARCH": "amd64",
            "GOAMD64": "v1",
            "GOENV": "off",
            "GOEXPERIMENT": "",
            "GOFLAGS": "",
            "GOOS": "linux",
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "GOTELEMETRY": "off",
            **{key: str(path) for key, path in paths.items()},
        }
    )
    return environment


def _build_go_binary(
    go_bin: Path,
    *,
    module_root: Path,
    target: str,
    output: Path,
    environment: Mapping[str, str],
) -> None:
    _run_observable(
        (
            str(go_bin),
            "build",
            *_GO_BUILD_FLAGS,
            "-o",
            str(output),
            target,
        ),
        cwd=module_root,
        environment=environment,
    )


def _require_regular_executable(entry: Path, *, root: Path) -> None:
    try:
        metadata = entry.lstat()
        resolved = entry.resolve(strict=True)
    except OSError as error:
        pytest.fail(f"external Go executable is unavailable: {error}")
    if not stat.S_ISREG(metadata.st_mode):
        pytest.fail("external Go executable must be one regular file")
    if not resolved.is_relative_to(root.resolve(strict=True)):
        pytest.fail("external Go executable escaped the build root")
    if metadata.st_mode & 0o111 == 0:
        pytest.fail("external Go executable has no execute bit")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
