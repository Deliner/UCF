#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from inventory_reference.discovery import (
    DISCOVERY_CAPABILITY,
    DISCOVERY_RESULT_SCHEMA_URI,
    build_discovery_result,
    decode_discovery_request,
    encode_discovery_result_payload,
)
from inventory_reference.implementation_evidence import (
    MAPPING_CAPABILITY,
    VERIFICATION_CAPABILITY,
    ProfileError,
    VerificationPlan,
    build_mapping_payload,
    build_verification_result_payload,
    decode_verification_plan,
)
from inventory_reference.native_verification import (
    NativeVerificationCancelled,
    NativeVerificationError,
    build_execution_environment,
    run_native_verification,
)
from inventory_reference.profile import (
    INVENTORY_CAPABILITY,
    INVENTORY_PAGE_SCHEMA_URI,
    INVENTORY_VERSION,
    PRODUCER,
    InvalidProfile,
    InventoryRun,
    build_inventory_page,
    build_inventory_run,
    canonical_json,
    decode_inventory_request,
    decode_tagged,
    encode_inventory_page_payload,
    encode_tagged,
)
from inventory_reference.traversal import ScanCancelled, scan_repository

MAX_FRAME_BYTES = 1_048_576
MAX_REQUESTS_PER_SESSION = 65_536
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_QUALIFIED_NAME = re.compile(
    r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
    r"(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$"
)
_CONTROL_SCHEMA_URI = "urn:ucf:adapter-conformance:control:1.0.0"
GENERATION_CAPABILITY = "org.ucf.adapter.generation"
_METHOD_CAPABILITY = {
    "ucf.inventory": INVENTORY_CAPABILITY,
    "ucf.discover": DISCOVERY_CAPABILITY,
    "ucf.map": MAPPING_CAPABILITY,
    "ucf.generate": GENERATION_CAPABILITY,
    "ucf.verify": VERIFICATION_CAPABILITY,
}
_METHOD_REQUEST_KIND = {
    "ucf.inventory": "inventory_request",
    "ucf.discover": "discover_request",
    "ucf.map": "map_request",
    "ucf.generate": "generate_request",
    "ucf.verify": "verify_request",
}
_METHOD_RESULT_KIND = {
    "ucf.inventory": "inventory_result",
    "ucf.discover": "discover_result",
    "ucf.map": "map_result",
    "ucf.generate": "generate_result",
    "ucf.verify": "verify_result",
}
_STDOUT_LOCK = threading.Lock()


class StrictJsonError(ValueError):
    pass


@dataclass(frozen=True)
class ProtocolFailure(Exception):
    code: str
    category: str
    message: str
    request_id: str | None = None


@dataclass
class Session:
    mode: str
    conformance_mode: bool = False
    state: str = "new"
    request_count: int = 0
    request_ids: set[str] | None = None
    inventory_negotiated: bool = False
    discovery_negotiated: bool = False
    mapping_negotiated: bool = False
    generation_negotiated: bool = False
    verification_negotiated: bool = False
    inventory_complete: bool = False
    run: InventoryRun | None = None
    run_key: bytes | None = None
    inventory_request: dict[str, object] | None = None
    mapping: dict[str, object] | None = None
    pending: PendingOperation | None = None

    def __post_init__(self) -> None:
        self.request_ids = set()


@dataclass(frozen=True)
class PendingOperation:
    request_id: str
    cancel_event: threading.Event
    future: concurrent.futures.Future[dict[str, object]]


@dataclass(frozen=True)
class ControlRequest:
    operation: str
    target_request_id: str | None = None
    tagged_value: object | None = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--mode",
        choices=(
            "normal",
            "wrong-profile",
            "invalid-page",
            "fail-second-page",
            "wrong-discovery-profile",
            "invalid-candidate",
            "fail-discovery",
            "block-map",
            "block-verify",
        ),
        default="normal",
    )
    parser.add_argument("--conformance", action="store_true")
    arguments = parser.parse_args(argv)
    session = Session(
        mode=arguments.mode,
        conformance_mode=arguments.conformance,
    )
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="inventory-scan",
    )
    try:
        while session.state != "closed":
            frame = b""
            try:
                frame = _read_frame()
                if frame is None:
                    return 0 if session.state == "closed" else 3
                message = _decode_message(frame)
                response = _dispatch(session, message, executor)
            except ProtocolFailure as error:
                response = _error_response(error)
            except InvalidProfile:
                response = _error_response(
                    ProtocolFailure(
                        code="invalid_params",
                        category="protocol_failure",
                        message="inventory request is invalid",
                        request_id=_recover_request_id(frame),
                    )
                )
            except OSError:
                response = _error_response(
                    ProtocolFailure(
                        code="operation_failed",
                        category="adapter_failure",
                        message="inventory root is unavailable",
                        request_id=_recover_request_id(frame),
                    )
                )
            except (AssertionError, KeyError, TypeError, ValueError):
                response = _error_response(
                    ProtocolFailure(
                        code="internal_error",
                        category="adapter_failure",
                        message="inventory operation failed",
                        request_id=_recover_request_id(frame),
                    )
                )
            if response is not None:
                _write_response(response)
        return 0
    finally:
        if session.pending is not None:
            session.pending.cancel_event.set()
        executor.shutdown(wait=False, cancel_futures=True)


