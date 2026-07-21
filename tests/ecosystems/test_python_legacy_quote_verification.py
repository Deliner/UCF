from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.ecosystems.test_python_legacy_quote_mapping import (
    _mapping_request,
    _mapping_result,
    _reviewed_bundle,
)
from tests.fixtures.adapters.inventory_reference.implementation_evidence import (
    CHECK_ID,
    CHECK_PROCEDURE_URI,
    VERIFICATION_ADAPTER_PROCEDURE_URI,
    ProfileError,
    build_verification_result_payload,
    decode_verification_plan,
    encode_adapter_payload,
)
from tests.fixtures.adapters.inventory_reference.native_verification import (
    DEFAULT_LIMITS,
    NativeVerificationCancelled,
    NativeVerificationError,
    NativeVerificationLimits,
    build_execution_environment,
    run_native_verification,
)
from tests.inventory.reference_adapter_harness import (
    nonfollowing_tree_manifest,
)
from tests.onboarding.test_decisions import _decisions
from tests.onboarding.test_process_client import (
    FIXTURE_ROOT,
    REFERENCE_ADAPTER,
)
from tests.onboarding.test_process_client import (
    _request as _inventory_request,
)
from ucf.adapter_protocol import (
    AdapterPayload,
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    CapabilitySelection,
    ErrorCategory,
    Method,
    ProcessTimeouts,
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
    validate_execution_verification_result,
)
from ucf.inventory import INVENTORY_CAPABILITY, collect_inventory_from_process
from ucf.ir.models import Check, EntityRef, IntegerValue, PortRef
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    Claim,
    ClaimLevel,
)
from ucf.onboarding import build_onboarding_bundle, collect_onboarding_evidence


def _logical_inventory():
    return _reviewed_bundle().inventory.model_dump(mode="json")


def _verification_request(
    *,
    expected_total_cents: int = 2500,
    root_path: Path = FIXTURE_ROOT,
    inventory=None,
    bundle=None,
    mapping=None,
) -> ExecutionVerificationRequest:
    bundle = _reviewed_bundle() if bundle is None else bundle
    mapping = (
        _mapping_result(_mapping_request(bundle)) if mapping is None else mapping
    )
    binding = mapping.bindings[0]
    subject = next(
        entity
        for entity in bundle.behavior.entities
        if entity.id == binding.behavior.target_id
    )
    owner = EntityRef(
        kind="entity_ref",
        target_kind=binding.behavior.target_kind,
        target_id=binding.behavior.target_id,
    )
    logical_inventory = (
        bundle.inventory.model_dump(mode="json")
        if inventory is None
        else inventory
    )
    environment = build_execution_environment(root_path, logical_inventory)
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
        adapter_procedure_uri=VERIFICATION_ADAPTER_PROCEDURE_URI,
        mapping=ImplementationMappingResultRef(
            kind="implementation_mapping_result_ref",
            schema_uri=IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
            schema_version=IMPLEMENTATION_EVIDENCE_VERSION,
            target_id=mapping.id,
            canonical_digest=canonical_implementation_evidence_digest(mapping),
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
                    value={"quantity": 2, "unit-price-cents": 1250}[port.name],
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
                    value=expected_total_cents,
                ),
            )
            for port in subject.output_ports
        ),
        source=ImplementationSource(
            kind="implementation_source",
            subject_uri=logical_inventory["subject_uri"],
            source_revision=logical_inventory["source_revision"],
            records=binding.source_records,
        ),
        environment=ExecutionEnvironment.model_validate(environment),
        check=Check(
            kind="check",
            id=CHECK_ID,
            version=IMPLEMENTATION_EVIDENCE_VERSION,
            procedure_uri=CHECK_PROCEDURE_URI,
        ),
    )


def _verification_plan(request: ExecutionVerificationRequest):
    mapping = _mapping_result()
    current_inventory = _logical_inventory()
    return decode_verification_plan(
        execution_verification_request_to_payload(request).model_dump(mode="json"),
        current_inventory=current_inventory,
        mapping=mapping.model_dump(mode="json"),
        expected_environment=request.environment.model_dump(mode="json"),
    )


