# Dependency Graph

> **Current status: implemented for a spec-only dependency graph.**
>
> The canonical capability statement and reproducible evidence are in
> [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md), especially CAP-004.

The current graph is built from specifications already loaded into a
`SpecRegistry`. It does not scan source files, imports, framework routes, test
coverage, or runtime calls. The broader code-aware graph described in the
planned section is not a current UCF capability.

## Current implemented scope

`DependencyGraph` creates one node for each loaded action, event, component,
protocol, use case, and invariant. It derives edges only from declarations in
those models:

- use-case main and alternative steps depend on their referenced actions or
  protocols;
- use cases depend on required components and referenced invariants;
- component steps depend on their referenced specs;
- a component declared as a protocol implementation is linked to that
  protocol;
- an event whose `trigger.after` is a bare action name can receive an
  action-to-event edge when that action node exists;
- an invariant's explicit `applies_to.action` and `applies_to.usecase`
  declarations constrain those specs.

References that are absent from the loaded registry are not invented as graph
nodes. Reference validity belongs to the loader, registry, and validator
boundary described by CAP-002.

### Current queries

The current implementation supports:

- direct and selected transitive spec impact for a named graph node;
- spec reference counts and isolated-spec reporting;
- Mermaid serialization of the in-memory spec graph;
- a declared write-conflict heuristic based on two otherwise independent specs
  naming the same resource in `writes`.

The write-conflict result is a review candidate. It does not prove that two
operations execute concurrently, that a transaction is unsafe, or that a
resolution strategy works.

### Current CLI surface

The repository exposes these graph subcommands:

- `ucf graph show`
- `ucf graph impact`
- `ucf graph conflicts`
- `ucf graph coverage`
- `ucf graph mermaid`

Argument details and executable evidence are controlled by the current CLI and
CAP-004. In this document, “coverage” means whether a loaded spec participates
in a declared graph relation. It is not source-code or test coverage.

## Current limitations

The current graph:

- has no source-code or import nodes;
- does not discover `@implements` mappings or filesystem conventions;
- does not update incrementally on file changes;
- does not observe runtime call graphs;
- does not execute conflict strategies, compensation, rollback, queues, or
  locks;
- does not generate or run concurrent conflict-resolution tests;
- does not establish verification evidence for a declared relationship.

Web graph views are experimental and have their own narrower status in
CAP-106.

## Planned design material — not current behavior

The following ideas are retained as design direction only. They require the
language-neutral IR, adapters, brownfield evidence, and verification packages
named in `docs/CAPABILITIES.md`.

### Code and import graph

A future discovery adapter may emit observed code symbols, imports, routes,
tests, and spec-to-code mappings with source revision, provenance, and
confidence. Those observations could extend the graph without putting
language-specific parsing in the Python core.

An illustrative future relation set is:

```text
declared spec --mapped-to--> observed code symbol
observed code symbol --imports/calls--> observed code symbol
tested check --covers--> mapped behavior
```

These edges must remain distinct from declared spec edges. A naming convention
or marker alone must not be promoted to verified implementation evidence.

### Incremental updates

A future adapter protocol may report revision-bound changes so only affected
observations and evidence are invalidated. The current graph is rebuilt from
the supplied registry and has no incremental filesystem watcher.

### Conflict policy and execution

Future work may attach explicit concurrency policies, executable checks, and
verification evidence to conflict candidates. Automatic ordering,
compensation, saga rollback, queue execution, and auto-resolution are not
implemented by the current graph.

### Rich impact analysis

Once revision-bound mappings exist, impact analysis may include observed code,
tests, adapters, and stale evidence. Until then, current impact results are
limited to declared spec relationships and must not be presented as a complete
system impact map.
