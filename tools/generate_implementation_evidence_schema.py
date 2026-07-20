"""Generate deterministic UCF implementation-evidence 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.implementation_evidence import (
    EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
    EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
    IMPLEMENTATION_EVIDENCE_VERSION,
    IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
    IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
    MAX_IMPLEMENTATION_BINDINGS,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ImplementationMappingRequest,
    ImplementationMappingResult,
)
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT
    / "src"
    / "ucf"
    / "schemas"
    / "implementation_evidence"
    / "v1"
)
MAPPING_REQUEST_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "mapping-request.schema.json"
)
MAPPING_RESULT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "mapping-result.schema.json"
)
VERIFICATION_REQUEST_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "verification-request.schema.json"
)
VERIFICATION_RESULT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "verification-result.schema.json"
)

_DOCUMENTS = (
    (
        MAPPING_REQUEST_SCHEMA_OUTPUT,
        ImplementationMappingRequest,
        IMPLEMENTATION_MAPPING_REQUEST_SCHEMA_URI,
        "implementation_mapping_request",
        "UCF implementation mapping request profile 1.0.0",
    ),
    (
        MAPPING_RESULT_SCHEMA_OUTPUT,
        ImplementationMappingResult,
        IMPLEMENTATION_MAPPING_RESULT_SCHEMA_URI,
        "implementation_mapping_result",
        "UCF implementation mapping result profile 1.0.0",
    ),
    (
        VERIFICATION_REQUEST_SCHEMA_OUTPUT,
        ExecutionVerificationRequest,
        EXECUTION_VERIFICATION_REQUEST_SCHEMA_URI,
        "execution_verification_request",
        "UCF execution verification request profile 1.0.0",
    ),
    (
        VERIFICATION_RESULT_SCHEMA_OUTPUT,
        ExecutionVerificationResult,
        EXECUTION_VERIFICATION_RESULT_SCHEMA_URI,
        "execution_verification_result",
        "UCF execution verification result profile 1.0.0",
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
                "Generated deterministically from UCF implementation-evidence "
                "profile 1.0.0 models; do not edit by hand. Exact bundle, "
                "source, mapping, producer, capability, procedure, result, "
                "and successor checks remain runtime semantics."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-implementation-evidence-version": (
                IMPLEMENTATION_EVIDENCE_VERSION
            ),
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "exact reviewed bundle, behavior, and inventory identity",
                "reviewed materialization roots only",
                "canonical unique behavior and inventory references",
                (
                    "exactly one complete source binding per requested "
                    "target"
                ),
                "candidate public interface and evidence containment",
                "content-derived mapping and verification result identities",
                "exact echoed request and initialized producer",
                "exact selected operation capability and procedure",
                "current source revision before and after execution",
                "exact mapping, subject, check, and environment coordinates",
                "passed-only tested evidence successor projection",
                "no mapped or verified claim promotion",
                f"maximum {MAX_IMPLEMENTATION_BINDINGS} bindings or records",
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
        description=(
            "Generate or check the implementation-evidence schemas."
        )
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
        stale = [
            path
            for path, content in expected.items()
            if not path.is_file()
            or path.read_text(encoding="utf-8") != content
        ]
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