def _result(request: ExecutionVerificationRequest, outcome: str):
    product = build_verification_result_payload(
        request.model_dump(mode="json"),
        outcome=outcome,
        executed_at=datetime.now(UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return execution_verification_result_from_payload(
        AdapterPayload.model_validate_json(json.dumps(product.payload))
    )


def test_python_native_verification_passes_and_projects_only_tested_evidence():
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)
    bundle = _reviewed_bundle()
    mapping = _mapping_result()
    request = _verification_request()
    plan = _verification_plan(request)

    execution = run_native_verification(
        FIXTURE_ROOT,
        _logical_inventory(),
        expected_total_cents=plan.expected_total_cents,
    )
    result = _result(request, execution.outcome)

    assert execution.outcome == "passed"
    assert result.request == request
    assert result.procedure_uri == VERIFICATION_ADAPTER_PROCEDURE_URI
    assert result.id == derive_execution_verification_result_id(result)
    validate_execution_verification_result(
        result,
        request=request,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=bundle.inventory,
        mapping_initialized_adapter=mapping.producer,
        initialized_adapter=result.producer,
        negotiated_capabilities={
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
        },
    )
    projection = project_execution_verification(
        result,
        request=request,
        mapping_result=mapping,
        bundle=bundle,
        current_inventory=bundle.inventory,
        mapping_initialized_adapter=mapping.producer,
        initialized_adapter=result.producer,
        negotiated_capabilities={
            IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
            EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
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
    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before


def test_python_reference_adapter_verifies_through_the_real_process() -> None:
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)
    bundle = _reviewed_bundle()
    mapping_request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
            ),
            cwd=FIXTURE_ROOT,
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
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(7),
                operation_timeout=5.0,
            )
            mapping_payload = await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=5.0,
            )
            mapping = implementation_mapping_result_from_payload(
                mapping_payload
            )
            request = _verification_request()
            result_payload = await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
                timeout=10.0,
            )
            result = execution_verification_result_from_payload(result_payload)
        finally:
            await adapter.close()
        return initialized, inventory, mapping, request, result, adapter

    initialized, inventory, mapping, request, result, adapter = asyncio.run(
        scenario()
    )

    assert mapping == _mapping_result(mapping_request)
    assert result.outcome == "passed"
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
    assert adapter.stderr_total_bytes == 0
    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before


def test_python_reference_adapter_verifies_a_non_dot_inventory_root() -> None:
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)
    bundle = _reviewed_bundle()
    mapping_request = _mapping_request(bundle)
    inventory_request = _inventory_request(7).model_copy(
        update={"root_path": FIXTURE_ROOT.name}
    )

    async def scenario():
        adapter = AdapterProcess(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
            ),
            cwd=FIXTURE_ROOT.parent,
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
        )
        try:
            await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=inventory_request,
                operation_timeout=5.0,
            )
            await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=5.0,
            )
            request = _verification_request(root_path=FIXTURE_ROOT)
            payload = await adapter.call(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
                timeout=10.0,
            )
            result = execution_verification_result_from_payload(payload)
        finally:
            await adapter.close()
        return inventory, result, adapter

    inventory, result, adapter = asyncio.run(scenario())

    assert inventory == bundle.inventory
    assert result.outcome == "passed"
    assert adapter.stderr_total_bytes == 0
    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before


def test_python_reference_verify_preflight_observes_process_cancellation() -> None:
    bundle = _reviewed_bundle()
    mapping_request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
                "--mode",
                "block-verify",
            ),
            cwd=FIXTURE_ROOT,
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
        )
        try:
            await adapter.start()
            await collect_inventory_from_process(
                adapter,
                request=_inventory_request(7),
                operation_timeout=5.0,
            )
            await adapter.call(
                Method.MAP,
                implementation_mapping_request_to_payload(mapping_request),
                timeout=5.0,
            )
            call = await adapter.begin(
                Method.VERIFY,
                execution_verification_request_to_payload(
                    _verification_request()
                ),
            )
            with pytest.raises(AdapterProtocolError) as cancelled:
                await call.cancel()
            assert cancelled.value.request_id == call.request_id
            assert cancelled.value.category is ErrorCategory.CANCELLED
            assert cancelled.value.code is ProtocolCode.REQUEST_CANCELLED
        finally:
            await adapter.close()
        return adapter

    adapter = asyncio.run(scenario())

    assert adapter.stderr_total_bytes == 0


