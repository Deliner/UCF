# Invariants

## What is an Invariant

An invariant is a statement that is **always true**, regardless of which use case executes, in what order, how many times, by which actor. If an invariant is violated, the system is broken. No exceptions.

Unlike preconditions/postconditions (which belong to one use case), an invariant spans the entire system:

```
Precondition:  "user must be logged in before purchasing"  → one use case
Postcondition: "order status is 'pending' after creation"  → one use case
Invariant:     "stock quantity is never negative"          → all use cases, all time
```

---

## Six Types of Invariants

### Type 1: Data Invariant

A field value always satisfies a constraint. No action in the system can produce a value that breaks this rule.

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
  - action: actions/restock-product
  - action: actions/cancel-order
```

### Type 2: Relationship Invariant

If entity X exists in a certain state, entity Y must exist. Both directions must be specified.

```yaml
kind: invariant
metadata:
  name: payment-requires-order
  severity: critical
type: relationship
rule: |
  forward:  every completed payment must reference an existing order
  inverse:  deleting an order is forbidden while completed payments exist
entities:
  source: { entity: payment, condition: "payment.status = completed" }
  target: { entity: order, field: "payment.order_id -> order.id" }
applies_to:
  - resource: payment
  - resource: order
  - action: actions/process-payment
  - action: actions/delete-order
```

### Type 3: Aggregate Invariant

A sum or computed total across multiple records satisfies a rule.

```yaml
kind: invariant
metadata:
  name: money-consistency
  severity: critical
type: aggregate
rules:
  - name: order-total-is-sum-of-items
    rule: order.total_cents = sum(order_item.price_cents * order_item.quantity)
  - name: payment-equals-order
    rule: sum(payment.amount_cents where order_id = order.id) = order.total_cents
    condition: order.status in [completed, shipped, delivered]
  - name: balance-consistency
    rule: user.balance_cents = sum(transactions.amount_cents where user_id = user.id)
applies_to:
  - resource: order
  - resource: payment
  - resource: transaction
  - usecase: use-cases/purchase-product
```

### Type 4: State Machine Invariant

An entity transitions only between allowed states. Forbidden transitions are listed with reasons.

```yaml
kind: invariant
metadata:
  name: order-state-machine
  severity: critical
type: state-machine
entity: order
field: status
states: [pending, confirmed, shipped, delivered, cancelled, return_requested, returned]
transitions:
  pending:           [confirmed, cancelled]
  confirmed:         [shipped, cancelled]
  shipped:           [delivered, return_requested]
  delivered:         [return_requested]
  return_requested:  [returned, delivered]
forbidden:
  - { from: cancelled, to: any, reason: terminal state }
  - { from: returned, to: any, reason: terminal state }
  - { from: pending, to: shipped, reason: must confirm before shipping }
applies_to:
  - resource: order
  - action: actions/confirm-order
  - action: actions/ship-order
  - action: actions/cancel-order
```

### Type 5: Temporal Invariant

Event A always happens before event B, across use case boundaries:

```yaml
kind: invariant
metadata:
  name: payment-before-fulfillment
  severity: critical
type: temporal
rule: payment.completed_at < shipment.created_at
before: { event: payment-completed, field: payment.completed_at }
after:  { event: shipment-created, field: shipment.created_at }
join: shipment.order_id = payment.order_id
applies_to:
  - usecase: use-cases/purchase-product
  - usecase: use-cases/fulfill-order
```

### Type 6: Uniqueness Invariant

No two entities share the same value for a given field combination within a scope:

```yaml
kind: invariant
metadata:
  name: one-active-cart-per-user
  severity: medium
type: uniqueness
entity: cart
unique_fields: [user_id]
scope: "cart.status = active"
rule: count(cart where user_id = X and status = active) <= 1
applies_to:
  - resource: cart
  - action: actions/create-cart
  - action: actions/merge-carts
```

---

## Binding to Other Primitives

### Explicit Binding (`applies_to`)

Every invariant lists the resources and actions it guards in `applies_to`. Use cases bind invariants with `$ref`:

```yaml
kind: use_case
metadata:
  name: purchase-product
invariants:
  - $ref: invariants/stock-never-negative
  - $ref: invariants/money-consistency
```

### Automatic Binding (via writes analysis)

An action that writes to `product.stock` without being in `applies_to` is still detected. The framework scans every action's `writes` section and cross-references with invariant rules:

```
$ ucf graph invariant-bindings

Invariant: stock-never-negative (rule: product.stock >= 0)
  explicit:     ✓ actions/purchase-product, ✓ actions/restock-product
  auto-detected: ⚠ actions/bulk-import-products, ⚠ actions/admin-adjust-stock

Invariant: order-state-machine
  explicit:     ✓ actions/confirm-order, ✓ actions/ship-order
  auto-detected: ⚠ actions/admin-force-status

Summary: 2 invariants, 4 explicit, 3 auto-detected (unguarded)
```

Auto-detected unguarded bindings prevent invariant drift when new actions are added.

---

## Four Levels of Verification

### Level 1: Static (at spec time, no code)

State machine verification checks that every action produces only valid transitions. Temporal verification confirms `before` events always precede `after` events. No code required.

```
$ ucf validate invariants

Checking: order-state-machine
  actions/confirm-order:  pending → confirmed       ✓
  actions/ship-order:     confirmed → shipped        ✓
  actions/cancel-order:   pending → cancelled        ✓
                          confirmed → cancelled      ✓

Checking: payment-before-fulfillment
  use-cases/purchase-product
    step 3: process-payment → step 5: create-shipment  ✓ correct order

All invariants passed static verification.
```

### Level 2: Generated Tests (at CI)

Property-based tests using Hypothesis — random valid operations, invariant assertion after every step.

```python
from hypothesis import given, settings
from hypothesis import strategies as st

