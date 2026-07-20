"""Generate deterministic UCF change-lifecycle 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.change_lifecycle import (
    ARCHIVE_RECORD_SCHEMA_URI,
    BEHAVIOR_DELTA_SCHEMA_URI,
    CHANGE_LIFECYCLE_VERSION,
    CHANGE_PROPOSAL_SCHEMA_URI,
    IMPLEMENTATION_RECORD_SCHEMA_URI,
    TASK_GRAPH_SCHEMA_URI,
    VERIFICATION_RECORD_SCHEMA_URI,
    ArchiveRecord,
    BehaviorDelta,
    ChangeProposal,
    ImplementationRecord,
    TaskGraph,
    VerificationRecord,
)
from ucf.change_lifecycle.models import MAX_OPENSPEC_ARTIFACT_BYTES
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "change_lifecycle" / "v1"
)

_DOCUMENTS = (
    (
        "proposal.schema.json",
        ChangeProposal,
        CHANGE_PROPOSAL_SCHEMA_URI,
        "change_proposal",
        "UCF change proposal profile 1.0.0",
    ),
    (
        "behavior-delta.schema.json",
        BehaviorDelta,
        BEHAVIOR_DELTA_SCHEMA_URI,
        "behavior_delta",
        "UCF behavior delta profile 1.0.0",
    ),
    (
        "task-graph.schema.json",
        TaskGraph,
        TASK_GRAPH_SCHEMA_URI,
        "task_graph",
        "UCF change task graph profile 1.0.0",
    ),
    (
        "implementation-record.schema.json",
        ImplementationRecord,
        IMPLEMENTATION_RECORD_SCHEMA_URI,
        "implementation_record",
        "UCF change implementation record profile 1.0.0",
    ),
    (
        "verification-record.schema.json",
        VerificationRecord,
        VERIFICATION_RECORD_SCHEMA_URI,
        "verification_record",
        "UCF change verification record profile 1.0.0",
    ),
    (
        "archive-record.schema.json",
        ArchiveRecord,
        ARCHIVE_RECORD_SCHEMA_URI,
        "archive_record",
        "UCF change archive record profile 1.0.0",
    ),
)

_COMMON_RUNTIME_SEMANTIC_CHECKS = (
    "strict UTF-8 and duplicate-member JSON decoding",
    f"maximum JSON nesting depth {MAX_JSON_NESTING}",
)
_RUNTIME_SEMANTIC_CHECKS_BY_KIND = {
    "change_proposal": (
        (
            "canonical RFC 4648 base64 with decoded artifact byte bound "
            f"{MAX_OPENSPEC_ARTIFACT_BYTES}"
        ),
        "artifact byte SHA-256 matches decoded content",
        "UTF-8 text content for every non-binary artifact media type",
        (
            "safe relative POSIX artifact paths without empty, dot, dot-dot, "
            "backslash, absolute, or NUL segments"
        ),
        "canonical artifact path ordering and uniqueness",
        "exact OpenSpec artifact role, path, and media-type correlation",
        "one supported spec-driven profile declaration with unique YAML keys",
        (
            "canonical one-level delta-spec paths and base-spec-to-delta "
            "capability coverage"
        ),
        "no OpenSpec artifact file/directory path-prefix collisions",
    ),
    "behavior_delta": (
        "exact proposal, base behavior, and final behavior context",
        ("delta entry subjects bind their top-level behavior document coordinates"),
        "exhaustive canonical behavior delta",
    ),
    "task_graph": (
        "exact behavior delta and proposal context",
        "resolved acyclic canonically ordered task dependency graph",
        "exact task-to-delta subject coverage",
        "exact task source artifact and OpenSpec checkbox coordinates",
    ),
    "implementation_record": (
        "exact task graph, behavior delta, and proposal context",
        "completed tasks before implementation evidence",
        (
            "one context-validated imported evidence result and "
            "durable validation receipt per supported delta subject"
        ),
        "removed behavior requires a separate final-state absence-evidence profile",
    ),
    "verification_record": (
        (
            "exact implementation record, task graph, behavior delta, "
            "and proposal context"
        ),
        "passed evidence only before verification acceptance",
        "verification subjects exactly match accepted implementation evidence",
    ),
    "archive_record": (
        (
            "exact proposal, behavior delta, task graph, implementation, "
            "and verification predecessor chain"
        ),
        "exact final behavior snapshot matches the accepted behavior delta",
    ),
}


def build_schemas() -> dict[Path, dict[str, Any]]:
    return {
        DEFAULT_OUTPUT_DIRECTORY / filename: _build_schema(
            document_type,
            schema_uri=schema_uri,
            document_kind=document_kind,
            title=title,
        )
        for (
            filename,
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
    runtime_semantic_checks = [
        *_COMMON_RUNTIME_SEMANTIC_CHECKS,
        *_RUNTIME_SEMANTIC_CHECKS_BY_KIND[document_kind],
    ]
    schema.update(
        {
            "$comment": (
                "Generated deterministically from UCF change-lifecycle "
                "profile 1.0.0 models; do not edit by hand. The "
                "x-ucf-runtime-semantic-checks annotation names only the "
                "additional runtime checks for this document kind."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-change-lifecycle-version": CHANGE_LIFECYCLE_VERSION,
            "x-ucf-document-kind": document_kind,
            "x-ucf-runtime-semantic-checks": runtime_semantic_checks,
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
        description="Generate or check the change-lifecycle schemas."
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
            if not path.is_file() or path.read_text(encoding="utf-8") != content
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
