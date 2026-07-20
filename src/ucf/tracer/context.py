"""Core data structures for context tracing: slots, snapshots, effects, findings."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import StrEnum


class SlotState(StrEnum):
    AVAILABLE = "available"
    MUTATED = "mutated"
    INVALIDATED = "invalidated"


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingCategory(StrEnum):
    DATA_GAP = "data_gap"
    DEAD_DATA = "dead_data"
    TYPE_MISMATCH = "type_mismatch"
    OVERWRITE_WARNING = "overwrite_warning"
    BRANCH_DIVERGENCE = "branch_divergence"
    BRANCH_STATE_DIFFERENCE = "branch_state_difference"
    FORBIDDEN_TRANSITION = "forbidden_transition"
    CROSS_UC_MUTATION_CONFLICT = "cross_uc_mutation_conflict"
    MISSING_POSTCONDITION = "missing_postcondition"
    UNCOVERED_ERROR = "uncovered_error"
    UNCOVERED_INPUT_PARTITION = "uncovered_input_partition"
    UNREACHABLE_STATE = "unreachable_state"
    DEAD_END_STATE = "dead_end_state"
    UNCOVERED_HTTP_SCENARIO = "uncovered_http_scenario"
    UNTESTABLE_INVARIANT = "untestable_invariant"
    UNGUARDED_RESOURCE_CONFLICT = "unguarded_resource_conflict"


@dataclass
class ContextSlot:
    name: str
    type: str
    source_step: str
    state: SlotState = SlotState.AVAILABLE
    constraint: str | None = None
    read_by: list[str] = field(default_factory=list)


@dataclass
class ContextSnapshot:
    step_id: str
    slots: dict[str, ContextSlot] = field(default_factory=dict)

    def has(self, name: str) -> bool:
        slot = self.slots.get(name)
        return slot is not None and slot.state != SlotState.INVALIDATED

    def get_type(self, name: str) -> str | None:
        slot = self.slots.get(name)
        return slot.type if slot else None

    def fork(self, new_step_id: str) -> ContextSnapshot:
        forked = copy.deepcopy(self)
        forked.step_id = new_step_id
        return forked


@dataclass(frozen=True)
class ReadEffect:
    field: str
    expected_type: str = ""


@dataclass(frozen=True)
class WriteEffect:
    field: str
    type: str = ""
    constraint: str | None = None


@dataclass(frozen=True)
class InvalidateEffect:
    field: str


@dataclass
class ActionEffect:
    reads: list[ReadEffect] = field(default_factory=list)
    writes: list[WriteEffect] = field(default_factory=list)
    invalidates: list[InvalidateEffect] = field(default_factory=list)

    @classmethod
    def from_step_spec(cls, step: dict) -> ActionEffect:
        (
            "Build effect from a use case step, deriving reads/writes from "
            "input/output."
        )
        reads: list[ReadEffect] = []
        writes: list[WriteEffect] = []

        for field_name, binding in step.get("input", {}).items():
            if isinstance(binding, str) and binding.startswith("$steps."):
                parts = binding.split(".")
                if len(parts) >= 3:
                    reads.append(ReadEffect(field=parts[2]))

        for field_name, binding in step.get("output", {}).items():
            writes.append(
                WriteEffect(field=binding if isinstance(binding, str) else field_name)
            )

        return cls(reads=reads, writes=writes)


@dataclass(frozen=True)
class Finding:
    severity: FindingSeverity
    category: FindingCategory
    step_id: str
    message: str
    suggestion: str = ""
