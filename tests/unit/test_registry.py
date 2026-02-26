"""Unit tests for SpecRegistry."""

from __future__ import annotations

import warnings

import pytest

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.invariant import InvariantSpec
from ucf.models.spec import parse_spec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry


def _action(name: str = "my-action") -> ActionSpec:
    return parse_spec({"kind": "action", "metadata": {"name": name}})


def _usecase(name: str = "my-uc") -> UseCaseSpec:
    return parse_spec({"kind": "usecase", "metadata": {"name": name}})


def _component(name: str = "my-comp") -> ComponentSpec:
    return parse_spec({"kind": "component", "metadata": {"name": name}})


class TestSpecRegistry:
    def test_register_and_get(self):
        r = SpecRegistry()
        a = _action()
        r.register(a)
        assert r.get("action", "my-action") is a

    def test_resolve_ref_plural(self):
        r = SpecRegistry()
        r.register(_action("foo"))
        assert r.resolve_ref("actions/foo") is not None
        assert r.resolve_ref("actions/nope") is None

    def test_resolve_ref_singular_fallback(self):
        r = SpecRegistry()
        r.register(_action("bar"))
        assert r.resolve_ref("action/bar") is not None

    def test_usecase_ref(self):
        r = SpecRegistry()
        r.register(_usecase("x"))
        assert r.resolve_ref("use-cases/x") is not None
        assert r.resolve_ref("usecase/x") is not None

    def test_duplicate_warns(self):
        r = SpecRegistry()
        r.register(_action("dup"))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            r.register(_action("dup"))
            assert len(w) == 1
            assert "Duplicate" in str(w[0].message)

    def test_all_specs(self):
        r = SpecRegistry()
        r.register(_action("a1"))
        r.register(_usecase("u1"))
        assert len(r.all_specs()) == 2

    def test_counts(self):
        r = SpecRegistry()
        r.register(_action("a1"))
        r.register(_action("a2"))
        r.register(_usecase("u1"))
        assert r.counts == {"action": 2, "usecase": 1}
        assert r.total == 3

    def test_typed_accessors(self):
        r = SpecRegistry()
        r.register(_action("x"))
        r.register(_usecase("y"))
        r.register(_component("z"))
        assert len(r.actions()) == 1
        assert len(r.usecases()) == 1
        assert len(r.components()) == 1
        assert len(r.events()) == 0
