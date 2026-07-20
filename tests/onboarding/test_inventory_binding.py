from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ucf.inventory import (
    IgnorePolicy,
    IgnoreRule,
    canonical_inventory_json,
)
from ucf.ir.models import Digest
from ucf.onboarding import (
    OnboardingErrorCode,
    OnboardingValidationError,
    validate_discovery_exchange,
)

from .test_codec import _request, _result


def _digest(payload: bytes) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(payload).hexdigest(),
    )


def test_request_binds_policy_and_classification_not_only_source_revision():
    request = _request()
    original_policy = request.inventory.applied_policy
    changed_rule = original_policy.rules[0].model_copy(
        update={"reason": "org.ucf.inventory.generated"}
    )
    changed_policy = IgnorePolicy(
        kind="ignore_policy",
        policy_version=original_policy.policy_version,
        rules=(
            IgnoreRule.model_validate(
                changed_rule.model_dump(mode="json")
            ),
        ),
    )
    changed_inventory = request.inventory.model_copy(
        update={"applied_policy": changed_policy}
    )

    assert changed_inventory.source_revision == (
        request.inventory.source_revision
    )
    assert canonical_inventory_json(changed_inventory) != (
        canonical_inventory_json(request.inventory)
    )
    with pytest.raises(ValidationError, match="exact snapshot"):
        type(request)(
            **{
                **request.model_dump(mode="python"),
                "inventory": changed_inventory,
            }
        )


@pytest.mark.parametrize(
    "field",
    ["subject_uri", "source_revision", "canonical_digest"],
)
def test_result_must_bind_the_exact_discovery_request_inventory(field: str):
    request = _request()
    result = _result()
    binding = result.inventory_binding
    if field == "subject_uri":
        replacement = "urn:ucf:repository:other"
    elif field == "source_revision":
        replacement = _digest(b"other source revision\n")
    else:
        replacement = _digest(b"other canonical inventory\n")
    changed = result.model_copy(
        update={
            "inventory_binding": binding.model_copy(
                update={field: replacement}
            )
        }
    )

    with pytest.raises(OnboardingValidationError) as captured:
        validate_discovery_exchange(request, changed)

    assert captured.value.code is (
        OnboardingErrorCode.DOCUMENT_IDENTITY_MISMATCH
    )
    assert captured.value.location == f"$.inventory_binding.{field}"
