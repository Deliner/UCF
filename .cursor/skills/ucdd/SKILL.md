---
name: ucdd
description: Use Case-Driven Development workflow for the UCF framework. Enforces user-centric, specs-first development where YAML specs describe WHAT users want (not HOW system works), tests are generated from specs, then implementation fills in the stubs. Use when building features, fixing bugs, or when user says UCDD, use-case driven, or specs-first.
---

# Use Case-Driven Development (UCDD)

**Core Principle**: Start with **user perspective**, not technical implementation.

```
❌ BAD:  "System needs to lookup URL, increment counter, redirect"
✅ GOOD: "Visitor wants to access original page via short link"
```

Every feature in UCF follows this strict sequence: **Spec → Validate → Trace → Generate → Implement → Verify**. Never write implementation code before its spec exists.

---

## Golden Rules (Read First!)

Before starting ANY UCF work, internalize these 8 rules:

1. **User First**: Use cases describe **actor goals**, not system internals
2. **Actor Required**: Every use case **MUST** have an actor (user, admin, system, visitor)
3. **Actions Atomic**: One responsibility, stateless (same input → same output)
4. **Hide Implementation**: Steps = **business operations**, not DB/HTTP calls
5. **UCDD Always**: Even for framework changes — no hardcoding fixes!
6. **Declare Errors**: Every action must list **all** possible errors
7. **Verify Early**: Run `validate` and `trace` **before** `generate`
8. **No Edits**: Never touch generated files (`interface.py`, `test_orchestrator.py`)

---

## Critical Pre-Flight Checks

### ✅ The Golden Filter (Before Writing Specs):

Ask yourself for every line in the spec: **"Does the user/business care about this, or is this just how the backend works?"**

**If it's an infrastructure or backend concept, it DOES NOT belong in the YAML spec. It belongs in `impl.py`.**

1. **Who is the actor?** (If no human, is it `system`?)
2. **What does actor want to achieve?** (Not "how system works")
3. **Are steps business operations?** (Not "lookup DB", "send HTTP")
4. **Are postconditions user-verifiable?** (Not "record inserted into table")

### 🚨 Red Flags (STOP if you see these):

- **Infrastructure keywords in YAML**: `cache`, `redis`, `ttl`, `cron`, `schedule`, `transaction`, `rollback`, `idempotency_key`. (These belong in `impl.py` or infrastructure config, not business specs!)
- Use case without actor
- Step names like `select-from-database`, `return-http-200`
- Action with multiple verbs (`validate-save-and-notify`)
- Postcondition mentions DB/HTTP (`record inserted into users table`)
- Component for infrastructure (`email-sender`, `database-connection`)

If you see a red flag → **Move technical details to `impl.py` or Read UCF_FRAMEWORK_GUIDE.md** → Fix → Continue

---

## The 6 (+1) Primitives

### 1. Action — Atomic Domain Operation

**What**: Single, testable operation. NO actor (actions are actor-agnostic).

**Examples**:
- ✅ `validate-email` — checks email format
- ✅ `send-notification` — sends message
- ❌ `validate-and-save` — TWO operations!
- ❌ `lookup-then-increment` — TWO operations!

**Rules**:
- **Stateless**: same input → same output
- **Atomic**: one responsibility
- **< 5 seconds** execution

---

### 2. UseCase — Complete User Scenario

**What**: Goal-oriented scenario from **actor's perspective**.

**REQUIRED**: `actor` field (user, admin, system, visitor, etc.)

**Examples**:
- ✅ `visit-short-link` (actor: visitor)
- ✅ `register-new-user` (actor: new user)
- ❌ `lookup-and-redirect` — NO ACTOR!
- ❌ `redirect-to-original` — Technical name!

**Rules**:
- ONE actor per use case
- Steps describe **business logic**, not implementation
- Postconditions **user-verifiable**
- Use `terminal: true` if completes actor's goal

---

### 3. Component — Stateful Business Entity

