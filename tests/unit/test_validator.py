"""Unit tests for SpecValidator."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucf.models.spec import parse_spec
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.validator.core import IssueCategory, IssueSeverity, SpecValidator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
        {
            "id": "s1",
            "use": "actions/validate-spec",
            "input": {},
            "output": {"v": "valid"},
        },
        {
            "id": "s2",
            "use": "actions/render-results",
            "input": {},
            "output": {},
            "depends_on": ["s1"],
        },
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
                {
                    "id": "s1",
                    "use": "actions/render-results",
                    "input": {},
                    "output": {},
                },
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
        assert all(issue.severity == IssueSeverity.ERROR for issue in broken)

    def test_valid_step_ref_no_warning(self):
        reg = _make_registry(ACTION_VALIDATE, ACTION_RENDER, USECASE_BASIC)
        v = SpecValidator(reg)
        issues = v.validate_all()
        broken = [
            i
            for i in issues
            if i.category == IssueCategory.BROKEN_REF
            and i.severity == IssueSeverity.WARNING
        ]
        assert broken == []

    def test_bad_depends_on(self):
        uc = {
            "kind": "usecase",
            "metadata": {"name": "bad-dep"},
            "steps": [
                {
                    "id": "s1",
                    "use": "actions/validate-spec",
                    "input": {},
                    "output": {},
                    "depends_on": ["nonexistent"],
                },
            ],
            "postconditions": ["done"],
        }
        reg = _make_registry(ACTION_VALIDATE, uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        broken = [i for i in issues if i.category == IssueCategory.BROKEN_REF]
        assert any("nonexistent" in i.message for i in broken)


MISSING_REFERENCE_CASES = [
    (
        {
            "kind": "usecase",
            "metadata": {"name": "missing-requirement"},
            "requires": [{"$ref": "components/missing", "as": "missing"}],
            "steps": [],
        },
        "requires",
    ),
    (
        {
            "kind": "usecase",
            "metadata": {"name": "missing-invariant"},
            "invariants": [{"$ref": "invariants/missing"}],
            "steps": [],
        },
        "invariant",
    ),
    (
        {
            "kind": "action",
            "metadata": {"name": "missing-emitted-event"},
            "emits": [{"event": "events/missing"}],
        },
        "emits",
    ),
    (
        {
            "kind": "event",
            "metadata": {"name": "missing-trigger-action"},
            "trigger": {"after": "missing"},
        },
        "trigger",
    ),
    (
        {
            "kind": "protocol",
            "metadata": {"name": "missing-implementation"},
            "implementations": [{"$ref": "components/missing"}],
        },
        "implementation",
    ),
    (
        {
            "kind": "invariant",
            "metadata": {"name": "missing-action-binding"},
            "type": "data",
            "rule": "must hold",
            "applies_to": [{"action": "actions/missing"}],
        },
        "applies_to.action",
    ),
    (
        {
            "kind": "invariant",
            "metadata": {"name": "missing-usecase-binding"},
            "type": "data",
            "rule": "must hold",
            "applies_to": [{"usecase": "use-cases/missing"}],
        },
        "applies_to.usecase",
    ),
    (
        {
            "kind": "usecase",
            "metadata": {"name": "missing-trigger-event"},
            "trigger": "event/missing",
            "steps": [],
        },
        "trigger",
    ),
    (
        {
            "kind": "usecase",
            "metadata": {"name": "missing-parent"},
            "extends": "use-cases/missing",
            "steps": [],
        },
        "extends",
    ),
]


class TestReferenceContracts:
    @staticmethod
    def _reference_errors(*specs_data) -> list:
        return [
            issue
            for issue in SpecValidator(_make_registry(*specs_data)).validate_all()
            if issue.category
            in (IssueCategory.BROKEN_REF, IssueCategory.TYPE_MISMATCH)
            and issue.severity == IssueSeverity.ERROR
        ]

    @pytest.mark.parametrize(("owner_spec", "relationship"), MISSING_REFERENCE_CASES)
    def test_missing_identity_reference_is_an_error(
        self, owner_spec: dict, relationship: str
    ) -> None:
        errors = self._reference_errors(owner_spec)

        matching = [issue for issue in errors if relationship in issue.message]
        assert matching
        assert all(issue.category == IssueCategory.BROKEN_REF for issue in matching)

    @pytest.mark.parametrize(
        ("target_spec", "owner_spec", "relationship"),
        [
            (
                {"kind": "component", "metadata": {"name": "wrong"}},
                {
                    "kind": "usecase",
                    "metadata": {"name": "wrong-step-kind"},
                    "steps": [{"id": "s1", "use": "components/wrong"}],
                },
                "step",
            ),
            (
                {"kind": "action", "metadata": {"name": "wrong"}},
                {
                    "kind": "usecase",
                    "metadata": {"name": "wrong-requirement-kind"},
                    "requires": [{"$ref": "actions/wrong", "as": "wrong"}],
                    "steps": [],
                },
                "requires",
            ),
            (
                {"kind": "action", "metadata": {"name": "wrong"}},
                {
                    "kind": "action",
                    "metadata": {"name": "wrong-emitted-kind"},
                    "emits": [{"event": "actions/wrong"}],
                },
                "emits",
            ),
            (
                {"kind": "component", "metadata": {"name": "wrong"}},
                {
                    "kind": "event",
                    "metadata": {"name": "wrong-trigger-kind"},
                    "trigger": {"after": "components/wrong"},
                },
                "trigger",
            ),
            (
                {"kind": "action", "metadata": {"name": "wrong"}},
                {
                    "kind": "protocol",
                    "metadata": {"name": "wrong-implementation-kind"},
                    "implementations": [{"$ref": "actions/wrong"}],
                },
                "implementation",
            ),
            (
                {"kind": "usecase", "metadata": {"name": "wrong"}, "steps": []},
                {
                    "kind": "invariant",
                    "metadata": {"name": "wrong-action-binding"},
                    "type": "data",
                    "rule": "must hold",
                    "applies_to": [{"action": "use-cases/wrong"}],
                },
                "applies_to.action",
            ),
            (
                {"kind": "action", "metadata": {"name": "wrong"}},
                {
                    "kind": "usecase",
                    "metadata": {"name": "wrong-invariant-kind"},
                    "invariants": [{"$ref": "actions/wrong"}],
                    "steps": [],
                },
                "invariant",
            ),
            (
                {"kind": "action", "metadata": {"name": "wrong"}},
                {
                    "kind": "invariant",
                    "metadata": {"name": "wrong-usecase-binding"},
                    "type": "data",
                    "rule": "must hold",
                    "applies_to": [{"usecase": "actions/wrong"}],
                },
                "applies_to.usecase",
            ),
            (
                {"kind": "action", "metadata": {"name": "wrong"}},
                {
                    "kind": "usecase",
                    "metadata": {"name": "wrong-parent-kind"},
                    "extends": "actions/wrong",
                    "steps": [],
                },
                "extends",
            ),
        ],
    )
    def test_reference_to_wrong_spec_kind_is_an_error(
        self, target_spec: dict, owner_spec: dict, relationship: str
    ) -> None:
        errors = self._reference_errors(target_spec, owner_spec)

        matching = [issue for issue in errors if relationship in issue.message]
        assert matching
        assert all(issue.category == IssueCategory.TYPE_MISMATCH for issue in matching)

    def test_alternative_flow_depends_on_unknown_step_is_an_error(self) -> None:
        usecase = {
            "kind": "usecase",
            "metadata": {"name": "bad-alt-dependency"},
            "steps": [{"id": "main", "use": "actions/validate-spec"}],
            "alternative_flows": [
                {
                    "name": "fallback",
                    "trigger": "failure",
                    "steps": [
                        {
                            "id": "recover",
                            "use": "actions/render-results",
                            "depends_on": ["missing"],
                        }
                    ],
                }
            ],
        }

        errors = self._reference_errors(ACTION_VALIDATE, ACTION_RENDER, usecase)

        assert any("alternative flow" in issue.message for issue in errors)

    def test_component_depends_on_unknown_step_is_an_error(self) -> None:
        component = {
            "kind": "component",
            "metadata": {"name": "bad-component-dependency"},
            "steps": [
                {
                    "id": "run",
                    "use": "actions/validate-spec",
                    "depends_on": ["missing"],
                }
            ],
        }

        errors = self._reference_errors(ACTION_VALIDATE, component)

        assert any("component" in issue.message for issue in errors)

    def test_valid_cross_kind_references_have_no_reference_errors(self) -> None:
        action = {
            "kind": "action",
            "metadata": {"name": "publish-result"},
            "emits": [{"event": "events/result-published"}],
        }
        event = {
            "kind": "event",
            "metadata": {"name": "result-published"},
            "trigger": {"after": "actions/publish-result"},
        }
        component = {
            "kind": "component",
            "metadata": {"name": "publisher"},
            "steps": [{"id": "publish", "use": "actions/publish-result"}],
        }
        protocol = {
            "kind": "protocol",
            "metadata": {"name": "publishing"},
            "implementations": [{"$ref": "components/publisher"}],
        }
        invariant = {
            "kind": "invariant",
            "metadata": {"name": "published-result-valid"},
            "type": "data",
            "rule": "published result is valid",
            "applies_to": [
                {"action": "actions/publish-result"},
                {"usecase": "use-cases/publish-result"},
            ],
        }
        usecase = {
            "kind": "usecase",
            "metadata": {"name": "publish-result"},
            "trigger": "event/result-published",
            "requires": [{"$ref": "components/publisher", "as": "publisher"}],
            "steps": [{"id": "publish", "use": "protocols/publishing"}],
            "invariants": [{"$ref": "invariants/published-result-valid"}],
        }

        assert (
            self._reference_errors(
                action,
                event,
                component,
                protocol,
                invariant,
                usecase,
            )
            == []
        )


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
        orphans = [
            i
            for i in issues
            if i.category == IssueCategory.ORPHAN and "action" in i.message.lower()
        ]
        assert orphans == []


class TestMissingFields:
    def test_usecase_no_steps(self):
        uc = {"kind": "usecase", "metadata": {"name": "empty"}}
        reg = _make_registry(uc)
        v = SpecValidator(reg)
        issues = v.validate_all()
        missing = [
            i
            for i in issues
            if i.category == IssueCategory.MISSING_FIELD and "no steps" in i.message
        ]
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
        missing = [
            i
            for i in issues
            if i.category == IssueCategory.MISSING_FIELD
            and "postconditions" in i.message
        ]
        assert len(missing) == 1


class TestRepositorySpecs:
    def test_all_specs_parse_and_step_references_resolve(self):
        loaded, load_errors = SpecLoader(PROJECT_ROOT / "specs").load_all_tolerant()
        assert load_errors == []

        registry = SpecRegistry()
        for _path, spec in loaded:
            registry.register(spec)

        reference_errors = [
            issue
            for issue in SpecValidator(registry).validate_all()
            if issue.category
            in (IssueCategory.BROKEN_REF, IssueCategory.TYPE_MISMATCH)
        ]
        assert reference_errors == []
