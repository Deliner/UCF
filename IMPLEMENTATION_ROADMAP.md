# UCF Implementation Roadmap

> **Status: Superseded proposal.** Capability and release claims in this
> document are not current; [the capability matrix](docs/CAPABILITIES.md)
> controls the current status.

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Pattern matching, modern typing, target ecosystem |
| YAML Parsing | Pydantic + PyYAML | Validation through types, rich error messages |
| Graph | networkx | DAG construction, topological sort, impact analysis |
| Templates | Jinja2 | Mature, extensible code generation |
| CLI | typer | Modern CLI with auto-generated help and completion |
| Validation | JSON Schema | IDE autocomplete and inline validation for YAML specs |
| Packaging | `pip install usecase-gen` | Standard distribution via PyPI |

---

## Implementation Phases

### Phase 1: Schema + Parser + Validator (1–2 weeks)

**Goal:** Parse and validate UCF specs with precise error reporting.

- Define Pydantic models for all 6 primitives (Entity, UseCase, Step, Rule, Error, DataContract)
- YAML parser with structural and semantic validation
- `$ref` resolver supporting cross-file references (`$ref: "../entities/user.yaml"`)
- Detect broken refs, missing required fields, type mismatches
- CLI: `ucf validate specs/`

**Immediate value:** catches broken references, incomplete specs, and schema
violations before any code is written. Works on day one with existing YAML files.

---

### Phase 2: Dependency Graph (1–2 weeks)

**Goal:** Build a queryable DAG from parsed specs for impact and coverage analysis.

- Construct a directed acyclic graph from parsed specs using networkx
- Impact analysis: "what use cases, rules, and contracts depend on Entity X?"
- Coverage analysis: "which specs have no corresponding implementation?"
- Cycle detection with clear error reporting (A → B → C → A)
- Orphan detection: specs that nothing references
- CLI commands:
  - `ucf graph impact Entity.User` — show downstream dependents
  - `ucf graph coverage` — report unimplemented specs
  - `ucf graph conflicts` — detect cycles and orphans

**Immediate value:** answer "what breaks if I change X?" before touching code.

---

### Phase 3: Expression Resolver (1 week)

**Goal:** Parse and type-check `$` expressions that wire steps together.

- Parse `$steps.validate_input.output`, `$auth.user_id`, `$context.tenant`
- Resolve expressions against the dependency graph
- Type checking between producer output and consumer input
- Build the resolution infrastructure used by Context Tracer and generators

