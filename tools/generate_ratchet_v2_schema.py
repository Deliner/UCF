"""Generate deterministic UCF ratchet profile 2.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.ir.codec import MAX_JSON_NESTING
from ucf.ratchet.v2 import (
    BEHAVIOR_OBSERVED_FINGERPRINT_ALGORITHM_URI,
    BEHAVIOR_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
    COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI,
    COVERAGE_QUALIFICATION_ALGORITHM_URI,
    COVERAGE_RECONCILIATION_ALGORITHM_URI,
    COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
    COVERAGE_SUBJECT_KEY_ALGORITHM_URI,
    MAX_RATCHET_RULES,
    MAX_RATCHET_SUBJECTS,
    MAX_RATCHET_VIOLATIONS,
    RATCHET_ASSESSMENT_SCHEMA_URI,
    RATCHET_BASELINE_SCHEMA_URI,
    RATCHET_EVALUATION_PROCEDURE_URI,
    RATCHET_EVALUATION_REPORT_SCHEMA_URI,
    RATCHET_POLICY_SCHEMA_URI,
    RATCHET_VERSION,
    RatchetAssessment,
    RatchetBaseline,
    RatchetEvaluationReport,
    RatchetPolicy,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "ratchet" / "v2"
)
POLICY_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "policy.schema.json"
ASSESSMENT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "assessment.schema.json"
)
BASELINE_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "baseline.schema.json"
EVALUATION_REPORT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "evaluation-report.schema.json"
)

_DOCUMENTS = (
    (
        POLICY_SCHEMA_OUTPUT,
        RatchetPolicy,
        RATCHET_POLICY_SCHEMA_URI,
        "ratchet_policy",
        "UCF ratchet policy profile 2.0.0",
    ),
    (
        ASSESSMENT_SCHEMA_OUTPUT,
        RatchetAssessment,
        RATCHET_ASSESSMENT_SCHEMA_URI,
        "ratchet_assessment",
        "UCF ratchet assessment profile 2.0.0",
    ),
    (
        BASELINE_SCHEMA_OUTPUT,
        RatchetBaseline,
        RATCHET_BASELINE_SCHEMA_URI,
        "ratchet_baseline",
        "UCF ratchet baseline profile 2.0.0",
    ),
    (
        EVALUATION_REPORT_SCHEMA_OUTPUT,
        RatchetEvaluationReport,
        RATCHET_EVALUATION_REPORT_SCHEMA_URI,
        "ratchet_evaluation_report",
        "UCF ratchet evaluation report profile 2.0.0",
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
        for path, document_type, schema_uri, document_kind, title in _DOCUMENTS
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
                "Generated deterministically from UCF ratchet profile "
                "2.0.0 models; do not edit by hand. Content identities, "
                "canonical order, resolved references, exact source "
                "projections, accepted lineage pins, predecessor lineage, "
                "and recomputed summaries remain runtime semantics."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-ratchet-version": RATCHET_VERSION,
            "x-ucf-normative-algorithms": [
                BEHAVIOR_OBSERVED_FINGERPRINT_ALGORITHM_URI,
                BEHAVIOR_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
                COVERAGE_OBSERVED_FINGERPRINT_ALGORITHM_URI,
                COVERAGE_QUALIFICATION_ALGORITHM_URI,
                COVERAGE_RECONCILIATION_ALGORITHM_URI,
                COVERAGE_SEMANTIC_FINGERPRINT_ALGORITHM_URI,
                COVERAGE_SUBJECT_KEY_ALGORITHM_URI,
                RATCHET_EVALUATION_PROCEDURE_URI,
            ],
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "content-derived document, subject, debt, and violation IDs",
                "exact policy, bundle, assessment, baseline, and report refs",
                "independently pinned accepted baseline and migration tip IDs",
                "canonical unique rules, groups, debts, and classifications",
                "language-neutral Behavior and coverage projections",
                "complete comparison domain and rule coverage before advance",
                "fail-first Behavior, coverage, and combined outcomes",
                "granular inherited, changed, resolved, and reintroduced debt",
                "immutable predecessor-bound tightening and protections",
                "source-complete v1 migration without reset or downgrade",
                f"maximum {MAX_RATCHET_RULES} policy rules",
                f"maximum {MAX_RATCHET_SUBJECTS} current subjects",
                f"maximum {MAX_RATCHET_VIOLATIONS} violation identities",
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
        description="Generate or check the published ratchet v2 schemas."
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
    rendered = {
        options.output_directory / path.name: content
        for path, content in render_schemas().items()
    }
    if options.check:
        stale = [
            path
            for path, content in rendered.items()
            if not path.is_file()
            or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0
    options.output_directory.mkdir(parents=True, exist_ok=True)
    for path, content in rendered.items():
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
