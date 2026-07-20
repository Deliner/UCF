from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_conformance import (
    CONFORMANCE_KIT_VERSION,
    CaseProcedure,
    CaseStatus,
    ConformanceAsset,
    ConformanceCase,
    ConformanceCaseResult,
    ConformanceExitCode,
    ConformanceFixture,
    ConformanceKitIndex,
    ConformanceManifest,
    ConformanceReport,
    ExpectStep,
    FaultProfile,
    RunStatus,
    SendStep,
    canonical_conformance_json,
    parse_conformance_fixture_json,
    parse_conformance_kit_index_json,
    parse_conformance_manifest_json,
    parse_conformance_report_json,
    validate_report_against_manifest,
)
from ucf.adapter_protocol import ErrorCategory, ProtocolCode


def _case(
    case_id: str,
    *,
    procedure: CaseProcedure = CaseProcedure.INITIALIZE_SHUTDOWN,
    fixture: str = "fixtures/initialize-shutdown.json",
    required_capabilities: tuple[str, ...] = (),
) -> ConformanceCase:
    return ConformanceCase(
        kind="conformance_case",
        case_id=case_id,
        surface="universal",
        isolation="fresh_process",
        procedure=procedure,
        fixture=fixture,
        required_capabilities=required_capabilities,
    )


def _manifest() -> ConformanceManifest:
    return ConformanceManifest(
        kind="adapter_conformance_manifest",
        kit_version=CONFORMANCE_KIT_VERSION,
        protocol_version="1.0.0",
        profile="org.ucf.adapter-conformance.full",
        control_schema_uri=(
            "urn:ucf:adapter-conformance:control:1.0.0"
        ),
        cases=(
            _case("case.initialize_shutdown"),
            _case(
                "case.capability_gate",
                procedure=CaseProcedure.CAPABILITY_GATE,
                fixture="fixtures/capability-gate.json",
                required_capabilities=("org.ucf.adapter.inventory",),
            ),
        ),
        fault_profiles=(
            FaultProfile(
                kind="fault_profile",
                fault_id="fault.accepts_unnegotiated",
                arguments=("--fault", "accepts-unnegotiated"),
                expected_case_id="case.capability_gate",
            ),
        ),
        sample_adapter="samples/reference_adapter.mjs",
        fault_adapter="samples/fault_adapter.mjs",
    )


def _report(
    *results: ConformanceCaseResult,
    status: RunStatus = RunStatus.CONFORMANT,
) -> ConformanceReport:
    return ConformanceReport(
        kind="adapter_conformance_report",
        kit_version=CONFORMANCE_KIT_VERSION,
        protocol_version="1.0.0",
        profile="org.ucf.adapter-conformance.full",
        status=status,
        cases=results,
    )


def _result(
    case_id: str,
    status: CaseStatus = CaseStatus.PASSED,
) -> ConformanceCaseResult:
    return ConformanceCaseResult(
        kind="conformance_case_result",
        case_id=case_id,
        status=status,
        expected="success",
        actual="success" if status is CaseStatus.PASSED else "protocol_error",
        protocol_code=None,
    )


