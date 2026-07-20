from __future__ import annotations

import json

from ucf.adapter_protocol import (
    AdapterPayload,
    ir_value_to_json_profile,
    json_profile_to_ir_value,
)
from ucf.onboarding.models import (
    DISCOVERY_REQUEST_SCHEMA_URI,
    DISCOVERY_RESULT_SCHEMA_URI,
    ONBOARDING_VERSION,
    DiscoveryRequest,
    DiscoveryResult,
)


def discovery_request_to_payload(
    request: DiscoveryRequest,
) -> AdapterPayload:
    return _to_payload(request, DISCOVERY_REQUEST_SCHEMA_URI)


def discovery_request_from_payload(
    payload: AdapterPayload,
) -> DiscoveryRequest:
    return _from_payload(
        payload,
        schema_uri=DISCOVERY_REQUEST_SCHEMA_URI,
        model=DiscoveryRequest,
    )


def discovery_result_to_payload(
    result: DiscoveryResult,
) -> AdapterPayload:
    return _to_payload(result, DISCOVERY_RESULT_SCHEMA_URI)


def discovery_result_from_payload(
    payload: AdapterPayload,
) -> DiscoveryResult:
    return _from_payload(
        payload,
        schema_uri=DISCOVERY_RESULT_SCHEMA_URI,
        model=DiscoveryResult,
    )


def _to_payload(document, schema_uri: str) -> AdapterPayload:
    return AdapterPayload(
        kind="adapter_payload",
        schema_uri=schema_uri,
        schema_version=ONBOARDING_VERSION,
        value=json_profile_to_ir_value(
            document.model_dump(mode="json")
        ),
    )


def _from_payload(payload, *, schema_uri: str, model):
    if not isinstance(payload, AdapterPayload):
        raise ValueError("discovery payload must be an adapter payload")
    if (
        payload.schema_uri != schema_uri
        or payload.schema_version != ONBOARDING_VERSION
    ):
        raise ValueError("discovery payload coordinates are incompatible")
    decoded = ir_value_to_json_profile(payload.value)
    if not isinstance(decoded, dict):
        raise ValueError("discovery payload root must be a record")
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return model.model_validate_json(normalized)