def _dispatch(
    session: Session,
    message: dict[str, object],
    executor: concurrent.futures.ThreadPoolExecutor,
) -> dict[str, object] | None:
    method = message["method"]
    if method == "ucf.cancel":
        _cancel_pending_operation(session, message["params"])
        return None
    request_id = str(message["id"])
    assert session.request_ids is not None
    if request_id in session.request_ids:
        raise ProtocolFailure(
            code="duplicate_request_id",
            category="protocol_failure",
            message="request ID has already been used",
            request_id=request_id,
        )
    if session.request_count >= MAX_REQUESTS_PER_SESSION or (
        session.request_count == MAX_REQUESTS_PER_SESSION - 1
        and method != "ucf.shutdown"
    ):
        raise ProtocolFailure(
            code="session_request_limit",
            category="protocol_failure",
            message="session request limit was reached",
            request_id=request_id,
        )
    session.request_ids.add(request_id)
    session.request_count += 1
    if method == "ucf.initialize":
        return _initialize(session, request_id, message["params"])
    if method in _METHOD_CAPABILITY:
        _require_operation_capability(session, method, request_id)
        control = _decode_control_request(message["params"], request_id)
        if control is not None and control.operation != "block":
            return _control_response(session, method, request_id, control)
    if method == "ucf.inventory":
        if session.pending is not None:
            raise ProtocolFailure(
                code="too_many_pending",
                category="protocol_failure",
                message="only one inventory request may be pending",
                request_id=request_id,
            )
        cancel_event = threading.Event()
        future = executor.submit(
            _run_inventory_operation,
            session,
            request_id,
            message["params"],
            cancel_event,
            control,
        )
        pending = PendingOperation(
            request_id=request_id,
            cancel_event=cancel_event,
            future=future,
        )
        session.pending = pending
        future.add_done_callback(
            lambda completed: _complete_operation(
                session,
                pending,
                completed,
            )
        )
        return None
    if method == "ucf.discover":
        if session.pending is not None:
            raise ProtocolFailure(
                code="invalid_lifecycle",
                category="protocol_failure",
                message="discovery is illegal while inventory is pending",
                request_id=request_id,
            )
        return _discover(session, request_id, message["params"])
    if method == "ucf.map":
        if session.pending is not None:
            raise ProtocolFailure(
                code="too_many_pending",
                category="protocol_failure",
                message="mapping is illegal while an operation is pending",
                request_id=request_id,
            )
        cancel_event = threading.Event()
        future = executor.submit(
            _run_map_operation,
            session,
            request_id,
            message["params"],
            cancel_event,
        )
        pending = PendingOperation(
            request_id=request_id,
            cancel_event=cancel_event,
            future=future,
        )
        session.pending = pending
        future.add_done_callback(
            lambda completed: _complete_operation(
                session,
                pending,
                completed,
            )
        )
        return None
    if method == "ucf.verify":
        if session.pending is not None:
            raise ProtocolFailure(
                code="too_many_pending",
                category="protocol_failure",
                message="only one operation may be pending",
                request_id=request_id,
            )
        cancel_event = threading.Event()
        future = executor.submit(
            _run_verification_operation,
            session,
            request_id,
            message["params"],
            cancel_event,
        )
        pending = PendingOperation(
            request_id=request_id,
            cancel_event=cancel_event,
            future=future,
        )
        session.pending = pending
        future.add_done_callback(
            lambda completed: _complete_operation(
                session,
                pending,
                completed,
            )
        )
        return None
    if method == "ucf.generate":
        raise ProtocolFailure(
            code="operation_failed",
            category="adapter_failure",
            message="negotiated operation has no implementation",
            request_id=request_id,
        )
    if method == "ucf.shutdown":
        if session.pending is not None:
            raise ProtocolFailure(
                code="invalid_lifecycle",
                category="protocol_failure",
                message="shutdown is illegal while inventory is pending",
                request_id=request_id,
            )
        return _shutdown(session, request_id, message["params"])
    raise ProtocolFailure(
        code="method_not_found",
        category="protocol_failure",
        message="method is not supported",
        request_id=request_id,
    )


