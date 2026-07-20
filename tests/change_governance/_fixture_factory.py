from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from tests.change_governance._support import (
    additive_root_final,
    base_behavior,
    root_loss_final,
)
from tests.change_lifecycle._fixture_factory import proposal
from ucf.change_governance import (
    AssessmentBasis,
    DecisionAssessment,
    DecisionClass,
    DecisionClassAssessment,
    DecisionDeclaration,
    DecisionDisposition,
    DecisionEvidence,
    DecisionOutcome,
    DeclaredBasis,
    DeclaredDecision,
    GateEvaluation,
    ImpactReport,
    canonical_change_governance_json,
    create_decision_assessment,
    create_decision_declaration,
    decision_assessment_ref,
    derive_impact_report,
    evaluate_change_gate,
    impact_report_ref,
)
from ucf.change_lifecycle import (
    BehaviorDelta,
    ChangeProposal,
    canonical_change_lifecycle_json,
    derive_behavior_delta,
)
from ucf.ir import canonical_ir_json
from ucf.ir.models import BehaviorIR, Digest

DEFAULT_FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "fixtures" / "change_governance" / "v1"
)


@dataclass(frozen=True)
class GovernanceProfile:
    base: BehaviorIR
    final: BehaviorIR
    proposal: ChangeProposal
    delta: BehaviorDelta
    impact: ImpactReport
    assessment: DecisionAssessment
    declaration: DecisionDeclaration | None
    gate: GateEvaluation


@dataclass(frozen=True)
class GovernanceFixtures:
    compatible: GovernanceProfile
    breaking_required: GovernanceProfile
    breaking_approved: GovernanceProfile
    breaking_rejected: GovernanceProfile


def governance_fixtures() -> GovernanceFixtures:
    base = base_behavior()
    change_proposal = proposal(base)
    compatible_final = additive_root_final(base)
    compatible_delta = derive_behavior_delta(
        change_proposal,
        base,
        compatible_final,
    )
    compatible_impact = derive_impact_report(
        change_proposal,
        compatible_delta,
        base_behavior=base,
        final_behavior=compatible_final,
    )
    compatible_assessment = create_decision_assessment(
        compatible_impact,
        tuple(_classification(item) for item in DecisionClass),
        change_proposal,
        compatible_delta,
        base_behavior=base,
        final_behavior=compatible_final,
    )
    compatible_gate = evaluate_change_gate(
        compatible_assessment,
        compatible_impact,
        None,
        change_proposal,
        compatible_delta,
        base_behavior=base,
        final_behavior=compatible_final,
    )
    compatible = GovernanceProfile(
        base=base,
        final=compatible_final,
        proposal=change_proposal,
        delta=compatible_delta,
        impact=compatible_impact,
        assessment=compatible_assessment,
        declaration=None,
        gate=compatible_gate,
    )

    breaking_final = root_loss_final(base)
    breaking_delta = derive_behavior_delta(
        change_proposal,
        base,
        breaking_final,
    )
    breaking_impact = derive_impact_report(
        change_proposal,
        breaking_delta,
        base_behavior=base,
        final_behavior=breaking_final,
    )
    breaking_assessment = create_decision_assessment(
        breaking_impact,
        tuple(
            _classification(item)
            for item in DecisionClass
            if item not in breaking_impact.derived_required_classes
        ),
        change_proposal,
        breaking_delta,
        base_behavior=base,
        final_behavior=breaking_final,
    )
    required_gate = evaluate_change_gate(
        breaking_assessment,
        breaking_impact,
        None,
        change_proposal,
        breaking_delta,
        base_behavior=base,
        final_behavior=breaking_final,
    )
    breaking_required = GovernanceProfile(
        base=base,
        final=breaking_final,
        proposal=change_proposal,
        delta=breaking_delta,
        impact=breaking_impact,
        assessment=breaking_assessment,
        declaration=None,
        gate=required_gate,
    )

    approved_declaration = _declaration(
        breaking_assessment,
        breaking_impact,
        change_proposal,
        breaking_delta,
        base=base,
        final=breaking_final,
        outcome=DecisionOutcome.APPROVED,
    )
    approved_gate = evaluate_change_gate(
        breaking_assessment,
        breaking_impact,
        approved_declaration,
        change_proposal,
        breaking_delta,
        base_behavior=base,
        final_behavior=breaking_final,
    )
    breaking_approved = GovernanceProfile(
        base=base,
        final=breaking_final,
        proposal=change_proposal,
        delta=breaking_delta,
        impact=breaking_impact,
        assessment=breaking_assessment,
        declaration=approved_declaration,
        gate=approved_gate,
    )

    rejected_declaration = _declaration(
        breaking_assessment,
        breaking_impact,
        change_proposal,
        breaking_delta,
        base=base,
        final=breaking_final,
        outcome=DecisionOutcome.REJECTED,
    )
    rejected_gate = evaluate_change_gate(
        breaking_assessment,
        breaking_impact,
        rejected_declaration,
        change_proposal,
        breaking_delta,
        base_behavior=base,
        final_behavior=breaking_final,
    )
    breaking_rejected = GovernanceProfile(
        base=base,
        final=breaking_final,
        proposal=change_proposal,
        delta=breaking_delta,
        impact=breaking_impact,
        assessment=breaking_assessment,
        declaration=rejected_declaration,
        gate=rejected_gate,
    )
    return GovernanceFixtures(
        compatible=compatible,
        breaking_required=breaking_required,
        breaking_approved=breaking_approved,
        breaking_rejected=breaking_rejected,
    )


