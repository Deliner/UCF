"""Generate the deterministic UCF inventory profile 1.0.0 schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.inventory import (
    INVENTORY_PAGE_SCHEMA_URI,
    INVENTORY_REQUEST_SCHEMA_URI,
    INVENTORY_SCHEMA_URI,
    INVENTORY_VERSION,
    MAX_INVENTORY_DIAGNOSTICS,
    MAX_INVENTORY_PAGES,
    MAX_INVENTORY_RECORDS,
    MAX_PAGE_RECORDS,
    FactKind,
    InventoryPage,
    InventoryRequest,
    InventorySnapshot,
)
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT
    / "src"
    / "ucf"
    / "schemas"
    / "inventory"
    / "v1"
)
DEFAULT_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "schema.json"
REQUEST_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "request.schema.json"
PAGE_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "page.schema.json"
SCHEMA_ID = INVENTORY_SCHEMA_URI

def build_schema() -> dict[str, Any]:
    """Build the exact closed inventory snapshot schema."""

    return _build_document_schema(
        InventorySnapshot,
        schema_id=INVENTORY_SCHEMA_URI,
        document_kind="inventory_snapshot",
        title="UCF inventory snapshot profile 1.0.0",
        description=(
            "Closed logical schema for a complete UCF observed-only "
            "brownfield inventory snapshot."
        ),
    )


def build_schemas() -> dict[Path, dict[str, Any]]:
    """Build every independently addressable inventory profile resource."""

    return {
        DEFAULT_OUTPUT: build_schema(),
        REQUEST_SCHEMA_OUTPUT: _build_document_schema(
            InventoryRequest,
            schema_id=INVENTORY_REQUEST_SCHEMA_URI,
            document_kind="inventory_request_profile",
            title="UCF inventory request profile 1.0.0",
            description=(
                "Closed logical schema for one UCF adapter inventory "
                "request profile."
            ),
        ),
        PAGE_SCHEMA_OUTPUT: _build_document_schema(
            InventoryPage,
            schema_id=INVENTORY_PAGE_SCHEMA_URI,
            document_kind="inventory_page",
            title="UCF inventory page profile 1.0.0",
            description=(
                "Closed logical schema for one bounded UCF adapter "
                "inventory result page."
            ),
        ),
    }


def _build_document_schema(
    document_type: Any,
    *,
    schema_id: str,
    document_kind: str,
    title: str,
    description: str,
) -> dict[str, Any]:
    schema = TypeAdapter(document_type).json_schema(mode="validation")
    _add_local_profile_constraints(schema, document_type)
    schema.update(
        {
            "$comment": (
                "Generated deterministically from UCF inventory profile "
                "1.0.0 models; do not edit by hand. Strict JSON, global "
                "identity, reference, coverage, paging, and digest semantics "
                "remain runtime checks."
            ),
            "$id": schema_id,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "description": description,
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-inventory-version": INVENTORY_VERSION,
            "x-ucf-wire-contract": (
                "tagged AdapterPayload in adapter protocol 1.0.0"
            ),
            "x-ucf-normative-algorithms": [
                "urn:ucf:inventory-algorithm:cursor-coordinate:1.0.0",
                "urn:ucf:inventory-algorithm:ignore-policy:1.0.0",
                "urn:ucf:inventory-algorithm:page-terminal:1.0.0",
                "urn:ucf:inventory-algorithm:portable-path:1.0.0",
                "urn:ucf:inventory-algorithm:source-span-order:1.0.0",
            ],
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "canonical tagged IRValue field order and exact value kinds",
                "content-derived record identities",
                "content-derived source revision",
                "typed cross-record reference resolution",
                "repository parent topology and portable path identity",
                "Unicode NFC normalization of repository paths",
                "explicit ignore-policy matching and pruned evidence",
                (
                    "ignore rule ID and portable matcher uniqueness with "
                    "canonical ID order"
                ),
                "coverage counts and error-diagnostic agreement",
                "producer, provenance path, and content digest agreement",
                "canonical record order and semantic identity uniqueness",
                "revision-bound contiguous page cursor chain",
                "exact repeated page headers and terminal state",
                "assembled canonical snapshot digest agreement",
                f"maximum {MAX_PAGE_RECORDS} records per page",
                f"maximum {MAX_INVENTORY_RECORDS} records per snapshot",
                f"maximum {MAX_INVENTORY_PAGES} pages per snapshot",
                (
                    "maximum "
                    f"{MAX_INVENTORY_DIAGNOSTICS} diagnostics per snapshot"
                ),
            ],
        }
    )
    return schema


def _add_local_profile_constraints(
    schema: dict[str, Any],
    document_type: Any,
) -> None:
    if document_type in {InventoryPage, InventorySnapshot}:
        coverage = schema["properties"]["coverage"]
        coverage_item = coverage["items"]
        coverage.update(
            {
                "prefixItems": [
                    {
                        **coverage_item,
                        "properties": {
                            "fact_kind": {"const": fact_kind.value}
                        },
                    }
                    for fact_kind in FactKind
                ],
                "items": False,
                "minItems": len(FactKind),
                "maxItems": len(FactKind),
                "x-ucf-canonical-order-by": ["fact_kind"],
            }
        )
    if document_type is InventoryPage:
        schema.setdefault("allOf", []).append(
            {
                "if": {
                    "properties": {"complete": {"const": True}},
                    "required": ["complete"],
                },
                "then": {
                    "properties": {"next_cursor": {"type": "null"}}
                },
                "else": {
                    "properties": {
                        "next_cursor": {
                            "$ref": "#/$defs/InventoryCursor"
                        }
                    }
                },
            }
        )
        schema["x-ucf-validation-algorithm"] = (
            "urn:ucf:inventory-algorithm:page-terminal:1.0.0"
        )


def render_schema() -> str:
    """Render the exact inventory snapshot resource."""

    return _render(build_schema())


def render_schemas() -> dict[Path, str]:
    """Render the complete exact inventory schema resource set."""

    return {
        path: _render(schema) for path, schema in build_schemas().items()
    }


def _render(schema: dict[str, Any]) -> str:
    return (
        json.dumps(
            schema,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check the published UCF inventory schema."
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=(
            "Schema output directory "
            f"(default: {DEFAULT_OUTPUT_DIRECTORY})"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero instead of writing when the schema is stale.",
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_args(arguments)
    output_directory: Path = args.output_directory
    rendered = {
        output_directory / source.name: content
        for source, content in render_schemas().items()
    }

    if args.check:
        for output, content in rendered.items():
            if not output.exists():
                print(f"Schema is missing: {output}")
                return 1
            if output.read_text(encoding="utf-8") != content:
                print(f"Schema is stale: {output}")
                return 1
        print(
            "Inventory schemas are current: "
            f"{', '.join(str(path) for path in sorted(rendered))}"
        )
        return 0

    output_directory.mkdir(parents=True, exist_ok=True)
    for output, content in rendered.items():
        output.write_text(content, encoding="utf-8")
        print(f"Wrote schema: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
