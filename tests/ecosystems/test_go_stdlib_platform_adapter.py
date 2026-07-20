from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import GoStdlibHarness
from tools.go_stdlib_platform_contract import (
    GO_STDLIB_CLI_EXECUTION_ENVIRONMENT_IDENTITY_URI,
    GO_STDLIB_EVENT_EXECUTION_ENVIRONMENT_IDENTITY_URI,
    GoStdlibPlatformHarness,
    GoStdlibPlatformTarget,
    go_stdlib_platform_execution_environment_revision,
    go_stdlib_platform_manifest,
)

from tests.ecosystems.test_go_stdlib_inventory import FAST_TIMEOUTS
from tests.ecosystems.test_go_stdlib_mapping import _mapping_request
from tests.ecosystems.test_go_stdlib_verification import (
    _child_pids,
)
from tests.ecosystems.test_go_stdlib_verification import (
    _verification_request as _http_verification_request,
)
from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    ProtocolCode,
)
from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_CAPABILITY,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    ExecutionEnvironment,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    execution_verification_request_to_payload,
    execution_verification_result_from_payload,
    implementation_mapping_request_to_payload,
    implementation_mapping_result_from_payload,
    project_execution_verification,
    validate_execution_verification_request,
    validate_execution_verification_result,
    validate_implementation_mapping_result,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    IgnorePolicy,
    InventoryPageRequest,
    InventoryRequest,
    RepositoryEntryFact,
    collect_inventory_from_process,
)
from ucf.ir import validate_trust_against_behavior
from ucf.ir.models import Check, Digest, IntegerValue, Producer
from ucf.ir.trust_models import Claim, ClaimLevel
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    ONBOARDING_VERSION,
    AcceptedDecision,
    CandidateRef,
    CaptureContext,
    DecisionSet,
    DiscoveryDocumentRef,
    build_onboarding_bundle,
    canonical_onboarding_digest,
    collect_onboarding_evidence,
    derive_decision_id,
)

PLATFORM_SUBJECT_URI = "urn:ucf:repository:go-stdlib-legacy-platforms"
CLI_PROCESS_CAPABILITY = "org.ucf.platform.cli-process"
FILE_SPOOL_EVENT_CAPABILITY = "org.ucf.platform.file-spool-event"
CLI_VERIFICATION_PROCEDURE_URI = "urn:ucf:adapter:go-stdlib-real-cli-verification:1.0.0"
CLI_CHECK_PROCEDURE_URI = "urn:ucf:fixture-check:quote-order-cli-process-contract:1.0.0"
EVENT_VERIFICATION_PROCEDURE_URI = (
    "urn:ucf:adapter:go-stdlib-file-spool-event-verification:1.0.0"
)
EVENT_CHECK_PROCEDURE_URI = (
    "urn:ucf:fixture-check:quote-order-event-enqueue-dispatch-observe:1.0.0"
)
EXPECTED_PLATFORM_PATHS = {
    ".",
    ".gitignore",
    "README.md",
    "cmd",
    "cmd/platform",
    "cmd/platform/main.go",
    "cmd/platform/main_test.go",
    "go.mod",
    "quote",
    "quote/service.go",
    "quote/service_test.go",
    "spool",
    "spool/spool.go",
    "spool/spool_test.go",
}


