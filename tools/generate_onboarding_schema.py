"""Generate deterministic UCF onboarding profile 1.0.0 schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from ucf.ir.codec import MAX_JSON_NESTING
from ucf.onboarding import (
    DECISION_SET_SCHEMA_URI,
    DISCOVERY_REQUEST_SCHEMA_URI,
    DISCOVERY_RESULT_SCHEMA_URI,
    MAX_DISCOVERY_CANDIDATES,
    MAX_DISCOVERY_DIAGNOSTICS,
    ONBOARDING_BUNDLE_SCHEMA_URI,
    ONBOARDING_VERSION,
    DecisionSet,
    DiscoveryRequest,
    DiscoveryResult,
    OnboardingBundle,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "ucf" / "schemas" / "onboarding" / "v1"
)
REQUEST_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "discovery-request.schema.json"
)
RESULT_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "discovery-result.schema.json"
)
DECISION_SCHEMA_OUTPUT = (
    DEFAULT_OUTPUT_DIRECTORY / "decision-set.schema.json"
)
BUNDLE_SCHEMA_OUTPUT = DEFAULT_OUTPUT_DIRECTORY / "bundle.schema.json"

_DOCUMENTS = (
    (
        REQUEST_SCHEMA_OUTPUT,
        DiscoveryRequest,
        DISCOVERY_REQUEST_SCHEMA_URI,
        "discovery_request_profile",
        "UCF discovery request profile 1.0.0",
    ),
    (
        RESULT_SCHEMA_OUTPUT,
        DiscoveryResult,
        DISCOVERY_RESULT_SCHEMA_URI,
        "discovery_result_profile",
        "UCF discovery result profile 1.0.0",
    ),
    (
        DECISION_SCHEMA_OUTPUT,
        DecisionSet,
        DECISION_SET_SCHEMA_URI,
        "decision_set_profile",
        "UCF onboarding decision set profile 1.0.0",
    ),
    (
        BUNDLE_SCHEMA_OUTPUT,
        OnboardingBundle,
        ONBOARDING_BUNDLE_SCHEMA_URI,
        "onboarding_bundle",
        "UCF deterministic onboarding bundle profile 1.0.0",
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
                "Generated deterministically from UCF onboarding profile "
                "1.0.0 models; do not edit by hand. Cross-document identity, "
                "reference, candidate, decision, materialization, trust, and "
                "summary checks remain runtime semantics."
            ),
            "$id": schema_uri,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "x-ucf-document-kind": document_kind,
            "x-ucf-onboarding-version": ONBOARDING_VERSION,
            "x-ucf-runtime-semantic-checks": [
                "strict UTF-8 and duplicate-member JSON decoding",
                f"maximum JSON nesting depth {MAX_JSON_NESTING}",
                "complete inventory canonical digest and source revision",
                "exact discovery capability and profile coordinates",
                "typed inventory reference resolution and target kinds",
                "content-derived candidate and decision identities",
                "canonical candidate, evidence, decision, and entity order",
                "closed proposal graph topology and required input bindings",
                "exact accepted, edited, rejected, uncertain decision coverage",
                "stale discovery, candidate, and replacement rejection",
                "accepted and edited materialization only",
                "exact Behavior IR and Trust IR document binding",
                "observed and declared claims without confidence promotion",
                "derived baseline document, disposition, coverage, and claim summaries",
                f"maximum {MAX_DISCOVERY_CANDIDATES} discovery candidates",
                f"maximum {MAX_DISCOVERY_DIAGNOSTICS} discovery diagnostics",
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
        description="Generate or check the published onboarding schemas."
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
    rendered = render_schemas()
    expected = {
        options.output_directory / path.name: content
        for path, content in rendered.items()
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