def _require_operation_capability(
    session: Session,
    method: str,
    request_id: str,
) -> None:
    if session.state != "ready":
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="operations require an initialized session",
            request_id=request_id,
        )
    capability = _METHOD_CAPABILITY[method]
    negotiated = {
        INVENTORY_CAPABILITY: session.inventory_negotiated,
        DISCOVERY_CAPABILITY: session.discovery_negotiated,
        MAPPING_CAPABILITY: session.mapping_negotiated,
        GENERATION_CAPABILITY: session.generation_negotiated,
        VERIFICATION_CAPABILITY: session.verification_negotiated,
    }.get(capability, False)
    if not negotiated:
        raise ProtocolFailure(
            code="capability_not_negotiated",
            category="protocol_failure",
            message="operation capability was not negotiated",
            request_id=request_id,
        )


def _decode_control_request(
    value: object,
    request_id: str,
) -> ControlRequest | None:
    params = _expect_object(value, "operation params")
    payload = params["payload"]
    if type(payload) is not dict or payload.get("schema_uri") != _CONTROL_SCHEMA_URI:
        return None
    _exact_fields(
        payload,
        {"kind", "schema_uri", "schema_version", "value"},
        request_id,
    )
    if (
        payload["kind"] != "adapter_payload"
        or payload["schema_version"] != INVENTORY_VERSION
    ):
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="control payload coordinates are invalid",
            request_id=request_id,
        )
    try:
        logical = decode_tagged(payload["value"])
    except InvalidProfile as error:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="control payload is invalid",
            request_id=request_id,
        ) from error
    if type(logical) is not dict or type(logical.get("operation")) is not str:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="control operation is invalid",
            request_id=request_id,
        )
    operation = logical["operation"]
    if operation == "block" and set(logical) == {"operation"}:
        return ControlRequest(operation=operation)
    if operation == "echo" and set(logical) == {"operation", "value"}:
        return ControlRequest(
            operation=operation,
            tagged_value=encode_tagged(logical["value"]),
        )
    target = logical.get("target_request_id")
    if (
        operation == "readiness"
        and set(logical) == {"operation", "target_request_id"}
        and type(target) is str
        and _REQUEST_ID.fullmatch(target) is not None
    ):
        return ControlRequest(
            operation=operation,
            target_request_id=target,
        )
    raise ProtocolFailure(
        code="invalid_params",
        category="protocol_failure",
        message="control operation is invalid",
        request_id=request_id,
    )


def _control_response(
    session: Session,
    method: str,
    request_id: str,
    control: ControlRequest,
) -> dict[str, object]:
    if control.operation == "echo":
        entries = [
            _control_entry("operation", {"kind": "string", "value": "echo_result"}),
            _control_entry("value", control.tagged_value),
        ]
    elif control.operation == "readiness":
        target = control.target_request_id
        assert target is not None
        active = session.pending is not None and session.pending.request_id == target
        entries = [
            _control_entry(
                "operation",
                {"kind": "string", "value": "readiness_result"},
            ),
            _control_entry(
                "target_request_id",
                {"kind": "string", "value": target},
            ),
            _control_entry("active", {"kind": "boolean", "value": active}),
        ]
    else:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="control operation is unavailable for this method",
            request_id=request_id,
        )
    payload = {
        "kind": "adapter_payload",
        "schema_uri": _CONTROL_SCHEMA_URI,
        "schema_version": INVENTORY_VERSION,
        "value": {"kind": "record", "entries": entries},
    }
    return _success_response(
        request_id,
        {"kind": _METHOD_RESULT_KIND[method], "payload": payload},
    )


def _control_entry(name: str, value: object) -> dict[str, object]:
    return {"kind": "record_entry", "name": name, "value": value}


def _map_implementation(
    session: Session,
    request_id: str,
    value: object,
    cancel_event: threading.Event,
) -> dict[str, object]:
    snapshot = _refresh_current_inventory(
        session,
        request_id,
        cancel_event,
    )
    params = _expect_object(value, "mapping params")
    try:
        product = build_mapping_payload(
            params["payload"],
            current_inventory=snapshot,
        )
    except ProfileError as error:
        raise _profile_failure(error, request_id) from error
    if cancel_event.is_set():
        raise ScanCancelled
    response = _success_response(
        request_id,
        {"kind": "map_result", "payload": product.payload},
    )
    if _bounded_response_size(response) > MAX_FRAME_BYTES:
        raise ProtocolFailure(
            code="operation_failed",
            category="adapter_failure",
            message="mapping result exceeds the response frame",
            request_id=request_id,
        )
    session.mapping = product.logical
    return response


