from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from ucf.adapter_protocol import CapabilitySelection
from ucf.inventory import (
    INVENTORY_CAPABILITY,
    INVENTORY_PAGE_SCHEMA_URI,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    ApiDescriptionFact,
    BuildManifestFact,
    FactKind,
    IgnorePolicy,
    IgnoreRule,
    InventoryConfidence,
    InventoryCoverage,
    InventoryDiagnostic,
    InventoryIgnoreMatch,
    InventoryPageRequest,
    InventoryProvenance,
    InventoryRecord,
    InventoryRecordKind,
    InventoryRecordRef,
    InventoryRequest,
    InventorySnapshot,
    PathPrefixMatcher,
    PathSegmentMatcher,
    PublicInterfaceFact,
    RepositoryEntryFact,
    SourceSpan,
    canonical_inventory_json,
    derive_inventory_record_id,
    derive_inventory_source_revision,
    parse_inventory_request_json,
    parse_inventory_snapshot_json,
)
from ucf.inventory import (
    TestAssetFact as InventoryTestAssetFact,
)
from ucf.ir.models import Digest, Producer

_ZERO = "0" * 64
_ONE = "1" * 64
_TWO = "2" * 64
_THREE = "3" * 64
_FOUR = "4" * 64
_FIVE = "5" * 64
_SIX = "6" * 64
_SEVEN = "7" * 64
_EIGHT = "8" * 64
_RECORD_ADAPTER = TypeAdapter(InventoryRecord)


def _producer() -> Producer:
    return Producer(
        kind="producer",
        name="org.ucf.inventory-fixture",
        version="1.0.0",
    )


def _ref(kind: str, identifier: str) -> InventoryRecordRef:
    return InventoryRecordRef(
        kind="inventory_record_ref",
        target_kind=InventoryRecordKind(kind),
        target_id=identifier,
    )


def _confidence() -> InventoryConfidence:
    return InventoryConfidence(
        kind="confidence",
        scale="decimal-0-to-1",
        value="1",
        basis="urn:ucf:inventory-procedure:fixture-public-interface:1.0.0",
    )


def _identified(record: InventoryRecord) -> InventoryRecord:
    return record.model_copy(
        update={"id": derive_inventory_record_id(record)}
    )


def _reidentify_payload(record: dict[str, object]) -> tuple[str, str]:
    old_id = str(record["id"])
    model = _RECORD_ADAPTER.validate_json(json.dumps(record))
    new_id = derive_inventory_record_id(model)
    record["id"] = new_id
    return old_id, new_id


def _policy() -> IgnorePolicy:
    return IgnorePolicy(
        kind="ignore_policy",
        policy_version="1.0.0",
        rules=(
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.vendor",
                reason="org.ucf.inventory.vendor",
                matcher=PathSegmentMatcher(
                    kind="path_segment",
                    segment="vendor",
                ),
            ),
        ),
    )


