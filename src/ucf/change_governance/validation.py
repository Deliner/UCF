from __future__ import annotations

from ucf.change_governance.codec import (
    canonical_change_governance_json,
    decision_assessment_ref,
    decision_declaration_ref,
    impact_report_ref,
    parse_decision_assessment_json,
    parse_decision_declaration_json,
    parse_gate_evaluation_json,
    parse_impact_report_json,
)
from ucf.change_governance.errors import (
    ChangeGovernanceErrorCode,
    ChangeGovernanceValidationError,
)
from ucf.change_governance.impact import derive_impact_report
from ucf.change_governance.models import (
    CHANGE_GOVERNANCE_VERSION,
    DECISION_ASSESSMENT_SCHEMA_URI,
    DECISION_DECLARATION_SCHEMA_URI,
    GATE_EVALUATION_PROCEDURE_URI,
    GATE_EVALUATION_SCHEMA_URI,
    HUMAN_DECISION_POLICY_URI,
    AssessmentBasis,
    DecisionAssessment,
    DecisionClass,
    DecisionClassAssessment,
    DecisionDeclaration,
    DecisionDisposition,
    DecisionOutcome,
    DeclaredDecision,
    GateBlocker,
    GateBlockerReason,
    GateEvaluation,
    GateStatus,
    ImpactReport,
)
from ucf.change_lifecycle import (
    BehaviorDelta,
    ChangeLifecycleValidationError,
    ChangeProposal,
    behavior_delta_ref,
    change_proposal_ref,
)
from ucf.ir.models import BehaviorIR


def validate_impact_report(
    report: ImpactReport,
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> ImpactReport:
    _reparse_impact_report(report)
    try:
        expected = derive_impact_report(
            proposal,
            delta,
            base_behavior=base_behavior,
            final_behavior=final_behavior,
        )
    except ChangeLifecycleValidationError as error:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.CONTENT_IDENTITY_MISMATCH,
            str(error),
            location="$",
        ) from error
    if report != expected:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.SUMMARY_MISMATCH,
            "impact report does not equal the report recomputed from its "
            "exact proposal, delta, base, and final behavior",
            location="$",
        )
    return report


def _reparse_impact_report(report: ImpactReport) -> None:
    if type(report) is not ImpactReport:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "impact report must use its exact declared type",
            location="$",
        )
    parse_impact_report_json(canonical_change_governance_json(report))


def create_decision_assessment(
    impact: ImpactReport,
    declarations: tuple[DecisionClassAssessment, ...],
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> DecisionAssessment:
    validate_impact_report(
        impact,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    for position, declaration in enumerate(declarations):
        if type(declaration) is not DecisionClassAssessment:
            raise ChangeGovernanceValidationError(
                ChangeGovernanceErrorCode.INVALID_STRUCTURE,
                "declared assessment must use its exact canonical type",
                location=f"$.declarations[{position}]",
            )
        if declaration.basis is not AssessmentBasis.DECLARED:
            raise ChangeGovernanceValidationError(
                ChangeGovernanceErrorCode.DERIVED_CLASS_MISMATCH,
                "caller classifications must use declared basis",
                location=f"$.declarations[{position}].basis",
            )
    classes = tuple(item.decision_class for item in declarations)
    if len(classes) != len(set(classes)):
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.DUPLICATE_IDENTITY,
            "declared assessment contains duplicate decision classes",
            location="$.declarations",
        )
    derived = set(impact.derived_required_classes)
    expected_declared = tuple(
        decision_class
        for decision_class in DecisionClass
        if decision_class not in derived
    )
    extra = set(classes) - set(expected_declared)
    if extra:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.DERIVED_CLASS_MISMATCH,
            "caller cannot replace a structurally derived decision class",
            location="$.declarations",
        )
    if set(classes) != set(expected_declared):
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INCOMPLETE_ASSESSMENT,
            "declared assessment must classify every non-derived decision class",
            location="$.declarations",
        )
    if classes != expected_declared:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.NON_CANONICAL_ORDER,
            "declared assessment classes are not in taxonomy order",
            location="$.declarations",
        )
    declared_by_class = {item.decision_class: item for item in declarations}
    assessments = tuple(
        DecisionClassAssessment(
            kind="decision_class_assessment",
            decision_class=decision_class,
            disposition=DecisionDisposition.APPLIES,
            basis=AssessmentBasis.DERIVED,
            declared_basis=None,
        )
        if decision_class in derived
        else declared_by_class[decision_class]
        for decision_class in DecisionClass
    )
    return DecisionAssessment(
        kind="decision_assessment",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=DECISION_ASSESSMENT_SCHEMA_URI,
        change_id=impact.change_id,
        proposal=change_proposal_ref(proposal),
        delta=behavior_delta_ref(delta),
        base_behavior=impact.base_behavior,
        final_behavior=impact.final_behavior,
        impact=impact_report_ref(impact),
        decision_policy_uri=HUMAN_DECISION_POLICY_URI,
        assessments=assessments,
    )


