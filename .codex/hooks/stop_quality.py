from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

Runner = Callable[[str, Path], int]
ACTIVE_PACKAGE = re.compile(
    r"^active_work_package:\s*(?P<package>[A-Z]+-\d+)\s*$",
    re.MULTILINE,
)
UNSAFE_PATH_CHARACTER = re.compile(r"[^A-Za-z0-9_.-]")


class HookInputError(ValueError):
    pass


def _profile(environment: Mapping[str, str], state_text: str) -> str:
    override = environment.get("UCF_STOP_PROFILE")
    if override is not None:
        if override != "all":
            raise HookInputError("UCF_STOP_PROFILE only accepts the safe value 'all'")
        return "all"

    match = ACTIVE_PACKAGE.search(state_text)
    if match is None:
        return "all"
    return "all" if match.group("package").startswith("REL-") else "affected"


def _safe_path_component(value: object, fallback: str) -> str:
    if not isinstance(value, str) or not value:
        return fallback
    sanitized = UNSAFE_PATH_CHARACTER.sub("_", value)
    return sanitized[:64] or fallback


def _validate_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("hook_event_name") != "Stop":
        raise HookInputError("hook_event_name must be 'Stop'")
    if not isinstance(payload.get("stop_hook_active"), bool):
        raise HookInputError("stop_hook_active must be a boolean")


def _failure(reason: str) -> dict[str, str]:
    return {"decision": "block", "reason": reason}


def handle_stop(
    payload: Mapping[str, Any],
    *,
    repository_root: Path,
    environment: Mapping[str, str],
    state_text: str,
    runner: Runner,
) -> dict[str, object]:
    try:
        _validate_payload(payload)
        if payload["stop_hook_active"]:
            return {"continue": True}
        profile = _profile(environment, state_text)
    except HookInputError as error:
        return _failure(f"UCF Stop-hook input is invalid: {error}")

    session = _safe_path_component(payload.get("session_id"), "session")
    turn = _safe_path_component(payload.get("turn_id"), "turn")
    relative_log_dir = Path(".artifacts") / "quality" / "stop-hook" / (
        f"{session}-{turn}"
    )
    log_dir = repository_root / relative_log_dir
    returncode = runner(profile, log_dir)
    if returncode == 0:
        return {"continue": True}
    return _failure(
        f"UCF {profile} quality profile failed. Inspect "
        f"{(relative_log_dir / 'summary.txt').as_posix()} and fix the failing "
        "gate before stopping."
    )


def _run_profile(repository_root: Path, profile: str, log_dir: Path) -> int:
    completed = subprocess.run(
        (
            sys.executable,
            str(repository_root / "tools" / "quality_gates.py"),
            "--profile",
            profile,
            "--log-dir",
            str(log_dir),
        ),
        cwd=repository_root,
        env=os.environ.copy(),
        stdout=sys.stderr,
        stderr=sys.stderr,
        check=False,
    )
    return completed.returncode


def _read_payload() -> Mapping[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise HookInputError(f"stdin is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise HookInputError("stdin JSON must be an object")
    return payload


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    try:
        payload = _read_payload()
    except HookInputError as error:
        result: dict[str, object] = _failure(
            f"UCF Stop-hook input is invalid: {error}"
        )
    else:
        state_path = repository_root / "docs" / "automation" / "STATE.md"
        state_text = state_path.read_text() if state_path.is_file() else ""
        result = handle_stop(
            payload,
            repository_root=repository_root,
            environment=os.environ,
            state_text=state_text,
            runner=lambda profile, log_dir: _run_profile(
                repository_root,
                profile,
                log_dir,
            ),
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
