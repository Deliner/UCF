# UCF Framework: Known Limitations, Edge Cases & Mitigations

UCF provides structural guarantees that most codebases lack — but it is not
a silver bullet. This document catalogues the sharp edges we know about,
rates their severity, and describes the mitigations that exist today or are
planned.

---

## 1. Spec Rot (Documentation Decay)

**Severity: Critical**

### Problem

Developers change code, forget to update YAML specs.
Two sources of truth emerge and contradict each other.
The spec becomes a lie — worse than no spec at all, because people trust it.

### Mitigations

**A. Bi-directional drift detection**

CI runs two checks on every push:

| Direction | What it catches |
|-----------|----------------|
| Code → Spec | Endpoint exists in code but not in any spec |
| Spec → Code | Spec references a component that no longer exists |

If either direction detects drift, CI fails. There is no "warn" mode —
drift is a hard error.

**B. `@implements` decorator is mandatory**

Every public function, endpoint, or handler must carry an `@implements`
annotation linking it to a spec use-case. Pre-commit hooks block commits
that introduce unannotated code.

---

## 2. Double Work (Spec = Code Duplication)

**Severity: Medium**

### Problem

If a spec describes every parameter, type, and postcondition in full detail,
you are writing the same logic twice — once in YAML, once in Python.
Maintenance cost doubles and the two copies inevitably diverge (see §1).

### Mitigation

Strict editorial rule enforced by linter:

> **Spec describes WHAT, not HOW.**
> If you are describing an algorithm in YAML — you are doing it wrong.

A use-case spec should not exceed **40–60 lines** of YAML.
The `ucf lint` command warns when a single spec file crosses 80 lines and
errors above 120.

---

## 3. Greenfield Bias

**Severity: High**

### Problem

UCF works beautifully for new projects where specs come first.
99 % of real projects are legacy codebases with zero specs.
Requiring specs before any change would freeze development.

### Mitigations

**A. "No New Code Without Spec" rule**

Old code continues to work exactly as before.
Only *new* code (new endpoints, new use cases) requires a spec.
The boundary is enforced by git diff: if a file did not exist before this
branch, it needs a corresponding spec entry.

**B. `ucf scaffold` command**

Auto-generates skeleton specs from existing artifacts:

| Source | What it produces |
|--------|-----------------|
| OpenAPI / Swagger | Use-case stubs with actors, endpoints, parameters |
| Code AST | Component graph, protocol stubs |
| Running API | Recorded request/response pairs → postcondition drafts |

The generated specs are intentionally incomplete — they are a starting point,
not a finished product.

---

## 4. YAML Hell

**Severity: Medium**

### Problem

Deep nesting, `$ref` chains across files, expression syntax inside strings —
YAML becomes its own programming language, but without IDE support,
type checking, or debuggability.

### Mitigations

**A. JSON Schema for validation and autocomplete**

Every UCF primitive has a published JSON Schema. IDEs that support YAML +
JSON Schema (VS Code with Red Hat extension, JetBrains) get:
- Autocomplete for keys and enum values
- Inline validation errors
- Hover documentation

**B. LSP server**

A dedicated Language Server Protocol implementation provides:
- **Ctrl+Click** on `$ref` navigates to the referenced definition
- **Hover** on a component name shows what the component `provides`
- **Diagnostics** for broken references, type mismatches, unused components

**C. Max `$ref` depth limit**

The validator enforces a maximum `$ref` resolution depth of **3 levels**.
If a reference chain exceeds this, `ucf validate` fails with a clear error
pointing at the offending chain. This prevents the "maze of indirection"
problem.

---

## 5. Who Writes Specs?

**Severity: Critical**

### Problem

Product managers cannot write YAML.
Developers do not want to write YAML.
Nobody maintains specs — they become abandoned artifacts.

### Mitigation

Responsibility is split by abstraction level:

| Role | Writes | Format |
|------|--------|--------|
| Product / Analyst | Use Case description | Free text, user story |
| LLM | Conversion to YAML draft | `ucf draft --from-text "..."` |
| Developer | Actions, Components, Protocols | YAML (reviewed, committed) |
| System (static analysis) | Invariants, Conflicts | Auto-detected from reads/writes |

The key insight: nobody writes a spec from scratch.
The LLM draft gives developers a 70–80 % complete starting point.
Developers refine and commit it as regular code.

---

## 6. False Sense of Security

**Severity: High**

### Problem

"All specs pass" does not mean the system works.
Specs can be wrong, incomplete, or testing the wrong invariants.
Green CI becomes a comfort blanket that hides real bugs.

### Mitigations

**A. Smoke tests against real staging**

`ucf validate` checks structural correctness.
Smoke tests check *behavioral* correctness by hitting a real staging
environment with the happy-path scenario from each use case.

**B. Canary invariants**

Critical invariants are not only checked at spec time — they are compiled
into runtime assertions that run in production code.
Example: "account balance must never be negative" is checked on every
transaction, not just during `ucf validate`.

**C. Mandatory human review for spec changes**

Any PR that modifies a `.ucf.yaml` file requires approval from the
domain owner (CODEOWNERS rule). This prevents specs from silently weakening
their guarantees.

---

## 7. Static Analysis Limits for Conflicts

