from __future__ import annotations

import asyncio
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from tests.ecosystems.test_python_legacy_quote_mapping import _mapping_request
from tests.ecosystems.test_python_legacy_quote_verification import (
    _verification_request,
)
from tests.inventory.reference_adapter_harness import nonfollowing_tree_manifest
from tests.onboarding.test_decisions import _decisions
from tests.onboarding.test_process_client import (
    FAST_TIMEOUTS,
    FIXTURE_ROOT,
    REFERENCE_ADAPTER,
)
from tests.onboarding.test_process_client import _request as _inventory_request
from ucf.adapter_protocol import (
    AdapterProcess,
    CapabilityRequest,
    Method,
)
from ucf.evidence_status import (
    EvidenceStatus,
    EvidenceStatusReasonCode,
    assess_verification_evidence,
    record_verification_evidence,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationMappingResult,
    derive_execution_verification_result_id,
    execution_verification_request_to_payload,
    execution_verification_result_from_payload,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    project_execution_verification,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    InventorySnapshot,
    collect_inventory_from_process,
)
from ucf.ir.models import Producer
from ucf.ir.trust_models import Claim, ClaimLevel
from ucf.onboarding import (
    OnboardingBundle,
    build_onboarding_bundle,
    collect_onboarding_evidence,
)


@dataclass(frozen=True)
class _EvidenceContext:
    bundle: OnboardingBundle
    inventory: InventorySnapshot
    mapping: ImplementationMappingResult
    request: ExecutionVerificationRequest
    result: ExecutionVerificationResult
    adapter: Producer
    capabilities: dict[str, str]


def test_real_python_verification_records_fresh_tested_evidence() -> None:
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)

    context = _real_context(FIXTURE_ROOT)
    envelope = _record(context)
    assessment = _assess(envelope, context, context)
    projection = project_execution_verification(
        context.result,
        **_verification_arguments(context),
    )
    claims = tuple(
        record
        for record in projection.tested_trust.records
        if isinstance(record, Claim)
    )

    assert context.result.outcome == "passed"
    assert assessment.status is EvidenceStatus.FRESH
    assert assessment.reasons == ()
    assert [claim.level for claim in claims] == [ClaimLevel.TESTED]
    assert all(claim.level is not ClaimLevel.VERIFIED for claim in claims)
    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before


def test_python_evidence_drift_is_selective_for_exact_native_inputs(
    tmp_path: Path,
) -> None:
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)
    recorded = _real_context(FIXTURE_ROOT)
    envelope = _record(recorded)

    unrelated_root = _copy_fixture(tmp_path / "unrelated")
    note = unrelated_root / "docs" / "legacy-note.txt"
    note.parent.mkdir()
    note.write_text("Unrelated legacy inventory evidence.\n", encoding="utf-8")
    unrelated_observed = _real_context(unrelated_root)
    unrelated = _hold_result_coordinate(unrelated_observed, recorded)

    target_root = _copy_fixture(tmp_path / "target")
    service = target_root / "src" / "legacy_quote" / "service.py"
    service.write_text(
        service.read_text(encoding="utf-8") + "\n# bound source drift\n",
        encoding="utf-8",
    )
    target_observed = _real_context(target_root)
    target = _hold_result_coordinate(target_observed, recorded)

    unrelated_assessment = _assess(envelope, recorded, unrelated)
    target_assessment = _assess(envelope, recorded, target)

    assert unrelated.inventory.source_revision != (
        recorded.inventory.source_revision
    )
    assert unrelated.request.environment == recorded.request.environment
    assert unrelated_observed.result.outcome == "passed"
    assert unrelated_assessment.status is EvidenceStatus.FRESH
    assert unrelated_assessment.reasons == ()

    assert target.inventory.source_revision != recorded.inventory.source_revision
    assert target.request.environment != recorded.request.environment
    assert target_observed.result.outcome == "passed"
    assert target_assessment.status is EvidenceStatus.STALE
    assert tuple(reason.code for reason in target_assessment.reasons) == (
        EvidenceStatusReasonCode.ENVIRONMENT_CHANGED,
        EvidenceStatusReasonCode.MAPPING_BINDING_CHANGED,
        EvidenceStatusReasonCode.SOURCE_BINDING_CHANGED,
    )
    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before