def _snapshot() -> InventorySnapshot:
    producer = _producer()
    root_provenance = _identified(
        InventoryProvenance(
            kind="inventory_provenance",
            id=f"provenance.{_ZERO}",
            source_path=".",
            content_digest=None,
            source_span=None,
            producer=producer,
            procedure_uri=(
                "urn:ucf:inventory-procedure:fixture-entry:1.0.0"
            ),
        )
    )
    source_provenance = _identified(
        InventoryProvenance(
            kind="inventory_provenance",
            id=f"provenance.{_ZERO}",
            source_path="src",
            content_digest=None,
            source_span=None,
            producer=producer,
            procedure_uri=(
                "urn:ucf:inventory-procedure:fixture-entry:1.0.0"
            ),
        )
    )
    file_provenance = _identified(
        InventoryProvenance(
            kind="inventory_provenance",
            id=f"provenance.{_ZERO}",
            source_path="src/service.py",
            content_digest=Digest(
                kind="digest",
                algorithm="sha-256",
                value=_SEVEN,
            ),
            source_span=None,
            producer=producer,
            procedure_uri=(
                "urn:ucf:inventory-procedure:fixture-source:1.0.0"
            ),
        )
    )
    root_entry = _identified(
        RepositoryEntryFact(
            kind="repository_entry",
            id=f"entry.{_ZERO}",
            level="observed",
            provenance=_ref(
                "inventory_provenance",
                root_provenance.id,
            ),
            confidence=_confidence(),
            path=".",
            entry_kind="directory",
            size_bytes=None,
            content_digest=None,
            symlink_target_digest=None,
        )
    )
    source_entry = _identified(
        RepositoryEntryFact(
            kind="repository_entry",
            id=f"entry.{_ZERO}",
            level="observed",
            provenance=_ref(
                "inventory_provenance",
                source_provenance.id,
            ),
            confidence=_confidence(),
            path="src",
            entry_kind="directory",
            size_bytes=None,
            content_digest=None,
            symlink_target_digest=None,
        )
    )
    file_entry = _identified(
        RepositoryEntryFact(
            kind="repository_entry",
            id=f"entry.{_ZERO}",
            level="observed",
            provenance=_ref(
                "inventory_provenance",
                file_provenance.id,
            ),
            confidence=_confidence(),
            path="src/service.py",
            entry_kind="file",
            size_bytes=12,
            content_digest=Digest(
                kind="digest",
                algorithm="sha-256",
                value=_SEVEN,
            ),
            symlink_target_digest=None,
        )
    )
    interface = _identified(
        PublicInterfaceFact(
            kind="public_interface",
            id=f"interface.{_ZERO}",
            level="observed",
            provenance=_ref(
                "inventory_provenance",
                file_provenance.id,
            ),
            confidence=_confidence(),
            entry=_ref("repository_entry", file_entry.id),
            interface_kind_uri=(
                "urn:ucf:inventory-interface:function:1.0.0"
            ),
            name="shorten",
            container=None,
            declaration_digest=Digest(
                kind="digest",
                algorithm="sha-256",
                value=_SIX,
            ),
        )
    )
    records = tuple(
        sorted(
            (
                root_provenance,
                source_provenance,
                file_provenance,
                interface,
                root_entry,
                source_entry,
                file_entry,
            ),
            key=lambda record: (record.kind, record.id),
        )
    )
    return InventorySnapshot(
        kind="inventory_snapshot",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        path_identity="unicode-nfc-ascii-casefold-1",
        source_revision=derive_inventory_source_revision(records),
        producer=producer,
        capability=CapabilitySelection(
            kind="capability",
            name=INVENTORY_CAPABILITY,
            version=INVENTORY_VERSION,
        ),
        applied_policy=_policy(),
        coverage=(
            InventoryCoverage(
                kind="inventory_coverage",
                fact_kind=FactKind.API_DESCRIPTION,
                status="complete",
                record_count=0,
            ),
            InventoryCoverage(
                kind="inventory_coverage",
                fact_kind=FactKind.BUILD_MANIFEST,
                status="complete",
                record_count=0,
            ),
            InventoryCoverage(
                kind="inventory_coverage",
                fact_kind=FactKind.PUBLIC_INTERFACE,
                status="complete",
                record_count=1,
            ),
            InventoryCoverage(
                kind="inventory_coverage",
                fact_kind=FactKind.REPOSITORY_ENTRY,
                status="complete",
                record_count=3,
            ),
            InventoryCoverage(
                kind="inventory_coverage",
                fact_kind=FactKind.TEST_ASSET,
                status="complete",
                record_count=0,
            ),
        ),
        records=records,
    )


def test_inventory_contract_has_exact_independent_coordinates():
    request = InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=_policy(),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=256,
            cursor=None,
        ),
    )

    assert INVENTORY_VERSION == "1.0.0"
    assert INVENTORY_REQUEST_SCHEMA_URI.endswith(":1.0.0")
    assert INVENTORY_PAGE_SCHEMA_URI.endswith(":1.0.0")
    assert INVENTORY_SCHEMA_URI.endswith(":1.0.0")
    assert request.fact_kinds == tuple(FactKind)


