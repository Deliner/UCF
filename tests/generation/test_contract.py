from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from ucf.adapter_protocol import AdapterPayload
from ucf.generation import (
    MAX_GENERATED_FILE_BYTES,
    MAX_GENERATED_TOTAL_BYTES,
    GeneratedFile,
    GenerationErrorCode,
    GenerationValidationError,
    canonical_generation_json,
    derive_generation_request_id,
    derive_generation_result_id,
    generation_request_from_payload,
    generation_request_to_payload,
    generation_result_from_payload,
    generation_result_to_payload,
    parse_generation_request_json,
    parse_generation_result_json,
    validate_generation_request,
    validate_generation_result,
)
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import (
    Digest,
    IntegerValue,
    RecordEntry,
    RecordValue,
    StringValue,
)

from ._support import (
    PYTHON_PROFILE_CAPABILITY,
    generation_request,
    generation_result,
)


def _identified_request(request):
    return request.model_copy(
        update={"id": derive_generation_request_id(request)}
    )


def _identified_result(result):
    return result.model_copy(
        update={"id": derive_generation_result_id(result)}
    )


def test_request_is_exact_canonical_and_context_valid() -> None:
    request = generation_request()
    encoded = canonical_generation_json(request)

    assert encoded.endswith(b"\n")
    assert parse_generation_request_json(encoded) == request
    assert canonical_generation_json(parse_generation_request_json(encoded)) == encoded
    assert request.id == derive_generation_request_id(request)
    validate_generation_request(request)


def test_request_rejects_noncanonical_embedded_behavior_order() -> None:
    request = generation_request()
    canonical_behavior = parse_ir_json(canonical_ir_json(request.behavior))
    canonical_request = _identified_request(
        request.model_copy(update={"behavior": canonical_behavior})
    )
    validate_generation_request(canonical_request)

    noncanonical_behavior = canonical_behavior.model_copy(
        update={"entities": tuple(reversed(canonical_behavior.entities))}
    )
    noncanonical_request = _identified_request(
        canonical_request.model_copy(update={"behavior": noncanonical_behavior})
    )

    assert canonical_ir_json(noncanonical_behavior) == canonical_ir_json(
        canonical_behavior
    )
    assert noncanonical_request.id != canonical_request.id
    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.NON_CANONICAL_ORDER.value,
    ):
        validate_generation_request(noncanonical_request)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("generation_version",), "2.0.0"),
        (("schema_uri",), "urn:ucf:generation:request:2.0.0"),
        (("capability", "name"), "org.ucf.adapter.verification"),
        (("capability", "version"), "2.0.0"),
        (("profile_capability", "name"), "org.ucf.adapter.generation"),
        (("profile_capability", "version"), "2.0.0"),
        (
            ("profile_procedure_uri",),
            "urn:ucf:generation:manifest:2.0.0",
        ),
        (("adapter_procedure_uri",), "not-versioned"),
    ],
)
def test_request_rejects_incompatible_coordinates(
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = generation_request().model_dump(mode="json")
    target = payload
    for coordinate in path[:-1]:
        target = target[coordinate]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        parse_generation_request_json(json.dumps(payload))


def test_request_rejects_unknown_duplicate_and_stale_identity() -> None:
    payload = generation_request().model_dump(mode="json")
    payload["future"] = True
    with pytest.raises(ValidationError):
        parse_generation_request_json(json.dumps(payload))

    encoded = canonical_generation_json(generation_request())
    duplicate = encoded.replace(
        b'{"adapter_procedure_uri":',
        b'{"adapter_procedure_uri":"duplicate","adapter_procedure_uri":',
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_generation_request_json(duplicate)

    stale = generation_request().model_copy(
        update={"id": f"generation-request.{'f' * 64}"}
    )
    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.REQUEST_IDENTITY_MISMATCH.value,
    ):
        validate_generation_request(stale)


def test_request_rejects_behavior_subject_and_port_context_mismatch() -> None:
    request = generation_request()
    stale_subject = request.subject.model_copy(
        update={
            "canonical_digest": Digest(
                kind="digest",
                algorithm="sha-256",
                value="f" * 64,
            )
        }
    )
    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.DOCUMENT_IDENTITY_MISMATCH.value,
    ):
        validate_generation_request(
            _identified_request(request.model_copy(update={"subject": stale_subject}))
        )

    broken_subject = request.subject.model_copy(
        update={"target_id": "action.missing"}
    )
    broken_input = request.inputs[0].model_copy(
        update={
            "port": request.inputs[0].port.model_copy(
                update={
                    "owner": request.inputs[0].port.owner.model_copy(
                        update={"target_id": "action.missing"}
                    )
                }
            )
        }
    )
    broken_output = request.expected_outputs[0].model_copy(
        update={
            "port": request.expected_outputs[0].port.model_copy(
                update={
                    "owner": request.expected_outputs[0].port.owner.model_copy(
                        update={"target_id": "action.missing"}
                    )
                }
            )
        }
    )
    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.BROKEN_REFERENCE.value,
    ):
        validate_generation_request(
            _identified_request(
                request.model_copy(
                    update={
                        "subject": broken_subject,
                        "inputs": (broken_input,),
                        "expected_outputs": (broken_output,),
                    }
                )
            )
        )

    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.INCOMPLETE_PORT_VALUES.value,
    ):
        validate_generation_request(
            _identified_request(request.model_copy(update={"inputs": ()}))
        )

    wrong_value = request.inputs[0].model_copy(
        update={"value": IntegerValue(kind="integer", value=1)}
    )
    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.VALUE_KIND_MISMATCH.value,
    ):
        validate_generation_request(
            _identified_request(request.model_copy(update={"inputs": (wrong_value,)}))
        )