def _run_map_operation(
    session: Session,
    request_id: str,
    value: object,
    cancel_event: threading.Event,
) -> dict[str, object]:
    try:
        if session.mode == "block-map":
            cancel_event.wait()
            raise ScanCancelled
        return _map_implementation(
            session,
            request_id,
            value,
            cancel_event,
        )
    except ProtocolFailure as error:
        return _error_response(error)
    except ScanCancelled:
        return _error_response(
            ProtocolFailure(
                code="request_cancelled",
                category="cancelled",
                message="request was cancelled",
                request_id=request_id,
            )
        )
    except OSError:
        return _error_response(
            ProtocolFailure(
                code="operation_failed",
                category="adapter_failure",
                message="mapping source is unavailable",
                request_id=request_id,
            )
        )
    except (AssertionError, KeyError, TypeError, ValueError):
        return _error_response(
            ProtocolFailure(
                code="internal_error",
                category="adapter_failure",
                message="mapping operation failed",
                request_id=request_id,
            )
        )


def _prepare_verification(
    session: Session,
    request_id: str,
    value: object,
    cancel_event: threading.Event,
) -> tuple[VerificationPlan, dict[str, object]]:
    if session.mapping is None:
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="verification requires a current mapping",
            request_id=request_id,
        )
    snapshot = _refresh_current_inventory(
        session,
        request_id,
        cancel_event,
    )
    try:
        environment = build_execution_environment(
            _inventory_root(session, request_id),
            snapshot,
        )
        if cancel_event.is_set():
            raise NativeVerificationCancelled
        params = _expect_object(value, "verification params")
        plan = decode_verification_plan(
            params["payload"],
            current_inventory=snapshot,
            mapping=session.mapping,
            expected_environment=environment,
        )
    except ProfileError as error:
        raise _profile_failure(error, request_id) from error
    except NativeVerificationError as error:
        raise ProtocolFailure(
            code=error.code,
            category="adapter_failure",
            message=str(error),
            request_id=request_id,
        ) from error
    return plan, snapshot


def _run_verification_operation(
    session: Session,
    request_id: str,
    value: object,
    cancel_event: threading.Event,
) -> dict[str, object]:
    try:
        if session.mode == "block-verify":
            cancel_event.wait()
            raise NativeVerificationCancelled
        plan, snapshot = _prepare_verification(
            session,
            request_id,
            value,
            cancel_event,
        )
        execution = run_native_verification(
            _inventory_root(session, request_id),
            snapshot,
            expected_total_cents=plan.expected_total_cents,
            cancel_event=cancel_event,
        )
        _refresh_current_inventory(session, request_id, cancel_event)
        executed_at = (
            datetime.now(UTC)
            .replace(microsecond=0)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        product = build_verification_result_payload(
            plan.request,
            outcome=execution.outcome,
            executed_at=executed_at,
        )
        response = _success_response(
            request_id,
            {"kind": "verify_result", "payload": product.payload},
        )
        if _bounded_response_size(response) > MAX_FRAME_BYTES:
            raise NativeVerificationError(
                "operation_failed",
                "verification result exceeds the response frame",
            )
        return response
    except (NativeVerificationCancelled, ScanCancelled):
        return _error_response(
            ProtocolFailure(
                code="request_cancelled",
                category="cancelled",
                message="request was cancelled",
                request_id=request_id,
            )
        )
    except ProfileError as error:
        return _error_response(_profile_failure(error, request_id))
    except NativeVerificationError as error:
        return _error_response(
            ProtocolFailure(
                code=error.code,
                category="adapter_failure",
                message=str(error),
                request_id=request_id,
            )
        )
    except ProtocolFailure as error:
        return _error_response(error)


def _refresh_current_inventory(
    session: Session,
    request_id: str,
    cancel_event: threading.Event,
) -> dict[str, object]:
    if (
        not session.inventory_complete
        or session.run is None
        or session.inventory_request is None
    ):
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="operation requires a completed current inventory",
            request_id=request_id,
        )
    request = session.inventory_request
    scan = scan_repository(
        root_path=str(request["root_path"]),
        ignore_rules=tuple(request["ignore_policy"]["rules"]),
        cancel_event=cancel_event,
    )
    current = build_inventory_run(request, scan)
    if canonical_json(current.snapshot) != canonical_json(session.run.snapshot):
        session.inventory_complete = False
        session.mapping = None
        raise ProtocolFailure(
            code="operation_failed",
            category="adapter_failure",
            message="inventory changed after the accepted snapshot",
            request_id=request_id,
        )
    return current.snapshot


def _inventory_root(session: Session, request_id: str) -> Path:
    request = session.inventory_request
    if request is None or type(request.get("root_path")) is not str:
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="operation requires an accepted inventory root",
            request_id=request_id,
        )
    return Path.cwd() / str(request["root_path"])


def _profile_failure(error: ProfileError, request_id: str) -> ProtocolFailure:
    return ProtocolFailure(
        code=error.code,
        category=(
            "protocol_failure"
            if error.code == "invalid_params"
            else "adapter_failure"
        ),
        message=str(error),
        request_id=request_id,
    )


def _cancel_pending_operation(session: Session, value: object) -> None:
    params = _expect_object(value, "cancel params")
    pending = session.pending
    if pending is not None and params["request_id"] == pending.request_id:
        pending.cancel_event.set()


