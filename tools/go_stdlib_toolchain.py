"""Resolve the exact Go toolchain used by the compiled ecosystem proof."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from collections.abc import Mapping
from pathlib import Path

GO_STDLIB_VERSION_OUTPUT = "go version go1.26.5 linux/amd64\n"
_GO_STDLIB_CACHE_PATH = Path(
    ".cache/ucf-toolchains/go1.26.5/go/bin/go"
)
_VERSION_PROBE_TIMEOUT_SECONDS = 5.0


class GoStdlibToolchainError(RuntimeError):
    """Raised when no exact executable Go toolchain can be resolved."""


def resolve_go_stdlib_binary(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Return a verified Go 1.26.5 Linux/amd64 executable.

    An explicitly configured binary is authoritative: an invalid
    ``UCF_GO_BIN`` fails without trying another installation. Otherwise an
    exact ``go`` on ``PATH`` is preferred, followed by the portable per-user
    toolchain cache.
    """

    selected_environment = (
        os.environ.copy() if environment is None else dict(environment)
    )
    if "UCF_GO_BIN" in selected_environment:
        explicit = selected_environment["UCF_GO_BIN"]
        if not explicit:
            raise GoStdlibToolchainError(
                "UCF_GO_BIN must name the exact Go 1.26.5 executable"
            )
        return _require_exact_go_binary(
            Path(explicit).expanduser(),
            source="UCF_GO_BIN",
            environment=selected_environment,
        )

    failures: list[str] = []
    path_candidate = shutil.which(
        "go",
        path=selected_environment.get("PATH", ""),
    )
    if path_candidate is not None:
        try:
            return _require_exact_go_binary(
                Path(path_candidate),
                source="PATH",
                environment=selected_environment,
            )
        except GoStdlibToolchainError as error:
            failures.append(str(error))

    cache_candidate = Path.home() / _GO_STDLIB_CACHE_PATH
    try:
        return _require_exact_go_binary(
            cache_candidate,
            source="per-user cache",
            environment=selected_environment,
        )
    except GoStdlibToolchainError as error:
        failures.append(str(error))

    detail = "; ".join(failures)
    if not detail:
        detail = "no PATH or per-user cache candidate was available"
    raise GoStdlibToolchainError(
        f"Go 1.26.5 linux/amd64 executable is unavailable: {detail}"
    )


def _require_exact_go_binary(
    candidate: Path,
    *,
    source: str,
    environment: Mapping[str, str],
) -> Path:
    try:
        resolved = candidate.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise GoStdlibToolchainError(
            f"{source} Go executable is unavailable: {candidate}: {error}"
        ) from error

    if not stat.S_ISREG(metadata.st_mode):
        raise GoStdlibToolchainError(
            f"{source} Go executable is not a regular file: {resolved}"
        )
    if metadata.st_mode & 0o111 == 0:
        raise GoStdlibToolchainError(
            f"{source} Go executable is not executable: {resolved}"
        )

    probe_environment = dict(environment)
    probe_environment["GOTOOLCHAIN"] = "local"
    try:
        completed = subprocess.run(
            (str(resolved), "version"),
            capture_output=True,
            check=False,
            env=probe_environment,
            timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GoStdlibToolchainError(
            f"{source} Go version probe failed: {resolved}: {error}"
        ) from error

    expected = GO_STDLIB_VERSION_OUTPUT.encode("ascii")
    if (
        completed.returncode != 0
        or completed.stdout != expected
        or completed.stderr != b""
    ):
        raise GoStdlibToolchainError(
            f"{source} Go executable is outside the exact "
            "go1.26.5 linux/amd64 profile: "
            f"path={resolved}, exit={completed.returncode}, "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        )
    return resolved
