from __future__ import annotations

import hashlib
import json
from typing import Any

from ucf.change_governance.graph import derive_impact_graph
from ucf.change_governance.models import (
    CHANGE_GOVERNANCE_VERSION,
    HUMAN_DECISION_POLICY_URI,
    IMPACT_REPORT_SCHEMA_URI,
    STRUCTURAL_IMPACT_PROCEDURE_URI,
    CompatibilityAssessment,
    CompatibilityOutcome,
    CompatibilityProfile,
    DecisionClass,
    GraphSide,
    ImpactFinding,
    ImpactPrecision,
    ImpactReport,
    ImpactSubject,
    UnresolvedImpact,
    UnresolvedImpactReason,
)
from ucf.change_lifecycle import (
    BehaviorDelta,
    ChangeProposal,
    behavior_delta_ref,
    change_proposal_ref,
    validate_behavior_delta,
)
from ucf.change_lifecycle.models import (
    AddedBehavior,
    ModifiedBehavior,
    RemovedBehavior,
)
from ucf.ir import canonical_ir_json
from ucf.ir.models import BehaviorIR, CapabilityRequirement, Digest, EntityKind
from ucf.ir.trust_models import BehaviorDocumentRef


def derive_impact_report(
    proposal: ChangeProposal,
    delta: BehaviorDelta,
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> ImpactReport:
    validate_behavior_delta(
        delta,
        proposal,
        base_behavior,
        final_behavior,
    )
    base_entities, base_roots = _canonical_entities_and_roots(base_behavior)
    final_entities, final_roots = _canonical_entities_and_roots(final_behavior)
    findings = tuple(
        _direct_finding(
            entry,
            base_entities=base_entities,
            final_entities=final_entities,
        )
        for entry in delta.entries
    )
    compatibility = _classify_compatibility(
        base_behavior,
        final_behavior,
        base_entities=base_entities,
        final_entities=final_entities,
        base_roots=base_roots,
        final_roots=final_roots,
    )
    required_classes = (
        (DecisionClass.PUBLIC_CONTRACT,)
        if compatibility.outcome is CompatibilityOutcome.BREAKING
        else ()
    )
    edges, witnesses = derive_impact_graph(
        delta,
        findings,
        base_behavior=base_behavior,
        final_behavior=final_behavior,
    )
    unresolved = _derive_unresolved_impacts(findings)
    return ImpactReport(
        kind="impact_report",
        change_governance_version=CHANGE_GOVERNANCE_VERSION,
        schema_uri=IMPACT_REPORT_SCHEMA_URI,
        change_id=proposal.change_id,
        proposal=change_proposal_ref(proposal),
        delta=behavior_delta_ref(delta),
        base_behavior=_behavior_ref(base_behavior),
        final_behavior=_behavior_ref(final_behavior),
        procedure_uri=STRUCTURAL_IMPACT_PROCEDURE_URI,
        decision_policy_uri=HUMAN_DECISION_POLICY_URI,
        findings=findings,
        edges=edges,
        witnesses=witnesses,
        unresolved=unresolved,
        compatibility=compatibility,
        derived_required_classes=required_classes,
    )


def _derive_unresolved_impacts(
    findings: tuple[ImpactFinding, ...],
) -> tuple[UnresolvedImpact, ...]:
    unresolved = []
    for finding in findings:
        sides = _finding_sides(finding)
        for changed_path in finding.changed_paths:
            reason = _unresolved_reason(
                finding.subject.target_kind,
                changed_path,
            )
            if reason is None:
                continue
            unresolved.append(
                UnresolvedImpact(
                    kind="unresolved_impact",
                    subject=finding.subject,
                    changed_path=changed_path,
                    sides=sides,
                    reason=reason,
                )
            )
    return tuple(
        sorted(
            unresolved,
            key=lambda item: (
                item.subject.operation,
                item.subject.target_kind.value,
                item.subject.target_id,
                item.changed_path,
                item.reason.value,
            ),
        )
    )


def _finding_sides(finding: ImpactFinding) -> tuple[GraphSide, ...]:
    if finding.subject.operation == "added":
        return (GraphSide.FINAL,)
    if finding.subject.operation == "removed":
        return (GraphSide.BASE,)
    return (GraphSide.BASE, GraphSide.FINAL)


def _unresolved_reason(
    target_kind: EntityKind,
    changed_path: str,
) -> UnresolvedImpactReason | None:
    if target_kind is EntityKind.INVARIANT and changed_path.startswith("/condition"):
        return UnresolvedImpactReason.OPAQUE_DECLARED_RULE
    if target_kind in {EntityKind.EFFECT, EntityKind.OBSERVATION} and (
        changed_path.startswith("/operation") or changed_path.startswith("/target")
    ):
        return UnresolvedImpactReason.DOMAIN_SEMANTICS
    if target_kind in {
        EntityKind.BINDING,
        EntityKind.EFFECT,
        EntityKind.OBSERVATION,
    } and (changed_path.startswith("/source") or changed_path.startswith("/value")):
        return UnresolvedImpactReason.VALUE_SEMANTICS
    if target_kind is EntityKind.PROVENANCE:
        return UnresolvedImpactReason.PROVENANCE_CONTEXT
    if target_kind is EntityKind.VERIFICATION_EVIDENCE and (
        changed_path.startswith("/check")
        or changed_path.startswith("/environment")
        or changed_path.startswith("/executed_at")
        or changed_path.startswith("/outcome")
        or changed_path.startswith("/source_revision")
    ):
        return UnresolvedImpactReason.VERIFICATION_CONTEXT
    if target_kind is EntityKind.CAPABILITY_REQUIREMENT and changed_path.startswith(
        "/name"
    ):
        return UnresolvedImpactReason.CAPABILITY_SEMANTICS
    return None


def _direct_finding(
    entry: AddedBehavior | ModifiedBehavior | RemovedBehavior,
    *,
    base_entities: dict[tuple[str, str], dict[str, Any]],
    final_entities: dict[tuple[str, str], dict[str, Any]],
) -> ImpactFinding:
    if isinstance(entry, AddedBehavior):
        operation = "added"
        subject = entry.final_subject
        changed_paths = ("",)
    elif isinstance(entry, RemovedBehavior):
        operation = "removed"
        subject = entry.base_subject
        changed_paths = ("",)
    else:
        operation = "modified"
        subject = entry.base_subject
        key = (subject.target_kind.value, subject.target_id)
        changed_paths = tuple(
            _field_changes(
                base_entities[key],
                final_entities[key],
            )
        )
        if entry.base_is_root != entry.final_is_root:
            changed_paths = tuple(sorted((*changed_paths, "/@root")))
    return ImpactFinding(
        kind="impact_finding",
        subject=ImpactSubject(
            kind="impact_subject",
            operation=operation,
            target_kind=subject.target_kind,
            target_id=subject.target_id,
        ),
        precision=ImpactPrecision.DEFINITE,
        changed_paths=changed_paths,
    )


def _classify_compatibility(
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
    *,
    base_entities: dict[tuple[str, str], dict[str, Any]],
    final_entities: dict[tuple[str, str], dict[str, Any]],
    base_roots: set[tuple[str, str]],
    final_roots: set[tuple[str, str]],
) -> CompatibilityAssessment:
    lost_roots = sorted(base_roots - final_roots)
    if lost_roots:
        return CompatibilityAssessment(
            kind="compatibility_assessment",
            outcome=CompatibilityOutcome.BREAKING,
            profile=CompatibilityProfile.BREAKING_BASE_ROOT_CONTRACT,
            reasons=tuple(
                f"base root {kind}:{identifier} is not a final root"
                for kind, identifier in lost_roots
            ),
        )

    required_breaks = _required_capability_breaks(
        base_behavior,
        final_behavior,
    )
    if required_breaks:
        return CompatibilityAssessment(
            kind="compatibility_assessment",
            outcome=CompatibilityOutcome.BREAKING,
            profile=CompatibilityProfile.BREAKING_REQUIRED_CAPABILITY,
            reasons=required_breaks,
        )

    base_is_exact_subgraph = all(
        final_entities.get(key) == value for key, value in base_entities.items()
    )
    if base_is_exact_subgraph:
        return CompatibilityAssessment(
            kind="compatibility_assessment",
            outcome=CompatibilityOutcome.COMPATIBLE,
            profile=CompatibilityProfile.BACKWARD_COMPATIBLE_GRAPH_EXTENSION,
            reasons=("every base entity and root remains byte-exact",),
        )

    return CompatibilityAssessment(
        kind="compatibility_assessment",
        outcome=CompatibilityOutcome.UNRESOLVED,
        profile=CompatibilityProfile.COMPATIBILITY_UNRESOLVED,
        reasons=("existing behavior changed outside the narrow structural profile",),
    )


def _required_capability_breaks(
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> tuple[str, ...]:
    base = {
        entity.id: entity
        for entity in base_behavior.entities
        if isinstance(entity, CapabilityRequirement)
    }
    final = {
        entity.id: entity
        for entity in final_behavior.entities
        if isinstance(entity, CapabilityRequirement)
    }
    reasons = []
    for identifier, requirement in sorted(final.items()):
        if not requirement.required:
            continue
        previous = base.get(identifier)
        if previous is None or not previous.required:
            reasons.append(f"required capability {requirement.name} was introduced")
            continue
        if _version(requirement.minimum_version) > _version(previous.minimum_version):
            reasons.append(
                f"required capability {requirement.name} minimum version "
                f"increased from {previous.minimum_version} to "
                f"{requirement.minimum_version}"
            )
    return tuple(reasons)


def _version(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def _field_changes(
    base: object,
    final: object,
    *,
    path: str = "",
) -> list[str]:
    if type(base) is not type(final):
        return [path]
    if isinstance(base, dict):
        changed = []
        for key in sorted(base.keys() | final.keys()):
            child = f"{path}/{_escape_pointer(key)}"
            if key not in base or key not in final:
                changed.append(child)
            else:
                changed.extend(_field_changes(base[key], final[key], path=child))
        return changed
    if isinstance(base, list):
        changed = []
        for index in range(max(len(base), len(final))):
            child = f"{path}/{index}"
            if index >= len(base) or index >= len(final):
                changed.append(child)
            else:
                changed.extend(_field_changes(base[index], final[index], path=child))
        return changed
    return [] if base == final else [path]


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _canonical_entities_and_roots(
    document: BehaviorIR,
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    set[tuple[str, str]],
]:
    canonical = json.loads(canonical_ir_json(document))
    entities = {
        (entity["kind"], entity["id"]): entity for entity in canonical["entities"]
    }
    roots = {(root["target_kind"], root["target_id"]) for root in canonical["roots"]}
    return entities, roots


def _behavior_ref(document: BehaviorIR) -> BehaviorDocumentRef:
    return BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=document.document_id,
        ir_version=document.ir_version,
        canonical_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(
                canonical_ir_json(document).encode("utf-8")
            ).hexdigest(),
        ),
    )
