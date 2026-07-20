from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from tools.quality_gates import PROFILES, affected_gates

ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = ROOT / ".codex" / "hooks" / "stop_quality.py"
HOOK_CONFIG = ROOT / ".codex" / "hooks.json"


def _gate_names(paths: tuple[str, ...]) -> list[str]:
    return [gate.name for gate in affected_gates(paths)]


def _load_hook_module():
    spec = importlib.util.spec_from_file_location("ucf_stop_quality_hook", HOOK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_affected_profile_selects_only_relevant_stable_gates():
    assert _gate_names(("docs/automation/STATE.md",)) == ["automation-tests"]
    assert _gate_names(("web/src/pages/GraphPage.tsx",)) == [
        "automation-tests",
        "web-build",
        "web-lint",
    ]
    assert _gate_names(("src/ucf/models/spec.py",)) == [
        "automation-tests",
        "python-tests",
        "python-lint",
        "spec-validation",
        "packaging-contract",
    ]
    assert _gate_names(("unclassified.release-input",)) == [
        gate.name for gate in PROFILES["all"]
    ]


@pytest.mark.parametrize(
    "changed_path",
    (
        "adapters/go-stdlib/cmd/adapter/main.go",
        (
            "tests/fixtures/brownfield/"
            "go_stdlib_legacy_platforms/go.mod"
        ),
        "tools/go_stdlib_platform_contract.py",
        "tools/installed_go_stdlib_platform_smoke.py",
    ),
)
def test_affected_profile_routes_platform_distribution_inputs_to_packaging(
    changed_path,
):
    assert _gate_names((changed_path,)) == [
        "automation-tests",
        "python-tests",
        "python-lint",
        "packaging-contract",
    ]


def test_stop_hook_configuration_uses_official_project_contract():
    configuration = json.loads(HOOK_CONFIG.read_text())

    [matcher_group] = configuration["hooks"]["Stop"]
    assert "matcher" not in matcher_group
    [hook] = matcher_group["hooks"]
    assert hook == {
        "type": "command",
        "command": (
            '/usr/bin/python3 "$(git rev-parse --show-toplevel)/'
            '.codex/hooks/stop_quality.py"'
        ),
        "timeout": 1200,
        "statusMessage": "Running UCF quality gates",
    }


def test_stop_hook_selects_affected_or_explicit_release_profile(tmp_path):
    hook = _load_hook_module()
    calls: list[tuple[str, Path]] = []

    def passing_runner(profile: str, log_dir: Path) -> int:
        calls.append((profile, log_dir))
        return 0

    payload = {
        "hook_event_name": "Stop",
        "session_id": "session",
        "turn_id": "turn",
        "cwd": str(ROOT),
        "stop_hook_active": False,
    }
    ordinary = hook.handle_stop(
        payload,
        repository_root=ROOT,
        environment={},
        state_text="active_work_package: FND-003\n",
        runner=passing_runner,
    )
    release = hook.handle_stop(
        payload,
        repository_root=ROOT,
        environment={},
        state_text="active_work_package: REL-001\n",
        runner=passing_runner,
    )
    override = hook.handle_stop(
        payload,
        repository_root=ROOT,
        environment={"UCF_STOP_PROFILE": "all"},
        state_text="active_work_package: FND-003\n",
        runner=passing_runner,
    )

    assert ordinary == {"continue": True}
    assert release == {"continue": True}
    assert override == {"continue": True}
    assert [profile for profile, _ in calls] == ["affected", "all", "all"]


def test_stop_hook_blocks_with_same_profile_and_retained_evidence():
    hook = _load_hook_module()
    payload = {
        "hook_event_name": "Stop",
        "session_id": "unsafe/session",
        "turn_id": "turn",
        "cwd": str(ROOT),
        "stop_hook_active": False,
    }

    result = hook.handle_stop(
        payload,
        repository_root=ROOT,
        environment={},
        state_text="active_work_package: FND-003\n",
        runner=lambda _profile, _log_dir: 1,
    )

    assert result["decision"] == "block"
    assert "affected" in result["reason"]
    assert ".artifacts/quality/stop-hook/unsafe_session-turn/summary.txt" in result[
        "reason"
    ]


def test_stop_hook_prevents_continuation_loop_without_running_gates():
    hook = _load_hook_module()
    called = False

    def forbidden_runner(_profile: str, _log_dir: Path) -> int:
        nonlocal called
        called = True
        return 1

    result = hook.handle_stop(
        {
            "hook_event_name": "Stop",
            "session_id": "session",
            "turn_id": "turn",
            "cwd": str(ROOT),
            "stop_hook_active": True,
        },
        repository_root=ROOT,
        environment={},
        state_text="active_work_package: REL-002\n",
        runner=forbidden_runner,
    )

    assert result == {"continue": True}
    assert not called


def test_stop_hook_stdout_is_exact_json_for_loop_prevention():
    completed = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(
            {
                "hook_event_name": "Stop",
                "session_id": "session",
                "turn_id": "turn",
                "cwd": str(ROOT),
                "stop_hook_active": True,
            }
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"continue": True}
    assert completed.stdout == '{"continue":true}\n'
    assert completed.stderr == ""