def test_go_stdlib_platform_inventory_observes_exact_frozen_source(
    tmp_path: Path,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(tmp_path / "platform-target")
    before = go_stdlib_platform_manifest(target.fixture_root)

    async def scenario():
        adapter = AdapterProcess(
            command=target.verification_command(),
            cwd=target.fixture_root,
            requested_capabilities=(
                _required(INVENTORY_CAPABILITY),
                _required(CLI_PROCESS_CAPABILITY),
                _required(FILE_SPOOL_EVENT_CAPABILITY),
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(),
                operation_timeout=10.0,
            )
            return (
                initialized,
                inventory,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    initialized, inventory, stderr_total, stderr_tail = asyncio.run(scenario())

    assert {item.name for item in initialized.capabilities} == {
        INVENTORY_CAPABILITY,
        CLI_PROCESS_CAPABILITY,
        FILE_SPOOL_EVENT_CAPABILITY,
    }
    assert inventory.subject_uri == PLATFORM_SUBJECT_URI
    assert {
        record.path
        for record in inventory.records
        if isinstance(record, RepositoryEntryFact)
    } == EXPECTED_PLATFORM_PATHS
    assert inventory.producer.name == "org.ucf.adapter.go-stdlib"
    assert inventory.producer.version == INVENTORY_VERSION
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_platform_manifest(target.fixture_root) == before


def test_go_stdlib_platform_discovers_and_maps_one_neutral_behavior(
    tmp_path: Path,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(tmp_path / "platform-target")
    before = go_stdlib_platform_manifest(target.fixture_root)
    evidence = asyncio.run(
        collect_onboarding_evidence(
            command=target.verification_command(),
            cwd=target.fixture_root,
            inventory_request=_inventory_request(),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=10.0,
        )
    )

    assert len(evidence.discovery.candidates) == 1
    candidate = evidence.discovery.candidates[0]
    assert candidate.proposal.root.target_id == "use-case.quote-order"
    bundle = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _accepted_platform_decision(evidence.discovery),
    )
    request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=target.verification_command(),
            cwd=target.fixture_root,
            requested_capabilities=(
                _required(INVENTORY_CAPABILITY),
                _required(IMPLEMENTATION_MAPPING_CAPABILITY),
                _required(CLI_PROCESS_CAPABILITY),
                _required(FILE_SPOOL_EVENT_CAPABILITY),
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(),
                operation_timeout=10.0,
            )
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
            return result, adapter.stderr_total_bytes, adapter.stderr_tail
        finally:
            await adapter.close()

    mapping, stderr_total, stderr_tail = asyncio.run(scenario())

    assert mapping.bindings[0].behavior.target_id == "use-case.quote-order"
    assert len(mapping.bindings[0].source_records) == 10
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_platform_manifest(target.fixture_root) == before


def test_go_stdlib_platform_executes_real_cli_verification(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(tmp_path / "platform-target")
    before = go_stdlib_platform_manifest(target.fixture_root)
    (
        bundle,
        initialized,
        inventory,
        mapping,
        request,
        result,
        failed,
        stderr_total,
        stderr_tail,
    ) = _run_platform_verification(
        target=target,
        go_stdlib_harness=go_stdlib_harness,
        go_stdlib_platform_harness=go_stdlib_platform_harness,
        adapter_procedure_uri=CLI_VERIFICATION_PROCEDURE_URI,
        environment_uri=(GO_STDLIB_CLI_EXECUTION_ENVIRONMENT_IDENTITY_URI),
        boundary="cli-process",
        check_id="check.quote-order.real-cli",
        check_procedure_uri=CLI_CHECK_PROCEDURE_URI,
    )

    assert inventory == bundle.inventory
    assert mapping.request == _mapping_request(bundle)
    assert result.request == request
    assert result.producer == initialized.adapter
    assert result.procedure_uri == CLI_VERIFICATION_PROCEDURE_URI
    assert result.status == "completed"
    assert result.outcome == "passed"
    _assert_tested_projection(
        result=result,
        request=request,
        mapping=mapping,
        bundle=bundle,
        inventory=inventory,
        initialized=initialized,
    )
    _assert_failed_not_projectable(
        result=failed,
        request=failed.request,
        mapping=mapping,
        bundle=bundle,
        inventory=inventory,
        initialized=initialized,
    )
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_platform_manifest(target.fixture_root) == before


def test_go_stdlib_platform_executes_temporally_decoupled_event_verification(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(tmp_path / "platform-target")
    before = go_stdlib_platform_manifest(target.fixture_root)
    (
        bundle,
        initialized,
        inventory,
        mapping,
        request,
        result,
        failed,
        stderr_total,
        stderr_tail,
    ) = _run_platform_verification(
        target=target,
        go_stdlib_harness=go_stdlib_harness,
        go_stdlib_platform_harness=go_stdlib_platform_harness,
        adapter_procedure_uri=EVENT_VERIFICATION_PROCEDURE_URI,
        environment_uri=(GO_STDLIB_EVENT_EXECUTION_ENVIRONMENT_IDENTITY_URI),
        boundary="file-spool-event",
        check_id="check.quote-order.file-spool-event",
        check_procedure_uri=EVENT_CHECK_PROCEDURE_URI,
    )

    assert inventory == bundle.inventory
    assert mapping.request == _mapping_request(bundle)
    assert result.request == request
    assert result.producer == initialized.adapter
    assert result.procedure_uri == EVENT_VERIFICATION_PROCEDURE_URI
    assert result.status == "completed"
    assert result.outcome == "passed"
    _assert_tested_projection(
        result=result,
        request=request,
        mapping=mapping,
        bundle=bundle,
        inventory=inventory,
        initialized=initialized,
    )
    _assert_failed_not_projectable(
        result=failed,
        request=failed.request,
        mapping=mapping,
        bundle=bundle,
        inventory=inventory,
        initialized=initialized,
    )
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_platform_manifest(target.fixture_root) == before


def test_go_stdlib_platform_rejects_capability_procedure_cross_product_before_spawn(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(
        tmp_path / "platform-negative-target"
    )
    before = go_stdlib_platform_manifest(target.fixture_root)
    evidence = asyncio.run(
        collect_onboarding_evidence(
            command=target.verification_command(),
            cwd=target.fixture_root,
            inventory_request=_inventory_request(),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=10.0,
        )
    )
    bundle = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _accepted_platform_decision(evidence.discovery),
    )
    mapping_request = _mapping_request(bundle)

    profiles = (
        (
            CLI_PROCESS_CAPABILITY,
            EVENT_VERIFICATION_PROCEDURE_URI,
            GO_STDLIB_EVENT_EXECUTION_ENVIRONMENT_IDENTITY_URI,
            "file-spool-event",
            "check.quote-order.file-spool-event",
            EVENT_CHECK_PROCEDURE_URI,
            ProtocolCode.CAPABILITY_NOT_NEGOTIATED,
        ),
        (
            FILE_SPOOL_EVENT_CAPABILITY,
            CLI_VERIFICATION_PROCEDURE_URI,
            GO_STDLIB_CLI_EXECUTION_ENVIRONMENT_IDENTITY_URI,
            "cli-process",
            "check.quote-order.real-cli",
            CLI_CHECK_PROCEDURE_URI,
            ProtocolCode.CAPABILITY_NOT_NEGOTIATED,
        ),
    )

    async def scenario():
        failures: list[AdapterProtocolError] = []
        for (
            selected_platform_capability,
            procedure_uri,
            environment_uri,
            boundary,
            check_id,
            check_procedure_uri,
            expected_code,
        ) in profiles:
            adapter = AdapterProcess(
                command=target.verification_command(),
                cwd=target.fixture_root,
                requested_capabilities=(
                    _required(INVENTORY_CAPABILITY),
                    _required(IMPLEMENTATION_MAPPING_CAPABILITY),
                    _required(EXECUTION_VERIFICATION_CAPABILITY),
                    _required(selected_platform_capability),
                ),
                timeouts=FAST_TIMEOUTS,
            )
            try:
                initialized = await adapter.start()
                inventory = await collect_inventory_from_process(
                    adapter,
                    request=_inventory_request(),
                    operation_timeout=10.0,
                )
                mapping = implementation_mapping_result_from_payload(
                    await adapter.call(
                        Method.MAP,
                        implementation_mapping_request_to_payload(mapping_request),
                        timeout=10.0,
                    )
                )
                request = _platform_verification_request(
                    mapping=mapping,
                    go_stdlib_harness=go_stdlib_harness,
                    go_stdlib_platform_harness=(go_stdlib_platform_harness),
                    adapter_procedure_uri=procedure_uri,
                    environment_uri=environment_uri,
                    boundary=boundary,
                    check_id=check_id,
                    check_procedure_uri=check_procedure_uri,
                )
                process_id = adapter.pid
                assert process_id is not None
                assert _child_pids(process_id) == set()
                with pytest.raises(AdapterProtocolError) as rejected:
                    await adapter.call(
                        Method.VERIFY,
                        execution_verification_request_to_payload(request),
                        timeout=10.0,
                    )
                assert rejected.value.code is expected_code
                assert _child_pids(process_id) == set()
                failures.append(rejected.value)
                assert inventory == bundle.inventory
                assert mapping.request == mapping_request
                assert initialized.adapter.name == ("org.ucf.adapter.go-stdlib")
            finally:
                await adapter.close()
        return failures

    failures = asyncio.run(scenario())
    assert len(failures) == 2
    assert all(
        failure.category is ErrorCategory.PROTOCOL_FAILURE for failure in failures
    )
    assert go_stdlib_platform_manifest(target.fixture_root) == before


def test_go_stdlib_platform_rejects_source_drift_before_spawn_and_recovers(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
) -> None:
    target = go_stdlib_platform_harness.new_target(tmp_path / "platform-drift-target")
    before = go_stdlib_platform_manifest(target.fixture_root)
    evidence = asyncio.run(
        collect_onboarding_evidence(
            command=target.verification_command(),
            cwd=target.fixture_root,
            inventory_request=_inventory_request(),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=10.0,
        )
    )
    bundle = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _accepted_platform_decision(evidence.discovery),
    )
    mapping_request = _mapping_request(bundle)
    changed_path = target.fixture_root / "README.md"
    original = changed_path.read_bytes()

    async def scenario():
        adapter = AdapterProcess(
            command=target.verification_command(),
            cwd=target.fixture_root,
            requested_capabilities=(
                _required(INVENTORY_CAPABILITY),
                _required(IMPLEMENTATION_MAPPING_CAPABILITY),
                _required(EXECUTION_VERIFICATION_CAPABILITY),
                _required(CLI_PROCESS_CAPABILITY),
                _required(FILE_SPOOL_EVENT_CAPABILITY),
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            await adapter.start()
            await collect_inventory_from_process(
                adapter,
                request=_inventory_request(),
                operation_timeout=10.0,
            )
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(mapping_request),
                    timeout=10.0,
                )
            )
            request = _platform_verification_request(
                mapping=mapping,
                go_stdlib_harness=go_stdlib_harness,
                go_stdlib_platform_harness=go_stdlib_platform_harness,
                adapter_procedure_uri=EVENT_VERIFICATION_PROCEDURE_URI,
                environment_uri=(GO_STDLIB_EVENT_EXECUTION_ENVIRONMENT_IDENTITY_URI),
                boundary="file-spool-event",
                check_id="check.quote-order.file-spool-event",
                check_procedure_uri=EVENT_CHECK_PROCEDURE_URI,
            )
            process_id = adapter.pid
            assert process_id is not None
            changed_path.write_bytes(original + b"\n")
            with pytest.raises(AdapterProtocolError) as rejected:
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            assert rejected.value.category is ErrorCategory.ADAPTER_FAILURE
            assert rejected.value.code is ProtocolCode.OPERATION_FAILED
            assert _child_pids(process_id) == set()

            changed_path.write_bytes(original)
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(),
                operation_timeout=10.0,
            )
            restored_mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(mapping_request),
                    timeout=10.0,
                )
            )
            restored_request = _platform_verification_request(
                mapping=restored_mapping,
                go_stdlib_harness=go_stdlib_harness,
                go_stdlib_platform_harness=go_stdlib_platform_harness,
                adapter_procedure_uri=EVENT_VERIFICATION_PROCEDURE_URI,
                environment_uri=(GO_STDLIB_EVENT_EXECUTION_ENVIRONMENT_IDENTITY_URI),
                boundary="file-spool-event",
                check_id="check.quote-order.file-spool-event",
                check_procedure_uri=EVENT_CHECK_PROCEDURE_URI,
            )
            restored = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(restored_request),
                    timeout=10.0,
                )
            )
            return inventory, restored
        finally:
            changed_path.write_bytes(original)
            await adapter.close()

    inventory, restored = asyncio.run(scenario())
    assert inventory == bundle.inventory
    assert restored.outcome == "passed"
    assert go_stdlib_platform_manifest(target.fixture_root) == before


