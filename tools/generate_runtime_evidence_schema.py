"""Generate deterministic UCF runtime-evidence profile 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.ir.codec import MAX_JSON_NESTING
from ucf.runtime_evidence import (
    RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
    RUNTIME_EVIDENCE_POLICY_SCHEMA_URI,
    RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
    RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
    RUNTIME_EVIDENCE_VERSION,
    RuntimeEnvironment,
    RuntimeEvidenceImportRequest,
    RuntimeEvidencePolicy,
    RuntimeEvidenceResult,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT
    / "src"
    / "ucf"
    / "schemas"
    / "runtime_evidence"
    / "v1"
)
POLICY_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "policy.schema.json"
ENVIRONMENT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "environment.schema.json"
)
REQUEST_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "request.schema.json"
RESULT_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "result.schema.json"

_DOCUMENTS = (
    (
        POLICY_SCHEMA_OUTPUT,
        RuntimeEvidencePolicy,
        RUNTIME_EVIDENCE_POLICY_SCHEMA_URI,
        "runtime_evidence_policy",
        "UCF runtime evidence policy profile 1.0.0",
    ),
    (
        ENVIRONMENT_SCHEMA_OUTPUT,
        RuntimeEnvironment,
        RUNTIME_EVIDENCE_ENVIRONMENT_SCHEMA_URI,
        "runtime_environment",
        "UCF runtime environment profile 1.0.0",
    ),
    (
        REQUEST_SCHEMA_OUTPUT,
        RuntimeEvidenceImportRequest,
        RUNTIME_EVIDENCE_REQUEST_SCHEMA_URI,
        "runtime_evidence_import_request",
        "UCF runtime evidence import request profile 1.0.0",
    ),
    (
        RESULT_SCHEMA_OUTPUT,
        RuntimeEvidenceResult,
        RUNTIME_EVIDENCE_RESULT_SCHEMA_URI,
        "runtime_evidence_result",
        "UCF runtime evidence result profile 1.0.0",
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
                "Generated deterministically from UCF runtime-evidence "
                "profile 1.0.0 models; do not edit by hand. Content identity, "
                "canonical order, exact external references, source "
                "integrity, negotiated capabilities, and observed-only "
                "projection remain runtime semantics."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-runtime-evidence-version": RUNTIME_EVIDENCE_VERSION,
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "safe opaque and explicitly versioned identity URNs",
                "exact Behavior document and observation slot resolution",
                "exact environment document digest and revision",
                "partial sampling without absence inference",
                "canonical unique policy rules and selected rule references",
                "content-derived result identity",
                "exact echoed request and initialized producer",
                "required verification and runtime profile capabilities",
                "local source revision stability before and after import",
                "code-only policy rejection without peer-authored prose",
                "observed-only Trust projection from accepted policy rules",
                "no raw recording or retained diagnostic bytes",
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
            "Generate or check the published runtime-evidence schemas."
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
