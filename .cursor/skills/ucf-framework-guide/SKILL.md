# UCF Framework Guide Skill

## When to Use This Skill

Use this skill **EVERY TIME** you work with UCF Framework:

- ✅ Creating new specs (actions, use cases, events, etc.)
- ✅ Reviewing existing specs for correctness
- ✅ Implementing use cases
- ✅ Fixing framework bugs
- ✅ Answering questions about UCF philosophy
- ✅ Code reviewing UCF-related PRs

**DO NOT SKIP THIS SKILL** — it prevents critical conceptual errors like:
- Writing technical chains instead of user use cases
- Missing actors in use cases
- Creating multi-responsibility actions
- Exposing implementation details in specs

---

## How to Use

### Step 1: Read the Guide

First, **read the full guide** to understand UCF philosophy:

**Location**: `/Users/abalov-d/projects/ucf/UCF_FRAMEWORK_GUIDE.md`

Use the Read tool to load the guide before proceeding with any UCF work.

---

### Step 2: Apply the Checklist

Before creating or reviewing any spec, run through this checklist:

#### For Use Cases:
- [ ] Does it have an **actor**? (visitor, customer, admin, etc.)
- [ ] Does it describe **what the actor wants**, not system internals?
- [ ] Are steps **business operations**, not DB/HTTP calls?
- [ ] Are postconditions **verifiable from actor's perspective**?
- [ ] Does it avoid exposing implementation details?
- [ ] Does it have `terminal: true` if it completes actor's goal?

**Example Check**:
```yaml
# ❌ BAD - No actor, technical steps
kind: usecase
name: redirect-to-original
steps:
  - id: lookup-url
  - id: increment-clicks

# ✅ GOOD - Clear actor, business operation
kind: usecase
name: visit-short-link
actor: visitor
steps:
  - id: redirect-to-destination
```

---

#### For Actions:
- [ ] Is it **atomic** (one responsibility)?
- [ ] Is it **stateless** (same input → same output)?
- [ ] Does it declare **all possible errors**?
- [ ] Are preconditions/postconditions clear?
- [ ] Does it complete in < 5 seconds?

**Example Check**:
```yaml
# ❌ BAD - Multiple responsibilities
kind: action
name: validate-and-save-user

# ✅ GOOD - Single responsibility
kind: action
name: validate-user-credentials
```

---

#### For Events:
- [ ] Is it **past tense** (something that happened)?
- [ ] Is it from **external source** (not internal state change)?
- [ ] Does it have a clear **trigger** for use cases?

---

#### For Components:
- [ ] Is it **business entity** (NOT infrastructure!)?
- [ ] Does it have **business state** (total, count), not technical state (is_connected)?
- [ ] Is it **reusable** across multiple use cases?
- [ ] Can I hide this in action implementation instead? (prefer this!)

⚠️ **WARNING**: Component is controversial primitive. Avoid for infrastructure (SMTP, DB, cache).

---

### Step 3: Follow UCDD Workflow

**Always follow these 6 steps**:

```bash
# 1. SPEC - Write YAML
vim specs/use-cases/my-use-case.yaml

# 2. VALIDATE - Check syntax and references
ucf validate specs

# 3. TRACE - Check data flow
ucf trace specs

# 4. GENERATE - Create test files
ucf generate specs --output tests/generated

# 5. IMPLEMENT - Write business logic
vim tests/generated/my_use_case/impl.py

# 6. VERIFY - Run tests
pytest tests/generated/my_use_case/
```

**Critical**: Never skip steps 2-3! Running `generate` before `validate` will propagate errors.

---

### Step 4: Common Patterns Reference

#### Pattern 1: Creating a New Use Case

```yaml
kind: usecase
metadata:
  name: <verb>-<noun>
  actor: <who-wants-this>      # ← REQUIRED!
  tags: [domain, feature]

trigger: <what-initiates-this>

input_from_event:
  <field>: <field>

preconditions:
  - <what-must-be-true-before>

steps:
  - id: <business-operation>
    use: actions/<action-name>
    input:
      <field>: $inputs.<field>
    output:
      <field>: <field>

postconditions:
  - <what-actor-can-verify>

alternative_flows:
  - name: <error-scenario>
    handles_error: <ERROR_CODE>
    steps:
      - id: <recovery-step>

terminal: true
```

---

#### Pattern 2: Creating a New Action

```yaml
kind: action
metadata:
  name: <verb>-<noun>
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
  - code: <ERROR_CODE>
    status: 400 | 404 | 500
    condition: <when-this-happens>
    description: <human-readable>

preconditions:
  - <what-must-be-true>

postconditions:
  - <what-is-guaranteed>

reads:
  - resource: <resource-name>
    fields: [<field1>, <field2>]

writes:
  - resource: <resource-name>
    mutation: create | update | delete | increment
```

---

#### Pattern 3: Using $refs and Bindings

```yaml
# Reference other specs
steps:
  - id: validate
    use: actions/validate-email  # ← Reference by path

# Reference step outputs
  - id: send
    use: actions/send-email
    input:
      email: $steps.validate.email  # ← Binding to previous step

# Reference inputs
  - id: process
    input:
      data: $inputs.user_data  # ← Binding to use case input

# Reference component state
  - id: query
    input:
      connection: $requires.database.connection  # ← Component state

# Nested field access
  - id: redirect
    input:
      url: $steps.lookup.record.original_url  # ← Nested field
```

