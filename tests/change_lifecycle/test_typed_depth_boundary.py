from __future__ import annotations

import pytest

from ucf.change_lifecycle import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
    canonical_change_lifecycle_json,
)
from ucf.ir.models import ListValue, NullValue

from ._fixture_factory import lifecycle_chain


def test_canonical_typed_boundary_rejects_excessive_depth_at_exact_location() -> None:
    nested = NullValue(kind="null")
    for _ in range(600):
        nested = ListValue(kind="list", items=(nested,))

    record = lifecycle_chain().implementation
    binding = record.bindings[0]
    request = binding.result.request
    first_input = request.inputs[0].model_copy(update={"value": nested})
    request = request.model_copy(update={"inputs": (first_input, *request.inputs[1:])})
    result = binding.result.model_copy(update={"request": request})
    binding = binding.model_copy(update={"result": result})
    record = record.model_copy(update={"bindings": (binding, *record.bindings[1:])})

    with pytest.raises(ChangeLifecycleValidationError) as captured:
        canonical_change_lifecycle_json(record)

    expected_location = (
        "$.bindings[0].result.request.inputs[0].value" + ".items[0]" * 61
    )
    assert captured.value.code is ChangeLifecycleErrorCode.INVALID_STRUCTURE
    assert captured.value.location == expected_location
    assert "maximum typed nesting depth of 128" in str(captured.value)


def test_canonical_typed_depth_guard_preserves_valid_canonical_bytes() -> None:
    record = lifecycle_chain().implementation

    first = canonical_change_lifecycle_json(record)
    second = canonical_change_lifecycle_json(record)

    assert first == second
