"""State Coverage analyzer — extract implicit state machine from UCs and find gaps.

@implements("actions/analyze-state-coverage")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ucf.parser.registry import SpecRegistry
from ucf.tracer.context import Finding, FindingCategory, FindingSeverity


@dataclass
class StateNode:
    name: str
    preconditions: frozenset[str]
    postconditions: frozenset[str]
    source_ucs: list[str] = field(default_factory=list)
    terminal: bool = False


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    via_uc: str


@dataclass
class StateGraph:
    states: dict[str, StateNode] = field(default_factory=dict)
    transitions: list[StateTransition] = field(default_factory=list)
    initial_state: str = "initial"

    def reachable_from(self, start: str) -> set[str]:
        visited: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for t in self.transitions:
                if t.from_state == current and t.to_state not in visited:
                    stack.append(t.to_state)
        return visited

    def outgoing(self, state: str) -> list[StateTransition]:
        return [t for t in self.transitions if t.from_state == state]


class StateCoverageAnalyzer:
    """Builds an implicit state graph from UC pre/postconditions and checks for gaps."""

    def __init__(self, registry: SpecRegistry) -> None:
        self.registry = registry

    def analyze(self) -> tuple[StateGraph, list[Finding]]:
        graph = self._build_state_graph()
        findings = self._check_coverage(graph)
        return graph, findings

    def _build_state_graph(self) -> StateGraph:
        graph = StateGraph()
        graph.states["initial"] = StateNode(
            name="initial",
            preconditions=frozenset(),
            postconditions=frozenset(),
        )

        for uc in self.registry.usecases():
            assumed = frozenset(uc.assumed_preconditions)
            non_assumed_pre = frozenset(uc.preconditions) - assumed
            post = frozenset(uc.postconditions)

            from_state = (
                self._state_name_for(non_assumed_pre) if non_assumed_pre else "initial"
            )
            to_state = self._state_name_for(post) if post else from_state

            if from_state not in graph.states:
                graph.states[from_state] = StateNode(
                    name=from_state,
                    preconditions=non_assumed_pre,
                    postconditions=frozenset(),
                )

            if to_state not in graph.states:
                graph.states[to_state] = StateNode(
                    name=to_state,
                    preconditions=frozenset(),
                    postconditions=post,
                    source_ucs=[uc.metadata.name],
                    terminal=uc.terminal,
                )
            else:
                graph.states[to_state].source_ucs.append(uc.metadata.name)
                if uc.terminal:
                    graph.states[to_state].terminal = True

            graph.transitions.append(
                StateTransition(
                    from_state=from_state,
                    to_state=to_state,
                    via_uc=uc.metadata.name,
                )
            )

        return graph

    def _check_coverage(self, graph: StateGraph) -> list[Finding]:
        findings: list[Finding] = []

        reachable = graph.reachable_from("initial")

        for name, state in graph.states.items():
            if name == "initial":
                continue
            if name not in reachable:
                precondition_summary = (
                    sorted(state.preconditions) if state.preconditions else "none"
                )
                findings.append(
                    Finding(
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.UNREACHABLE_STATE,
                        step_id=f"state:{name}",
                        message=(
                            f"State '{name}' is not reachable from the initial state. "
                            f"Preconditions: {precondition_summary}"
                        ),
                        suggestion=(
                            "Add a use case whose postconditions establish the "
                            "preconditions "
                            "needed to reach this state"
                        ),
                    )
                )

        for name in reachable:
            if name == "initial":
                continue
            state = graph.states[name]
            outgoing = graph.outgoing(name)
            if not outgoing and not state.terminal:
                findings.append(
                    Finding(
                        severity=FindingSeverity.INFO,
                        category=FindingCategory.DEAD_END_STATE,
                        step_id=f"state:{name}",
                        message=(
                            f"State '{name}' has no outgoing use cases (dead end). "
                            f"Source UCs: {state.source_ucs}"
                        ),
                        suggestion=(
                            "Mark the use case as terminal: true if this is an "
                            "expected "
                            "leaf state, or add use cases that continue from this state"
                        ),
                    )
                )

        used_preconditions: set[str] = set()
        assumed: set[str] = set()
        produced_postconditions: set[str] = set()
        for uc in self.registry.usecases():
            used_preconditions.update(uc.preconditions)
            assumed.update(uc.assumed_preconditions)
            produced_postconditions.update(uc.postconditions)

        orphan_preconditions = used_preconditions - produced_postconditions - assumed
        for pre in orphan_preconditions:
            findings.append(
                Finding(
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.UNREACHABLE_STATE,
                    step_id="precondition",
                    message=(
                        f"Precondition '{pre}' is required by a UC but never "
                        f"established as a postcondition by any other UC"
                    ),
                    suggestion=(
                        "Add a use case whose postconditions include this "
                        "precondition, "
                        "or mark it as an external/assumed precondition"
                    ),
                )
            )

        return findings

    @staticmethod
    def _state_name_for(conditions: frozenset[str]) -> str:
        """Generate a stable name from a set of conditions."""
        if not conditions:
            return "initial"
        words: list[str] = []
        for cond in sorted(conditions):
            tokens = cond.lower().split()[:4]
            words.extend(tokens)
        slug = "-".join(words[:6])
        return slug