def test_inventory_snapshot_round_trips_as_strict_canonical_json():
    snapshot = _snapshot()
    encoded = canonical_inventory_json(snapshot)

    assert encoded.endswith(b"\n")
    assert not encoded.endswith(b"\n\n")
    assert parse_inventory_snapshot_json(encoded) == snapshot
    assert canonical_inventory_json(parse_inventory_snapshot_json(encoded)) == (
        encoded
    )

    duplicate = encoded.replace(
        b'"kind":"inventory_snapshot"',
        b'"kind":"inventory_snapshot","kind":"inventory_snapshot"',
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_inventory_snapshot_json(duplicate)

    unknown = snapshot.model_dump(mode="json")
    unknown["future"] = True
    with pytest.raises(ValidationError):
        InventorySnapshot.model_validate_json(json.dumps(unknown))

    incompatible = snapshot.model_dump(mode="json")
    incompatible["inventory_version"] = "1.0.1"
    with pytest.raises(ValidationError):
        InventorySnapshot.model_validate_json(json.dumps(incompatible))


def test_inventory_request_rejects_ambiguous_policy_and_fact_sets():
    request = InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=_policy(),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=256,
            cursor=None,
        ),
    )
    payload = request.model_dump(mode="json")
    payload["fact_kinds"].reverse()
    with pytest.raises(ValidationError, match="fact kinds"):
        InventoryRequest.model_validate_json(json.dumps(payload))

    policy = _policy().model_dump(mode="json")
    policy["rules"].append(policy["rules"][0])
    with pytest.raises(ValidationError, match="rule IDs"):
        IgnorePolicy.model_validate_json(json.dumps(policy))