**Severity: Medium**

### Problem

Static analysis finds "both use cases write to `product.stock`" — but the
real conflict may be context-dependent.
Example: two use cases both decrement stock, but the conflict only manifests
when `stock == 1`. Static analysis cannot distinguish "always conflicts"
from "conflicts under specific conditions."

### Mitigations

**A. Static catches ~80 % (structural conflicts)**

Two use cases writing to the same field is a conflict *by default*.
The developer must explicitly mark it as safe with a `resolution:` block
explaining why. This is the right default — false positives are better than
false negatives for data integrity.

**B. Property-based tests catch the remaining ~20 %**

For context-dependent conflicts, `ucf generate` produces Hypothesis-based
property tests that run thousands of randomized scenarios.
These tests explore the state space that static analysis cannot reach:
concurrent execution order, boundary values, race conditions.

---

## 8. LLM Non-Determinism in Generation

**Severity: Low**

### Problem

If the LLM generates test code, each run produces slightly different output.
This breaks reproducibility: the same spec + same code should always produce
the same test suite. Non-deterministic generation also makes code review
meaningless — every regeneration is a full diff.

### Mitigation

LLM is used **only for initial generation**. The workflow is:

1. `ucf generate` calls LLM → produces test file
2. Developer reviews, adjusts, **commits** the file as regular code
3. On spec change, `ucf generate --patch` produces a **diff**, not a rewrite
4. Developer reviews the diff, applies selectively

Over time, as patterns stabilize, LLM generation is replaced by
deterministic **Jinja2 templates** that produce identical output for
identical input.

---

## 9. Edge Cases That Break the Framework

The basic 6 primitives (UseCase, Actor, Action, Component, Protocol,
Invariant) cannot express three classes of real-world systems.

### 9.1 Long-Running Processes

**Example**: Mortgage application, insurance claim, visa processing.

| Property | UCF assumption | Reality |
|----------|---------------|---------|
| Duration | Seconds to minutes | Weeks to years |
| Actors | Fixed for UC lifetime | Change mid-process (hand-offs) |
| Timeouts | Not modeled | Days, with escalation |
| Deployment | Single version | Process outlives multiple deployments |

**Impact**: Breaks temporal model, actor model, and versioning assumptions.

**Future fix**: `Session` primitive — a state machine with named phases,
actor switching between phases, timeout/escalation rules, and version
pinning per session instance.

### 9.2 Continuous Interactions

**Example**: Google Docs, collaborative whiteboard, multiplayer game state.

| Property | UCF assumption | Reality |
|----------|---------------|---------|
| Actors | 1–3 per UC | N concurrent actors |
| Operations | Discrete steps | Infinite stream |
| Postconditions | Checked after last step | State always changing |
| Consistency | Immediate | Eventually consistent |

**Impact**: Breaks step model, actor model, and postcondition model.

**Future fix**: `Stream` primitive — a channel with typed operations,
convergence model (last-write-wins, CRDT merge, OT transform), and
eventual-consistency guarantees instead of postconditions.

### 9.3 Cyclic Workflows

**Example**: Auction, negotiation, iterative approval.

| Property | UCF assumption | Reality |
|----------|---------------|---------|
| Flow | DAG (directed acyclic) | Cycles (bid → counter-bid → bid) |
| Iterations | Known at spec time | Unknown, data-dependent |
| Self-modification | Not possible | Events modify own triggers (anti-sniping) |
| Concurrency | 2–3 conflicting UCs | N instances of same UC competing |

**Impact**: Breaks DAG assumption. Conflict detector produces N² false
positives when N instances of the same UC run concurrently.

**Future fix**: `Loop` primitive — with `until` condition,
`max_iterations` safety bound, `concurrent_actors` count, and a conflict
resolution strategy for same-UC competition.

---

## 10. Performance Concerns

**Severity: Low (solvable)**

### Problem

Running `ucf validate` + `ucf conflicts` + `ucf generate` on every commit
adds non-trivial CI time. For a monorepo with 200+ specs, full validation
can take 30–60 seconds.

### Mitigation

Incremental validation: only check specs affected by the current changeset.

```
ucf validate --affected $(git diff --name-only HEAD~1)
```

The `--affected` flag resolves the dependency graph from changed files to
their spec owners, validates only those specs, and skips everything else.
Full validation runs nightly or on merge to main.

---

## 11. Verdict

The most dangerous problems in this list are **not technical** —
they are **human**:

1. **Spec Rot** (§1) — developers forget to update specs
2. **Who Writes Specs** (§5) — nobody wants to write them

Technical problems (YAML ergonomics, static analysis limits, LLM
non-determinism) are solved by engineering: better tooling, smarter
algorithms, deterministic templates.

Human problems are solved only by **automation and workflow integration**
so that *not writing a spec is harder than writing one*:

- Pre-commit blocks unannotated code → path of least resistance is to
  add the annotation
- `ucf scaffold` generates 80 % of the spec → developer only refines
- CI fails on drift → fixing the spec is the fastest way to unblock
  the pipeline
- LLM drafts from free text → product managers contribute without
  learning YAML

The framework succeeds not when it is technically perfect, but when the
cost of ignoring it exceeds the cost of using it.
