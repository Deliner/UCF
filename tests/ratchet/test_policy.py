from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.ir import IRValidationError
from ucf.ir.models import Producer
from ucf.ratchet import (
    RATCHET_EVALUATOR_CAPABILITY,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetErrorCode,
    RatchetPolicy,
    RatchetRule,
    RatchetValidationError,
    canonical_ratchet_json,
    derive_policy_id,
    parse_ratchet_policy_json,
)


def _rule(identifier: str = "rule.missing-tested-evidence") -> RatchetRule:
    return RatchetRule(
        kind="ratchet_rule",
        id=identifier,
        version="1.0.0",
        procedure_uri=(
            "urn:ucf:ratchet-rule:missing-tested-evidence:1.0.0"
        ),
        producer=Producer(
            kind="producer",
            name="org.ucf.fixture-rules",
            version="1.0.0",
        ),
        summary="Require a named tested claim for this behavior.",
    )


def _policy(*rules: RatchetRule) -> RatchetPolicy:
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
        rules=rules or (_rule(),),
    )
    return provisional.model_copy(
        update={"id": derive_policy_id(provisional)}
    )


def test_policy_round_trips_as_exact_canonical_json() -> None:
    policy = _policy()
    encoded = canonical_ratchet_json(policy)

    assert encoded.endswith(b"\n")
    assert parse_ratchet_policy_json(encoded) == policy
    assert canonical_ratchet_json(parse_ratchet_policy_json(encoded)) == (
        encoded
    )
    assert policy.id.startswith("policy.")


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("unknown", ValidationError),
        ("version", ValidationError),
        ("schema", ValidationError),
        ("capability", ValidationError),
        ("procedure", ValidationError),
        ("identity", RatchetValidationError),
        ("order", RatchetValidationError),
        ("duplicate", RatchetValidationError),
    ],
)
def test_policy_rejects_every_untrusted_boundary(
    mutation: str,
    expected: type[Exception],
) -> None:
    first = _rule("rule.alpha")
    second = _rule("rule.beta").model_copy(
        update={
            "procedure_uri": "urn:ucf:ratchet-rule:beta:1.0.0",
            "summary": "Second exact rule.",
        }
    )
    payload = _policy(first, second).model_dump(mode="json")
    if mutation == "unknown":
        payload["unexpected"] = True
    elif mutation == "version":
        payload["ratchet_version"] = "2.0.0"
    elif mutation == "schema":
        payload["schema_uri"] = "urn:ucf:ratchet:policy:2.0.0"
    elif mutation == "capability":
        payload["evaluator"]["name"] = "org.ucf.ratchet.unsupported"
    elif mutation == "procedure":
        payload["rules"][0]["procedure_uri"] = (
            "urn:ucf:ratchet-rule:alpha"
        )
    elif mutation == "identity":
        payload["id"] = f"policy.{'f' * 64}"
    elif mutation == "order":
        payload["rules"] = list(reversed(payload["rules"]))
    else:
        payload["rules"][1]["id"] = payload["rules"][0]["id"]
    encoded = json.dumps(payload, separators=(",", ":"))

    with pytest.raises(expected) as captured:
        parse_ratchet_policy_json(encoded)

    if mutation == "identity":
        assert captured.value.code is (
            RatchetErrorCode.CONTENT_IDENTITY_MISMATCH
        )
        assert captured.value.location == "$.id"
    elif mutation == "order":
        assert captured.value.code is RatchetErrorCode.NON_CANONICAL_ORDER
        assert captured.value.location == "$.rules"
    elif mutation == "duplicate":
        assert captured.value.code is RatchetErrorCode.DUPLICATE_IDENTITY
        assert captured.value.location == "$.rules"


def test_policy_parser_rejects_duplicate_raw_json_member() -> None:
    encoded = canonical_ratchet_json(_policy()).decode("utf-8")
    duplicate = encoded.replace(
        '"kind":"ratchet_policy"',
        '"kind":"ratchet_policy","kind":"ratchet_policy"',
        1,
    )

    with pytest.raises(IRValidationError):
        parse_ratchet_policy_json(duplicate)