def validate_decision_assessment(
    assessment: DecisionAssessment,
    impact: ImpactReport,
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> DecisionAssessment:
    if type(assessment) is not DecisionAssessment:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "decision assessment must use its exact declared type",
            location="$",
        )
    parse_decision_assessment_json(canonical_change_governance_json(assessment))
    validate_impact_report(
        impact,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    if assessment.impact != impact_report_ref(impact):
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "decision assessment impact reference does not match exact impact",
            location="$.impact",
        )
    declarations = tuple(
        item
        for item in assessment.assessments
        if item.basis is AssessmentBasis.DECLARED
    )
    expected = create_decision_assessment(
        impact,
        declarations,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    if assessment != expected:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.SUMMARY_MISMATCH,
            "decision assessment does not equal the assessment recomputed "
            "from its exact impact and declarations",
            location="$",
        )
    return assessment


def create_decision_declaration(
    assessment: DecisionAssessment,
    impact: ImpactReport,
    decisions: tuple[DeclaredDecision, ...],
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> DecisionDeclaration:
    validate_decision_assessment(
        assessment,
        impact,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    unresolved = tuple(
        item.decision_class
        for item in assessment.assessments
        if item.disposition is DecisionDisposition.UNRESOLVED
    )
    if unresolved:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.UNRESOLVED_ASSESSMENT,
            "an unresolved assessment cannot be replaced by a decision",
            location="$.assessment.assessments",
        )
    applicable = tuple(
        item.decision_class
        for item in assessment.assessments
        if item.disposition is DecisionDisposition.APPLIES
    )
    for position, decision in enumerate(decisions):
        if type(decision) is not DeclaredDecision:
            raise ChangeGovernanceValidationError(
                ChangeGovernanceErrorCode.INVALID_STRUCTURE,
                "decision must use its exact canonical type",
                location=f"$.decisions[{position}]",
            )
    classes = tuple(decision.decision_class for decision in decisions)
    if not applicable or len(classes) != len(set(classes)) or classes != applicable:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.DECISION_SET_MISMATCH,
            "decision classes must equal the exact applicable class set "
            "in taxonomy order",
            location="$.decisions",
        )
    return DecisionDeclaration(
        kind="decision_declaration",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=DECISION_DECLARATION_SCHEMA_URI,
        change_id=assessment.change_id,
        proposal=change_proposal_ref(proposal),
        delta=behavior_delta_ref(delta),
        base_behavior=assessment.base_behavior,
        final_behavior=assessment.final_behavior,
        impact=impact_report_ref(impact),
        assessment=decision_assessment_ref(assessment),
        decision_policy_uri=HUMAN_DECISION_POLICY_URI,
        decisions=decisions,
    )


def validate_decision_declaration(
    declaration: DecisionDeclaration,
    assessment: DecisionAssessment,
    impact: ImpactReport,
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> DecisionDeclaration:
    if type(declaration) is not DecisionDeclaration:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "decision declaration must use its exact declared type",
            location="$",
        )
    parse_decision_declaration_json(canonical_change_governance_json(declaration))
    validate_decision_assessment(
        assessment,
        impact,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    if declaration.impact != impact_report_ref(
        impact
    ) or declaration.assessment != decision_assessment_ref(assessment):
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.CONTENT_IDENTITY_MISMATCH,
            "decision declaration predecessor references are stale",
            location="$",
        )
    expected = create_decision_declaration(
        assessment,
        impact,
        declaration.decisions,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    if declaration != expected:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.SUMMARY_MISMATCH,
            "decision declaration does not equal the declaration recomputed "
            "from its exact predecessors",
            location="$",
        )
    return declaration