⚠️ **DESIGN WARNING**: Component is controversial. Use sparingly.

**What**: Stateful **business entity** shared across use cases.

**Critical Rule**: Component must be **business concept**, NOT infrastructure!

**Examples**:
- ✅ `shopping-cart` (business: total, items)
- ✅ `payment-processor` (business: transaction_id, amount)
- ❌ `email-sender` — Infrastructure! Hide in action!
- ❌ `database-connection` — Infrastructure! Implicit in actions!
- ❌ `cache-manager` — Infrastructure! Implementation detail!

**Guideline**: Avoid Component for infrastructure. Hide it in action implementations.

---

### 4. Event — External Trigger

**What**: Something that happens **outside** the system.

**Examples**:
- ✅ `payment-received` (past tense)
- ✅ `file-uploaded` (past tense)
- ❌ `database-updated` — Internal state change!

---

### 5. Protocol — External System Contract

**What**: Interface to external service (Stripe, Twilio, AWS S3).

---

### 6. Invariant — System-Wide Constraint

**What**: Rule that must **always** be true.

**Examples**:
- ✅ `user-email-is-unique`
- ✅ `balance-never-negative`

---

## UCDD Workflow

### Phase 1: Write Specs (User Perspective!)

Create YAML specs in `specs/` before touching any Python code.

#### 1. Action Specs (`specs/actions/{name}.yaml`)

**Template**:
```yaml
kind: action
metadata:
  name: <verb>-<noun>         # e.g., validate-email
  version: 1.0.0
  owner: <team>
  tags: [domain]
  
input:
  <field>:
    type: string | integer | boolean | array | object
    required: true | false
    description: <what-this-is>
    
output:
  <field>:
    type: <type>
    description: <what-this-returns>
    
errors:
  - code: <ERROR_CODE>        # REQUIRED! Declare ALL errors
    status: 400 | 404 | 500
    condition: <when-happens>
    description: <human-readable>
    
reads:
  - resource: <resource-name>
    fields: [<field1>, <field2>]
    
writes:
  - resource: <resource-name>
    mutation: create | set | increment | decrement | append | delete
    
preconditions:
  - <what-must-be-true>
  
postconditions:
  - <what-is-guaranteed>
```

**Rules**:
- Define `input`, `output`, `errors` (ALL of them!)
- `reads`/`writes` for resource access
- `preconditions`/`postconditions` for contracts
- Each action = one atomic operation

---

#### 2. Use Case Specs (`specs/use-cases/{name}.yaml`)

**Template**:
```yaml
kind: usecase
metadata:
  name: <verb>-<noun>         # e.g., visit-short-link
  actor: <who-wants-this>     # ← REQUIRED!
  version: 1.0.0
  owner: <team>
  tags: [domain, feature]
  
trigger: <what-initiates-this>

input_from_event:
  <field>: <field>
  
preconditions:
  - <what-must-be-true-before>
  
assumed_preconditions:        # For state coverage analysis
  - <what-we-assume>
  
steps:
  - id: <business-operation>  # NOT "query-db" or "send-http"!
    use: actions/<action-name>
    input:
      <field>: $inputs.<field>           # From use case input
      <field>: $steps.<step-id>.<field>  # From previous step
      <field>: literal-value             # Literal
    output:
      <field>: <field>
      
postconditions:
  - <what-actor-can-verify>   # User-verifiable, NOT "DB updated"!
  
alternative_flows:
  - name: <error-scenario>
    trigger: <what-goes-wrong>
    handles_error: <ERROR_CODE>
    steps:
      - id: <recovery-step>
        
terminal: true                # If completes actor's goal

invariants:
  - $ref: invariants/<invariant-name>
```

**Rules**:
- **MUST** have `actor`
- Steps = **business operations** (hide DB/HTTP in actions)
- Postconditions = **user-verifiable** (not "record inserted")
- Alternative flows handle errors via `handles_error`

---