def test_snapshot_rejects_duplicate_paths_broken_refs_and_bad_coverage():
    snapshot = _snapshot()
    payload = snapshot.model_dump(mode="json")
    duplicate = payload["records"][-1].copy()
    duplicate["id"] = f"entry.{_EIGHT}"
    duplicate["path"] = "SRC/SERVICE.PY"
    _reidentify_payload(duplicate)
    payload["records"].append(duplicate)
    payload["records"].sort(key=lambda item: (item["kind"], item["id"]))
    payload["coverage"][3]["record_count"] = 4
    with pytest.raises(ValidationError, match="path"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    payload = snapshot.model_dump(mode="json")
    public = next(
        item for item in payload["records"] if item["kind"] == "public_interface"
    )
    public["entry"]["target_id"] = f"entry.{_EIGHT}"
    _reidentify_payload(public)
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="reference"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    payload = snapshot.model_dump(mode="json")
    payload["coverage"][2]["record_count"] = 0
    with pytest.raises(ValidationError, match="coverage"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_result_models_reject_noncanonical_confidence_and_fact_shape():
    with pytest.raises(ValidationError):
        InventoryConfidence(
            kind="confidence",
            scale="decimal-0-to-1",
            value="0.50",
            basis="urn:ucf:inventory-procedure:test:1.0.0",
        )


def test_snapshot_rejects_missing_parent_and_fact_below_ignored_root():
    snapshot = _snapshot()
    payload = snapshot.model_dump(mode="json")
    payload["records"] = [
        record
        for record in payload["records"]
        if not (
            record["kind"] == "repository_entry"
            and record["path"] == "src"
        )
    ]
    payload["coverage"][3]["record_count"] = 2
    with pytest.raises(ValidationError, match="parent"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    ignored_provenance = _identified(
        InventoryProvenance(
            kind="inventory_provenance",
            id=f"provenance.{_ZERO}",
            source_path="vendor",
            content_digest=None,
            source_span=None,
            producer=_producer(),
            procedure_uri=(
                "urn:ucf:inventory-procedure:fixture-entry:1.0.0"
            ),
        )
    )
    payload = snapshot.model_dump(mode="json")
    payload["records"].append(ignored_provenance.model_dump(mode="json"))
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="ignored"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_snapshot_rejects_directory_fact_refs_and_semantic_duplicates():
    snapshot = _snapshot()
    payload = snapshot.model_dump(mode="json")
    public = next(
        record
        for record in payload["records"]
        if record["kind"] == "public_interface"
    )
    source_entry = next(
        record
        for record in payload["records"]
        if record["kind"] == "repository_entry"
        and record["path"] == "src"
    )
    source_provenance = next(
        record
        for record in payload["records"]
        if record["kind"] == "inventory_provenance"
        and record["source_path"] == "src"
    )
    public["entry"]["target_id"] = source_entry["id"]
    public["provenance"]["target_id"] = source_provenance["id"]
    _reidentify_payload(public)
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="file"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    payload = snapshot.model_dump(mode="json")
    public = next(
        record
        for record in payload["records"]
        if record["kind"] == "public_interface"
    )
    duplicate = {**public, "id": f"interface.{_EIGHT}"}
    _reidentify_payload(duplicate)
    payload["records"].append(duplicate)
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    payload["coverage"][2]["record_count"] = 2
    with pytest.raises(ValidationError, match="record IDs"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "fact_kind",
    [
        FactKind.API_DESCRIPTION,
        FactKind.BUILD_MANIFEST,
        FactKind.PUBLIC_INTERFACE,
        FactKind.TEST_ASSET,
    ],
)
def test_snapshot_rejects_duplicate_claim_with_different_confidence(
    fact_kind: FactKind,
):
    snapshot = _snapshot()
    file_entry = next(
        record
        for record in snapshot.records
        if isinstance(record, RepositoryEntryFact)
        and record.path == "src/service.py"
    )
    file_provenance = next(
        record
        for record in snapshot.records
        if isinstance(record, InventoryProvenance)
        and record.source_path == "src/service.py"
    )
    if fact_kind is FactKind.PUBLIC_INTERFACE:
        fact = next(
            record
            for record in snapshot.records
            if isinstance(record, PublicInterfaceFact)
        )
    elif fact_kind is FactKind.BUILD_MANIFEST:
        fact = _identified(
            BuildManifestFact(
                kind="build_manifest",
                id=f"manifest.{_ZERO}",
                level="observed",
                provenance=_ref(
                    "inventory_provenance",
                    file_provenance.id,
                ),
                confidence=_confidence(),
                entry=_ref("repository_entry", file_entry.id),
                dialect_uri="urn:ucf:build:fixture:1.0.0",
            )
        )
    elif fact_kind is FactKind.TEST_ASSET:
        fact = _identified(
            InventoryTestAssetFact(
                kind="test_asset",
                id=f"test.{_ZERO}",
                level="observed",
                provenance=_ref(
                    "inventory_provenance",
                    file_provenance.id,
                ),
                confidence=_confidence(),
                entry=_ref("repository_entry", file_entry.id),
                test_kind_uri="urn:ucf:test:fixture:1.0.0",
                name="test_shorten",
            )
        )
    else:
        fact = _identified(
            ApiDescriptionFact(
                kind="api_description",
                id=f"api.{_ZERO}",
                level="observed",
                provenance=_ref(
                    "inventory_provenance",
                    file_provenance.id,
                ),
                confidence=_confidence(),
                entry=_ref("repository_entry", file_entry.id),
                dialect_uri="urn:ucf:api:fixture:1.0.0",
                declared_version="1.0.0",
            )
        )

    payload = snapshot.model_dump(mode="json")
    if fact_kind is not FactKind.PUBLIC_INTERFACE:
        payload["records"].append(fact.model_dump(mode="json"))
        coverage = next(
            item
            for item in payload["coverage"]
            if item["fact_kind"] == fact_kind.value
        )
        coverage["record_count"] = 1
    duplicate = fact.model_dump(mode="json")
    duplicate["confidence"]["value"] = "0.5"
    _reidentify_payload(duplicate)
    payload["records"].append(duplicate)
    coverage = next(
        item
        for item in payload["coverage"]
        if item["fact_kind"] == fact_kind.value
    )
    coverage["record_count"] = 2
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))

    with pytest.raises(ValidationError, match="semantic"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_snapshot_rejects_false_duplicate_and_uncovered_ignore_evidence():
    snapshot = _snapshot()
    unmatched = _identified(
        InventoryIgnoreMatch(
            kind="inventory_ignore_match",
            id=f"ignore.{_ZERO}",
            rule_id="ignore.vendor",
            path="src",
        )
    ).model_dump(mode="json")
    payload = snapshot.model_dump(mode="json")
    payload["records"].append(unmatched)
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="match"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    matched = {
        **unmatched,
        "path": "vendor",
    }
    _reidentify_payload(matched)
    duplicate = dict(matched)
    payload = snapshot.model_dump(mode="json")
    payload["records"].extend((matched, duplicate))
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="record IDs"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    diagnostic = _identified(
        InventoryDiagnostic(
            kind="inventory_diagnostic",
            id=f"diagnostic.{_ZERO}",
            severity="error",
            code="org.ucf.inventory.source-changed",
            fact_kind=None,
            path=".",
            stage="scan",
            message="source changed during inventory",
            provenance=None,
        )
    ).model_dump(mode="json")
    payload = snapshot.model_dump(mode="json")
    payload["records"].append(diagnostic)
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="coverage"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_ignore_policy_rejects_root_and_snapshot_rejects_overlap_evidence():
    with pytest.raises(ValidationError, match="root"):
        PathPrefixMatcher(kind="path_prefix", path=".")

    policy = IgnorePolicy(
        kind="ignore_policy",
        policy_version="1.0.0",
        rules=(
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.prefix",
                reason="org.ucf.inventory.vendor",
                matcher=PathPrefixMatcher(
                    kind="path_prefix",
                    path="vendor",
                ),
            ),
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.segment",
                reason="org.ucf.inventory.vendor",
                matcher=PathSegmentMatcher(
                    kind="path_segment",
                    segment="vendor",
                ),
            ),
        ),
    )
    matches = tuple(
        _identified(
            InventoryIgnoreMatch(
                kind="inventory_ignore_match",
                id=f"ignore.{_ZERO}",
                rule_id=rule.id,
                path="vendor",
            )
        )
        for rule in policy.rules
    )
    payload = _snapshot().model_dump(mode="json")
    payload["applied_policy"] = policy.model_dump(mode="json")
    payload["records"].extend(
        match.model_dump(mode="json") for match in matches
    )
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))

    with pytest.raises(ValidationError, match="pruned path"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "paths",
    [
        ("vendor", "vendor/child"),
        ("vendor/child",),
        ("missing/vendor",),
    ],
)
def test_ignore_matches_are_topology_bound_minimal_pruned_roots(
    paths: tuple[str, ...],
):
    matches = tuple(
        _identified(
            InventoryIgnoreMatch(
                kind="inventory_ignore_match",
                id=f"ignore.{_ZERO}",
                rule_id="ignore.vendor",
                path=path,
            )
        )
        for path in paths
    )
    payload = _snapshot().model_dump(mode="json")
    payload["records"].extend(
        match.model_dump(mode="json") for match in matches
    )
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))

    with pytest.raises(ValidationError, match="pruned path"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_ignore_match_paths_share_the_repository_portable_identity():
    policy = IgnorePolicy(
        kind="ignore_policy",
        policy_version="1.0.0",
        rules=(
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.upper",
                reason="org.ucf.inventory.vendor",
                matcher=PathPrefixMatcher(
                    kind="path_prefix",
                    path="Vendor",
                ),
            ),
            IgnoreRule(
                kind="ignore_rule",
                id="ignore.vendor",
                reason="org.ucf.inventory.vendor",
                matcher=PathSegmentMatcher(
                    kind="path_segment",
                    segment="vendor",
                ),
            ),
        ),
    )
    matches = tuple(
        _identified(
            InventoryIgnoreMatch(
                kind="inventory_ignore_match",
                id=f"ignore.{_ZERO}",
                rule_id=rule.id,
                path=path,
            )
        )
        for rule, path in zip(
            policy.rules,
            ("Vendor", "vendor"),
            strict=True,
        )
    )
    payload = _snapshot().model_dump(mode="json")
    payload["applied_policy"] = policy.model_dump(mode="json")
    payload["records"].extend(
        match.model_dump(mode="json") for match in matches
    )
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))

    with pytest.raises(ValidationError, match="path identity"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_snapshot_rejects_forged_record_identity_and_source_revision():
    payload = _snapshot().model_dump(mode="json")
    public = next(
        record
        for record in payload["records"]
        if record["kind"] == "public_interface"
    )
    public["id"] = f"interface.{_EIGHT}"
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="semantic identity"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    payload = _snapshot().model_dump(mode="json")
    payload["source_revision"]["value"] = _EIGHT
    with pytest.raises(ValidationError, match="source revision"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_snapshot_rejects_provenance_digest_that_disagrees_with_file():
    payload = _snapshot().model_dump(mode="json")
    provenance = next(
        record
        for record in payload["records"]
        if record["kind"] == "inventory_provenance"
        and record["source_path"] == "src/service.py"
    )
    provenance["content_digest"]["value"] = _EIGHT
    old_provenance_id, new_provenance_id = _reidentify_payload(provenance)
    entry = next(
        record
        for record in payload["records"]
        if record["kind"] == "repository_entry"
        and record["path"] == "src/service.py"
    )
    public = next(
        record
        for record in payload["records"]
        if record["kind"] == "public_interface"
    )
    entry["provenance"]["target_id"] = new_provenance_id
    old_entry_id, new_entry_id = _reidentify_payload(entry)
    public["provenance"]["target_id"] = new_provenance_id
    public["entry"]["target_id"] = new_entry_id
    _reidentify_payload(public)
    assert old_provenance_id != new_provenance_id
    assert old_entry_id != new_entry_id
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))

    with pytest.raises(ValidationError, match="digest"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_incomplete_repository_evidence_changes_source_revision():
    snapshot = _snapshot()
    diagnostic = _identified(
        InventoryDiagnostic(
            kind="inventory_diagnostic",
            id=f"diagnostic.{_ZERO}",
            severity="error",
            code="org.ucf.inventory.source-changed",
            fact_kind=None,
            path=".",
            stage="scan",
            message="source changed during inventory",
            provenance=None,
        )
    )
    payload = snapshot.model_dump(mode="json")
    payload["records"].append(diagnostic.model_dump(mode="json"))
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    for coverage in payload["coverage"]:
        coverage["status"] = "partial"

    with pytest.raises(ValidationError, match="source revision"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_diagnostic_provenance_path_and_procedure_versions_are_exact():
    snapshot = _snapshot()
    file_provenance = next(
        record
        for record in snapshot.records
        if isinstance(record, InventoryProvenance)
        and record.source_path == "src/service.py"
    )
    diagnostic = _identified(
        InventoryDiagnostic(
            kind="inventory_diagnostic",
            id=f"diagnostic.{_ZERO}",
            severity="info",
            code="org.ucf.inventory.observation",
            fact_kind=FactKind.PUBLIC_INTERFACE,
            path="src",
            stage="classify",
            message="classification observation",
            provenance=_ref(
                "inventory_provenance",
                file_provenance.id,
            ),
        )
    )
    payload = snapshot.model_dump(mode="json")
    payload["records"].append(diagnostic.model_dump(mode="json"))
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="path"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    provenance = file_provenance.model_dump(mode="json")
    provenance["procedure_uri"] = "urn:ucf:inventory-procedure:fixture"
    with pytest.raises(ValidationError, match="version"):
        InventoryProvenance.model_validate_json(json.dumps(provenance))

    confidence = _confidence().model_dump(mode="json")
    confidence["basis"] = "urn:ucf:inventory-procedure:fixture"
    with pytest.raises(ValidationError, match="version"):
        InventoryConfidence.model_validate_json(json.dumps(confidence))


def test_snapshot_rejects_orphan_provenance_and_duplicate_diagnostics():
    orphan = _identified(
        InventoryProvenance(
            kind="inventory_provenance",
            id=f"provenance.{_ZERO}",
            source_path="orphan.py",
            content_digest=None,
            source_span=None,
            producer=_producer(),
            procedure_uri=(
                "urn:ucf:inventory-procedure:fixture-entry:1.0.0"
            ),
        )
    )
    payload = _snapshot().model_dump(mode="json")
    payload["records"].append(orphan.model_dump(mode="json"))
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="orphan provenance"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    diagnostics = tuple(
        _identified(
            InventoryDiagnostic(
                kind="inventory_diagnostic",
                id=f"diagnostic.{_ZERO}",
                severity="info",
                code="org.ucf.inventory.observation",
                fact_kind=FactKind.PUBLIC_INTERFACE,
                path=".",
                stage="classify",
                message=message,
                provenance=None,
            )
        )
        for message in ("first observation", "second observation")
    )
    payload = _snapshot().model_dump(mode="json")
    payload["records"].extend(
        diagnostic.model_dump(mode="json")
        for diagnostic in diagnostics
    )
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))
    with pytest.raises(ValidationError, match="diagnostic semantic"):
        InventorySnapshot.model_validate_json(json.dumps(payload))


