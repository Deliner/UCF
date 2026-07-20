"""Generate the deterministic UCF adapter protocol 1.0.0 JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.adapter_protocol.models import (
    ADAPTER_PROTOCOL_VERSION,
    MAX_FRAME_BYTES,
    ClientMessage,
    ServerMessage,
)
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "src"
    / "ucf"
    / "schemas"
    / "adapter_protocol"
    / "v1"
    / "schema.json"
)
SCHEMA_ID = "urn:ucf:schema:adapter-protocol:1.0.0"


def build_schema() -> dict[str, Any]:
    """Build the closed structural schema from authoritative wire models."""

    schema = TypeAdapter(ClientMessage | ServerMessage).json_schema(
        mode="validation"
    )
    schema.update(
        {
            "$comment": (
                "Generated deterministically from the UCF adapter protocol "
                "1.0.0 models; do not edit by hand. Framing, message-method "
                "agreement, lifecycle, capability, correlation, and embedded "
                "IR semantics are enforced by the runtime contract."
            ),
            "$id": SCHEMA_ID,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "description": (
                "Closed structural schema for one UCF adapter JSON-RPC "
                "message. Each encoded message is one LF-terminated UTF-8 "
                "object; JSON-RPC batches are unsupported."
            ),
            "title": "UCF adapter protocol 1.0.0 message",
            "x-ucf-adapter-protocol-version": ADAPTER_PROTOCOL_VERSION,
            "x-ucf-max-frame-bytes": MAX_FRAME_BYTES,
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "method/params discriminator agreement",
                "exact protocol version and lifecycle",
                "capability uniqueness and minimum-version negotiation",
                "request/result correlation and result-kind agreement",
                "embedded Behavior IR, Trust IR, and IR-value semantics",
                "error category and symbolic error-code agreement",
                "JSON-RPC numeric and symbolic error-code agreement",
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
        description="Generate or check the UCF adapter protocol JSON Schema."
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