def _inventory_request() -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri=PLATFORM_SUBJECT_URI,
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version=INVENTORY_VERSION,
            rules=(),
        ),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=256,
            cursor=None,
        ),
    )


def _run_platform_verification(
    *,
    target: GoStdlibPlatformTarget,
    go_stdlib_harness: GoStdlibHarness,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
    adapter_procedure_uri: str,
    environment_uri: str,
    boundary: str,
    check_id: str,
    check_procedure_uri: str,
):
    evidence = asyncio.run(
        collect_onboarding_evidence(
            command=target.verification_command(),
            cwd=target.fixture_root,
            inventory_request=_inventory_request(),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=10.0,
        )
    )
    bundle = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _accepted_platform_decision(evidence.discovery),
    )
    mapping_request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=target.verification_command(),
            cwd=target.fixture_root,
            requested_capabilities=(
                _required(INVENTORY_CAPABILITY),
                _required(IMPLEMENTATION_MAPPING_CAPABILITY),
                _required(EXECUTION_VERIFICATION_CAPABILITY),
                _required(CLI_PROCESS_CAPABILITY),
                _required(FILE_SPOOL_EVENT_CAPABILITY),
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(),
                operation_timeout=10.0,
            )
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(mapping_request),
                    timeout=10.0,
                )
            )
            validate_implementation_mapping_result(
                mapping,
                request=mapping_request,
                bundle=bundle,
                current_inventory=inventory,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            request = _platform_verification_request(
                mapping=mapping,
                go_stdlib_harness=go_stdlib_harness,
                go_stdlib_platform_harness=(go_stdlib_platform_harness),
                adapter_procedure_uri=adapter_procedure_uri,
                environment_uri=environment_uri,
                boundary=boundary,
                check_id=check_id,
                check_procedure_uri=check_procedure_uri,
            )
            validate_execution_verification_request(
                request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            result = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            )
            validate_execution_verification_result(
                result,
                request=request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            failed_request = request.model_copy(
                update={
                    "expected_outputs": (
                        request.expected_outputs[0].model_copy(
                            update={
                                "value": IntegerValue(
                                    kind="integer",
                                    value=2501,
                                )
                            }
                        ),
                    )
                }
            )
            failed = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(failed_request),
                    timeout=10.0,
                )
            )
            validate_execution_verification_result(
                failed,
                request=failed_request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            return (
                bundle,
                initialized,
                inventory,
                mapping,
                request,
                result,
                failed,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    return asyncio.run(scenario())


def _platform_verification_request(
    *,
    mapping,
    go_stdlib_harness: GoStdlibHarness,
    go_stdlib_platform_harness: GoStdlibPlatformHarness,
    adapter_procedure_uri: str,
    environment_uri: str,
    boundary: str,
    check_id: str,
    check_procedure_uri: str,
):
    return _http_verification_request(
        mapping,
        harness=go_stdlib_harness,
    ).model_copy(
        update={
            "adapter_procedure_uri": adapter_procedure_uri,
            "environment": ExecutionEnvironment(
                kind="execution_environment",
                identity_uri=environment_uri,
                revision=Digest(
                    kind="digest",
                    algorithm="sha-256",
                    value=(
                        go_stdlib_platform_execution_environment_revision(
                            go_stdlib_harness.build_receipt,
                            go_stdlib_platform_harness.build_receipt,
                            source_revision=(
                                mapping.request.inventory.source_revision.value
                            ),
                            boundary=boundary,
                        )
                    ),
                ),
            ),
            "check": Check(
                kind="check",
                id=check_id,
                version="1.0.0",
                procedure_uri=check_procedure_uri,
            ),
        }
    )


def _assert_tested_projection(
    *,
    result,
    request,
    mapping,
    bundle,
    inventory,
    initialized,
) -> None:
    projection = project_execution_verification(
        result,
        request=request,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=inventory,
        mapping_initialized_adapter=initialized.adapter,
        initialized_adapter=initialized.adapter,
        negotiated_capabilities={
            capability.name: capability.version
            for capability in initialized.capabilities
        },
    )
    claims = [
        record
        for record in projection.tested_trust.records
        if isinstance(record, Claim)
    ]
    assert len(claims) == 1
    assert claims[0].level is ClaimLevel.TESTED
    assert all(claim.level is not ClaimLevel.VERIFIED for claim in claims)
    assert (
        validate_trust_against_behavior(
            projection.tested_trust,
            projection.successor_behavior,
        )
        is None
    )


def _assert_failed_not_projectable(
    *,
    result,
    request,
    mapping,
    bundle,
    inventory,
    initialized,
) -> None:
    assert result.status == "completed"
    assert result.outcome == "failed"
    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        project_execution_verification(
            result,
            request=request,
            mapping_result=mapping,
            bundle=bundle,
            current_inventory=inventory,
            mapping_initialized_adapter=initialized.adapter,
            initialized_adapter=initialized.adapter,
            negotiated_capabilities={
                capability.name: capability.version
                for capability in initialized.capabilities
            },
        )
    assert captured.value.code is (ImplementationEvidenceErrorCode.EVIDENCE_NOT_PASSED)


def _required(name: str) -> CapabilityRequest:
    return CapabilityRequest(
        kind="capability_request",
        name=name,
        minimum_version="1.0.0",
        required=True,
    )


def _accepted_platform_decision(discovery) -> DecisionSet:
    base = DecisionSet(
        kind="decision_set_profile",
        onboarding_version=ONBOARDING_VERSION,
        schema_uri=DECISION_SET_SCHEMA_URI,
        discovery=DiscoveryDocumentRef(
            kind="discovery_document_ref",
            schema_uri=discovery.schema_uri,
            schema_version=discovery.onboarding_version,
            canonical_digest=canonical_onboarding_digest(discovery),
        ),
        inventory_binding=discovery.inventory_binding,
        reviewer=Producer(
            kind="producer",
            name="org.ucf.ecosystem-reviewer",
            version="1.0.0",
        ),
        capture_context=CaptureContext(
            kind="capture_context",
            captured_at="2026-07-19T12:00:00Z",
            environment=Digest(
                kind="digest",
                algorithm="sha-256",
                value=hashlib.sha256(
                    b"ucf-eco003-go-platform-review-policy:1.0.0\n"
                ).hexdigest(),
            ),
        ),
        decisions=(),
    )
    candidate = discovery.candidates[0]
    decision = AcceptedDecision(
        kind="accepted_decision",
        id=f"decision.{'0' * 64}",
        candidate=CandidateRef(
            kind="candidate_ref",
            discovery_digest=canonical_onboarding_digest(discovery),
            candidate_id=candidate.id,
            semantic_digest=candidate.semantic_digest,
        ),
        reason=(
            "Native process evidence matches the reviewed quote-order "
            "CLI and file-spool event scope."
        ),
    )
    return base.model_copy(
        update={
            "decisions": (
                decision.model_copy(update={"id": derive_decision_id(decision, base)}),
            )
        }
    )