def _classification(
    decision_class: DecisionClass,
) -> DecisionClassAssessment:
    return DecisionClassAssessment(
        kind="decision_class_assessment",
        decision_class=decision_class,
        disposition=DecisionDisposition.DOES_NOT_APPLY,
        basis=AssessmentBasis.DECLARED,
        declared_basis=DeclaredBasis(
            kind="declared_basis",
            source_uri=f"urn:ucf:fixture:assessment:{decision_class.value}",
            source_digest=_digest("a"),
            summary=f"fixture classified {decision_class.value}",
        ),
    )


def _declaration(
    assessment: DecisionAssessment,
    impact: ImpactReport,
    change_proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base: BehaviorIR,
    final: BehaviorIR,
    outcome: DecisionOutcome,
) -> DecisionDeclaration:
    decision_class = DecisionClass.PUBLIC_CONTRACT
    decision = DeclaredDecision(
        kind="declared_decision",
        decision_class=decision_class,
        outcome=outcome,
        evidence=DecisionEvidence(
            kind="decision_evidence",
            source_uri=(
                f"urn:ucf:fixture:decision:{decision_class.value}:{outcome.value}"
            ),
            source_digest=_digest("b" if outcome is DecisionOutcome.APPROVED else "c"),
            summary=f"fixture decision {outcome.value}",
        ),
    )
    return create_decision_declaration(
        assessment,
        impact,
        (decision,),
        change_proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )


def _digest(character: str) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=character * 64,
    )


