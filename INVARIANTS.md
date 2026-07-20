# Invariants

> **Current status: experimental declaration support, not enforcement.**
>
> The canonical capability statement and reproducible evidence are in
> [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md), especially CAP-105 and
> CAP-107.

UCF currently parses selected invariant intent and validates a limited set of
references. It does not formally prove invariant rules, automatically enforce
them at runtime, generate state-machine verification, monitor production,
rollback transactions, or apply fixes.

## Current experimental scope

The strict source model accepts these invariant type labels:

- `data`
- `relationship`
- `aggregate`
- `state-machine`
- `temporal`
- `uniqueness`
- `composite`

Parser acceptance means only that a document matches the current source shape.
It does not mean the rule is executable or true.

The current registry-aware validator:

- requires an invariant to contain `rule`, `rules`, or `transitions`;
- resolves `applies_to.action` as an action reference;
- resolves `applies_to.usecase` as a use-case reference;
- resolves invariant references declared by use cases;
- reports missing and wrong-kind supported references as errors.

`applies_to.resource`, entity names, state names, temporal `before`/`after`
maps, and `composed_of` entries remain declaration-only data. They are not
typed, resolved verification contracts in the current model.

The dependency graph can represent explicit action/use-case constraint edges.
Completeness analyzers can report heuristic candidates based on declared
references and resources. Neither operation evaluates the invariant rule or
raises its claim above declared/mapped intent.

Where the current Python skeleton generator emits a `verify_*` method for an
invariant binding, that method is a user-owned implementation obligation. Its
name does not interpret the rule; a passing generated suite is evidence only
for assertions that the user implementation actually executes.

## Declaration examples

These examples show accepted intent, not executable enforcement.

### Data declaration

```yaml
kind: invariant
metadata:
  name: stock-never-negative
  severity: critical
type: data
entity: product
field: stock
condition: ">= 0"
rule: product.stock >= 0
applies_to:
  - resource: product
  - action: actions/purchase-product
```

### State-machine declaration

```yaml
kind: invariant
metadata:
  name: order-state-machine
type: state-machine
entity: order
field: status
states: [pending, confirmed, shipped, cancelled]
transitions:
  pending: [confirmed, cancelled]
  confirmed: [shipped, cancelled]
forbidden:
  - { from: cancelled, to: any, reason: terminal state }
applies_to:
  - resource: order
```

### Temporal declaration

```yaml
kind: invariant
metadata:
  name: payment-before-fulfillment
type: temporal
rule: payment.completed_at < shipment.created_at
before: { event: payment-completed, field: payment.completed_at }
after: { event: shipment-created, field: shipment.created_at }
join: shipment.order_id = payment.order_id
```

The current parser retains these state and temporal declarations. It does not
check the transitions or event ordering.

## Current limitations

- Invariant expressions are not parsed into a language-neutral executable
  expression model.
- Resource and entity bindings are not resolved against a canonical domain
  model.
- Temporal event names and composite members are not strict identity
  references.
- Referencing an invariant does not make a use case tested.
- A write to a named resource is not proof that an invariant is guarded.
- There is no automatic property-test generation for invariant semantics.
- There is no runtime decorator, transaction savepoint, rollback, audit hook,
  production monitor, alert integration, or auto-fix mechanism.
- There is no formal proof or exhaustive state-space result.

## Planned design material — not current behavior

The following verification levels are design goals only. They depend on the
versioned IR, adapters, executable generation, and revision-bound evidence
listed in `docs/CAPABILITIES.md`.

### Planned static checking

A future verifier may evaluate typed state transitions, temporal ordering, and
composite rules over a precisely defined graph. Any result must name the
property, assumptions, algorithm, source revision, and checked artifacts.

### Planned generated checks

Future generators may emit executable property or state-machine tests when an
adapter declares the necessary capabilities. Generated obligations alone are
not evidence; only a named executed check with recorded results can support a
`tested` claim.

### Planned runtime enforcement

Runtime guards, transaction rollback, and application-specific error handling
would require adapter-owned execution semantics. They must not be inferred
from the current Python source model.

### Planned production monitoring

Scheduled checks, alert integrations, privacy-safe observations, and any
remediation workflow belong to explicit runtime-evidence and release packages.
Automatic monitoring, rollback, and auto-fix are not current UCF features.

### Planned conflict protection

Future conflict analysis may relate an executable invariant check to a
revision-bound concurrency finding. The current graph reports only declared
write-conflict candidates and explicit constraint relationships; it does not
evaluate protection adequacy.
