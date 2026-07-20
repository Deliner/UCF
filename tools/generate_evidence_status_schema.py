"""Generate deterministic UCF evidence-status 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.evidence_status import (
    EVIDENCE_STATUS_VERSION,
    VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI,
    VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
    VerificationEvidenceAssessment,
    VerificationEvidenceEnvelope,
)
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "evidence_status" / "v1"
)
ENVELOPE_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "envelope.schema.json"
ASSESSMENT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "assessment.schema.json"
)

_DOCUMENTS = (
    (
        ENVELOPE_SCHEMA_OUTPUT,
        VerificationEvidenceEnvelope,
        VERIFICATION_EVIDENCE_ENVELOPE_SCHEMA_URI,
        "verification_evidence_envelope",
        "UCF verification evidence envelope 1.0.0",
        (
            "strict UTF-8 and duplicate-member JSON decoding",
            f"maximum JSON nesting depth {MAX_JSON_NESTING}",
            "content-derived envelope identity and exact typed references",
            "canonical unique projection members",
            "reviewed behavior and transitive source dependency projection",
            "exact adapter, capability, procedure, environment, and check coordinates",
            "trace coordinates are not standalone stale predicates",
            "tested-only historical claim binding without verified promotion",
        ),
    ),
    (
        ASSESSMENT_SCHEMA_OUTPUT,
        VerificationEvidenceAssessment,
        VERIFICATION_EVIDENCE_ASSESSMENT_SCHEMA_URI,
        "verification_evidence_assessment",
        "UCF verification evidence assessment 1.0.0",
        (
            "strict UTF-8 and duplicate-member JSON decoding",
            f"maximum JSON nesting depth {MAX_JSON_NESTING}",
            "content-derived assessment and exact envelope identity",
            "canonical unique projection members",
            "canonical unique reasons",
            "fresh, stale, and indeterminate shapes are mutually exclusive",
            "current projections are core-derived from validated context",
            "no status produces a verified claim",
        ),
    ),
)


def build_schemas() -> dict[Path, dict[str, Any]]:
    return {
        path: _build_schema(
            document_type,
            schema_uri=schema_uri,
            document_kind=document_kind,
            title=title,
            semantic_checks=semantic_checks,
        )
        for (
            path,
            document_type,
            schema_uri,
            document_kind,
            title,
            semantic_checks,
        ) in _DOCUMENTS
    }


def _build_schema(
    document_type: Any,
    *,
    schema_uri: str,
    document_kind: str,
    title: str,
    semantic_checks: tuple[str, ...],
) -> dict[str, Any]:
    schema = TypeAdapter(document_type).json_schema(mode="validation")
    schema.update(
        {
            "$comment": (
                "Generated deterministically from UCF evidence-status "
                "profile 1.0.0 models; do not edit by hand."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-evidence-status-version": EVIDENCE_STATUS_VERSION,
            "x-ucf-evidence-status-semantic-checks": list(
                semantic_checks
            ),
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
        description="Generate or check the evidence-status schemas."
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
