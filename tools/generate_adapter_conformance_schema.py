"""Generate the deterministic UCF adapter conformance kit 1.0.0 schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.adapter_conformance.models import (
    CONFORMANCE_KIT_VERSION,
    ConformanceDocument,
)
from ucf.adapter_protocol import ADAPTER_PROTOCOL_VERSION
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "src"
    / "ucf"
    / "schemas"
    / "adapter_conformance"
    / "v1"
    / "schema.json"
)
SCHEMA_ID = "urn:ucf:schema:adapter-conformance:1.0.0"


def build_schema() -> dict[str, Any]:
    """Build the closed structural schema from authoritative kit models."""

    schema = TypeAdapter(ConformanceDocument).json_schema(mode="validation")
    schema.update(
        {
            "$comment": (
                "Generated deterministically from UCF adapter conformance "
                "kit 1.0.0 models; do not edit by hand. Cross-record "
                "identities, report disposition, strict JSON, and executable "
                "wire behavior remain runtime checks."
            ),
            "$id": SCHEMA_ID,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "description": (
                "Closed schema for the UCF adapter conformance manifest, "
                "ordered wire fixtures, deterministic result report, and "
                "content-addressed distribution index."
            ),
            "title": "UCF adapter conformance kit 1.0.0 documents",
            "x-ucf-adapter-protocol-version": ADAPTER_PROTOCOL_VERSION,
            "x-ucf-conformance-kit-version": CONFORMANCE_KIT_VERSION,
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "case and step identity uniqueness",
                "fault-profile references to manifest cases",
                "fixture case and procedure agreement with the manifest",
                "error category, symbolic code, and JSON-RPC code agreement",
                "report status derivation and exact manifest case order",
                "asset identity uniqueness and lexicographic index order",
                "asset size and SHA-256 agreement with installed bytes",
                "wire framing, lifecycle, correlation, deadlines, and cleanup",
            ],
        }
    )
    return schema


def render_schema() -> str:
    return (
        json.dumps(
            build_schema(),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check the adapter conformance kit schema."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Schema output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero instead of writing when the schema is stale.",
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_args(arguments)
    rendered = render_schema()
    output: Path = args.output
    if args.check:
        if not output.exists():
            print(f"Schema is missing: {output}")
            return 1
        if output.read_text(encoding="utf-8") != rendered:
            print(f"Schema is stale: {output}")
            return 1
        print(f"Schema is current: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote schema: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