def test_python_reference_native_verify_cancels_and_reaps_its_process(
    tmp_path: Path,
) -> None:
    root = tmp_path / "process-cancel"
    shutil.copytree(
        FIXTURE_ROOT,
        root,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    service = root / "src" / "legacy_quote" / "service.py"
    service.write_text(
        "def quote_order(unit_price_cents: int, quantity: int) -> int:\n"
        "    while True:\n"
        "        pass\n\n"
        "def format_receipt(total_cents: int) -> str:\n"
        "    return f'Total: {total_cents / 100:.2f}'\n",
        encoding="utf-8",
    )
    timeouts = ProcessTimeouts(
        initialize=2.0,
        operation=10.0,
        write=1.0,
        cancellation=3.0,
        shutdown=2.0,
        terminate=0.5,
        kill=0.5,
    )

    async def collect():
        return await collect_onboarding_evidence(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
            ),
            cwd=root,
            inventory_request=_inventory_request(7),
            timeouts=timeouts,
            operation_timeout=10.0,
        )

    evidence = asyncio.run(collect())
    bundle = build_onboarding_bundle(
        evidence.inventory,
        evidence.discovery,
        _decisions(evidence.discovery),
    )
    mapping_request = _mapping_request(bundle)

    async def scenario():
        adapter = AdapterProcess(
            command=(
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(REFERENCE_ADAPTER),
            ),
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
            timeouts=timeouts,
        )
        try:
            initialized = await adapter.start()
            inventory = await collect_inventory_from_process(
                adapter,
                request=_inventory_request(7),
                operation_timeout=10.0,
            )
            mapping = implementation_mapping_result_from_payload(
                await adapter.call(
                    Method.MAP,
                    implementation_mapping_request_to_payload(mapping_request),
                    timeout=10.0,
                )
            )
            request = _verification_request(
                root_path=root,
                inventory=inventory.model_dump(mode="json"),
                bundle=bundle,
                mapping=mapping,
            )
            call = await adapter.begin(
                Method.VERIFY,
                execution_verification_request_to_payload(request),
            )
            children = await asyncio.to_thread(_wait_for_children, adapter.pid)
            with pytest.raises(AdapterProtocolError) as cancelled:
                await call.cancel()
            assert cancelled.value.request_id == call.request_id
            assert cancelled.value.category is ErrorCategory.CANCELLED
            assert cancelled.value.code is ProtocolCode.REQUEST_CANCELLED
            assert all(not Path(f"/proc/{pid}").exists() for pid in children)
            assert _child_pids(adapter.pid) == set()
        finally:
            await adapter.close()
        return initialized, inventory, mapping, adapter

    initialized, inventory, mapping, adapter = asyncio.run(scenario())

    assert initialized.adapter == mapping.producer
    assert inventory == bundle.inventory
    assert adapter.stderr_total_bytes == 0


def test_python_native_verification_expected_mismatch_is_not_projectable():
    request = _verification_request(expected_total_cents=2501)
    plan = _verification_plan(request)
    execution = run_native_verification(
        FIXTURE_ROOT,
        _logical_inventory(),
        expected_total_cents=plan.expected_total_cents,
    )
    result = _result(request, execution.outcome)

    assert execution.outcome == "failed"
    with pytest.raises(ImplementationEvidenceValidationError) as captured:
        project_execution_verification(
            result,
            request=request,
            mapping_result=_mapping_result(),
            bundle=_reviewed_bundle(),
            current_inventory=_reviewed_bundle().inventory,
            mapping_initialized_adapter=_mapping_result().producer,
            initialized_adapter=result.producer,
            negotiated_capabilities={
                IMPLEMENTATION_MAPPING_CAPABILITY: "1.0.0",
                EXECUTION_VERIFICATION_CAPABILITY: "1.0.0",
            },
        )
    assert captured.value.code is ImplementationEvidenceErrorCode.EVIDENCE_NOT_PASSED


