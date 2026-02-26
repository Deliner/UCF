"""Central registry of all loaded specs with lookup by kind, name, and ref path."""

from __future__ import annotations

from pathlib import Path

from ucf.models.action import ActionSpec
from ucf.models.component import ComponentSpec
from ucf.models.event import EventSpec
from ucf.models.invariant import InvariantSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.spec import AnySpec
from ucf.models.usecase import UseCaseSpec

_KIND_PLURAL: dict[type, str] = {
    ActionSpec: "actions",
    EventSpec: "events",
    ComponentSpec: "components",
    ProtocolSpec: "protocols",
    UseCaseSpec: "use-cases",
    InvariantSpec: "invariants",
}


class SpecRegistry:
    """Holds all loaded specs indexed by kind and name."""

    def __init__(self) -> None:
        self._by_kind: dict[str, dict[str, AnySpec]] = {}
        self._by_ref: dict[str, AnySpec] = {}
        self._paths: dict[str, Path] = {}

    def register(self, spec: AnySpec, path: Path | None = None) -> None:
        kind = spec.kind
        name = spec.metadata.name

        self._by_kind.setdefault(kind, {})[name] = spec

        plural = _KIND_PLURAL.get(type(spec), f"{kind}s")
        ref_key = f"{plural}/{name}"
        self._by_ref[ref_key] = spec

        if path is not None:
            self._paths[ref_key] = path

    def get(self, kind: str, name: str) -> AnySpec | None:
        return self._by_kind.get(kind, {}).get(name)

    def resolve_ref(self, ref: str) -> AnySpec | None:
        return self._by_ref.get(ref)

    def get_path(self, ref: str) -> Path | None:
        return self._paths.get(ref)

    def all_specs(self) -> list[AnySpec]:
        return [spec for group in self._by_kind.values() for spec in group.values()]

    def specs_of_kind(self, kind: str) -> list[AnySpec]:
        return list(self._by_kind.get(kind, {}).values())

    def actions(self) -> list[ActionSpec]:
        return [s for s in self.specs_of_kind("action") if isinstance(s, ActionSpec)]

    def events(self) -> list[EventSpec]:
        return [s for s in self.specs_of_kind("event") if isinstance(s, EventSpec)]

    def components(self) -> list[ComponentSpec]:
        return [s for s in self.specs_of_kind("component") if isinstance(s, ComponentSpec)]

    def protocols(self) -> list[ProtocolSpec]:
        return [s for s in self.specs_of_kind("protocol") if isinstance(s, ProtocolSpec)]

    def usecases(self) -> list[UseCaseSpec]:
        return [s for s in self.specs_of_kind("usecase") if isinstance(s, UseCaseSpec)]

    def invariants(self) -> list[InvariantSpec]:
        return [s for s in self.specs_of_kind("invariant") if isinstance(s, InvariantSpec)]

    @property
    def counts(self) -> dict[str, int]:
        return {kind: len(specs) for kind, specs in self._by_kind.items()}

    @property
    def total(self) -> int:
        return sum(len(specs) for specs in self._by_kind.values())
