from __future__ import annotations

import json

import pytest

from tests.change_governance._support import (
    base_behavior,
    change_pair,
    output_requiredness_final,
)
from ucf.change_governance import (
    ChangeGovernanceErrorCode,
    ChangeGovernanceValidationError,
    ImpactReport,
    canonical_change_governance_json,
    derive_impact_report,
    parse_impact_report_json,
)
from ucf.change_governance.models import ImpactFinding


class _EmptyImpactFinding(ImpactFinding):
    pass


class _HiddenTuple(tuple):
    hidden: bool


class _HiddenString(str):
    hidden: bool


def _report() -> ImpactReport:
    base = base_behavior()
    final = output_requiredness_final(base)
    proposal, delta = change_pair(base, final)
    return derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )


def test_impact_report_has_one_strict_canonical_round_trip() -> None:
    report = _report()

    first = canonical_change_governance_json(report)
    second = canonical_change_governance_json(report)

    assert first == second
    assert first.endswith(b"\n")
    assert parse_impact_report_json(first) == report


def test_duplicate_and_unknown_members_are_rejected_explicitly() -> None:
    canonical = canonical_change_governance_json(_report())
    duplicate = canonical.replace(
        b'"change_governance_version":"1.0.0",',
        (b'"change_governance_version":"1.0.0","change_governance_version":"1.0.0",'),
        1,
    )
    payload = json.loads(canonical)
    payload["unexpected"] = True

    with pytest.raises(ChangeGovernanceValidationError) as duplicate_error:
        parse_impact_report_json(duplicate)
    with pytest.raises(ChangeGovernanceValidationError) as unknown_error:
        parse_impact_report_json(json.dumps(payload))

    assert duplicate_error.value.code is ChangeGovernanceErrorCode.DUPLICATE_JSON_MEMBER
    assert unknown_error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("change_governance_version", "2.0.0"),
        ("schema_uri", "urn:ucf:change-governance:impact-report:2.0.0"),
        ("procedure_uri", "urn:ucf:change-governance:other-procedure:1.0.0"),
    ],
)
def test_unsupported_wire_coordinates_are_rejected(
    field: str,
    value: str,
) -> None:
    payload = json.loads(canonical_change_governance_json(_report()))
    payload[field] = value

    with pytest.raises(ChangeGovernanceValidationError) as error:
        parse_impact_report_json(json.dumps(payload))

    assert error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE


def test_direct_python_subclasses_and_corrupted_copies_are_rejected() -> None:
    report = _report()

    class HiddenImpactReport(ImpactReport):
        hidden: str

    hidden = HiddenImpactReport(
        **report.model_dump(),
        hidden="must not serialize",
    )
    corrupted = report.model_copy(update={"change_governance_version": "2.0.0"})

    with pytest.raises(ChangeGovernanceValidationError) as hidden_error:
        canonical_change_governance_json(hidden)
    with pytest.raises(ChangeGovernanceValidationError) as corrupted_error:
        canonical_change_governance_json(corrupted)

    assert hidden_error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE
    assert corrupted_error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE


def test_invisible_nested_model_subclass_is_rejected_at_exact_location() -> None:
    report = _report()
    first = _EmptyImpactFinding.model_validate(
        report.findings[0].model_dump(mode="python")
    )
    corrupted = report.model_copy(update={"findings": (first, *report.findings[1:])})

    with pytest.raises(ChangeGovernanceValidationError) as error:
        canonical_change_governance_json(corrupted)

    assert error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE
    assert error.value.location == "$.findings[0]"


def test_nested_container_and_scalar_subclasses_are_rejected() -> None:
    report = _report()
    findings = _HiddenTuple(report.findings)
    findings.hidden = True
    corrupt_container = report.model_copy(update={"findings": findings})
    kind = _HiddenString("impact_report")
    kind.hidden = True
    corrupt_scalar = report.model_copy(update={"kind": kind})

    with pytest.raises(ChangeGovernanceValidationError) as container_error:
        canonical_change_governance_json(corrupt_container)
    with pytest.raises(ChangeGovernanceValidationError) as scalar_error:
        canonical_change_governance_json(corrupt_scalar)

    assert container_error.value.location == "$.findings"
    assert scalar_error.value.location == "$.kind"