def test_subject_uri_cannot_expose_a_local_file_coordinate():
    request = InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=_policy(),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=1,
            cursor=None,
        ),
    )
    payload = request.model_dump(mode="json")
    payload["subject_uri"] = "file:///tmp/private-repository"

    with pytest.raises(ValidationError, match="subject URI"):
        InventoryRequest.model_validate_json(json.dumps(payload))


def test_repository_entry_provenance_cannot_claim_a_source_span():
    payload = _snapshot().model_dump(mode="json")
    file_provenance = next(
        record
        for record in payload["records"]
        if record["kind"] == "inventory_provenance"
        and record["source_path"] == "src/service.py"
    )
    file_provenance["source_span"] = SourceSpan(
        kind="source_span",
        start_line=1,
        start_column=1,
        end_line=1,
        end_column=1,
    ).model_dump(mode="json")
    old_provenance_id, new_provenance_id = _reidentify_payload(
        file_provenance
    )
    file_entry = next(
        record
        for record in payload["records"]
        if record["kind"] == "repository_entry"
        and record["path"] == "src/service.py"
    )
    public = next(
        record
        for record in payload["records"]
        if record["kind"] == "public_interface"
    )
    assert file_entry["provenance"]["target_id"] == old_provenance_id
    file_entry["provenance"]["target_id"] = new_provenance_id
    old_entry_id, new_entry_id = _reidentify_payload(file_entry)
    public["provenance"]["target_id"] = new_provenance_id
    assert public["entry"]["target_id"] == old_entry_id
    public["entry"]["target_id"] = new_entry_id
    _reidentify_payload(public)
    payload["records"].sort(key=lambda record: (record["kind"], record["id"]))

    with pytest.raises(ValidationError, match="source span"):
        InventorySnapshot.model_validate_json(json.dumps(payload))

    provenance = next(
        record
        for record in _snapshot().model_dump(mode="json")["records"]
        if record["kind"] == "inventory_provenance"
        and record["source_path"] == "."
    )
    provenance["source_span"] = SourceSpan(
        kind="source_span",
        start_line=1,
        start_column=1,
        end_line=1,
        end_column=1,
    ).model_dump(mode="json")
    provenance["id"] = f"provenance.{_ZERO}"
    with pytest.raises(ValidationError, match="content digest"):
        InventoryProvenance.model_validate_json(json.dumps(provenance))


