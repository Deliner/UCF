"""Unit tests for ContextTracer."""

from __future__ import annotations

from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import FindingCategory, FindingSeverity
from ucf.tracer.engine import ContextTracer


def _registry_with(*specs_data) -> SpecRegistry:
    r = SpecRegistry()
    for d in specs_data:
        r.register(parse_spec(d))
    return r


ACTION_CREATE = {
    "kind": "action",
    "metadata": {"name": "create-order"},
    "input": {"item": {"type": "string"}},
    "output": {"order_id": {"type": "string"}, "total": {"type": "number"}},
}

ACTION_CONFIRM = {
    "kind": "action",
    "metadata": {"name": "confirm-order"},
    "input": {"order_id": {"type": "string"}},
    "output": {"confirmed": {"type": "boolean"}},
}

COMPONENT_AUTH = {
    "kind": "component",
    "metadata": {"name": "auth"},
    "provides": {
        "user_id": {"type": "string"},
        "token": {"type": "string"},
    },
}


class TestHappyPath:
    def test_no_findings_for_clean_flow(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "order-flow"},
            "requires": [{"$ref": "components/auth", "as": "auth"}],
            "steps": [
                {
                    "id": "create",
                    "use": "actions/create-order",
                    "input": {"item": "$inputs.item"},
                    "output": {"order_id": "order_id", "total": "total"},
                },
                {
                    "id": "confirm",
                    "use": "actions/confirm-order",
                    "input": {"order_id": "$steps.create.order_id"},
                    "output": {"confirmed": "confirmed"},
                },
            ],
            "postconditions": ["order is confirmed"],
        }
        reg = _registry_with(ACTION_CREATE, ACTION_CONFIRM, COMPONENT_AUTH, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        errors = [f for f in findings if f.severity == FindingSeverity.ERROR]
        assert errors == []


class TestDataGap:
    def test_reading_undefined_field(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "gap-uc"},
            "steps": [
                {
                    "id": "confirm",
                    "use": "actions/confirm-order",
                    "input": {"order_id": "$steps.nonexistent.order_id"},
                    "output": {"confirmed": "confirmed"},
                },
            ],
            "postconditions": ["done"],
        }
        reg = _registry_with(ACTION_CONFIRM, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        gaps = [f for f in findings if f.category == FindingCategory.DATA_GAP]
        assert len(gaps) >= 1


class TestDeadData:
    def test_unused_output_flagged(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "dead-uc"},
            "steps": [
                {
                    "id": "create",
                    "use": "actions/create-order",
                    "input": {"item": "$inputs.item"},
                    "output": {"order_id": "order_id", "total": "total"},
                },
            ],
            "postconditions": ["done"],
        }
        reg = _registry_with(ACTION_CREATE, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        dead = [f for f in findings if f.category == FindingCategory.DEAD_DATA]
        assert len(dead) >= 1

    def test_consumed_output_not_dead(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "alive-uc"},
            "steps": [
                {
                    "id": "create",
                    "use": "actions/create-order",
                    "input": {"item": "$inputs.item"},
                    "output": {"order_id": "order_id"},
                },
                {
                    "id": "confirm",
                    "use": "actions/confirm-order",
                    "input": {"order_id": "$steps.create.order_id"},
                    "output": {"confirmed": "confirmed"},
                },
            ],
            "postconditions": ["done"],
        }
        reg = _registry_with(ACTION_CREATE, ACTION_CONFIRM, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        dead = [
            f
            for f in findings
            if f.category == FindingCategory.DEAD_DATA and "order_id" in f.message
        ]
        assert dead == []


class TestNestedReads:
    def test_nested_dict_binding(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "nested-uc"},
            "steps": [
                {
                    "id": "create",
                    "use": "actions/create-order",
                    "input": {"item": "$inputs.item"},
                    "output": {"order_id": "order_id"},
                },
                {
                    "id": "confirm",
                    "use": "actions/confirm-order",
                    "input": {
                        "data": {
                            "id": "$steps.create.order_id",
                        }
                    },
                    "output": {"confirmed": "confirmed"},
                },
            ],
            "postconditions": ["done"],
        }
        reg = _registry_with(ACTION_CREATE, ACTION_CONFIRM, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        dead_order = [
            f
            for f in findings
            if f.category == FindingCategory.DEAD_DATA and "order_id" in f.message
        ]
        assert dead_order == []


class TestOverwrite:
    def test_overwrite_warning(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "overwrite-uc"},
            "steps": [
                {
                    "id": "s1",
                    "use": "actions/create-order",
                    "input": {},
                    "output": {"order_id": "order_id"},
                },
                {
                    "id": "s2",
                    "use": "actions/create-order",
                    "input": {},
                    "output": {"order_id": "order_id"},
                },
            ],
            "postconditions": ["done"],
        }
        reg = _registry_with(ACTION_CREATE, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        overwrites = [
            f for f in findings if f.category == FindingCategory.OVERWRITE_WARNING
        ]
        assert len(overwrites) >= 1


class TestAltFlowDeadData:
    def test_alt_flow_read_prevents_dead_data(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "alt-uc"},
            "steps": [
                {
                    "id": "create",
                    "use": "actions/create-order",
                    "input": {},
                    "output": {"order_id": "order_id"},
                },
            ],
            "alternative_flows": [
                {
                    "name": "cancel",
                    "trigger": "user cancels",
                    "steps": [
                        {
                            "id": "cancel-step",
                            "use": "actions/confirm-order",
                            "input": {"order_id": "$steps.create.order_id"},
                            "output": {},
                        },
                    ],
                },
            ],
            "postconditions": ["done"],
        }
        reg = _registry_with(ACTION_CREATE, ACTION_CONFIRM, uc)
        tracer = ContextTracer(reg)
        findings = tracer.trace_usecase(reg.usecases()[0])
        dead_order = [
            f
            for f in findings
            if f.category == FindingCategory.DEAD_DATA and "order_id" in f.message
        ]
        assert dead_order == []
