from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ucf.adapter_protocol import (
    MAX_REQUESTS_PER_SESSION,
    CapabilitySelection,
)
from ucf.ir.models import (
    URI,
    Digest,
    Identifier,
    IRModel,
    Producer,
    QualifiedName,
    SafeInteger,
    SemanticToken,
)

INVENTORY_VERSION = "1.0.0"
INVENTORY_CAPABILITY = "org.ucf.adapter.inventory"
INVENTORY_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:inventory-request:1.0.0"
)
INVENTORY_PAGE_SCHEMA_URI = "urn:ucf:adapter:inventory-page:1.0.0"
INVENTORY_SCHEMA_URI = "urn:ucf:schema:inventory:1.0.0"
PATH_IDENTITY = "unicode-nfc-ascii-casefold-1"
IGNORE_POLICY_VERSION = "1.0.0"
MAX_IGNORE_RULES = 256
MAX_INVENTORY_DIAGNOSTICS = 10_000
MAX_INVENTORY_PAGES = MAX_REQUESTS_PER_SESSION - 2
MAX_INVENTORY_RECORDS = MAX_INVENTORY_PAGES
MAX_PAGE_RECORDS = 256

_CONFIDENCE_PATTERN = re.compile(r"^(?:0|1|0\.[0-9]*[1-9])$")
_VERSIONED_URI_PATTERN = re.compile(
    r"(?:[:/])(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
_VERSIONED_URI_JSON_SCHEMA = {
    "pattern": _VERSIONED_URI_PATTERN.pattern,
}
_INVENTORY_CAPABILITY_JSON_SCHEMA = {
    "properties": {
        "name": {"const": INVENTORY_CAPABILITY},
        "version": {"const": INVENTORY_VERSION},
    }
}
_RECORD_ID_PATTERN = (
    r"^(?:api|diagnostic|entry|ignore|interface|manifest|provenance|test)"
    r"\.[0-9a-f]{64}$"
)
_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "AUX",
        "CON",
        "NUL",
        "PRN",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)
_WINDOWS_RESERVED_SCHEMA_PATTERN = (
    r"(?:[Aa][Uu][Xx]|[Cc][Oo][Nn]|[Nn][Uu][Ll]|[Pp][Rr][Nn]|"
    r"[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])"
)
_PORTABLE_SEGMENT_SCHEMA_PATTERN = (
    rf"(?!(?:{_WINDOWS_RESERVED_SCHEMA_PATTERN})(?:\.|$))"
    r'[^/\\:<>"|?*\u0000-\u001f\u007f]*'
    r'[^/\\:<>"|?*\u0000-\u001f\u007f .]'
)
_REPOSITORY_PATH_SCHEMA_PATTERN = (
    rf"^(?:\.|{_PORTABLE_SEGMENT_SCHEMA_PATTERN}"
    rf"(?:/{_PORTABLE_SEGMENT_SCHEMA_PATTERN})*)$"
)
_PATH_SEGMENT_SCHEMA_PATTERN = (
    rf"^{_PORTABLE_SEGMENT_SCHEMA_PATTERN}$"
)
_PORTABLE_PATH_ALGORITHM = (
    "urn:ucf:inventory-algorithm:portable-path:1.0.0"
)
_SOURCE_SPAN_ORDER_ALGORITHM = (
    "urn:ucf:inventory-algorithm:source-span-order:1.0.0"
)
_SOURCE_SPAN_SCHEMA = {
    "x-ucf-validation-algorithm": _SOURCE_SPAN_ORDER_ALGORITHM,
}
_PROVENANCE_COORDINATE_SCHEMA = {
    "allOf": [
        {
            "if": {
                "properties": {
                    "source_span": {"not": {"type": "null"}}
                },
                "required": ["source_span"],
            },
            "then": {
                "properties": {
                    "content_digest": {"not": {"type": "null"}}
                }
            },
        }
    ]
}
_ENTRY_COORDINATE_SCHEMA = {
    "allOf": [
        {
            "if": {
                "properties": {"entry_kind": {"const": "directory"}},
                "required": ["entry_kind"],
            },
            "then": {
                "properties": {
                    "size_bytes": {"type": "null"},
                    "content_digest": {"type": "null"},
                    "symlink_target_digest": {"type": "null"},
                }
            },
        },
        {
            "if": {
                "properties": {"entry_kind": {"const": "file"}},
                "required": ["entry_kind"],
            },
            "then": {
                "properties": {
                    "size_bytes": {"type": "integer"},
                    "content_digest": {"not": {"type": "null"}},
                    "symlink_target_digest": {"type": "null"},
                }
            },
        },
        {
            "if": {
                "properties": {"entry_kind": {"const": "symlink"}},
                "required": ["entry_kind"],
            },
            "then": {
                "properties": {
                    "size_bytes": {"type": "null"},
                    "content_digest": {"type": "null"},
                    "symlink_target_digest": {
                        "not": {"type": "null"}
                    },
                }
            },
        },
    ]
}


