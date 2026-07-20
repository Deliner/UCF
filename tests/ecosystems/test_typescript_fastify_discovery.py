from __future__ import annotations

import asyncio
from pathlib import Path

from tools.typescript_fastify_adapter_contract import (
    TypeScriptFastifyHarness,
    TypeScriptFastifyTarget,
    typescript_fastify_fixture_manifest,
)

from tests.ecosystems.test_typescript_fastify_inventory import (
    FAST_TIMEOUTS,
    SOURCE_REVISION,
    _entry_path,
    _request,
)
from tests.onboarding.test_process_client import (
    _collect as collect_python_onboarding_evidence,
)
from ucf.inventory import (
    BuildManifestFact,
    PublicInterfaceFact,
    canonical_inventory_json,
)
from ucf.onboarding import (
    canonical_onboarding_json,
    collect_onboarding_evidence,
    derive_discovery_candidate_id,
)

DISCOVERY_PROCEDURE_URI = (
    "urn:ucf:onboarding-procedure:"
    "typescript-fastify-static-discovery:1.0.0"
)
DISCOVERY_CONFIDENCE_BASIS = (
    "urn:ucf:onboarding-confidence:"
    "typescript-exported-function:1.0.0"
)
EXPECTED_SEMANTIC_DIGESTS = {
    "use-case.format-receipt": (
        "ba7d915efbc19bff087cee325125b801f64d3d3f932db3df96a87d9dadf4569c"
    ),
    "use-case.legacy-discount-hint": (
        "d0182d40ad306dd41fef8090a3caca94ba491f30a5a1dc83a702dbd5f207f8b8"
    ),
    "use-case.normalize-coupon": (
        "d44419a028758d14eb1dfc5edc5d1c2b8d6fc1f1744fa6b17f063117d409261f"
    ),
    "use-case.quote-order": (
        "cd09cf6ac27457ddbd62715ad903b4b3e0217c6b580cbde1d75c8d2c1b17153a"
    ),
}
EXPECTED_ROOTS_BY_SUBJECT = {
    "formatReceipt": "use-case.format-receipt",
    "legacyDiscountHint": "use-case.legacy-discount-hint",
    "normalizeCoupon": "use-case.normalize-coupon",
    "quoteOrder": "use-case.quote-order",
}
EXPECTED_CONFIDENCE_BY_SUBJECT = {
    "formatReceipt": "0.82",
    "legacyDiscountHint": "0.61",
    "normalizeCoupon": "0.82",
    "quoteOrder": "0.82",
}


def test_typescript_fastify_discovery_is_exact_contextual_repeatable_and_read_only(
    tmp_path: Path,
    typescript_fastify_harness: TypeScriptFastifyHarness,
) -> None:
    target = typescript_fastify_harness.new_target(
        tmp_path / "discovery-target"
    )
    before = typescript_fastify_fixture_manifest(target.fixture_root)
    assert before == target.source_manifest
    assert len(before) == 7

    first = _collect(
        target=target,
        record_limit=7,
        hash_seed=1,
        stderr_path=tmp_path / "adapter-a.stderr",
    )
    second = _collect(
        target=target,
        record_limit=1,
        hash_seed=31_337,
        stderr_path=tmp_path / "adapter-b.stderr",
    )

    assert (tmp_path / "adapter-a.stderr").read_bytes() == b""
    assert (tmp_path / "adapter-b.stderr").read_bytes() == b""
    assert typescript_fastify_fixture_manifest(target.fixture_root) == before
    assert canonical_inventory_json(first.inventory) == canonical_inventory_json(
        second.inventory
    )
    assert first.inventory.source_revision.value == SOURCE_REVISION
    assert second.inventory.source_revision.value == SOURCE_REVISION
    assert canonical_onboarding_json(
        first.discovery
    ) == canonical_onboarding_json(second.discovery)

    discovery = first.discovery
    assert discovery.producer.name == "org.ucf.adapter.typescript-fastify"
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
    assert eligible == {
        "POST /quote-order",
        "buildApp",
        "formatReceipt",
        "legacyDiscountHint",
        "normalizeCoupon",
        "quoteOrder",
    }
    assert uncovered == {"POST /quote-order", "buildApp"}

    quote = candidates_by_subject["quoteOrder"]
    assert {
        _evidence_descriptor(reference.target_id, records_by_id)
        for reference in quote.evidence
    } == {
        ("build_manifest", "package-lock.json"),
        ("build_manifest", "package.json"),
        ("build_manifest", "tsconfig.json"),
        ("public_interface", "POST /quote-order"),
        ("public_interface", "quoteOrder"),
    }
    for subject_name in (
        "formatReceipt",
        "legacyDiscountHint",
        "normalizeCoupon",
    ):
        candidate = candidates_by_subject[subject_name]
        assert candidate.evidence == (candidate.subject,)

    python_discovery = collect_python_onboarding_evidence().discovery
    python_quote = next(
        candidate
        for candidate in python_discovery.candidates
        if candidate.semantic_digest.value
        == EXPECTED_SEMANTIC_DIGESTS["use-case.quote-order"]
    )
    assert python_quote.semantic_digest == quote.semantic_digest
    assert python_quote.id != quote.id


def _collect(
    *,
    target: TypeScriptFastifyTarget,
    record_limit: int,
    hash_seed: int,
    stderr_path: Path,
):
    async def scenario():
        return await collect_onboarding_evidence(
            command=(
                "/bin/sh",
                "-c",
                'exec "$1" "$2" "$3" 2>"$4"',
                "ucf-typescript-fastify-discovery",
                *target.command(hash_seed=hash_seed),
                str(stderr_path),
            ),
            cwd=target.fixture_root,
            inventory_request=_request(record_limit),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=10.0,
        )

    return asyncio.run(scenario())


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
