# Context Tracer

> **Current status: experimental declared data-flow analysis.**
>
> The canonical capability statement and reproducible evidence are in
> [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md), especially CAP-102.

The current tracer interprets a limited subset of declarations in loaded UCF
specs. It is not a compiler, virtual machine, runtime simulator, state-machine
verifier, or proof engine. Findings are static review heuristics about the
modeled bindings; they are not observations of application behavior.

## Current experimental scope

For one loaded use case, `ContextTracer`:

1. resolves current `extends` composition;
2. seeds an abstract slot map from fields provided by required components;
3. processes main steps in declaration order;
4. records step output bindings as available slots;
5. recognizes nested `$steps.<step>.<field>` input strings as declared reads;
6. records alternative-flow reads with a simplified branch model;
7. reports selected findings over the resulting declared slot map.

The focused executable evidence demonstrates:

- `data_gap` when a recognized `$steps` field is unavailable;
- `overwrite_warning` when a later output reuses an available slot name;
- `dead_data` when a produced main-flow output has no recognized consumer;
- nested and alternative-flow reads counting as declared consumers.

The code also contains provisional type, branch, postcondition, and
cross-use-case diagnostic paths. They are not a stable semantic contract, and
some depend on constraints or types that the current source model does not
carry through an end-to-end trace. None observes transactions, threads,
messages, or runtime mutation order.

## What the tracer does not interpret

The current tracer does not execute or verify:

- action implementation code or business logic;
- `when`, `skip_if`, retry, error handling, or dependency scheduling;
- concurrency policies or transaction boundaries;
- event activation, payload mapping, delivery, or asynchronous ordering;
- invariant rules, state transitions, temporal relationships, or uniqueness;
- HTTP, CLI, Kafka, UI, GraphQL, or gRPC behavior;
- arbitrary preconditions and postconditions;
- database state, source imports, runtime telemetry, or rollback behavior.

Unsupported declarations may still be accepted by the source schema as intent.
Their presence must not be read as evidence that the tracer executed them.

## Current model

The internal context is a map of slot names to lightweight records containing
the declared type, producing step, optional constraint, state, and recognized
readers. This representation is local to the current Python prototype. It is
not the versioned language-neutral IR planned in CAP-202.

The tracer's step processing is intentionally narrower than program execution:

```text
required component fields
        |
        v
declared slot map --recognized $steps read--> heuristic finding
        |
        +--declared step output-------------> updated slot map
```

No value computation or condition evaluation occurs.

## Current CLI surface

`ucf trace` loads a spec directory, traces all or one selected use case, and
renders the declared steps, slots, and findings. Its output is diagnostic. It
does not establish `tested` or `verified` claim levels.

## Planned design material — not current behavior

The following concepts describe possible future work and must not be read as
current support.

### Language-neutral data-flow evidence

IR-002 may define typed effects, observations, mappings, confidence, and claim
levels. Adapters could then provide language-specific evidence without
embedding framework semantics in the Python core.

### Precise branch and scheduling semantics

A future verifier may model dependency ordering, conditional paths, retry,
events, and concurrency after those semantics exist in the versioned IR and
adapter protocol. The current tracer processes only the limited declarations
listed above.

### State-machine and temporal checking

A future verification package may check a named transition or temporal
property under recorded assumptions and attach reproducible evidence. There is
no current `StateMachineVerifier` or combined `UseCaseVerifier` implementation.

### Runtime correlation

Optional sanitized runtime evidence is planned separately. It would require
explicit environment identity, privacy policy, provenance, and revision
binding. The current tracer neither captures nor replays runtime behavior.
