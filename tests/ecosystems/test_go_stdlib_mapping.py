from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GoStdlibHarness,
    GoStdlibTarget,
    go_stdlib_fixture_manifest,
)

from tests.ecosystems.test_go_stdlib_inventory import (
    FAST_TIMEOUTS,
    SOURCE_REVISION,
    _request,
)
from tests.ecosystems.test_go_stdlib_inventory import (
    _page as _inventory_page,
)
from tests.ecosystems.test_go_stdlib_reconciliation import (
    _reviewed_bundle,
)
from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    Method,
    ProtocolCode,
)
from ucf.implementation_evidence import (
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    IMPLEMENTATION_MAPPING_PROCEDURE_URI,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    ImplementationMappingRequest,
    OnboardingBundleBinding,
    canonical_implementation_evidence_json,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    validate_implementation_mapping_request,
    validate_implementation_mapping_result,
)
from ucf.inventory import collect_inventory_from_process
from ucf.ir import ClaimLevel
from ucf.ir.models import Digest, NullValue, RecordEntry, RecordValue
from ucf.onboarding import (
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    canonical_onboarding_digest,
)

MAPPING_PROCEDURE_URI = (
    "urn:ucf:adapter:go-stdlib-static-mapping:1.0.0"
)
EXPECTED_MAPPING_ID = (
    "mapping.1ac553e103d8a887e1fa971788cf6f327"
    "84ba81265498de5474353313f3274c6"
)