def test_manifest_and_report_are_exact_independently_versioned_contracts():
    manifest = _manifest()
    report = _report(
        _result("case.initialize_shutdown"),
        _result("case.capability_gate"),
    )

    assert CONFORMANCE_KIT_VERSION == "1.0.0"
    assert manifest.kit_version == "1.0.0"
    assert manifest.protocol_version == "1.0.0"
    assert report.kit_version == "1.0.0"
    assert ConformanceExitCode.CONFORMANT == 0
    assert ConformanceExitCode.NON_CONFORMANT == 1
    assert ConformanceExitCode.RUNNER_ERROR == 3

    with pytest.raises(ValidationError):
        ConformanceManifest.model_validate_json(
            json.dumps(
                {
                    **manifest.model_dump(mode="json"),
                    "future_field": True,
                }
            )
        )
    with pytest.raises(ValidationError):
        ConformanceReport.model_validate_json(
            json.dumps(
                {
                    **report.model_dump(mode="json"),
                    "duration_seconds": 1,
                }
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kit_version", "1.0.1"),
        ("protocol_version", "1.0.1"),
        ("profile", "python.pytest"),
        ("control_schema_uri", "not a uri"),
    ],
)
def test_manifest_rejects_incompatible_coordinates(field: str, value: str):
    payload = _manifest().model_dump(mode="json")
    payload[field] = value

    with pytest.raises(ValidationError):
        ConformanceManifest.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "path",
    [
        "",
        ".",
        "../fixture.json",
        "fixtures/../fixture.json",
        "/tmp/fixture.json",
        r"fixtures\fixture.json",
        "fixtures//fixture.json",
    ],
)
def test_manifest_rejects_unsafe_resource_paths(path: str):
    payload = _manifest().model_dump(mode="json")
    payload["cases"][0]["fixture"] = path

    with pytest.raises(ValidationError):
        ConformanceManifest.model_validate_json(json.dumps(payload))


def test_case_rejects_unimplemented_isolation_modes():
    payload = _case("case.initialize_shutdown").model_dump(mode="json")
    payload["isolation"] = "shared_session"

    with pytest.raises(ValidationError, match="fresh_process"):
        ConformanceCase.model_validate_json(json.dumps(payload))


def test_manifest_rejects_duplicate_or_broken_case_and_fault_identities():
    payload = _manifest().model_dump(mode="json")
    payload["cases"].append(payload["cases"][0])
    with pytest.raises(ValidationError, match="case IDs"):
        ConformanceManifest.model_validate_json(json.dumps(payload))

    payload = _manifest().model_dump(mode="json")
    payload["fault_profiles"].append(payload["fault_profiles"][0])
    with pytest.raises(ValidationError, match="fault IDs"):
        ConformanceManifest.model_validate_json(json.dumps(payload))

    payload = _manifest().model_dump(mode="json")
    payload["fault_profiles"][0]["expected_case_id"] = "case.unknown"
    with pytest.raises(ValidationError, match="unknown case"):
        ConformanceManifest.model_validate_json(json.dumps(payload))

    case = _case("case.initialize_shutdown").model_dump(mode="json")
    case["required_capabilities"] = [
        "org.ucf.adapter.inventory",
        "org.ucf.adapter.inventory",
    ]
    with pytest.raises(ValidationError, match="required capabilities"):
        ConformanceCase.model_validate_json(json.dumps(case))


@pytest.mark.parametrize(
    ("status", "case_status"),
    [
        (RunStatus.CONFORMANT, CaseStatus.FAILED),
        (RunStatus.CONFORMANT, CaseStatus.ERROR),
        (RunStatus.NON_CONFORMANT, CaseStatus.PASSED),
        (RunStatus.RUNNER_ERROR, CaseStatus.FAILED),
    ],
)
def test_report_status_is_derived_from_case_results(
    status: RunStatus,
    case_status: CaseStatus,
):
    payload = _report(
        _result("case.initialize_shutdown"),
    ).model_dump(mode="json")
    payload["status"] = status.value
    payload["cases"][0]["status"] = case_status.value
    payload["cases"][0]["actual"] = (
        "success"
        if case_status is CaseStatus.PASSED
        else "protocol_error"
    )

    with pytest.raises(ValidationError, match="status"):
        ConformanceReport.model_validate_json(json.dumps(payload))