def validate_repository_path(value: str) -> str:
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\0" in value
        or "//" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError("repository path is not normalized")
    if value == ".":
        return value
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("repository path is not normalized")
    if str(path) != value:
        raise ValueError("repository path is not normalized")
    for part in path.parts:
        _validate_portable_path_segment(part)
    return value


def validate_path_segment(value: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\0" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError("path segment is not normalized")
    _validate_portable_path_segment(value)
    return value


def _validate_portable_path_segment(value: str) -> None:
    if (
        len(value) > 255
        or ":" in value
        or any(character in '<>"|?*' for character in value)
        or value.endswith((" ", "."))
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("path segment is not portable")
    basename = value.partition(".")[0].upper()
    if basename in _WINDOWS_RESERVED_BASENAMES:
        raise ValueError("path segment is not portable")


def _validate_subject_uri(value: str) -> str:
    if value.partition(":")[0] == "file":
        raise ValueError("inventory subject URI cannot be a local file URI")
    return value


type RepositoryPath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=1024),
    AfterValidator(validate_repository_path),
    Field(
        json_schema_extra={
            "pattern": _REPOSITORY_PATH_SCHEMA_PATTERN,
            "x-ucf-normalization": "unicode-nfc",
            "x-ucf-validation-algorithm": _PORTABLE_PATH_ALGORITHM,
        }
    ),
]
type PathSegment = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255),
    AfterValidator(validate_path_segment),
    Field(
        json_schema_extra={
            "pattern": _PATH_SEGMENT_SCHEMA_PATTERN,
            "x-ucf-normalization": "unicode-nfc",
            "x-ucf-validation-algorithm": _PORTABLE_PATH_ALGORITHM,
        }
    ),
]
type InventoryRecordId = Annotated[
    str,
    StringConstraints(pattern=_RECORD_ID_PATTERN),
]
type ConfidenceValue = Annotated[
    str,
    StringConstraints(max_length=64, pattern=_CONFIDENCE_PATTERN.pattern),
]
type InventorySubjectURI = Annotated[
    URI,
    AfterValidator(_validate_subject_uri),
    Field(json_schema_extra={"not": {"pattern": "^file:"}}),
]


class FactKind(StrEnum):
    API_DESCRIPTION = "api_description"
    BUILD_MANIFEST = "build_manifest"
    PUBLIC_INTERFACE = "public_interface"
    REPOSITORY_ENTRY = "repository_entry"
    TEST_ASSET = "test_asset"


class InventoryRecordKind(StrEnum):
    API_DESCRIPTION = "api_description"
    BUILD_MANIFEST = "build_manifest"
    INVENTORY_DIAGNOSTIC = "inventory_diagnostic"
    INVENTORY_IGNORE_MATCH = "inventory_ignore_match"
    INVENTORY_PROVENANCE = "inventory_provenance"
    PUBLIC_INTERFACE = "public_interface"
    REPOSITORY_ENTRY = "repository_entry"
    TEST_ASSET = "test_asset"


_RECORD_PREFIX_BY_KIND = {
    InventoryRecordKind.API_DESCRIPTION: "api",
    InventoryRecordKind.BUILD_MANIFEST: "manifest",
    InventoryRecordKind.INVENTORY_DIAGNOSTIC: "diagnostic",
    InventoryRecordKind.INVENTORY_IGNORE_MATCH: "ignore",
    InventoryRecordKind.INVENTORY_PROVENANCE: "provenance",
    InventoryRecordKind.PUBLIC_INTERFACE: "interface",
    InventoryRecordKind.REPOSITORY_ENTRY: "entry",
    InventoryRecordKind.TEST_ASSET: "test",
}
_CURSOR_COORDINATE_SCHEMA = {
    "allOf": [
        {
            "if": {
                "properties": {
                    "after_kind": {"const": record_kind.value}
                },
                "required": ["after_kind"],
            },
            "then": {
                "properties": {
                    "after_id": {
                        "pattern": (
                            rf"^{prefix}\.[0-9a-f]{{64}}$"
                        )
                    }
                }
            },
        }
        for record_kind, prefix in _RECORD_PREFIX_BY_KIND.items()
    ],
    "x-ucf-validation-algorithm": (
        "urn:ucf:inventory-algorithm:cursor-coordinate:1.0.0"
    ),
}
_CANONICAL_FACT_KINDS_SCHEMA = {
    "prefixItems": [
        {"const": fact_kind.value} for fact_kind in FactKind
    ],
    "items": False,
    "minItems": len(FactKind),
    "maxItems": len(FactKind),
}
_IGNORE_RULES_SCHEMA = {
    "uniqueItems": True,
    "x-ucf-canonical-order-by": ["id"],
    "x-ucf-unique-by": [
        "id",
        "matcher.kind+portable-path-identity",
    ],
    "x-ucf-validation-algorithm": (
        "urn:ucf:inventory-algorithm:ignore-policy:1.0.0"
    ),
}


