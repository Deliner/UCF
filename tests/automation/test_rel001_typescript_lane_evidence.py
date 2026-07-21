from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from tools import installed_typescript_fastify_smoke as smoke


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _valid_cli_paths(tmp_path: Path) -> tuple[Path, Path]:
    adapter = tmp_path / "adapter"
    adapter.write_text("#!/bin/sh\n", encoding="ascii")
    adapter.chmod(0o755)
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    return adapter, fixture


def _sample_envelope() -> dict[str, object]:
    manifest = {
        "b.ts": smoke._SourceFile(size=2, digest="b" * 64),
        "a.ts": smoke._SourceFile(size=1, digest="a" * 64),
    }
    deterministic = {
        "inventory": {"kind": "inventory_snapshot"},
        "discovery": {"kind": "discovery_result_profile"},
        "decisions": {"kind": "decision_set_profile"},
        "bundle": {"kind": "onboarding_bundle"},
        "mapping": {"kind": "implementation_mapping_result"},
        "verification_requests": [
            {"kind": "execution_verification_request"}
        ],
    }
    runtime = {
        "verification_results": [
            {"kind": "execution_verification_result"}
        ],
        "successor_behaviors": [{"kind": "behavior_ir"}],
        "tested_trust": [{"kind": "trust_ir"}],
    }
    metrics = {
        "inventory_record_count": 42,
        "candidate_count": 4,
        "dispositions": {
            "accepted": 1,
            "edited": 0,
            "rejected": 3,
            "uncertain": 0,
        },
        "eligible_interface_count": 6,
        "uncovered_interface_count": 2,
        "materialization_count": 1,
        "mapping_binding_count": 1,
        "tested_claim_count": 1,
        "verified_claim_count": 0,
        "verification_evidence_count": 1,
        "transports": ["http"],
    }
    return smoke._lane_evidence(
        manifest,
        smoke._WorkflowEvidence(
            deterministic=deterministic,
            runtime=runtime,
            metrics=metrics,
        ),
    )


