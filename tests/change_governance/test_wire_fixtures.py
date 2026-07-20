from __future__ import annotations

from collections.abc import Callable

import pytest

from ucf.change_governance import (
    ChangeGovernanceErrorCode,
    ChangeGovernanceValidationError,
    DecisionAssessment,
    DecisionDeclaration,
    GateEvaluation,
    ImpactReport,
    parse_decision_assessment_json,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
    parse_impact_report_json,
    validate_decision_assessment,
    validate_decision_declaration,
    validate_gate_evaluation,
    validate_impact_report,
)
from ucf.change_lifecycle import (
    parse_behavior_delta_json,
    parse_change_proposal_json,
)
from ucf.ir import parse_ir_json

from . import _fixture_factory as fixture_factory
from ._fixture_factory import (
    DEFAULT_FIXTURE_DIRECTORY,
    render_wire_fixtures,
)

type GovernanceDocument = (
    ImpactReport | DecisionAssessment | DecisionDeclaration | GateEvaluation
)
type Parser = Callable[[str | bytes], GovernanceDocument]


def _fixture(relative_path: str) -> bytes:
    return (DEFAULT_FIXTURE_DIRECTORY / relative_path).read_bytes()


def test_committed_governance_fixtures_are_current_and_contextually_valid() -> None:
    rendered = render_wire_fixtures()
    assert len(rendered) == 29
    for path, content in rendered.items():
        assert path.read_text(encoding="utf-8") == content

    base = parse_ir_json(_fixture("context/base-behavior.json"))
    proposal = parse_change_proposal_json(_fixture("context/proposal.json"))
    for profile in ("compatible", "breaking"):
        final = parse_ir_json(_fixture(f"context/{profile}-final-behavior.json"))
        delta = parse_behavior_delta_json(_fixture(f"context/{profile}-delta.json"))
        impact = parse_impact_report_json(
            _fixture(f"positive/{profile}-impact-report.json")
        )
        assessment = parse_decision_assessment_json(
            _fixture(f"positive/{profile}-assessment.json")
        )
        validate_impact_report(
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        validate_decision_assessment(
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        if profile == "compatible":
            gate = parse_gate_evaluation_json(_fixture("positive/compatible-gate.json"))
            validate_gate_evaluation(
                gate,
                assessment,
                impact,
                None,
                proposal,
                delta,
                base_behavior=base,
                final_behavior=final,
            )
            continue
        for outcome in ("approved", "rejected"):
            declaration = parse_decision_declaration_json(
                _fixture(f"positive/breaking-{outcome}-declaration.json")
            )
            gate = parse_gate_evaluation_json(
                _fixture(f"positive/breaking-{outcome}-gate.json")
            )
            validate_decision_declaration(
                declaration,
                assessment,
                impact,
                proposal,
                delta,
                base_behavior=base,
                final_behavior=final,
            )
            validate_gate_evaluation(
                gate,
                assessment,
                impact,
                declaration,
                proposal,
                delta,
                base_behavior=base,
                final_behavior=final,
            )
        required_gate = parse_gate_evaluation_json(
            _fixture("positive/breaking-required-gate.json")
        )
        validate_gate_evaluation(
            required_gate,
            assessment,
            impact,
            None,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )


@pytest.mark.parametrize(
    ("filename", "parser", "expected_code"),
    [
        (
            "duplicate-json-member.json",
            parse_impact_report_json,
            ChangeGovernanceErrorCode.DUPLICATE_JSON_MEMBER,
        ),
        (
            "unknown-root-field.json",
            parse_impact_report_json,
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
        ),
        (
            "unsupported-version.json",
            parse_impact_report_json,
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
        ),
        (
            "noncanonical-edge-order.json",
            parse_impact_report_json,
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
        ),
        (
            "out-of-range-witness.json",
            parse_impact_report_json,
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
        ),
        (
            "incomplete-assessment.json",
            parse_decision_assessment_json,
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
        ),
        (
            "forged-pass-gate.json",
            parse_gate_evaluation_json,
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
        ),
    ],
)
def test_structural_negative_fixtures_fail_explicitly(
    filename: str,
    parser: Parser,
    expected_code: ChangeGovernanceErrorCode,
) -> None:
    with pytest.raises(ChangeGovernanceValidationError) as error:
        parser(_fixture(f"invalid/{filename}"))

    assert error.value.code is expected_code


def test_contextual_negative_fixtures_cannot_bypass_the_predecessor_chain() -> None:
    base = parse_ir_json(_fixture("context/base-behavior.json"))
    proposal = parse_change_proposal_json(_fixture("context/proposal.json"))
    compatible_final = parse_ir_json(_fixture("context/compatible-final-behavior.json"))
    compatible_delta = parse_behavior_delta_json(
        _fixture("context/compatible-delta.json")
    )
    compatible_impact = parse_impact_report_json(
        _fixture("positive/compatible-impact-report.json")
    )
    compatible_assessment = parse_decision_assessment_json(
        _fixture("positive/compatible-assessment.json")
    )
    breaking_final = parse_ir_json(_fixture("context/breaking-final-behavior.json"))
    breaking_delta = parse_behavior_delta_json(_fixture("context/breaking-delta.json"))
    breaking_impact = parse_impact_report_json(
        _fixture("positive/breaking-impact-report.json")
    )
    breaking_assessment = parse_decision_assessment_json(
        _fixture("positive/breaking-assessment.json")
    )
    approved = parse_decision_declaration_json(
        _fixture("positive/breaking-approved-declaration.json")
    )

    cases = (
        (
            lambda: validate_decision_assessment(
                parse_decision_assessment_json(
                    _fixture("invalid/derived-downgrade.json")
                ),
                breaking_impact,
                proposal,
                breaking_delta,
                base_behavior=base,
                final_behavior=breaking_final,
            ),
            ChangeGovernanceErrorCode.DERIVED_CLASS_MISMATCH,
        ),
        (
            lambda: validate_decision_assessment(
                parse_decision_assessment_json(
                    _fixture("invalid/stale-impact-assessment.json")
                ),
                compatible_impact,
                proposal,
                compatible_delta,
                base_behavior=base,
                final_behavior=compatible_final,
            ),
            ChangeGovernanceErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
        (
            lambda: validate_decision_declaration(
                parse_decision_declaration_json(
                    _fixture("invalid/extra-decision.json")
                ),
                breaking_assessment,
                breaking_impact,
                proposal,
                breaking_delta,
                base_behavior=base,
                final_behavior=breaking_final,
            ),
            ChangeGovernanceErrorCode.DECISION_SET_MISMATCH,
        ),
        (
            lambda: validate_decision_declaration(
                parse_decision_declaration_json(
                    _fixture("invalid/stale-assessment-declaration.json")
                ),
                breaking_assessment,
                breaking_impact,
                proposal,
                breaking_delta,
                base_behavior=base,
                final_behavior=breaking_final,
            ),
            ChangeGovernanceErrorCode.CONTENT_IDENTITY_MISMATCH,
        ),
        (
            lambda: validate_decision_declaration(
                parse_decision_declaration_json(
                    _fixture("invalid/irrelevant-declaration.json")
                ),
                compatible_assessment,
                compatible_impact,
                proposal,
                compatible_delta,
                base_behavior=base,
                final_behavior=compatible_final,
            ),
            ChangeGovernanceErrorCode.DECISION_SET_MISMATCH,
        ),
        (
            lambda: validate_gate_evaluation(
                parse_gate_evaluation_json(
                    _fixture("invalid/stale-declaration-gate.json")
                ),
                breaking_assessment,
                breaking_impact,
                approved,
                proposal,
                breaking_delta,
                base_behavior=base,
                final_behavior=breaking_final,
            ),
            ChangeGovernanceErrorCode.SUMMARY_MISMATCH,
        ),
    )
    for validate, expected_code in cases:
        with pytest.raises(ChangeGovernanceValidationError) as error:
            validate()
        assert error.value.code is expected_code


def test_fixture_freshness_check_rejects_unexpected_files(
    tmp_path,
    monkeypatch,
) -> None:
    fixture_directory = tmp_path / "fixtures"
    monkeypatch.setattr(
        fixture_factory,
        "DEFAULT_FIXTURE_DIRECTORY",
        fixture_directory,
    )
    assert fixture_factory.main([]) == 0
    unexpected = fixture_directory / "unexpected.json"
    unexpected.write_text("{}\n", encoding="utf-8")

    assert fixture_factory.main(["--check"]) == 1
