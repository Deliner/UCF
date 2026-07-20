from __future__ import annotations

import json

from jsonschema import Draft202012Validator
from tools.generate_change_governance_schema import (
    DEFAULT_OUTPUT_DIRECTORY,
    render_schemas,
)


def test_change_governance_schemas_are_current_closed_and_distinct() -> None:
    rendered = render_schemas()

    assert {path.name for path in rendered} == {
        "impact-report.schema.json",
        "decision-assessment.schema.json",
        "decision-declaration.schema.json",
        "gate-evaluation.schema.json",
    }
    document_kinds = set()
    for path, expected in rendered.items():
        assert path.parent == DEFAULT_OUTPUT_DIRECTORY
        assert path.read_text(encoding="utf-8") == expected
        schema = json.loads(expected)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == ("https://json-schema.org/draft/2020-12/schema")
        assert schema["$id"].startswith("urn:ucf:change-governance:")
        assert schema["x-ucf-change-governance-version"] == "1.0.0"
        assert schema["additionalProperties"] is False
        document_kinds.add(schema["x-ucf-document-kind"])
        _assert_every_object_shape_is_closed(schema)

    assert document_kinds == {
        "impact_report",
        "decision_assessment",
        "decision_declaration",
        "gate_evaluation",
    }


def test_schema_runtime_annotations_do_not_claim_authentication() -> None:
    rendered = render_schemas()
    annotations = {
        schema["x-ucf-document-kind"]: tuple(schema["x-ucf-runtime-semantic-checks"])
        for schema in (json.loads(content) for content in rendered.values())
    }

    assert all(
        "authenticated" not in check
        and "signature" not in check
        and "non-repudiation" not in check
        for checks in annotations.values()
        for check in checks
    )
    assert (
        "exact proposal, delta, base, and final behavior context"
        in (annotations["impact_report"])
    )
    assert (
        "exact six-class assessment with no derived downgrade"
        in (annotations["decision_assessment"])
    )
    assert (
        "exact applicable decision-class coverage"
        in (annotations["decision_declaration"])
    )
    assert (
        "full predecessor replay and gate recomputation"
        in (annotations["gate_evaluation"])
    )


def _assert_every_object_shape_is_closed(value: object) -> None:
    if isinstance(value, dict):
        if value.get("type") == "object" or "properties" in value:
            assert value.get("additionalProperties") is False
        for nested in value.values():
            _assert_every_object_shape_is_closed(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_every_object_shape_is_closed(nested)