def test_lane_envelope_has_exact_shape_and_canonical_source_digest() -> None:
    envelope = _sample_envelope()
    manifest_records = [
        {"digest": "a" * 64, "path": "a.ts", "size": 1},
        {"digest": "b" * 64, "path": "b.ts", "size": 2},
    ]

    assert set(envelope) == {
        "kind",
        "evidence_version",
        "lane",
        "status",
        "source",
        "deterministic",
        "runtime",
        "metrics",
    }
    assert envelope["kind"] == "rel001_lane_evidence"
    assert envelope["evidence_version"] == "1.0.0"
    assert envelope["lane"] == "typescript_fastify"
    assert envelope["status"] == "passed"
    assert envelope["source"] == {
        "file_count": 2,
        "byte_count": 3,
        "manifest_digest": hashlib.sha256(
            _canonical_bytes(manifest_records)
        ).hexdigest(),
    }
    assert set(envelope["deterministic"]) == {
        "inventory",
        "discovery",
        "decisions",
        "bundle",
        "mapping",
        "verification_requests",
    }
    assert set(envelope["runtime"]) == {
        "verification_results",
        "successor_behaviors",
        "tested_trust",
    }
    assert isinstance(envelope["runtime"]["tested_trust"], list)
    assert len(envelope["runtime"]["tested_trust"]) == 1
    assert set(envelope["metrics"]) == {
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


def test_lane_envelope_rejects_scalar_runtime_bound_resources() -> None:
    envelope = _sample_envelope()
    runtime = dict(envelope["runtime"])
    runtime["tested_trust"] = {"kind": "trust_ir"}
    workflow = smoke._WorkflowEvidence(
        deterministic=envelope["deterministic"],
        runtime=runtime,
        metrics=envelope["metrics"],
    )
    manifest = {
        "fixture.ts": smoke._SourceFile(size=1, digest="a" * 64),
    }

    with pytest.raises(smoke.SmokeFailure) as captured:
        smoke._lane_evidence(manifest, workflow)

    assert captured.value.code == "runtime_evidence_shape_mismatch"


def test_optional_output_is_canonical_and_default_stdout_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter, fixture = _valid_cli_paths(tmp_path)
    envelope = _sample_envelope()
    observed_outputs = []

    def fake_run(arguments):
        observed_outputs.append(arguments.evidence_output)
        return envelope if arguments.evidence_output is not None else None

    monkeypatch.setattr(smoke, "_run", fake_run)

    assert smoke.main(
        ["--adapter", str(adapter), "--fixture", str(fixture)]
    ) == 0
    assert capsys.readouterr() == ("{\"status\":\"PASS\"}\n", "")

    output = tmp_path / "typescript-evidence.json"
    assert smoke.main(
        [
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--evidence-output",
            str(output),
        ]
    ) == 0
    assert capsys.readouterr() == ("{\"status\":\"PASS\"}\n", "")
    assert output.read_bytes() == _canonical_bytes(envelope)
    assert observed_outputs == [None, output]
    assert str(tmp_path).encode("ascii") not in output.read_bytes()


@pytest.mark.parametrize(
    ("output_kind", "expected_code"),
    [
        ("relative", "evidence_output_not_absolute"),
        ("existing", "evidence_output_exists"),
        ("symlink", "evidence_output_is_symlink"),
        ("missing_parent", "evidence_output_parent_missing"),
    ],
)
def test_invalid_output_is_rejected_before_work_and_preserved(
    output_kind: str,
    expected_code: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter, fixture = _valid_cli_paths(tmp_path)
    sentinel = b"do-not-replace\n"
    if output_kind == "relative":
        output = Path("relative-evidence.json")
    elif output_kind == "existing":
        output = tmp_path / "evidence.json"
        output.write_bytes(sentinel)
    elif output_kind == "symlink":
        target = tmp_path / "sentinel.json"
        target.write_bytes(sentinel)
        output = tmp_path / "evidence.json"
        output.symlink_to(target)
    else:
        output = tmp_path / "missing" / "evidence.json"

    def reject_work(_arguments):
        raise AssertionError("workflow must not start")

    monkeypatch.setattr(smoke, "_run", reject_work)

    assert smoke.main(
        [
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--evidence-output",
            str(output),
        ]
    ) == 3
    assert capsys.readouterr() == (
        "",
        f'{{"code":"{expected_code}","status":"FAIL"}}\n',
    )
    if output_kind == "existing":
        assert output.read_bytes() == sentinel
    elif output_kind == "symlink":
        assert output.is_symlink()
        assert output.read_bytes() == sentinel


def test_atomic_publication_preserves_racing_sentinel_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter, fixture = _valid_cli_paths(tmp_path)
    output = tmp_path / "evidence.json"
    sentinel = b"won-the-race\n"
    monkeypatch.setattr(smoke, "_run", lambda _arguments: _sample_envelope())

    def racing_link(_source, destination, *, follow_symlinks):
        assert follow_symlinks is False
        Path(destination).write_bytes(sentinel)
        raise FileExistsError

    monkeypatch.setattr(smoke.os, "link", racing_link)

    assert smoke.main(
        [
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--evidence-output",
            str(output),
        ]
    ) == 3
    assert capsys.readouterr() == (
        "",
        '{"code":"evidence_output_appeared","status":"FAIL"}\n',
    )
    assert output.read_bytes() == sentinel
    assert list(tmp_path.glob(".evidence.json.*.tmp")) == []


def test_changed_fixture_prevents_evidence_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter, fixture = _valid_cli_paths(tmp_path)
    output = tmp_path / "evidence.json"
    expected = {
        path: smoke._SourceFile(size=size, digest=digest)
        for path, (size, digest) in smoke._EXPECTED_SOURCE_MANIFEST.items()
    }
    changed = dict(expected)
    first_path = next(iter(changed))
    changed[first_path] = smoke._SourceFile(size=1, digest="f" * 64)
    manifests = iter((expected, changed))

    monkeypatch.setattr(smoke, "_assert_installed_boundary", lambda: None)
    monkeypatch.setattr(smoke, "_assert_fixture_is_fresh", lambda _root: None)
    monkeypatch.setattr(smoke, "_source_manifest", lambda _root: next(manifests))

    async def fake_workflow(_arguments):
        return smoke._WorkflowResult(
            source_revision=smoke._SOURCE_REVISION,
            semantic_digest=smoke._QUOTE_SEMANTIC_DIGEST,
            behavior_root=smoke._QUOTE_ROOT,
            verification_outcome="passed",
            claim_level="tested",
            stderr_bytes=0,
        )

    monkeypatch.setattr(smoke, "_run_workflow", fake_workflow)

    assert smoke.main(
        [
            "--adapter",
            str(adapter),
            "--fixture",
            str(fixture),
            "--evidence-output",
            str(output),
        ]
    ) == 3
    assert capsys.readouterr() == (
        "",
        '{"code":"fixture_source_changed_by_workflow","status":"FAIL"}\n',
    )
    assert not output.exists()
