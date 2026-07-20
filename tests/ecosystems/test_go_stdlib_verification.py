from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GO_STDLIB_EXECUTION_ENVIRONMENT_IDENTITY_URI,
    GoStdlibHarness,
    GoStdlibTarget,
    go_stdlib_execution_environment_revision,
    go_stdlib_fixture_manifest,
)

from tests.ecosystems.test_go_stdlib_inventory import (
    FAST_TIMEOUTS,
    SOURCE_REVISION,
    _request,
)
from tests.ecosystems.test_go_stdlib_mapping import (
    _map,
    _mapping_request,
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
    EXECUTION_VERIFICATION_CAPABILITY,
    EXECUTION_VERIFICATION_PROCEDURE_URI,
    EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_CAPABILITY,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
    ExecutionEnvironment,
    ExecutionPortValue,
    ExecutionVerificationRequest,
    ImplementationEvidenceErrorCode,
    ImplementationEvidenceValidationError,
    ImplementationMappingResultRef,
    ImplementationSource,
    canonical_implementation_evidence_digest,
    derive_execution_verification_result_id,
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
    collect_inventory_from_process,
)
from ucf.ir import validate_trust_against_behavior
from ucf.ir.models import (
    Check,
    Digest,
    EntityRef,
    IntegerValue,
    NullValue,
    PortRef,
    Producer,
    RecordEntry,
    RecordValue,
)
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    Claim,
    ClaimLevel,
    TrustRecordKind,
)

VERIFICATION_PROCEDURE_URI = (
    "urn:ucf:adapter:go-stdlib-real-http-verification:1.0.0"
)
HTTP_LOOPBACK_CAPABILITY = "org.ucf.platform.http-loopback"