class PathPrefixMatcher(IRModel):
    kind: Literal["path_prefix"]
    path: RepositoryPath = Field(
        json_schema_extra={"not": {"const": "."}}
    )

    @field_validator("path")
    @classmethod
    def reject_root_prefix(cls, value: str) -> str:
        if value == ".":
            raise ValueError("ignore policy cannot exclude the repository root")
        return value


class PathSegmentMatcher(IRModel):
    kind: Literal["path_segment"]
    segment: PathSegment


type IgnoreMatcher = Annotated[
    PathPrefixMatcher | PathSegmentMatcher,
    Field(discriminator="kind"),
]


class IgnoreRule(IRModel):
    kind: Literal["ignore_rule"]
    id: Identifier
    reason: QualifiedName
    matcher: IgnoreMatcher


class IgnorePolicy(IRModel):
    kind: Literal["ignore_policy"]
    policy_version: Literal[IGNORE_POLICY_VERSION]
    rules: Annotated[
        tuple[IgnoreRule, ...],
        Field(
            max_length=MAX_IGNORE_RULES,
            json_schema_extra=_IGNORE_RULES_SCHEMA,
        ),
    ]

    @model_validator(mode="after")
    def validate_rules(self) -> IgnorePolicy:
        ids = tuple(rule.id for rule in self.rules)
        if len(ids) != len(set(ids)):
            raise ValueError("ignore policy rule IDs must be unique")
        if ids != tuple(sorted(ids)):
            raise ValueError("ignore policy rules must be sorted by ID")
        identities = tuple(
            (
                rule.matcher.kind,
                _portable_path_key(_matcher_value(rule.matcher)),
            )
            for rule in self.rules
        )
        if len(identities) != len(set(identities)):
            raise ValueError("ignore policy matchers must be unique")
        return self


class InventoryRecordRef(IRModel):
    kind: Literal["inventory_record_ref"]
    target_kind: InventoryRecordKind
    target_id: InventoryRecordId


class InventoryConfidence(IRModel):
    kind: Literal["confidence"]
    scale: Literal["decimal-0-to-1"]
    value: ConfidenceValue
    basis: URI = Field(json_schema_extra=_VERSIONED_URI_JSON_SCHEMA)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        if _CONFIDENCE_PATTERN.fullmatch(value) is None:
            raise ValueError("confidence value is not in canonical form")
        return value

    @field_validator("basis")
    @classmethod
    def validate_basis_version(cls, value: str) -> str:
        return _validate_versioned_uri(value)


class SourceSpan(IRModel):
    model_config = ConfigDict(json_schema_extra=_SOURCE_SPAN_SCHEMA)

    kind: Literal["source_span"]
    start_line: Annotated[SafeInteger, Field(ge=1)]
    start_column: Annotated[SafeInteger, Field(ge=1)]
    end_line: Annotated[SafeInteger, Field(ge=1)]
    end_column: Annotated[SafeInteger, Field(ge=1)]

    @model_validator(mode="after")
    def validate_order(self) -> SourceSpan:
        if (self.end_line, self.end_column) < (
            self.start_line,
            self.start_column,
        ):
            raise ValueError("source span end precedes its start")
        return self


