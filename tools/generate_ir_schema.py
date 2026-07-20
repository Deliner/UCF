"""Generate the deterministic public JSON Schema for UCF behavior IR v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ucf.ir.codec import MAX_JSON_NESTING
from ucf.ir.models import BehaviorIR

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "ir" / "v1" / "schema.json"
)
SCHEMA_ID = "urn:ucf:schema:ir:1.0.0"
IR_VERSION = "1.0.0"


def build_schema() -> dict[str, Any]:
    """Build the structural schema from the authoritative IR models."""

    schema = BehaviorIR.model_json_schema(mode="validation")
    schema.update(
        {
            "$comment": (
                "Generated deterministically from the UCF IR v1 contract; "
                "do not edit by hand. Cross-record identity and reference "
                "checks are performed by the IR runtime validator."
            ),
            "$id": SCHEMA_ID,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "description": (
                "Closed structural schema for UCF language-neutral behavior "
                "IR 1.0.0. It does not promote evidence or execute declared "
                "rules."
            ),
            "title": "UCF behavior IR 1.0.0",
            "x-ucf-ir-version": IR_VERSION,
            "x-ucf-runtime-semantic-checks": [
                "global entity identity uniqueness",
                "typed cross-record reference resolution",
                "port resolution and binding compatibility",
                "record entry uniqueness",
                "required capability availability",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
            ],
        }
    )
    return schema


def render_schema() -> str:
    return json.dumps(
        build_schema(),
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check the published UCF IR JSON Schema."
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
        help="Exit non-zero instead of writing when the checked schema is stale.",
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
