from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from ucf.adapter_protocol import (
    AdapterDispatcher,
    AdapterPayload,
    AdapterRequestCancelled,
    CapabilitySelection,
    Method,
    RequestContext,
    run_stdio_server,
)
from ucf.ir.models import (
    BooleanValue,
    Producer,
    RecordEntry,
    RecordValue,
    StringValue,
)

_CAPABILITIES = (
    "org.ucf.adapter.inventory",
    "org.ucf.adapter.discovery",
    "org.ucf.adapter.mapping",
    "org.ucf.adapter.generation",
    "org.ucf.adapter.verification",
)
_STDERR_PROBE_BYTES = 1_048_576
_CONTROL_SCHEMA_URI = "urn:ucf:adapter-conformance:control:1.0.0"
_ACTIVE_CONTROL_REQUESTS: set[str] = set()


def _record_entries(value: RecordValue) -> dict[str, object]:
    return {entry.name: entry.value for entry in value.entries}


def _control_result(
    payload: AdapterPayload,
    *entries: RecordEntry,
) -> AdapterPayload:
    return payload.model_copy(
        update={
            "value": RecordValue(
                kind="record",
                entries=entries,
            )
        }
    )


async def _handle(
    method: Method,
    payload,
    context: RequestContext,
):
    del method
    if not isinstance(payload, AdapterPayload):
        return payload

    if (
        payload.schema_uri == _CONTROL_SCHEMA_URI
        and isinstance(payload.value, RecordValue)
    ):
        entries = _record_entries(payload.value)
        operation = entries.get("operation")
        if isinstance(operation, StringValue) and operation.value == "block":
            _ACTIVE_CONTROL_REQUESTS.add(context.request_id)
            try:
                await context.cancelled.wait()
            finally:
                _ACTIVE_CONTROL_REQUESTS.discard(context.request_id)
            raise AdapterRequestCancelled
        if (
            isinstance(operation, StringValue)
            and operation.value == "readiness"
        ):
            target = entries.get("target_request_id")
            assert isinstance(target, StringValue)
            return _control_result(
                payload,
                RecordEntry(
                    kind="record_entry",
                    name="operation",
                    value=StringValue(
                        kind="string",
                        value="readiness_result",
                    ),
                ),
                RecordEntry(
                    kind="record_entry",
                    name="target_request_id",
                    value=target,
                ),
                RecordEntry(
                    kind="record_entry",
                    name="active",
                    value=BooleanValue(
                        kind="boolean",
                        value=target.value in _ACTIVE_CONTROL_REQUESTS,
                    ),
                ),
            )
        if isinstance(operation, StringValue) and operation.value == "echo":
            return _control_result(
                payload,
                RecordEntry(
                    kind="record_entry",
                    name="operation",
                    value=StringValue(
                        kind="string",
                        value="echo_result",
                    ),
                ),
                RecordEntry(
                    kind="record_entry",
                    name="value",
                    value=entries["value"],
                ),
            )

    if payload.schema_uri.endswith(":block"):
        await context.cancelled.wait()
        raise AdapterRequestCancelled

    if payload.schema_uri.endswith(":delay"):
        assert isinstance(payload.value, StringValue)
        await asyncio.sleep(float(payload.value.value))
        return payload

    if payload.schema_uri.endswith(":stderr-flood"):
        sys.stderr.buffer.write(b"x" * _STDERR_PROBE_BYTES)
        sys.stderr.buffer.flush()
        return payload

    if payload.schema_uri.endswith(":environment"):
        return payload.model_copy(
            update={
                "value": BooleanValue(
                    kind="boolean",
                    value="UCF_ADAPTER_SENTINEL_SECRET" in os.environ,
                )
            }
        )

    if payload.schema_uri.endswith(":python-runtime-environment"):
        return payload.model_copy(
            update={
                "value": BooleanValue(
                    kind="boolean",
                    value=any(
                        name in os.environ
                        for name in (
                            "PYTHONDONTWRITEBYTECODE",
                            "PYTHONUTF8",
                        )
                    ),
                )
            }
        )

    if payload.schema_uri.endswith(":cwd"):
        return payload.model_copy(
            update={
                "value": StringValue(
                    kind="string",
                    value=str(Path.cwd()),
                )
            }
        )

    return payload


def _dispatcher() -> AdapterDispatcher:
    return AdapterDispatcher(
        adapter=Producer(
            kind="producer",
            name="org.ucf.reference-adapter",
            version="1.0.0",
        ),
        offered_capabilities=tuple(
            CapabilitySelection(
                kind="capability",
                name=name,
                version="1.0.0",
            )
            for name in _CAPABILITIES
        ),
        handler=_handle,
    )


if __name__ == "__main__":
    raise SystemExit(run_stdio_server(_dispatcher()))