class InventoryProvenance(IRModel):
    model_config = ConfigDict(
        json_schema_extra=_PROVENANCE_COORDINATE_SCHEMA
    )

    kind: Literal["inventory_provenance"]
    id: InventoryRecordId
    source_path: RepositoryPath
    content_digest: Digest | None
    source_span: SourceSpan | None
    producer: Producer
    procedure_uri: URI = Field(
        json_schema_extra=_VERSIONED_URI_JSON_SCHEMA
    )

    @field_validator("procedure_uri")
    @classmethod
    def validate_procedure_version(cls, value: str) -> str:
        return _validate_versioned_uri(value)

    @model_validator(mode="after")
    def validate_span_has_content(self) -> InventoryProvenance:
        if self.source_span is not None and self.content_digest is None:
            raise ValueError(
                "provenance source span requires a content digest"
            )
        return self


class InventoryFact(IRModel):
    id: InventoryRecordId
    level: Literal["observed"]
    provenance: InventoryRecordRef
    confidence: InventoryConfidence


class RepositoryEntryFact(InventoryFact):
    model_config = ConfigDict(json_schema_extra=_ENTRY_COORDINATE_SCHEMA)

    kind: Literal["repository_entry"]
    path: RepositoryPath
    entry_kind: Literal["directory", "file", "symlink"]
    size_bytes: Annotated[SafeInteger, Field(ge=0)] | None
    content_digest: Digest | None
    symlink_target_digest: Digest | None

    @model_validator(mode="after")
    def validate_entry_coordinates(self) -> RepositoryEntryFact:
        if self.entry_kind == "directory":
            if (
                self.size_bytes is not None
                or self.content_digest is not None
                or self.symlink_target_digest is not None
            ):
                raise ValueError(
                    "directory entry cannot contain file or symlink data"
                )
            return self
        if self.entry_kind == "file":
            if (
                self.size_bytes is None
                or self.content_digest is None
                or self.symlink_target_digest is not None
            ):
                raise ValueError("file entry has incompatible coordinates")
            return self
        if (
            self.size_bytes is not None
            or self.content_digest is not None
            or self.symlink_target_digest is None
        ):
            raise ValueError("symlink entry has incompatible coordinates")
        return self


class BuildManifestFact(InventoryFact):
    kind: Literal["build_manifest"]
    entry: InventoryRecordRef
    dialect_uri: URI


class PublicInterfaceFact(InventoryFact):
    kind: Literal["public_interface"]
    entry: InventoryRecordRef
    interface_kind_uri: URI
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    container: (
        Annotated[str, StringConstraints(min_length=1, max_length=255)]
        | None
    )
    declaration_digest: Digest


class TestAssetFact(InventoryFact):
    kind: Literal["test_asset"]
    entry: InventoryRecordRef
    test_kind_uri: URI
    name: (
        Annotated[str, StringConstraints(min_length=1, max_length=255)]
        | None
    )


class ApiDescriptionFact(InventoryFact):
    kind: Literal["api_description"]
    entry: InventoryRecordRef
    dialect_uri: URI
    declared_version: (
        Annotated[str, StringConstraints(min_length=1, max_length=255)]
        | None
    )


class InventoryDiagnostic(IRModel):
    kind: Literal["inventory_diagnostic"]
    id: InventoryRecordId
    severity: Literal["info", "warning", "error"]
    code: QualifiedName
    fact_kind: FactKind | None
    path: RepositoryPath | None
    stage: SemanticToken
    message: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    provenance: InventoryRecordRef | None


class InventoryIgnoreMatch(IRModel):
    kind: Literal["inventory_ignore_match"]
    id: InventoryRecordId
    rule_id: Identifier
    path: RepositoryPath


type InventoryRecord = Annotated[
    ApiDescriptionFact
    | BuildManifestFact
    | InventoryDiagnostic
    | InventoryIgnoreMatch
    | InventoryProvenance
    | PublicInterfaceFact
    | RepositoryEntryFact
    | TestAssetFact,
    Field(discriminator="kind"),
]


class InventoryCoverage(IRModel):
    kind: Literal["inventory_coverage"]
    fact_kind: FactKind
    status: Literal["complete", "partial"]
    record_count: Annotated[SafeInteger, Field(ge=0)]


class InventoryCursor(IRModel):
    model_config = ConfigDict(json_schema_extra=_CURSOR_COORDINATE_SCHEMA)

    kind: Literal["inventory_cursor"]
    snapshot_digest: Digest
    after_kind: InventoryRecordKind
    after_id: InventoryRecordId

    @model_validator(mode="after")
    def validate_cursor_coordinates(self) -> InventoryCursor:
        if not self.after_id.startswith(
            f"{_record_id_prefix(self.after_kind)}."
        ):
            raise ValueError(
                "inventory cursor kind does not match its record ID"
            )
        return self


