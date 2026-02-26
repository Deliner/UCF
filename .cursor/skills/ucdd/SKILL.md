---
name: ucdd
description: Use Case-Driven Development workflow for the UCF framework. Enforces specs-first development where YAML specs are written before code, tests are generated from specs, then implementation fills in the stubs. Use when building new features, adding capabilities, fixing generator issues, or when the user says UCDD, use-case driven, or specs-first.
---

# Use Case-Driven Development (UCDD)

Every feature in UCF follows this strict sequence: **Spec → Validate → Trace → Generate → Implement → Verify**. Never write implementation code before its spec exists.

## Workflow

### Phase 1: Write Specs

Create YAML specs in `specs/` before touching any Python code.

**Required for every feature:**

1. **Action specs** (`specs/actions/{name}.yaml`) — one per atomic operation
   - Define `input`, `output`, `reads`, `writes`, `preconditions`, `postconditions`
   - Each action maps to exactly one function/class in the codebase

2. **Use case spec** (`specs/use-cases/{name}.yaml`) — the user-facing scenario
   - Wire actions together via `steps` with `$` expression bindings
   - Add `requires` for component dependencies
   - Add `postconditions` (these become `verify_*` test methods)
   - Add `invariants` referencing business rules
   - Add `alternative_flows` for non-happy-path scenarios

**Add when needed:**

3. **Component specs** (`specs/components/{name}.yaml`) — reusable setup blocks
4. **Invariant specs** (`specs/invariants/{name}.yaml`) — business rules that must never break

**Naming rules:**
- All names are kebab-case: `detect-spec-code-drift`, not `detectSpecCodeDrift`
- Action refs use plural: `actions/my-action`, `components/my-comp`
- Step IDs are short and descriptive: `build-graph`, `detect`, `render-results`

### Phase 2: Validate & Trace

Run these commands and fix all errors before proceeding:

```bash
ucf validate specs/           # 0 errors required
ucf trace specs/              # 0 data gaps required
```

Common issues to fix:
- Broken `$ref` → ensure referenced spec file exists
- Data gap → a step reads a field no prior step produces
- Dead data → a step produces a field nothing consumes (add a consumer or remove the output)

### Phase 3: Generate Test Skeletons

```bash
ucf generate specs/ --output tests/generated
```

This produces three files per use case in `tests/generated/{snake_name}/`:

| File | Regenerated? | Contents |
|------|-------------|----------|
| `interface.py` | Yes, always | Abstract class with `setup_*`, `action_*`, `verify_*` methods + dataclasses |
| `test_orchestrator.py` | Yes, always | Pytest test that calls methods in spec-defined order |
| `impl.py` | No, never overwritten | Concrete class with `NotImplementedError` stubs |

**Method categories derived from spec sections:**

| Spec section | Method prefix | Source |
|---|---|---|
| `requires` | `setup_*` | Component `provides` fields → return dataclass |
| `steps` | `action_*` | Step `input` → params, step `output` → return dataclass |
| `postconditions` | `verify_*` | Free-text assertion descriptions |
| `invariants` | `verify_*` | Referenced invariant names |

### Phase 4: Implement

Fill in `impl.py` — this is the only file you write by hand:

1. **`setup_*` methods** — instantiate real UCF objects (loader, registry, scanner, etc.)
2. **`action_*` methods** — call the real module code, return the generated dataclass
3. **`verify_*` methods** — write meaningful assertions, not just `assert isinstance(x, list)`
4. **Create a pytest fixture** at the bottom that instantiates the impl class

Store state on `self` so verify methods can check results from action methods.

### Phase 5: Verify

```bash
# Run the new use case tests
python -m pytest tests/generated/{snake_name}/ -v --tb=short

# Run full suite to catch regressions
python -m pytest tests/ -v --tb=short

# Check drift
ucf drift specs/ --source src/
```

**After implementation, add `@implements` markers** to source files:

```python
"""Module docstring.

@implements("actions/my-action")
@implements("use-cases/my-use-case")
"""
```

### Phase 6: Iterate

If tests fail → fix `impl.py` or the source module, never the `interface.py` or `test_orchestrator.py`.

If the generated orchestrator has issues (wrong args, scoping problems) → fix the **generator code** in `src/ucf/generator/`, then re-run `ucf generate`.

## Spec Authoring Reference

### Step input bindings

```yaml
input:
  registry: $loader.registry          # component alias.field
  graph: $steps.build-graph.graph     # previous step output
  target: $inputs.target              # external input (user-provided)
  data:                               # nested dict (passed as-is)
    count: $steps.detect.count
    items: $steps.detect.items
  format: table                       # literal value
```

### Step output bindings

```yaml
output:
  graph: graph              # action output field → context name
  node_count: node_count    # maps 1:1 to action spec's output fields
```

### Alternative flows

```yaml
alternative_flows:
  - name: no-results-found
    trigger: result_count is zero
    steps:
      - id: render-empty
        use: actions/render-cli-output
        input:
          data:
            message: no results
          format: tree
```

## Checklist

Before marking a feature complete:

- [ ] All action specs have `input`, `output`, `preconditions`, `postconditions`
- [ ] Use case spec has `steps`, `postconditions`, at least one `requires`
- [ ] `ucf validate specs/` reports 0 errors
- [ ] `ucf trace specs/` reports 0 data gaps
- [ ] `ucf generate` ran successfully
- [ ] `impl.py` filled with real assertions (not just `isinstance` checks)
- [ ] All tests pass (`python -m pytest tests/`)
- [ ] `@implements` markers added to source files
- [ ] `ucf drift specs/ --source src/` shows the new specs as mapped