def test_request_rejects_noncanonical_or_duplicate_profile_configuration() -> None:
    request = generation_request()
    entries = request.profile_configuration.entries

    payload = request.model_dump(mode="json")
    payload["profile_configuration"]["entries"].reverse()
    with pytest.raises(ValidationError, match="canonical"):
        parse_generation_request_json(json.dumps(payload))

    duplicate = request.profile_configuration.model_copy(
        update={
            "entries": (
                entries[0],
                RecordEntry(
                    kind="record_entry",
                    name=entries[0].name,
                    value=StringValue(kind="string", value="other"),
                ),
            )
        }
    )
    payload = request.model_dump(mode="json")
    payload["profile_configuration"] = duplicate.model_dump(mode="json")
    with pytest.raises((ValidationError, ValueError), match="duplicate"):
        parse_generation_request_json(json.dumps(payload))


def test_result_is_exact_canonical_complete_and_context_bound() -> None:
    request = generation_request()
    result = generation_result(request=request)
    encoded = canonical_generation_json(result)

    assert parse_generation_result_json(encoded) == result
    assert canonical_generation_json(parse_generation_result_json(encoded)) == encoded
    assert result.id == derive_generation_result_id(result)
    validate_generation_result(
        result,
        request=request,
        initialized_adapter=result.producer,
        negotiated_capabilities={
            result.capability.name: result.capability.version,
            result.profile_capability.name: result.profile_capability.version,
        },
    )