class InventoryPageRequest(IRModel):
    kind: Literal["inventory_page_request"]
    record_limit: Annotated[
        SafeInteger,
        Field(ge=1, le=MAX_PAGE_RECORDS),
    ]
    cursor: InventoryCursor | None


class InventoryRequest(IRModel):
    kind: Literal["inventory_request_profile"]
    inventory_version: Literal[INVENTORY_VERSION]
    schema_uri: Literal[INVENTORY_REQUEST_SCHEMA_URI]
    subject_uri: InventorySubjectURI
    root_path: RepositoryPath
    fact_kinds: tuple[FactKind, ...] = Field(
        json_schema_extra=_CANONICAL_FACT_KINDS_SCHEMA
    )
    ignore_policy: IgnorePolicy
    page: InventoryPageRequest

    @model_validator(mode="after")
    def validate_fact_kinds(self) -> InventoryRequest:
        if self.fact_kinds != tuple(FactKind):
            raise ValueError(
                "inventory request fact kinds must be the exact canonical set"
            )
        return self


class InventorySnapshot(IRModel):
    kind: Literal["inventory_snapshot"]
    inventory_version: Literal[INVENTORY_VERSION]
    schema_uri: Literal[INVENTORY_SCHEMA_URI]
    subject_uri: InventorySubjectURI
    path_identity: Literal[PATH_IDENTITY]
    source_revision: Digest
    producer: Producer
    capability: CapabilitySelection = Field(
        json_schema_extra=_INVENTORY_CAPABILITY_JSON_SCHEMA
    )
    applied_policy: IgnorePolicy
    coverage: tuple[InventoryCoverage, ...]
    records: Annotated[
        tuple[InventoryRecord, ...],
        Field(max_length=MAX_INVENTORY_RECORDS),
    ]

    @model_validator(mode="after")
    def validate_snapshot(self) -> InventorySnapshot:
        _validate_snapshot_header(
            producer=self.producer,
            capability=self.capability,
            coverage=self.coverage,
            records=self.records,
        )
        _validate_records(
            records=self.records,
            coverage=self.coverage,
            producer=self.producer,
            policy=self.applied_policy,
            source_revision=self.source_revision,
        )
        return self


class InventoryPage(IRModel):
    kind: Literal["inventory_page"]
    inventory_version: Literal[INVENTORY_VERSION]
    schema_uri: Literal[INVENTORY_PAGE_SCHEMA_URI]
    subject_uri: InventorySubjectURI
    path_identity: Literal[PATH_IDENTITY]
    source_revision: Digest
    snapshot_digest: Digest
    producer: Producer
    capability: CapabilitySelection = Field(
        json_schema_extra=_INVENTORY_CAPABILITY_JSON_SCHEMA
    )
    applied_policy: IgnorePolicy
    coverage: tuple[InventoryCoverage, ...]
    request_cursor: InventoryCursor | None
    records: Annotated[
        tuple[InventoryRecord, ...],
        Field(min_length=1, max_length=MAX_PAGE_RECORDS),
    ]
    next_cursor: InventoryCursor | None
    complete: bool

    @model_validator(mode="after")
    def validate_page(self) -> InventoryPage:
        _validate_snapshot_header(
            producer=self.producer,
            capability=self.capability,
            coverage=self.coverage,
            records=None,
        )
        for record in self.records:
            _validate_record_id(record)
        keys = tuple(_record_key(record) for record in self.records)
        if len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
            raise ValueError(
                "inventory page records must be unique and canonically sorted"
            )
        if self.complete != (self.next_cursor is None):
            raise ValueError(
                "inventory page completion does not match its cursor"
            )
        if (
            self.request_cursor is not None
            and self.request_cursor.snapshot_digest != self.snapshot_digest
        ):
            raise ValueError(
                "inventory page request cursor has a different snapshot"
            )
        if (
            self.request_cursor is not None
            and keys[0]
            <= (
                self.request_cursor.after_kind.value,
                self.request_cursor.after_id,
            )
        ):
            raise ValueError(
                "inventory page does not advance beyond its request cursor"
            )
        if self.next_cursor is not None:
            last = self.records[-1]
            if (
                self.next_cursor.snapshot_digest != self.snapshot_digest
                or self.next_cursor.after_kind is not _record_kind(last)
                or self.next_cursor.after_id != last.id
            ):
                raise ValueError(
                    "inventory page cursor does not identify its last record"
                )
        return self


