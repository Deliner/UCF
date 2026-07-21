from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import ucf.runtime_evidence.client as runtime_client
from ucf.adapter_protocol import (
    ErrorCategory,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.ir import canonical_ir_json, parse_ir_json
from ucf.ir.models import Digest, DomainTarget, EntityKind, StringValue
from ucf.ir.trust_models import (
    BehaviorDocumentRef,
    BehaviorEntityRef,
    FactAssertion,
)
from ucf.runtime_evidence import (
    RuntimeEvidenceAcceptedResult,
    RuntimeEvidenceClientError,
    RuntimeEvidenceImportRequest,
    RuntimeEvidencePolicy,
    RuntimeEvidenceRejectedResult,
    RuntimeObservationRule,
    RuntimePolicyRejectionCode,
    import_runtime_evidence,
    runtime_recording_digest,
)

from .test_validation import _bound_request

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = (
    ROOT
    / "tests"
    / "fixtures"
    / "adapters"
    / "runtime_evidence_reference_adapter.py"
)
RECORDING = (
    ROOT
    / "tests"
    / "fixtures"
    / "runtime_evidence"
    / "recorded_trace_v1"
    / "recording.json"
)
TIMEOUTS = ProcessTimeouts(
    initialize=1.0,
    operation=1.0,
    write=1.0,
    cancellation=0.2,
    shutdown=0.5,
    terminate=0.2,
    kill=0.5,
)


def _request_for_recording():
    request, behavior, environment = _bound_request()
    source = request.source.model_copy(
        update={
            "source_revision": request.source.source_revision.model_copy(
                update={
                    "value": hashlib.sha256(
                        RECORDING.read_bytes()
                    ).hexdigest()
                }
            )
        }
    )
    return (
        request.model_copy(update={"source": source}),
        behavior,
        environment,
    )


def _command(
    mode: str = "normal",
    *,
    pid_file: Path | None = None,
) -> tuple[str, ...]:
    command = (
        sys.executable,
        str(ADAPTER),
        str(RECORDING),
        "--mode",
        mode,
    )
    if pid_file is not None:
        command += ("--pid-file", str(pid_file))
    return command


def test_real_process_imports_exact_accepted_and_rejected_results() -> None:
    async def scenario():
        request, behavior, environment = _request_for_recording()
        accepted = await import_runtime_evidence(
            command=_command(),
            cwd=ROOT,
            recording_path=RECORDING,
            request=request,
            behavior=behavior,
            environment=environment,
            timeouts=TIMEOUTS,
            operation_timeout=1.0,
        )
        rejected = await import_runtime_evidence(
            command=_command("rejected"),
            cwd=ROOT,
            recording_path=RECORDING,
            request=request,
            behavior=behavior,
            environment=environment,
            timeouts=TIMEOUTS,
            operation_timeout=1.0,
        )

        assert isinstance(accepted, RuntimeEvidenceAcceptedResult)
        assert isinstance(rejected, RuntimeEvidenceRejectedResult)
        assert tuple(rejected.reason_codes) == (
            "selected_value_not_allowed",
        )

    asyncio.run(scenario())


def test_multi_rule_unsafe_selection_returns_all_typed_rejections() -> None:
    request, original_behavior, environment = _request_for_recording()
    first_observation = next(
        entity
        for entity in original_behavior.entities
        if entity.id == "observation.reservation-created"
    )
    second_observation = first_observation.model_copy(
        update={
            "id": "observation.reservation-audited",
            "target": DomainTarget(
                kind="domain_target",
                subject="reservation",
                path=("audit_status",),
            ),
            "value": StringValue(kind="string", value="recorded"),
        }
    )
    behavior = parse_ir_json(
        canonical_ir_json(
            original_behavior.model_copy(
                update={
                    "entities": (
                        *original_behavior.entities,
                        second_observation,
                    )
                }
            )
        )
    )
    behavior_digest = Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(
            canonical_ir_json(behavior).encode("ascii")
        ).hexdigest(),
    )
    behavior_ref = BehaviorDocumentRef(
        kind="behavior_document_ref",
        document_id=behavior.document_id,
        ir_version=behavior.ir_version,
        canonical_digest=behavior_digest,
    )

    def rule(
        *,
        identifier: str,
        selector_uri: str,
        observation,
    ) -> RuntimeObservationRule:
        return RuntimeObservationRule(
            kind="runtime_observation_rule",
            id=identifier,
            selector_uri=selector_uri,
            subject=BehaviorEntityRef(
                kind="behavior_entity_ref",
                document_id=behavior.document_id,
                ir_version=behavior.ir_version,
                canonical_digest=behavior_digest,
                target_kind=EntityKind.OBSERVATION,
                target_id=observation.id,
            ),
            assertion=FactAssertion(
                kind="fact_assertion",
                target=observation.target,
                value=observation.value,
            ),
        )

    policy = RuntimeEvidencePolicy(
        **{
            **request.policy.model_dump(mode="python", exclude={"rules"}),
            "rules": (
                rule(
                    identifier="rule.selected-personal",
                    selector_uri=(
                        "urn:ucf:fixture-selector:"
                        "selected-personal-data:1.0.0"
                    ),
                    observation=second_observation,
                ),
                rule(
                    identifier="rule.selected-secret",
                    selector_uri=(
                        "urn:ucf:fixture-selector:selected-secret:1.0.0"
                    ),
                    observation=first_observation,
                ),
            ),
        }
    )
    bound_request = RuntimeEvidenceImportRequest(
        **{
            **request.model_dump(
                mode="python",
                exclude={"behavior", "policy"},
            ),
            "behavior": behavior_ref,
            "policy": policy,
        }
    )

    result = asyncio.run(
        import_runtime_evidence(
            command=_command(),
            cwd=ROOT,
            recording_path=RECORDING,
            request=bound_request,
            behavior=behavior,
            environment=environment,
            timeouts=TIMEOUTS,
            operation_timeout=1.0,
        )
    )

    assert isinstance(result, RuntimeEvidenceRejectedResult)
    assert tuple(result.reason_codes) == (
        RuntimePolicyRejectionCode.SELECTED_PERSONAL_DATA,
        RuntimePolicyRejectionCode.SELECTED_SECRET,
    )
    rendered = repr(result.model_dump(mode="json"))
    assert all(value not in rendered for value in _forbidden_values())


