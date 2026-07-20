from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GoStdlibHarness,
    GoStdlibTarget,
    go_stdlib_fixture_manifest,
)

from tests.ecosystems.test_go_stdlib_discovery import (
    EXPECTED_UNCOVERED,
    _collect,
    _interface_name,
)
from ucf.ir import ClaimLevel
from ucf.ir.models import Digest, Producer
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    DispositionKind,
    OnboardingErrorCode,
    OnboardingValidationError,
    RejectedDecision,
    UncertainDecision,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    canonical_onboarding_json,
    derive_decision_id,
    validate_onboarding_bundle,
)

REVIEW_ENVIRONMENT = hashlib.sha256(
    b"ucf-eco002-go-review-policy:1.0.0\n"
).hexdigest()


def test_go_stdlib_review_materializes_only_explicitly_accepted_behavior(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "review-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    evidence = _collect(
        target=target,
        record_limit=7,
        stderr_path=tmp_path / "discovery.stderr",
    )
    decisions = _quote_order_decisions(evidence.discovery)

    first = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        decisions,
    )
    second = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        decisions,
    )
    validate_onboarding_bundle(first)

    assert canonical_onboarding_json(first) == canonical_onboarding_json(
        second
    )
    assert len(first.baseline.materializations) == 1
    materialization = first.baseline.materializations[0]
    accepted = next(
        candidate
        for candidate in first.discovery.candidates
        if candidate.id == materialization.candidate.candidate_id
    )
    assert accepted.proposal.root.target_id == "use-case.quote-order"
    assert tuple(root.target_id for root in first.behavior.roots) == (
        "use-case.quote-order",
    )
    assert materialization.root.target_id == "use-case.quote-order"

    disposition_ids = {
        summary.disposition: summary.candidate_ids
        for summary in first.baseline.dispositions
    }
    assert disposition_ids[DispositionKind.ACCEPTED] == (accepted.id,)
    assert len(disposition_ids[DispositionKind.REJECTED]) == 2
    assert len(disposition_ids[DispositionKind.UNCERTAIN]) == 1
    assert disposition_ids[DispositionKind.EDITED] == ()
    assert first.baseline.discovery_status == "partial"
    records_by_id = {
        record.id: record for record in first.inventory.records
    }
    assert {
        _interface_name(reference.target_id, records_by_id)
        for reference in first.baseline.uncovered_subjects
    } == EXPECTED_UNCOVERED

    claims = {
        summary.level: summary.claim_ids
        for summary in first.baseline.claim_levels
    }
    assert len(claims[ClaimLevel.OBSERVED]) == 1
    assert len(claims[ClaimLevel.DECLARED]) == 1
    assert claims[ClaimLevel.MAPPED] == ()
    assert claims[ClaimLevel.TESTED] == ()
    assert claims[ClaimLevel.VERIFIED] == ()
    assert first.decisions.reviewer.name == "org.ucf.ecosystem-reviewer"
    assert first.decisions.capture_context.environment.value == (
        REVIEW_ENVIRONMENT
    )
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_review_rejects_a_stale_candidate_reference(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "review-target")
    evidence = _collect(
        target=target,
        record_limit=7,
        stderr_path=tmp_path / "discovery.stderr",
    )
    decisions = _quote_order_decisions(evidence.discovery)
    first = decisions.decisions[0]
    stale = first.model_copy(
        update={
            "candidate": first.candidate.model_copy(
                update={
                    "semantic_digest": Digest(
                        kind="digest",
                        algorithm="sha-256",
                        value="0" * 64,
                    )
                }
            )
        }
    )
    changed = decisions.model_copy(
        update={"decisions": (stale, *decisions.decisions[1:])}
    )

    with pytest.raises(OnboardingValidationError) as rejected:
        build_onboarding_bundle(
            evidence.inventory,
            evidence.discovery,
            changed,
        )

    assert rejected.value.code is OnboardingErrorCode.STALE_DECISION
    assert (tmp_path / "discovery.stderr").read_bytes() == b""


def _reviewed_bundle(
    *,
    target: GoStdlibTarget,
    stderr_path: Path,
):
    evidence = _collect(
        target=target,
        record_limit=7,
        stderr_path=stderr_path,
    )
    decisions = _quote_order_decisions(evidence.discovery)
    return build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        decisions,
    )


def _quote_order_decisions(discovery) -> DecisionSet:
    base = DecisionSet(
        kind="decision_set_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DECISION_SET_SCHEMA_URI,
        discovery=DiscoveryDocumentRef(
            kind="discovery_document_ref",
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=canonical_onboarding_digest(discovery),
        ),
        inventory_binding=discovery.inventory_binding,
        reviewer=Producer(
            kind="producer",
            name="org.ucf.ecosystem-reviewer",
            version="1.0.0",
        ),
        capture_context=CaptureContext(
            kind="capture_context",
            captured_at="2026-07-19T12:00:00Z",
            environment=Digest(
                kind="digest",
                algorithm="sha-256",
                value=REVIEW_ENVIRONMENT,
            ),
        ),
        decisions=(),
    )
    decisions = []
    for candidate in discovery.candidates:
        candidate_ref = CandidateRef(
            kind="candidate_ref",
            discovery_digest=canonical_onboarding_digest(discovery),
            candidate_id=candidate.id,
            semantic_digest=candidate.semantic_digest,
        )
        common = {
            "id": f"decision.{'0' * 64}",
            "candidate": candidate_ref,
        }
        root = candidate.proposal.root.target_id
        if root == "use-case.quote-order":
            decision = AcceptedDecision(
                kind="accepted_decision",
                reason=(
                    "Native Go tests and literal HTTP evidence match the "
                    "reviewed quote-order scope."
                ),
                **common,
            )
        elif root == "use-case.legacy-discount-hint":
            decision = UncertainDecision(
                kind="uncertain_decision",
                reason=(
                    "No executable evidence establishes the legacy hint as "
                    "intended behavior."
                ),
                **common,
            )
        else:
            decision = RejectedDecision(
                kind="rejected_decision",
                reason="Outside the reviewed quote-order acceptance scope.",
                **common,
            )
        decisions.append(
            decision.model_copy(
                update={"id": derive_decision_id(decision, base)}
            )
        )
    return base.model_copy(
        update={
            "decisions": tuple(
                sorted(
                    decisions,
                    key=lambda item: item.candidate.candidate_id,
                )
            )
        }
    )