def _run_inventory_operation(
    session: Session,
    request_id: str,
    value: object,
    cancel_event: threading.Event,
    control: ControlRequest | None,
) -> dict[str, object]:
    try:
        if control is not None:
            cancel_event.wait()
            raise ScanCancelled
        return _inventory(
            session,
            request_id,
            value,
            cancel_event=cancel_event,
        )
    except ProtocolFailure as error:
        return _error_response(error)
    except InvalidProfile:
        return _error_response(
            ProtocolFailure(
                code="invalid_params",
                category="protocol_failure",
                message="inventory request is invalid",
                request_id=request_id,
            )
        )
    except ScanCancelled:
        return _error_response(
            ProtocolFailure(
                code="request_cancelled",
                category="cancelled",
                message="request was cancelled",
                request_id=request_id,
            )
        )
    except OSError:
        return _error_response(
            ProtocolFailure(
                code="operation_failed",
                category="adapter_failure",
                message="inventory root is unavailable",
                request_id=request_id,
            )
        )
    except (AssertionError, KeyError, TypeError, ValueError):
        return _error_response(
            ProtocolFailure(
                code="internal_error",
                category="adapter_failure",
                message="inventory operation failed",
                request_id=request_id,
            )
        )


def _complete_operation(
    session: Session,
    pending: PendingOperation,
    future: concurrent.futures.Future[dict[str, object]],
) -> None:
    try:
        response = future.result()
    except concurrent.futures.CancelledError:
        response = _error_response(
            ProtocolFailure(
                code="request_cancelled",
                category="cancelled",
                message="request was cancelled",
                request_id=pending.request_id,
            )
        )
    if session.pending is pending:
        session.pending = None
    _write_response(response)


def _initialize(
    session: Session,
    request_id: str,
    value: object,
) -> dict[str, object]:
    if session.state != "new":
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="initialize is legal only in the new state",
            request_id=request_id,
        )
    params = _expect_object(value, "initialize params")
    _exact_fields(
        params,
        {"kind", "protocol_version", "client", "capabilities"},
        request_id,
    )
    if (
        params["kind"] != "initialize_request"
        or params["protocol_version"] != INVENTORY_VERSION
    ):
        raise ProtocolFailure(
            code="incompatible_version",
            category="protocol_failure",
            message="adapter protocol version is incompatible",
            request_id=request_id,
        )
    _validate_producer(params["client"], request_id)
    capabilities = _expect_array(params["capabilities"], request_id)
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for value_capability in capabilities:
        capability = _expect_object(value_capability, "capability request")
        _exact_fields(
            capability,
            {"kind", "name", "minimum_version", "required"},
            request_id,
        )
        name = capability["name"]
        minimum = capability["minimum_version"]
        required = capability["required"]
        if (
            capability["kind"] != "capability_request"
            or type(name) is not str
            or _QUALIFIED_NAME.fullmatch(name) is None
            or type(minimum) is not str
            or _VERSION.fullmatch(minimum) is None
            or type(required) is not bool
        ):
            raise ProtocolFailure(
                code="invalid_params",
                category="protocol_failure",
                message="capability request is invalid",
                request_id=request_id,
            )
        if name in seen:
            raise ProtocolFailure(
                code="duplicate_capability",
                category="protocol_failure",
                message="capability request is duplicated",
                request_id=request_id,
            )
        seen.add(name)
        supported = name in {
            INVENTORY_CAPABILITY,
            DISCOVERY_CAPABILITY,
            MAPPING_CAPABILITY,
            VERIFICATION_CAPABILITY,
        } and _version_at_least(INVENTORY_VERSION, minimum)
        supported = supported or (
            session.conformance_mode
            and name == GENERATION_CAPABILITY
            and _version_at_least(INVENTORY_VERSION, minimum)
        )
        if supported:
            selected.append(
                {
                    "kind": "capability",
                    "name": name,
                    "version": INVENTORY_VERSION,
                }
            )
        elif required:
            raise ProtocolFailure(
                code="unsupported_capability",
                category="protocol_failure",
                message="required capability is unsupported",
                request_id=request_id,
            )
    session.state = "ready"
    session.inventory_negotiated = any(
        item["name"] == INVENTORY_CAPABILITY for item in selected
    )
    session.discovery_negotiated = any(
        item["name"] == DISCOVERY_CAPABILITY for item in selected
    )
    session.mapping_negotiated = any(
        item["name"] == MAPPING_CAPABILITY for item in selected
    )
    session.generation_negotiated = any(
        item["name"] == GENERATION_CAPABILITY for item in selected
    )
    session.verification_negotiated = any(
        item["name"] == VERIFICATION_CAPABILITY for item in selected
    )
    return _success_response(
        request_id,
        {
            "kind": "initialize_result",
            "protocol_version": INVENTORY_VERSION,
            "adapter": PRODUCER,
            "capabilities": selected,
        },
    )


