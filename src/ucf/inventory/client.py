from __future__ import annotations

from pathlib import Path

from ucf.adapter_protocol import (
    AdapterProcess,
    AdapterProtocolError,
    CapabilityRequest,
    ErrorCategory,
    Method,
    ProcessState,
    ProcessTimeouts,
    ProtocolCode,
)
from ucf.inventory.models import (
    INVENTORY_CAPABILITY,
    INVENTORY_VERSION,
    MAX_INVENTORY_PAGES,
    MAX_INVENTORY_RECORDS,
    InventoryPage,
    InventoryPageRequest,
    InventoryRequest,
    InventorySnapshot,
)
from ucf.inventory.paging import assemble_inventory_pages
from ucf.inventory.wire import (
    inventory_page_from_payload,
    inventory_request_to_payload,
)


async def collect_inventory(
    *,
    command: tuple[str, ...],
    cwd: Path,
    request: InventoryRequest,
    timeouts: ProcessTimeouts | None = None,
    operation_timeout: float | None = None,
) -> InventorySnapshot:
    """Collect and validate one complete inventory in one adapter session."""

    if not isinstance(request, InventoryRequest):
        raise TypeError("inventory request must be a validated model")
    if request.page.cursor is not None:
        raise ValueError("inventory collection must start without a cursor")

    adapter = AdapterProcess(
        command=command,
        cwd=cwd,
        requested_capabilities=(
            CapabilityRequest(
                kind="capability_request",
                name=INVENTORY_CAPABILITY,
                minimum_version=INVENTORY_VERSION,
                required=True,
            ),
        ),
        timeouts=timeouts,
    )
    try:
        await adapter.start()
        return await collect_inventory_from_process(
            adapter,
            request=request,
            operation_timeout=operation_timeout,
        )
    finally:
        await adapter.close()


async def collect_inventory_from_process(
    adapter: AdapterProcess,
    *,
    request: InventoryRequest,
    operation_timeout: float | None = None,
) -> InventorySnapshot:
    """Collect inventory through one already initialized adapter session."""

    if not isinstance(adapter, AdapterProcess):
        raise TypeError("adapter must be an AdapterProcess")
    if adapter.state is not ProcessState.READY:
        raise ValueError("adapter must be initialized before inventory")
    if not isinstance(request, InventoryRequest):
        raise TypeError("inventory request must be a validated model")
    if request.page.cursor is not None:
        raise ValueError("inventory collection must start without a cursor")

    pages: list[InventoryPage] = []
    cursor = None
    record_count = 0
    while True:
        page_request = InventoryPageRequest(
            kind="inventory_page_request",
            record_limit=request.page.record_limit,
            cursor=cursor,
        )
        current_request = request.model_copy(
            update={"page": page_request}
        )
        raw_page = await adapter.call(
            Method.INVENTORY,
            inventory_request_to_payload(current_request),
            timeout=operation_timeout,
        )
        page = _decode_adapter_page(raw_page)
        if page.request_cursor != cursor:
            raise _invalid_adapter_output()
        if len(page.records) > request.page.record_limit:
            raise _invalid_adapter_output()

        pages.append(page)
        record_count += len(page.records)
        if (
            len(pages) > MAX_INVENTORY_PAGES
            or record_count > MAX_INVENTORY_RECORDS
        ):
            raise _invalid_adapter_output()
        if page.complete:
            break
        if len(pages) == MAX_INVENTORY_PAGES:
            raise _invalid_adapter_output()
        cursor = page.next_cursor

    try:
        return assemble_inventory_pages(
            tuple(pages),
            record_limit=request.page.record_limit,
        )
    except ValueError as error:
        raise _invalid_adapter_output() from error


def _decode_adapter_page(payload: object) -> InventoryPage:
    try:
        return inventory_page_from_payload(payload)
    except (TypeError, ValueError) as error:
        raise _invalid_adapter_output() from error


def _invalid_adapter_output() -> AdapterProtocolError:
    return AdapterProtocolError(
        ErrorCategory.PROCESS_FAILURE,
        ProtocolCode.INVALID_ADAPTER_OUTPUT,
        "adapter returned an invalid inventory page",
    )
