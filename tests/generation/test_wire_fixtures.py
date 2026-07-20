from __future__ import annotations

from pathlib import Path

import pytest

from ucf.generation import (
    GenerationErrorCode,
    GenerationValidationError,
    parse_generation_request_json,
    parse_generation_result_json,
    validate_generation_result,
)

from ._fixture_factory import DEFAULT_OUTPUT_DIRECTORY, generated_fixtures
from ._support import (
    PYTHON_PROFILE_CAPABILITY,
    generation_request,
    generation_result,
)


def test_positive_wire_fixtures_are_exact_and_parseable() -> None:
    request = parse_generation_request_json(
        (DEFAULT_OUTPUT_DIRECTORY / "positive" / "request.json").read_bytes()
    )
    result = parse_generation_result_json(
        (DEFAULT_OUTPUT_DIRECTORY / "positive" / "result.json").read_bytes()
    )

    assert request == generation_request()
    assert result == generation_result(request=request)


@pytest.mark.parametrize(
    ("name", "parser"),
    [
        ("unknown-root-field.json", parse_generation_request_json),
        ("unsupported-version.json", parse_generation_request_json),
        ("stale-request-id.json", parse_generation_request_json),
        ("duplicate-json-member.json", parse_generation_request_json),
        ("noncanonical-behavior-order.json", parse_generation_request_json),
        ("broken-subject-reference.json", parse_generation_request_json),
        ("wrong-subject-kind.json", parse_generation_request_json),
        ("missing-required-input.json", parse_generation_request_json),
        ("unknown-input-port.json", parse_generation_request_json),
        ("wrong-input-value-kind.json", parse_generation_request_json),
        ("noncanonical-profile.json", parse_generation_request_json),
        ("duplicate-profile-entry.json", parse_generation_request_json),
        ("unsupported-capability.json", parse_generation_request_json),
        ("unversioned-procedure.json", parse_generation_request_json),
        ("unsafe-path.json", parse_generation_result_json),
        ("trailing-period-path.json", parse_generation_result_json),
        ("content-digest-mismatch.json", parse_generation_result_json),
        ("duplicate-path.json", parse_generation_result_json),
        ("ancestor-path-collision.json", parse_generation_result_json),
        ("noncanonical-file-order.json", parse_generation_result_json),
        ("ambiguous-ownership.json", parse_generation_result_json),
    ],
)
def test_negative_wire_fixtures_are_rejected(name: str, parser) -> None:
    with pytest.raises(ValueError):
        parser((DEFAULT_OUTPUT_DIRECTORY / "invalid" / name).read_bytes())


@pytest.mark.parametrize(
    ("name", "code"),
    [
        (
            "stale-request-context.json",
            GenerationErrorCode.REQUEST_IDENTITY_MISMATCH,
        ),
        (
            "stale-producer-context.json",
            GenerationErrorCode.PRODUCER_IDENTITY_MISMATCH,
        ),
    ],
)
def test_contextual_negative_result_fixtures_are_rejected(
    name: str,
    code: GenerationErrorCode,
) -> None:
    request = generation_request()
    result = parse_generation_result_json(
        (
            DEFAULT_OUTPUT_DIRECTORY
            / "invalid-context"
            / name
        ).read_bytes()
    )

    with pytest.raises(GenerationValidationError, match=code.value):
        validate_generation_result(
            result,
            request=request,
            initialized_adapter=generation_result().producer,
            negotiated_capabilities={
                result.capability.name: result.capability.version,
                PYTHON_PROFILE_CAPABILITY: "1.0.0",
            },
        )


def test_wire_fixture_tree_is_exact_and_fresh() -> None:
    expected = {
        DEFAULT_OUTPUT_DIRECTORY / path: content
        for path, content in generated_fixtures().items()
    }
    actual = {
        path
        for path in DEFAULT_OUTPUT_DIRECTORY.rglob("*")
        if path.is_file() or path.is_symlink()
    }

    assert actual == set(expected)
    for path, content in expected.items():
        assert not path.is_symlink()
        assert path.read_bytes() == content


def test_fixture_check_rejects_an_extra_file(tmp_path: Path) -> None:
    from ._fixture_factory import main

    assert main(["--output-directory", str(tmp_path)]) == 0
    (tmp_path / "extra.json").write_text("{}\n", encoding="utf-8")

    assert main(["--output-directory", str(tmp_path), "--check"]) == 1
