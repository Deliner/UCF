from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from tools import installed_go_stdlib_platform_smoke as platform_smoke
from tools import installed_go_stdlib_smoke as http_smoke

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("module", "executable_option"),
    [
        (http_smoke, "--fixture-executable"),
        (platform_smoke, "--platform-fixture-executable"),
    ],
    ids=["go-http", "go-platform"],
)
def test_evidence_output_accepts_an_absolute_absent_file(
    module,
    executable_option: str,
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    adapter = _executable(tmp_path / "adapter")
    fixture_executable = _executable(tmp_path / "fixture-executable")
    output = tmp_path / "evidence.json"

    arguments = module._parse_arguments(
        [
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            executable_option,
            str(fixture_executable),
            "--evidence-output",
            str(output),
        ]
    )

    assert arguments.evidence_output == output
    assert not output.exists()


@pytest.mark.parametrize(
    ("module", "lane", "transports", "verification_count"),
    [
        (http_smoke, "go_http", ["http"], 1),
        (platform_smoke, "go_platform", ["cli", "event"], 2),
    ],
    ids=["go-http", "go-platform"],
)
def test_lane_evidence_has_the_closed_canonical_shape(
    module,
    lane: str,
    transports: list[str],
    verification_count: int,
) -> None:
    manifest = _manifest(module)
    result = _workflow_result(module, verification_count)

    evidence = module._build_evidence(manifest, result)
    encoded = module._canonical_json_bytes(evidence)

    assert set(evidence) == {
        "kind",
        "evidence_version",
        "lane",
        "status",
        "source",
        "deterministic",
        "runtime",
        "metrics",
    }
    assert evidence["kind"] == "rel001_lane_evidence"
    assert evidence["evidence_version"] == "1.0.0"
    assert evidence["lane"] == lane
    assert evidence["status"] == "passed"
    assert evidence["source"] == {
        "file_count": 2,
        "byte_count": 12,
        "manifest_digest": _manifest_digest(manifest),
    }
    deterministic = evidence["deterministic"]
    assert set(deterministic) == {
        "inventory",
        "discovery",
        "decisions",
        "bundle",
        "mapping",
        "verification_requests",
    }
    assert deterministic["inventory"] == {"resource": "inventory"}
    assert len(deterministic["verification_requests"]) == verification_count
    assert set(evidence["runtime"]) == {
        "verification_results",
        "successor_behaviors",
        "tested_trust",
    }
    assert len(evidence["runtime"]["verification_results"]) == (
        verification_count
    )
    assert len(evidence["runtime"]["successor_behaviors"]) == verification_count
    assert len(evidence["runtime"]["tested_trust"]) == verification_count
    metrics = evidence["metrics"]
    assert set(metrics) == {
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
    assert metrics == (
        {
            "inventory_record_count": 51,
            "candidate_count": 4,
            "dispositions": {
                "accepted": 1,
                "edited": 0,
                "rejected": 2,
                "uncertain": 1,
            },
            "eligible_interface_count": 12,
            "uncovered_interface_count": 8,
            "materialization_count": 1,
            "mapping_binding_count": 1,
            "tested_claim_count": 1,
            "verified_claim_count": 0,
            "verification_evidence_count": 1,
            "transports": transports,
        }
        if lane == "go_http"
        else {
            "inventory_record_count": 62,
            "candidate_count": 1,
            "dispositions": {
                "accepted": 1,
                "edited": 0,
                "rejected": 0,
                "uncertain": 0,
            },
            "eligible_interface_count": 9,
            "uncovered_interface_count": 8,
            "materialization_count": 1,
            "mapping_binding_count": 1,
            "tested_claim_count": 2,
            "verified_claim_count": 0,
            "verification_evidence_count": 2,
            "transports": transports,
        }
    )
    assert encoded.endswith(b"\n")
    assert encoded == (
        json.dumps(
            evidence,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


@pytest.mark.parametrize(
    ("module", "fixture_name", "file_count", "byte_count"),
    [
        (http_smoke, "go_stdlib_legacy_quote", 6, 6_692),
        (platform_smoke, "go_stdlib_legacy_platforms", 9, 20_810),
    ],
    ids=["go-http", "go-platform"],
)
def test_frozen_go_source_manifest_has_exact_evidence_denominators(
    module,
    fixture_name: str,
    file_count: int,
    byte_count: int,
) -> None:
    fixture = (
        ROOT / "tests" / "fixtures" / "brownfield" / fixture_name
    ).resolve(strict=True)
    manifest = module._source_manifest(fixture)
    source = module._build_evidence(
        manifest,
        _workflow_result(module, 1 if module is http_smoke else 2),
    )["source"]

    assert source == {
        "file_count": file_count,
        "byte_count": byte_count,
        "manifest_digest": _manifest_digest(manifest),
    }


@pytest.mark.parametrize("module", [http_smoke, platform_smoke])
def test_atomic_evidence_publish_never_overwrites_and_cleans_temp_files(
    module,
    tmp_path: Path,
) -> None:
    output = tmp_path / "lane.json"
    evidence = {
        "kind": "rel001_lane_evidence",
        "evidence_version": "1.0.0",
    }

    module._publish_evidence(output, evidence)
    accepted = output.read_bytes()

    with pytest.raises(module.SmokeFailure) as captured:
        module._publish_evidence(output, {"replacement": True})

    assert captured.value.code == "evidence_output_appeared"
    assert output.read_bytes() == accepted
    assert list(tmp_path.glob(".lane.json.*.tmp")) == []


@pytest.mark.parametrize(
    ("module", "executable_option", "summary", "verification_count"),
    [
        (
            http_smoke,
            "--fixture-executable",
            {"status": "PASS"},
            1,
        ),
        (
            platform_smoke,
            "--platform-fixture-executable",
            {
                "candidate_count": 1,
                "deterministic_sessions": 2,
                "mismatch_rejections": 2,
                "status": "PASS",
                "tested_claim_count": 2,
                "verified_claim_count": 0,
            },
            2,
        ),
    ],
    ids=["go-http", "go-platform"],
)
def test_main_keeps_default_stdout_and_optionally_publishes_evidence(
    module,
    executable_option: str,
    summary: dict[str, object],
    verification_count: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    adapter = _executable(tmp_path / "adapter")
    fixture_executable = _executable(tmp_path / "fixture-executable")
    output = tmp_path / "evidence.json"
    evidence = module._build_evidence(
        _manifest(module),
        _workflow_result(module, verification_count),
    )
    run_result = module._RunResult(summary=summary, evidence=evidence)
    calls = []
    monkeypatch.setattr(
        module,
        "_run",
        lambda arguments: calls.append(arguments) or run_result,
    )
    base = [
        "--adapter",
        str(adapter),
        "--fixture",
        str(fixture),
        executable_option,
        str(fixture_executable),
    ]

    assert module.main(base) == 0
    default_output = capsys.readouterr()
    assert module.main([*base, "--evidence-output", str(output)]) == 0
    evidence_output = capsys.readouterr()

    expected_stdout = (
        json.dumps(
            summary,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    assert default_output.out == expected_stdout
    assert default_output.err == ""
    assert evidence_output.out == expected_stdout
    assert evidence_output.err == ""
    assert output.read_bytes() == module._canonical_json_bytes(evidence)
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("module", "executable_option"),
    [
        (http_smoke, "--fixture-executable"),
        (platform_smoke, "--platform-fixture-executable"),
    ],
    ids=["go-http", "go-platform"],
)
@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("relative", "evidence_output_not_absolute"),
        ("existing", "evidence_output_exists"),
        ("symlink", "evidence_output_is_symlink"),
    ],
)
def test_invalid_evidence_destinations_fail_before_work_and_preserve_sentinel(
    module,
    executable_option: str,
    mode: str,
    expected_code: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    adapter = _executable(tmp_path / "adapter")
    fixture_executable = _executable(tmp_path / "fixture-executable")
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"preserve-me")
    if mode == "relative":
        output = Path(f"rel001-{tmp_path.name}.json")
    elif mode == "existing":
        output = sentinel
    else:
        output = tmp_path / "evidence.json"
        output.symlink_to(sentinel)
    monkeypatch.setattr(
        module,
        "_run",
        lambda arguments: pytest.fail("workflow started for invalid output"),
    )

    result = module.main(
        [
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            executable_option,
            str(fixture_executable),
            "--evidence-output",
            str(output),
        ]
    )
    captured = capsys.readouterr()

    assert result == 3
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "code": expected_code,
        "status": "FAIL",
    }
    assert sentinel.read_bytes() == b"preserve-me"


@pytest.mark.parametrize("module", [http_smoke, platform_smoke])
def test_evidence_publish_is_bounded_before_creating_a_temp_file(
    module,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lane.json"
    monkeypatch.setattr(module, "_MAX_EVIDENCE_BYTES", 8)

    with pytest.raises(module.SmokeFailure) as captured:
        module._publish_evidence(output, {"too": "large"})

    assert captured.value.code == "evidence_output_too_large"
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("module", [http_smoke, platform_smoke])
def test_atomic_publication_preserves_a_racing_sentinel(
    module,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "lane.json"
    sentinel = b"won-the-race\n"
    observed_temporary = None

    def racing_link(source, destination, *, follow_symlinks):
        nonlocal observed_temporary
        observed_temporary = Path(source)
        assert Path(source).parent == Path(destination).parent
        assert follow_symlinks is False
        Path(destination).write_bytes(sentinel)
        raise FileExistsError

    monkeypatch.setattr(module.os, "link", racing_link)

    with pytest.raises(module.SmokeFailure) as captured:
        module._publish_evidence(output, {"accepted": True})

    assert captured.value.code == "evidence_output_appeared"
    assert output.read_bytes() == sentinel
    assert observed_temporary is not None
    assert not observed_temporary.exists()
    assert list(tmp_path.glob(".lane.json.*.tmp")) == []


def test_installed_go_drivers_do_not_import_repository_test_helpers() -> None:
    for module in (http_smoke, platform_smoke):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "from tests" not in source
        assert "import tests" not in source


def _workflow_result(module, verification_count: int):
    deterministic_values = {
        "inventory": _canonical_resource("inventory"),
        "discovery": _canonical_resource("discovery"),
        "decisions": _canonical_resource("decisions"),
        "bundle": _canonical_resource("bundle"),
        "mapping": _canonical_resource("mapping"),
    }
    if module is http_smoke:
        deterministic = module._DeterministicArtifacts(
            **deterministic_values,
            verification_request=_canonical_resource("request-http"),
        )
        runtime = module._RuntimeArtifacts(
            verification_result=_canonical_resource("result-http"),
            successor_behavior=_canonical_text("behavior-http"),
            tested_trust=_canonical_text("trust-http"),
            executed_at="2026-07-21T12:00:00Z",
        )
        return module._WorkflowResult(
            deterministic=deterministic,
            runtime=runtime,
            source_revision="a" * 64,
            semantic_digest="b" * 64,
            behavior_root="use-case.quote-order",
            mapping_id="mapping." + "c" * 64,
            mapping_source_record_ids=("interface.fixture",),
            verification_outcome="passed",
            tested_claim_count=1,
            verified_claim_count=0,
            verification_evidence_count=1,
            stderr_bytes=0,
        )
    deterministic = module._DeterministicArtifacts(
        **deterministic_values,
        cli_request=_canonical_resource("request-cli"),
        event_request=_canonical_resource("request-event"),
    )
    runtime = module._RuntimeArtifacts(
        verification_results=(
            _canonical_resource("result-cli"),
            _canonical_resource("result-event"),
        ),
        successor_behaviors=(
            _canonical_text("behavior-cli"),
            _canonical_text("behavior-event"),
        ),
        tested_trust=(
            _canonical_text("trust-cli"),
            _canonical_text("trust-event"),
        ),
    )
    return module._WorkflowResult(
        deterministic=deterministic,
        runtime=runtime,
        bundle=object(),
        mapping_id="mapping." + "c" * 64,
        mapping_source_record_ids=("interface.fixture",),
        verification_outcomes=("passed", "passed"),
        tested_claim_count=2,
        verified_claim_count=0,
        verification_evidence_count=2,
        stderr_bytes=0,
    )


def _manifest(module):
    common = {
        "size": 6,
        "digest": hashlib.sha256(b"source").hexdigest(),
    }
    if module is http_smoke:
        identity = module._FileIdentity(**common)
    else:
        identity = module._FileIdentity(
            **common,
            device=1,
            inode=2,
            mode=0o100600,
            modified_ns=3,
            changed_ns=4,
        )
    return {"a.go": identity, "b.go": identity}


def _manifest_digest(manifest) -> str:
    records = [
        {"path": path, "size": identity.size, "digest": identity.digest}
        for path, identity in sorted(manifest.items())
    ]
    payload = (
        json.dumps(
            records,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _canonical_resource(name: str) -> bytes:
    return _canonical_text(name).encode("ascii")


def _canonical_text(name: str) -> str:
    return json.dumps(
        {"resource": name},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _executable(path: Path) -> Path:
    path.write_bytes(b"fixture executable\n")
    path.chmod(0o700)
    return path
