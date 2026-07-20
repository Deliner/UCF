from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

GATE_MANIFEST_SCHEMA_VERSION = 1
SAFE_GATE_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]
    working_directory: Path = Path(".")


@dataclass(frozen=True)
class GateResult:
    gate: Gate
    returncode: int
    duration_seconds: float
    log_path: Path

    @property
    def passed(self) -> bool:
        return self.returncode == 0


AUTOMATION_TESTS = Gate(
    name="automation-tests",
    command=(
        "uv",
        "run",
        "--locked",
        "--extra",
        "dev",
        "pytest",
        "-q",
        "tests/automation",
        "--no-cov",
    ),
)
PYTHON_TESTS = Gate(
    name="python-tests",
    command=(
        "uv",
        "run",
        "--locked",
        "--extra",
        "dev",
        "--extra",
        "web",
        "pytest",
        "-q",
        "--disable-warnings",
        "--capture=tee-sys",
    ),
)
PYTHON_LINT = Gate(
    name="python-lint",
    command=(
        "uv",
        "run",
        "--locked",
        "--extra",
        "dev",
        "ruff",
        "check",
        "src",
        "tests",
        "tools",
        ".codex/hooks/stop_quality.py",
    ),
)
SPEC_VALIDATION = Gate(
    name="spec-validation",
    command=(
        "uv",
        "run",
        "--locked",
        "--extra",
        "web",
        "ucf",
        "validate",
        "specs",
    ),
)
PACKAGING_CONTRACT = Gate(
    name="packaging-contract",
    command=("uv", "run", "--locked", "python", "tools/package_contract.py"),
)
WEB_BUILD = Gate(
    name="web-build",
    command=("npm", "run", "build"),
    working_directory=Path("web"),
)
WEB_LINT = Gate(
    name="web-lint",
    command=("npm", "run", "lint"),
    working_directory=Path("web"),
)

PROFILES: dict[str, tuple[Gate, ...]] = {
    "automation": (AUTOMATION_TESTS,),
    "all": (
        AUTOMATION_TESTS,
        PYTHON_TESTS,
        PYTHON_LINT,
        SPEC_VALIDATION,
        PACKAGING_CONTRACT,
        WEB_BUILD,
        WEB_LINT,
    ),
}
PROFILE_NAMES = (*PROFILES, "affected")

PACKAGING_TOOL_INPUTS = {
    "tests/generation/_fixture_factory.py",
    "tools/generate_change_governance_schema.py",
    "tools/generate_generation_schema.py",
    "tools/go_stdlib_adapter_contract.py",
    "tools/go_stdlib_platform_contract.py",
    "tools/go_stdlib_toolchain.py",
    "tools/installed_go_stdlib_smoke.py",
    "tools/installed_go_stdlib_platform_smoke.py",
    "tools/installed_typescript_fastify_smoke.py",
    "tools/package_contract.py",
    "tools/quality_gates.py",
    "tools/typescript_fastify_adapter_contract.py",
}


def affected_gates(changed_files: Sequence[str]) -> tuple[Gate, ...]:
    all_gates = PROFILES["all"]
    if not changed_files:
        return ()

    selected: set[Gate] = {AUTOMATION_TESTS}
    for raw_path in changed_files:
        path = raw_path.removeprefix("./").replace("\\", "/")
        if path.startswith("web/"):
            selected.update((WEB_BUILD, WEB_LINT))
        elif path.startswith(("adapters/", "tests/fixtures/")):
            selected.update((PYTHON_TESTS, PYTHON_LINT, PACKAGING_CONTRACT))
        elif path in PACKAGING_TOOL_INPUTS:
            selected.update((PYTHON_TESTS, PYTHON_LINT, PACKAGING_CONTRACT))
        elif path.startswith(("src/ucf/", "tests/", "tools/")) or path.endswith(
            ".py"
        ):
            selected.update((PYTHON_TESTS, PYTHON_LINT))
            if path.startswith(("src/ucf/", "tools/")):
                selected.add(SPEC_VALIDATION)
            if path.startswith("src/ucf/") or path in {
                "tools/package_contract.py",
                "tools/quality_gates.py",
            }:
                selected.add(PACKAGING_CONTRACT)
        elif path.startswith(("specs/", "examples/specs/")):
            selected.update((PYTHON_TESTS, SPEC_VALIDATION))
        elif path in {"pyproject.toml", "uv.lock"}:
            selected.update((PYTHON_TESTS, PYTHON_LINT, PACKAGING_CONTRACT))
        elif path.startswith((".github/", ".codex/", "docs/")) or path in {
            "AGENTS.md",
            "PLANS.md",
            "README.md",
        }:
            pass
        elif path.endswith(".md"):
            pass
        else:
            return all_gates

    return tuple(gate for gate in all_gates if gate in selected)


