from __future__ import annotations

import sys
from pathlib import Path

from ucf.adapter_conformance import (
    CaseStatus,
    ConformanceTimeouts,
    RunStatus,
    load_conformance_fixture,
    load_conformance_manifest,
    run_conformance,
)
from ucf.adapter_conformance.models import SendStep
from ucf.adapter_conformance.runner import _RawAdapterSession
from ucf.adapter_protocol import ErrorResponse, ProtocolCode

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADAPTER = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "inventory_reference_adapter.py"
)
FIXTURE_ROOT = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "brownfield" / "python_legacy_quote"
)
TIMEOUTS = ConformanceTimeouts(
    response=1.0,
    write=1.0,
    shutdown=1.0,
    terminate=0.2,
    kill=0.5,
)


def _command(*, conformance: bool = False) -> tuple[str, ...]:
    command = (
        sys.executable,
        "-B",
        "-X",
        "utf8",
        str(ADAPTER),
    )
    return (*command, "--conformance") if conformance else command


def _manifest_for(*case_ids: str):
    manifest = load_conformance_manifest()
    selected = tuple(case for case in manifest.cases if case.case_id in case_ids)
    assert len(selected) == len(case_ids)
    return manifest.model_copy(update={"cases": selected, "fault_profiles": ()})


def _run(*case_ids: str, conformance: bool = False):
    return run_conformance(
        command=_command(conformance=conformance),
        cwd=FIXTURE_ROOT,
        environment={"PYTHONDONTWRITEBYTECODE": "1"},
        timeouts=TIMEOUTS,
        manifest=_manifest_for(*case_ids),
    )


def _assert_case_passes(case_id: str) -> None:
    report = _run(case_id)

    assert report.status is RunStatus.CONFORMANT
    assert len(report.cases) == 1
    assert report.cases[0].case_id == case_id
    assert report.cases[0].status is CaseStatus.PASSED


def test_known_unnegotiated_operation_is_capability_error() -> None:
    _assert_case_passes("case.capability_gate")


def test_malformed_shutdown_params_fail_before_lifecycle() -> None:
    _assert_case_passes("case.invalid_params")


def test_control_profile_supports_targeted_cancellation() -> None:
    _assert_case_passes("case.targeted_cancellation")


def test_shutdown_is_rejected_while_control_request_is_pending() -> None:
    _assert_case_passes("case.shutdown_pending")


def test_explicit_conformance_mode_passes_the_full_public_profile() -> None:
    manifest = load_conformance_manifest()
    report = _run(
        *(case.case_id for case in manifest.cases),
        conformance=True,
    )

    assert report.status is RunStatus.CONFORMANT
    assert len(report.cases) == len(manifest.cases) == 17
    assert all(result.status is CaseStatus.PASSED for result in report.cases)


def test_adapter_rejects_required_unimplemented_capabilities() -> None:
    manifest = load_conformance_manifest()
    case = next(
        item for item in manifest.cases if item.case_id == "case.operation_families"
    )
    fixture = load_conformance_fixture(case.fixture)
    initialize = fixture.steps[0]
    assert isinstance(initialize, SendStep)
    session = _RawAdapterSession(
        command=_command(),
        cwd=FIXTURE_ROOT,
        environment={"PYTHONDONTWRITEBYTECODE": "1"},
        timeouts=TIMEOUTS,
    )
    try:
        session.send(initialize.frame)
        response = session.receive()
    finally:
        session.terminate()

    assert isinstance(response, ErrorResponse)
    assert response.error.data.ucf_code is ProtocolCode.UNSUPPORTED_CAPABILITY
    assert response.error.data.category.value == "protocol_failure"
