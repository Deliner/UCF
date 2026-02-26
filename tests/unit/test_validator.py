"""Unit tests for SpecValidator."""

from __future__ import annotations

import pytest

from ucf.models.spec import parse_spec
from ucf.parser.registry import SpecRegistry
from ucf.validator.core import IssueCategory, IssueSeverity, SpecValidator


def _make_registry(*specs_data) -> SpecRegistry:
    r = SpecRegistry()
    for data in specs_data:
        r.register(parse_spec(data))
    return r


ACTION_VALIDATE = {
    "kind": "action",
    "metadata": {"name": "validate-spec"},
    "input": {"path": {"type": "string"}},
    "output": {"valid": {"type": "boolean"}},
}

ACTION_RENDER = {
    "kind": "action",
    "metadata": {"name": "render-results"},
}

USECASE_BASIC = {
    "kind": "usecase",
    "metadata": {"name": "validate-dir"},
    "steps": [
        {"id": "s1", "use": "actions/validate-spec", "input": {}, "output": {"v": "valid"}},
        {"id": "s2", "use": "actions/render-results", "input": {}, "output": {},
         "depends_on": ["s1"]},
    ],
    "postconditions": ["spec is validated"],
}


class TestNaming:
    def test_kebab_case_pass(self):
        reg = _make_registry(ACTION_VALIDATE)
        v = SpecValidator(reg)
        issues = v.validate_all()
        naming = [i for i in issues if i.category == IssueCategory.NAMING]
        assert naming == []

    def test_bad_name(self):
        data = {"kind": "action", "metadata": {"name": "BadName"}}
        reg = _make_registry(data)
        v = SpecValidator(reg)
        issues = v.validate_all()
        naming = [i for i in issues if i.category == IssueCategory.NAMING]
        assert len(naming) == 1


class TestDuplicateStepIds:
    def test_duplicate_detected(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "dup-steps"},
            "steps": [
                {"id": "s1", "use": "actions/validate-spec", "input": {}, "output": {}},
                {"id": "s1", "use": "actions/render-results", "input": {}, "output": {}},
            ],
            "postconditions": ["done"],
        }
        reg = _make_registry(ACTION_VALIDATE, ACTION_RENDER, uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        dups = [i for i in issues if i.category == IssueCategory.DUPLICATE]
        assert any("Duplicate step id" in i.message for i in dups)


class TestBrokenRefs:
    def test_missing_step_ref(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "bad-ref"},
            "steps": [
                {"id": "s1", "use": "actions/nonexistent", "input": {}, "output": {}},
            ],
            "postconditions": ["done"],
        }
        reg = _make_registry(uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        broken = [i for i in issues if i.category == IssueCategory.BROKEN_REF]
        assert len(broken) >= 1

    def test_valid_step_ref_no_warning(self):
        reg = _make_registry(ACTION_VALIDATE, ACTION_RENDER, USECASE_BASIC)
        v = SpecValidator(reg)
        issues = v.validate_all()
        broken = [i for i in issues
                  if i.category == IssueCategory.BROKEN_REF
                  and i.severity == IssueSeverity.WARNING]
        assert broken == []

    def test_bad_depends_on(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "bad-dep"},
            "steps": [
                {"id": "s1", "use": "actions/validate-spec", "input": {}, "output": {},
                 "depends_on": ["nonexistent"]},
            ],
            "postconditions": ["done"],
        }
        reg = _make_registry(ACTION_VALIDATE, uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        broken = [i for i in issues if i.category == IssueCategory.BROKEN_REF]
        assert any("nonexistent" in i.message for i in broken)


class TestOrphans:
    def test_orphan_action_detected(self):
        reg = _make_registry(ACTION_VALIDATE)
        v = SpecValidator(reg)
        issues = v.validate_all()
        orphans = [i for i in issues if i.category == IssueCategory.ORPHAN]
        assert any("validate-spec" in i.message for i in orphans)

    def test_used_action_not_orphan(self):
        reg = _make_registry(ACTION_VALIDATE, ACTION_RENDER, USECASE_BASIC)
        v = SpecValidator(reg)
        issues = v.validate_all()
        orphans = [i for i in issues
                   if i.category == IssueCategory.ORPHAN and "action" in i.message.lower()]
        assert orphans == []


class TestMissingFields:
    def test_usecase_no_steps(self):
        uc = {"kind": "usecase", "metadata": {"name": "empty"}}
        reg = _make_registry(uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        missing = [i for i in issues
                   if i.category == IssueCategory.MISSING_FIELD
                   and "no steps" in i.message]
        assert len(missing) == 1

    def test_usecase_no_postconditions(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "no-post"},
            "steps": [
                {"id": "s1", "use": "actions/validate-spec", "input": {}, "output": {}},
            ],
        }
        reg = _make_registry(ACTION_VALIDATE, uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        missing = [i for i in issues
                   if i.category == IssueCategory.MISSING_FIELD
                   and "postconditions" in i.message]
        assert len(missing) == 1
