from __future__ import annotations

from tests.change_governance._support import (
    additive_root_final,
    base_behavior,
    change_pair,
    output_requiredness_final,
    root_loss_final,
)
from ucf.change_governance import (
    CompatibilityOutcome,
    DecisionClass,
    ImpactPrecision,
    derive_impact_report,
)
from ucf.ir.models import EntityKind


def test_additive_root_is_a_narrow_backward_compatible_graph_extension() -> None:
    base = base_behavior()
    final = additive_root_final(base)
    proposal, delta = change_pair(base, final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    assert report.compatibility.outcome is CompatibilityOutcome.COMPATIBLE
    assert report.compatibility.profile == "backward_compatible_graph_extension"
    assert report.derived_required_classes == ()
    assert [
        (
            finding.subject.operation,
            finding.subject.target_kind,
            finding.subject.target_id,
            finding.precision,
        )
        for finding in report.findings
    ] == [
        (
            "added",
            EntityKind.USE_CASE,
            "use-case.health-check",
            ImpactPrecision.DEFINITE,
        )
    ]


def test_base_root_loss_is_breaking_and_derives_only_public_contract_gate() -> None:
    base = base_behavior()
    final = root_loss_final(base)
    proposal, delta = change_pair(base, final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    assert report.compatibility.outcome is CompatibilityOutcome.BREAKING
    assert report.compatibility.profile == "breaking_base_root_contract"
    assert report.derived_required_classes == (DecisionClass.PUBLIC_CONTRACT,)


def test_existing_definition_change_is_unresolved_and_does_not_overclaim() -> None:
    base = base_behavior()
    final = output_requiredness_final(base)
    proposal, delta = change_pair(base, final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    assert report.compatibility.outcome is CompatibilityOutcome.UNRESOLVED
    assert report.compatibility.profile == "compatibility_unresolved"
    assert report.derived_required_classes == ()
    direct = next(
        finding
        for finding in report.findings
        if finding.precision is ImpactPrecision.DEFINITE
    )
    assert direct.subject.target_id == "use-case.reserve-item"
    assert "/output_ports/0/required" in direct.changed_paths
    assert not any(
        finding.subject.target_id == "binding.item-id"
        and finding.precision is ImpactPrecision.DEFINITE
        for finding in report.findings
    )
    assert not any(
        witness.affected.kind == "entity_coordinate"
        and witness.affected.target_id == "binding.item-id"
        for witness in report.witnesses
    )