def test_result_rejects_unknown_duplicate_noncanonical_and_forged_file_data() -> None:
    result = generation_result()
    payload = result.model_dump(mode="json")
    payload["future"] = True
    with pytest.raises(ValidationError):
        parse_generation_result_json(json.dumps(payload))

    encoded = canonical_generation_json(result)
    duplicate = encoded.replace(
        b'{"byte_size":',
        b'{"byte_size":1,"byte_size":',
        1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_generation_result_json(duplicate)

    file = result.files[0]
    forged = file.model_copy(update={"byte_size": file.byte_size + 1})
    with pytest.raises(ValidationError, match="byte size"):
        parse_generation_result_json(
            json.dumps(
                _identified_result(
                    result.model_copy(update={"files": (forged,)})
                ).model_dump(mode="json")
            )
        )

    forged = file.model_copy(
        update={
            "content_digest": Digest(
                kind="digest",
                algorithm="sha-256",
                value="f" * 64,
            )
        }
    )
    with pytest.raises(ValidationError, match="digest"):
        parse_generation_result_json(
            json.dumps(
                _identified_result(
                    result.model_copy(update={"files": (forged,)})
                ).model_dump(mode="json")
            )
        )


@pytest.mark.parametrize(
    "path",
    [
        "../escape.py",
        "/absolute.py",
        "nested//empty.py",
        "nested/../escape.py",
        "nested\\escape.py",
        "a.py.",
        "foo./a.py",
        "dir.",
        ".",
    ],
)
def test_result_rejects_unsafe_generated_paths(path: str) -> None:
    result = generation_result()
    forged = result.files[0].model_copy(update={"path": path})

    with pytest.raises(ValidationError, match="path"):
        parse_generation_result_json(
            json.dumps(
                _identified_result(
                    result.model_copy(update={"files": (forged,)})
                ).model_dump(mode="json")
            )
        )


def test_result_rejects_duplicate_casefold_paths_and_noncanonical_order() -> None:
    result = generation_result()
    first = result.files[0].model_copy(update={"path": "A.py"})
    second = result.files[0].model_copy(update={"path": "a.py"})
    payload = _identified_result(
        result.model_copy(update={"files": (first, second)})
    ).model_dump(mode="json")
    with pytest.raises(ValidationError, match="duplicate"):
        parse_generation_result_json(json.dumps(payload))

    first = result.files[0].model_copy(update={"path": "z.py"})
    second = result.files[0].model_copy(update={"path": "a.py"})
    payload = _identified_result(
        result.model_copy(update={"files": (first, second)})
    ).model_dump(mode="json")
    with pytest.raises(ValidationError, match="canonical"):
        parse_generation_result_json(json.dumps(payload))


def test_result_rejects_file_directory_ancestor_collisions() -> None:
    result = generation_result()
    first = result.files[0].model_copy(update={"path": "nested"})
    second = result.files[0].model_copy(update={"path": "nested/test.py"})
    payload = _identified_result(
        result.model_copy(update={"files": (first, second)})
    ).model_dump(mode="json")

    with pytest.raises(ValidationError, match="ancestor"):
        parse_generation_result_json(json.dumps(payload))


def test_valid_result_must_fit_the_exact_protocol_response_frame() -> None:
    request = generation_request()
    large_configuration = RecordValue(
        kind="record",
        entries=(
            RecordEntry(
                kind="record_entry",
                name="blob",
                value=StringValue(kind="string", value="x" * 600_000),
            ),
        ),
    )
    large_request = _identified_request(
        request.model_copy(
            update={"profile_configuration": large_configuration}
        )
    )
    validate_generation_request(large_request)

    content = "x" * MAX_GENERATED_FILE_BYTES
    encoded = content.encode("utf-8")
    files = tuple(
        GeneratedFile(
            kind="generated_file",
            path=f"f{index}.txt",
            ownership="generator_owned",
            media_type="text/plain",
            encoding="utf-8",
            byte_size=len(encoded),
            content_digest=Digest(
                kind="digest",
                algorithm="sha-256",
                value=hashlib.sha256(encoded).hexdigest(),
            ),
            content=content,
        )
        for index in range(
            MAX_GENERATED_TOTAL_BYTES // MAX_GENERATED_FILE_BYTES
        )
    )
    result = _identified_result(
        generation_result(request=large_request).model_copy(
            update={"files": files}
        )
    )

    with pytest.raises(
        GenerationValidationError,
        match="frame_budget_exceeded",
    ):
        validate_generation_result(
            result,
            request=large_request,
            initialized_adapter=result.producer,
            negotiated_capabilities={
                result.capability.name: result.capability.version,
                result.profile_capability.name: (
                    result.profile_capability.version
                ),
            },
        )


def test_result_rejects_stale_request_producer_and_capabilities() -> None:
    request = generation_request()
    result = generation_result(request=request)
    other_request = _identified_request(
        request.model_copy(
            update={
                "profile_configuration": request.profile_configuration.model_copy(
                    update={
                        "entries": (
                            request.profile_configuration.entries[0],
                            request.profile_configuration.entries[1].model_copy(
                                update={
                                    "value": StringValue(
                                        kind="string",
                                        value="other_module",
                                    )
                                }
                            ),
                        )
                    }
                )
            }
        )
    )
    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.REQUEST_IDENTITY_MISMATCH.value,
    ):
        validate_generation_result(
            result,
            request=other_request,
            initialized_adapter=result.producer,
            negotiated_capabilities={
                result.capability.name: result.capability.version,
                result.profile_capability.name: result.profile_capability.version,
            },
        )

    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.PRODUCER_IDENTITY_MISMATCH.value,
    ):
        validate_generation_result(
            result,
            request=request,
            initialized_adapter=result.producer.model_copy(
                update={"version": "1.0.1"}
            ),
            negotiated_capabilities={
                result.capability.name: result.capability.version,
                result.profile_capability.name: result.profile_capability.version,
            },
        )

    with pytest.raises(
        GenerationValidationError,
        match=GenerationErrorCode.CAPABILITY_MISMATCH.value,
    ):
        validate_generation_result(
            result,
            request=request,
            initialized_adapter=result.producer,
            negotiated_capabilities={
                result.capability.name: result.capability.version,
                PYTHON_PROFILE_CAPABILITY: "1.0.1",
            },
        )