def _inventory(
    session: Session,
    request_id: str,
    value: object,
    *,
    cancel_event: threading.Event,
) -> dict[str, object]:
    if session.state != "ready":
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="inventory requires an initialized session",
            request_id=request_id,
        )
    if not session.inventory_negotiated:
        raise ProtocolFailure(
            code="capability_not_negotiated",
            category="protocol_failure",
            message="inventory capability was not negotiated",
            request_id=request_id,
        )
    params = _expect_object(value, "operation params")
    _exact_fields(params, {"kind", "payload"}, request_id)
    if params["kind"] != "inventory_request":
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="inventory operation kind is invalid",
            request_id=request_id,
        )
    request = decode_inventory_request(params["payload"])
    page_request = request["page"]
    assert isinstance(page_request, dict)
    cursor = page_request["cursor"]
    if cancel_event.is_set():
        raise ScanCancelled
    if session.mode == "fail-second-page" and cursor is not None:
        raise ProtocolFailure(
            code="operation_failed",
            category="adapter_failure",
            message="deterministic second page failure",
            request_id=request_id,
        )
    run_key = _inventory_run_key(request)
    if cursor is None:
        session.inventory_complete = False
        session.mapping = None
        scan = scan_repository(
            root_path=str(request["root_path"]),
            ignore_rules=tuple(request["ignore_policy"]["rules"]),
            cancel_event=cancel_event,
        )
        session.run = build_inventory_run(request, scan)
        session.run_key = run_key
        session.inventory_request = json.loads(canonical_json(request))
    elif session.run is None or session.run_key != run_key:
        scan = scan_repository(
            root_path=str(request["root_path"]),
            ignore_rules=tuple(request["ignore_policy"]["rules"]),
            cancel_event=cancel_event,
        )
        recomputed = build_inventory_run(request, scan)
        cursor_digest = cursor["snapshot_digest"]["value"]
        if recomputed.snapshot_digest != cursor_digest:
            raise ProtocolFailure(
                code="operation_failed",
                category="adapter_failure",
                message="inventory source changed between pages",
                request_id=request_id,
            )
        session.run = recomputed
        session.run_key = run_key
    assert session.run is not None
    if cancel_event.is_set():
        raise ScanCancelled
    page = build_inventory_page(request, session.run)
    if session.mode == "invalid-page":
        payload = encode_inventory_page_payload({"kind": "inventory_page"})
    else:
        schema_uri = (
            "urn:ucf:adapter:wrong-inventory-page:1.0.0"
            if session.mode == "wrong-profile"
            else INVENTORY_PAGE_SCHEMA_URI
        )
        payload = encode_inventory_page_payload(
            page,
            schema_uri=schema_uri,
        )
    result = {
        "kind": "inventory_result",
        "payload": payload,
    }
    response = _success_response(request_id, result)
    if _bounded_response_size(response) <= MAX_FRAME_BYTES:
        session.inventory_complete = bool(page["complete"])
        return response
    requested_limit = int(page_request["record_limit"])
    for limit in range(requested_limit - 1, 0, -1):
        page = build_inventory_page(
            request,
            session.run,
            record_limit=limit,
        )
        result["payload"] = encode_inventory_page_payload(page)
        response = _success_response(request_id, result)
        if _bounded_response_size(response) <= MAX_FRAME_BYTES:
            session.inventory_complete = bool(page["complete"])
            return response
    raise ProtocolFailure(
        code="operation_failed",
        category="adapter_failure",
        message="one inventory record exceeds the response frame",
        request_id=request_id,
    )


def _discover(
    session: Session,
    request_id: str,
    value: object,
) -> dict[str, object]:
    if session.state != "ready":
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="discovery requires an initialized session",
            request_id=request_id,
        )
    if not session.discovery_negotiated:
        raise ProtocolFailure(
            code="capability_not_negotiated",
            category="protocol_failure",
            message="discovery capability was not negotiated",
            request_id=request_id,
        )
    if session.run is None or not session.inventory_complete:
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="discovery requires a completed inventory",
            request_id=request_id,
        )
    if session.mode == "fail-discovery":
        raise ProtocolFailure(
            code="operation_failed",
            category="adapter_failure",
            message="deterministic discovery failure",
            request_id=request_id,
        )
    params = _expect_object(value, "operation params")
    _exact_fields(params, {"kind", "payload"}, request_id)
    if params["kind"] != "discover_request":
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="discovery operation kind is invalid",
            request_id=request_id,
        )
    try:
        request = decode_discovery_request(
            params["payload"],
            inventory=session.run.snapshot,
        )
    except InvalidProfile as error:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="discovery request is invalid",
            request_id=request_id,
        ) from error
    result = build_discovery_result(request)
    if session.mode == "invalid-candidate":
        candidates = result["candidates"]
        assert isinstance(candidates, list)
        assert candidates
        first = candidates[0]
        assert isinstance(first, dict)
        first["semantic_digest"] = {
            "kind": "digest",
            "algorithm": "sha-256",
            "value": "0" * 64,
        }
    schema_uri = (
        "urn:ucf:adapter:wrong-discovery-result:1.0.0"
        if session.mode == "wrong-discovery-profile"
        else DISCOVERY_RESULT_SCHEMA_URI
    )
    response = _success_response(
        request_id,
        {
            "kind": "discover_result",
            "payload": encode_discovery_result_payload(
                result,
                schema_uri=schema_uri,
            ),
        },
    )
    if _bounded_response_size(response) > MAX_FRAME_BYTES:
        raise ProtocolFailure(
            code="operation_failed",
            category="adapter_failure",
            message="discovery result exceeds the response frame",
            request_id=request_id,
        )
    return response


