from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator
from tools.generate_change_lifecycle_schema import (
    DEFAULT_OUTPUT_DIRECTORY,
    render_schemas,
)

from ucf.change_lifecycle import (
    ChangeLifecycleValidationError,
    parse_change_proposal_json,
)

from ._fixture_factory import DEFAULT_FIXTURE_DIRECTORY

_POSITIVE_SCHEMA_BY_FIXTURE = {
    "proposal.json": "proposal.schema.json",
    "behavior-delta.json": "behavior-delta.schema.json",
    "task-graph.json": "task-graph.schema.json",
    "implementation-record.json": "implementation-record.schema.json",
    "verification-record.json": "verification-record.schema.json",
    "archive-record.json": "archive-record.schema.json",
}

_COMMON_RUNTIME_CHECKS = (
    "strict UTF-8 and duplicate-member JSON decoding",
    "maximum JSON nesting depth 128",
)
_RUNTIME_CHECKS_BY_KIND = {
    "change_proposal": (
        *_COMMON_RUNTIME_CHECKS,
        "canonical RFC 4648 base64 with decoded artifact byte bound 262144",
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
        *_COMMON_RUNTIME_CHECKS,
        "exact proposal, base behavior, and final behavior context",
        ("delta entry subjects bind their top-level behavior document coordinates"),
        "exhaustive canonical behavior delta",
    ),
    "task_graph": (
        *_COMMON_RUNTIME_CHECKS,
        "exact behavior delta and proposal context",
        "resolved acyclic canonically ordered task dependency graph",
        "exact task-to-delta subject coverage",
        "exact task source artifact and OpenSpec checkbox coordinates",
    ),
    "implementation_record": (
        *_COMMON_RUNTIME_CHECKS,
        "exact task graph, behavior delta, and proposal context",
        "completed tasks before implementation evidence",
        (
            "one context-validated imported evidence result and "
            "durable validation receipt per supported delta subject"
        ),
        "removed behavior requires a separate final-state absence-evidence profile",
    ),
    "verification_record": (
        *_COMMON_RUNTIME_CHECKS,
        (
            "exact implementation record, task graph, behavior delta, "
            "and proposal context"
        ),
        "passed evidence only before verification acceptance",
        "verification subjects exactly match accepted implementation evidence",
    ),
    "archive_record": (
        *_COMMON_RUNTIME_CHECKS,
        (
            "exact proposal, behavior delta, task graph, implementation, "
            "and verification predecessor chain"
        ),
        "exact final behavior snapshot matches the accepted behavior delta",
    ),
}


def test_change_lifecycle_schemas_are_current_and_closed() -> None:
    rendered = render_schemas()
    assert len(rendered) == 6
    for path, expected in rendered.items():
        assert path.parent == DEFAULT_OUTPUT_DIRECTORY
        assert path.read_text(encoding="utf-8") == expected
        schema = json.loads(expected)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == ("https://json-schema.org/draft/2020-12/schema")
        assert schema["$id"].startswith("urn:ucf:change-lifecycle:")
        assert schema["x-ucf-change-lifecycle-version"] == "1.0.0"
        assert schema["additionalProperties"] is False
        _assert_every_object_shape_is_closed(schema)


def test_runtime_semantic_checks_are_exactly_document_local() -> None:
    rendered = render_schemas()
    checks_by_kind = {
        schema["x-ucf-document-kind"]: tuple(schema["x-ucf-runtime-semantic-checks"])
        for schema in (json.loads(content) for content in rendered.values())
    }

    assert checks_by_kind == _RUNTIME_CHECKS_BY_KIND
    for kind, checks in checks_by_kind.items():
        other_stage_checks = {
            check
            for other_kind, expected in _RUNTIME_CHECKS_BY_KIND.items()
            if other_kind != kind
            for check in expected
            if check not in _COMMON_RUNTIME_CHECKS
        }
        assert set(checks).isdisjoint(other_stage_checks)


