from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir.models import Producer
from ucf.ratchet import (
    RatchetPolicy as RatchetV1Policy,
)
from ucf.ratchet import (
    RatchetRule as RatchetV1Rule,
)
from ucf.ratchet import (
    RatchetValidationError as RatchetV1ValidationError,
)
from ucf.ratchet import (
    canonical_ratchet_json as canonical_ratchet_v1_json,
)
from ucf.ratchet import (
    derive_policy_id as derive_v1_policy_id,
)
from ucf.ratchet import (
    parse_ratchet_policy_json as parse_ratchet_v1_policy_json,
)
from ucf.ratchet.v2 import (
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetPolicy,
    RatchetRule,
    RatchetValidationError,
    canonical_ratchet_json,
    derive_policy_id,
    parse_ratchet_policy_json,
)


def _producer() -> Producer:
    return Producer(
        kind="producer",
        name="org.ucf.fixture-ratchet",
        version="1.0.0",
    )


def _policy() -> RatchetPolicy:
    rule = RatchetRule(
        kind="ratchet_rule",
        id="required-check",
        version="1.0.0",
        procedure_uri="urn:ucf:ratchet-rule:required-check:1.0.0",
        producer=_producer(),
        summary="Require the selected check.",
    )
    provisional = RatchetPolicy(
        kind="ratchet_policy",
        ratchet_version=RATCHET_VERSION,
        schema_uri=RATCHET_POLICY_SCHEMA_URI,
        id=f"policy.{'0' * 64}",
        evaluator=CapabilitySelection(
            kind="capability",
            name=RATCHET_EVALUATOR_CAPABILITY,
            version=RATCHET_VERSION,
        ),
        rules=(rule,),
    )
    return provisional.model_copy(update={"id": derive_policy_id(provisional)})


def _v1_policy() -> RatchetV1Policy:
    rule = RatchetV1Rule(
        kind="ratchet_rule",
        id="required-check",
        version="1.0.0",
        procedure_uri="urn:ucf:ratchet-rule:required-check:1.0.0",
        producer=_producer(),
        summary="Require the selected check.",
    )
    provisional = RatchetV1Policy(
        kind="ratchet_policy",
        ratchet_version="1.0.0",
        schema_uri="urn:ucf:ratchet:policy:1.0.0",
        id=f"policy.{'0' * 64}",
        evaluator=CapabilitySelection(
            kind="capability",
            name="org.ucf.ratchet.baseline",
            version="1.0.0",
        ),
        rules=(rule,),
    )
    return provisional.model_copy(
        update={"id": derive_v1_policy_id(provisional)}
    )


def test_v2_policy_has_an_exact_isolated_major_version_boundary() -> None:
    policy = _policy()
    encoded = canonical_ratchet_json(policy)

    assert RATCHET_VERSION == "2.0.0"
    assert RATCHET_POLICY_SCHEMA_URI == "urn:ucf:ratchet:policy:2.0.0"
    assert parse_ratchet_policy_json(encoded) == policy
    assert canonical_ratchet_json(parse_ratchet_policy_json(encoded)) == encoded

    with pytest.raises((ValidationError, RatchetV1ValidationError)):
        parse_ratchet_v1_policy_json(encoded)
    with pytest.raises((ValidationError, RatchetValidationError)):
        parse_ratchet_policy_json(canonical_ratchet_v1_json(_v1_policy()))

    payload = json.loads(encoded)
    payload["unknown"] = True
    with pytest.raises(ValidationError):
        parse_ratchet_policy_json(json.dumps(payload))

    mixed = encoded.decode().replace(
        '"schema_uri":"urn:ucf:ratchet:policy:2.0.0"',
        '"schema_uri":"urn:ucf:ratchet:policy:1.0.0"',
    )
    with pytest.raises(RatchetValidationError) as captured:
        parse_ratchet_policy_json(mixed)
    assert captured.value.location == "$.schema_uri"

    duplicate = encoded.decode().replace(
        '"kind":"ratchet_policy"',
        '"kind":"ratchet_policy","kind":"ratchet_policy"',
        1,
    )
    with pytest.raises(Exception) as captured:
        parse_ratchet_policy_json(duplicate)
    assert captured.type is not KeyError
