# UCF Framework Guide — The Source of Truth

**Version**: 1.0  
**Last Updated**: Feb 2026  
**Status**: Living Document

---

## Table of Contents

1. [Core Philosophy](#core-philosophy)
2. [The 6 (+1) Primitives](#the-6-1-primitives)
3. [When to Use What](#when-to-use-what)
4. [UCDD Workflow](#ucdd-workflow)
5. [Common Mistakes](#common-mistakes)
6. [Best Practices](#best-practices)
7. [Examples: Good vs Bad](#examples-good-vs-bad)

---

## Core Philosophy

### Use Case-Driven Development (UCDD)

**Central Principle**: Start with **user perspective**, not technical implementation.

```
❌ BAD:  "System needs to lookup URL, increment counter, redirect"
✅ GOOD: "Visitor wants to access original page via short link"
```

### Three Layers

```
┌─────────────────────────────────────────┐
│  USE CASE (Business/User Perspective)   │  ← What user wants to achieve
├─────────────────────────────────────────┤
│  ACTIONS (Domain Operations)            │  ← What system can do
├─────────────────────────────────────────┤
│  IMPLEMENTATION (Code)                  │  ← How it's done
└─────────────────────────────────────────┘
```

**Critical Rule**: Use cases must describe **actor goals**, not system internals.

---

## The 6 (+1) Primitives

### 1. **Action** — Atomic Domain Operation

**What**: Single, testable operation with clear inputs/outputs.

**Actor**: None (actions are actor-agnostic).

**Examples**:
- ✅ `validate-email` — checks email format
- ✅ `send-notification` — sends a message
- ✅ `calculate-total` — computes sum
- ❌ `lookup-then-increment` — TWO operations (split them!)

**Key Fields**:
```yaml
kind: action
metadata:
  name: validate-email
  version: 1.0.0
  owner: auth-team
input:
  email: string (required)
output:
  is_valid: boolean
  error_message: string
errors:
  - code: INVALID_FORMAT
    condition: email doesn't match regex
preconditions:
  - email is not empty
postconditions:
  - validation result is deterministic
```

**Rules**:
- Must be **stateless** (same input → same output)
- Must declare **all** errors that can occur
- Should complete in **< 5 seconds** (use async for long operations)

---

### 2. **UseCase** — Complete User Scenario

**What**: A goal-oriented scenario from **actor's perspective**.

**Actor**: REQUIRED (user, admin, system, visitor, etc.)

**Examples**:
- ✅ `register-new-user` (actor: new user)
- ✅ `approve-leave-request` (actor: manager)
- ✅ `visit-short-link` (actor: visitor)
- ❌ `lookup-and-redirect` (NO ACTOR! This is technical chain)

**Key Fields**:
```yaml
kind: usecase
metadata:
  name: register-new-user
  actor: new-user           # ← REQUIRED!
  
input_from_event:
  email: email
  password: password
  
steps:
  - id: validate-input
    use: actions/validate-email
  - id: check-exists
    use: actions/check-user-exists
  - id: create-account
    use: actions/create-user
    
postconditions:
  - user account is created
  - confirmation email is sent
  
alternative_flows:
  - name: email-already-exists
    trigger: email is already registered
    handles_error: USER_EXISTS
```

**Rules**:
- **ONE** actor per use case
- Steps describe **business logic flow**, not implementation details
- Postconditions must be **verifiable** from actor's perspective
- Use `terminal: true` if use case completes actor's goal

---

### 3. **Event** — External Trigger

**What**: Something that happens outside the system.

**Examples**:
- ✅ `user-clicked-button`
- ✅ `payment-received`
- ✅ `file-uploaded`
- ❌ `database-updated` (internal state change, not event!)

**Key Fields**:
```yaml
kind: event
metadata:
  name: payment-received
payload:
  order_id: string
  amount: number
  payment_method: string
source: payment-gateway
triggers:
  - use-cases/fulfill-order
```

**Rules**:
- Events are **immutable facts** (past tense)
- Events **trigger** use cases
- Don't create events for internal state changes

---

### 4. **Component** — Reusable Step Sequence

**What**: Encapsulated sequence of steps (like a function).

**Examples**:
- ✅ `email-sender` (SMTP connection, template rendering, sending)
- ✅ `database-connection` (connect, health check, pool mgmt)
- ❌ `user-registration-flow` (that's a use case!)

**Key Fields**:
```yaml
kind: component
metadata:
  name: email-sender
parameters:
  smtp_host: string
  port: integer
provides:
  is_connected: boolean
  send_count: integer
steps:
  - id: connect
    use: actions/smtp-connect
  - id: verify
    use: actions/smtp-verify
```

**Rules**:
- Use for **infrastructure concerns** (DB, cache, messaging)
- Use in `requires:` section of use cases
- Components have **state** (unlike actions)

---

### 5. **Protocol** — External System Contract

**What**: Interface to external service.

**Examples**:
- ✅ `stripe-payment-api`
- ✅ `twilio-sms-gateway`
- ✅ `aws-s3-storage`

**Key Fields**:
```yaml
kind: protocol
metadata:
  name: stripe-payment-api
endpoint: https://api.stripe.com/v1
authentication:
  type: bearer
  token: $env.STRIPE_SECRET_KEY
operations:
  create-payment-intent:
    method: POST
    path: /payment_intents
    input:
      amount: integer
      currency: string
```

**Rules**:
- One protocol per external service
- Document **all** rate limits
- Include retry/timeout strategies

---

### 6. **Invariant** — System-Wide Constraint

**What**: Rule that must **always** be true.

**Examples**:
- ✅ `user-email-is-unique`
- ✅ `balance-never-negative`
- ✅ `password-meets-complexity`

**Key Fields**:
```yaml
kind: invariant
metadata:
  name: user-email-is-unique
applies_to:
  - action: actions/create-user
  - action: actions/update-user-email
condition: "COUNT(users WHERE email = $input.email) <= 1"
severity: error
```

**Rules**:
- Checked **before and after** actions
- Use for **business rules** that span multiple actions
- Must be **testable**

---

### +1. **Spec** — Container for Primitives

**What**: YAML file containing one primitive.

**Rules**:
- One spec per file
- File path matches `kind`: `specs/actions/validate-email.yaml`
- Use `$ref` for references: `$ref: "actions/validate-email"`

---

## When to Use What

### Decision Tree

```
┌─ Does it describe what a USER/ACTOR wants to achieve?
│  YES → UseCase
│  NO ↓
│
├─ Is it a single, testable operation?
│  YES → Action
│  NO ↓
│
├─ Is it an external event?
│  YES → Event
│  NO ↓
│
├─ Is it infrastructure/reusable step sequence?
│  YES → Component
│  NO ↓
│
├─ Is it an external service contract?
│  YES → Protocol
│  NO ↓
│
└─ Is it a system-wide rule?
   YES → Invariant
```

### Common Patterns

| Pattern | Use Case | Action | Component |
|---------|----------|--------|-----------|
| "User wants to X" | ✅ | ❌ | ❌ |
| "System validates X" | ❌ | ✅ | ❌ |
| "System sends X" | ❌ | ✅ | ❌ |
| "DB connection pool" | ❌ | ❌ | ✅ |
| "SMTP sender" | ❌ | ❌ | ✅ |
| "Multi-step technical flow" | ❌ | split into actions | ✅ |

---

## UCDD Workflow

### The 6-Step Process

```
1. SPEC    → Write YAML (use case, actions, etc.)
2. VALIDATE → ucf validate specs
3. TRACE    → ucf trace specs (check data flow)
4. GENERATE → ucf generate specs --output tests/generated
5. IMPLEMENT → Write impl.py (business logic)
6. VERIFY   → pytest tests/generated/<name>/
```

### Critical Rules

**Rule 1**: **NEVER** write code before spec exists.

**Rule 2**: **ALWAYS** run `validate` and `trace` before `generate`.

**Rule 3**: **ONLY** edit `impl.py`, never touch generated files (interface, orchestrator).

**Rule 4**: If you need to change framework code, **use UCDD for that too**!

### Example: Adding Retry to Framework

❌ **WRONG** (what I did):
```python
# Directly edited pytest_plugin.py
def _build_step_args(...):
    args.append(f"{fname}={binding}")  # Hardcoded fix
```

✅ **CORRECT** (UCDD way):
```yaml
# specs/use-cases/generate-retry-logic.yaml
kind: usecase
actor: framework-developer
steps:
  - id: parse-retry-config
    use: actions/parse-retry-section
  - id: generate-loop
    use: actions/generate-python-for-loop
  - id: inject-backoff
    use: actions/add-sleep-statement
```

---

## Common Mistakes

### ❌ Mistake #1: Technical Chains as Use Cases

**Bad**:
```yaml
kind: usecase
name: redirect-to-original
steps:
  - id: lookup-url       # ← Technical detail!
  - id: increment-clicks # ← Technical detail!
  - id: redirect         # ← Technical detail!
```

**Good**:
```yaml
kind: usecase
name: visit-short-link
actor: visitor
steps:
  - id: redirect-visitor
    use: actions/redirect-to-original  # ← One action from user POV
postconditions:
  - visitor sees original page
```

**Why**: User doesn't care about lookup/increment — they just click and expect redirect.

---

### ❌ Mistake #2: Missing Actor

**Bad**:
```yaml
kind: usecase
name: process-payment
# ← No actor!
```

**Good**:
```yaml
kind: usecase
name: process-payment
actor: customer  # ← or 'payment-gateway' if system-initiated
```

**Why**: Every use case must answer "who wants this?"

---

### ❌ Mistake #3: Actions with Multiple Responsibilities

**Bad**:
```yaml
kind: action
name: validate-and-save-user
# ← TWO operations!
```

**Good**:
```yaml
# Action 1
kind: action
name: validate-user-input

# Action 2
kind: action
name: save-user
```

**Why**: Single Responsibility Principle — actions must be atomic.

---

### ❌ Mistake #4: Use Case Depends on Implementation Details

**Bad**:
```yaml
postconditions:
  - record is inserted into users table with ID > 0
```

**Good**:
```yaml
postconditions:
  - user account is created
  - user can log in with provided credentials
```

**Why**: Postconditions must be **business-verifiable**, not DB-verifiable.

---

### ❌ Mistake #5: Skipping Validation/Trace

**Bad**:
```bash
ucf generate specs  # ← No validation first!
```

**Good**:
```bash
ucf validate specs
ucf trace specs
ucf generate specs  # ← Only after validation passes
```

**Why**: Catch errors early (broken refs, data gaps, dead data).

---

## Best Practices

### 1. Naming Conventions

**Use Cases**: `<verb>-<noun>` from actor's POV
- ✅ `register-user`
- ✅ `approve-request`
- ✅ `visit-link`
- ❌ `user-registration-flow` (too generic)

**Actions**: `<verb>-<noun>` (atomic operation)
- ✅ `validate-email`
- ✅ `send-sms`
- ✅ `calculate-total`
- ❌ `validate-and-send` (two operations)

**Events**: `<noun>-<past-tense-verb>`
- ✅ `payment-received`
- ✅ `file-uploaded`
- ❌ `receive-payment` (should be past tense)

### 2. Keep Steps Coarse-Grained

**Bad** (too fine-grained):
```yaml
steps:
  - id: open-db
  - id: begin-transaction
  - id: insert-user
  - id: commit-transaction
  - id: close-db
```

**Good** (right granularity):
```yaml
steps:
  - id: save-user
    use: actions/save-user
    # ← Transaction handling is inside the action
```

**Rule**: Steps should be **business operations**, not DB/HTTP calls.

---

### 3. Use Alternative Flows for Errors

**Bad**:
```yaml
steps:
  - id: validate
  - id: handle-error  # ← Don't mix happy path with error handling
```

**Good**:
```yaml
steps:
  - id: validate
alternative_flows:
  - name: invalid-input
    handles_error: VALIDATION_ERROR
    steps:
      - id: return-error
```

---

### 4. Declare All Errors

**Bad**:
```yaml
kind: action
name: send-email
# ← No errors section, but SMTP can fail!
```

**Good**:
```yaml
kind: action
name: send-email
errors:
  - code: SMTP_CONNECTION_FAILED
    condition: cannot connect to SMTP server
  - code: INVALID_EMAIL
    condition: recipient email is malformed
```

---

### 5. One Actor Per Use Case

**Bad**:
```yaml
kind: usecase
name: order-processing
actor: customer, admin  # ← Multiple actors!
```

**Good**:
```yaml
# Use Case 1
kind: usecase
name: place-order
actor: customer

# Use Case 2
kind: usecase
name: review-order
actor: admin
```

---

## Examples: Good vs Bad

### Example 1: URL Shortener

#### ❌ BAD (Technical Perspective)

```yaml
kind: usecase
name: redirect-to-original
# NO ACTOR!
steps:
  - id: lookup-url          # Technical detail
    use: actions/db-query
  - id: increment-counter   # Technical detail
    use: actions/db-update
  - id: return-http-302     # Technical detail
```

**Problems**:
1. No actor
2. Steps describe implementation (DB query, HTTP 302)
3. User doesn't care about "lookup" or "increment"

---

#### ✅ GOOD (User Perspective)

```yaml
kind: usecase
name: visit-short-link
actor: visitor
trigger: visitor clicks shortened URL

steps:
  - id: redirect-to-destination
    use: actions/redirect-to-original
    input:
      short_code: $inputs.short_code
    output:
      destination_url: url

postconditions:
  - visitor is redirected to original page
  - visit is recorded for analytics

terminal: true
```

**Why Good**:
1. Clear actor (visitor)
2. One step from user POV ("redirect")
3. Postconditions are user-verifiable
4. Implementation details (lookup, increment) hidden in action

---

### Example 2: E-commerce Checkout

#### ❌ BAD

```yaml
kind: usecase
name: process-checkout
steps:
  - id: validate-cart
  - id: calculate-tax
  - id: calculate-shipping
  - id: calculate-total
  - id: charge-card
  - id: update-inventory
  - id: send-confirmation
  - id: create-shipment
```

**Problems**:
1. No actor
2. Too many fine-grained steps (tax, shipping calculations are technical)
3. Mixes business logic (checkout) with side effects (send email, create shipment)

---

#### ✅ GOOD

```yaml
kind: usecase
name: complete-purchase
actor: customer
trigger: customer clicks "Place Order"

steps:
  - id: finalize-order
    use: actions/finalize-order
    input:
      cart_id: $inputs.cart_id
      payment_method: $inputs.payment_method
    output:
      order_id: id
      total: amount

  - id: confirm-to-customer
    use: actions/send-order-confirmation
    input:
      order_id: $steps.finalize-order.order_id

postconditions:
  - order is placed
  - customer receives confirmation email
  - inventory is reserved

alternative_flows:
  - name: payment-failed
    handles_error: PAYMENT_DECLINED
    steps:
      - id: notify-failure
        use: actions/send-payment-failure-email

terminal: true
```

**Why Good**:
1. Clear actor (customer)
2. Steps are **business operations** (finalize, confirm)
3. Technical details (tax, shipping) hidden in `finalize-order` action
4. Alternative flows handle errors

---

### Example 3: User Registration

#### ❌ BAD

```yaml
kind: usecase
name: register-user
steps:
  - id: check-email-format
    use: actions/regex-validate
  - id: check-password-length
    use: actions/string-length
  - id: hash-password
    use: actions/bcrypt-hash
  - id: insert-db
    use: actions/db-insert
  - id: send-smtp-email
    use: actions/smtp-send
```

**Problems**:
1. Exposes implementation (regex, bcrypt, SMTP)
2. Too fine-grained (email format, password length should be one "validate" step)

---

#### ✅ GOOD

```yaml
kind: usecase
name: register-new-user
actor: visitor

input_from_event:
  email: email
  password: password

steps:
  - id: validate-credentials
    use: actions/validate-user-credentials
    input:
      email: $inputs.email
      password: $inputs.password

  - id: create-account
    use: actions/create-user-account
    depends_on: [validate-credentials]
    input:
      email: $inputs.email
      password: $inputs.password
    output:
      user_id: id

  - id: send-welcome
    use: actions/send-welcome-email
    depends_on: [create-account]
    input:
      user_id: $steps.create-account.user_id

postconditions:
  - user account exists
  - user can log in
  - welcome email is sent

alternative_flows:
  - name: email-exists
    handles_error: USER_ALREADY_EXISTS
    steps:
      - id: suggest-login
        use: actions/render-login-suggestion

terminal: true
```

**Why Good**:
1. Clear actor
2. Steps are **domain operations** (validate, create, send)
3. Implementation hidden (bcrypt, SMTP inside actions)
4. Verifiable postconditions

---

## Summary: Golden Rules

1. **User First**: Use cases describe **actor goals**, not system internals
2. **One Responsibility**: Actions must be **atomic** and **stateless**
3. **UCDD Always**: Spec → Validate → Trace → Generate → Implement → Verify
4. **Actor Required**: Every use case **must** have an actor
5. **Hide Implementation**: Steps should be **business operations**, not DB/HTTP calls
6. **Declare Errors**: Every action must list **all** possible errors
7. **Verify Early**: Run `validate` and `trace` **before** generating code
8. **Framework Changes**: If you change UCF code, **use UCDD for that too**

---

**Remember**: UCF is about **capturing business intent**, not documenting code structure.

If your use case reads like a technical sequence diagram, you're doing it wrong.

If your use case reads like a user story, you're doing it right.

---

**Next Steps**:
1. Read this guide when starting any new spec
2. Review existing specs against this guide
3. Update specs that violate these principles
4. Use this as reference when code-reviewing specs

**Questions?** Check `BOTTLE_NECKS.md` and `STRESS_TEST_REPORT.md` for real examples of what went wrong.
