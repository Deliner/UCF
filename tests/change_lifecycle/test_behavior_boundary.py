from __future__ import annotations

from typing import Literal

import pytest

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    derive_behavior_delta,
    validate_archive_record,
    validate_change_proposal,
)

from ._fixture_factory import lifecycle_chain


@pytest.mark.parametrize(
    ("boundary", "expected_location"),
    (
        ("derive_delta", "$.final_behavior"),
        ("validate_proposal", "$.base_behavior"),
        ("validate_archive", "$.final_behavior"),
    ),
)
def test_public_behavior_boundary_maps_corrupted_exact_model(
    boundary: Literal["derive_delta", "validate_proposal", "validate_archive"],
    expected_location: str,
) -> None:
    chain = lifecycle_chain()
    if boundary == "validate_proposal":
        broken = chain.base.model_copy(update={"entities": (object(),)})
    else:
        broken = chain.final.model_copy(update={"entities": (object(),)})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        if boundary == "derive_delta":
            derive_behavior_delta(chain.proposal, chain.base, broken)
        elif boundary == "validate_proposal":
            validate_change_proposal(chain.proposal, broken)
        else:
            validate_archive_record(
                chain.archive,
                chain.proposal,
                chain.delta,
                chain.graph,
                chain.implementation,
                chain.verification,
                chain.base,
                broken,
                evidence_contexts=chain.evidence_contexts,
            )

    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == expected_location


def test_public_behavior_boundary_preserves_ir_error_mapping() -> None:
    chain = lifecycle_chain()
    removed_id = chain.final.roots[0].target_id
    broken = chain.final.model_copy(
        update={
            "entities": tuple(
                entity for entity in chain.final.entities if entity.id != removed_id
            )
        }
    )

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        derive_behavior_delta(chain.proposal, chain.base, broken)

    assert captured.value.code is ChangeLifecycleErrorCode.BROKEN_REFERENCE
    assert captured.value.location == "$.final_behavior.roots[0]"