def _json_payload(value: object) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def render_wire_fixtures() -> dict[Path, str]:
    fixtures = governance_fixtures()
    compatible = fixtures.compatible
    breaking = fixtures.breaking_required
    approved = fixtures.breaking_approved
    rejected = fixtures.breaking_rejected
    if approved.declaration is None or rejected.declaration is None:
        raise AssertionError("fixture declarations were not constructed")

    context = {
        "context/base-behavior.json": canonical_ir_json(compatible.base),
        "context/compatible-final-behavior.json": canonical_ir_json(compatible.final),
        "context/breaking-final-behavior.json": canonical_ir_json(breaking.final),
        "context/proposal.json": canonical_change_lifecycle_json(
            compatible.proposal
        ).decode("utf-8"),
        "context/compatible-delta.json": canonical_change_lifecycle_json(
            compatible.delta
        ).decode("utf-8"),
        "context/breaking-delta.json": canonical_change_lifecycle_json(
            breaking.delta
        ).decode("utf-8"),
    }
    positive_documents = {
        "positive/compatible-impact-report.json": compatible.impact,
        "positive/compatible-assessment.json": compatible.assessment,
        "positive/compatible-gate.json": compatible.gate,
        "positive/breaking-impact-report.json": breaking.impact,
        "positive/breaking-assessment.json": breaking.assessment,
        "positive/breaking-approved-declaration.json": approved.declaration,
        "positive/breaking-approved-gate.json": approved.gate,
        "positive/breaking-rejected-declaration.json": rejected.declaration,
        "positive/breaking-rejected-gate.json": rejected.gate,
        "positive/breaking-required-gate.json": breaking.gate,
    }
    rendered = {
        DEFAULT_FIXTURE_DIRECTORY / relative_path: content
        for relative_path, content in context.items()
    }
    rendered.update(
        {
            DEFAULT_FIXTURE_DIRECTORY / relative_path: (
                canonical_change_governance_json(document).decode("utf-8")
            )
            for relative_path, document in positive_documents.items()
        }
    )

    compatible_impact = compatible.impact.model_dump(mode="json")
    unknown = deepcopy(compatible_impact)
    unknown["unexpected"] = True
    unsupported = deepcopy(compatible_impact)
    unsupported["change_governance_version"] = "2.0.0"
    noncanonical_edges = deepcopy(compatible_impact)
    noncanonical_edges["edges"].reverse()
    out_of_range = deepcopy(compatible_impact)
    out_of_range["witnesses"][0]["edge_indexes"] = [len(out_of_range["edges"])]
    incomplete_assessment = compatible.assessment.model_dump(mode="json")
    incomplete_assessment["assessments"].pop()
    derived_downgrade = breaking.assessment.model_dump(mode="json")
    derived_downgrade["assessments"][0] = deepcopy(derived_downgrade["assessments"][1])
    derived_downgrade["assessments"][0]["decision_class"] = (
        DecisionClass.PUBLIC_CONTRACT.value
    )
    stale_impact = compatible.assessment.model_dump(mode="json")
    stale_impact["impact"]["canonical_digest"]["value"] = "f" * 64
    extra_decision = approved.declaration.model_dump(mode="json")
    extra = deepcopy(extra_decision["decisions"][0])
    extra["decision_class"] = DecisionClass.PRODUCTION_DEPENDENCY.value
    extra_decision["decisions"].append(extra)
    stale_assessment = approved.declaration.model_dump(mode="json")
    stale_assessment["assessment"]["canonical_digest"]["value"] = "f" * 64
    forged_pass = breaking.gate.model_dump(mode="json")
    forged_pass["status"] = "pass_approved"
    forged_pass["blockers"] = []
    stale_declaration = approved.gate.model_dump(mode="json")
    stale_declaration["declaration"]["canonical_digest"]["value"] = "f" * 64
    irrelevant_declaration = approved.declaration.model_dump(mode="json")
    irrelevant_declaration.update(
        {
            "delta": compatible.assessment.delta.model_dump(mode="json"),
            "final_behavior": compatible.assessment.final_behavior.model_dump(
                mode="json"
            ),
            "impact": impact_report_ref(compatible.impact).model_dump(mode="json"),
            "assessment": decision_assessment_ref(compatible.assessment).model_dump(
                mode="json"
            ),
        }
    )
    canonical_impact = canonical_change_governance_json(compatible.impact).decode(
        "utf-8"
    )
    invalid = {
        "invalid/duplicate-json-member.json": (
            '{"kind":"duplicate",' + canonical_impact[1:]
        ),
        "invalid/unknown-root-field.json": _json_payload(unknown),
        "invalid/unsupported-version.json": _json_payload(unsupported),
        "invalid/noncanonical-edge-order.json": _json_payload(noncanonical_edges),
        "invalid/out-of-range-witness.json": _json_payload(out_of_range),
        "invalid/incomplete-assessment.json": _json_payload(incomplete_assessment),
        "invalid/derived-downgrade.json": _json_payload(derived_downgrade),
        "invalid/stale-impact-assessment.json": _json_payload(stale_impact),
        "invalid/extra-decision.json": _json_payload(extra_decision),
        "invalid/stale-assessment-declaration.json": _json_payload(stale_assessment),
        "invalid/forged-pass-gate.json": _json_payload(forged_pass),
        "invalid/stale-declaration-gate.json": _json_payload(stale_declaration),
        "invalid/irrelevant-declaration.json": _json_payload(irrelevant_declaration),
    }
    rendered.update(
        {
            DEFAULT_FIXTURE_DIRECTORY / relative_path: content
            for relative_path, content in invalid.items()
        }
    )
    return rendered


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check change-governance wire fixtures."
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = _parse_args(arguments)
    fixtures = render_wire_fixtures()
    if options.check:
        stale = [
            path
            for path, content in fixtures.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        expected_paths = set(fixtures)
        stale.extend(
            path
            for path in sorted(DEFAULT_FIXTURE_DIRECTORY.rglob("*"))
            if (path.is_file() or path.is_symlink()) and path not in expected_paths
        )
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0
    for path, content in fixtures.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