#### 3. Component Specs (⚠️ Use Sparingly)

**ONLY for business entities**, NOT infrastructure!

```yaml
kind: component
metadata:
  name: shopping-cart          # Business concept!
  
parameters:
  user_id: string
  
provides:
  total: number                # Business state
  item_count: integer          # Business state
  
steps:
  - id: calculate-total
    use: actions/sum-item-prices
```

**Avoid** Component for:
- SMTP senders
- Database connections
- Cache managers
- HTTP clients

→ Hide infrastructure in action implementations instead!

---

### Phase 2: Validate & Trace

**CRITICAL**: Run these BEFORE `generate`. Fix ALL errors.

```bash
# Step 1: Validate syntax and references
ucf validate specs/

# Expected: "Summary: 0 errors"
# Fix: Broken $ref, missing fields, invalid enums

# Step 2: Trace data flow
ucf trace specs/

# Expected: No "error" findings (info/warning OK for final outputs)
# Fix: Data gaps, broken bindings, type mismatches
```

**Common Issues**:

| Issue | Error | Fix |
|-------|-------|-----|
| Broken reference | `$ref not found` | Create missing spec file |
| Data gap | `Step reads 'field' but it doesn't exist` | Add output to previous step |
| Dead data | `Step produces 'field' but nothing reads it` | Add consumer or remove output |
| Type mismatch | `Binding type mismatch` | Fix binding path |

