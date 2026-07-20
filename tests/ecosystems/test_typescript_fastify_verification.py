from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tools.typescript_fastify_adapter_contract import (
    TypeScriptFastifyHarness,
    TypeScriptFastifyTarget,
    typescript_fastify_fixture_manifest,
)

from tests.ecosystems.test_typescript_fastify_inventory import (
    FAST_TIMEOUTS,
    _request,
)
from tests.ecosystems.test_typescript_fastify_mapping import (
    _mapping_request,
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
    canonical_execution_environment_digest,
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
from ucf.ir import (
    canonical_ir_json,
    canonical_trust_ir_json,
    validate_trust_against_behavior,
)
from ucf.ir.models import (
    Check,
    Digest,
    EntityKind,
    EntityRef,
    IntegerValue,
    PortRef,
    Producer,
    Provenance,
    VerificationEvidence,
)
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    Claim,
    ClaimLevel,
    TrustRecordKind,
)
from ucf.onboarding import canonical_onboarding_json

VERIFICATION_PROCEDURE_URI = (
    "urn:ucf:adapter:"
    "typescript-fastify-real-http-verification:1.0.0"
)
ENVIRONMENT_IDENTITY_URI = (
    "urn:ucf:fixture-environment:node22-linux-loopback:1.0.0"
)
ENVIRONMENT_REVISION = (
    "5c1cb86c391a5942088462fa2fe4e8a4deec768f6b37fd69027e37729555ce02"
)
ENVIRONMENT_DIGEST = (
    "0d7174c8c09882285d8942bb93fe9c6623dc39affc1ce797a473b5a88f94f927"
)
_HANGING_SERVICE_MODULE = """\
import { createServer } from "node:http";

let server;

export function buildApp() {
  return {
    async listen({ host, port }) {
      server = createServer(() => {});
      await new Promise((resolve, reject) => {
        server.once("error", reject);
        server.listen(port, host, resolve);
      });
      const address = server.address();
      return `http://127.0.0.1:${address.port}`;
    },
    async close() {
      if (server?.listening) {
        await new Promise((resolve, reject) => {
          server.close((error) => error ? reject(error) : resolve());
        });
      }
    },
  };
}
"""


def test_typescript_fastify_real_http_verification_projects_tested_evidence(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "verification-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest
    assert len(before) == 7
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "discovery.stderr",
    )
    bundle_before = canonical_onboarding_json(bundle)

    run = _verify(target=target, bundle=bundle)

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
    assert set(run.passed.model_dump(mode="json")) == {
        "kind",
        "implementation_evidence_version",
        "schema_uri",
        "id",
        "status",
        "request",
        "outcome",
        "executed_at",
        "producer",
        "capability",
        "procedure_uri",
    }

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
    repeated = project_execution_verification(
        run.passed,
        request=run.request,
        mapping_result=run.mapping,
        bundle=bundle,
        current_inventory=run.inventory,
        mapping_initialized_adapter=run.initialized_adapter,
        initialized_adapter=run.initialized_adapter,
        negotiated_capabilities=run.negotiated_capabilities,
    )
    assert canonical_ir_json(projection.successor_behavior) == (
        canonical_ir_json(repeated.successor_behavior)
    )
    assert canonical_trust_ir_json(projection.tested_trust) == (
        canonical_trust_ir_json(repeated.tested_trust)
    )
    _assert_projection(projection, run.passed, bundle)

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

    assert canonical_onboarding_json(bundle) == bundle_before
    assert (tmp_path / "discovery.stderr").read_bytes() == b""
    assert typescript_fastify_fixture_manifest(target.fixture_root) == before