@pytest.mark.parametrize(
    "filename",
    [
        "proposal.schema.json",
        "behavior-delta.schema.json",
        "task-graph.schema.json",
        "implementation-record.schema.json",
        "verification-record.schema.json",
        "archive-record.schema.json",
    ],
)
def test_schema_rejects_unknown_root_field(filename: str) -> None:
    schema = json.loads(
        (DEFAULT_OUTPUT_DIRECTORY / filename).read_text(encoding="utf-8")
    )
    fixture_name = next(
        fixture
        for fixture, schema_name in _POSITIVE_SCHEMA_BY_FIXTURE.items()
        if schema_name == filename
    )
    document = json.loads(
        (DEFAULT_FIXTURE_DIRECTORY / "positive" / fixture_name).read_text(
            encoding="utf-8"
        )
    )
    document["unknown"] = True
    assert tuple(Draft202012Validator(schema).iter_errors(document))


def test_positive_documents_match_exactly_one_lifecycle_schema() -> None:
    schemas = {
        path.name: Draft202012Validator(json.loads(content))
        for path, content in render_schemas().items()
    }
    for fixture_name, expected_schema in _POSITIVE_SCHEMA_BY_FIXTURE.items():
        document = json.loads(
            (DEFAULT_FIXTURE_DIRECTORY / "positive" / fixture_name).read_text(
                encoding="utf-8"
            )
        )
        accepted = {
            name
            for name, validator in schemas.items()
            if not tuple(validator.iter_errors(document))
        }
        assert accepted == {expected_schema}


def test_schema_and_runtime_only_negatives_are_distinguished() -> None:
    cases = (
        (
            "stale-delta-proposal-reference.json",
            "behavior-delta.schema.json",
        ),
        ("cyclic-task-dependency.json", "task-graph.schema.json"),
        (
            "stale-verification-reference.json",
            "verification-record.schema.json",
        ),
        (
            "unsupported-evidence-capability.json",
            "implementation-record.schema.json",
        ),
    )
    for fixture_name, schema_name in cases:
        schema = json.loads(
            (DEFAULT_OUTPUT_DIRECTORY / schema_name).read_text(encoding="utf-8")
        )
        document = json.loads(
            (DEFAULT_FIXTURE_DIRECTORY / "invalid" / fixture_name).read_text(
                encoding="utf-8"
            )
        )
        assert not tuple(Draft202012Validator(schema).iter_errors(document))
        assert schema["x-ucf-runtime-semantic-checks"]

    nested_unknown = json.loads(
        (DEFAULT_FIXTURE_DIRECTORY / "invalid" / "unknown-nested-field.json").read_text(
            encoding="utf-8"
        )
    )
    proposal_schema = json.loads(
        (DEFAULT_OUTPUT_DIRECTORY / "proposal.schema.json").read_text(encoding="utf-8")
    )
    assert tuple(Draft202012Validator(proposal_schema).iter_errors(nested_unknown))


def test_proposal_schema_names_exact_runtime_artifact_profile_checks() -> None:
    proposal_schema = json.loads(
        (DEFAULT_OUTPUT_DIRECTORY / "proposal.schema.json").read_text(encoding="utf-8")
    )
    required_checks = set(_RUNTIME_CHECKS_BY_KIND["change_proposal"])
    assert required_checks <= set(proposal_schema["x-ucf-runtime-semantic-checks"])

    validator = Draft202012Validator(proposal_schema)
    for fixture_name in (
        "invalid-artifact-utf8.json",
        "noncanonical-artifact-base64.json",
        "mismatched-artifact-digest.json",
        "unsafe-artifact-path.json",
        "artifact-role-path-mismatch.json",
        "binary-tasks-media-mismatch.json",
        "noncanonical-delta-spec-layout.json",
        "orphan-base-spec.json",
        "unsupported-profile-metadata.json",
        "missing-profile-declaration.json",
        "excessive-profile-nesting.json",
        "file-directory-prefix-collision.json",
    ):
        payload = (DEFAULT_FIXTURE_DIRECTORY / "invalid" / fixture_name).read_bytes()
        assert not tuple(validator.iter_errors(json.loads(payload)))
        with pytest.raises(ChangeLifecycleValidationError):
            parse_change_proposal_json(payload)


def _assert_every_object_shape_is_closed(value: object) -> None:
    if isinstance(value, dict):
        if value.get("type") == "object" or "properties" in value:
            assert value.get("additionalProperties") is False
        for nested in value.values():
            _assert_every_object_shape_is_closed(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_every_object_shape_is_closed(nested)
