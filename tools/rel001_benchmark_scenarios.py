"""Prepare and execute the four REL-001 component scenarios externally."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from ucf.adapter_conformance import (
    canonical_conformance_json,
    load_conformance_manifest,
    parse_conformance_report_json,
    validate_report_against_manifest,
)

if __package__:
    from .go_stdlib_adapter_contract import (
        copy_go_stdlib_adapter,
        copy_go_stdlib_fixture,
        go_stdlib_adapter_manifest,
        go_stdlib_fixture_manifest,
    )
    from .go_stdlib_platform_contract import (
        GO_STDLIB_PLATFORM_BINARY_SHA256,
        GO_STDLIB_PLATFORM_BUILD_FLAGS,
        GO_STDLIB_PLATFORM_SOURCE_REVISION,
        copy_go_stdlib_platform_fixture,
        go_stdlib_platform_manifest,
        go_stdlib_platform_source_revision,
    )
    from .go_stdlib_toolchain import (
        GO_STDLIB_VERSION_OUTPUT,
        resolve_go_stdlib_binary,
    )
    from .typescript_fastify_adapter_contract import (
        copy_typescript_fastify_adapter,
        copy_typescript_fastify_fixture,
        typescript_fastify_adapter_manifest,
        typescript_fastify_fixture_manifest,
    )
else:
    from go_stdlib_adapter_contract import (
        copy_go_stdlib_adapter,
        copy_go_stdlib_fixture,
        go_stdlib_adapter_manifest,
        go_stdlib_fixture_manifest,
    )
    from go_stdlib_platform_contract import (
        GO_STDLIB_PLATFORM_BINARY_SHA256,
        GO_STDLIB_PLATFORM_BUILD_FLAGS,
        GO_STDLIB_PLATFORM_SOURCE_REVISION,
        copy_go_stdlib_platform_fixture,
        go_stdlib_platform_manifest,
        go_stdlib_platform_source_revision,
    )
    from go_stdlib_toolchain import (
        GO_STDLIB_VERSION_OUTPUT,
        resolve_go_stdlib_binary,
    )
    from typescript_fastify_adapter_contract import (
        copy_typescript_fastify_adapter,
        copy_typescript_fastify_fixture,
        typescript_fastify_adapter_manifest,
        typescript_fastify_fixture_manifest,
    )


_COMMAND_TIMEOUT_SECONDS = 600.0
_MAX_COMMAND_OUTPUT_BYTES = 32 * 1024 * 1024
_COMMAND_OUTPUT_CHUNK_BYTES = 64 * 1024
_MAX_LANE_EVIDENCE_BYTES = 16 * 1024 * 1024
_MAX_COMPILER_INPUT_BYTES = 64 * 1024 * 1024
_MAX_COMPILED_REPORT_BYTES = 4 * 1024 * 1024
_GO_BUILD_FLAGS = (
    "-mod=readonly",
    "-trimpath",
    "-buildvcs=false",
    "-ldflags=-buildid=",
)
_GENERATED_TYPESCRIPT_ROOTS = (
    ".artifacts",
    ".npm",
    "dist",
    "node_modules",
)
_DRIVER_NAMES = {
    "python": "installed_python_legacy_quote_smoke.py",
    "typescript_fastify": "installed_typescript_fastify_smoke.py",
    "go_http": "installed_go_stdlib_smoke.py",
    "go_platform": "installed_go_stdlib_platform_smoke.py",
}


class ScenarioFailure(ValueError):
    """One external benchmark setup or execution failure."""


def collect_benchmark_report(
    repository_root: Path,
    *,
    repetitions: int,
) -> dict[str, object]:
    """Run clean installed scenarios and compile their report under the wheel."""

    root = repository_root.resolve(strict=True)
    if repetitions < 3:
        raise ScenarioFailure("REL-001 requires at least three repetitions")
    host_platform = {
        "system": platform.system(),
        "architecture": platform.machine(),
    }
    if host_platform != {"system": "Linux", "architecture": "x86_64"}:
        raise ScenarioFailure("REL-001 requires exact Linux/x86_64")
    sources = _SourceRoots.from_repository(root)
    before = sources.manifests()
    with tempfile.TemporaryDirectory(prefix="ucf-rel001-benchmark-") as temporary:
        workspace = Path(temporary).resolve(strict=True)
        if workspace.is_relative_to(root):
            raise ScenarioFailure("benchmark workspace must be outside checkout")
        installed = _prepare_installed_wheel(root, workspace)
        drivers = _copy_drivers(root, workspace)
        compiler = _copy_compiler(root, workspace)
        python_adapter = _copy_python_adapter(root, workspace)
        typescript = _prepare_typescript(root, workspace)
        go = _prepare_go(root, workspace)
        conformance = _run_conformance(
            workspace=workspace,
            installed=installed,
            python_adapter=python_adapter,
            typescript_adapter=typescript.adapter_entry,
            go_adapter=go.adapter_entry,
        )
        lane_runs: dict[str, list[dict[str, object]]] = {
            lane: [] for lane in _DRIVER_NAMES
        }
        runtime: dict[tuple[str, str], list[int]] = {}
        for repetition in range(repetitions):
            repetition_root = workspace / f"run-{repetition + 1}"
            repetition_root.mkdir()
            _run_python_lane(
                lane_runs,
                runtime,
                repetition_root=repetition_root,
                driver=drivers["python"],
                python=installed.python,
                adapter=python_adapter,
                source=sources.python_fixture,
            )
            _run_typescript_lane(
                lane_runs,
                runtime,
                repetition_root=repetition_root,
                driver=drivers["typescript_fastify"],
                python=installed.python,
                adapter=typescript.adapter_entry,
                source=sources.typescript_fixture,
            )
            _run_go_http_lane(
                lane_runs,
                runtime,
                repetition_root=repetition_root,
                driver=drivers["go_http"],
                python=installed.python,
                adapter=go.adapter_entry,
                executable=go.http_entry,
                source=sources.go_http_fixture,
                environment=go.environment,
                go_bin=go.go_bin,
            )
            _run_go_platform_lane(
                lane_runs,
                runtime,
                repetition_root=repetition_root,
                driver=drivers["go_platform"],
                python=installed.python,
                adapter=go.adapter_entry,
                executable=go.platform_entry,
                source=sources.go_platform_fixture,
                environment=go.environment,
                go_bin=go.go_bin,
            )
        after = sources.manifests()
        if after != before:
            raise ScenarioFailure("repository benchmark sources changed")
        compiler_input = {
            "kind": "rel001_benchmark_compilation_input",
            "input_version": "1.0.0",
            "lane_runs": lane_runs,
            "runtime_samples": [
                {"lane": lane, "phase": phase, "samples": samples}
                for (lane, phase), samples in sorted(runtime.items())
            ],
            "wheel_sha256": _sha256(installed.wheel),
            "runtime_lock_sha256": installed.runtime_lock_sha256,
            "installed_distributions": installed.distributions,
            "host_platform": host_platform,
            "adapter_artifact_digests": {
                "python": _regular_tree_digest(python_adapter.parent),
                "typescript_fastify": _sha256(typescript.adapter_entry),
                "go": _sha256(go.adapter_entry),
            },
            "driver_artifact_digests": {
                lane: _sha256(path) for lane, path in drivers.items()
            },
            "benchmark_tool_digests": {
                "compiler": _sha256(root / "tools" / "rel001_benchmark.py"),
                "scenarios": _sha256(
                    root / "tools" / "rel001_benchmark_scenarios.py"
                ),
                "go_adapter_contract": _sha256(
                    root / "tools" / "go_stdlib_adapter_contract.py"
                ),
                "go_platform_contract": _sha256(
                    root / "tools" / "go_stdlib_platform_contract.py"
                ),
                "go_toolchain": _sha256(
                    root / "tools" / "go_stdlib_toolchain.py"
                ),
                "typescript_contract": _sha256(
                    root / "tools" / "typescript_fastify_adapter_contract.py"
                ),
            },
            "conformance_report_digests": conformance,
            "toolchains": {
                "node": typescript.node_version,
                "npm": typescript.npm_version,
                "go": GO_STDLIB_VERSION_OUTPUT.removeprefix("go version ").strip(),
            },
        }
        return _compile_installed_report(
            installed=installed,
            compiler=compiler,
            workspace=workspace,
            compiler_input=compiler_input,
        )


class _SourceRoots:
    def __init__(
        self,
        *,
        python_fixture: Path,
        typescript_adapter: Path,
        typescript_fixture: Path,
        go_adapter: Path,
        go_http_fixture: Path,
        go_platform_fixture: Path,
    ) -> None:
        self.python_fixture = python_fixture
        self.typescript_adapter = typescript_adapter
        self.typescript_fixture = typescript_fixture
        self.go_adapter = go_adapter
        self.go_http_fixture = go_http_fixture
        self.go_platform_fixture = go_platform_fixture

    @classmethod
    def from_repository(cls, root: Path) -> _SourceRoots:
        brownfield = root / "tests" / "fixtures" / "brownfield"
        return cls(
            python_fixture=(brownfield / "python_legacy_quote").resolve(strict=True),
            typescript_adapter=(root / "adapters" / "typescript-fastify").resolve(
                strict=True
            ),
            typescript_fixture=(brownfield / "typescript_fastify_legacy_quote").resolve(
                strict=True
            ),
            go_adapter=(root / "adapters" / "go-stdlib").resolve(strict=True),
            go_http_fixture=(brownfield / "go_stdlib_legacy_quote").resolve(
                strict=True
            ),
            go_platform_fixture=(brownfield / "go_stdlib_legacy_platforms").resolve(
                strict=True
            ),
        )

    def manifests(self) -> dict[str, object]:
        return {
            "python": _regular_tree_manifest(self.python_fixture),
            "typescript_adapter": typescript_fastify_adapter_manifest(
                self.typescript_adapter
            ),
            "typescript": typescript_fastify_fixture_manifest(self.typescript_fixture),
            "go_adapter": go_stdlib_adapter_manifest(self.go_adapter),
            "go_http": go_stdlib_fixture_manifest(self.go_http_fixture),
            "go_platform": go_stdlib_platform_manifest(self.go_platform_fixture),
        }


class _Installed:
    def __init__(
        self,
        python: Path,
        ucf: Path,
        wheel: Path,
        *,
        runtime_lock_sha256: str,
        distributions: Mapping[str, str],
    ) -> None:
        self.python = python
        self.ucf = ucf
        self.wheel = wheel
        self.runtime_lock_sha256 = runtime_lock_sha256
        self.distributions = dict(distributions)


class _TypeScript:
    def __init__(
        self,
        adapter_entry: Path,
        node_version: str,
        npm_version: str,
    ) -> None:
        self.adapter_entry = adapter_entry
        self.node_version = node_version
        self.npm_version = npm_version


class _Go:
    def __init__(
        self,
        *,
        go_bin: Path,
        adapter_entry: Path,
        http_entry: Path,
        platform_entry: Path,
        environment: Mapping[str, str],
    ) -> None:
        self.go_bin = go_bin
        self.adapter_entry = adapter_entry
        self.http_entry = http_entry
        self.platform_entry = platform_entry
        self.environment = dict(environment)


def _prepare_installed_wheel(root: Path, workspace: Path) -> _Installed:
    uv = shutil.which("uv")
    if uv is None:
        raise ScenarioFailure("uv is unavailable")
    wheels = workspace / "wheels"
    wheels.mkdir()
    _run_observable((uv, "build", "--wheel", "--out-dir", str(wheels)), cwd=root)
    candidates = tuple(wheels.glob("*.whl"))
    if len(candidates) != 1:
        raise ScenarioFailure("wheel build did not produce exactly one wheel")
    environment = workspace / "installed"
    _run_observable(
        (uv, "venv", "--python", sys.executable, str(environment)),
        cwd=workspace,
    )
    python = environment / "bin" / "python"
    ucf = environment / "bin" / "ucf"
    runtime_lock = workspace / "runtime-requirements.txt"
    _run_observable(
        (
            uv,
            "export",
            "--quiet",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--output-file",
            str(runtime_lock),
        ),
        cwd=root,
    )
    _run_observable(
        (
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--require-hashes",
            "--requirements",
            str(runtime_lock),
        ),
        cwd=workspace,
    )
    _run_observable(
        (
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            str(candidates[0]),
        ),
        cwd=workspace,
    )
    _require_executable(python, allow_symlink=True)
    _require_executable(ucf)
    distributions = _installed_distributions(python, workspace)
    return _Installed(
        python,
        ucf,
        candidates[0],
        runtime_lock_sha256=_sha256(runtime_lock),
        distributions=distributions,
    )


def _installed_distributions(python: Path, workspace: Path) -> dict[str, str]:
    script = (
        "import importlib.metadata,json;"
        "items=[(d.metadata['Name'].lower().replace('_','-'),d.version) "
        "for d in importlib.metadata.distributions()];"
        "assert len(items)==len(dict(items));"
        "print(json.dumps(dict(sorted(items)),sort_keys=True,separators=(',',':')))"
    )
    payload = _run_observable(
        (str(python), "-I", "-c", script),
        cwd=workspace,
    )
    decoded = json.loads(payload)
    if not isinstance(decoded, dict) or decoded.get("ucf") is None:
        raise ScenarioFailure("installed distribution inventory is incomplete")
    if any(
        not isinstance(name, str)
        or not name
        or not isinstance(version, str)
        or not version
        for name, version in decoded.items()
    ):
        raise ScenarioFailure("installed distribution inventory is invalid")
    return decoded


def _copy_drivers(root: Path, workspace: Path) -> dict[str, Path]:
    destination = workspace / "drivers"
    destination.mkdir()
    drivers = {}
    for lane, name in _DRIVER_NAMES.items():
        source = root / "tools" / name
        target = destination / name
        shutil.copy2(source, target)
        if target.read_bytes() != source.read_bytes():
            raise ScenarioFailure(f"copied driver differs: {name}")
        drivers[lane] = target.resolve(strict=True)
    return drivers


def _copy_compiler(root: Path, workspace: Path) -> Path:
    source = root / "tools" / "rel001_benchmark.py"
    destination = workspace / "compiler"
    destination.mkdir()
    target = destination / source.name
    shutil.copy2(source, target)
    if target.read_bytes() != source.read_bytes():
        raise ScenarioFailure("copied benchmark compiler differs")
    return target.resolve(strict=True)


def _compile_installed_report(
    *,
    installed: _Installed,
    compiler: Path,
    workspace: Path,
    compiler_input: Mapping[str, object],
) -> dict[str, object]:
    content = _canonical_json_bytes(compiler_input)
    if len(content) > _MAX_COMPILER_INPUT_BYTES:
        raise ScenarioFailure("benchmark compiler input exceeds the byte budget")
    input_path = workspace / "compiler-input.json"
    with input_path.open("xb") as stream:
        stream.write(content)
    output_path = workspace / "compiled-report.json"
    _run_observable(
        (
            str(installed.python),
            "-I",
            str(compiler),
            "compile-evidence",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ),
        cwd=workspace,
    )
    if output_path.is_symlink() or not output_path.is_file():
        raise ScenarioFailure("installed compiler did not publish a regular report")
    if output_path.stat().st_size > _MAX_COMPILED_REPORT_BYTES:
        raise ScenarioFailure("installed compiler report exceeds the byte budget")
    report_content = output_path.read_bytes()
    try:
        report = json.loads(report_content)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ScenarioFailure("installed compiler report is invalid JSON") from error
    if report_content != _canonical_json_bytes(report):
        raise ScenarioFailure("installed compiler report is noncanonical")
    return report


def _copy_python_adapter(root: Path, workspace: Path) -> Path:
    source = root / "tests" / "fixtures" / "adapters"
    destination = workspace / "python-adapter"
    destination.mkdir()
    adapter = destination / "inventory_reference_adapter.py"
    shutil.copy2(source / adapter.name, adapter)
    shutil.copytree(
        source / "inventory_reference",
        destination / "inventory_reference",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return adapter.resolve(strict=True)


def _prepare_typescript(root: Path, workspace: Path) -> _TypeScript:
    source_adapter = root / "adapters" / "typescript-fastify"
    source_fixture = (
        root / "tests" / "fixtures" / "brownfield" / "typescript_fastify_legacy_quote"
    )
    adapter = workspace / "typescript-adapter"
    package_fixture = workspace / "typescript-package-fixture"
    copied_adapter = copy_typescript_fastify_adapter(source_adapter, adapter)
    copied_fixture = copy_typescript_fastify_fixture(source_fixture, package_fixture)
    node = _run_observable(("node", "--version"), cwd=adapter).strip()
    npm = _run_observable(("npm", "--version"), cwd=adapter).strip()
    if node != "v22.22.3" or npm != "10.9.8":
        raise ScenarioFailure(
            f"TypeScript toolchain mismatch: node={node!r}, npm={npm!r}"
        )
    environment = {
        **os.environ,
        "UCF_TYPESCRIPT_FASTIFY_FIXTURE_ROOT": str(package_fixture),
    }
    for command in (
        ("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"),
        ("npm", "run", "build"),
        ("npm", "test"),
    ):
        _run_observable(command, cwd=adapter, environment=environment)
    if (
        typescript_fastify_adapter_manifest(adapter) != copied_adapter
        or typescript_fastify_fixture_manifest(package_fixture) != copied_fixture
    ):
        raise ScenarioFailure("TypeScript build changed accepted source")
    entry = (adapter / "dist" / "main.js").resolve(strict=True)
    entry.chmod(entry.stat().st_mode | stat.S_IXUSR)
    _require_executable(entry)
    return _TypeScript(entry, node, npm)


def _prepare_go(root: Path, workspace: Path) -> _Go:
    go_bin = resolve_go_stdlib_binary()
    source_root = root / "tests" / "fixtures" / "brownfield"
    adapter = workspace / "go-adapter"
    http = workspace / "go-http-build"
    platform_root = workspace / "go-platform-build"
    copy_go_stdlib_adapter(root / "adapters" / "go-stdlib", adapter)
    copy_go_stdlib_fixture(source_root / "go_stdlib_legacy_quote", http)
    platform_manifest = copy_go_stdlib_platform_fixture(
        source_root / "go_stdlib_legacy_platforms", platform_root
    )
    if (
        go_stdlib_platform_source_revision(platform_manifest)
        != GO_STDLIB_PLATFORM_SOURCE_REVISION
        or tuple(GO_STDLIB_PLATFORM_BUILD_FLAGS) != _GO_BUILD_FLAGS
    ):
        raise ScenarioFailure("Go platform source/build profile differs")
    environment = _go_environment(workspace / "go-work")
    for module in (adapter, http, platform_root):
        for command in (
            (str(go_bin), "mod", "tidy", "-diff"),
            (str(go_bin), "mod", "verify"),
            (str(go_bin), "list", "-mod=readonly", "-m", "all"),
            (str(go_bin), "vet", "-mod=readonly", "./..."),
            (
                str(go_bin),
                "test",
                "-count=1",
                "-mod=readonly",
                "-trimpath",
                "-buildvcs=false",
                "./...",
            ),
        ):
            _run_observable(command, cwd=module, environment=environment)
    binaries = workspace / "go-binaries"
    binaries.mkdir()
    adapter_entry = binaries / "ucf-go-stdlib-adapter"
    http_entry = binaries / "legacy-quote-server"
    platform_entry = binaries / "legacy-platforms"
    for module, target, output in (
        (adapter, "./cmd/adapter", adapter_entry),
        (http, "./cmd/server", http_entry),
        (platform_root, "./cmd/platform", platform_entry),
    ):
        _run_observable(
            (
                str(go_bin),
                "build",
                *_GO_BUILD_FLAGS,
                "-o",
                str(output),
                target,
            ),
            cwd=module,
            environment=environment,
        )
        _require_executable(output)
    if _sha256(platform_entry) != GO_STDLIB_PLATFORM_BINARY_SHA256:
        raise ScenarioFailure("Go platform binary is not reproducible")
    return _Go(
        go_bin=go_bin,
        adapter_entry=adapter_entry.resolve(strict=True),
        http_entry=http_entry.resolve(strict=True),
        platform_entry=platform_entry.resolve(strict=True),
        environment=environment,
    )


def _run_conformance(
    *,
    workspace: Path,
    installed: _Installed,
    python_adapter: Path,
    typescript_adapter: Path,
    go_adapter: Path,
) -> dict[str, str]:
    reports = {}
    commands: dict[str, Sequence[str]] = {
        "python": (
            str(installed.python),
            "-B",
            "-X",
            "utf8",
            str(python_adapter),
            "--conformance",
        ),
        "typescript_fastify": (str(typescript_adapter), "--conformance"),
        "go": (str(go_adapter), "--conformance"),
    }
    for ecosystem, adapter_command in commands.items():
        report = workspace / f"conformance-{ecosystem}.json"
        _run_observable(
            (
                str(installed.ucf),
                "adapter",
                "conformance",
                "--cwd",
                str(workspace),
                "--report",
                str(report),
                "--",
                *adapter_command,
            ),
            cwd=workspace,
        )
        content = report.read_bytes()
        parsed = parse_conformance_report_json(content)
        manifest = load_conformance_manifest()
        validate_report_against_manifest(parsed, manifest)
        canonical = canonical_conformance_json(parsed)
        if (
            content != canonical
            or parsed.status.value != "conformant"
            or any(case.status.value != "passed" for case in parsed.cases)
        ):
            raise ScenarioFailure(f"{ecosystem} conformance report differs")
        reports[ecosystem] = hashlib.sha256(canonical).hexdigest()
    return reports


def _run_python_lane(
    lane_runs,
    runtime,
    *,
    repetition_root: Path,
    driver: Path,
    python: Path,
    adapter: Path,
    source: Path,
) -> None:
    lane = "python"
    fixture = repetition_root / "python-fixture"
    _timed(runtime, lane, "copy_source", _copy_python_fixture, source, fixture)
    before = _regular_tree_manifest(fixture)
    environment = {**os.environ, "PYTHONPATH": str(fixture / "src")}
    native = (str(python), "-B", "tests/behavior_checks.py")
    _timed(
        runtime,
        lane,
        "native_pre",
        _run_observable,
        native,
        cwd=fixture,
        environment=environment,
    )
    output = repetition_root / "python-evidence.json"
    _timed(
        runtime,
        lane,
        "workflow",
        _run_observable,
        (
            str(python),
            "-I",
            str(driver),
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--evidence-output",
            str(output),
        ),
        cwd=repetition_root,
    )
    _timed(
        runtime,
        lane,
        "native_post",
        _run_observable,
        native,
        cwd=fixture,
        environment=environment,
    )
    _timed(
        runtime,
        lane,
        "manifest_recheck",
        _assert_equal,
        _regular_tree_manifest(fixture),
        before,
        "Python fixture changed",
    )
    lane_runs[lane].append(_read_lane(output, lane))


def _run_typescript_lane(
    lane_runs,
    runtime,
    *,
    repetition_root: Path,
    driver: Path,
    python: Path,
    adapter: Path,
    source: Path,
) -> None:
    lane = "typescript_fastify"
    fixture = repetition_root / "typescript-fixture"
    source_manifest = typescript_fastify_fixture_manifest(source)
    _timed(
        runtime,
        lane,
        "copy_source",
        copy_typescript_fastify_fixture,
        source,
        fixture,
    )
    npm_environment = {
        **os.environ,
        "npm_config_audit": "false",
        "npm_config_fund": "false",
        "npm_config_update_notifier": "false",
    }
    _timed(
        runtime,
        lane,
        "native_pre",
        _run_typescript_native,
        fixture,
        npm_environment,
        True,
    )
    for name in _GENERATED_TYPESCRIPT_ROOTS:
        path = fixture / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            raise ScenarioFailure(f"unexpected generated TypeScript path: {name}")
    output = repetition_root / "typescript-evidence.json"
    _timed(
        runtime,
        lane,
        "workflow",
        _run_observable,
        (
            str(python),
            "-I",
            str(driver),
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--evidence-output",
            str(output),
        ),
        cwd=repetition_root,
        environment=npm_environment,
    )
    _timed(
        runtime,
        lane,
        "native_post",
        _run_typescript_native,
        fixture,
        npm_environment,
        False,
    )
    _timed(
        runtime,
        lane,
        "manifest_recheck",
        _assert_equal,
        typescript_fastify_fixture_manifest(fixture),
        source_manifest,
        "TypeScript fixture changed",
    )
    lane_runs[lane].append(_read_lane(output, lane))


def _run_go_http_lane(
    lane_runs,
    runtime,
    *,
    repetition_root: Path,
    driver: Path,
    python: Path,
    adapter: Path,
    executable: Path,
    source: Path,
    environment: Mapping[str, str],
    go_bin: Path,
) -> None:
    lane = "go_http"
    fixture = repetition_root / "go-http-fixture"
    expected = go_stdlib_fixture_manifest(source)
    _timed(
        runtime,
        lane,
        "copy_source",
        copy_go_stdlib_fixture,
        source,
        fixture,
    )
    native = (
        str(go_bin),
        "test",
        "-count=1",
        "-mod=readonly",
        "-trimpath",
        "-buildvcs=false",
        "./...",
    )
    _timed(
        runtime,
        lane,
        "native_pre",
        _run_observable,
        native,
        cwd=fixture,
        environment=environment,
    )
    output = repetition_root / "go-http-evidence.json"
    _timed(
        runtime,
        lane,
        "workflow",
        _run_observable,
        (
            str(python),
            "-I",
            str(driver),
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--fixture-executable",
            str(executable),
            "--evidence-output",
            str(output),
        ),
        cwd=repetition_root,
        environment=environment,
    )
    _timed(
        runtime,
        lane,
        "native_post",
        _run_observable,
        native,
        cwd=fixture,
        environment=environment,
    )
    _timed(
        runtime,
        lane,
        "manifest_recheck",
        _assert_equal,
        go_stdlib_fixture_manifest(fixture),
        expected,
        "Go HTTP fixture changed",
    )
    lane_runs[lane].append(_read_lane(output, lane))


def _run_go_platform_lane(
    lane_runs,
    runtime,
    *,
    repetition_root: Path,
    driver: Path,
    python: Path,
    adapter: Path,
    executable: Path,
    source: Path,
    environment: Mapping[str, str],
    go_bin: Path,
) -> None:
    lane = "go_platform"
    fixture = repetition_root / "go-platform-fixture"
    expected = go_stdlib_platform_manifest(source)
    _timed(
        runtime,
        lane,
        "copy_source",
        copy_go_stdlib_platform_fixture,
        source,
        fixture,
    )
    native = (
        str(go_bin),
        "test",
        "-count=1",
        "-mod=readonly",
        "-trimpath",
        "-buildvcs=false",
        "./...",
    )
    _timed(
        runtime,
        lane,
        "native_pre",
        _run_observable,
        native,
        cwd=fixture,
        environment=environment,
    )
    output = repetition_root / "go-platform-evidence.json"
    _timed(
        runtime,
        lane,
        "workflow",
        _run_observable,
        (
            str(python),
            "-I",
            str(driver),
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--platform-fixture-executable",
            str(executable),
            "--evidence-output",
            str(output),
        ),
        cwd=repetition_root,
        environment=environment,
    )
    _timed(
        runtime,
        lane,
        "native_post",
        _run_observable,
        native,
        cwd=fixture,
        environment=environment,
    )
    _timed(
        runtime,
        lane,
        "manifest_recheck",
        _assert_equal,
        go_stdlib_platform_manifest(fixture),
        expected,
        "Go platform fixture changed",
    )
    lane_runs[lane].append(_read_lane(output, lane))


def _run_typescript_native(
    fixture: Path,
    environment: Mapping[str, str],
    install: bool,
) -> None:
    if install:
        _run_observable(
            ("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"),
            cwd=fixture,
            environment=environment,
        )
        _run_observable(("npm", "run", "build"), cwd=fixture, environment=environment)
    _run_observable(("npm", "test"), cwd=fixture, environment=environment)


def _copy_python_fixture(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _read_lane(path: Path, expected_lane: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ScenarioFailure("lane evidence is not a regular file")
    if path.stat().st_size > _MAX_LANE_EVIDENCE_BYTES:
        raise ScenarioFailure("lane evidence exceeds the read budget")
    content = path.read_bytes()
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ScenarioFailure("lane evidence is invalid JSON") from error
    canonical = _canonical_json_bytes(payload)
    if content != canonical or payload.get("lane") != expected_lane:
        raise ScenarioFailure("lane evidence is noncanonical or misrouted")
    return payload


def _timed(runtime, lane: str, phase: str, function, *args, **kwargs):
    started = time.monotonic_ns()
    result = function(*args, **kwargs)
    elapsed = time.monotonic_ns() - started
    if elapsed <= 0:
        raise ScenarioFailure("monotonic runtime sample is not positive")
    runtime.setdefault((lane, phase), []).append(elapsed)
    return result


def _assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise ScenarioFailure(message)


def _go_environment(workspace: Path) -> dict[str, str]:
    paths = {
        "GOCACHE": workspace / "cache",
        "GOMODCACHE": workspace / "modcache",
        "GOPATH": workspace / "gopath",
        "GOTMPDIR": workspace / "tmp",
    }
    for path in paths.values():
        path.mkdir(parents=True)
    return {
        **os.environ,
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


def _run_observable(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> str:
    print(f"$ {cwd} $ {shlex.join(command)}", flush=True)
    child_environment = os.environ.copy()
    if environment is not None:
        child_environment.update(environment)
    process = subprocess.Popen(
        tuple(command),
        cwd=cwd,
        env=child_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=os.name == "posix",
    )
    assert process.stdout is not None
    chunks: list[bytes] = []
    total = 0
    output_exceeded = threading.Event()

    def read_output() -> None:
        nonlocal total
        while chunk := process.stdout.read(_COMMAND_OUTPUT_CHUNK_BYTES):
            total += len(chunk)
            if total > _MAX_COMMAND_OUTPUT_BYTES:
                output_exceeded.set()
                _terminate(process)
                return
            chunks.append(chunk)
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        return_code = process.wait(timeout=_COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _terminate(process)
        raise ScenarioFailure(
            f"external command timed out: {shlex.join(command)}"
        ) from error
    finally:
        reader.join(timeout=5.0)
        process.stdout.close()
    if reader.is_alive():
        _terminate(process)
        raise ScenarioFailure("external command output reader did not stop")
    if output_exceeded.is_set():
        raise ScenarioFailure("external command exceeded output budget")
    output = b"".join(chunks)
    if return_code != 0:
        raise ScenarioFailure(
            f"external command failed with exit {return_code}: {shlex.join(command)}"
        )
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ScenarioFailure("external command output is not UTF-8") from error


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        process.terminate()
    try:
        process.wait(timeout=1.0)
        return
    except subprocess.TimeoutExpired:
        pass
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    else:
        process.kill()
    process.wait(timeout=1.0)


def _regular_tree_manifest(root: Path) -> tuple[tuple[str, int, str], ...]:
    records = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ScenarioFailure(f"tree contains a symlink: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ScenarioFailure(f"tree contains a non-file: {relative}")
        records.append((relative, metadata.st_size, _sha256(path)))
    return tuple(records)


def _regular_tree_digest(root: Path) -> str:
    payload = "".join(
        f"{path}\t{size}\t{digest}\n"
        for path, size, digest in _regular_tree_manifest(root)
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_executable(path: Path, *, allow_symlink: bool = False) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ScenarioFailure(f"executable is unavailable: {path}") from error
    if stat.S_ISLNK(metadata.st_mode) and allow_symlink:
        try:
            metadata = path.resolve(strict=True).stat()
        except OSError as error:
            raise ScenarioFailure(
                f"executable symlink target is unavailable: {path}"
            ) from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o111 == 0:
        raise ScenarioFailure(f"path is not an executable file: {path}")
