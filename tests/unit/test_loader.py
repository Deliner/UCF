"""Unit tests for SpecLoader — YAML loading and $ref resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.spec import SpecParseError
from ucf.parser.loader import RefResolutionError, SpecLoader


@pytest.fixture
def tmp_specs(tmp_path: Path):
    """Create a temp specs directory helper."""

    def write(name: str, content: str) -> Path:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    return write


class TestSpecLoader:
    def test_load_simple_action(self, tmp_path, tmp_specs):
        tmp_specs(
            "actions/greet.yaml",
            """
kind: action
metadata:
  name: greet
input:
  name: {type: string}
output:
  greeting: {type: string}
""",
        )
        loader = SpecLoader(tmp_path)
        spec = loader.load_file(tmp_path / "actions/greet.yaml")
        assert isinstance(spec, ActionSpec)
        assert spec.metadata.name == "greet"

    def test_ref_resolution(self, tmp_path, tmp_specs):
        tmp_specs(
            "actions/base.yaml",
            """
kind: action
metadata:
  name: base
""",
        )
        tmp_specs(
            "use-cases/uc.yaml",
            """
kind: usecase
metadata:
  name: uc
steps:
  - id: s1
    use: actions/base
    input: {}
    output: {}
requires:
  - $ref: actions/base
    as: b
""",
        )
        loader = SpecLoader(tmp_path)
        pairs = loader.load_all()
        assert len(pairs) == 2

    def test_ref_depth_exceeded(self, tmp_path, tmp_specs):
        tmp_specs(
            "a.yaml", "kind: action\nmetadata:\n  name: a\nreads:\n  - $ref: b.yaml\n"
        )
        tmp_specs(
            "b.yaml", "kind: action\nmetadata:\n  name: b\nreads:\n  - $ref: c.yaml\n"
        )
        tmp_specs(
            "c.yaml", "kind: action\nmetadata:\n  name: c\nreads:\n  - $ref: d.yaml\n"
        )
        tmp_specs("d.yaml", "kind: action\nmetadata:\n  name: d\n")

        loader = SpecLoader(tmp_path)
        with pytest.raises(RefResolutionError, match="depth"):
            loader.load_file(tmp_path / "a.yaml")

    def test_path_traversal_blocked(self, tmp_path, tmp_specs):
        evil = tmp_path.parent / "evil.yaml"
        evil.write_text("kind: action\nmetadata:\n  name: evil\n", encoding="utf-8")

        tmp_specs(
            "uc.yaml",
            """
kind: usecase
metadata:
  name: bad
invariants:
  - $ref: ../evil
""",
        )
        loader = SpecLoader(tmp_path)
        with pytest.raises(RefResolutionError, match="outside base directory"):
            loader.load_file(tmp_path / "uc.yaml")

    def test_missing_file(self, tmp_path):
        loader = SpecLoader(tmp_path)
        with pytest.raises(SpecParseError, match="File not found"):
            loader.load_file(tmp_path / "nope.yaml")

    def test_non_dict_yaml(self, tmp_path, tmp_specs):
        tmp_specs("bad.yaml", "- just\n- a\n- list\n")
        loader = SpecLoader(tmp_path)
        with pytest.raises(SpecParseError, match="Expected YAML mapping"):
            loader.load_file(tmp_path / "bad.yaml")

    def test_load_all_tolerant(self, tmp_path, tmp_specs):
        tmp_specs("actions/good.yaml", "kind: action\nmetadata:\n  name: good\n")
        tmp_specs("actions/bad.yaml", "kind: bogus\nmetadata:\n  name: bad\n")
        loader = SpecLoader(tmp_path)
        results, errors = loader.load_all_tolerant()
        assert len(results) == 1
        assert len(errors) == 1

    def test_file_cache(self, tmp_path, tmp_specs):
        tmp_specs("a.yaml", "kind: action\nmetadata:\n  name: a\n")
        loader = SpecLoader(tmp_path)
        loader.load_file(tmp_path / "a.yaml")
        loader.load_file(tmp_path / "a.yaml")
        assert len(loader._file_cache) == 1

    def test_protocol_logical_ref_loads_as_typed_resolved_implementation(
        self, tmp_path, tmp_specs
    ):
        tmp_specs(
            "components/worker.yml",
            "kind: component\nmetadata:\n  name: worker\n",
        )
        protocol_path = tmp_specs(
            "protocols/work.yaml",
            """\
kind: protocol
metadata:
  name: work
implementations:
  - $ref: components/worker
""",
        )

        protocol = SpecLoader(tmp_path).load_file(protocol_path)

        assert isinstance(protocol, ProtocolSpec)
        assert len(protocol.implementations) == 1
        assert isinstance(protocol.implementations[0], ComponentSpec)
        assert protocol.implementations[0].metadata.name == "worker"

    def test_non_string_ref_is_reported_as_ref_resolution_error(
        self, tmp_path, tmp_specs
    ):
        usecase_path = tmp_specs(
            "use-cases/bad-ref.yaml",
            """\
kind: usecase
metadata:
  name: bad-ref
invariants:
  - $ref: 123
""",
        )

        with pytest.raises(RefResolutionError, match="must be a string"):
            SpecLoader(tmp_path).load_file(usecase_path)

    @pytest.mark.parametrize(
        ("target_kind", "target_name", "actual_identity"),
        [
            ("component", "impostor", "component/impostor"),
            ("action", "worker", "action/worker"),
        ],
    )
    def test_logical_ref_target_must_match_declared_identity(
        self,
        tmp_path,
        tmp_specs,
        target_kind,
        target_name,
        actual_identity,
    ):
        tmp_specs(
            "components/worker.yaml",
            f"kind: {target_kind}\nmetadata:\n  name: {target_name}\n",
        )
        protocol_path = tmp_specs(
            "protocols/work.yaml",
            """\
kind: protocol
metadata:
  name: work
implementations:
  - $ref: components/worker
""",
        )

        with pytest.raises(
            RefResolutionError,
            match=f"components/worker.*{actual_identity}",
        ):
            SpecLoader(tmp_path).load_file(protocol_path)

    @pytest.mark.parametrize(
        ("singular", "plural", "kind", "extra"),
        [
            ("action", "actions", "action", ""),
            ("event", "events", "event", ""),
            ("component", "components", "component", ""),
            ("protocol", "protocols", "protocol", ""),
            ("usecase", "use-cases", "usecase", ""),
            ("invariant", "invariants", "invariant", "type: data\nrule: valid\n"),
        ],
    )
    def test_singular_logical_ref_alias_loads_canonical_identity(
        self,
        tmp_path,
        tmp_specs,
        singular,
        plural,
        kind,
        extra,
    ):
        tmp_specs(
            f"{plural}/worker.yaml",
            f"kind: {kind}\nmetadata:\n  name: worker\n{extra}",
        )
        alias_path = tmp_specs("alias.yaml", f"$ref: {singular}/worker\n")

        loaded = SpecLoader(tmp_path).load_file(alias_path)

        assert loaded.kind == kind
        assert loaded.metadata.name == "worker"

    def test_default_directory_load_discovers_yaml_and_yml(self, tmp_path, tmp_specs):
        tmp_specs("actions/one.yaml", "kind: action\nmetadata:\n  name: one\n")
        tmp_specs("actions/two.yml", "kind: action\nmetadata:\n  name: two\n")

        loaded = SpecLoader(tmp_path).load_all()

        assert {spec.metadata.name for _, spec in loaded} == {"one", "two"}
