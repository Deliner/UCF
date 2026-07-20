from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from tests.inventory.reference_adapter_harness import (
    nonfollowing_tree_manifest,
)
from ucf.adapter_protocol import (
    AdapterProtocolError,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.inventory import (
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_VERSION,
    FactKind,
    IgnorePolicy,
    InventoryPageRequest,
    InventoryRequest,
)
from ucf.onboarding import (
    canonical_onboarding_json,
    collect_onboarding_evidence,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "brownfield"
    / "python_legacy_quote"
)
REFERENCE_ADAPTER = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "inventory_reference_adapter.py"
)
FAST_TIMEOUTS = ProcessTimeouts(
    initialize=2.0,
    operation=5.0,
    write=1.0,
    cancellation=0.2,
    shutdown=1.0,
    terminate=0.2,
    kill=0.5,
)


def _request(record_limit: int = 3) -> InventoryRequest:
    return InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:python-legacy-quote",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=IgnorePolicy(
            kind="ignore_policy",
            policy_version=INVENTORY_VERSION,
            rules=(),
        ),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=record_limit,
            cursor=None,
        ),
    )


def _command(*arguments: str) -> tuple[str, ...]:
    return (
        sys.executable,
        "-B",
        "-X",
        "utf8",
        str(REFERENCE_ADAPTER),
        *arguments,
    )


def _collect(*, record_limit: int = 3, mode: str = "normal"):
    async def scenario():
        return await collect_onboarding_evidence(
            command=_command("--mode", mode),
            cwd=FIXTURE_ROOT,
            inventory_request=_request(record_limit),
            timeouts=FAST_TIMEOUTS,
            operation_timeout=5.0,
        )

    return asyncio.run(scenario())


def test_one_process_collects_inventory_then_exact_repeatable_discovery():
    before = nonfollowing_tree_manifest(FIXTURE_ROOT)

    first = _collect(record_limit=3)
    second = _collect(record_limit=1)

    assert nonfollowing_tree_manifest(FIXTURE_ROOT) == before
    assert canonical_onboarding_json(first.discovery) == (
        canonical_onboarding_json(second.discovery)
    )
    assert first.inventory == second.inventory
    assert len(first.discovery.candidates) == 4
    assert first.discovery.coverage.status == "complete"
    assert first.discovery.coverage.uncovered_subjects == ()
    assert {
        candidate.proposal.root.target_id
        for candidate in first.discovery.candidates
    } == {
        "use-case.quote-order",
        "use-case.format-receipt",
        "use-case.normalize-coupon",
        "use-case.legacy-discount-hint",
    }


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("wrong-discovery-profile", ProtocolCode.INVALID_ADAPTER_OUTPUT),
        ("invalid-candidate", ProtocolCode.INVALID_ADAPTER_OUTPUT),
        ("fail-discovery", ProtocolCode.OPERATION_FAILED),
    ],
)
def test_discovery_failure_returns_no_partial_onboarding_evidence(
    mode: str,
    expected: ProtocolCode,
):
    with pytest.raises(AdapterProtocolError) as captured:
        _collect(mode=mode)

    assert captured.value.code is expected