def test_report_rejects_duplicates_and_must_match_manifest_order_exactly():
    duplicate = _report(
        _result("case.initialize_shutdown"),
    ).model_dump(mode="json")
    duplicate["cases"].append(duplicate["cases"][0])
    with pytest.raises(ValidationError, match="case IDs"):
        ConformanceReport.model_validate_json(json.dumps(duplicate))

    manifest = _manifest()
    reversed_report = _report(
        _result("case.capability_gate"),
        _result("case.initialize_shutdown"),
    )
    with pytest.raises(ValueError, match="exactly match"):
        validate_report_against_manifest(reversed_report, manifest)

    missing_report = _report(_result("case.initialize_shutdown"))
    with pytest.raises(ValueError, match="exactly match"):
        validate_report_against_manifest(missing_report, manifest)


def test_manifest_parser_is_strict_and_canonical_report_is_byte_stable():
    manifest = _manifest()
    raw = canonical_conformance_json(manifest)

    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert parse_conformance_manifest_json(raw) == manifest
    assert canonical_conformance_json(parse_conformance_manifest_json(raw)) == raw
    assert json.loads(raw)["kind"] == "adapter_conformance_manifest"

    duplicate_member = raw.replace(
        b'"kind":"adapter_conformance_manifest"',
        (
            b'"kind":"adapter_conformance_manifest",'
            b'"kind":"adapter_conformance_manifest"'
        ),
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_conformance_manifest_json(duplicate_member)


def test_fixture_is_a_closed_ordered_wire_transcript():
    fixture = ConformanceFixture(
        kind="adapter_conformance_fixture",
        kit_version="1.0.0",
        case_id="case.initialize_shutdown",
        procedure=CaseProcedure.INITIALIZE_SHUTDOWN,
        steps=(
            SendStep(
                kind="send",
                step_id="send.initialize",
                frame='{"id":"initialize","jsonrpc":"2.0"}',
            ),
            ExpectStep(
                kind="expect",
                step_id="expect.initialize",
                request_id="initialize",
                outcome="success",
                result_kind="initialize_result",
                error_category=None,
                protocol_code=None,
                jsonrpc_code=None,
                selected_capabilities=(),
                expected_payload=None,
            ),
        ),
    )

    raw = canonical_conformance_json(fixture)
    assert parse_conformance_fixture_json(raw) == fixture

    unknown = fixture.model_dump(mode="json")
    unknown["steps"][0]["future"] = True
    with pytest.raises(ValidationError):
        ConformanceFixture.model_validate_json(json.dumps(unknown))

    duplicate = fixture.model_dump(mode="json")
    duplicate["steps"].append(duplicate["steps"][0])
    with pytest.raises(ValidationError, match="step IDs"):
        ConformanceFixture.model_validate_json(json.dumps(duplicate))


def test_fixture_rejects_ambiguous_expectations_and_non_frame_bytes():
    success = ExpectStep(
        kind="expect",
        step_id="expect.success",
        request_id="request",
        outcome="success",
        result_kind="shutdown_result",
        error_category=None,
        protocol_code=None,
        jsonrpc_code=None,
        selected_capabilities=(),
        expected_payload=None,
    ).model_dump(mode="json")
    success["protocol_code"] = "invalid_lifecycle"
    with pytest.raises(ValidationError, match="success"):
        ExpectStep.model_validate_json(json.dumps(success))

    error = ExpectStep(
        kind="expect",
        step_id="expect.error",
        request_id="request",
        outcome="error",
        result_kind=None,
        error_category=ErrorCategory.PROTOCOL_FAILURE,
        protocol_code=ProtocolCode.INVALID_LIFECYCLE,
        jsonrpc_code=-32000,
        selected_capabilities=(),
        expected_payload=None,
    ).model_dump(mode="json")
    error["jsonrpc_code"] = None
    with pytest.raises(ValidationError, match="error"):
        ExpectStep.model_validate_json(json.dumps(error))

    with pytest.raises(ValidationError, match="terminal LF"):
        SendStep(
            kind="send",
            step_id="send.invalid",
            frame='{"jsonrpc":"2.0"}\n',
        )


def test_fixture_rejects_result_specific_success_coordinate_mismatches():
    success = ExpectStep(
        kind="expect",
        step_id="expect.success",
        request_id="request",
        outcome="success",
        result_kind="shutdown_result",
        error_category=None,
        protocol_code=None,
        jsonrpc_code=None,
        selected_capabilities=(),
        expected_payload=None,
    ).model_dump(mode="json")

    unknown_result = {**success, "result_kind": "future_result"}
    with pytest.raises(ValidationError, match="result"):
        ExpectStep.model_validate_json(json.dumps(unknown_result))

    shutdown_capabilities = {
        **success,
        "selected_capabilities": ["org.ucf.adapter.inventory"],
    }
    with pytest.raises(ValidationError, match="shutdown"):
        ExpectStep.model_validate_json(json.dumps(shutdown_capabilities))

    operation_without_payload = {
        **success,
        "result_kind": "inventory_result",
    }
    with pytest.raises(ValidationError, match="operation"):
        ExpectStep.model_validate_json(json.dumps(operation_without_payload))

    duplicate_capabilities = {
        **success,
        "result_kind": "initialize_result",
        "selected_capabilities": [
            "org.ucf.adapter.inventory",
            "org.ucf.adapter.inventory",
        ],
    }
    with pytest.raises(ValidationError, match="unique"):
        ExpectStep.model_validate_json(json.dumps(duplicate_capabilities))


def test_kit_index_is_closed_sorted_and_digest_exact():
    index = ConformanceKitIndex(
        kind="adapter_conformance_kit_index",
        kit_version="1.0.0",
        protocol_version="1.0.0",
        assets=(
            ConformanceAsset(
                kind="conformance_asset",
                name="manifest.json",
                sha256="0" * 64,
                size=1,
            ),
            ConformanceAsset(
                kind="conformance_asset",
                name="samples/reference_adapter.mjs",
                sha256="f" * 64,
                size=2,
            ),
        ),
    )
    assert canonical_conformance_json(index).endswith(b"\n")

    reversed_index = index.model_dump(mode="json")
    reversed_index["assets"].reverse()
    with pytest.raises(ValidationError, match="sorted"):
        ConformanceKitIndex.model_validate_json(json.dumps(reversed_index))

    duplicate = index.model_dump(mode="json")
    duplicate["assets"].append(duplicate["assets"][0])
    with pytest.raises(ValidationError, match="unique"):
        ConformanceKitIndex.model_validate_json(json.dumps(duplicate))

    invalid_digest = index.model_dump(mode="json")
    invalid_digest["assets"][0]["sha256"] = "ABC"
    with pytest.raises(ValidationError):
        ConformanceKitIndex.model_validate_json(json.dumps(invalid_digest))


def test_report_and_index_public_parsers_reject_duplicate_json_members():
    report = _report(_result("case.initialize_shutdown"))
    report_raw = canonical_conformance_json(report)
    assert parse_conformance_report_json(report_raw) == report
    duplicate_report = report_raw.replace(
        b'"kind":"adapter_conformance_report"',
        (
            b'"kind":"adapter_conformance_report",'
            b'"kind":"adapter_conformance_report"'
        ),
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_conformance_report_json(duplicate_report)

    index = ConformanceKitIndex(
        kind="adapter_conformance_kit_index",
        kit_version="1.0.0",
        protocol_version="1.0.0",
        assets=(
            ConformanceAsset(
                kind="conformance_asset",
                name="manifest.json",
                sha256="0" * 64,
                size=1,
            ),
        ),
    )
    index_raw = canonical_conformance_json(index)
    assert parse_conformance_kit_index_json(index_raw) == index
    duplicate_index = index_raw.replace(
        b'"kind":"adapter_conformance_kit_index"',
        (
            b'"kind":"adapter_conformance_kit_index",'
            b'"kind":"adapter_conformance_kit_index"'
        ),
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_conformance_kit_index_json(duplicate_index)