def _shutdown(
    session: Session,
    request_id: str,
    value: object,
) -> dict[str, object]:
    if session.state != "ready":
        raise ProtocolFailure(
            code="invalid_lifecycle",
            category="protocol_failure",
            message="shutdown requires an initialized session",
            request_id=request_id,
        )
    params = _expect_object(value, "shutdown params")
    _exact_fields(params, {"kind"}, request_id)
    if params["kind"] != "shutdown_request":
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="shutdown params are invalid",
            request_id=request_id,
        )
    session.state = "closed"
    return _success_response(request_id, {"kind": "shutdown_result"})


def _decode_message(frame: bytes) -> dict[str, object]:
    request_id = _recover_request_id(frame)
    try:
        message = _strict_json(frame[:-1])
    except StrictJsonError as error:
        raise ProtocolFailure(
            code="parse_error",
            category="protocol_failure",
            message="protocol frame is not valid canonical JSON",
            request_id=None,
        ) from error
    if type(message) is not dict:
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="protocol message root must be an object",
            request_id=None,
        )
    method = message.get("method")
    notification = "id" not in message
    expected = (
        {"jsonrpc", "method", "params"}
        if notification
        else {"jsonrpc", "id", "method", "params"}
    )
    if set(message) != expected or message.get("jsonrpc") != "2.0":
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="request envelope fields are not exact",
            request_id=request_id,
        )
    if type(method) is not str:
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="request method must be a string",
            request_id=request_id,
        )
    known = {
        "ucf.initialize",
        "ucf.inventory",
        "ucf.discover",
        "ucf.map",
        "ucf.generate",
        "ucf.verify",
        "ucf.cancel",
        "ucf.shutdown",
    }
    if method not in known:
        raise ProtocolFailure(
            code="method_not_found",
            category="protocol_failure",
            message="method is not supported",
            request_id=request_id,
        )
    if notification:
        if method != "ucf.cancel":
            raise ProtocolFailure(
                code="invalid_message",
                category="protocol_failure",
                message="only cancellation may be a notification",
            )
        _validate_cancel(message["params"])
        return message
    if method == "ucf.cancel":
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="cancellation must be a notification",
            request_id=request_id,
        )
    if type(message["id"]) is not str or _REQUEST_ID.fullmatch(message["id"]) is None:
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="request ID is invalid",
            request_id=None,
        )
    if type(message["params"]) is not dict:
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="request params must be an object",
            request_id=request_id,
        )
    _validate_request_params(method, message["params"], request_id)
    return message


def _validate_request_params(
    method: str,
    value: object,
    request_id: str,
) -> None:
    params = _expect_object(value, "request params")
    if method == "ucf.initialize":
        _exact_fields(
            params,
            {"kind", "protocol_version", "client", "capabilities"},
            request_id,
        )
        expected_kind = "initialize_request"
    elif method == "ucf.shutdown":
        _exact_fields(params, {"kind"}, request_id)
        expected_kind = "shutdown_request"
    else:
        _exact_fields(params, {"kind", "payload"}, request_id)
        expected_kind = _METHOD_REQUEST_KIND[method]
    if params["kind"] != expected_kind:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="request params do not match the method",
            request_id=request_id,
        )


def _validate_cancel(value: object) -> None:
    params = _expect_object(value, "cancel params")
    if (
        set(params) != {"kind", "request_id"}
        or params["kind"] != "cancel_request"
        or type(params["request_id"]) is not str
        or _REQUEST_ID.fullmatch(params["request_id"]) is None
    ):
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="cancel params are invalid",
        )


