"""Resource Conflict Coverage — shared resources must be guarded.

@implements("actions/analyze-resource-conflicts")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding, FindingCategory, FindingSeverity


@dataclass
class ResourceConflict:
    resource: str
    writers: list[str] = field(default_factory=list)
    has_invariant: bool = False
    has_concurrency_policy: bool = False
    guarded_by_ucs: list[str] = field(default_factory=list)

    @property
    def is_guarded(self) -> bool:
        return self.has_invariant or self.has_concurrency_policy


class ResourceConflictAnalyzer:
    """When two actions write the same resource, verify guards exist."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> tuple[list[ResourceConflict], list[Finding]]:
        conflicts: list[ResourceConflict] = []
        findings: list[Finding] = []

        resource_writers = self._collect_resource_writers()
        guarded_resources = self._collect_guarded_resources()
        concurrency_resources = self._collect_concurrency_policies()

        for resource, writers in resource_writers.items():
            if len(writers) < 2:
                continue

            conflict = ResourceConflict(
                resource=resource,
                writers=sorted(writers),
                has_invariant=resource in guarded_resources,
                has_concurrency_policy=resource in concurrency_resources,
                guarded_by_ucs=sorted(concurrency_resources.get(resource, [])),
            )
            conflicts.append(conflict)

            if not conflict.is_guarded:
                findings.append(
                    Finding(
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.UNGUARDED_RESOURCE_CONFLICT,
                        step_id=f"resource:{resource}",
                        message=(
                            f"Resource '{resource}' is written by multiple actions "
                            f"({', '.join(sorted(writers))}) but has no invariant or "
                            f"concurrency policy guarding it"
                        ),
                        suggestion=(
                            f"Add an invariant for '{resource}' or add a concurrency "
                            f"policy to use cases that access it"
                        ),
                    )
                )

        return conflicts, findings

    def _collect_resource_writers(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for action in self.registry.actions():
            for write in action.writes:
                result.setdefault(write.resource, set()).add(action.metadata.name)
        return result

    def _collect_guarded_resources(self) -> set[str]:
        guarded: set[str] = set()
        for inv in self.registry.invariants():
            for binding in inv.applies_to:
                if binding.resource:
                    guarded.add(binding.resource)
            if inv.entity:
                guarded.add(inv.entity)
        return guarded

    def _collect_concurrency_policies(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for uc in self.registry.usecases():
            for conc in uc.concurrency:
                result.setdefault(conc.conflict, []).append(uc.metadata.name)
        return result
