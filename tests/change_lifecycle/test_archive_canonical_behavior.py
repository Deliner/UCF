from __future__ import annotations

import json
from typing import Literal

import pytest

from ucf.change_lifecycle import (
    ArchiveRecord,
    canonical_change_lifecycle_digest,
    canonical_change_lifecycle_json,
    derive_archive_record,
    parse_archive_record_json,
    validate_archive_record,
)
from ucf.ir import canonical_ir_json

from ._fixture_factory import lifecycle_chain


def _noncanonical_archive_payload(archive: ArchiveRecord) -> bytes:
    return (
        json.dumps(
            archive.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


@pytest.mark.parametrize(
    "boundary",
    ("derive", "canonical", "parse", "validate"),
)
def test_archive_final_behavior_has_one_canonical_representation(
    boundary: Literal["derive", "canonical", "parse", "validate"],
) -> None:
    chain = lifecycle_chain()
    reordered = chain.final.model_copy(
        update={
            "roots": tuple(reversed(chain.final.roots)),
            "entities": tuple(reversed(chain.final.entities)),
        }
    )
    assert reordered != chain.final
    assert canonical_ir_json(reordered) == canonical_ir_json(chain.final)

    if boundary == "derive":
        archive = derive_archive_record(
            chain.proposal,
            chain.delta,
            chain.graph,
            chain.implementation,
            chain.verification,
            chain.base,
            reordered,
            evidence_contexts=chain.evidence_contexts,
        )
        assert archive == chain.archive
        assert canonical_change_lifecycle_digest(archive) == (
            canonical_change_lifecycle_digest(chain.archive)
        )
    elif boundary == "canonical":
        reordered_archive = chain.archive.model_copy(
            update={"final_behavior": reordered}
        )
        assert canonical_change_lifecycle_json(reordered_archive) == (
            canonical_change_lifecycle_json(chain.archive)
        )
    elif boundary == "parse":
        reordered_archive = chain.archive.model_copy(
            update={"final_behavior": reordered}
        )
        parsed = parse_archive_record_json(
            _noncanonical_archive_payload(reordered_archive)
        )
        assert parsed == chain.archive
    else:
        validate_archive_record(
            chain.archive,
            chain.proposal,
            chain.delta,
            chain.graph,
            chain.implementation,
            chain.verification,
            chain.base,
            reordered,
            evidence_contexts=chain.evidence_contexts,
        )