ACTIONS = [purchase_product, restock_product, cancel_order, bulk_import]

@given(
    actions=st.lists(st.sampled_from(ACTIONS), min_size=1, max_size=50),
    quantities=st.lists(st.integers(min_value=1, max_value=100), min_size=50),
)
@settings(max_examples=500)
def test_stock_never_negative(actions, quantities, test_context):
    ctx = test_context.setup(initial_stock=10)
    for action, qty in zip(actions, quantities):
        try:
            action(ctx, quantity=qty)
        except BusinessRuleViolation:
            pass
        for product in ctx.all_products():
            assert product.stock >= 0
```

For state machine invariants, the generator produces a Hypothesis `RuleBasedStateMachine` where each action is a `@rule()` and `@invariant()` methods assert constraints after every step:

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

VALID = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"delivered", "return_requested"},
    "delivered": {"return_requested"},
    "return_requested": {"returned", "delivered"},
}
TERMINAL = {"cancelled", "returned"}

class OrderStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.order, self.state = create_order(), "pending"

    @rule()
    def confirm(self): self._try("confirmed", confirm_order)
    @rule()
    def ship(self): self._try("shipped", ship_order)
    @rule()
    def cancel(self): self._try("cancelled", cancel_order)

    def _try(self, target, fn):
        if target in VALID.get(self.state, set()):
            fn(self.order); self.state = target
        else:
            with pytest.raises(InvalidTransitionError): fn(self.order)

    @invariant()
    def terminal_states_are_final(self):
        if self.state in TERMINAL: assert self.order.status == self.state
```

### Level 3: Runtime Assertions (in application)

The `@invariant_check` decorator wraps mutations in a transaction savepoint. After the function completes but before commit, it evaluates the invariant rule. On violation: rollback, `InvariantViolationError`, audit log entry.

```python
from ucf.runtime import invariant_check

@invariant_check("stock-never-negative")
async def purchase_product(order: Order, db: Database) -> None:
    for item in order.items:
        await db.execute(
            "UPDATE product SET stock = stock - :qty WHERE id = :id",
            {"qty": item.quantity, "id": item.product_id},
        )

@invariant_check("order-state-machine")
async def update_order_status(order_id: str, new_status: str, db: Database) -> None:
    await db.execute(
        "UPDATE orders SET status = :status WHERE id = :id",
        {"status": new_status, "id": order_id},
    )
```

For state machine invariants, the decorator validates `current → new_status` against the transitions table.

### Level 4: Production Monitoring

Periodic queries catch race conditions, manual edits, migration failures:

```yaml
runtime_monitoring:
  schedule: "*/5 * * * *"
  query: "SELECT id, name, stock FROM product WHERE stock < 0"
  expected: zero_rows
  on_violation:
    - { type: pagerduty, severity: critical, message: "stock-never-negative — {row_count} products" }
    - { type: slack, channel: "#ops-alerts", message: "Negative stock detected: {rows}" }
    - type: auto_fix
      action: "UPDATE product SET stock = 0 WHERE stock < 0"
      requires_approval: true
      approvers: [oncall-eng]
```

The framework generates cron jobs, alert integrations, and auto-fix scripts from this config.

---

## Invariant Composition

### Composite Invariants

Related invariants grouped under one name. Violated if **any** component is violated.

```yaml
kind: invariant
metadata:
  name: financial-integrity
  severity: critical
type: composite
composed_of:
  - $ref: invariants/money-consistency
  - $ref: invariants/payment-requires-order
  - $ref: invariants/refund-never-exceeds-original
  - $ref: invariants/balance-consistency
```

### Parameterized Invariants

Same pattern applied to multiple entities. Each instance expands into a standalone invariant at validation time.

```yaml
kind: invariant
metadata:
  name: quantity-never-negative
  severity: critical
type: data
parameters:
  entity: string
  field: string
rule: "{entity}.{field} >= 0"
instances:
  - name: stock-never-negative
    params: { entity: product, field: stock }
    applies_to: [{ resource: product }]
  - name: cart-quantity-positive
    params: { entity: cart_item, field: quantity }
    applies_to: [{ resource: cart_item }]
  - name: warehouse-count-valid
    params: { entity: warehouse_slot, field: count }
    applies_to: [{ resource: warehouse_slot }]
```

---

## Invariants + Conflict Detection

When the ConflictDetector (see [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md)) finds a write-write conflict, it cross-references the conflicted resource with invariants and reports whether protection is adequate:

```
$ ucf conflicts --with-invariants

purchase-product ⟷ restock-product | product.stock
  ✓ stock-never-negative (runtime + DB CHECK)       → ADEQUATE
create-cart ⟷ create-cart | cart per user
  ✓ one-active-cart-per-user (unique index)          → ADEQUATE
confirm-order ⟷ cancel-order | order.status
  ✓ order-state-machine (runtime check)              → PARTIAL
  Race between two valid transitions. Recommendation: add row-level locking.

Summary: 3 conflicts, 2 adequate, 1 needs attention
```

The detector identifies conflicts and evaluates protection — resolution is up to the developer.

---

## Summary

| Level | When | What it catches | Cost of miss |
|---|---|---|---|
| **Static** | Spec authoring | Invalid transitions, temporal ordering, missing bindings | Broken design shipped to dev |
| **Generated Tests** | CI pipeline | Logic errors, edge cases, property violations | Bug reaches production |
| **Runtime Assertions** | Every mutation | Constraint violations, invalid transitions | Corrupt data persisted |
| **Monitoring** | Periodic checks | Race conditions, manual edits, migration failures | Undetected corruption |

Each level is a safety net for the previous one.