def test_request_and_result_round_trip_only_their_exact_adapter_payloads() -> None:
    request = generation_request()
    result = generation_result(request=request)

    assert generation_request_from_payload(
        generation_request_to_payload(request)
    ) == request
    assert generation_result_from_payload(
        generation_result_to_payload(result)
    ) == result

    with pytest.raises(ValueError, match="coordinates"):
        generation_request_from_payload(generation_result_to_payload(result))

    payload = generation_request_to_payload(request).model_copy(
        update={"schema_version": "1.1.0"}
    )
    with pytest.raises(ValueError, match="coordinates"):
        generation_request_from_payload(payload)

    with pytest.raises(ValueError, match="adapter payload"):
        generation_request_from_payload(
            "not-a-payload"  # type: ignore[arg-type]
        )

    malformed = AdapterPayload(
        kind="adapter_payload",
        schema_uri=generation_request_to_payload(request).schema_uri,
        schema_version=generation_request_to_payload(request).schema_version,
        value=StringValue(kind="string", value="not-a-record"),
    )
    with pytest.raises(ValueError, match="root"):
        generation_request_from_payload(malformed)


def test_outbound_wire_encoders_reject_the_opposite_exact_model() -> None:
    request = generation_request()
    result = generation_result(request=request)

    with pytest.raises(TypeError, match="exact generation request"):
        generation_request_to_payload(result)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="exact generation result"):
        generation_result_to_payload(request)  # type: ignore[arg-type]


def test_outbound_encoders_revalidate_structurally_invalid_model_copies() -> None:
    request = generation_request()
    result = generation_result(request=request)
    invalid_request = request.model_copy(
        update={"generation_version": "9.0.0"}
    )
    invalid_file = result.files[0].model_copy(
        update={"path": "../escape.py"}
    )
    invalid_result = result.model_copy(
        update={"files": (invalid_file,)}
    )

    for document, encoder in (
        (invalid_request, canonical_generation_json),
        (invalid_request, generation_request_to_payload),
        (invalid_result, canonical_generation_json),
        (invalid_result, generation_result_to_payload),
    ):
        with pytest.raises(
            GenerationValidationError,
            match=GenerationErrorCode.INVALID_STRUCTURE.value,
        ):
            encoder(document)  # type: ignore[arg-type]
