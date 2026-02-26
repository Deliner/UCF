# Use Case-Driven Development Framework (UCF)

## Problem

Modern spec-driven tools operate at the level of individual operations (OpenAPI describes one endpoint, Arazzo chains HTTP calls, OpenSpec manages text specs without formal verification). None of them solve the problem of **formal verification of system behavior at the level of user scenarios** — with composition, reuse, conflict detection, and cross-platform test generation.

Agentic development (Cursor, Claude Code, Codex) makes this worse: AI agents don't understand business context, lose context in long sessions, and can't see dependencies between system components.

## Philosophy

### Principle 1: Use Case is the Unit of Software

The minimal unit of software value is not a function, class, or endpoint — it's a **Use Case**: a complete user scenario. Everything else (code, tests, infrastructure) exists only to make Use Cases work.

### Principle 2: Compose, Don't Duplicate

Any specification element is described once and reused via references. Duplication is a spec bug.

### Principle 3: If It's Not Verified, It Doesn't Exist

A specification without automatic verification is documentation. Documentation rots. Verification doesn't.

## Positioning

| | OpenAPI | Arazzo | OpenSpec | **UCF** |
|---|---|---|---|---|
| Abstraction Level | Single operation | HTTP call chain | Text spec | Use Case (full scenario) |
| Format | YAML (typed) | YAML (typed) | Markdown (free) | YAML (typed) |
| Platforms | HTTP | HTTP | Any (text) | HTTP, gRPC, GraphQL, UI, CLI, MQ |
| Composition | No | Minimal | No | Full (components, protocols, $ref) |
| Test Generation | Yes (contract) | Partial | No | Yes (E2E, alt flows, invariants, conflicts) |
| Dependency Graph | No | No | No | Yes (spec↔spec, spec↔code, code↔code) |
| Conflict Detection | No | No | No | Yes (static + dynamic) |
| Drift Detection | No | No | No | Yes (code→spec, spec→code) |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   SPEC LANGUAGE                       │
│  Primitives: Action, Event, Component, Protocol,     │
│              UseCase, Invariant                       │
├──────────────────────────────────────────────────────┤
│                  CONTEXT TRACER                       │
│  Abstract context model ("eidos") that verifies       │
│  data flow without executing code                     │
├──────────────────────────────────────────────────────┤
│                 DEPENDENCY GRAPH                      │
│  Edge types: spec→spec, spec→code, code→code         │
│  + conflict edges: spec⟷spec                         │
├──────────────────────────────────────────────────────┤
│               GENERATOR ENGINE                        │
│  Plugin system: pytest, jest, playwright,             │
│  go-test, mock-server, mermaid-docs                   │
├──────────────────────────────────────────────────────┤
│              VALIDATOR ENGINE                         │
│  Spec validation, drift detection, coverage,          │
│  conflict detection, invariant verification           │
├──────────────────────────────────────────────────────┤
│              INTEGRATION LAYER                        │
│  CLI, CI/CD, IDE (LSP), Cursor hooks, Git hooks       │
└──────────────────────────────────────────────────────┘
```

## Documentation Index

| Document | Description |
|---|---|
| [SPEC_LANGUAGE.md](SPEC_LANGUAGE.md) | The 6 specification primitives with full syntax |
| [CONTEXT_TRACER.md](CONTEXT_TRACER.md) | Abstract context model and business logic compiler |
| [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) | Dependency graph, impact analysis, conflict detection |
| [GENERATORS.md](GENERATORS.md) | Test generation architecture (interface + orchestrator + implementation) |
| [INVARIANTS.md](INVARIANTS.md) | Invariant types and 4-level verification system |
| [CURSOR_HOOKS.md](CURSOR_HOOKS.md) | Cursor IDE hooks for agent discipline |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Tech stack, phases, adoption strategy |
| [CRITIQUE.md](CRITIQUE.md) | Known limitations, edge cases, and mitigations |

## Core Formula

```
Use Case = State Setup + Action Sequence + Verification
```

- **State Setup**: Bring the system to the required initial state
- **Action Sequence**: Execute steps in correct order with correct data
- **Verification**: Confirm the system is in the correct final state

The framework generates the **structure** (what to test, in what order) deterministically. AI generates the **implementation** (how to call, how to assert). The human controls **everything**.