def test_go_stdlib_maps_the_reviewed_quote_order_deterministically(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "mapping-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )
    assert len(bundle.baseline.materializations) == 1
    materialization = bundle.baseline.materializations[0]
    candidate = next(
        candidate
        for candidate in bundle.discovery.candidates
        if candidate.id == materialization.candidate.candidate_id
    )
    assert _claim_ids(bundle, ClaimLevel.MAPPED) == ()

    request = _mapping_request(bundle)
    validate_implementation_mapping_request(request, bundle=bundle)

    first = _map(
        target=target,
        request=request,
        bundle=bundle,
        record_limit=7,
    )
    second = _map(
        target=target,
        request=request,
        bundle=bundle,
        record_limit=1,
    )

    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert first.stderr_bytes == second.stderr_bytes == 0
    assert first.stderr_tail == second.stderr_tail == b""
    assert first.inventory == second.inventory == bundle.inventory
    assert canonical_implementation_evidence_json(first.result) == (
        canonical_implementation_evidence_json(second.result)
    )
    assert first.result.request == request
    assert first.result.id == second.result.id == EXPECTED_MAPPING_ID
    assert first.result.producer.name == "org.ucf.adapter.go-stdlib"
    assert first.result.procedure_uri == MAPPING_PROCEDURE_URI
    assert len(first.result.bindings) == 1
    assert first.result.bindings[0].behavior == materialization.root
    assert first.result.bindings[0].source_records == candidate.evidence
    assert len(first.result.bindings[0].source_records) == 10
    assert first.inventory.source_revision.value == SOURCE_REVISION
    assert _claim_ids(bundle, ClaimLevel.MAPPED) == ()
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_mapping_rejects_unbound_profiles_and_recovers(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "mapping-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )
    request = _mapping_request(bundle)

    async def scenario():
        adapter = _mapping_adapter(target)
        failures: list[AdapterProtocolError] = []
        try:
            initialized = await adapter.start()
            with pytest.raises(AdapterProtocolError) as before_inventory:
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(before_inventory.value)

            first = await _inventory_page(adapter, _request(1))
            assert not first.complete
            with pytest.raises(AdapterProtocolError) as incomplete:
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(incomplete.value)

            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            assert inventory == request.inventory
            for malformed in _unbound_mapping_payloads(request):
                with pytest.raises(AdapterProtocolError) as rejected:
                    await adapter.call(
                        Method.MAP,
                        malformed,
                        timeout=10.0,
                    )
                failures.append(rejected.value)

            recovered = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(request),
                    timeout=10.0,
                )
            )
            validate_implementation_mapping_result(
                recovered,
                request=request,
                bundle=bundle,
                current_inventory=inventory,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            return (
                failures,
                recovered,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    failures, recovered, stderr_total, stderr_tail = asyncio.run(scenario())

    assert [failure.code for failure in failures[:2]] == [
        ProtocolCode.OPERATION_FAILED,
        ProtocolCode.OPERATION_FAILED,
    ]
    assert all(
        failure.category is ErrorCategory.ADAPTER_FAILURE
        for failure in failures[:2]
    )
    assert len(failures[2:]) == 7
    assert all(
        failure.code is ProtocolCode.INVALID_PARAMS
        and failure.category is ErrorCategory.PROTOCOL_FAILURE
        for failure in failures[2:]
    )
    assert recovered.id == EXPECTED_MAPPING_ID
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_mapping_invalidates_evidence_when_source_drifts(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "mapping-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )
    request = _mapping_request(bundle)
    readme = target.fixture_root / "README.md"
    original = readme.read_bytes()

    async def scenario():
        adapter = _mapping_adapter(target)
        failures: list[AdapterProtocolError] = []
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            readme.write_bytes(original + b"\nsource drift\n")
            with pytest.raises(AdapterProtocolError) as drifted:
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(drifted.value)
            readme.write_bytes(original)

            with pytest.raises(AdapterProtocolError) as invalidated:
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(invalidated.value)
            refreshed = await collect_inventory_from_process(
                adapter,
                request=_request(1),
                operation_timeout=10.0,
            )
            result = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(request),
                    timeout=10.0,
                )
            )
            validate_implementation_mapping_result(
                result,
                request=request,
                bundle=bundle,
                current_inventory=refreshed,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            return (
                inventory,
                refreshed,
                failures,
                result,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            readme.write_bytes(original)
            await adapter.close()

    inventory, refreshed, failures, result, stderr_total, stderr_tail = (
        asyncio.run(scenario())
    )

    assert inventory == refreshed == request.inventory
    assert [failure.code for failure in failures] == [
        ProtocolCode.OPERATION_FAILED,
        ProtocolCode.OPERATION_FAILED,
    ]
    assert all(
        failure.category is ErrorCategory.ADAPTER_FAILURE
        for failure in failures
    )
    assert result.id == EXPECTED_MAPPING_ID
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def _mapping_request(bundle) -> ImplementationMappingRequest:
    materialization = bundle.baseline.materializations[0]
    return ImplementationMappingRequest(
        kind="implementation_mapping_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=IMPLEMENTATION_MAPPING_PROCEDURE_URI,
        adapter_procedure_uri=MAPPING_PROCEDURE_URI,
        onboarding=OnboardingBundleBinding(
            kind="onboarding_bundle_binding",
            schema_uri=ONBOARDING_BUNDLE_SCHEMA_URI,
            schema_version=ONBOARDING_VERSION,
            canonical_digest=canonical_onboarding_digest(bundle),
        ),
        behavior=bundle.behavior,
        inventory=bundle.inventory,
        targets=(materialization.root,),
    )


def _unbound_mapping_payloads(request: ImplementationMappingRequest):
    stale_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value="0" * 64,
    )
    stale_inventory = request.inventory.model_copy(
        update={"source_revision": stale_digest}
    )
    stale_request = request.model_copy(
        update={"inventory": stale_inventory}
    )
    wrong_procedure = request.model_copy(
        update={
            "adapter_procedure_uri": (
                "urn:ucf:adapter:go-stdlib-forged-mapping:1.0.0"
            )
        }
    )
    wrong_capability = request.model_copy(
        update={
            "capability": request.capability.model_copy(
                update={"name": "org.ucf.adapter.generation"}
            )
        }
    )
    broken_behavior = request.model_copy(
        update={
            "behavior": request.behavior.model_copy(
                update={"document_id": "behavior.forged"}
            )
        }
    )
    broken_target = request.model_copy(
        update={
            "targets": (
                request.targets[0].model_copy(
                    update={"canonical_digest": stale_digest}
                ),
            )
        }
    )

    exact_payload = implementation_mapping_request_to_payload(request)
    root = exact_payload.value
    assert isinstance(root, RecordValue)
    unknown_field = exact_payload.model_copy(
        update={
            "value": RecordValue(
                kind="record",
                entries=(
                    *root.entries,
                    RecordEntry(
                        kind="record_entry",
                        name="unexpected",
                        value=NullValue(kind="null"),
                    ),
                ),
            )
        }
    )
    nested_entries = []
    for entry in root.entries:
        if entry.name != "behavior":
            nested_entries.append(entry)
            continue
        assert isinstance(entry.value, RecordValue)
        nested_entries.append(
            entry.model_copy(
                update={
                    "value": entry.value.model_copy(
                        update={"entries": tuple(reversed(entry.value.entries))}
                    )
                }
            )
        )
    noncanonical_nested_record = exact_payload.model_copy(
        update={
            "value": root.model_copy(
                update={"entries": tuple(nested_entries)}
            )
        }
    )
    return (
        implementation_mapping_request_to_payload(stale_request),
        implementation_mapping_request_to_payload(wrong_procedure),
        implementation_mapping_request_to_payload(wrong_capability),
        implementation_mapping_request_to_payload(broken_behavior),
        implementation_mapping_request_to_payload(broken_target),
        unknown_field,
        noncanonical_nested_record,
    )


def _mapping_adapter(target: GoStdlibTarget) -> AdapterProcess:
    return AdapterProcess(
        command=target.command(),
        cwd=target.fixture_root,
        requested_capabilities=(
            CapabilityRequest(
                kind="capability_request",
                name="org.ucf.adapter.inventory",
                minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                required=True,
            ),
            CapabilityRequest(
                kind="capability_request",
                name=IMPLEMENTATION_MAPPING_CAPABILITY,
                minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                required=True,
            ),
        ),
        timeouts=FAST_TIMEOUTS,
    )


class _MappingRun:
    def __init__(
        self,
        *,
        result,
        inventory,
        stderr_bytes: int,
        stderr_tail: bytes,
    ) -> None:
        self.result = result
        self.inventory = inventory
        self.stderr_bytes = stderr_bytes
        self.stderr_tail = stderr_tail


def _map(
    *,
    target: GoStdlibTarget,
    request: ImplementationMappingRequest,
    bundle,
    record_limit: int,
) -> _MappingRun:
    async def scenario() -> _MappingRun:
        adapter = _mapping_adapter(target)
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(record_limit),
                operation_timeout=10.0,
            )
            assert inventory == request.inventory
            payload = await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(request),
                timeout=10.0,
            )
            result = implementation_mapping_result_from_payload(payload)
            validate_implementation_mapping_result(
                result,
                request=request,
                bundle=bundle,
                current_inventory=inventory,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
        finally:
            await adapter.close()
        return _MappingRun(
            result=result,
            inventory=inventory,
            stderr_bytes=adapter.stderr_total_bytes,
            stderr_tail=adapter.stderr_tail,
        )

    return asyncio.run(scenario())


def _claim_ids(bundle, level: ClaimLevel) -> tuple[str, ...]:
    return next(
        summary.claim_ids
        for summary in bundle.baseline.claim_levels
        if summary.level is level
    )