def discover_changed_files(repository_root: Path) -> tuple[str, ...] | None:
    commands = (
        ("git", "diff", "--name-only", "-z", "HEAD", "--"),
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    )
    paths: set[str] = set()
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        paths.update(path for path in completed.stdout.split("\0") if path)
    return tuple(sorted(paths))


def select_profile_gates(
    profile: str,
    repository_root: Path,
    changed_files: Sequence[str] | None = None,
) -> tuple[Gate, ...]:
    if profile != "affected":
        return PROFILES[profile]
    discovered = (
        tuple(changed_files)
        if changed_files is not None
        else discover_changed_files(repository_root)
    )
    return PROFILES["all"] if discovered is None else affected_gates(discovered)


def run_gates(
    gates: Sequence[Gate],
    log_dir: Path,
    repository_root: Path | None = None,
) -> tuple[GateResult, ...]:
    _validate_gates(gates)
    root = repository_root or Path.cwd()
    log_dir.mkdir(parents=True, exist_ok=True)
    results = tuple(_run_gate(gate, root, log_dir) for gate in gates)
    _write_summary(results, log_dir)
    _print_summary(results, log_dir)
    return results


def profile_manifest(profile: str, gates: Sequence[Gate]) -> dict[str, object]:
    _validate_gates(gates)
    return {
        "schema_version": GATE_MANIFEST_SCHEMA_VERSION,
        "profile": profile,
        "gates": [
            {
                "id": gate.name,
                "command": list(gate.command),
                "cwd": gate.working_directory.as_posix(),
            }
            for gate in gates
        ],
    }


def _validate_gates(gates: Sequence[Gate]) -> None:
    identities: set[str] = set()
    for gate in gates:
        if not SAFE_GATE_ID.fullmatch(gate.name):
            raise ValueError(f"invalid gate identity: {gate.name!r}")
        if gate.name in identities:
            raise ValueError(f"duplicate gate identity: {gate.name}")
        identities.add(gate.name)


def _run_gate(gate: Gate, root: Path, log_dir: Path) -> GateResult:
    working_directory = root / gate.working_directory
    log_path = log_dir / f"{gate.name}.log"
    command_text = shlex.join(gate.command)
    print(
        f"\n==> {gate.name}\ncwd: {working_directory}\ncommand: {command_text}",
        flush=True,
    )

    started_at = time.monotonic()
    returncode = _stream_process(gate.command, working_directory, log_path)
    duration_seconds = time.monotonic() - started_at
    status = "PASS" if returncode == 0 else "FAIL"
    print(
        f"<== {gate.name}: {status} ({duration_seconds:.2f}s, exit {returncode})",
        flush=True,
    )
    return GateResult(gate, returncode, duration_seconds, log_path)


def _stream_process(
    command: tuple[str, ...],
    working_directory: Path,
    log_path: Path,
) -> int:
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    try:
        process = subprocess.Popen(
            command,
            cwd=working_directory,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        message = f"Could not start command: {error}\n"
        print(message, end="", flush=True)
        log_path.write_text(message)
        return 127

    assert process.stdout is not None
    with log_path.open("w") as log_file:
        for line in process.stdout:
            print(line, end="", flush=True)
            log_file.write(line)
            log_file.flush()
    return process.wait()


def _write_summary(results: Sequence[GateResult], log_dir: Path) -> None:
    lines = [_summary_line(result) for result in results]
    (log_dir / "summary.txt").write_text("\n".join(lines) + "\n")


def _print_summary(results: Sequence[GateResult], log_dir: Path) -> None:
    print("\nQuality gate summary", flush=True)
    for result in results:
        print(_summary_line(result), flush=True)
    print(f"Logs: {log_dir}", flush=True)


def _summary_line(result: GateResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    return (
        f"{status:4} {result.gate.name:20} "
        f"{result.duration_seconds:8.2f}s exit={result.returncode}"
    )


def _default_log_dir(root: Path) -> Path:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / ".artifacts" / "quality" / run_id


def _parse_args(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run UCF quality gates with live, retained output."
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_NAMES),
        default="all",
        help="Named set of gates to run.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Directory for gate logs. Defaults to a timestamped artifact path.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List gates in the selected profile without running them.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Listing format used with --list.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        help=(
            "Explicit changed path for the affected profile. Repeat as needed; "
            "normally paths are discovered from Git."
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(arguments or sys.argv[1:])
    root = Path(__file__).resolve().parents[1]
    if args.changed_file and args.profile != "affected":
        raise SystemExit("--changed-file requires --profile affected")
    gates = select_profile_gates(args.profile, root, args.changed_file)
    if args.list:
        if args.format == "json":
            print(
                json.dumps(
                    profile_manifest(args.profile, gates),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        for gate in gates:
            print(f"{gate.name}: {shlex.join(gate.command)}")
        return 0

    log_dir = args.log_dir or _default_log_dir(root)
    results = run_gates(gates, log_dir=log_dir, repository_root=root)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
