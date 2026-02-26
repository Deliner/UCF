"""Dependency graph: spec→spec, spec→code, conflict edges, impact analysis.

@implements("actions/build-dependency-graph")
@implements("actions/compute-impact")
@implements("actions/detect-write-conflicts")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import networkx as nx

from ucf.models.action import ActionSpec
from ucf.models.protocol import ProtocolSpec
from ucf.models.usecase import UseCaseSpec
from ucf.parser.registry import SpecRegistry


class EdgeType(str, Enum):
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    CONFLICTS_WITH = "conflicts_with"
    CONSTRAINS = "constrains"
    EMITS = "emits"
    TRIGGERS = "triggers"


@dataclass
class ImpactResult:
    """Result of an impact analysis query."""
    target: str
    direct_dependents: list[str] = field(default_factory=list)
    transitive_dependents: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    """Spec coverage statistics."""
    counts: dict[str, tuple[int, int]] = field(default_factory=dict)
    orphans: list[str] = field(default_factory=list)


class DependencyGraph:
    """Builds and queries a directed graph from UCF specs."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry
        self.g = nx.DiGraph()
        self._build()

    def _build(self) -> None:
        for spec in self.registry.all_specs():
            node_id = self._node_id(spec)
            self.g.add_node(node_id, kind=spec.kind, name=spec.metadata.name)

        for uc in self.registry.usecases():
            uc_id = f"usecase/{uc.metadata.name}"
            self._build_usecase_edges(uc, uc_id)

        for comp in self.registry.components():
            comp_id = f"component/{comp.metadata.name}"
            for step in comp.steps:
                target = self._normalize_ref(step.use)
                if self.g.has_node(target):
                    self.g.add_edge(comp_id, target, type=EdgeType.DEPENDS_ON.value)

        for proto in self.registry.protocols():
            proto_id = f"protocol/{proto.metadata.name}"
            for impl_ref in proto.implementations:
                target = self._normalize_ref(impl_ref.ref)
                if self.g.has_node(target):
                    self.g.add_edge(target, proto_id, type=EdgeType.IMPLEMENTS.value)

        for event in self.registry.events():
            event_id = f"event/{event.metadata.name}"
            if event.trigger and event.trigger.after:
                target = f"action/{event.trigger.after}"
                if self.g.has_node(target):
                    self.g.add_edge(target, event_id, type=EdgeType.EMITS.value)

        for inv in self.registry.invariants():
            inv_id = f"invariant/{inv.metadata.name}"
            for binding in inv.applies_to:
                if binding.action:
                    target = self._normalize_ref(binding.action)
                    if self.g.has_node(target):
                        self.g.add_edge(inv_id, target, type=EdgeType.CONSTRAINS.value)
                if binding.usecase:
                    target = self._normalize_ref(binding.usecase)
                    if self.g.has_node(target):
                        self.g.add_edge(inv_id, target, type=EdgeType.CONSTRAINS.value)

    def _build_usecase_edges(self, uc: UseCaseSpec, uc_id: str) -> None:
        for step in uc.steps:
            target = self._normalize_ref(step.use)
            if self.g.has_node(target):
                self.g.add_edge(uc_id, target, type=EdgeType.DEPENDS_ON.value)

        for alt in uc.alternative_flows:
            for step in alt.steps:
                target = self._normalize_ref(step.use)
                if self.g.has_node(target):
                    self.g.add_edge(uc_id, target, type=EdgeType.DEPENDS_ON.value)

        for req in uc.requires:
            if isinstance(req, dict):
                ref = req.get("$ref", "")
            else:
                ref = req.ref
            target = self._normalize_ref(ref)
            if self.g.has_node(target):
                self.g.add_edge(uc_id, target, type=EdgeType.DEPENDS_ON.value)

        for inv_ref in uc.invariants:
            if isinstance(inv_ref, dict):
                ref = inv_ref.get("$ref", "")
            else:
                ref = inv_ref.ref
            target = self._normalize_ref(ref)
            if self.g.has_node(target):
                self.g.add_edge(uc_id, target, type=EdgeType.DEPENDS_ON.value)

    def impact(self, node_id: str) -> ImpactResult:
        node_id = self._normalize_ref(node_id)
        result = ImpactResult(target=node_id)

        if not self.g.has_node(node_id):
            return result

        for pred in self.g.predecessors(node_id):
            edge_data = self.g.edges[pred, node_id]
            if edge_data.get("type") == EdgeType.CONSTRAINS.value:
                result.invariants.append(pred)
            elif edge_data.get("type") == EdgeType.CONFLICTS_WITH.value:
                result.conflicts.append(pred)
            else:
                result.direct_dependents.append(pred)

        for ancestor in nx.ancestors(self.g, node_id):
            if ancestor not in result.direct_dependents and ancestor != node_id:
                data = self.g.nodes.get(ancestor, {})
                if data.get("kind") in ("usecase", "component"):
                    result.transitive_dependents.append(ancestor)

        return result

    def find_write_conflicts(self) -> list[tuple[str, str, str]]:
        """Find pairs of independent specs that write to the same resource.

        Skips conflicts between a use case and its own child actions/protocols,
        since those are expected intra-scenario writes.
        """
        resource_writers: dict[str, list[str]] = {}

        for spec in self.registry.all_specs():
            node_id = self._node_id(spec)
            resources = self._extract_writes(spec)
            for res in resources:
                resource_writers.setdefault(res, []).append(node_id)

        parent_children: dict[str, set[str]] = {}
        for uc in self.registry.usecases():
            uc_id = self._node_id(uc)
            children: set[str] = set()
            for step in uc.steps:
                children.add(self._normalize_ref(step.use))
            for alt in uc.alternative_flows:
                for step in alt.steps:
                    children.add(self._normalize_ref(step.use))
            parent_children[uc_id] = children

        def _is_related(a: str, b: str) -> bool:
            if a == b:
                return True
            if a in parent_children and b in parent_children[a]:
                return True
            if b in parent_children and a in parent_children[b]:
                return True
            return False

        conflicts = []
        for resource, writers in resource_writers.items():
            unique = sorted(set(writers))
            if len(unique) < 2:
                continue
            for i, w1 in enumerate(unique):
                for w2 in unique[i + 1:]:
                    if not _is_related(w1, w2):
                        conflicts.append((w1, w2, resource))

        return conflicts

    def coverage(self) -> CoverageReport:
        report = CoverageReport()
        for kind in ("action", "event", "component", "protocol", "usecase", "invariant"):
            specs = self.registry.specs_of_kind(kind)
            referenced = sum(
                1 for s in specs
                if self.g.in_degree(self._node_id(s)) > 0
                or self.g.out_degree(self._node_id(s)) > 0
            )
            report.counts[kind] = (referenced, len(specs))

        for node in self.g.nodes():
            if self.g.degree(node) == 0:
                report.orphans.append(node)

        return report

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self.g.nodes():
            safe = node.replace("/", "_").replace("-", "_")
            lines.append(f"    {safe}[\"{node}\"]")

        for u, v, data in self.g.edges(data=True):
            u_safe = u.replace("/", "_").replace("-", "_")
            v_safe = v.replace("/", "_").replace("-", "_")
            label = data.get("type", "")
            lines.append(f"    {u_safe} -->|{label}| {v_safe}")

        return "\n".join(lines)

    def _node_id(self, spec) -> str:
        kind = spec.kind
        name = spec.metadata.name
        return f"{kind}/{name}"

    def _normalize_ref(self, ref: str) -> str:
        """Normalize refs like 'actions/foo' -> 'action/foo'."""
        parts = ref.split("/", 1)
        if len(parts) == 2:
            plural_map = {
                "actions": "action",
                "events": "event",
                "components": "component",
                "protocols": "protocol",
                "use-cases": "usecase",
                "invariants": "invariant",
            }
            parts[0] = plural_map.get(parts[0], parts[0])
            return "/".join(parts)
        return ref

    def _extract_writes(self, spec) -> list[str]:
        resources = []
        if isinstance(spec, ActionSpec):
            resources = [w.resource for w in spec.writes]
        elif isinstance(spec, ProtocolSpec):
            resources = [w.resource for w in spec.writes]
        elif isinstance(spec, UseCaseSpec):
            all_steps = list(spec.steps)
            for alt in spec.alternative_flows:
                all_steps.extend(alt.steps)
            for step in all_steps:
                action = self.registry.resolve_ref(step.use)
                if isinstance(action, ActionSpec):
                    resources.extend(w.resource for w in action.writes)
        return resources
