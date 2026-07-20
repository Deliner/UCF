#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from ucf.adapter_protocol import (
    AdapterDispatcher,
    AdapterPayload,
    CapabilitySelection,
    ErrorCategory,
    ErrorData,
    ErrorObject,
    ErrorResponse,
    Method,
    ProtocolCode,
    RequestContext,
    run_stdio_server,
)
from ucf.ir.models import Producer, StringValue
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_CAPABILITY,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEvidenceAcceptedResult,
    RuntimeEvidenceRejectedResult,
    RuntimeObservation,
    RuntimeObservationRuleRef,
    RuntimePolicyRejectionCode,
    RuntimeSanitizationSummary,
    derive_runtime_evidence_result_id,
    runtime_evidence_request_from_payload,
    runtime_evidence_result_to_payload,
)

VERIFICATION_CAPABILITY = "org.ucf.adapter.verification"
SELECTOR_URI = "urn:ucf:fixture-selector:reservation-created:1.0.0"
SECRET_SELECTOR_URI = "urn:ucf:fixture-selector:selected-secret:1.0.0"
PERSONAL_SELECTOR_URI = (
    "urn:ucf:fixture-selector:selected-personal-data:1.0.0"
)
ATTRIBUTE_KEY = "ucf.observation.reservation.status"
PRODUCER = Producer(
    kind="producer",
    name="org.ucf.fixture-runtime-adapter",
    version="1.0.0",
)


