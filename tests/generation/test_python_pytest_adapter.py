from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.generation import (
    GENERATION_CAPABILITY,
    generation_request_to_payload,
    generation_result_from_payload,
    validate_generation_result,
)
from ucf.ir.models import (
    RecordEntry,
    RecordValue,
    StringValue,
)

from ._support import (
    PYTHON_PROCEDURE_URI,
    PYTHON_PROFILE_CAPABILITY,
    generation_request,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
ADAPTER = REPOSITORY_ROOT / "adapters" / "python-pytest" / "adapter.py"
EXPECTED_PRODUCER = "org.ucf.adapter.python-pytest"


def _run_adapter(request, *, hash_seed: str):
    async def run():
        process = AdapterProcess(
            command=(
                sys.executable,
                "-I",
                "-B",
                "-X",
                "utf8",
                str(ADAPTER),
            ),
            cwd=REPOSITORY_ROOT,
            requested_capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name=GENERATION_CAPABILITY,
                    minimum_version="1.0.0",
                    required=True,
                ),
                CapabilityRequest(
                    kind="capability_request",
                    name=PYTHON_PROFILE_CAPABILITY,
                    minimum_version="1.0.0",
                    required=True,
                ),
            ),
            timeouts=ProcessTimeouts(operation=5.0),
            environment={"PYTHONHASHSEED": hash_seed},
        )
        initialized = await process.start()
        try:
            payload = await process.call(
                Method.GENERATE,
                generation_request_to_payload(request),
            )
            result = generation_result_from_payload(payload)
            validate_generation_result(
                result,
                request=request,
                initialized_adapter=initialized.adapter,
                negotiated_capabilities={
                    capability.name: capability.version
                    for capability in initialized.capabilities
                },
            )
            stderr = process.stderr_tail
            return initialized, result, stderr
        finally:
            await process.close()

    return asyncio.run(run())


def test_external_adapter_returns_deterministic_complete_python_test() -> None:
    request = generation_request()

    initialized_a, result_a, stderr_a = _run_adapter(
        request,
        hash_seed="1",
    )
    initialized_b, result_b, stderr_b = _run_adapter(
        request,
        hash_seed="777",
    )

    assert initialized_a == initialized_b
    assert initialized_a.adapter.name == EXPECTED_PRODUCER
    assert result_a == result_b
    assert stderr_a == stderr_b == b""
    assert result_a.request == request
    assert result_a.procedure_uri == PYTHON_PROCEDURE_URI
    assert [file.path for file in result_a.files] == [
        "test_action_reserve_item.py"
    ]
    generated = result_a.files[0].content
    assert "legacy_inventory" in generated
    assert "reserve_item" in generated
    assert "item_id" in generated
    assert "sku-123" in generated
    assert "reservation-456" in generated
    compile(generated, result_a.files[0].path, "exec")
    assert result_a.verification.argv == (
        "python3",
        "-B",
        "-m",
        "pytest",
        "-q",
        "{generated_root}",
    )


def test_external_adapter_rejects_nonexact_profile_and_recovers() -> None:
    request = generation_request()
    configuration = request.profile_configuration
    entries = configuration.entries
    extra_configuration = configuration.model_copy(
        update={
            "entries": (
                *entries,
                RecordEntry(
                    kind="record_entry",
                    name="unknown",
                    value=StringValue(kind="string", value="value"),
                ),
            )
        }
    )
    extra_request = request.model_copy(
        update={"profile_configuration": extra_configuration}
    )
    from ucf.generation import derive_generation_request_id

    extra_request = extra_request.model_copy(
        update={"id": derive_generation_request_id(extra_request)}
    )

    async def run() -> None:
        process = AdapterProcess(
            command=(sys.executable, "-I", "-B", "-X", "utf8", str(ADAPTER)),
            cwd=REPOSITORY_ROOT,
            requested_capabilities=(
                CapabilityRequest(
                    kind="capability_request",
                    name=GENERATION_CAPABILITY,
                    minimum_version="1.0.0",
                    required=True,
                ),
                CapabilityRequest(
                    kind="capability_request",
                    name=PYTHON_PROFILE_CAPABILITY,
                    minimum_version="1.0.0",
                    required=True,
                ),
            ),
            timeouts=ProcessTimeouts(operation=5.0),
            environment={"PYTHONHASHSEED": "1"},
        )
        await process.start()
        try:
            with pytest.raises(AdapterProtocolError) as captured:
                await process.call(
                    Method.GENERATE,
                    generation_request_to_payload(extra_request),
                )
            assert captured.value.category is ErrorCategory.ADAPTER_FAILURE
            assert captured.value.code is ProtocolCode.OPERATION_FAILED

            valid = generation_result_from_payload(
                await process.call(
                    Method.GENERATE,
                    generation_request_to_payload(request),
                )
            )
            assert valid.request == request
            assert process.stderr_tail == b""
        finally:
            await process.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("module", "../escape"),
        ("module", "not-a-module!"),
        ("callable", "not-a-callable!"),
        ("parameters", "not-a-record"),
    ],
)
def test_external_adapter_rejects_unsafe_backend_configuration(
    field: str,
    value: str,
) -> None:
    request = generation_request()
    entries = tuple(
        entry.model_copy(
            update={"value": StringValue(kind="string", value=value)}
        )
        if entry.name == field
        else entry
        for entry in request.profile_configuration.entries
    )
    changed = request.model_copy(
        update={
            "profile_configuration": RecordValue(
                kind="record",
                entries=entries,
            )
        }
    )
    from ucf.generation import derive_generation_request_id

    changed = changed.model_copy(
        update={"id": derive_generation_request_id(changed)}
    )

    with pytest.raises(AdapterProtocolError) as captured:
        _run_adapter(changed, hash_seed="1")
    assert captured.value.category is ErrorCategory.ADAPTER_FAILURE
    assert captured.value.code is ProtocolCode.OPERATION_FAILED


def test_adapter_is_external_and_does_not_import_legacy_generator() -> None:
    assert ADAPTER.is_file()
    source = ADAPTER.read_text(encoding="utf-8")

    assert "ucf.generator" not in source
    assert "jinja" not in source.casefold()
    assert not any(
        path.is_file()
        for path in (
            REPOSITORY_ROOT
            / "src"
            / "ucf"
            / "generation"
        ).glob("*python*")
    )
    assert os.path.commonpath((ADAPTER, REPOSITORY_ROOT / "src")) != str(
        REPOSITORY_ROOT / "src"
    )
