from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest
from tools.go_stdlib_adapter_contract import (
    GoStdlibHarness,
    GoStdlibTarget,
    go_stdlib_fixture_manifest,
)

from tests.ecosystems.test_go_stdlib_inventory import (
    EXPECTED_INTERFACES,
    FAST_TIMEOUTS,
    SOURCE_REVISION,
    _entry_path,
    _page,
    _request,
)
from tests.ecosystems.test_typescript_fastify_discovery import (
    EXPECTED_SEMANTIC_DIGESTS,
)
from tests.onboarding.test_process_client import (
    _collect as collect_python_onboarding_evidence,
)
from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    ProtocolCode,
)
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_VERSION,
    BuildManifestFact,
    InventoryProvenance,
    PublicInterfaceFact,
    canonical_inventory_json,
    collect_inventory_from_process,
)
from ucf.ir.models import (
    Digest,
    NullValue,
    Producer,
    RecordEntry,
    RecordValue,
)
from ucf.onboarding import (
    DISCOVERY_CAPABILITY,
    ONBOARDING_VERSION,
    canonical_onboarding_json,
    collect_onboarding_evidence,
    derive_discovery_candidate_id,
    discovery_request_to_payload,
    discovery_result_from_payload,
)
from ucf.onboarding.client import _discovery_request

DISCOVERY_PROCEDURE_URI = (
    "urn:ucf:onboarding-procedure:go-stdlib-static-discovery:1.0.0"
)
DISCOVERY_CONFIDENCE_BASIS = (
    "urn:ucf:onboarding-confidence:go-exported-function:1.0.0"
)
EXPECTED_ROOTS_BY_SUBJECT = {
    "FormatReceipt": "use-case.format-receipt",
    "LegacyDiscountHint": "use-case.legacy-discount-hint",
    "NormalizeCoupon": "use-case.normalize-coupon",
    "QuoteOrder": "use-case.quote-order",
}
EXPECTED_CONFIDENCE_BY_SUBJECT = {
    "FormatReceipt": "0.82",
    "LegacyDiscountHint": "0.61",
    "NormalizeCoupon": "0.82",
    "QuoteOrder": "0.82",
}
EXPECTED_ELIGIBLE = {
    "FormatReceipt",
    "LegacyDiscountHint",
    "NormalizeCoupon",
    "POST /quote-order",
    "QuoteOrder",
    "error",
    "http-response-write",
    "quantity",
    "quote.Handler.func1",
    "receipt",
    "total_cents",
    "unit_price_cents",
}
EXPECTED_UNCOVERED = EXPECTED_ELIGIBLE - set(EXPECTED_ROOTS_BY_SUBJECT)
EXPECTED_QUOTE_EVIDENCE = {
    ("build_manifest", "go.mod"),
    ("public_interface", "POST /quote-order"),
    ("public_interface", "QuoteOrder"),
    ("public_interface", "error"),
    ("public_interface", "http-response-write"),
    ("public_interface", "quantity"),
    ("public_interface", "quote.Handler.func1"),
    ("public_interface", "receipt"),
    ("public_interface", "total_cents"),
    ("public_interface", "unit_price_cents"),
}


