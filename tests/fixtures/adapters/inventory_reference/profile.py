from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass

from .limits import MAX_CANONICAL_RECORDS
from .traversal import ScanResult

INVENTORY_VERSION = "1.0.0"
INVENTORY_CAPABILITY = "org.ucf.adapter.inventory"
INVENTORY_REQUEST_SCHEMA_URI = (
    "urn:ucf:adapter:inventory-request:1.0.0"
)
INVENTORY_PAGE_SCHEMA_URI = "urn:ucf:adapter:inventory-page:1.0.0"
INVENTORY_SCHEMA_URI = "urn:ucf:schema:inventory:1.0.0"
PATH_IDENTITY = "unicode-nfc-ascii-casefold-1"
PRODUCER = {
    "kind": "producer",
    "name": "org.ucf.inventory-reference-adapter",
    "version": "1.0.0",
}
CAPABILITY = {
    "kind": "capability",
    "name": INVENTORY_CAPABILITY,
    "version": INVENTORY_VERSION,
}
FACT_KINDS = (
    "api_description",
    "build_manifest",
    "public_interface",
    "repository_entry",
    "test_asset",
)
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_PROFILE_DEPTH = 128
MAX_PAGE_RECORDS = 256

_IDENTIFIER = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)
_QUALIFIED_NAME = re.compile(
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
    r"(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$"
)
_URI = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_RESERVED = frozenset(
    {
        "AUX",
        "CON",
        "NUL",
        "PRN",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)
_RECORD_PREFIX = {
    "api_description": "api",
    "build_manifest": "manifest",
    "inventory_diagnostic": "diagnostic",
    "inventory_ignore_match": "ignore",
    "inventory_provenance": "provenance",
    "public_interface": "interface",
    "repository_entry": "entry",
    "test_asset": "test",
}
_ENTRY_PROCEDURE = (
    "urn:ucf:inventory-procedure:reference-entry:1.0.0"
)
_CONFIDENCE_BASIS = (
    "urn:ucf:inventory-procedure:direct-observation:1.0.0"
)


class InvalidProfile(ValueError):
    pass


@dataclass(frozen=True)
class InventoryRun:
    snapshot: dict[str, object]
    snapshot_digest: str


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def decode_inventory_request(payload: object) -> dict[str, object]:
    document = _expect_dict(payload, "adapter payload")
    _exact_keys(
        document,
        {"kind", "schema_uri", "schema_version", "value"},
        "adapter payload",
    )
    if (
        document["kind"] != "adapter_payload"
        or document["schema_uri"] != INVENTORY_REQUEST_SCHEMA_URI
        or document["schema_version"] != INVENTORY_VERSION
    ):
        raise InvalidProfile("inventory payload coordinates are incompatible")
    logical = decode_tagged(document["value"])
    request = _expect_dict(logical, "inventory request")
    _exact_keys(
        request,
        {
            "kind",
            "inventory_version",
            "schema_uri",
            "subject_uri",
            "root_path",
            "fact_kinds",
            "ignore_policy",
            "page",
        },
        "inventory request",
    )
    if (
        request["kind"] != "inventory_request_profile"
        or request["inventory_version"] != INVENTORY_VERSION
        or request["schema_uri"] != INVENTORY_REQUEST_SCHEMA_URI
    ):
        raise InvalidProfile("inventory request coordinates are incompatible")
    _require_uri(request["subject_uri"], "subject URI")
    _validate_repository_path(request["root_path"])
    fact_kinds = _expect_list(request["fact_kinds"], "fact kinds")
    if tuple(fact_kinds) != FACT_KINDS:
        raise InvalidProfile("fact kinds must be the canonical complete set")
    request["ignore_policy"] = _validate_ignore_policy(
        request["ignore_policy"]
    )
    request["page"] = _validate_page_request(request["page"])
    return request


def encode_inventory_page_payload(
    page: dict[str, object],
    *,
    schema_uri: str = INVENTORY_PAGE_SCHEMA_URI,
) -> dict[str, object]:
    return {
        "kind": "adapter_payload",
        "schema_uri": schema_uri,
        "schema_version": INVENTORY_VERSION,
        "value": encode_tagged(page),
    }


def encode_tagged(value: object, *, depth: int = 0) -> dict[str, object]:
    _check_depth(depth)
    if value is None:
        return {"kind": "null"}
    if type(value) is bool:
        return {"kind": "boolean", "value": value}
    if type(value) is str:
        return {"kind": "string", "value": value}
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise InvalidProfile("integer is outside the exact range")
        return {"kind": "integer", "value": value}
    if type(value) is list or type(value) is tuple:
        return {
            "kind": "list",
            "items": [
                encode_tagged(item, depth=depth + 1) for item in value
            ],
        }
    if type(value) is dict:
        if any(
            type(name) is not str or _IDENTIFIER.fullmatch(name) is None
            for name in value
        ):
            raise InvalidProfile("record name is not an identifier")
        return {
            "kind": "record",
            "entries": [
                {
                    "kind": "record_entry",
                    "name": name,
                    "value": encode_tagged(value[name], depth=depth + 1),
                }
                for name in sorted(value)
            ],
        }
    raise InvalidProfile("unsupported tagged value")


def decode_tagged(value: object, *, depth: int = 0) -> object:
    _check_depth(depth)
    tagged = _expect_dict(value, "tagged value")
    kind = tagged.get("kind")
    if kind == "null":
        _exact_keys(tagged, {"kind"}, "null value")
        return None
    if kind == "boolean":
        _exact_keys(tagged, {"kind", "value"}, "boolean value")
        if type(tagged["value"]) is not bool:
            raise InvalidProfile("boolean value has wrong type")
        return tagged["value"]
    if kind == "string":
        _exact_keys(tagged, {"kind", "value"}, "string value")
        if type(tagged["value"]) is not str:
            raise InvalidProfile("string value has wrong type")
        return tagged["value"]
    if kind == "integer":
        _exact_keys(tagged, {"kind", "value"}, "integer value")
        number = tagged["value"]
        if (
            type(number) is not int
            or not -MAX_SAFE_INTEGER <= number <= MAX_SAFE_INTEGER
        ):
            raise InvalidProfile("integer value is outside the exact range")
        return number
    if kind == "list":
        _exact_keys(tagged, {"kind", "items"}, "list value")
        items = _expect_list(tagged["items"], "list items")
        return [
            decode_tagged(item, depth=depth + 1) for item in items
        ]
    if kind == "record":
        _exact_keys(tagged, {"kind", "entries"}, "record value")
        entries = _expect_list(tagged["entries"], "record entries")
        result: dict[str, object] = {}
        names: list[str] = []
        for item in entries:
            entry = _expect_dict(item, "record entry")
            _exact_keys(
                entry,
                {"kind", "name", "value"},
                "record entry",
            )
            name = entry["name"]
            if (
                entry["kind"] != "record_entry"
                or type(name) is not str
                or _IDENTIFIER.fullmatch(name) is None
            ):
                raise InvalidProfile("record entry is invalid")
            names.append(name)
            if name in result:
                raise InvalidProfile("record contains a duplicate name")
            result[name] = decode_tagged(
                entry["value"],
                depth=depth + 1,
            )
        if names != sorted(names):
            raise InvalidProfile("record names are not sorted")
        return result
    raise InvalidProfile("tagged value kind is unsupported")


def build_inventory_run(
    request: dict[str, object],
    scan: ScanResult,
) -> InventoryRun:
    records: list[dict[str, object]] = []
    provenance_by_path: dict[str, dict[str, object]] = {}
    entry_by_path: dict[str, dict[str, object]] = {}
    confidence = {
        "kind": "confidence",
        "scale": "decimal-0-to-1",
        "value": "1",
        "basis": _CONFIDENCE_BASIS,
    }
    for scanned in scan.entries:
        digest_value = (
            scanned.content_digest
            if scanned.entry_kind == "file"
            else scanned.symlink_target_digest
            if scanned.entry_kind == "symlink"
            else None
        )
        provenance = _identified(
            {
                "kind": "inventory_provenance",
                "source_path": scanned.path,
                "content_digest": (
                    _digest(digest_value)
                    if digest_value is not None
                    else None
                ),
                "source_span": None,
                "producer": PRODUCER,
                "procedure_uri": _ENTRY_PROCEDURE,
            }
        )
        provenance_by_path[scanned.path] = provenance
        records.append(provenance)
        entry = _identified(
            {
                "kind": "repository_entry",
                "level": "observed",
                "provenance": _reference(provenance),
                "confidence": confidence,
                "path": scanned.path,
                "entry_kind": scanned.entry_kind,
                "size_bytes": scanned.size_bytes,
                "content_digest": (
                    _digest(scanned.content_digest)
                    if scanned.content_digest is not None
                    else None
                ),
                "symlink_target_digest": (
                    _digest(scanned.symlink_target_digest)
                    if scanned.symlink_target_digest is not None
                    else None
                ),
            }
        )
        entry_by_path[scanned.path] = entry
        records.append(entry)

    for classified in scan.classifications:
        provenance = provenance_by_path[classified.path]
        entry = entry_by_path[classified.path]
        common = {
            "kind": classified.fact.kind,
            "level": "observed",
            "provenance": _reference(provenance),
            "confidence": confidence,
            "entry": _reference(entry),
        }
        records.append(
            _identified({**common, **classified.fact.attributes})
        )

    for ignored in scan.ignores:
        records.append(
            _identified(
                {
                    "kind": "inventory_ignore_match",
                    "rule_id": ignored.rule_id,
                    "path": ignored.path,
                }
            )
        )

    for diagnostic in scan.diagnostics:
        records.append(
            _identified(
                {
                    "kind": "inventory_diagnostic",
                    "severity": diagnostic.severity,
                    "code": diagnostic.code,
                    "fact_kind": diagnostic.fact_kind,
                    "path": diagnostic.path,
                    "stage": diagnostic.stage,
                    "message": diagnostic.message,
                    "provenance": None,
                }
            )
        )

    if len(records) > MAX_CANONICAL_RECORDS:
        raise InvalidProfile("inventory record limit was exceeded")
    records.sort(key=lambda item: (str(item["kind"]), str(item["id"])))
    coverage = _coverage(records)
    source_revision = derive_source_revision(records)
    snapshot: dict[str, object] = {
        "kind": "inventory_snapshot",
        "inventory_version": INVENTORY_VERSION,
        "schema_uri": INVENTORY_SCHEMA_URI,
        "subject_uri": request["subject_uri"],
        "path_identity": PATH_IDENTITY,
        "source_revision": _digest(source_revision),
        "producer": PRODUCER,
        "capability": CAPABILITY,
        "applied_policy": request["ignore_policy"],
        "coverage": coverage,
        "records": records,
    }
    snapshot_digest = hashlib.sha256(canonical_json(snapshot)).hexdigest()
    return InventoryRun(
        snapshot=snapshot,
        snapshot_digest=snapshot_digest,
    )


def build_inventory_page(
    request: dict[str, object],
    run: InventoryRun,
    *,
    record_limit: int | None = None,
) -> dict[str, object]:
    page_request = _expect_dict(request["page"], "page request")
    cursor = page_request["cursor"]
    records = run.snapshot["records"]
    assert isinstance(records, list)
    start = 0
    if cursor is not None:
        cursor_object = _expect_dict(cursor, "cursor")
        if cursor_object["snapshot_digest"]["value"] != run.snapshot_digest:
            raise InvalidProfile("inventory cursor snapshot is stale")
        coordinate = (
            cursor_object["after_kind"],
            cursor_object["after_id"],
        )
        for index, record in enumerate(records):
            if (record["kind"], record["id"]) == coordinate:
                start = index + 1
                break
        else:
            raise InvalidProfile("inventory cursor coordinate is unknown")
    if start >= len(records):
        raise InvalidProfile("inventory cursor is terminal")
    limit = (
        int(page_request["record_limit"])
        if record_limit is None
        else record_limit
    )
    selected = records[start : start + limit]
    terminal = start + len(selected) == len(records)
    next_cursor = None
    if not terminal:
        last = selected[-1]
        next_cursor = {
            "kind": "inventory_cursor",
            "snapshot_digest": _digest(run.snapshot_digest),
            "after_kind": last["kind"],
            "after_id": last["id"],
        }
    return {
        "kind": "inventory_page",
        "inventory_version": INVENTORY_VERSION,
        "schema_uri": INVENTORY_PAGE_SCHEMA_URI,
        "subject_uri": run.snapshot["subject_uri"],
        "path_identity": PATH_IDENTITY,
        "source_revision": run.snapshot["source_revision"],
        "snapshot_digest": _digest(run.snapshot_digest),
        "producer": PRODUCER,
        "capability": CAPABILITY,
        "applied_policy": run.snapshot["applied_policy"],
        "coverage": run.snapshot["coverage"],
        "request_cursor": cursor,
        "records": selected,
        "next_cursor": next_cursor,
        "complete": terminal,
    }


def derive_source_revision(records: list[dict[str, object]]) -> str:
    entries = sorted(
        (
            {
                "content_digest": record["content_digest"],
                "entry_kind": record["entry_kind"],
                "path": record["path"],
                "read_status": record["level"],
                "size_bytes": record["size_bytes"],
                "symlink_target_digest": record[
                    "symlink_target_digest"
                ],
            }
            for record in records
            if record["kind"] == "repository_entry"
        ),
        key=lambda item: str(item["path"]).encode("utf-8"),
    )
    failures = sorted(
        (
            {
                "code": record["code"],
                "fact_kind": record["fact_kind"],
                "path": record["path"],
                "severity": record["severity"],
                "stage": record["stage"],
            }
            for record in records
            if record["kind"] == "inventory_diagnostic"
            and record["severity"] == "error"
            and record["fact_kind"] in {None, "repository_entry"}
        ),
        key=lambda item: canonical_json(item),
    )
    projection = {"entries": entries, "failures": failures}
    return hashlib.sha256(canonical_json(projection)).hexdigest()


def _coverage(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    errors = [
        record
        for record in records
        if record["kind"] == "inventory_diagnostic"
        and record["severity"] == "error"
    ]
    all_partial = any(record["fact_kind"] is None for record in errors)
    partial = {
        record["fact_kind"]
        for record in errors
        if record["fact_kind"] is not None
    }
    return [
        {
            "kind": "inventory_coverage",
            "fact_kind": fact_kind,
            "status": (
                "partial"
                if all_partial or fact_kind in partial
                else "complete"
            ),
            "record_count": sum(
                record["kind"] == fact_kind for record in records
            ),
        }
        for fact_kind in FACT_KINDS
    ]


def _identified(record: dict[str, object]) -> dict[str, object]:
    identified = dict(record)
    digest = hashlib.sha256(canonical_json(identified)).hexdigest()
    prefix = _RECORD_PREFIX[str(record["kind"])]
    identified["id"] = f"{prefix}.{digest}"
    return identified


def _reference(record: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "inventory_record_ref",
        "target_kind": record["kind"],
        "target_id": record["id"],
    }


def _digest(value: str) -> dict[str, str]:
    if _DIGEST.fullmatch(value) is None:
        raise InvalidProfile("digest is not canonical")
    return {"kind": "digest", "algorithm": "sha-256", "value": value}


def _validate_ignore_policy(value: object) -> dict[str, object]:
    policy = _expect_dict(value, "ignore policy")
    _exact_keys(
        policy,
        {"kind", "policy_version", "rules"},
        "ignore policy",
    )
    if (
        policy["kind"] != "ignore_policy"
        or policy["policy_version"] != INVENTORY_VERSION
    ):
        raise InvalidProfile("ignore policy coordinates are incompatible")
    rules = _expect_list(policy["rules"], "ignore rules")
    if len(rules) > 256:
        raise InvalidProfile("ignore policy has too many rules")
    normalized: list[dict[str, object]] = []
    identities: set[tuple[str, str]] = set()
    ids: list[str] = []
    for value_rule in rules:
        rule = _expect_dict(value_rule, "ignore rule")
        _exact_keys(
            rule,
            {"kind", "id", "reason", "matcher"},
            "ignore rule",
        )
        if rule["kind"] != "ignore_rule":
            raise InvalidProfile("ignore rule kind is incompatible")
        _require_identifier(rule["id"], "ignore rule ID")
        _require_qualified_name(rule["reason"], "ignore reason")
        matcher = _expect_dict(rule["matcher"], "ignore matcher")
        if matcher.get("kind") == "path_segment":
            _exact_keys(
                matcher,
                {"kind", "segment"},
                "path segment matcher",
            )
            _validate_path_segment(matcher["segment"])
            identity = ("path_segment", str(matcher["segment"]))
        elif matcher.get("kind") == "path_prefix":
            _exact_keys(
                matcher,
                {"kind", "path"},
                "path prefix matcher",
            )
            _validate_repository_path(matcher["path"])
            if matcher["path"] == ".":
                raise InvalidProfile("root path-prefix ignore is unsupported")
            identity = ("path_prefix", str(matcher["path"]))
        else:
            raise InvalidProfile("ignore matcher kind is unsupported")
        if identity in identities:
            raise InvalidProfile("ignore policy matchers are duplicated")
        identities.add(identity)
        ids.append(str(rule["id"]))
        normalized.append(rule)
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise InvalidProfile("ignore rule IDs must be sorted and unique")
    policy["rules"] = normalized
    return policy


def _validate_page_request(value: object) -> dict[str, object]:
    page = _expect_dict(value, "page request")
    _exact_keys(page, {"kind", "record_limit", "cursor"}, "page request")
    if page["kind"] != "inventory_page_request":
        raise InvalidProfile("page request kind is incompatible")
    limit = page["record_limit"]
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE_RECORDS:
        raise InvalidProfile("page record limit is outside the profile")
    cursor = page["cursor"]
    if cursor is None:
        return page
    cursor_value = _expect_dict(cursor, "inventory cursor")
    _exact_keys(
        cursor_value,
        {"kind", "snapshot_digest", "after_kind", "after_id"},
        "inventory cursor",
    )
    if cursor_value["kind"] != "inventory_cursor":
        raise InvalidProfile("inventory cursor kind is incompatible")
    digest = _expect_dict(
        cursor_value["snapshot_digest"],
        "cursor snapshot digest",
    )
    _exact_keys(digest, {"kind", "algorithm", "value"}, "digest")
    if (
        digest["kind"] != "digest"
        or digest["algorithm"] != "sha-256"
        or type(digest["value"]) is not str
        or _DIGEST.fullmatch(digest["value"]) is None
    ):
        raise InvalidProfile("cursor digest is invalid")
    kind = cursor_value["after_kind"]
    identifier = cursor_value["after_id"]
    if (
        type(kind) is not str
        or kind not in _RECORD_PREFIX
        or type(identifier) is not str
        or not identifier.startswith(f"{_RECORD_PREFIX[kind]}.")
        or _DIGEST.fullmatch(identifier.split(".", 1)[1]) is None
    ):
        raise InvalidProfile("cursor coordinate is invalid")
    return page


def _validate_repository_path(value: object) -> None:
    if type(value) is not str or not value:
        raise InvalidProfile("repository path is invalid")
    if value == ".":
        return
    if (
        value.startswith("/")
        or "//" in value
        or "\\" in value
        or unicodedata.normalize("NFC", value) != value
        or len(value.encode("utf-8")) > 1_024
    ):
        raise InvalidProfile("repository path is not normalized")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InvalidProfile("repository path is not normalized")
    for part in parts:
        _validate_path_segment(part)


def _validate_path_segment(value: object) -> None:
    if type(value) is not str or not value:
        raise InvalidProfile("path segment is invalid")
    if (
        value in {".", ".."}
        or "/" in value
        or "\\" in value
        or ":" in value
        or any(character in '<>"|?*' for character in value)
        or value.endswith((" ", "."))
        or unicodedata.normalize("NFC", value) != value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or len(value.encode("utf-8")) > 255
        or value.partition(".")[0].upper() in _WINDOWS_RESERVED
    ):
        raise InvalidProfile("path segment is not portable")


def _require_identifier(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) > 255
        or _IDENTIFIER.fullmatch(value) is None
    ):
        raise InvalidProfile(f"{label} is invalid")


def _require_qualified_name(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) > 255
        or _QUALIFIED_NAME.fullmatch(value) is None
    ):
        raise InvalidProfile(f"{label} is invalid")


def _require_uri(value: object, label: str) -> None:
    if (
        type(value) is not str
        or not 3 <= len(value) <= 2_048
        or _URI.fullmatch(value) is None
    ):
        raise InvalidProfile(f"{label} is invalid")


def _exact_keys(
    value: dict[str, object],
    expected: set[str],
    label: str,
) -> None:
    if set(value) != expected:
        raise InvalidProfile(f"{label} fields are not exact")


def _expect_dict(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise InvalidProfile(f"{label} must be an object")
    return value


def _expect_list(value: object, label: str) -> list[object]:
    if type(value) is not list:
        raise InvalidProfile(f"{label} must be a list")
    return value


def _check_depth(depth: int) -> None:
    if depth > MAX_PROFILE_DEPTH:
        raise InvalidProfile("tagged value nesting limit was exceeded")