def _strict_json(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    decoded = json.loads(
        raw,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    if not isinstance(decoded, dict):
        raise ValueError("recording root must be an object")
    return decoded


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("recording contains a duplicate member")
        result[name] = value
    return result


def _reject_constant(value: str):
    raise ValueError("recording contains a non-finite number")


def _span_attributes(recording: dict[str, object]) -> dict[str, str]:
    spans = recording["resourceSpans"]
    if not isinstance(spans, list) or len(spans) != 1:
        raise ValueError("fixture recording has unsupported resource spans")
    scope_spans = spans[0]["scopeSpans"]
    if not isinstance(scope_spans, list) or len(scope_spans) != 1:
        raise ValueError("fixture recording has unsupported scope spans")
    items = scope_spans[0]["spans"]
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("fixture recording has unsupported spans")
    attributes = items[0]["attributes"]
    if not isinstance(attributes, list):
        raise ValueError("fixture recording attributes must be a list")
    result = {}
    for attribute in attributes:
        key = attribute["key"]
        value = attribute["value"]["stringValue"]
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("fixture attribute is not a string")
        if key in result:
            raise ValueError("fixture attribute key is duplicated")
        result[key] = value
    return result


def _accepted(request, recording_path: Path):
    revision = hashlib.sha256(recording_path.read_bytes()).hexdigest()
    if revision != request.source.source_revision.value:
        raise ValueError("recording revision differs from request")
    attributes = _span_attributes(_strict_json(recording_path))
    rules = {rule.selector_uri: rule for rule in request.policy.rules}
    unsafe_reasons = []
    if SECRET_SELECTOR_URI in rules:
        if "fixture.secret" not in attributes:
            raise ValueError("fixture secret category is absent")
        unsafe_reasons.append(
            RuntimePolicyRejectionCode.SELECTED_SECRET
        )
    if PERSONAL_SELECTOR_URI in rules:
        if "fixture.personal" not in attributes:
            raise ValueError("fixture personal-data category is absent")
        unsafe_reasons.append(
            RuntimePolicyRejectionCode.SELECTED_PERSONAL_DATA
        )
    if unsafe_reasons:
        return _rejected(request, *unsafe_reasons)
    if set(rules) != {SELECTOR_URI}:
        raise ValueError("fixture selector policy is unsupported")
    rule = rules[SELECTOR_URI]
    value = attributes.get(ATTRIBUTE_KEY)
    if not isinstance(rule.assertion.value, StringValue):
        raise ValueError("fixture rule value kind is unsupported")
    if value != rule.assertion.value.value:
        return _rejected(request)
    provisional = RuntimeEvidenceAcceptedResult(
        kind="runtime_evidence_result",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri="urn:ucf:adapter:runtime-evidence-result:1.0.0",
        id=f"result.{'0' * 64}",
        status="accepted",
        request=request,
        producer=PRODUCER,
        capability=CapabilitySelection(
            kind="capability",
            name=RUNTIME_EVIDENCE_CAPABILITY,
            version=RUNTIME_EVIDENCE_VERSION,
        ),
        procedure_uri=request.adapter_procedure_uri,
        sanitization=RuntimeSanitizationSummary(
            kind="runtime_sanitization_summary",
            selected_rule_count=1,
            forbidden_match_count=0,
            raw_retained=False,
        ),
        observations=(
            RuntimeObservation(
                kind="runtime_observation",
                rule=RuntimeObservationRuleRef(
                    kind="runtime_observation_rule_ref",
                    target_id=rule.id,
                ),
            ),
        ),
    )
    return provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )


def _rejected(
    request,
    *reasons: RuntimePolicyRejectionCode,
):
    if not reasons:
        reasons = (
            RuntimePolicyRejectionCode.SELECTED_VALUE_NOT_ALLOWED,
        )
    provisional = RuntimeEvidenceRejectedResult(
        kind="runtime_evidence_result",
        runtime_evidence_version=RUNTIME_EVIDENCE_VERSION,
        schema_uri="urn:ucf:adapter:runtime-evidence-result:1.0.0",
        id=f"result.{'0' * 64}",
        status="rejected",
        request=request,
        producer=PRODUCER,
        capability=CapabilitySelection(
            kind="capability",
            name=RUNTIME_EVIDENCE_CAPABILITY,
            version=RUNTIME_EVIDENCE_VERSION,
        ),
        procedure_uri=request.adapter_procedure_uri,
        reason_codes=tuple(sorted(set(reasons))),
    )
    return provisional.model_copy(
        update={"id": derive_runtime_evidence_result_id(provisional)}
    )


async def _handle(
    method: Method,
    payload: object,
    context: RequestContext,
) -> object:
    del context
    if method is not Method.VERIFY or not isinstance(payload, AdapterPayload):
        raise ValueError("runtime fixture accepts only verify requests")
    request = runtime_evidence_request_from_payload(payload)
    if MODE == "hang":
        await asyncio.Event().wait()
    if MODE == "wrong-profile":
        return payload.model_copy(
            update={
                "schema_uri": "urn:ucf:adapter:wrong-result:1.0.0",
            }
        )
    if MODE == "rejected":
        result = _rejected(request)
    else:
        result = _accepted(request, RECORDING_PATH)
    if MODE == "stderr":
        forbidden = _span_attributes(_strict_json(RECORDING_PATH))[
            "fixture.secret"
        ]
        sys.stderr.write(forbidden)
        sys.stderr.flush()
    return runtime_evidence_result_to_payload(result)


class _PeerErrorDispatcher:
    def __init__(self, delegate: AdapterDispatcher) -> None:
        self._delegate = delegate

    @property
    def state(self):
        return self._delegate.state

    async def dispatch(self, request):
        if request.method is Method.VERIFY:
            forbidden = _span_attributes(_strict_json(RECORDING_PATH))[
                "fixture.personal"
            ]
            return ErrorResponse(
                jsonrpc="2.0",
                id=request.id,
                error=ErrorObject(
                    code=-32000,
                    message=forbidden,
                    data=ErrorData(
                        category=ErrorCategory.ADAPTER_FAILURE,
                        ucf_code=ProtocolCode.OPERATION_FAILED,
                    ),
                ),
            )
        return await self._delegate.dispatch(request)


def _dispatcher():
    capabilities = [VERIFICATION_CAPABILITY]
    if MODE != "missing-runtime-capability":
        capabilities.append(RUNTIME_EVIDENCE_CAPABILITY)
    dispatcher = AdapterDispatcher(
        adapter=PRODUCER,
        offered_capabilities=tuple(
            CapabilitySelection(
                kind="capability",
                name=name,
                version=RUNTIME_EVIDENCE_VERSION,
            )
            for name in capabilities
        ),
        handler=_handle,
    )
    if MODE == "peer-error":
        return _PeerErrorDispatcher(dispatcher)
    return dispatcher


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument(
        "--mode",
        choices=(
            "normal",
            "rejected",
            "missing-runtime-capability",
            "wrong-profile",
            "stderr",
            "peer-error",
            "hang",
        ),
        default="normal",
    )
    parser.add_argument("--pid-file", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    OPTIONS = _parse_args()
    RECORDING_PATH = OPTIONS.recording
    MODE = OPTIONS.mode
    if OPTIONS.pid_file is not None:
        OPTIONS.pid_file.write_text(str(os.getpid()), encoding="ascii")
    raise SystemExit(run_stdio_server(_dispatcher()))