def test_python_native_environment_receipt_binds_only_executed_artifacts(
    tmp_path: Path,
):
    inventory = _logical_inventory()

    first = build_execution_environment(FIXTURE_ROOT, inventory)
    second = build_execution_environment(FIXTURE_ROOT, inventory)
    unrelated_revision = copy.deepcopy(inventory)
    unrelated_revision["source_revision"]["value"] = "f" * 64
    changed_root = tmp_path / "changed-source"
    shutil.copytree(
        FIXTURE_ROOT,
        changed_root,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    service = changed_root / "src" / "legacy_quote" / "service.py"
    service.write_text(
        service.read_text(encoding="utf-8") + "\n# environment receipt drift\n",
        encoding="utf-8",
    )
    changed_inventory = _inventory_with_current_files(changed_root)

    assert first == second
    assert first == build_execution_environment(
        FIXTURE_ROOT,
        unrelated_revision,
    )
    assert first != build_execution_environment(
        changed_root,
        changed_inventory,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "procedure",
        "mapping",
        "source",
        "environment",
        "check",
        "order",
        "input-value",
        "output-kind",
        "unknown",
    ],
)
def test_python_verification_rejects_rebound_context_before_execution(
    mutation: str,
):
    request = _verification_request()
    logical = request.model_dump(mode="json")
    if mutation == "procedure":
        logical["adapter_procedure_uri"] = (
            "urn:ucf:adapter:python-reference-other:1.0.0"
        )
    elif mutation == "mapping":
        logical["mapping"]["canonical_digest"]["value"] = "f" * 64
    elif mutation == "source":
        logical["source"]["source_revision"]["value"] = "f" * 64
    elif mutation == "environment":
        logical["environment"]["revision"]["value"] = "f" * 64
    elif mutation == "check":
        logical["check"]["id"] = "check.other"
    elif mutation == "order":
        logical["inputs"].reverse()
    elif mutation == "input-value":
        logical["inputs"][0]["value"]["value"] = 3
    elif mutation == "output-kind":
        logical["expected_outputs"][0]["value"] = {
            "kind": "string",
            "value": "2500",
        }
    else:
        logical["command"] = ["sh", "-c", "arbitrary"]

    payload = encode_adapter_payload(
        logical,
        schema_uri=EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    )
    with pytest.raises(ProfileError) as captured:
        decode_verification_plan(
            payload,
            current_inventory=_logical_inventory(),
            mapping=_mapping_result().model_dump(mode="json"),
            expected_environment=request.environment.model_dump(mode="json"),
        )
    assert captured.value.code == "invalid_params"