def _validate_snapshot_header(
    *,
    producer: Producer,
    capability: CapabilitySelection,
    coverage: tuple[InventoryCoverage, ...],
    records: tuple[InventoryRecord, ...] | None,
) -> None:
    del producer
    if (
        capability.name != INVENTORY_CAPABILITY
        or capability.version != INVENTORY_VERSION
    ):
        raise ValueError(
            "inventory snapshot capability coordinates are incompatible"
        )
    fact_kinds = tuple(item.fact_kind for item in coverage)
    if fact_kinds != tuple(FactKind):
        raise ValueError("inventory coverage must contain every fact kind")
    if records is None:
        return
    expected_counts = {
        fact_kind: sum(
            1
            for record in records
            if _fact_kind(record) is fact_kind
        )
        for fact_kind in FactKind
    }
    if any(
        item.record_count != expected_counts[item.fact_kind]
        for item in coverage
    ):
        raise ValueError("inventory coverage counts do not match records")
    errors = tuple(
        record
        for record in records
        if isinstance(record, InventoryDiagnostic)
        and record.severity == "error"
    )
    partial = (
        set(FactKind)
        if any(record.fact_kind is None for record in errors)
        else {
            record.fact_kind
            for record in errors
            if record.fact_kind is not None
        }
    )
    if any(
        (item.status == "partial") != (item.fact_kind in partial)
        for item in coverage
    ):
        raise ValueError(
            "inventory coverage status does not match error diagnostics"
        )