def evaluate_change_gate(
    assessment: DecisionAssessment,
    impact: ImpactReport,
    declaration: DecisionDeclaration | None,
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> GateEvaluation:
    validate_decision_assessment(
        assessment,
        impact,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    unresolved = tuple(
        item.decision_class
        for item in assessment.assessments
        if item.disposition is DecisionDisposition.UNRESOLVED
    )
    required = tuple(
        item.decision_class
        for item in assessment.assessments
        if item.disposition is DecisionDisposition.APPLIES
    )
    declaration_ref = None
    if unresolved:
        if declaration is not None:
            raise ChangeGovernanceValidationError(
                ChangeGovernanceErrorCode.UNRESOLVED_ASSESSMENT,
                "a declaration cannot bypass unresolved classification",
                location="$.declaration",
            )
        status = GateStatus.BLOCK_UNRESOLVED
        blockers = tuple(
            GateBlocker(
                kind="gate_blocker",
                decision_class=decision_class,
                reason=GateBlockerReason.UNRESOLVED_CLASSIFICATION,
            )
            for decision_class in unresolved
        )
    elif not required:
        if declaration is not None:
            raise ChangeGovernanceValidationError(
                ChangeGovernanceErrorCode.DECISION_SET_MISMATCH,
                "a declaration is invalid when no decision class applies",
                location="$.declaration",
            )
        status = GateStatus.PASS_NO_DECISION
        blockers = ()
    elif declaration is None:
        status = GateStatus.BLOCK_DECISION_REQUIRED
        blockers = tuple(
            GateBlocker(
                kind="gate_blocker",
                decision_class=decision_class,
                reason=GateBlockerReason.DECISION_REQUIRED,
            )
            for decision_class in required
        )
    else:
        validate_decision_declaration(
            declaration,
            assessment,
            impact,
            proposal,
            delta,
            base_behavior=base_behavior,
            final_behavior=final_behavior,
        )
        declaration_ref = decision_declaration_ref(declaration)
        rejected = tuple(
            decision.decision_class
            for decision in declaration.decisions
            if decision.outcome is DecisionOutcome.REJECTED
        )
        if rejected:
            status = GateStatus.BLOCK_REJECTED
            blockers = tuple(
                GateBlocker(
                    kind="gate_blocker",
                    decision_class=decision_class,
                    reason=GateBlockerReason.DECISION_REJECTED,
                )
                for decision_class in rejected
            )
        else:
            status = GateStatus.PASS_APPROVED
            blockers = ()
    return GateEvaluation(
        kind="gate_evaluation",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=GATE_EVALUATION_SCHEMA_URI,
        change_id=assessment.change_id,
        proposal=change_proposal_ref(proposal),
        delta=behavior_delta_ref(delta),
        base_behavior=assessment.base_behavior,
        final_behavior=assessment.final_behavior,
        impact=impact_report_ref(impact),
        assessment=decision_assessment_ref(assessment),
        declaration=declaration_ref,
        decision_policy_uri=HUMAN_DECISION_POLICY_URI,
        procedure_uri=GATE_EVALUATION_PROCEDURE_URI,
        status=status,
        required_classes=required,
        blockers=blockers,
    )


def validate_gate_evaluation(
    gate: GateEvaluation,
    assessment: DecisionAssessment,
    impact: ImpactReport,
    declaration: DecisionDeclaration | None,
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> GateEvaluation:
    if type(gate) is not GateEvaluation:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.INVALID_STRUCTURE,
            "gate evaluation must use its exact declared type",
            location="$",
        )
    parse_gate_evaluation_json(canonical_change_governance_json(gate))
    expected = evaluate_change_gate(
        assessment,
        impact,
        declaration,
        proposal,
        delta,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    if gate != expected:
        raise ChangeGovernanceValidationError(
            ChangeGovernanceErrorCode.SUMMARY_MISMATCH,
            "gate evaluation does not equal the result recomputed from "
            "its exact predecessors",
            location="$",
        )
    return gate
