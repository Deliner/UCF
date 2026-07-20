from __future__ import annotations

import hashlib
import json

from ucf.ir import decode_strict_json_object
from ucf.ir.models import Digest
from ucf.onboarding.models import (
    DecisionSet,
    DiscoveryRequest,
    DiscoveryResult,
    OnboardingBundle,
)

type OnboardingDocument = (
    DiscoveryRequest | DiscoveryResult | DecisionSet | OnboardingBundle
)


def canonical_onboarding_json(document: OnboardingDocument) -> bytes:
    return (
        json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def parse_discovery_request_json(
    payload: str | bytes,
) -> DiscoveryRequest:
    return _parse_onboarding_json(payload, DiscoveryRequest)


def parse_discovery_result_json(
    payload: str | bytes,
) -> DiscoveryResult:
    return _parse_onboarding_json(payload, DiscoveryResult)


def parse_decision_set_json(payload: str | bytes) -> DecisionSet:
    return _parse_onboarding_json(payload, DecisionSet)


def parse_onboarding_bundle_json(
    payload: str | bytes,
) -> OnboardingBundle:
    from ucf.onboarding.bundle import validate_onboarding_bundle

    bundle = _parse_onboarding_json(payload, OnboardingBundle)
    validate_onboarding_bundle(bundle)
    return bundle


def canonical_onboarding_digest(document: OnboardingDocument) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(canonical_onboarding_json(document)).hexdigest(),
    )


def _parse_onboarding_json(payload, model):
    decoded = decode_strict_json_object(payload)
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)