def _validate_records(
    *,
    records: tuple[InventoryRecord, ...],
    coverage: tuple[InventoryCoverage, ...],
    producer: Producer,
    policy: IgnorePolicy,
    source_revision: Digest,
) -> None:
    del coverage
    keys = tuple(_record_key(record) for record in records)
    ids = tuple(record.id for record in records)
    if len(ids) != len(set(ids)):
        raise ValueError("inventory record IDs must be unique")
    if keys != tuple(sorted(keys)):
        raise ValueError("inventory records must be canonically sorted")
    by_id = {record.id: record for record in records}
    ignored_rule_ids = {rule.id for rule in policy.rules}
    semantic_fact_identities: set[tuple[str, str]] = set()
    ignore_identities: set[str] = set()
    diagnostic_identities: set[str] = set()
    diagnostic_count = sum(
        isinstance(record, InventoryDiagnostic) for record in records
    )
    if diagnostic_count > MAX_INVENTORY_DIAGNOSTICS:
        raise ValueError(
            "inventory diagnostics exceed the profile limit"
        )
    for record in records:
        _validate_record_id(record)
        if isinstance(record, InventoryProvenance):
            if record.producer != producer:
                raise ValueError(
                    "inventory provenance producer differs from snapshot"
                )
            if _matching_rule_ids(policy, record.source_path):
                raise ValueError(
                    "inventory provenance records evidence below an ignored path"
                )
            continue
        if isinstance(record, InventoryFact):
            provenance = _resolve_ref(
                record.provenance,
                by_id,
                InventoryRecordKind.INVENTORY_PROVENANCE,
            )
            assert isinstance(provenance, InventoryProvenance)
            identity = _semantic_fact_identity(record)
            if identity in semantic_fact_identities:
                raise ValueError(
                    "inventory facts must have unique semantic identities"
                )
            semantic_fact_identities.add(identity)
            if isinstance(record, RepositoryEntryFact):
                if provenance.source_path != record.path:
                    raise ValueError(
                        "repository entry provenance path does not match"
                    )
                expected_digest = (
                    record.content_digest
                    if record.entry_kind == "file"
                    else record.symlink_target_digest
                    if record.entry_kind == "symlink"
                    else None
                )
                if provenance.content_digest != expected_digest:
                    raise ValueError(
                        "repository entry provenance digest does not match"
                    )
                if provenance.source_span is not None:
                    raise ValueError(
                        "repository entry provenance cannot have a source span"
                    )
                if _matching_rule_ids(policy, record.path):
                    raise ValueError(
                        "repository entry records evidence below an ignored path"
                    )
            else:
                entry = _resolve_ref(
                    record.entry,
                    by_id,
                    InventoryRecordKind.REPOSITORY_ENTRY,
                )
                assert isinstance(entry, RepositoryEntryFact)
                if entry.entry_kind != "file":
                    raise ValueError(
                        "inventory classification facts must reference a file"
                    )
                if provenance.source_path != entry.path:
                    raise ValueError(
                        "fact provenance path differs from its entry"
                    )
                if provenance.content_digest != entry.content_digest:
                    raise ValueError(
                        "fact provenance digest differs from its file entry"
                    )
            continue
        if isinstance(record, InventoryDiagnostic):
            identity = _diagnostic_identity(record)
            if identity in diagnostic_identities:
                raise ValueError(
                    "diagnostic semantic coordinates must be unique"
                )
            diagnostic_identities.add(identity)
            if (
                record.path is not None
                and _matching_rule_ids(policy, record.path)
            ):
                raise ValueError(
                    "inventory diagnostic records evidence below an ignored path"
                )
            if record.provenance is not None:
                provenance = _resolve_ref(
                    record.provenance,
                    by_id,
                    InventoryRecordKind.INVENTORY_PROVENANCE,
                )
                assert isinstance(provenance, InventoryProvenance)
                if (
                    record.path is None
                    or provenance.source_path != record.path
                ):
                    raise ValueError(
                        "diagnostic provenance path does not match"
                    )
            continue
        if isinstance(record, InventoryIgnoreMatch):
            if record.rule_id not in ignored_rule_ids:
                raise ValueError(
                    "ignore match references an unknown policy rule"
                )
            matching_rule_ids = _matching_rule_ids(policy, record.path)
            if record.rule_id not in matching_rule_ids:
                raise ValueError(
                    "ignore match path does not match its policy rule"
                )
            if record.rule_id != min(matching_rule_ids):
                raise ValueError(
                    "ignore match must use the canonical rule for its "
                    "pruned path"
                )
            identity = record.path
            if identity in ignore_identities:
                raise ValueError(
                    "each pruned path must have exactly one ignore match"
                )
            ignore_identities.add(identity)
    entries = tuple(
        record
        for record in records
        if isinstance(record, RepositoryEntryFact)
    )
    paths = tuple(entry.path for entry in entries)
    if len(paths) != len(set(paths)):
        raise ValueError("repository entry paths must be unique")
    portable = tuple(_portable_path_key(path) for path in paths)
    if len(portable) != len(set(portable)):
        raise ValueError("repository path identity collision")
    entries_by_path = {entry.path: entry for entry in entries}
    root = entries_by_path.get(".")
    if root is None or root.entry_kind != "directory":
        raise ValueError(
            "repository inventory must contain a root directory entry"
        )
    for entry in entries:
        if entry.path == ".":
            continue
        parent_path = str(PurePosixPath(entry.path).parent)
        parent = entries_by_path.get(parent_path)
        if parent is None or parent.entry_kind != "directory":
            raise ValueError(
                "repository entry parent must exist and be a directory"
            )
    ignore_matches = tuple(
        record
        for record in records
        if isinstance(record, InventoryIgnoreMatch)
    )
    ignore_portable_paths = tuple(
        _portable_path_key(match.path) for match in ignore_matches
    )
    if len(ignore_portable_paths) != len(set(ignore_portable_paths)):
        raise ValueError("ignore match path identity collision")
    for match in ignore_matches:
        prefixes = tuple(
            "/".join(PurePosixPath(match.path).parts[:index])
            for index in range(1, len(PurePosixPath(match.path).parts) + 1)
        )
        first_pruned = next(
            (
                prefix
                for prefix in prefixes
                if _matching_rule_ids(policy, prefix)
            ),
            None,
        )
        parent_path = str(PurePosixPath(match.path).parent)
        parent = entries_by_path.get(parent_path)
        if (
            first_pruned != match.path
            or parent is None
            or parent.entry_kind != "directory"
        ):
            raise ValueError(
                "ignore match is not a topology-bound minimal pruned path"
            )
    referenced_provenance = {
        record.provenance.target_id
        for record in records
        if isinstance(record, InventoryFact)
    } | {
        record.provenance.target_id
        for record in records
        if isinstance(record, InventoryDiagnostic)
        and record.provenance is not None
    }
    provenance_ids = {
        record.id
        for record in records
        if isinstance(record, InventoryProvenance)
    }
    if provenance_ids != referenced_provenance:
        raise ValueError("inventory contains orphan provenance")
    if source_revision != derive_inventory_source_revision(records):
        raise ValueError(
            "inventory source revision is not derived from repository entries"
        )


def _resolve_ref(
    reference: InventoryRecordRef,
    records: dict[str, InventoryRecord],
    expected: InventoryRecordKind,
) -> InventoryRecord:
    target = records.get(reference.target_id)
    if (
        target is None
        or reference.target_kind is not expected
        or _record_kind(target) is not expected
    ):
        raise ValueError("inventory reference is broken or has wrong kind")
    return target


