"""Generate deterministic UCF generation profile 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.generation import (
    GENERATION_PROFILE_VERSION,
    GENERATION_REQUEST_SCHEMA_URI,
    GENERATION_RESULT_SCHEMA_URI,
    GenerationRequest,
    GenerationResult,
)
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "generation" / "v1"
)
REQUEST_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "request.schema.json"
RESULT_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "result.schema.json"

_DOCUMENTS = (
    (
        REQUEST_SCHEMA_OUTPUT,
        GenerationRequest,
        GENERATION_REQUEST_SCHEMA_URI,
        "generation_request",
        "UCF generation request profile 1.0.0",
    ),
    (
        RESULT_SCHEMA_OUTPUT,
        GenerationResult,
        GENERATION_RESULT_SCHEMA_URI,
        "generation_result",
        "UCF generation result profile 1.0.0",
    ),
)


def build_schemas() -> dict[Path, dict[str, Any]]:
    return {
        path: _build_schema(
            document_type,
            schema_uri=schema_uri,
            document_kind=document_kind,
            title=title,
        )
        for (
            path,
            document_type,
            schema_uri,
            document_kind,
            title,
        ) in _DOCUMENTS
    }


def _build_schema(
    document_type: Any,
    *,
    schema_uri: str,
    document_kind: str,
    title: str,
) -> dict[str, Any]:
    schema = TypeAdapter(document_type).json_schema(mode="validation")
    schema.update(
        {
            "$comment": (
                "Generated deterministically from UCF generation profile "
                "1.0.0 models; do not edit by hand. Canonical ordering, "
                "content-derived identities, exact Behavior context, port "
                "coverage, negotiated capabilities, producer identity, "
                "manifest completeness, and publication safety remain "
                "runtime semantics."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-generation-version": GENERATION_PROFILE_VERSION,
            "x-ucf-generation-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "exact versioned profile and procedure coordinates",
                "content-derived request and result identities",
                "complete valid Behavior document and exact action subject",
                "canonical complete required input and output port values",
                "canonical profile configuration",
                "exact generic and profile capability selections",
                "exact initialized producer and echoed request",
                "safe unique canonical relative generated paths",
                "exact UTF-8 byte size and content digest",
                "bounded per-file, aggregate, and verification data",
                "exact request and result adapter protocol frame budgets",
                "generator-owned files only",
                "publication validation before destination mutation",
                "no claim-level promotion from generation",
            ],
        }
    )
    return schema


def render_schemas() -> dict[Path, str]:
    return {
        path: (
            json.dumps(
                schema,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        for path, schema in build_schemas().items()
    }


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check the published generation schemas."
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = _parse_args(arguments)
    expected = {
        options.output_directory / path.name: content
        for path, content in render_schemas().items()
    }
    if options.check:
        actual = {
            path
            for path in options.output_directory.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        stale = sorted(
            {
                path
                for path, content in expected.items()
                if path.is_symlink()
                or not path.is_file()
                or path.read_text(encoding="utf-8") != content
            }
            | (actual - set(expected))
        )
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0
    options.output_directory.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
