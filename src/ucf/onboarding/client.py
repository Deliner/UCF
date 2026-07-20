from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    Method,
    OperationKind,
    OperationParams,
    ProcessTimeouts,
    ProtocolCode,
    Request,
    encode_frame,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_VERSION,
    InventoryRequest,
    InventorySnapshot,
    canonical_inventory_json,
    collect_inventory_from_process,
)
from ucf.ir.models import Digest
from ucf.onboarding.models import (
    DISCOVERY_CAPABILITY,
    DISCOVERY_REQUEST_SCHEMA_URI,
    ONBOARDING_VERSION,
    DiscoveryRequest,
    DiscoveryResult,
    InventoryBinding,
)
from ucf.onboarding.validation import validate_discovery_exchange
from ucf.onboarding.wire import (
    discovery_request_to_payload,
    discovery_result_from_payload,
)


@dataclass(frozen=True)
class OnboardingEvidence:
    inventory: InventorySnapshot
    discovery: DiscoveryResult


async def collect_onboarding_evidence(
    *,
    command: tuple[str, ...],
    cwd: Path,
    inventory_request: InventoryRequest,
    timeouts: ProcessTimeouts | None = None,
    operation_timeout: float | None = None,
) -> OnboardingEvidence:
    """Collect inventory and discovery in one external adapter session."""

    adapter = AdapterProcess(
        command=command,
        cwd=cwd,
        requested_capabilities=(
            CapabilityRequest(
                kind="capability_request",
                name=INVENTORY_CAPABILITY,
                minimum_version=INVENTORY_VERSION,
                required=True,
            ),
            CapabilityRequest(
                kind="capability_request",
                name=DISCOVERY_CAPABILITY,
                minimum_version=ONBOARDING_VERSION,
                required=True,
            ),
        ),
        timeouts=timeouts,
    )
    try:
        initialized = await adapter.start()
        inventory = await collect_inventory_from_process(
            adapter,
            request=inventory_request,
            operation_timeout=operation_timeout,
        )
        request = _discovery_request(inventory)
        payload = discovery_request_to_payload(request)
        _preflight_discovery_frame(payload)
        raw_result = await adapter.call(
            Method.DISCOVER,
            payload,
            timeout=operation_timeout,
        )
        try:
            result = discovery_result_from_payload(raw_result)
            validate_discovery_exchange(request, result)
            if result.producer != initialized.adapter:
                raise ValueError(
                    "discovery producer differs from initialized adapter"
                )
        except (TypeError, ValueError) as error:
            raise _invalid_adapter_output() from error
        return OnboardingEvidence(
            inventory=inventory,
            discovery=result,
        )
    finally:
        await adapter.close()


def _discovery_request(inventory: InventorySnapshot) -> DiscoveryRequest:
    canonical = canonical_inventory_json(inventory)
    binding = InventoryBinding(
        kind="inventory_binding",
        schema_uri=inventory.schema_uri,
        inventory_version=inventory.inventory_version,
        subject_uri=inventory.subject_uri,
        source_revision=inventory.source_revision,
        canonical_digest=Digest(
            kind="digest",
            algorithm="sha-256",
            value=hashlib.sha256(canonical).hexdigest(),
        ),
    )
    return DiscoveryRequest(
        kind="discovery_request_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DISCOVERY_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=DISCOVERY_CAPABILITY,
            version=ONBOARDING_VERSION,
        ),
        inventory_binding=binding,
        inventory=inventory,
    )


def _preflight_discovery_frame(payload) -> None:
    encode_frame(
        Request(
            jsonrpc="2.0",
            id="x" * 64,
            method=Method.DISCOVER,
            params=OperationParams(
                kind=OperationKind.DISCOVER_REQUEST,
                payload=payload,
            ),
        )
    )


def _invalid_adapter_output() -> AdapterProtocolError:
    return AdapterProtocolError(
        ErrorCategory.PROCESS_FAILURE,
        ProtocolCode.INVALID_ADAPTER_OUTPUT,
        "adapter returned an invalid discovery result",
    )
