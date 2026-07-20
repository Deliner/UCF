from __future__ import annotations

import hashlib
import json

from ucf.ir.models import Digest
from ucf.onboarding.models import (
    CandidateProposal,
    Decision,
    DecisionSet,
    DiscoveryCandidate,
    DiscoveryResult,
)


def derive_candidate_semantic_digest(
    proposal: CandidateProposal,
) -> Digest:
    return _digest(_canonical_identity_bytes(proposal.model_dump(mode="json")))


def derive_discovery_candidate_id(
    candidate: DiscoveryCandidate,
    result: DiscoveryResult,
) -> str:
    projection = {
        "candidate": candidate.model_dump(
            mode="json",
            exclude={"id", "semantic_digest"},
        ),
        "capability": result.capability.model_dump(mode="json"),
        "inventory_binding": result.inventory_binding.model_dump(mode="json"),
        "procedure_uri": result.procedure_uri,
        "producer": result.producer.model_dump(mode="json"),
    }
    return (
        "candidate."
        + hashlib.sha256(_canonical_identity_bytes(projection)).hexdigest()
    )


def derive_decision_id(
    decision: Decision,
    decision_set: DecisionSet,
) -> str:
    projection = {
        "capture_context": decision_set.capture_context.model_dump(
            mode="json"
        ),
        "decision": decision.model_dump(mode="json", exclude={"id"}),
        "discovery": decision_set.discovery.model_dump(mode="json"),
        "inventory_binding": decision_set.inventory_binding.model_dump(
            mode="json"
        ),
        "reviewer": decision_set.reviewer.model_dump(mode="json"),
    }
    return (
        "decision."
        + hashlib.sha256(_canonical_identity_bytes(projection)).hexdigest()
    )


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def _canonical_identity_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
