"""Unit tests for use case composition (extends)."""

from __future__ import annotations

import pytest

from ucf.composition import CompositionError, resolve_extends
from ucf.models.base import Metadata
from ucf.models.component import StepDef
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry


def _uc(
    name: str,
    steps: list[dict] | None = None,
    postconditions: list[str] | None = None,
    preconditions: list[str] | None = None,
    extends: str | None = None,
    invariants: list[dict] | None = None,
    requires: list[dict] | None = None,
) -> UseCaseSpec:
    return UseCaseSpec(
        metadata=Metadata(name=name, version="0.1.0"),
        extends=extends,
        steps=[StepDef(**s) for s in (steps or [])],
        postconditions=postconditions or [],
        preconditions=preconditions or [],
        invariants=[{"$ref": r["$ref"]} for r in (invariants or [])],
        requires=[{"$ref": r["$ref"], "as": r["as"]} for r in (requires or [])],
    )


class TestBasicExtends:
    def test_no_extends_returns_unchanged(self):
        reg = SpecRegistry()
        uc = _uc("standalone", steps=[{"id": "s1", "use": "actions/foo", "input": {}}])
        reg.register(uc)

        flat, chain, parent_ids = resolve_extends(uc, reg)
        assert flat is uc
        assert chain == ["standalone"]
        assert parent_ids == []

    def test_simple_extends(self):
        reg = SpecRegistry()
        parent = _uc(
            "parent",
            steps=[{"id": "p1", "use": "actions/a", "input": {}}],
            postconditions=["parent done"],
        )
        child = _uc(
            "child",
            extends="$ref:use-cases/parent",
            steps=[{"id": "c1", "use": "actions/b", "input": {}}],
            postconditions=["child done"],
        )
        reg.register(parent)
        reg.register(child)

        flat, chain, parent_ids = resolve_extends(child, reg)

        assert [s.id for s in flat.steps] == ["p1", "c1"]
        assert flat.postconditions == ["parent done", "child done"]
        assert parent_ids == ["p1"]
        assert flat.metadata.name == "child"
        assert flat.extends is None

    def test_multi_level_extends(self):
        reg = SpecRegistry()
        grandparent = _uc("gp", steps=[{"id": "g1", "use": "actions/a", "input": {}}])
        parent = _uc(
            "p",
            extends="$ref:use-cases/gp",
            steps=[{"id": "p1", "use": "actions/b", "input": {}}],
        )
        child = _uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "c1", "use": "actions/c", "input": {}}],
        )
        reg.register(grandparent)
        reg.register(parent)
        reg.register(child)

        flat, chain, parent_ids = resolve_extends(child, reg)
        assert [s.id for s in flat.steps] == ["g1", "p1", "c1"]
        assert "gp" in chain and "p" in chain and "c" in chain


class TestMerging:
    def test_preconditions_merged(self):
        reg = SpecRegistry()
        p = _uc(
            "p", steps=[{"id": "p1", "use": "a", "input": {}}], preconditions=["pre-a"]
        )
        c = _uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "c1", "use": "b", "input": {}}],
            preconditions=["pre-b"],
        )
        reg.register(p)
        reg.register(c)
        flat, _, _ = resolve_extends(c, reg)
        assert "pre-a" in flat.preconditions
        assert "pre-b" in flat.preconditions

    def test_duplicate_postconditions_deduplicated(self):
        reg = SpecRegistry()
        p = _uc(
            "p", steps=[{"id": "p1", "use": "a", "input": {}}], postconditions=["done"]
        )
        c = _uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "c1", "use": "b", "input": {}}],
            postconditions=["done", "extra"],
        )
        reg.register(p)
        reg.register(c)
        flat, _, _ = resolve_extends(c, reg)
        assert flat.postconditions.count("done") == 1

    def test_invariants_merged(self):
        reg = SpecRegistry()
        p = _uc(
            "p",
            steps=[{"id": "p1", "use": "a", "input": {}}],
            invariants=[{"$ref": "invariants/inv-a"}],
        )
        c = _uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "c1", "use": "b", "input": {}}],
            invariants=[{"$ref": "invariants/inv-b"}],
        )
        reg.register(p)
        reg.register(c)
        flat, _, _ = resolve_extends(c, reg)
        inv_refs = [
            i.ref if hasattr(i, "ref") else i.get("$ref") for i in flat.invariants
        ]
        assert "invariants/inv-a" in inv_refs
        assert "invariants/inv-b" in inv_refs


class TestErrors:
    def test_parent_not_found(self):
        reg = SpecRegistry()
        c = _uc(
            "c",
            extends="$ref:use-cases/nonexistent",
            steps=[{"id": "c1", "use": "a", "input": {}}],
        )
        reg.register(c)
        with pytest.raises(CompositionError, match="PARENT_NOT_FOUND"):
            resolve_extends(c, reg)

    def test_circular_extends(self):
        reg = SpecRegistry()
        a = _uc(
            "a",
            extends="$ref:use-cases/b",
            steps=[{"id": "a1", "use": "x", "input": {}}],
        )
        b = _uc(
            "b",
            extends="$ref:use-cases/a",
            steps=[{"id": "b1", "use": "y", "input": {}}],
        )
        reg.register(a)
        reg.register(b)
        with pytest.raises(CompositionError, match="CIRCULAR_EXTENDS"):
            resolve_extends(a, reg)

    def test_step_id_clash(self):
        reg = SpecRegistry()
        p = _uc("p", steps=[{"id": "clash", "use": "a", "input": {}}])
        c = _uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "clash", "use": "b", "input": {}}],
        )
        reg.register(p)
        reg.register(c)
        with pytest.raises(CompositionError, match="STEP_ID_CLASH"):
            resolve_extends(c, reg)

    def test_extends_non_usecase(self):
        from ucf.models.action import ActionSpec

        reg = SpecRegistry()
        action = ActionSpec(
            metadata=Metadata(name="some-action", version="0.1.0"),
        )
        reg.register(action)
        c = _uc(
            "c",
            extends="$ref:actions/some-action",
            steps=[{"id": "c1", "use": "a", "input": {}}],
        )
        reg.register(c)
        with pytest.raises(CompositionError, match="PARENT_NOT_FOUND"):
            resolve_extends(c, reg)


class TestValidatorExtendsRules:
    def test_validator_catches_broken_extends(self):
        from ucf.validator.core import IssueSeverity, SpecValidator

        reg = SpecRegistry()
        c = _uc(
            "c",
            extends="$ref:use-cases/missing",
            steps=[{"id": "c1", "use": "a", "input": {}}],
        )
        reg.register(c)
        v = SpecValidator(reg)
        issues = v.validate_all()
        errors = [
            i
            for i in issues
            if i.severity == IssueSeverity.ERROR and "extends" in i.message
        ]
        assert len(errors) >= 1

    def test_validator_catches_step_clash(self):
        from ucf.validator.core import IssueSeverity, SpecValidator

        reg = SpecRegistry()
        p = _uc("p", steps=[{"id": "s1", "use": "a", "input": {}}])
        c = _uc(
            "c",
            extends="$ref:use-cases/p",
            steps=[{"id": "s1", "use": "b", "input": {}}],
        )
        reg.register(p)
        reg.register(c)
        v = SpecValidator(reg)
        issues = v.validate_all()
        errors = [
            i
            for i in issues
            if i.severity == IssueSeverity.ERROR and "conflict" in i.message
        ]
        assert len(errors) >= 1