@pytest.mark.parametrize(
    ("mode", "category", "code"),
    [
        (
            "missing-runtime-capability",
            ErrorCategory.PROTOCOL_FAILURE,
            ProtocolCode.UNSUPPORTED_CAPABILITY,
        ),
        (
            "wrong-profile",
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
        ),
        (
            "stderr",
            ErrorCategory.PROCESS_FAILURE,
            ProtocolCode.INVALID_ADAPTER_OUTPUT,
        ),
        (
            "peer-error",
            ErrorCategory.ADAPTER_FAILURE,
            ProtocolCode.OPERATION_FAILED,
        ),
    ],
)
def test_process_failures_are_sanitized_and_reaped(
    mode: str,
    category: ErrorCategory,
    code: ProtocolCode,
) -> None:
    request, behavior, environment = _request_for_recording()

    with pytest.raises(RuntimeEvidenceClientError) as captured:
        asyncio.run(
            import_runtime_evidence(
                command=_command(mode),
                cwd=ROOT,
                recording_path=RECORDING,
                request=request,
                behavior=behavior,
                environment=environment,
                timeouts=TIMEOUTS,
                operation_timeout=1.0,
            )
        )

    assert captured.value.category is category
    assert captured.value.code is code
    assert str(captured.value) == f"{category.value}/{code.value}"
    forbidden_values = _forbidden_values()
    chain = _exception_chain(captured.value)
    rendered = "\n".join(
        part
        for error in chain
        for part in (str(error), repr(error))
    )
    assert all(value not in rendered for value in forbidden_values)
    assert all(
        not hasattr(error, "message")
        for error in chain
        if isinstance(error, RuntimeEvidenceClientError)
    )


