from __future__ import annotations

import re
from pathlib import Path

import pytest

from ucf.adapter_conformance import (
    CONFORMANCE_KIT_VERSION,
    canonical_conformance_json,
    conformance_asset_names,
    conformance_kit_index,
    extract_conformance_kit,
    load_conformance_fixture,
    load_conformance_manifest,
    read_conformance_asset,
)

EXPECTED_CASE_IDS = (
    "case.initialize_shutdown",
    "case.incompatible_version",
    "case.duplicate_capability",
    "case.unsupported_required",
    "case.lifecycle",
    "case.capability_gate",
    "case.operation_families",
    "case.targeted_cancellation",
    "case.parse_error",
    "case.invalid_message",
    "case.optional_capability",
    "case.cancel_noop",
    "case.duplicate_request_id",
    "case.unknown_method",
    "case.invalid_params",
    "case.duplicate_json_member",
    "case.shutdown_pending",
)
EXPECTED_ASSETS = (
    "fixtures/cancel-noop.json",
    "fixtures/capability-gate.json",
    "fixtures/duplicate-capability.json",
    "fixtures/duplicate-json-member.json",
    "fixtures/duplicate-request-id.json",
    "fixtures/incompatible-version.json",
    "fixtures/initialize-shutdown.json",
    "fixtures/invalid-message.json",
    "fixtures/invalid-params.json",
    "fixtures/lifecycle.json",
    "fixtures/operation-families.json",
    "fixtures/optional-capability.json",
    "fixtures/parse-error.json",
    "fixtures/shutdown-pending.json",
    "fixtures/targeted-cancellation.json",
    "fixtures/unknown-method.json",
    "fixtures/unsupported-required.json",
    "manifest.json",
    "samples/reference_adapter.mjs",
)


def test_installed_kit_has_one_exact_manifest_and_asset_inventory():
    manifest = load_conformance_manifest()

    assert manifest.kit_version == CONFORMANCE_KIT_VERSION
    assert manifest.protocol_version == "1.0.0"
    assert tuple(case.case_id for case in manifest.cases) == EXPECTED_CASE_IDS
    assert conformance_asset_names() == EXPECTED_ASSETS
    assert {
        case.fixture for case in manifest.cases
    } == {
        name for name in EXPECTED_ASSETS if name.startswith("fixtures/")
    }

    for name in EXPECTED_ASSETS:
        content = read_conformance_asset(name)
        assert content
        if name.endswith((".json", ".mjs")):
            assert content.endswith(b"\n")
            assert not content.endswith(b"\n\n")

    for case in manifest.cases:
        fixture = load_conformance_fixture(case.fixture)
        assert fixture.case_id == case.case_id
        assert fixture.procedure is case.procedure
        assert fixture.steps
        assert canonical_conformance_json(fixture) == read_conformance_asset(
            case.fixture
        )


def test_sample_is_dependency_free_and_payloads_do_not_name_a_language():
    manifest = load_conformance_manifest()
    sources = {
        read_conformance_asset(name).decode()
        for name in {manifest.sample_adapter, manifest.fault_adapter}
    }

    for source in sources:
        assert re.search(r"(?m)^\s*(?:import|export)\b", source) is None
        assert "require(" not in source
        assert "python" not in source.lower()
        assert "node_modules" not in source

    for name in EXPECTED_ASSETS:
        if not name.startswith("fixtures/"):
            continue
        fixture = read_conformance_asset(name).decode()
        assert '"language"' not in fixture
        assert '"framework"' not in fixture
        assert '"python"' not in fixture.lower()


def test_kit_index_and_extraction_are_exact_and_never_overwrite(
    tmp_path: Path,
):
    index = conformance_kit_index()
    assert tuple(asset.name for asset in index.assets) == EXPECTED_ASSETS
    assert tuple(asset.name for asset in index.assets) == tuple(
        sorted(asset.name for asset in index.assets)
    )

    destination = tmp_path / "kit"
    extracted = extract_conformance_kit(destination)
    assert extracted == index
    for asset in index.assets:
        path = destination.joinpath(*asset.name.split("/"))
        assert path.is_file()
        assert path.stat().st_size == asset.size
        assert read_conformance_asset(asset.name) == path.read_bytes()

    marker = destination / "user-owned"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        extract_conformance_kit(destination)
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert canonical_conformance_json(index) == canonical_conformance_json(
        conformance_kit_index()
    )