@pytest.mark.parametrize(
    "path",
    [
        "C:/source.py",
        "CON",
        "src/name.",
        "src/name ",
        "src/\x01name",
        'src/a"name.py',
        "src/a<name.py",
        "src/a>name.py",
        "src/a|name.py",
        "src/a?name.py",
        "src/a*name.py",
    ],
)
def test_repository_path_rejects_nonportable_or_control_names(path: str):
    payload = _snapshot().records[-1].model_dump(mode="json")
    payload["path"] = path

    with pytest.raises(ValidationError, match="path"):
        RepositoryEntryFact.model_validate_json(json.dumps(payload))


def test_request_public_parser_rejects_duplicate_raw_json_members():
    request = InventoryRequest(
        kind="inventory_request_profile",
        inventory_version=INVENTORY_VERSION,
        schema_uri=INVENTORY_REQUEST_SCHEMA_URI,
        subject_uri="urn:ucf:repository:fixture",
        root_path=".",
        fact_kinds=tuple(FactKind),
        ignore_policy=_policy(),
        page=InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=256,
            cursor=None,
        ),
    )
    encoded = canonical_inventory_json(request)
    duplicate = encoded.replace(
        b'"kind":"inventory_request_profile"',
        (
            b'"kind":"inventory_request_profile",'
            b'"kind":"inventory_request_profile"'
        ),
        1,
    )

    with pytest.raises(ValueError, match="duplicate"):
        parse_inventory_request_json(duplicate)

    with pytest.raises(ValidationError):
        BuildManifestFact.model_validate_json(
            json.dumps(
                {
                "kind": "build_manifest",
                "id": f"manifest.{_ZERO}",
                "level": "observed",
                "provenance": _ref(
                    "inventory_provenance",
                    f"provenance.{_ONE}",
                ).model_dump(mode="json"),
                "confidence": _confidence().model_dump(mode="json"),
                "entry": _ref(
                    "repository_entry",
                    f"entry.{_TWO}",
                ).model_dump(mode="json"),
                "dialect_uri": "urn:ucf:build:fixture:1.0.0",
                "future": True,
                }
            )
        )