def test_go_stdlib_discovery_is_exact_contextual_repeatable_and_read_only(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "discovery-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest

    first = _collect(
        target=target,
        record_limit=7,
        stderr_path=tmp_path / "adapter-a.stderr",
    )
    second = _collect(
        target=target,
        record_limit=1,
        stderr_path=tmp_path / "adapter-b.stderr",
    )

    assert (tmp_path / "adapter-a.stderr").read_bytes() == b""
    assert (tmp_path / "adapter-b.stderr").read_bytes() == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before
    assert canonical_inventory_json(first.inventory) == canonical_inventory_json(
        second.inventory
    )
    assert first.inventory.source_revision.value == SOURCE_REVISION
    assert second.inventory.source_revision.value == SOURCE_REVISION
    assert canonical_onboarding_json(
        first.discovery
    ) == canonical_onboarding_json(second.discovery)

    discovery = first.discovery
    assert discovery.producer.name == "org.ucf.adapter.go-stdlib"
    assert discovery.producer.version == "1.0.0"
    assert discovery.procedure_uri == DISCOVERY_PROCEDURE_URI
    assert discovery.diagnostics == ()
    assert len(discovery.candidates) == 4

    records_by_id = {record.id: record for record in first.inventory.records}
    candidates_by_root = {
        candidate.proposal.root.target_id: candidate
        for candidate in discovery.candidates
    }
    assert {
        root: candidate.semantic_digest.value
        for root, candidate in candidates_by_root.items()
    } == EXPECTED_SEMANTIC_DIGESTS

    roots_by_subject: dict[str, str] = {}
    confidence_by_subject: dict[str, str] = {}
    candidates_by_subject = {}
    for candidate in discovery.candidates:
        subject = records_by_id[candidate.subject.target_id]
        assert isinstance(subject, PublicInterfaceFact)
        roots_by_subject[subject.name] = candidate.proposal.root.target_id
        confidence_by_subject[subject.name] = candidate.confidence.value
        candidates_by_subject[subject.name] = candidate
        assert candidate.confidence.basis == DISCOVERY_CONFIDENCE_BASIS
        assert candidate.id == derive_discovery_candidate_id(
            candidate,
            discovery,
        )
    assert roots_by_subject == EXPECTED_ROOTS_BY_SUBJECT
    assert confidence_by_subject == EXPECTED_CONFIDENCE_BY_SUBJECT

    eligible = {
        _interface_name(reference.target_id, records_by_id)
        for reference in discovery.coverage.eligible_subjects
    }
    uncovered = {
        _interface_name(reference.target_id, records_by_id)
        for reference in discovery.coverage.uncovered_subjects
    }
    assert discovery.coverage.status == "partial"
    assert eligible == EXPECTED_ELIGIBLE
    assert uncovered == EXPECTED_UNCOVERED

    quote = candidates_by_subject["QuoteOrder"]
    assert {
        _evidence_descriptor(reference.target_id, records_by_id)
        for reference in quote.evidence
    } == EXPECTED_QUOTE_EVIDENCE
    expected_spans = {
        name: span
        for _, _, name, _, span, _ in EXPECTED_INTERFACES
    }
    for reference in quote.evidence:
        target = records_by_id[reference.target_id]
        if not isinstance(target, PublicInterfaceFact):
            continue
        provenance = records_by_id[target.provenance.target_id]
        assert isinstance(provenance, InventoryProvenance)
        assert provenance.procedure_uri == (
            "urn:ucf:inventory-procedure:"
            "go-stdlib-syntax-classification:1.0.0"
        )
        span = provenance.source_span
        assert span is not None
        assert (
            span.start_line,
            span.start_column,
            span.end_line,
            span.end_column,
        ) == expected_spans[target.name]
    for subject_name in (
        "FormatReceipt",
        "LegacyDiscountHint",
        "NormalizeCoupon",
    ):
        candidate = candidates_by_subject[subject_name]
        assert candidate.evidence == (candidate.subject,)

    python_discovery = collect_python_onboarding_evidence().discovery
    python_by_root = {
        candidate.proposal.root.target_id: candidate
        for candidate in python_discovery.candidates
    }
    assert {
        root: candidate.semantic_digest.value
        for root, candidate in python_by_root.items()
    } == EXPECTED_SEMANTIC_DIGESTS
    assert all(
        candidates_by_root[root].id != python_by_root[root].id
        for root in EXPECTED_SEMANTIC_DIGESTS
    )


def test_go_stdlib_completed_inventory_remains_discoverable_after_page_replay(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "discovery-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)

    async def scenario():
        adapter = _discovery_adapter(target)
        try:
            await adapter.start()
            first = await _page(adapter, _request(7))
            assert first.next_cursor is not None
            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            request = _discovery_request(inventory)
            initial = discovery_result_from_payload(
                await adapter.call(
                    Method.DISCOVER,
                    discovery_request_to_payload(request),
                    timeout=10.0,
                )
            )

            replayed = await _page(
                adapter,
                _request(7, cursor=first.next_cursor),
            )
            repeated = discovery_result_from_payload(
                await adapter.call(
                    Method.DISCOVER,
                    discovery_request_to_payload(request),
                    timeout=10.0,
                )
            )
            return (
                replayed,
                initial,
                repeated,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    replayed, initial, repeated, stderr_total, stderr_tail = asyncio.run(
        scenario()
    )

    assert not replayed.complete
    assert initial == repeated
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def test_go_stdlib_discovery_rejects_unbound_profiles_and_recovers(
    tmp_path: Path,
    go_stdlib_harness: GoStdlibHarness,
) -> None:
    target = go_stdlib_harness.new_target(tmp_path / "discovery-target")
    before = go_stdlib_fixture_manifest(target.fixture_root)
    baseline = _collect(
        target=target,
        record_limit=256,
        stderr_path=tmp_path / "baseline.stderr",
    )
    before_inventory_request = _discovery_request(baseline.inventory)

    async def scenario():
        adapter = _discovery_adapter(target)
        failures: list[AdapterProtocolError] = []
        try:
            await adapter.start()
            with pytest.raises(AdapterProtocolError) as before_inventory:
                await adapter.call(
                    Method.DISCOVER,
                    discovery_request_to_payload(before_inventory_request),
                    timeout=10.0,
                )
            failures.append(before_inventory.value)

            first = await _page(adapter, _request(1))
            assert not first.complete
            with pytest.raises(AdapterProtocolError) as incomplete:
                await adapter.call(
                    Method.DISCOVER,
                    discovery_request_to_payload(before_inventory_request),
                    timeout=10.0,
                )
            failures.append(incomplete.value)

            inventory = await collect_inventory_from_process(
                adapter,
                request=_request(7),
                operation_timeout=10.0,
            )
            request = _discovery_request(inventory)
            for malformed in _unbound_discovery_payloads(request):
                with pytest.raises(AdapterProtocolError) as rejected:
                    await adapter.call(
                        Method.DISCOVER,
                        malformed,
                        timeout=10.0,
                    )
                failures.append(rejected.value)

            recovered = discovery_result_from_payload(
                await adapter.call(
                    Method.DISCOVER,
                    discovery_request_to_payload(request),
                    timeout=10.0,
                )
            )
            return (
                inventory,
                failures,
                recovered,
                adapter.stderr_total_bytes,
                adapter.stderr_tail,
            )
        finally:
            await adapter.close()

    inventory, failures, recovered, stderr_total, stderr_tail = asyncio.run(
        scenario()
    )

    assert canonical_inventory_json(inventory) == canonical_inventory_json(
        baseline.inventory
    )
    assert [failure.code for failure in failures[:2]] == [
        ProtocolCode.OPERATION_FAILED,
        ProtocolCode.OPERATION_FAILED,
    ]
    assert all(
        failure.category is ErrorCategory.ADAPTER_FAILURE
        for failure in failures[:2]
    )
    assert len(failures[2:]) == 5
    assert all(
        failure.category is ErrorCategory.PROTOCOL_FAILURE
        and failure.code is ProtocolCode.INVALID_PARAMS
        for failure in failures[2:]
    )
    assert recovered == baseline.discovery
    assert (tmp_path / "baseline.stderr").read_bytes() == b""
    assert stderr_total == 0
    assert stderr_tail == b""
    assert go_stdlib_fixture_manifest(target.fixture_root) == before


def _collect(
    *,
    target: GoStdlibTarget,
    record_limit: int,
    stderr_path: Path,
):
    async def scenario():
        return await collect_onboarding_evidence(
            command=(
                "/bin/sh",
                "-c",
                'exec "$1" 2>"$2"',
                "ucf-go-stdlib-discovery",
                *target.command(),
                str(stderr_path),
            ),
            cwd=target.fixture_root,
            inventory_request=_request(record_limit),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=10.0,
        )

    return asyncio.run(scenario())


def _discovery_adapter(target: GoStdlibTarget) -> AdapterProcess:
    return AdapterProcess(
        command=target.command(),
        cwd=target.fixture_root,
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
        timeouts=FAST_TIMEOUTS,
    )


def _unbound_discovery_payloads(request):
    stale_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value="0" * 64,
    )
    binding_only = request.model_copy(
        update={
            "inventory_binding": request.inventory_binding.model_copy(
                update={"canonical_digest": stale_digest}
            )
        }
    )
    stale_inventory = request.inventory.model_copy(
        update={"source_revision": stale_digest}
    )
    stale_request = request.model_copy(
        update={
            "inventory": stale_inventory,
            "inventory_binding": request.inventory_binding.model_copy(
                update={
                    "source_revision": stale_digest,
                    "canonical_digest": _inventory_digest(stale_inventory),
                }
            ),
        }
    )
    forged_inventory = request.inventory.model_copy(
        update={
            "producer": Producer(
                kind="producer",
                name="org.ucf.adapter.forged",
                version="1.0.0",
            )
        }
    )
    forged_request = request.model_copy(
        update={
            "inventory": forged_inventory,
            "inventory_binding": request.inventory_binding.model_copy(
                update={
                    "canonical_digest": _inventory_digest(forged_inventory)
                }
            ),
        }
    )

    exact_payload = discovery_request_to_payload(request)
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
        if entry.name != "inventory":
            nested_entries.append(entry)
            continue
        assert isinstance(entry.value, RecordValue)
        nested_entries.append(
            entry.model_copy(
                update={
                    "value": entry.value.model_copy(
                        update={
                            "entries": tuple(reversed(entry.value.entries))
                        }
                    )
                }
            )
        )
    recursively_noncanonical = exact_payload.model_copy(
        update={
            "value": root.model_copy(
                update={"entries": tuple(nested_entries)}
            )
        }
    )
    return (
        discovery_request_to_payload(binding_only),
        discovery_request_to_payload(stale_request),
        discovery_request_to_payload(forged_request),
        unknown_field,
        recursively_noncanonical,
    )


def _inventory_digest(inventory) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_inventory_json(inventory)
        ).hexdigest(),
    )


def _interface_name(
    target_id: str,
    records_by_id: dict[str, object],
) -> str:
    target = records_by_id[target_id]
    assert isinstance(target, PublicInterfaceFact)
    return target.name


def _evidence_descriptor(
    target_id: str,
    records_by_id: dict[str, object],
) -> tuple[str, str]:
    target = records_by_id[target_id]
    if isinstance(target, BuildManifestFact):
        return ("build_manifest", _entry_path(target, records_by_id))
    assert isinstance(target, PublicInterfaceFact)
    return ("public_interface", target.name)
