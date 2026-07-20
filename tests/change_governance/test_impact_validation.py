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
    canonical_change_governance_json,
    derive_impact_report,
    impact_report_ref,
    parse_impact_report_json,
    validate_impact_report,
)


def _context():
    base = base_behavior()
    final = output_requiredness_final(base)
    proposal, delta = change_pair(base, final)
    report = derive_impact_report(
        proposal,
        delta,
        base_behavior=base,
        final_behavior=final,
    )
    return base, final, proposal, delta, report


def test_impact_report_is_recomputed_against_every_exact_predecessor() -> None:
    base, final, proposal, delta, report = _context()

    assert (
        validate_impact_report(
            report,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )
        == report
    )
    assert impact_report_ref(report).canonical_digest.value

    forged = report.model_copy(update={"edges": report.edges[:-1]})
    with pytest.raises(ChangeGovernanceValidationError) as error:
        validate_impact_report(
            forged,
            proposal,
            delta,
            base_behavior=base,
            final_behavior=final,
        )

    assert error.value.code is ChangeGovernanceErrorCode.SUMMARY_MISMATCH


@pytest.mark.parametrize("mutation", ("reversed_edges", "duplicate_edge"))
def test_edge_graph_order_and_identity_are_closed(mutation: str) -> None:
    *_context_values, report = _context()
    payload = json.loads(canonical_change_governance_json(report))
    if mutation == "reversed_edges":
        payload["edges"].reverse()
    else:
        payload["edges"].insert(0, payload["edges"][0])

    with pytest.raises(ChangeGovernanceValidationError) as error:
        parse_impact_report_json(json.dumps(payload))

    assert error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE


@pytest.mark.parametrize("edge_index", (-1, None))
def test_witness_cannot_name_an_out_of_range_or_discontinuous_edge(
    edge_index: int | None,
) -> None:
    *_context_values, report = _context()
    payload = json.loads(canonical_change_governance_json(report))
    payload["witnesses"][0]["edge_indexes"] = [
        len(payload["edges"]) if edge_index is None else edge_index
    ]

    with pytest.raises(ChangeGovernanceValidationError) as error:
        parse_impact_report_json(json.dumps(payload))

    assert error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE


def test_witness_cannot_alias_a_valid_edge_with_a_negative_index() -> None:
    *_context_values, report = _context()
    payload = json.loads(canonical_change_governance_json(report))
    original_index = payload["witnesses"][0]["edge_indexes"][0]
    payload["witnesses"][0]["edge_indexes"] = [
        original_index - len(payload["edges"])
    ]

    with pytest.raises(ChangeGovernanceValidationError) as error:
        parse_impact_report_json(json.dumps(payload))

    assert error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE


def test_negative_witness_index_never_leaks_index_error_for_empty_edges() -> None:
    *_context_values, report = _context()
    payload = json.loads(canonical_change_governance_json(report))
    payload["edges"] = []
    payload["witnesses"][0]["edge_indexes"] = [-1]

    with pytest.raises(ChangeGovernanceValidationError) as error:
        parse_impact_report_json(json.dumps(payload))

    assert error.value.code is ChangeGovernanceErrorCode.INVALID_STRUCTURE