**Immediate value:** catches wiring errors ("step 3 references step 2's output,
but step 2 produces a different type") at spec validation time.

---

### Phase 4: Context Tracer (2 weeks)

**Goal:** Virtually execute use cases to detect logic errors without running code.

- `ContextSlot` and `ContextSnapshot` data structures for tracking data flow
- `ContextTracer` virtual machine that walks through steps symbolically
- Detection categories:
  - **Data gaps:** step consumes data that no prior step produces
  - **Dead data:** step produces data that no subsequent step consumes
  - **Branch divergence:** conditional branches leave context in incompatible states
  - **State violations:** entity transitions that break declared state machines
- Cross-use-case analysis: shared entity state consistency
- CLI: `ucf verify specs/`

**Immediate value:** catches logic errors — missing data, impossible transitions,
unreachable branches — without writing or running any code.

---

### Phase 5: First Generator — pytest + httpx (2–3 weeks)

**Goal:** Generate executable test skeletons from validated specs.

- Define `GeneratorPlugin` protocol for pluggable code generation backends
- Jinja2 template system for interface and orchestrator generation
- First plugin: `pytest-http`
  - Generates pytest test files with httpx calls
  - Fixtures from DataContracts
  - Assertions from Rules and expected Errors
  - Parametrized tests from spec variants
- CLI: `ucf generate --target pytest-http --output tests/generated/`

**Immediate value:** validated specs produce runnable test skeletons. Developers
fill in setup/teardown details; the structure and assertions come from specs.

---

### Phase 6: Spec↔Code Mapping (2 weeks)

**Goal:** Bidirectional traceability between specs and implementation code.

- **Convention-based matching:** file path patterns map specs to code
  (`specs/use_cases/create_order.yaml` → `src/handlers/create_order.py`)
- **Decorator scanning:** find `@implements("UC-CreateOrder")` annotations
  in Python source using ripgrep-based AST-light scanning
- **Explicit mapping:** `implemented_by: src/handlers/create_order.py` in specs
- Detection modes:
  - **Spec→Code drift:** spec changed but implementation unchanged
  - **Code→Spec drift:** implementation changed but spec not updated
  - **Orphan files:** code files with no corresponding spec
  - **Orphan specs:** specs with no corresponding implementation
- CLI: `ucf drift --detect`

**Immediate value:** finds undocumented code, stale specs, and implementation
gaps across the entire codebase.

---

### Phase 7: CI/CD + Hooks Integration (1 week)

**Goal:** Embed UCF validation into the development workflow.

- GitHub Actions workflow templates (`ucf-ci.yaml`)
- Cursor hooks integration for in-editor feedback
- Git pre-commit hooks via pre-commit framework
- Unified validation command: `ucf check` (runs validate + verify + drift)
- Configurable strictness levels (warn vs. block)

**Immediate value:** automated guardrails — specs stay in sync with code on
every commit and pull request.

---

## Total Timeline

| Phase | Deliverable | Duration | Cumulative | Immediate Value |
|-------|------------|----------|------------|-----------------|
| 1 | Schema + Parser + Validator | 1–2 weeks | 2 weeks | Catches broken refs and incomplete specs |
| 2 | Dependency Graph | 1–2 weeks | 4 weeks | Impact analysis before changes |
| 3 | Expression Resolver | 1 week | 5 weeks | Type-checked data wiring |
| 4 | Context Tracer | 2 weeks | 7 weeks | Logic error detection without code |
| 5 | Generator (pytest-http) | 2–3 weeks | 10 weeks | Auto-generated test skeletons |
| 6 | Spec↔Code Mapping | 2 weeks | 12 weeks | Drift and orphan detection |
| 7 | CI/CD + Hooks | 1 week | 13 weeks | Automated workflow guardrails |

**MVP (Phases 1–5): ~8–10 weeks for one developer.**
After Phase 5, the system is fully functional: specs are parsed, validated,
traced for logic errors, and used to generate executable tests.

---

## Adoption Strategy

### Phase 0: Brownfield Entry (Week 1)

Lower the barrier to entry by generating skeleton specs from existing assets.

- `ucf scaffold --from-openapi swagger.json` — generate Entity and DataContract
  specs from an OpenAPI definition
- `ucf scaffold --from-code src/handlers/` — infer UseCase skeletons from
  existing handler functions (routes, parameters, return types)
- Auto-generated specs are intentionally incomplete — they serve as a starting
  point, not a finished product

### Phase 1: New Code Only (Month 1–2)

Adopt incrementally without disrupting existing workflows.

- All new features go through spec-first development. Existing code is untouched.
- Pre-commit hook issues **warnings** (not blocks) for code without `@implements`
- Team builds familiarity with the spec language on low-risk new work

### Phase 2: Critical Paths (Month 3–4)

Expand coverage to high-value areas.

- Cover critical use cases (payments, authentication, authorization) with specs
- Enable invariant runtime checks on staging environments
- Run Context Tracer on critical paths to validate logic completeness

### Phase 3: Full Coverage (Month 5+)

Shift from optional to mandatory.

- Pre-commit switches from warnings to **blocks** for unspecified code
- Drift detection is mandatory in CI — PRs with spec↔code drift are rejected
- Coverage threshold enforced: **80%+** of use cases must have specs
- Orphan detection prevents accumulation of undocumented code

---

## Future Roadmap (Post-MVP)

### Additional Generator Plugins

- `jest` — TypeScript/JavaScript test generation
- `playwright` — End-to-end browser test generation
- `go-test` — Go test generation for backend services

### Developer Tooling

- **LSP server** for YAML specs: autocomplete, go-to-definition, inline
  validation, hover documentation
- **VS Code / Cursor extension** with dependency graph visualization,
  inline spec coverage indicators, and one-click navigation between
  specs and implementation

### Advanced Primitives

| Primitive | Purpose | Example |
|-----------|---------|---------|
| **Session** | Long-running, multi-actor processes | Onboarding wizard spanning multiple days |
| **Stream** | Continuous interactions | Collaborative document editing |
| **Loop** | Cyclic workflows with termination conditions | Auction bidding rounds |

These primitives extend the spec language for patterns that don't fit the
linear request-response model of the current UseCase primitive.

---

## Metrics of Success

### Efficiency

- **Time from spec to working tests:** target < 30 minutes for a standard
  use case (spec writing + generation + filling in details)
- **Spec writing overhead:** should not exceed 15–20% of total feature
  development time

### Quality

- **Bugs caught at spec level vs. production:** track the ratio over time.
  Target: 40%+ of logic bugs caught before implementation begins.
- **Drift incidents:** number of times spec↔code mapping catches a
  desynchronization before it reaches production

### Coverage

- **Spec coverage percentage:** tracked weekly, targeting 80%+ by month 5
- **Generator adoption:** percentage of specs that have at least one
  generated test target

### Developer Experience

- **Developer satisfaction:** quarterly survey — does UCF help or hinder?
- **Onboarding time:** how long until a new developer writes their first spec?
- **Abandonment rate:** how often do developers skip specs for "quick fixes"?
  (should trend toward zero as tooling matures)
