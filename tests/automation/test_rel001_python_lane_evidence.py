from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from tools.rel001_benchmark import (
    _benchmark_ratchet_policy,
    _compile_component,
)

from ucf.implementation_evidence import (
    canonical_implementation_evidence_json,
    parse_execution_verification_request_json,
    parse_execution_verification_result_json,
    parse_implementation_mapping_result_json,
)
from ucf.inventory import canonical_inventory_json, parse_inventory_snapshot_json
from ucf.ir import (
    canonical_ir_json,
    canonical_trust_ir_json,
    parse_ir_json,
    parse_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.onboarding import (
    canonical_onboarding_json,
    parse_decision_set_json,
    parse_discovery_result_json,
    parse_onboarding_bundle_json,
)

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tools" / "installed_python_legacy_quote_smoke.py"
ADAPTER_ROOT = ROOT / "tests" / "fixtures" / "adapters"
FIXTURE = ROOT / "tests" / "fixtures" / "brownfield" / "python_legacy_quote"
TOP_LEVEL_KEYS = {
    "kind",
    "evidence_version",
    "lane",
    "status",
    "source",
    "deterministic",
    "runtime",
    "metrics",
}
DETERMINISTIC_KEYS = {
    "inventory",
    "discovery",
    "decisions",
    "bundle",
    "mapping",
    "verification_requests",
}
METRIC_KEYS = {
    "inventory_record_count",
    "candidate_count",
    "dispositions",
    "eligible_interface_count",
    "uncovered_interface_count",
    "materialization_count",
    "mapping_binding_count",
    "tested_claim_count",
    "verified_claim_count",
    "verification_evidence_count",
    "transports",
}


def _run(*command: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )


def _canonical(value: object) -> bytes:
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


def _tree_manifest(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _source_manifest_digest(root: Path) -> str:
    entries = [
        {
            "path": path,
            "size": identity[0],
            "digest": identity[1],
        }
        for path, identity in sorted(_tree_manifest(root).items())
    ]
    return hashlib.sha256(_canonical(entries)).hexdigest()


def _assert_canonical_resources(evidence: dict[str, object]) -> None:
    deterministic = evidence["deterministic"]
    runtime = evidence["runtime"]
    assert isinstance(deterministic, dict)
    assert isinstance(runtime, dict)
    assert set(deterministic) == DETERMINISTIC_KEYS
    assert set(runtime) == {
        "verification_results",
        "successor_behaviors",
        "tested_trust",
    }

    inventory = parse_inventory_snapshot_json(_canonical(deterministic["inventory"]))
    assert canonical_inventory_json(inventory) == _canonical(deterministic["inventory"])
    discovery = parse_discovery_result_json(_canonical(deterministic["discovery"]))
    decisions = parse_decision_set_json(_canonical(deterministic["decisions"]))
    bundle = parse_onboarding_bundle_json(_canonical(deterministic["bundle"]))
    assert canonical_onboarding_json(discovery) == _canonical(
        deterministic["discovery"]
    )
    assert canonical_onboarding_json(decisions) == _canonical(
        deterministic["decisions"]
    )
    assert canonical_onboarding_json(bundle) == _canonical(deterministic["bundle"])
    mapping = parse_implementation_mapping_result_json(
        _canonical(deterministic["mapping"])
    )
    assert canonical_implementation_evidence_json(mapping) == _canonical(
        deterministic["mapping"]
    )

    requests = deterministic["verification_requests"]
    behaviors = runtime["successor_behaviors"]
    trust_documents = runtime["tested_trust"]
    results = runtime["verification_results"]
    assert isinstance(requests, list) and len(requests) == 1
    assert isinstance(behaviors, list) and len(behaviors) == 1
    assert isinstance(trust_documents, list) and len(trust_documents) == 1
    assert isinstance(results, list) and len(results) == 1
    request = parse_execution_verification_request_json(_canonical(requests[0]))
    result = parse_execution_verification_result_json(_canonical(results[0]))
    behavior = parse_ir_json(_canonical(behaviors[0]))
    trust = parse_trust_ir_json(_canonical(trust_documents[0]))
    assert canonical_implementation_evidence_json(request) == _canonical(requests[0])
    assert canonical_implementation_evidence_json(result) == _canonical(results[0])
    assert canonical_ir_json(behavior).encode("ascii") == _canonical(behaviors[0])
    assert canonical_trust_ir_json(trust).encode("ascii") == _canonical(
        trust_documents[0]
    )
    validate_trust_against_behavior(trust, behavior)


def test_installed_python_lane_emits_exact_evidence_and_rejects_unsafe_output(
    tmp_path: Path,
) -> None:
    assert DRIVER.is_file(), "production-owned Python lane driver is absent"
    source = DRIVER.read_text(encoding="utf-8")
    assert "from tests" not in source
    assert "import tests" not in source
    assert "inventory_reference." not in source

    external = tmp_path / "external"
    external.mkdir()
    adapter_directory = external / "adapter"
    adapter_directory.mkdir()
    adapter = adapter_directory / "inventory_reference_adapter.py"
    shutil.copy2(ADAPTER_ROOT / adapter.name, adapter)
    shutil.copytree(
        ADAPTER_ROOT / "inventory_reference",
        adapter_directory / "inventory_reference",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    fixture = external / "fixture"
    shutil.copytree(
        FIXTURE,
        fixture,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    driver = external / DRIVER.name
    shutil.copy2(DRIVER, driver)
    fixture_before = _tree_manifest(fixture)

    uv = shutil.which("uv")
    assert uv is not None
    wheel_directory = tmp_path / "wheel"
    built = _run(
        uv,
        "build",
        "--wheel",
        "--out-dir",
        str(wheel_directory),
        cwd=ROOT,
    )
    assert built.returncode == 0, built.stderr.decode("utf-8", "replace")
    wheels = tuple(wheel_directory.glob("*.whl"))
    assert len(wheels) == 1
    environment = tmp_path / "venv"
    created = _run(
        uv,
        "venv",
        "--python",
        sys.executable,
        str(environment),
        cwd=external,
    )
    assert created.returncode == 0, created.stderr.decode("utf-8", "replace")
    python = environment / "bin" / "python"
    installed = _run(
        uv,
        "pip",
        "install",
        "--python",
        str(python),
        str(wheels[0]),
        cwd=external,
    )
    assert installed.returncode == 0, installed.stderr.decode("utf-8", "replace")

    evidence_output = external / "python-lane-evidence.json"
    command = (
        str(python),
        "-I",
        str(driver),
        "--adapter",
        str(adapter),
        "--fixture",
        str(fixture),
    )
    completed = _run(
        *command,
        "--evidence-output",
        str(evidence_output),
        cwd=external,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b'{"status":"PASS"}\n'
    assert completed.stderr == b""
    payload = evidence_output.read_bytes()
    evidence = json.loads(payload)
    assert payload == _canonical(evidence)
    assert set(evidence) == TOP_LEVEL_KEYS
    assert evidence["kind"] == "rel001_lane_evidence"
    assert evidence["evidence_version"] == "1.0.0"
    assert evidence["lane"] == "python"
    assert evidence["status"] == "passed"
    assert evidence["source"] == {
        "file_count": 4,
        "byte_count": 1_584,
        "manifest_digest": _source_manifest_digest(fixture),
    }
    assert set(evidence["metrics"]) == METRIC_KEYS
    assert evidence["metrics"] == {
        "inventory_record_count": 24,
        "candidate_count": 4,
        "dispositions": {
            "accepted": 1,
            "edited": 1,
            "rejected": 1,
            "uncertain": 1,
        },
        "eligible_interface_count": 4,
        "uncovered_interface_count": 0,
        "materialization_count": 2,
        "mapping_binding_count": 1,
        "tested_claim_count": 1,
        "verified_claim_count": 0,
        "verification_evidence_count": 1,
        "transports": [],
    }
    _assert_canonical_resources(evidence)
    compiled = _compile_component(
        evidence,
        expected_lane="python",
        policy=_benchmark_ratchet_policy(),
    )
    assert compiled["component"]["claims"]["tested"] == 1
    assert compiled["component"]["claims"]["verified"] == 0
    assert _tree_manifest(fixture) == fixture_before

    sentinel = external / "existing-evidence.json"
    sentinel.write_bytes(b"preserve-me")
    rejected_existing = _run(
        *command,
        "--evidence-output",
        str(sentinel),
        cwd=external,
    )
    assert rejected_existing.returncode == 3
    assert rejected_existing.stdout == b""
    assert sentinel.read_bytes() == b"preserve-me"

    linked = external / "linked-evidence.json"
    linked.symlink_to(sentinel)
    rejected_symlink = _run(
        *command,
        "--evidence-output",
        str(linked),
        cwd=external,
    )
    assert rejected_symlink.returncode == 3
    assert rejected_symlink.stdout == b""
    assert linked.is_symlink()
    assert sentinel.read_bytes() == b"preserve-me"

    rejected_relative = _run(
        *command,
        "--evidence-output",
        "relative-evidence.json",
        cwd=external,
    )
    assert rejected_relative.returncode == 3
    assert rejected_relative.stdout == b""
    assert not (external / "relative-evidence.json").exists()
    assert _tree_manifest(fixture) == fixture_before