def test_timeout_and_caller_cancellation_reap_the_runtime_adapter(
    tmp_path: Path,
) -> None:
    async def wait_for_pid(path: Path) -> int:
        for _ in range(50):
            if path.exists():
                value = path.read_text(encoding="ascii")
                if value.isdecimal():
                    return int(value)
            await asyncio.sleep(0.01)
        raise AssertionError("runtime adapter did not publish its PID")

    async def scenario() -> None:
        request, behavior, environment = _request_for_recording()
        timeout_pid_path = tmp_path / "timeout.pid"
        with pytest.raises(RuntimeEvidenceClientError) as captured:
            await import_runtime_evidence(
                command=_command("hang", pid_file=timeout_pid_path),
                cwd=ROOT,
                recording_path=RECORDING,
                request=request,
                behavior=behavior,
                environment=environment,
                timeouts=TIMEOUTS,
                operation_timeout=0.05,
            )
        assert captured.value.category is ErrorCategory.TIMEOUT
        assert captured.value.code is ProtocolCode.OPERATION_TIMEOUT
        timeout_pid = await wait_for_pid(timeout_pid_path)
        with pytest.raises(ProcessLookupError):
            os.kill(timeout_pid, 0)

        cancellation_pid_path = tmp_path / "cancellation.pid"
        task = asyncio.create_task(
            import_runtime_evidence(
                command=_command(
                    "hang",
                    pid_file=cancellation_pid_path,
                ),
                cwd=ROOT,
                recording_path=RECORDING,
                request=request,
                behavior=behavior,
                environment=environment,
                timeouts=TIMEOUTS,
                operation_timeout=1.0,
            )
        )
        cancellation_pid = await wait_for_pid(cancellation_pid_path)
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(ProcessLookupError):
            os.kill(cancellation_pid, 0)

    asyncio.run(scenario())


def test_recording_digest_stops_at_the_limit_when_the_file_grows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = tmp_path / "growing-recording.json"
    recording.write_bytes(b"x")
    original_read = os.read
    returned_bytes = 0
    requested_sizes = []
    grew = False

    def grow_before_read(descriptor: int, size: int) -> bytes:
        nonlocal grew, returned_bytes
        requested_sizes.append(size)
        if not grew:
            with recording.open("ab") as stream:
                stream.write(b"y" * 100)
            grew = True
        chunk = original_read(descriptor, size)
        returned_bytes += len(chunk)
        return chunk

    monkeypatch.setattr(runtime_client, "MAX_RUNTIME_RECORDING_BYTES", 4)
    monkeypatch.setattr(runtime_client.os, "read", grow_before_read)

    with pytest.raises(ValueError, match="byte limit"):
        runtime_recording_digest(recording)

    assert requested_sizes
    assert max(requested_sizes) <= 5
    assert returned_bytes <= 5


def test_recording_digest_rejects_an_initial_oversized_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = tmp_path / "oversized-recording.json"
    recording.write_bytes(b"12345")
    monkeypatch.setattr(runtime_client, "MAX_RUNTIME_RECORDING_BYTES", 4)

    with pytest.raises(ValueError, match="byte limit"):
        runtime_recording_digest(recording)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"resourceSpans":[],"resourceSpans":[]}\n',
        b'{"value":NaN}\n',
    ],
)
def test_malformed_recording_is_a_sanitized_adapter_failure(
    tmp_path: Path,
    payload: bytes,
) -> None:
    recording = tmp_path / "malformed-recording.json"
    recording.write_bytes(payload)
    request, behavior, environment = _request_for_recording()
    source = request.source.model_copy(
        update={
            "source_revision": request.source.source_revision.model_copy(
                update={"value": hashlib.sha256(payload).hexdigest()}
            )
        }
    )
    bound_request = request.model_copy(update={"source": source})

    with pytest.raises(RuntimeEvidenceClientError) as captured:
        asyncio.run(
            import_runtime_evidence(
                command=(
                    sys.executable,
                    str(ADAPTER),
                    str(recording),
                ),
                cwd=ROOT,
                recording_path=recording,
                request=bound_request,
                behavior=behavior,
                environment=environment,
                timeouts=TIMEOUTS,
                operation_timeout=1.0,
            )
        )

    assert captured.value.category is ErrorCategory.ADAPTER_FAILURE
    assert captured.value.code is ProtocolCode.OPERATION_FAILED


def _forbidden_values() -> tuple[str, str]:
    recording = json.loads(RECORDING.read_text(encoding="utf-8"))
    attributes = recording["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
        "attributes"
    ]
    values = {
        item["key"]: item["value"]["stringValue"] for item in attributes
    }
    return values["fixture.secret"], values["fixture.personal"]


def _exception_chain(error: BaseException) -> tuple[BaseException, ...]:
    chain = []
    seen = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return tuple(chain)
