"""Generate deterministic UCF change-governance 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.change_governance import (
    CHANGE_GOVERNANCE_VERSION,
    DECISION_ASSESSMENT_SCHEMA_URI,
    DECISION_DECLARATION_SCHEMA_URI,
    GATE_EVALUATION_SCHEMA_URI,
    IMPACT_REPORT_SCHEMA_URI,
    DecisionAssessment,
    DecisionDeclaration,
    GateEvaluation,
    ImpactReport,
)
from ucf.ir.codec import MAX_JSON_NESTING

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "change_governance" / "v1"
)

_DOCUMENTS = (
    (
        "impact-report.schema.json",
        ImpactReport,
        IMPACT_REPORT_SCHEMA_URI,
        "impact_report",
        "UCF structural change impact report 1.0.0",
    ),
    (
        "decision-assessment.schema.json",
        DecisionAssessment,
        DECISION_ASSESSMENT_SCHEMA_URI,
        "decision_assessment",
        "UCF change decision assessment 1.0.0",
    ),
    (
        "decision-declaration.schema.json",
        DecisionDeclaration,
        DECISION_DECLARATION_SCHEMA_URI,
        "decision_declaration",
        "UCF change decision declaration 1.0.0",
    ),
    (
        "gate-evaluation.schema.json",
        GateEvaluation,
        GATE_EVALUATION_SCHEMA_URI,
        "gate_evaluation",
        "UCF change gate evaluation 1.0.0",
    ),
)

_COMMON_RUNTIME_SEMANTIC_CHECKS = (
    "strict UTF-8 and duplicate-member JSON decoding",
    f"maximum JSON and typed nesting depth {MAX_JSON_NESTING}",
    "exact canonical runtime model and container types",
)
_RUNTIME_SEMANTIC_CHECKS_BY_KIND = {
    "impact_report": (
        "exact proposal, delta, base, and final behavior context",
        "exhaustive direct delta subjects and canonical field differences",
        "side-separated supported edge graph with cycle-safe shortest witnesses",
        "narrow structural compatibility and explicit unresolved semantics",
    ),
    "decision_assessment": (
        "exact impact report and complete predecessor replay",
        "exact six-class assessment with no derived downgrade",
        "inspectable declared basis for every non-derived classification",
    ),
    "decision_declaration": (
        "exact impact and assessment predecessor replay",
        "exact applicable decision-class coverage",
        "rejection preserved as a blocking decision outcome",
    ),
    "gate_evaluation": (
        "full predecessor replay and gate recomputation",
        "distinct no-decision, approved, unresolved, required, and rejected states",
        "no declaration accepted for an irrelevant or unresolved class set",
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
    schema.update(
        {
            "$comment": (
                "Generated deterministically from UCF change-governance "
                "profile 1.0.0 models; do not edit by hand. The "
                "x-ucf-runtime-semantic-checks annotation names only "
                "additional checks beyond JSON Schema."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-change-governance-version": CHANGE_GOVERNANCE_VERSION,
            "x-ucf-document-kind": document_kind,
            "x-ucf-runtime-semantic-checks": [
                *_COMMON_RUNTIME_SEMANTIC_CHECKS,
                *_RUNTIME_SEMANTIC_CHECKS_BY_KIND[document_kind],
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
        description="Generate or check the change-governance schemas."
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