def _copy_fixture(destination: Path) -> Path:
    shutil.copytree(
        FIXTURE_ROOT,
        destination,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return destination


def _adapter_command() -> tuple[str, ...]:
    return (
        sys.executable,
        "-B",
        "-X",
        "utf8",
        str(REFERENCE_ADAPTER),
    )


def _reviewed_bundle(root: Path) -> OnboardingBundle:
    async def scenario():
        return await collect_onboarding_evidence(
            command=_adapter_command(),
            cwd=root,
            inventory_request=_inventory_request(7),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=5.0,
        )

    evidence = asyncio.run(scenario())
    return build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _decisions(evidence.discovery),
    )


def _real_context(root: Path) -> _EvidenceContext:
    bundle = _reviewed_bundle(root)
    mapping_request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=_adapter_command(),
            cwd=root,
            requested_capabilities=tuple(
                CapabilityRequest(
                    kind="capability_request",
                    name=name,
                    minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                    required=True,
                )
                for name in (
                    INVENTORY_CAPABILITY,
                    IMPLEMENTATION_MAPPING_CAPABILITY,
                    EXECUTION_VERIFICATION_CAPABILITY,
                )
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(7),
                operation_timeout=5.0,
            )
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(mapping_request),
                    timeout=5.0,
                )
            )
            request = _verification_request(
                root_path=root,
                inventory=inventory.model_dump(mode="json"),
                bundle=bundle,
                mapping=mapping,
            )
            result = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            )
            capabilities = dict(adapter.negotiated_capabilities)
        finally:
            await adapter.close()
        assert adapter.stderr_total_bytes == 0
        return initialized.adapter, inventory, mapping, request, result, capabilities

    adapter, inventory, mapping, request, result, capabilities = asyncio.run(
        scenario()
    )
    assert inventory == bundle.inventory
    return _EvidenceContext(
        bundle=bundle,
        inventory=inventory,
        mapping=mapping,
        request=request,
        result=result,
        adapter=adapter,
        capabilities=capabilities,
    )


def _record(context: _EvidenceContext):
    return record_verification_evidence(
        context.result,
        **_verification_arguments(context),
    )


def _assess(envelope, recorded: _EvidenceContext, current: _EvidenceContext):
    return assess_verification_evidence(
        envelope,
        recorded_result=recorded.result,
        recorded_request=recorded.request,
        recorded_mapping_result=recorded.mapping,
        recorded_bundle=recorded.bundle,
        recorded_current_inventory=recorded.inventory,
        recorded_mapping_initialized_adapter=recorded.adapter,
        recorded_initialized_adapter=recorded.adapter,
        recorded_negotiated_capabilities=recorded.capabilities,
        current_result=current.result,
        current_request=current.request,
        current_mapping_result=current.mapping,
        current_bundle=current.bundle,
        current_inventory=current.inventory,
        current_mapping_initialized_adapter=current.adapter,
        current_initialized_adapter=current.adapter,
        current_negotiated_capabilities=current.capabilities,
    )


def _verification_arguments(context: _EvidenceContext) -> dict[str, object]:
    return {
        "request": context.request,
        "mapping_result": context.mapping,
        "bundle": context.bundle,
        "current_inventory": context.inventory,
        "mapping_initialized_adapter": context.adapter,
        "initialized_adapter": context.adapter,
        "negotiated_capabilities": context.capabilities,
    }


def _hold_result_coordinate(
    current: _EvidenceContext,
    recorded: _EvidenceContext,
) -> _EvidenceContext:
    # Wall-clock execution time is independently freshness-sensitive. Both
    # unmodified process results passed; hold time fixed to isolate source drift.
    provisional = current.result.model_copy(
        update={"executed_at": recorded.result.executed_at}
    )
    result = provisional.model_copy(
        update={"id": derive_execution_verification_result_id(provisional)}
    )
    return replace(current, result=result)