---

### Step 5: Red Flags (Stop and Review)

🚨 **STOP** if you see these patterns:

1. **Use case without actor**
   ```yaml
   kind: usecase
   name: process-order
   # ← WHERE IS ACTOR?
   ```

2. **Technical step names**
   ```yaml
   steps:
     - id: select-from-database  # ← Too low-level!
     - id: return-http-200       # ← Implementation detail!
   ```

3. **Action with multiple verbs**
   ```yaml
   kind: action
   name: validate-save-and-notify  # ← THREE operations!
   ```

4. **Postcondition mentioning DB/HTTP**
   ```yaml
   postconditions:
     - record inserted into users table  # ← Implementation leak!
   ```

5. **Steps without `use:`**
   ```yaml
   steps:
     - id: do-something
       # ← No 'use:' — what action does this call?
   ```

---

## Examples from Real Mistakes

### Mistake: URL Shortener (Bad Version)

**What I did wrong**:
```yaml
kind: usecase
name: redirect-to-original
# ❌ NO ACTOR
steps:
  - id: lookup-url          # ❌ Technical detail
  - id: increment-clicks    # ❌ Technical detail
  - id: redirect            # ❌ Technical detail
```

**Why it's wrong**:
1. No actor (who is redirecting?)
2. Steps describe **implementation** (lookup, increment), not **user goal**
3. User doesn't care about "increment clicks" — that's a side effect

**Correct version**:
```yaml
kind: usecase
name: visit-short-link
actor: visitor              # ✅ Clear actor
trigger: visitor clicks shortened URL

steps:
  - id: redirect-to-destination  # ✅ One business operation
    use: actions/redirect-to-original
    input:
      short_code: $inputs.short_code

postconditions:
  - visitor is redirected to original page  # ✅ User-verifiable
  - visit is recorded for analytics

terminal: true
```

**Key Insight**: Implementation details (lookup, increment) belong **inside** the `redirect-to-original` action, not as use case steps.

---

### Mistake: Framework Fixes Without UCDD

**What I did wrong**:
```python
# Directly edited pytest_plugin.py
def _resolve_binding(val: str) -> str:
    fields = ".".join(parts[2:])  # ← Hardcoded fix
```

**Why it's wrong**:
- Didn't follow UCDD workflow
- No spec for "resolve nested field binding"
- Can't verify correctness with generated tests

**Correct approach**:
1. Create spec: `specs/use-cases/resolve-nested-field-binding.yaml`
2. Define actions: `parse-binding`, `split-parts`, `join-fields`
3. Validate → Trace → Generate → Implement → Verify
4. **Then** the fix is testable and documented

---

## Quick Reference: Decision Tree

```
Start Here: What am I trying to model?

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
├─ Is it infrastructure (DB, cache, SMTP)?
│  YES → Component (has state, reusable)
│  NO ↓
│
├─ Is it an external service API?
│  YES → Protocol (rate limits, auth, retries)
│  NO ↓
│
└─ Is it a system-wide rule?
   YES → Invariant (always true)
```

---

## Instructions for AI Agent

When you see `/ucf` or work with UCF specs:

1. **IMMEDIATELY** read `/Users/abalov-d/projects/ucf/UCF_FRAMEWORK_GUIDE.md`
2. **VERIFY** spec against checklist (actor present? business operations? no implementation leaks?)
3. **FOLLOW** UCDD workflow (Spec → Validate → Trace → Generate → Implement → Verify)
4. **REFERENCE** common patterns above
5. **STOP** if you see red flags and ask user for clarification

**Never**:
- Create use case without actor
- Mix implementation details into use case steps
- Skip validation/trace steps
- Edit generated files (interface, orchestrator)
- Hardcode framework fixes without specs

**Always**:
- Think "user perspective" for use cases
- Keep actions atomic and stateless
- Declare all errors in actions
- Run `ucf validate` before `ucf generate`
- Use UCDD for framework changes too

---

## Testing Your Understanding

Before you start, answer these:

1. **Q**: Is `redirect-to-original` a good use case name?  
   **A**: No — it's technical. Should be `visit-short-link` with actor `visitor`.

2. **Q**: Can an action have internal state?  
   **A**: No — actions must be stateless (same input → same output).

3. **Q**: Where do I put "lookup URL from database" logic?  
   **A**: Inside the action's implementation, NOT as a use case step.

4. **Q**: Can I skip `ucf validate` and go straight to `generate`?  
   **A**: No — validation catches broken refs, type errors early.

5. **Q**: How do I fix a framework bug?  
   **A**: Create spec for the fix, use UCDD workflow, don't hardcode.

---

## Summary

**The Golden Rule**: UCF captures **business intent**, not code structure.

If your spec reads like a **sequence diagram** → you're doing it wrong.  
If your spec reads like a **user story** → you're doing it right.

**Remember**: This skill is your **source of truth**. Read it before every UCF task.

---

**Files to Reference**:
- **Main Guide**: `/Users/abalov-d/projects/ucf/UCF_FRAMEWORK_GUIDE.md`
- **Real Examples**: `/Users/abalov-d/projects/ucf/BOTTLE_NECKS.md`
- **Stress Test**: `/Users/abalov-d/projects/ucf/STRESS_TEST_REPORT.md`