def test_typescript_fastify_verification_cancels_worker_before_ack_and_reuses_session(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "cancellation-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest
    assert len(before) == 7
    bundle = _reviewed_bundle(
        target=target,
        stderr_path=tmp_path / "cancellation-discovery.stderr",
    )

    run = _cancel_verification(target=target, bundle=bundle)

    assert run.active_tasks > run.baseline_tasks
    assert run.reaped_tasks == run.baseline_tasks
    assert run.refreshed_inventory == bundle.inventory
    assert run.stderr_bytes == 0
    assert run.stderr_tail == b""
    assert (tmp_path / "cancellation-discovery.stderr").read_bytes() == b""
    assert typescript_fastify_fixture_manifest(target.fixture_root) == before


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


@dataclass(frozen=True)
class _CancellationRun:
    baseline_tasks: int
    active_tasks: int
    reaped_tasks: int
    refreshed_inventory: object
    stderr_bytes: int
    stderr_tail: bytes


def _verify(
    *,
    target: TypeScriptFastifyTarget,
    bundle,
) -> _VerificationRun:
    repository = target.fixture_root

    async def scenario() -> _VerificationRun:
        adapter = AdapterProcess(
            command=target.command(),
            cwd=repository,
            requested_capabilities=(
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
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            assert inventory == bundle.inventory
            mapping_request = _mapping_request(bundle)
            mapping_payload = await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(
                    mapping_request
                ),
                timeout=10.0,
            )
            mapping = implementation_mapping_result_from_payload(
                mapping_payload
            )
            validate_implementation_mapping_result(
                mapping,
                request=mapping_request,
                bundle=bundle,
                current_inventory=inventory,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )

            await asyncio.to_thread(_build_fixture, repository)
            request = _verification_request(mapping)
            validate_execution_verification_request(
                request,
                mapping_result=mapping,
                bundle=bundle,
                current_inventory=inventory,
                mapping_initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            started_at = datetime.now(UTC).replace(microsecond=0)
            passed_payload = await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
                timeout=10.0,
            )
            ended_at = datetime.now(UTC).replace(microsecond=0)
            passed = execution_verification_result_from_payload(
                passed_payload
            )
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
            failed_payload = await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(
                    failed_request
                ),
                timeout=10.0,
            )
            failed = execution_verification_result_from_payload(
                failed_payload
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


def _cancel_verification(
    *,
    target: TypeScriptFastifyTarget,
    bundle,
) -> _CancellationRun:
    repository = target.fixture_root

    async def scenario() -> _CancellationRun:
        adapter = AdapterProcess(
            command=target.command(),
            cwd=repository,
            requested_capabilities=(
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
            ),
            timeouts=FAST_TIMEOUTS,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            assert inventory == bundle.inventory
            mapping_request = _mapping_request(bundle)
            mapping_payload = await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(
                    mapping_request
                ),
                timeout=10.0,
            )
            mapping = implementation_mapping_result_from_payload(
                mapping_payload
            )
            validate_implementation_mapping_result(
                mapping,
                request=mapping_request,
                bundle=bundle,
                current_inventory=inventory,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities=adapter.negotiated_capabilities,
            )
            distribution = repository / "dist"
            distribution.mkdir()
            (distribution / "service.js").write_text(
                _HANGING_SERVICE_MODULE,
                encoding="utf-8",
            )
            request = _verification_request(mapping)
            process_id = adapter.pid
            assert process_id is not None
            baseline_tasks = _task_count(process_id)
            call = await adapter.begin(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
            )
            active_tasks = await _wait_for_task_count(
                process_id,
                minimum=baseline_tasks + 1,
            )
            with pytest.raises(AdapterProtocolError) as captured:
                await call.cancel()
            assert captured.value.category is ErrorCategory.CANCELLED
            assert captured.value.code is ProtocolCode.REQUEST_CANCELLED
            assert captured.value.request_id == call.request_id
            reaped_tasks = await _wait_for_task_count(
                process_id,
                exact=baseline_tasks,
            )

            shutil.rmtree(distribution)
            refreshed = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            with pytest.raises(AdapterProtocolError) as stale:
                await adapter.call(
                    Method.VERIFY,
                    execution_verification_request_to_payload(request),
                    timeout=10.0,
                )
            assert stale.value.category is ErrorCategory.ADAPTER_FAILURE
            assert stale.value.code is ProtocolCode.OPERATION_FAILED
        finally:
            await adapter.close()
        return _CancellationRun(
            baseline_tasks=baseline_tasks,
            active_tasks=active_tasks,
            reaped_tasks=reaped_tasks,
            refreshed_inventory=refreshed,
            stderr_bytes=adapter.stderr_total_bytes,
            stderr_tail=adapter.stderr_tail,
        )

    return asyncio.run(scenario())


def _task_count(process_id: int) -> int:
    return sum(1 for _ in Path(f"/proc/{process_id}/task").iterdir())


async def _wait_for_task_count(
    process_id: int,
    *,
    minimum: int | None = None,
    exact: int | None = None,
) -> int:
    deadline = asyncio.get_running_loop().time() + 2.0
    while True:
        count = _task_count(process_id)
        if (
            (minimum is not None and count >= minimum)
            or (exact is not None and count == exact)
        ):
            return count
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail(
                "verification Worker task count did not reach "
                f"minimum={minimum!r}, exact={exact!r}; observed={count}"
            )
        await asyncio.sleep(0.01)


def _verification_request(mapping) -> ExecutionVerificationRequest:
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
            identity_uri=ENVIRONMENT_IDENTITY_URI,
            revision=Digest(
                kind="digest",
                algorithm="sha-256",
                value=ENVIRONMENT_REVISION,
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


def _build_fixture(repository: Path) -> None:
    subprocess.run(
        (
            "npm",
            "ci",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
        ),
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ("npm", "run", "build"),
        cwd=repository,
        check=True,
    )


def _assert_projection(projection, result, bundle) -> None:
    original = {
        (entity.kind, entity.id): entity
        for entity in bundle.behavior.entities
    }
    successor = {
        (entity.kind, entity.id): entity
        for entity in projection.successor_behavior.entities
    }
    assert all(successor[key] == entity for key, entity in original.items())
    added = [
        entity
        for key, entity in successor.items()
        if key not in original
    ]
    assert len(added) == 2
    provenance = next(
        entity for entity in added if isinstance(entity, Provenance)
    )
    evidence = next(
        entity
        for entity in added
        if isinstance(entity, VerificationEvidence)
    )
    result_digest = canonical_implementation_evidence_digest(result)
    assert provenance.id == f"provenance.execution.{result_digest.value}"
    assert provenance.source.uri == result.request.source.subject_uri
    assert provenance.source.revision == result.request.source.source_revision
    assert provenance.producer == result.producer
    assert provenance.captured_at == result.executed_at
    assert evidence.id == f"evidence.execution.{result_digest.value}"
    assert evidence.subjects == (
        EntityRef(
            kind="entity_ref",
            target_kind=EntityKind.USE_CASE,
            target_id="use-case.quote-order",
        ),
    )
    assert evidence.check == result.request.check
    assert evidence.outcome == "passed"
    assert evidence.source_revision == result.request.source.source_revision
    assert evidence.environment.value == ENVIRONMENT_DIGEST
    assert evidence.provenance.target_id == provenance.id

    records = projection.tested_trust.records
    assert len(records) == 2
    assert all(
        record.kind is not TrustRecordKind.MAPPING for record in records
    )
    claims = [record for record in records if isinstance(record, Claim)]
    assert len(claims) == 1
    assert claims[0].level is ClaimLevel.TESTED
    assert all(
        claim.level not in {ClaimLevel.MAPPED, ClaimLevel.VERIFIED}
        for claim in claims
    )
    assert validate_trust_against_behavior(
        projection.tested_trust,
        projection.successor_behavior,
    ) is None
    assert canonical_execution_environment_digest(
        result.request.environment
    ).value == ENVIRONMENT_DIGEST
