from __future__ import annotations

import hashlib

from ucf.inventory import (
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    InventorySnapshot,
    canonical_inventory_json,
)
from ucf.ir import (
    CURRENT_IR_VERSION,
    CURRENT_TRUST_IR_VERSION,
    canonical_ir_json,
    canonical_trust_ir_json,
)
from ucf.ir.models import BehaviorIR, Digest
from ucf.ir.trust_models import Claim, ClaimLevel, TrustIR
from ucf.onboarding.codec import canonical_onboarding_digest
from ucf.onboarding.errors import (
    OnboardingErrorCode,
    OnboardingValidationError,
)
from ucf.onboarding.models import (
    DECISION_SET_SCHEMA_URI,
    DISCOVERY_REQUEST_SCHEMA_URI,
    ONBOARDING_BUNDLE_SCHEMA_URI,
    AcceptedDecision,
    BehaviorMaterialization,
    BundleDocumentKind,
    BundleDocumentRef,
    ClaimLevelSummary,
    DecisionSet,
    DiscoveryRequest,
    DiscoveryResult,
    DispositionKind,
    DispositionSummary,
    EditedDecision,
    OnboardingBaseline,
    OnboardingBundle,
    RejectedDecision,
)
from ucf.onboarding.reconciliation import materialize_behavior
from ucf.onboarding.trust import build_onboarding_trust
from ucf.onboarding.validation import (
    validate_decision_set,
    validate_discovery_exchange,
)

_IR_SCHEMA_URI = "urn:ucf:schema:ir:1.0.0"
_TRUST_SCHEMA_URI = "urn:ucf:schema:trust-ir:1.0.0"


def build_onboarding_bundle(
    inventory: InventorySnapshot,
    discovery: DiscoveryResult,
    decisions: DecisionSet,
) -> OnboardingBundle:
    request = _request_for(inventory, discovery)
    validate_discovery_exchange(request, discovery)
    validate_decision_set(discovery, decisions)
    behavior, materializations = materialize_behavior(
        discovery,
        decisions,
    )
    trust = build_onboarding_trust(
        discovery,
        decisions,
        behavior,
        materializations,
    )
    bundle = OnboardingBundle(
        kind="onboarding_bundle",
        onboarding_version=discovery.onboarding_version,
        schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
        capture_context=decisions.capture_context,
        inventory=inventory,
        discovery=discovery,
        decisions=decisions,
        behavior=behavior,
        trust=trust,
        baseline=_derive_baseline(
            inventory,
            discovery,
            decisions,
            behavior,
            trust,
            materializations,
        ),
    )
    validate_onboarding_bundle(bundle)
    return bundle


def validate_onboarding_bundle(bundle: OnboardingBundle) -> None:
    if bundle.capture_context != bundle.decisions.capture_context:
        raise OnboardingValidationError(
            OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "bundle capture context differs from its decision set",
            location="$.capture_context",
        )
    request = _request_for(bundle.inventory, bundle.discovery)
    validate_discovery_exchange(request, bundle.discovery)
    validate_decision_set(bundle.discovery, bundle.decisions)
    expected_behavior, expected_materializations = materialize_behavior(
        bundle.discovery,
        bundle.decisions,
    )
    if bundle.behavior != expected_behavior:
        raise OnboardingValidationError(
            OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "embedded Behavior IR differs from deterministic materialization",
            location="$.behavior",
        )
    expected_trust = build_onboarding_trust(
        bundle.discovery,
        bundle.decisions,
        bundle.behavior,
        expected_materializations,
    )
    if bundle.trust != expected_trust:
        raise OnboardingValidationError(
            OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH,
            "embedded Trust IR differs from deterministic evidence import",
            location="$.trust",
        )
    expected_baseline = _derive_baseline(
        bundle.inventory,
        bundle.discovery,
        bundle.decisions,
        bundle.behavior,
        bundle.trust,
        expected_materializations,
    )
    if bundle.baseline != expected_baseline:
        raise OnboardingValidationError(
            OnboardingErrorCode.SUMMARY_MISMATCH,
            "onboarding baseline differs from its exact embedded documents",
            location="$.baseline",
        )