def _read_frame() -> bytes | None:
    frame = sys.stdin.buffer.readline(MAX_FRAME_BYTES + 1)
    if not frame:
        return None
    if len(frame) > MAX_FRAME_BYTES:
        while frame and not frame.endswith(b"\n"):
            frame = sys.stdin.buffer.readline(MAX_FRAME_BYTES + 1)
        raise ProtocolFailure(
            code="frame_too_large",
            category="protocol_failure",
            message="protocol frame exceeds the byte limit",
        )
    if not frame.endswith(b"\n"):
        raise ProtocolFailure(
            code="truncated_frame",
            category="protocol_failure",
            message="protocol frame is not LF terminated",
        )
    if frame == b"\n":
        raise ProtocolFailure(
            code="invalid_message",
            category="protocol_failure",
            message="protocol frame is empty",
        )
    return frame


def _write_response(response: dict[str, object]) -> None:
    with _STDOUT_LOCK:
        frame = canonical_json(response)
        if len(frame) > MAX_FRAME_BYTES:
            frame = canonical_json(
                _error_response(
                    ProtocolFailure(
                        code="internal_error",
                        category="adapter_failure",
                        message="adapter response exceeds the frame limit",
                        request_id=(
                            response.get("id")
                            if type(response.get("id")) is str
                            else None
                        ),
                    )
                )
            )
        sys.stdout.buffer.write(frame)
        sys.stdout.buffer.flush()


def _success_response(
    request_id: str,
    result: dict[str, object],
) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _bounded_response_size(response: dict[str, object]) -> int:
    sized = dict(response)
    sized["id"] = "r" * 64
    return len(canonical_json(sized))


def _error_response(error: ProtocolFailure) -> dict[str, object]:
    code = {
        "parse_error": -32700,
        "invalid_message": -32600,
        "method_not_found": -32601,
        "invalid_params": -32602,
        "internal_error": -32603,
    }.get(error.code, -32000)
    return {
        "jsonrpc": "2.0",
        "id": error.request_id,
        "error": {
            "code": code,
            "message": error.message,
            "data": {
                "category": error.category,
                "ucf_code": error.code,
            },
        },
    }


def _strict_json(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise StrictJsonError from error
    if text.startswith("\ufeff"):
        raise StrictJsonError

    def unique(pairs):
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise StrictJsonError
            result[key] = value
        return result

    def integer(token: str) -> int:
        if token == "-0" or len(token.removeprefix("-")) > 16:
            raise StrictJsonError
        value = int(token)
        if not -9_007_199_254_740_991 <= value <= 9_007_199_254_740_991:
            raise StrictJsonError
        return value

    def reject(_token: str):
        raise StrictJsonError

    try:
        value = json.loads(
            text,
            object_pairs_hook=unique,
            parse_int=integer,
            parse_float=reject,
            parse_constant=reject,
        )
    except (json.JSONDecodeError, RecursionError) as error:
        raise StrictJsonError from error
    _validate_json_depth(value)
    return value


def _validate_json_depth(value: object) -> None:
    pending = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > 128:
            raise StrictJsonError
        if type(current) is dict:
            pending.extend((item, depth + 1) for item in current.values())
        elif type(current) is list:
            pending.extend((item, depth + 1) for item in current)
        elif current is not None and type(current) not in {bool, int, str}:
            raise StrictJsonError


def _recover_request_id(frame: bytes) -> str | None:
    try:
        value = json.loads(frame)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        type(value) is dict
        and type(value.get("id")) is str
        and _REQUEST_ID.fullmatch(value["id"]) is not None
    ):
        return value["id"]
    return None


def _inventory_run_key(request: dict[str, object]) -> bytes:
    return canonical_json(
        {
            "subject_uri": request["subject_uri"],
            "root_path": request["root_path"],
            "fact_kinds": request["fact_kinds"],
            "ignore_policy": request["ignore_policy"],
        }
    )


def _validate_producer(value: object, request_id: str) -> None:
    producer = _expect_object(value, "client producer")
    _exact_fields(producer, {"kind", "name", "version"}, request_id)
    if (
        producer["kind"] != "producer"
        or type(producer["name"]) is not str
        or _QUALIFIED_NAME.fullmatch(producer["name"]) is None
        or type(producer["version"]) is not str
        or _VERSION.fullmatch(producer["version"]) is None
    ):
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="client producer is invalid",
            request_id=request_id,
        )


def _exact_fields(
    value: dict[str, object],
    expected: set[str],
    request_id: str,
) -> None:
    if set(value) != expected:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="request params fields are not exact",
            request_id=request_id,
        )


def _expect_object(
    value: object,
    _label: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="request value must be an object",
        )
    return value


def _expect_array(value: object, request_id: str) -> list[object]:
    if type(value) is not list:
        raise ProtocolFailure(
            code="invalid_params",
            category="protocol_failure",
            message="request value must be an array",
            request_id=request_id,
        )
    return value


def _version_at_least(actual: str, minimum: str) -> bool:
    return tuple(int(part) for part in actual.split(".")) >= tuple(
        int(part) for part in minimum.split(".")
    )


if __name__ == "__main__":
    raise SystemExit(main())