@pytest.mark.parametrize("mode", ["timeout", "overflow"])
def test_python_native_runtime_failures_are_minimal_and_reaped(
    tmp_path: Path,
    mode: str,
):
    root = tmp_path / mode
    shutil.copytree(FIXTURE_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    service = root / "src" / "legacy_quote" / "service.py"
    if mode == "timeout":
        service.write_text(
            "def quote_order(unit_price_cents: int, quantity: int) -> int:\n"
            "    while True:\n"
            "        pass\n\n"
            "def format_receipt(total_cents: int) -> str:\n"
            "    return f'Total: {total_cents / 100:.2f}'\n",
            encoding="utf-8",
        )
    else:
        service.write_text(
            "def quote_order(unit_price_cents: int, quantity: int) -> int:\n"
            "    print('x' * 4096)\n"
            "    return unit_price_cents * quantity\n\n"
            "def format_receipt(total_cents: int) -> str:\n"
            "    return f'Total: {total_cents / 100:.2f}'\n",
            encoding="utf-8",
        )
    inventory = _inventory_with_current_files(root)
    limits = NativeVerificationLimits(
        execution_timeout=0.2 if mode == "timeout" else 2.0,
        termination_grace=0.2,
        cleanup_timeout=0.5,
        max_output_bytes=128,
        max_source_file_bytes=DEFAULT_LIMITS.max_source_file_bytes,
        max_snapshot_bytes=DEFAULT_LIMITS.max_snapshot_bytes,
        max_interpreter_bytes=DEFAULT_LIMITS.max_interpreter_bytes,
    )

    result = run_native_verification(
        root,
        inventory,
        expected_total_cents=2500,
        limits=limits,
    )

    assert result.outcome == "error"
    assert _child_pids(os.getpid()) == set()


def test_python_native_cancellation_reaps_before_ack_and_cleans_snapshot(
    tmp_path: Path,
):
    root = tmp_path / "cancel"
    shutil.copytree(FIXTURE_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    service = root / "src" / "legacy_quote" / "service.py"
    service.write_text(
        "def quote_order(unit_price_cents: int, quantity: int) -> int:\n"
        "    while True:\n"
        "        pass\n\n"
        "def format_receipt(total_cents: int) -> str:\n"
        "    return f'Total: {total_cents / 100:.2f}'\n",
        encoding="utf-8",
    )
    inventory = _inventory_with_current_files(root)
    cancelled = threading.Event()
    snapshots_before = set(Path(tempfile.gettempdir()).glob("ucf-python-native-*"))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            run_native_verification,
            root,
            inventory,
            expected_total_cents=2500,
            cancel_event=cancelled,
        )
        children = _wait_for_children(os.getpid())
        cancelled.set()
        with pytest.raises(NativeVerificationCancelled):
            future.result(timeout=3.0)

    assert children
    assert all(not Path(f"/proc/{pid}").exists() for pid in children)
    assert _child_pids(os.getpid()) == set()
    assert set(Path(tempfile.gettempdir()).glob("ucf-python-native-*")) == (
        snapshots_before
    )


def test_python_native_source_swap_rejects_snapshot_result(tmp_path: Path):
    root = tmp_path / "swap"
    shutil.copytree(FIXTURE_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    service = root / "src" / "legacy_quote" / "service.py"
    service.write_text(
        "import time\n\n"
        "def quote_order(unit_price_cents: int, quantity: int) -> int:\n"
        "    time.sleep(0.4)\n"
        "    return unit_price_cents * quantity\n\n"
        "def format_receipt(total_cents: int) -> str:\n"
        "    return f'Total: {total_cents / 100:.2f}'\n",
        encoding="utf-8",
    )
    inventory = _inventory_with_current_files(root)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            run_native_verification,
            root,
            inventory,
            expected_total_cents=2500,
        )
        _wait_for_children(os.getpid())
        service.write_text("def quote_order(*args):\n    return 1\n", encoding="utf-8")
        with pytest.raises(NativeVerificationError) as captured:
            future.result(timeout=3.0)

    assert captured.value.code == "operation_failed"
    assert _child_pids(os.getpid()) == set()


@pytest.mark.parametrize("mode", ["changed-check", "symlinked-service"])
def test_python_native_rejects_untrusted_execution_layout_before_spawn(
    tmp_path: Path,
    mode: str,
):
    root = tmp_path / mode
    shutil.copytree(FIXTURE_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    if mode == "changed-check":
        check = root / "tests" / "behavior_checks.py"
        check.write_text("print('3 native behavior checks passed')\n", encoding="utf-8")
        inventory = _inventory_with_current_files(root)
    else:
        service = root / "src" / "legacy_quote" / "service.py"
        outside = root / "outside.py"
        outside.write_bytes(service.read_bytes())
        service.unlink()
        service.symlink_to(outside)
        inventory = _logical_inventory()

    with pytest.raises(NativeVerificationError) as captured:
        run_native_verification(
            root,
            inventory,
            expected_total_cents=2500,
        )

    assert captured.value.code == "operation_failed"
    assert _child_pids(os.getpid()) == set()


def _inventory_with_current_files(root: Path):
    inventory = copy.deepcopy(_logical_inventory())
    records = inventory["records"]
    for record in records:
        if record["kind"] != "repository_entry":
            continue
        path = root / record["path"]
        if record["entry_kind"] != "file" or not path.is_file():
            continue
        payload = path.read_bytes()
        record["size_bytes"] = len(payload)
        record["content_digest"]["value"] = hashlib.sha256(payload).hexdigest()
    inventory["source_revision"]["value"] = hashlib.sha256(
        b"test-native-inventory\0"
        + b"\0".join(
            (root / path).read_bytes()
            for path in (
                "src/legacy_quote/__init__.py",
                "src/legacy_quote/service.py",
                "tests/behavior_checks.py",
            )
        )
    ).hexdigest()
    return inventory


def _child_pids(process_id: int) -> set[int]:
    children: set[int] = set()
    task_root = Path(f"/proc/{process_id}/task")
    if not task_root.exists():
        return children
    for task in task_root.iterdir():
        child_file = task / "children"
        try:
            children.update(int(item) for item in child_file.read_text().split())
        except FileNotFoundError:
            continue
    return children


def _wait_for_children(process_id: int) -> set[int]:
    deadline = threading.Event()
    for _ in range(200):
        children = _child_pids(process_id)
        if children:
            return children
        deadline.wait(0.01)
    raise AssertionError("native verification child did not start")