**Example Iteration** (from real Bottle Neck #4 fix):
```
Attempt 1: ucf validate → mutation: update (invalid) → Fixed: mutation: set
Attempt 2: ucf trace → reads 'trigger_action' (doesn't exist) → Fixed: output mapping
Attempt 3: ucf trace → binding mismatch → Fixed: $steps...action_ref
✅ Clean!
```

---

### Phase 3: Generate Test Skeletons

```bash
ucf generate specs/ --output tests/generated
```

**Generates 3 files per use case** in `tests/generated/{snake_name}/`:

| File | Regenerated? | Contents |
|------|-------------|----------|
| `interface.py` | ✅ Always | Abstract class with methods + dataclasses |
| `test_orchestrator.py` | ✅ Always | Pytest test calling methods in order |
| `impl.py` | ❌ Never | Concrete class with stubs (you edit this!) |

**Method Mapping**:

| Spec Section | Method Prefix | Example |
|--------------|---------------|---------|
| `requires` | `setup_*` | `setup_registry()` |
| `steps` | `action_*` | `action_validate_email()` |
| `postconditions` | `verify_*` | `verify_user_can_login()` |
| `invariants` | `verify_*` | `verify_required_inputs_validated()` |

---

### Phase 4: Implement

**ONLY edit `impl.py`** — this is your implementation file.

```python
"""Implementation for use case: visit-short-link.

@implements("use-cases/visit-short-link")
"""

from __future__ import annotations
from typing import Any
import pytest

from .interface import VisitShortLinkInterface, RedirectResult


class VisitShortLinkImpl(VisitShortLinkInterface):
    def __init__(self) -> None:
        self.url_service = URLShortener()
        self._destination_url = None
    
    # ── Actions ──
    
    def action_redirect_to_destination(self, short_code: Any) -> RedirectResult:
        """One action hides: lookup + increment + redirect."""
        url_record = self.url_service.get_by_code(short_code)
        self.url_service.increment_clicks(short_code)
        self._destination_url = url_record.original_url
        
        return RedirectResult(
            destination_url=url_record.original_url,
            redirected=True
        )
    
    # ── Verifications ──
    
    def verify_visitor_is_redirected_to_original_page(self) -> None:
        assert self._destination_url is not None, "No redirect occurred"
        assert self._destination_url.startswith("http"), "Invalid URL"
    
    def verify_visit_is_recorded_for_analytics(self) -> None:
        # Check click counter was incremented
        assert self.url_service.get_clicks("test123") > 0
    
    def verify_required_inputs_validated(self) -> None:
        from pydantic import ValidationError
        from ucf.models.action import ActionSpec
        
        with pytest.raises(ValidationError):
            ActionSpec.model_validate({})


@pytest.fixture
def visit_short_link_impl() -> VisitShortLinkImpl:
    return VisitShortLinkImpl()
```

**Key Points**:
1. **Store state** on `self` for verify methods
2. **Call real code** in action methods (not mocks!)
3. **Meaningful assertions** in verify methods (not just `isinstance`)
4. **Fixture** at bottom returns impl instance

---

### Phase 5: Verify

```bash
# Run new use case tests
pytest tests/generated/{snake_name}/ -v --tb=short

# Run full suite (catch regressions)
pytest tests/ -v

# Check drift (should show new specs mapped)
ucf drift specs/ --source src/
```

**After tests pass**, add `@implements` markers:

```python
"""URL Shortener service.

@implements("actions/redirect-short-link")
@implements("use-cases/visit-short-link")
"""
```

---

### Phase 6: Iterate

**If tests fail**:
- Fix `impl.py` (your implementation)
- Fix source module (actual business logic)
- ❌ **NEVER** edit `interface.py` or `test_orchestrator.py`

**If generator has bugs**:
- Fix `src/ucf/generator/pytest_plugin.py`
- Re-run `ucf generate`
- But **use UCDD for generator fixes too!** (see Bottle Neck #4 example)

---

## Common Mistakes (Anti-Patterns)

### ❌ Mistake #1: Technical Chains as Use Cases

**Bad**:
```yaml
kind: usecase
name: redirect-to-original   # Technical name!
# NO ACTOR!
steps:
  - id: lookup-url            # DB query
  - id: increment-clicks      # Counter update
  - id: redirect              # HTTP 302
```

**Why wrong**: User doesn't care about "lookup" or "increment".

**Good**:
```yaml
kind: usecase
name: visit-short-link        # User action!
actor: visitor                # Clear actor!
steps:
  - id: redirect-to-destination  # One business operation
    use: actions/redirect-short-link
```

**Fix**: Hide technical details (lookup, increment) inside `redirect-short-link` action.

---

### ❌ Mistake #2: Missing Actor

**Bad**:
```yaml
kind: usecase
name: process-payment
# WHERE IS ACTOR?
```

**Good**:
```yaml
kind: usecase
name: process-payment
actor: customer              # Or 'system' for automated
```

---

### ❌ Mistake #3: Multi-Responsibility Actions

**Bad**:
```yaml
kind: action
name: validate-and-save-user  # TWO operations!
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

---

### ❌ Mistake #4: Implementation in Postconditions

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

---

### ❌ Mistake #5: Skipping Validation/Trace

**Bad**:
```bash
ucf generate specs  # ❌ No validation first!
```

**Good**:
```bash
ucf validate specs  # ✅ Fix errors
ucf trace specs     # ✅ Fix data flow
ucf generate specs  # ✅ Only after clean
```

---

## Spec Authoring Reference

### Step Input Bindings

```yaml
input:
  registry: $loader.registry               # Component field
  graph: $steps.build-graph.graph          # Previous step output
  target: $inputs.target                   # External input
  url: $steps.lookup.record.original_url   # Nested field access!
  data:                                    # Nested dict
    count: $steps.detect.count
    items: $steps.detect.items
  format: table                            # Literal value
```

### Step Output Bindings

```yaml
output:
  graph: graph              # action output field → context name
  node_count: node_count    # maps 1:1 to action spec's output
```

### Alternative Flows

```yaml
alternative_flows:
  - name: link-not-found
    trigger: short code doesn't exist
    handles_error: LINK_NOT_FOUND     # ← Links to action's error
    steps:
      - id: show-404
        use: actions/render-404-page
```

---

## Decision Tree: When to Use What?

```
Start: What am I trying to model?

┌─ Does it describe what a USER/ACTOR wants?
│  YES → UseCase (must have actor!)
│  NO ↓
│
├─ Is it a single operation the system can perform?
│  YES → Action (must be atomic, stateless)
│  NO ↓
│
├─ Did something happen outside the system?
│  YES → Event (past tense, immutable)
│  NO ↓
│
├─ Is it a BUSINESS entity (shopping cart, document)?
│  YES → Component (NOT infrastructure!)
│  NO ↓
│
├─ Is it an external service API?
│  YES → Protocol
│  NO ↓
│
└─ Is it a system-wide rule?
   YES → Invariant
```

---

## Real Example: URL Shortener

### Before (❌ Wrong):

```yaml
name: redirect-to-original
# NO ACTOR
steps:
  - lookup-url          # Technical
  - increment-clicks    # Technical
  - redirect            # Technical
```

### After (✅ Correct):

```yaml
name: visit-short-link
actor: visitor          # ✅
trigger: visitor clicks shortened URL

steps:
  - id: redirect-to-destination    # ✅ Business operation
    use: actions/redirect-short-link

postconditions:
  - visitor is redirected to original page    # ✅ User-verifiable
  - visit is recorded for analytics
```

**Implementation** (action hides technical details):

```python
# actions/redirect-short-link implementation
def redirect_short_link(short_code):
    url_record = db.lookup(short_code)      # Hidden from spec
    db.increment_clicks(short_code)         # Hidden from spec
    http.redirect_302(url_record.url)       # Hidden from spec
```

---

## Checklist

Before marking a feature complete:

### Specs:
- [ ] Use case has **actor** field
- [ ] Steps are **business operations** (not DB/HTTP calls)
- [ ] Postconditions are **user-verifiable**
- [ ] All actions have **all errors declared**
- [ ] Component used **only for business entities** (not infrastructure)

### Validation:
- [ ] `ucf validate specs/` reports **0 errors**
- [ ] `ucf trace specs/` reports **0 data gaps**
- [ ] No red flags (missing actor, technical step names)

### Implementation:
- [ ] `ucf generate` ran successfully
- [ ] `impl.py` filled with **real assertions** (not just `isinstance`)
- [ ] All tests pass (`pytest tests/`)
- [ ] `@implements` markers added to source files

### Verification:
- [ ] `ucf drift specs/ --source src/` shows new specs **mapped**
- [ ] No regressions in existing tests

---

## Meta-Improvement: Fix Framework with UCDD

**Critical**: When fixing UCF bugs, **use UCDD for the fix itself!**

**Example** (Bottle Neck #4 - Alt triggers not verified):

1. ✅ Created use case: `generate-alt-flow-verification`
2. ✅ Created actions: `extract-error-code`, `find-trigger-action`, `generate-assertion`
3. ✅ Validated & traced specs
4. ✅ Generated tests
5. ✅ Implemented assertion generation logic
6. ✅ Tests pass

**Wrong approach**: Directly edit `pytest_plugin.py` (hardcode fix).

**Right approach**: Spec describes fix → Generator uses spec → Framework improves itself!

---

## Resources

- **Full Guide**: `/Users/abalov-d/projects/ucf/UCF_FRAMEWORK_GUIDE.md`
- **Examples**: `/Users/abalov-d/projects/ucf/BOTTLE_NECKS.md`
- **Stress Test**: `/Users/abalov-d/projects/ucf/STRESS_TEST_REPORT.md`

---

## Summary

**The Golden Rule**: UCF captures **business intent**, not code structure.

If your spec reads like a **sequence diagram** → you're doing it wrong.  
If your spec reads like a **user story** → you're doing it right.

**Remember**:
1. User perspective first
2. Actor always required
3. Actions atomic and stateless
4. Hide implementation in actions
5. Validate/Trace before Generate
6. Use UCDD for framework fixes too

**Before ANY work**: Read UCF_FRAMEWORK_GUIDE.md → Apply principles → Follow workflow.