def test_go_stdlib_real_http_verification_projects_only_tested_evidence(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "verification-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )

    run = _verify(
        target=target,
        harness=go_stdlib_harness,
        bundle=bundle,
    )

    assert run.stderr_bytes == 0
    assert run.stderr_tail == b""
    assert run.inventory == bundle.inventory
    assert run.passed.request == run.request
    assert run.passed.producer == run.initialized_adapter
    assert run.passed.procedure_uri == VERIFICATION_PROCEDURE_URI
    assert run.passed.status == "completed"
    assert run.passed.outcome == "passed"
    assert run.passed.id == derive_execution_verification_result_id(
        run.passed
    )
    executed_at = datetime.fromisoformat(
        run.passed.executed_at.replace("Z", "+00:00")
    )
    assert run.started_at <= executed_at <= run.ended_at
    assert executed_at.microsecond == 0

    projection = project_execution_verification(
        run.passed,
        request=run.request,
        mapping_result=run.mapping,
        bundle=bundle,
        current_inventory=run.inventory,
        mapping_initialized_adapter=run.initialized_adapter,
        initialized_adapter=run.initialized_adapter,
        negotiated_capabilities=run.negotiated_capabilities,
    )
    claims = [
        record
        for record in projection.tested_trust.records
        if isinstance(record, Claim)
    ]
    assert len(claims) == 1
    assert claims[0].level is ClaimLevel.TESTED
    assert all(
        record.kind is not TrustRecordKind.MAPPING
        for record in projection.tested_trust.records
    )
    assert all(claim.level is not ClaimLevel.VERIFIED for claim in claims)
    assert validate_trust_against_behavior(
        projection.tested_trust,
        projection.successor_behavior,
    ) is None

    assert run.failed.outcome == "failed"
    with pytest.raises(
        ImplementationEvidenceValidationError
    ) as captured:
        project_execution_verification(
            run.failed,
            request=run.failed.request,
            mapping_result=run.mapping,
            bundle=bundle,
            current_inventory=run.inventory,
            mapping_initialized_adapter=run.initialized_adapter,
            initialized_adapter=run.initialized_adapter,
            negotiated_capabilities=run.negotiated_capabilities,
        )
    assert captured.value.code is (
        ImplementationEvidenceErrorCode.EVIDENCE_NOT_PASSED
    )
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_verification_cleans_child_before_cancellation_ack_and_recovers(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "cancellation-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )

    async def scenario():
        adapter = _verification_adapter(target)
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            mapping_request = _mapping_request(bundle)
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(
                        mapping_request
                    ),
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
            request = _verification_request(
                mapping,
                harness=go_stdlib_harness,
            )
            process_id = adapter.pid
            assert process_id is not None
            assert _child_pids(process_id) == set()

            call = await adapter.begin(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
            )
            with pytest.raises(AdapterProtocolError) as cancelled:
                await call.cancel()
            assert cancelled.value.request_id == call.request_id
            assert cancelled.value.category is ErrorCategory.CANCELLED
            assert cancelled.value.code is ProtocolCode.REQUEST_CANCELLED
            assert _child_pids(process_id) == set()

            recovered = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            )
            validate_execution_verification_result(
                recovered,
                request=request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            return (
                recovered,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    recovered, stderr_bytes, stderr_tail = asyncio.run(scenario())

    assert recovered.outcome == "passed"
    assert stderr_bytes == 0
    assert stderr_tail == b""
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_http_verification_requires_platform_capability_before_spawn(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "capability-target")
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )

    async def scenario():
        adapter = _verification_adapter(
            target,
            include_http_loopback=False,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            mapping_request = _mapping_request(bundle)
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(
                        mapping_request
                    ),
                    timeout=10.0,
                )
            )
            request = _verification_request(
                mapping,
                harness=go_stdlib_harness,
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
            assert rejected.value.category is ErrorCategory.PROTOCOL_FAILURE
            assert rejected.value.code is (
                ProtocolCode.CAPABILITY_NOT_NEGOTIATED
            )
            assert _child_pids(process_id) == set()

            reused = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(
                        mapping_request
                    ),
                    timeout=10.0,
                )
            )
            assert reused == mapping
            assert _child_pids(process_id) == set()
            return (
                initialized,
                inventory,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    initialized, inventory, stderr_bytes, stderr_tail = asyncio.run(scenario())

    assert initialized.adapter is not None
    assert inventory == bundle.inventory
    assert stderr_bytes == 0
    assert stderr_tail == b""
    assert (tmp_path / "discovery.stderr").read_bytes() == b""


def test_go_stdlib_verification_rejects_unbound_and_changed_execution_context(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    original_target = go_stdlib_harness.new_target(
        tmp_path / "negative-target"
    )
    fixture_entry = tmp_path / "legacy-quote-server"
    shutil.copy2(original_target.fixture_entry, fixture_entry)
    target = replace(original_target, fixture_entry=fixture_entry)
    before = go_stdlib_fixture_manifest(target.fixture_root)
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )
    mapping_request = _mapping_request(bundle)
    external_mapping = _map(
        target=target,
        request=mapping_request,
        bundle=bundle,
        record_limit=7,
    ).result
    request = _verification_request(
        external_mapping,
        harness=go_stdlib_harness,
    )
    executable_before = fixture_entry.read_bytes()

    async def scenario():
        adapter = _verification_adapter(target)
        failures: list[AdapterProtocolError] = []
        try:
            initialized = await adapter.start()
            process_id = adapter.pid
            assert process_id is not None
            with pytest.raises(AdapterProtocolError) as before_inventory:
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(before_inventory.value)

            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            with pytest.raises(AdapterProtocolError) as before_mapping:
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(before_mapping.value)

            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(
                        mapping_request
                    ),
                    timeout=10.0,
                )
            )
            assert mapping == external_mapping
            for malformed in _unbound_verification_payloads(request):
                with pytest.raises(AdapterProtocolError) as rejected:
                    await adapter.call(
                        Method.VERIFY,
                        malformed,
                        timeout=10.0,
                    )
                failures.append(rejected.value)

            recovered = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            )
            validate_execution_verification_result(
                recovered,
                request=request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            assert _child_pids(process_id) == set()

            _replace_executable(
                fixture_entry,
                executable_before + b"\x00",
            )
            with pytest.raises(AdapterProtocolError) as changed_artifact:
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            failures.append(changed_artifact.value)
            _replace_executable(fixture_entry, executable_before)

            restored = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            )
            assert _child_pids(process_id) == set()
            return (
                failures,
                recovered,
                restored,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            try:
                _replace_executable(fixture_entry, executable_before)
            finally:
                await adapter.close()

    failures, recovered, restored, stderr_bytes, stderr_tail = asyncio.run(
        scenario()
    )

    assert [failure.code for failure in failures[:2]] == [
        ProtocolCode.OPERATION_FAILED,
        ProtocolCode.OPERATION_FAILED,
    ]
    assert len(failures[2:-1]) == 7
    assert all(
        failure.code is ProtocolCode.INVALID_PARAMS
        and failure.category is ErrorCategory.PROTOCOL_FAILURE
        for failure in failures[2:]
    )
    assert recovered.outcome == restored.outcome == "passed"
    assert stderr_bytes == 0
    assert stderr_tail == b""
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


@dataclass(frozen=True)
class _VerificationRun:
    request: ExecutionVerificationRequest
    mapping: object
    passed: object
    failed: object
    inventory: object
    initialized_adapter: Producer
    negotiated_capabilities: dict[str, str]
    started_at: datetime
    ended_at: datetime
    stderr_bytes: int
    stderr_tail: bytes


def _verify(
    *,
    target: GoStdlibTarget,
    harness: GoStdlibHarness,
    bundle,
) -> _VerificationRun:
    async def scenario() -> _VerificationRun:
        adapter = _verification_adapter(target)
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            assert inventory == bundle.inventory
            mapping_request = _mapping_request(bundle)
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(
                        mapping_request
                    ),
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
            request = _verification_request(
                mapping,
                harness=harness,
            )
            validate_execution_verification_request(
                request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            started_at = datetime.now(UTC).replace(microsecond=0)
            passed = execution_verification_result_from_payload(
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            )
            ended_at = datetime.now(UTC).replace(microsecond=0)
            validate_execution_verification_result(
                passed,
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
                    execution_verification_request_to_payload(
                        failed_request
                    ),
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
            negotiated = adapter.negotiated_capabilities
        finally:
            await adapter.close()
        return _VerificationRun(
            request=request,
            mapping=mapping,
            passed=passed,
            failed=failed,
            inventory=inventory,
            initialized_adapter=initialized.adapter,
            negotiated_capabilities=negotiated,
            started_at=started_at,
            ended_at=ended_at,
            stderr_bytes=adapter.stderr_total_bytes,
            stderr_tail=adapter.stderr_tail,
        )

    return asyncio.run(scenario())


def _verification_adapter(
    target: GoStdlibTarget,
    *,
    include_http_loopback: bool = True,
) -> AdapterProcess:
    capabilities = [
        CapabilityRequest(
            kind="capability_request",
            name=INVENTORY_CAPABILITY,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        ),
        CapabilityRequest(
            kind="capability_request",
            name=IMPLEMENTATION_MAPPING_CAPABILITY,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        ),
        CapabilityRequest(
            kind="capability_request",
            name=EXECUTION_VERIFICATION_CAPABILITY,
            minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
            required=True,
        ),
    ]
    if include_http_loopback:
        capabilities.append(
            CapabilityRequest(
                kind="capability_request",
                name=HTTP_LOOPBACK_CAPABILITY,
                minimum_version=IMPLEMENTATION_EVIDENCE_VERSION,
                required=True,
            )
        )
    return AdapterProcess(
        command=target.verification_command(),
        cwd=target.fixture_root,
        requested_capabilities=tuple(capabilities),
        timeouts=FAST_TIMEOUTS,
    )


def _child_pids(process_id: int) -> set[int]:
    children: set[int] = set()
    for task in Path(f"/proc/{process_id}/task").iterdir():
        payload = (task / "children").read_text(encoding="ascii").strip()
        children.update(int(value) for value in payload.split())
    return children


def _replace_executable(path: Path, payload: bytes) -> None:
    replacement = path.with_name(f".{path.name}.replacement")
    replacement.write_bytes(payload)
    replacement.chmod(path.stat().st_mode & 0o777)
    os.replace(replacement, path)


def _unbound_verification_payloads(
    request: ExecutionVerificationRequest,
):
    stale_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value="0" * 64,
    )
    wrong_environment = request.model_copy(
        update={
            "environment": request.environment.model_copy(
                update={"revision": stale_digest}
            )
        }
    )
    wrong_mapping = request.model_copy(
        update={
            "mapping": request.mapping.model_copy(
                update={"target_id": f"mapping.{'0' * 64}"}
            )
        }
    )
    wrong_source = request.model_copy(
        update={
            "source": request.source.model_copy(
                update={"source_revision": stale_digest}
            )
        }
    )
    wrong_check = request.model_copy(
        update={
            "check": request.check.model_copy(
                update={"id": "check.quote-order.forged"}
            )
        }
    )
    wrong_input = request.model_copy(
        update={
            "inputs": (
                request.inputs[0].model_copy(
                    update={
                        "value": IntegerValue(kind="integer", value=3)
                    }
                ),
                request.inputs[1],
            )
        }
    )
    exact_payload = execution_verification_request_to_payload(request)
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
        if entry.name != "environment":
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
    noncanonical_environment = exact_payload.model_copy(
        update={
            "value": root.model_copy(
                update={"entries": tuple(nested_entries)}
            )
        }
    )
    return (
        execution_verification_request_to_payload(wrong_environment),
        execution_verification_request_to_payload(wrong_mapping),
        execution_verification_request_to_payload(wrong_source),
        execution_verification_request_to_payload(wrong_check),
        execution_verification_request_to_payload(wrong_input),
        unknown_field,
        noncanonical_environment,
    )


def _verification_request(
    mapping,
    *,
    harness: GoStdlibHarness,
) -> ExecutionVerificationRequest:
    binding = mapping.bindings[0]
    subject = next(
        entity
        for entity in mapping.request.behavior.entities
        if entity.id == binding.behavior.target_id
    )
    owner = EntityRef(
        kind="entity_ref",
        target_kind=binding.behavior.target_kind,
        target_id=binding.behavior.target_id,
    )
    inputs = {"quantity": 2, "unit-price-cents": 1250}
    expected_outputs = {"total-cents": 2500}
    return ExecutionVerificationRequest(
        kind="execution_verification_request",
        implementation_evidence_version=IMPLEMENTATION_EVIDENCE_VERSION,
        schema_uri=EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
        capability=CapabilitySelection(
            kind="capability",
            name=EXECUTION_VERIFICATION_CAPABILITY,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
        ),
        profile_procedure_uri=EXECUTION_VERIFICATION_PROCEDURE_URI,
        adapter_procedure_uri=VERIFICATION_PROCEDURE_URI,
        mapping=ImplementationMappingResultRef(
            kind="implementation_mapping_result_ref",
            schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
            schema_version=IMPLEMENTATION_EVIDENCE_VERSION,
            target_id=mapping.id,
            canonical_digest=canonical_implementation_evidence_digest(
                mapping
            ),
        ),
        base_behavior=BehaviorDocumentRef(
            kind="behavior_document_ref",
            document_id=binding.behavior.document_id,
            ir_version=binding.behavior.ir_version,
            canonical_digest=binding.behavior.canonical_digest,
        ),
        subject=binding.behavior,
        inputs=tuple(
            ExecutionPortValue(
                kind="execution_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=owner,
                    direction="input",
                    name=port.name,
                ),
                value=IntegerValue(
                    kind="integer",
                    value=inputs[port.name],
                ),
            )
            for port in subject.input_ports
        ),
        expected_outputs=tuple(
            ExecutionPortValue(
                kind="execution_port_value",
                port=PortRef(
                    kind="port_ref",
                    owner=owner,
                    direction="output",
                    name=port.name,
                ),
                value=IntegerValue(
                    kind="integer",
                    value=expected_outputs[port.name],
                ),
            )
            for port in subject.output_ports
        ),
        source=ImplementationSource(
            kind="implementation_source",
            subject_uri=mapping.request.inventory.subject_uri,
            source_revision=mapping.request.inventory.source_revision,
            records=binding.source_records,
        ),
        environment=ExecutionEnvironment(
            kind="execution_environment",
            identity_uri=GO_STDLIB_EXECUTION_ENVIRONMENT_IDENTITY_URI,
            revision=Digest(
                kind="digest",
                algorithm="sha-256",
                value=go_stdlib_execution_environment_revision(
                    harness.build_receipt,
                    source_revision=SOURCE_REVISION,
                ),
            ),
        ),
        check=Check(
            kind="check",
            id="check.quote-order.real-http",
            version="1.0.0",
            procedure_uri=(
                "urn:ucf:fixture-check:"
                "quote-order-http-contract:1.0.0"
            ),
        ),
    )
