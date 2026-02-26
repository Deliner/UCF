"""Unit tests for spec parsing and model validation."""

from __future__ import annotations

import pytest

from ucf.models.spec import AnySpec, SpecParseError, parse_spec
from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.event import EventSpec
from ucf.models.invariant import InvariantSpec, InvariantType
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec


def _minimal(kind: str, **overrides) -> dict:
    base = {"kind": kind, "metadata": {"name": f"test-{kind}"}}
    if kind == "invariant":
        base["type"] = "data"
        base["rule"] = "must hold"
    base.update(overrides)
    return base


class TestParseSpec:
    def test_action(self):
        spec = parse_spec(_minimal("action"))
        assert isinstance(spec, ActionSpec)
        assert spec.metadata.name == "test-action"

    def test_event(self):
        spec = parse_spec(_minimal("event"))
        assert isinstance(spec, EventSpec)

    def test_component(self):
        spec = parse_spec(_minimal("component"))
        assert isinstance(spec, ComponentSpec)

    def test_protocol(self):
        spec = parse_spec(_minimal("protocol"))
        assert isinstance(spec, ProtocolSpec)

    def test_usecase(self):
        spec = parse_spec(_minimal("usecase"))
        assert isinstance(spec, UseCaseSpec)

    def test_invariant(self):
        spec = parse_spec(_minimal("invariant"))
        assert isinstance(spec, InvariantSpec)
        assert spec.type == InvariantType.DATA

    def test_missing_kind(self):
        with pytest.raises(SpecParseError, match="Missing 'kind'"):
            parse_spec({"metadata": {"name": "x"}})

    def test_unknown_kind(self):
        with pytest.raises(SpecParseError, match="Unknown kind 'bogus'"):
            parse_spec({"kind": "bogus", "metadata": {"name": "x"}})

    def test_validation_error_missing_name(self):
        with pytest.raises(SpecParseError, match="Validation error"):
            parse_spec({"kind": "action"})

    def test_non_dict_input(self):
        with pytest.raises(SpecParseError, match="Expected a YAML mapping"):
            parse_spec("not a dict")  # type: ignore[arg-type]

    def test_source_path_propagated(self):
        with pytest.raises(SpecParseError) as exc_info:
            parse_spec({"kind": "bad"}, source_path="/a/b.yaml")
        assert exc_info.value.path == "/a/b.yaml"

    def test_action_with_input_output(self):
        data = _minimal("action")
        data["input"] = {"qty": {"type": "integer", "required": True}}
        data["output"] = {"order_id": {"type": "string"}}
        spec = parse_spec(data)
        assert isinstance(spec, ActionSpec)
        assert "qty" in spec.input
        assert "order_id" in spec.output

    def test_usecase_with_steps(self):
        data = _minimal("usecase")
        data["steps"] = [
            {"id": "s1", "use": "actions/foo", "input": {}, "output": {"x": "x"}},
        ]
        spec = parse_spec(data)
        assert isinstance(spec, UseCaseSpec)
        assert len(spec.steps) == 1
        assert spec.steps[0].id == "s1"

    def test_invariant_all_types(self):
        for it in InvariantType:
            data = _minimal("invariant", type=it.value)
            spec = parse_spec(data)
            assert spec.type == it
