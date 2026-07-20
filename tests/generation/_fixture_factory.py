from __future__ import annotations

import argparse
import json
from pathlib import Path

from ucf.generation import (
    GenerationRequest,
    canonical_generation_json,
    derive_generation_request_id,
    derive_generation_result_id,
)

from ._support import generation_request, generation_result

REPOSITORY_ROOT = Path(__file__).parents[2]
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "generation" / "v1"
)


def generated_fixtures() -> dict[Path, bytes]:
    request = generation_request()
    result = generation_result(request=request)
    request_bytes = canonical_generation_json(request)
    result_bytes = canonical_generation_json(result)

    request_payload = request.model_dump(mode="json")
    result_payload = result.model_dump(mode="json")

    unknown_request = _clone(request_payload)
    unknown_request["future"] = True

    unsupported_request = _clone(request_payload)
    unsupported_request["generation_version"] = "2.0.0"

    stale_request = _clone(request_payload)
    stale_request["id"] = f"generation-request.{'f' * 64}"

    noncanonical_behavior = _clone(request_payload)
    noncanonical_behavior["behavior"]["entities"].reverse()
    noncanonical_behavior = _identified_request_payload(
        noncanonical_behavior
    )

    broken_subject = _clone(request_payload)
    broken_subject["subject"]["target_id"] = "action.missing"
    for field in ("inputs", "expected_outputs"):
        for value in broken_subject[field]:
            value["port"]["owner"]["target_id"] = "action.missing"
    broken_subject = _identified_request_payload(broken_subject)

    wrong_subject_kind = _clone(request_payload)
    wrong_subject_kind["subject"]["target_kind"] = "use_case"

    missing_input = _clone(request_payload)
    missing_input["inputs"] = []
    missing_input = _identified_request_payload(missing_input)

    unknown_input = _clone(request_payload)
    unknown_input["inputs"][0]["port"]["name"] = "missing-port"
    unknown_input = _identified_request_payload(unknown_input)

    wrong_input_kind = _clone(request_payload)
    wrong_input_kind["inputs"][0]["value"] = {
        "kind": "integer",
        "value": 1,
    }
    wrong_input_kind = _identified_request_payload(wrong_input_kind)

    noncanonical_profile = _clone(request_payload)
    noncanonical_profile["profile_configuration"]["entries"].reverse()

    duplicate_profile = _clone(request_payload)
    duplicate_profile["profile_configuration"]["entries"].append(
        _clone(
            duplicate_profile["profile_configuration"]["entries"][0]
        )
    )

    unsupported_capability = _clone(request_payload)
    unsupported_capability["capability"]["name"] = (
        "org.ucf.adapter.unsupported"
    )

    unversioned_procedure = _clone(request_payload)
    unversioned_procedure["adapter_procedure_uri"] = (
        "urn:ucf:python-pytest:function-test"
    )

    unsafe_path = _clone(result_payload)
    unsafe_path["files"][0]["path"] = "../escape.py"

    trailing_period = _clone(result_payload)
    trailing_period["files"][0]["path"] = "test.py."

    mismatched_digest = _clone(result_payload)
    mismatched_digest["files"][0]["content_digest"]["value"] = "f" * 64

    duplicate_path = _clone(result_payload)
    duplicate_path["files"] = [
        {
            **duplicate_path["files"][0],
            "path": "A.py",
        },
        {
            **duplicate_path["files"][0],
            "path": "a.py",
        },
    ]

    ancestor_collision = _clone(result_payload)
    ancestor_collision["files"] = [
        {
            **ancestor_collision["files"][0],
            "path": "nested",
        },
        {
            **ancestor_collision["files"][0],
            "path": "nested/test.py",
        },
    ]

    noncanonical_files = _clone(result_payload)
    noncanonical_files["files"] = [
        {
            **noncanonical_files["files"][0],
            "path": "z.py",
        },
        {
            **noncanonical_files["files"][0],
            "path": "a.py",
        },
    ]

    ambiguous_ownership = _clone(result_payload)
    ambiguous_ownership["files"][0]["ownership"] = "user_owned"

    stale_context_request = request.model_copy(
        update={
            "environment": request.environment.model_copy(
                update={
                    "revision": request.environment.revision.model_copy(
                        update={"value": "f" * 64}
                    )
                }
            )
        }
    )
    stale_context_request = stale_context_request.model_copy(
        update={
            "id": derive_generation_request_id(stale_context_request)
        }
    )
    stale_context_result = generation_result(
        request=stale_context_request
    )
    stale_producer_result = result.model_copy(
        update={
            "producer": result.producer.model_copy(
                update={"version": "1.0.1"}
            )
        }
    )
    stale_producer_result = stale_producer_result.model_copy(
        update={"id": derive_generation_result_id(stale_producer_result)}
    )

    return {
        Path("positive/request.json"): request_bytes,
        Path("positive/result.json"): result_bytes,
        Path("invalid/unknown-root-field.json"): _canonical(unknown_request),
        Path("invalid/unsupported-version.json"): _canonical(
            unsupported_request
        ),
        Path("invalid/stale-request-id.json"): _canonical(stale_request),
        Path("invalid/noncanonical-behavior-order.json"): _canonical(
            noncanonical_behavior
        ),
        Path("invalid/broken-subject-reference.json"): _canonical(
            broken_subject
        ),
        Path("invalid/wrong-subject-kind.json"): _canonical(
            wrong_subject_kind
        ),
        Path("invalid/missing-required-input.json"): _canonical(
            missing_input
        ),
        Path("invalid/unknown-input-port.json"): _canonical(unknown_input),
        Path("invalid/wrong-input-value-kind.json"): _canonical(
            wrong_input_kind
        ),
        Path("invalid/noncanonical-profile.json"): _canonical(
            noncanonical_profile
        ),
        Path("invalid/duplicate-profile-entry.json"): _canonical(
            duplicate_profile
        ),
        Path("invalid/unsupported-capability.json"): _canonical(
            unsupported_capability
        ),
        Path("invalid/unversioned-procedure.json"): _canonical(
            unversioned_procedure
        ),
        Path("invalid/unsafe-path.json"): _canonical(unsafe_path),
        Path("invalid/trailing-period-path.json"): _canonical(
            trailing_period
        ),
        Path("invalid/content-digest-mismatch.json"): _canonical(
            mismatched_digest
        ),
        Path("invalid/duplicate-path.json"): _canonical(duplicate_path),
        Path("invalid/ancestor-path-collision.json"): _canonical(
            ancestor_collision
        ),
        Path("invalid/noncanonical-file-order.json"): _canonical(
            noncanonical_files
        ),
        Path("invalid/ambiguous-ownership.json"): _canonical(
            ambiguous_ownership
        ),
        Path("invalid/duplicate-json-member.json"): request_bytes.replace(
            b'{"adapter_procedure_uri":',
            b'{"adapter_procedure_uri":"duplicate",'
            b'"adapter_procedure_uri":',
            1,
        ),
        Path(
            "invalid-context/stale-request-context.json"
        ): canonical_generation_json(stale_context_result),
        Path(
            "invalid-context/stale-producer-context.json"
        ): canonical_generation_json(stale_producer_result),
    }


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _clone(value):
    return json.loads(json.dumps(value))


def _identified_request_payload(payload: dict) -> dict:
    request = GenerationRequest.model_validate_json(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    )
    identified = request.model_copy(
        update={"id": derive_generation_request_id(request)}
    )
    return identified.model_dump(mode="json")


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check generation profile wire fixtures."
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
        options.output_directory / path: content
        for path, content in generated_fixtures().items()
    }
    if options.check:
        actual = {
            path
            for path in options.output_directory.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        stale = sorted(
            {
                path
                for path, content in expected.items()
                if path.is_symlink()
                or not path.is_file()
                or path.read_bytes() != content
            }
            | (actual - set(expected))
        )
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0
    options.output_directory.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
