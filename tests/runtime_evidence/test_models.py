from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ucf.ir.models import (
    Digest,
    DomainTarget,
    EntityKind,
    StringValue,
)
from ucf.ir.trust_models import (
    BehaviorEntityRef,
    FactAssertion,
)
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_POLICY_SCHEMA_URI,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEvidencePolicy,
    RuntimeObservationRule,
    canonical_runtime_evidence_json,
    parse_runtime_evidence_policy_json,
)

_BEHAVIOR_DIGEST = Digest(
    kind="digest",
    algorithm="sha-256",
    value="a" * 64,
)


def _rule(
    identifier: str = "rule.reservation-created",
    *,
    value: str = "created",
) -> RuntimeObservationRule:
    return RuntimeObservationRule(
        kind="runtime_observation_rule",
        id=identifier,
        selector_uri=(
            "urn:ucf:fixture-selector:reservation-created:1.0.0"
        ),
        subject=BehaviorEntityRef(
            kind="behavior_entity_ref",
            document_id="document.checkout-reservation",
            ir_version="1.0.0",
            canonical_digest=_BEHAVIOR_DIGEST,
            target_kind=EntityKind.OBSERVATION,
            target_id="observation.reservation-created",
        ),
        assertion=FactAssertion(
            kind="fact_assertion",
            target=DomainTarget(
                kind="domain_target",
                subject="reservation",
                path=("status",),
            ),
            value=StringValue(kind="string", value=value),
        ),
    )


def _policy(*rules: RuntimeObservationRule) -> RuntimeEvidencePolicy:
    return RuntimeEvidencePolicy(
        kind="runtime_evidence_policy",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri=RUNTIME_EVIDENCE_POLICY_SCHEMA_URI,
        policy_uri="urn:ucf:fixture-policy:runtime-import:1.0.0",
        secret_handling="reject",
        personal_data_handling="reject",
        unselected_handling="omit",
        raw_retention="none",
        rules=rules or (_rule(),),
    )


def test_policy_is_exact_versioned_and_fail_closed() -> None:
    policy = _policy()
    encoded = canonical_runtime_evidence_json(policy)

    assert encoded.endswith(b"\n")
    assert parse_runtime_evidence_policy_json(encoded) == policy
    assert (
        canonical_runtime_evidence_json(
            parse_runtime_evidence_policy_json(encoded)
        )
        == encoded
    )
    assert policy.secret_handling == "reject"
    assert policy.personal_data_handling == "reject"
    assert policy.unselected_handling == "omit"
    assert policy.raw_retention == "none"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_evidence_version", "2.0.0"),
        ("schema_uri", "urn:ucf:runtime-evidence:policy:2.0.0"),
        ("secret_handling", "redact"),
        ("personal_data_handling", "hash"),
        ("unselected_handling", "retain"),
        ("raw_retention", "bounded"),
    ],
)
def test_policy_rejects_incompatible_or_unsafe_semantics(
    field: str,
    value: str,
) -> None:
    payload = _policy().model_dump(mode="json")
    payload[field] = value

    with pytest.raises(ValidationError):
        parse_runtime_evidence_policy_json(
            json.dumps(payload, separators=(",", ":"))
        )


def test_policy_rejects_unknown_duplicate_unsorted_and_unsafe_rules() -> None:
    second = _rule("rule.second", value="reserved").model_copy(
        update={
            "selector_uri": "urn:ucf:fixture-selector:second:1.0.0",
        }
    )
    payload = _policy(_rule(), second).model_dump(mode="json")

    unknown = dict(payload)
    unknown["future"] = True
    with pytest.raises(ValidationError):
        parse_runtime_evidence_policy_json(json.dumps(unknown))

    duplicate = dict(payload)
    duplicate["rules"] = [payload["rules"][0], payload["rules"][0]]
    with pytest.raises(ValueError, match="duplicate"):
        parse_runtime_evidence_policy_json(json.dumps(duplicate))

    unsorted = dict(payload)
    unsorted["rules"] = list(reversed(payload["rules"]))
    with pytest.raises(ValueError, match="order"):
        parse_runtime_evidence_policy_json(json.dumps(unsorted))

    unsafe_value = json.loads(json.dumps(payload))
    unsafe_value["rules"][0]["assertion"]["value"]["value"] = "x" * 129
    with pytest.raises(ValidationError):
        parse_runtime_evidence_policy_json(json.dumps(unsafe_value))

    encoded = canonical_runtime_evidence_json(_policy()).decode("utf-8")
    raw_duplicate = encoded.replace(
        '"kind":"runtime_evidence_policy"',
        (
            '"kind":"runtime_evidence_policy",'
            '"kind":"runtime_evidence_policy"'
        ),
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_runtime_evidence_policy_json(raw_duplicate)


def test_policy_rejects_unsafe_identity_or_ambiguous_projection() -> None:
    unsafe_selector = _rule().model_dump(mode="json")
    unsafe_selector["selector_uri"] = (
        "https://user@example.test/selectors/1.0.0"
    )
    with pytest.raises(ValidationError):
        RuntimeObservationRule.model_validate_json(
            json.dumps(unsafe_selector)
        )

    unsafe_policy = _policy().model_dump(mode="json")
    unsafe_policy["policy_uri"] = "https://user@example.test/policy/1.0.0"
    with pytest.raises(ValidationError):
        RuntimeEvidencePolicy.model_validate_json(json.dumps(unsafe_policy))

    wrong_subject_kind = _rule().model_dump(mode="json")
    wrong_subject_kind["subject"]["target_kind"] = "action"
    with pytest.raises(ValidationError):
        RuntimeObservationRule.model_validate_json(
            json.dumps(wrong_subject_kind)
        )

    duplicate_projection = _rule("rule.second").model_copy(
        update={
            "selector_uri": "urn:ucf:fixture-selector:second:1.0.0",
        }
    )
    with pytest.raises(ValueError, match="projection"):
        _policy(_rule(), duplicate_projection)

    excessive_rules = _policy().model_dump(mode="json")
    excessive_rules["rules"] = [excessive_rules["rules"][0]] * 65
    with pytest.raises(ValidationError):
        parse_runtime_evidence_policy_json(json.dumps(excessive_rules))

    excessive_path = _rule().model_dump(mode="json")
    excessive_path["assertion"]["target"]["path"] = [
        f"segment-{index}" for index in range(17)
    ]
    with pytest.raises(ValidationError):
        RuntimeObservationRule.model_validate_json(
            json.dumps(excessive_path)
        )
