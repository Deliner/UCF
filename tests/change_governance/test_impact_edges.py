from __future__ import annotations

from tests.change_governance._support import (
    base_behavior,
    capability_addition_final,
    change_pair,
    input_requiredness_final,
    mutate_behavior,
    output_requiredness_final,
)
from ucf.change_governance import (
    CompatibilityOutcome,
    GraphSide,
    ImpactPrecision,
    ImpactRelation,
    UnresolvedImpactReason,
    derive_impact_report,
)


def _affected_entity_ids(report: object) -> set[str]:
    return {
        witness.affected.target_id
        for witness in report.witnesses
        if witness.affected.kind == "entity_coordinate"
    }


def test_port_impact_uses_the_exact_selected_slot() -> None:
    base = base_behavior()
    input_final = input_requiredness_final(base)
    input_proposal, input_delta = change_pair(base, input_final)

    input_report = derive_impact_report(
        input_proposal,
        input_delta,
        base_behavior=base,
        final_behavior=input_final,
    )

    binding_witnesses = [
        witness
        for witness in input_report.witnesses
        if witness.affected.kind == "entity_coordinate"
        and witness.affected.target_id == "binding.item-id"
    ]
    assert {witness.side for witness in binding_witnesses} == {
        GraphSide.BASE,
        GraphSide.FINAL,
    }
    assert all(
        tuple(input_report.edges[index].relation for index in witness.edge_indexes)
        == (ImpactRelation.PORT_SELECTION,)
        for witness in binding_witnesses
    )

    output_final = output_requiredness_final(base)
    output_proposal, output_delta = change_pair(base, output_final)
    output_report = derive_impact_report(
        output_proposal,
        output_delta,
        base_behavior=base,
        final_behavior=output_final,
    )

    assert "binding.item-id" not in _affected_entity_ids(output_report)


def test_required_capability_has_an_explicit_document_wide_edge() -> None:
    base = base_behavior()
    required_final = capability_addition_final(base, required=True)
    proposal, delta = change_pair(base, required_final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=required_final,
    )

    assert report.compatibility.outcome is CompatibilityOutcome.BREAKING
    document_witness = next(
        witness
        for witness in report.witnesses
        if witness.affected.kind == "document_coordinate"
        and witness.direct_subject.target_id == "capability.unreferenced"
    )
    assert document_witness.side is GraphSide.FINAL
    assert document_witness.precision is ImpactPrecision.DEFINITE
    assert tuple(
        report.edges[index].relation for index in document_witness.edge_indexes
    ) == (ImpactRelation.REQUIRED_CAPABILITY,)


def test_optional_unreferenced_capability_does_not_gain_a_document_edge() -> None:
    base = base_behavior()
    optional_final = capability_addition_final(base, required=False)
    proposal, delta = change_pair(base, optional_final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=optional_final,
    )

    assert report.compatibility.outcome is CompatibilityOutcome.COMPATIBLE
    assert not any(
        witness.affected.kind == "document_coordinate"
        and witness.direct_subject.target_id == "capability.unreferenced"
        for witness in report.witnesses
    )


def test_cycles_yield_one_canonical_shortest_witness_per_affected_coordinate() -> None:
    base = base_behavior()
    final = output_requiredness_final(base)
    proposal, delta = change_pair(base, final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    keys = [
        (
            witness.side,
            witness.direct_subject.target_kind,
            witness.direct_subject.target_id,
            witness.affected,
        )
        for witness in report.witnesses
    ]
    assert len(keys) == len(set(keys))
    evidence_witnesses = [
        witness
        for witness in report.witnesses
        if witness.affected.kind == "entity_coordinate"
        and witness.affected.target_id == "evidence.reservation-present"
    ]
    assert {witness.side for witness in evidence_witnesses} == {
        GraphSide.BASE,
        GraphSide.FINAL,
    }
    assert all(len(witness.edge_indexes) == 2 for witness in evidence_witnesses)


def test_opaque_rule_change_is_unresolved_without_a_fabricated_edge() -> None:
    base = base_behavior()

    def change_rule(payload: dict[str, object]) -> None:
        entities = payload["entities"]
        invariant = next(entity for entity in entities if entity["kind"] == "invariant")
        invariant["condition"]["statement"] = (
            "looks like use-case.reserve-item but remains opaque"
        )

    final = mutate_behavior(base, change_rule)
    proposal, delta = change_pair(base, final)

    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )

    unresolved = next(
        item
        for item in report.unresolved
        if item.subject.target_id == "invariant.reservation-present"
    )
    assert unresolved.changed_path == "/condition/statement"
    assert unresolved.reason is UnresolvedImpactReason.OPAQUE_DECLARED_RULE
    assert unresolved.sides == (GraphSide.BASE, GraphSide.FINAL)
    assert not any("condition" in edge.field_path for edge in report.edges)