def _validate_record_id(record: InventoryRecord) -> None:
    expected_prefix = _record_id_prefix(_record_kind(record))
    if not record.id.startswith(f"{expected_prefix}."):
        raise ValueError("inventory record ID prefix does not match its kind")
    if record.id != derive_inventory_record_id(record):
        raise ValueError(
            "inventory record ID is not derived from its semantic identity"
        )


def _record_id_prefix(kind: InventoryRecordKind) -> str:
    return _RECORD_PREFIX_BY_KIND[kind]


def _record_key(
    record: InventoryRecord,
) -> tuple[str, str]:
    return (_record_kind(record).value, record.id)


def _record_kind(record: InventoryRecord) -> InventoryRecordKind:
    return InventoryRecordKind(record.kind)


def _fact_kind(record: InventoryRecord) -> FactKind | None:
    if isinstance(record, RepositoryEntryFact):
        return FactKind.REPOSITORY_ENTRY
    if isinstance(record, PublicInterfaceFact):
        return FactKind.PUBLIC_INTERFACE
    if isinstance(record, BuildManifestFact):
        return FactKind.BUILD_MANIFEST
    if isinstance(record, TestAssetFact):
        return FactKind.TEST_ASSET
    if isinstance(record, ApiDescriptionFact):
        return FactKind.API_DESCRIPTION
    return None


def _portable_path_key(path: str) -> str:
    return "".join(
        character.lower()
        if "A" <= character <= "Z"
        else character
        for character in path
    )


def _matcher_value(matcher: IgnoreMatcher) -> str:
    if isinstance(matcher, PathPrefixMatcher):
        return matcher.path
    return matcher.segment


def _matching_rule_ids(policy: IgnorePolicy, path: str) -> frozenset[str]:
    parts = () if path == "." else PurePosixPath(path).parts
    matches = {
        rule.id
        for rule in policy.rules
        if (
            isinstance(rule.matcher, PathPrefixMatcher)
            and (
                rule.matcher.path == "."
                or path == rule.matcher.path
                or path.startswith(f"{rule.matcher.path}/")
            )
        )
        or (
            isinstance(rule.matcher, PathSegmentMatcher)
            and rule.matcher.segment in parts
        )
    }
    return frozenset(matches)


def _semantic_fact_identity(record: InventoryFact) -> tuple[str, str]:
    payload = record.model_dump(
        mode="json",
        exclude={"confidence", "id", "level", "provenance"},
    )
    return (
        record.kind,
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _diagnostic_identity(record: InventoryDiagnostic) -> str:
    payload = record.model_dump(
        mode="json",
        exclude={"id", "message"},
    )
    return json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def derive_inventory_record_id(record: InventoryRecord) -> str:
    payload = record.model_dump(mode="json", exclude={"id"})
    digest = hashlib.sha256(_canonical_identity_bytes(payload)).hexdigest()
    return f"{_record_id_prefix(_record_kind(record))}.{digest}"


def derive_inventory_source_revision(
    records: tuple[InventoryRecord, ...],
) -> Digest:
    entries = sorted(
        (
            {
                "content_digest": (
                    record.content_digest.model_dump(mode="json")
                    if record.content_digest is not None
                    else None
                ),
                "entry_kind": record.entry_kind,
                "path": record.path,
                "read_status": record.level,
                "size_bytes": record.size_bytes,
                "symlink_target_digest": (
                    record.symlink_target_digest.model_dump(mode="json")
                    if record.symlink_target_digest is not None
                    else None
                ),
            }
            for record in records
            if isinstance(record, RepositoryEntryFact)
        ),
        key=lambda item: item["path"].encode("utf-8"),
    )
    failures = sorted(
        (
            {
                "code": record.code,
                "fact_kind": (
                    record.fact_kind.value
                    if record.fact_kind is not None
                    else None
                ),
                "path": record.path,
                "severity": record.severity,
                "stage": record.stage,
            }
            for record in records
            if isinstance(record, InventoryDiagnostic)
            and record.severity == "error"
            and record.fact_kind
            in {None, FactKind.REPOSITORY_ENTRY}
        ),
        key=_canonical_identity_bytes,
    )
    projection = {"entries": entries, "failures": failures}
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            _canonical_identity_bytes(projection)
        ).hexdigest(),
    )


def _canonical_identity_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _validate_versioned_uri(value: str) -> str:
    if _VERSIONED_URI_PATTERN.search(value) is None:
        raise ValueError("inventory procedure URI must end with a version")
    return value