def _request_for(
    inventory: InventorySnapshot,
    discovery: DiscoveryResult,
) -> DiscoveryRequest:
    return DiscoveryRequest(
        kind="discovery_request_profile",
        onboarding_version=discovery.onboarding_version,
        schema_uri=DISCOVERY_REQUEST_SCHEMA_URI,
        capability=discovery.capability,
        inventory_binding=discovery.inventory_binding,
        inventory=inventory,
    )


def _derive_baseline(
    inventory: InventorySnapshot,
    discovery: DiscoveryResult,
    decisions: DecisionSet,
    behavior: BehaviorIR,
    trust: TrustIR,
    materializations: tuple[BehaviorMaterialization, ...],
) -> OnboardingBaseline:
    documents = (
        BundleDocumentRef(
            kind="bundle_document_ref",
            document_kind=BundleDocumentKind.INVENTORY,
            schema_uri=INVENTORY_SCHEMA_URI,
            schema_version=INVENTORY_VERSION,
            canonical_digest=_digest(canonical_inventory_json(inventory)),
        ),
        BundleDocumentRef(
            kind="bundle_document_ref",
            document_kind=BundleDocumentKind.DISCOVERY,
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=canonical_onboarding_digest(discovery),
        ),
        BundleDocumentRef(
            kind="bundle_document_ref",
            document_kind=BundleDocumentKind.DECISIONS,
            schema_uri=DECISION_SET_SCHEMA_URI,
            schema_version=decisions.onboarding_version,
            canonical_digest=canonical_onboarding_digest(decisions),
        ),
        BundleDocumentRef(
            kind="bundle_document_ref",
            document_kind=BundleDocumentKind.BEHAVIOR,
            schema_uri=_IR_SCHEMA_URI,
            schema_version=CURRENT_IR_VERSION,
            canonical_digest=_digest(
                canonical_ir_json(behavior).encode("ascii")
            ),
        ),
        BundleDocumentRef(
            kind="bundle_document_ref",
            document_kind=BundleDocumentKind.TRUST,
            schema_uri=_TRUST_SCHEMA_URI,
            schema_version=CURRENT_TRUST_IR_VERSION,
            canonical_digest=_digest(
                canonical_trust_ir_json(trust).encode("ascii")
            ),
        ),
    )
    disposition_ids = {
        disposition: [] for disposition in DispositionKind
    }
    for decision in decisions.decisions:
        if isinstance(decision, AcceptedDecision):
            disposition = DispositionKind.ACCEPTED
        elif isinstance(decision, EditedDecision):
            disposition = DispositionKind.EDITED
        elif isinstance(decision, RejectedDecision):
            disposition = DispositionKind.REJECTED
        else:
            disposition = DispositionKind.UNCERTAIN
        disposition_ids[disposition].append(
            decision.candidate.candidate_id
        )
    dispositions = tuple(
        DispositionSummary(
            kind="disposition_summary",
            disposition=disposition,
            candidate_ids=tuple(sorted(disposition_ids[disposition])),
        )
        for disposition in DispositionKind
    )
    claim_ids = {level: [] for level in ClaimLevel}
    for record in trust.records:
        if isinstance(record, Claim):
            claim_ids[record.level].append(record.id)
    claim_levels = tuple(
        ClaimLevelSummary(
            kind="claim_level_summary",
            level=level,
            claim_ids=tuple(sorted(claim_ids[level])),
        )
        for level in ClaimLevel
    )
    return OnboardingBaseline(
        kind="onboarding_baseline",
        documents=documents,
        dispositions=dispositions,
        materializations=tuple(
            sorted(
                materializations,
                key=lambda item: item.candidate.candidate_id,
            )
        ),
        discovery_status=discovery.coverage.status,
        uncovered_subjects=discovery.coverage.uncovered_subjects,
        claim_levels=claim_levels,
    )


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )
