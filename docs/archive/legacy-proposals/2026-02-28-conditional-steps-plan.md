# Conditional Steps Implementation Plan

> **Historical proposal — superseded and not accepted.** This file is not an
> active UCF ExecPlan and none of its task or commit instructions authorize
> implementation. In particular, its raw expression/`eval()` direction was
> rejected as inconsistent with the current strict security boundary. It is
> retained only as historical context.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `when` and `skip_if` fields in use case steps to allow dynamic branching (if/else) logic during test generation based on runtime context.

**Architecture:** 
1. Add `when` and `skip_if` fields to Pydantic `StepDef` model with mutual exclusivity validation.
2. Update the code generator (`pytest_plugin.py`) to parse these expressions, resolve bindings (`$inputs`, `$steps`), and generate `if` statements around action executions.
3. Update the tracer (`tracer.py`) to visually mark these steps as conditional (`[?]`) and handle output dependencies properly.

**Tech Stack:** Python 3.12, Pydantic, Pytest, Jinja2 (optional for code gen, though currently using raw string builders).

---

### Task 1: Update Pydantic Models for Conditional Steps

**Files:**
- Modify: `src/ucf/models/usecase.py`
- Modify/Create: `tests/models/test_usecase.py`

**Step 1: Write the failing test**
```python
# Create tests/models/test_usecase.py if it doesn't exist, or add to it:
import pytest
from pydantic import ValidationError
from ucf.models.usecase import StepDef

def test_step_def_supports_when():
    step = StepDef(id="test", when="$inputs.x > 0")
    assert step.when == "$inputs.x > 0"

def test_step_def_supports_skip_if():
    step = StepDef(id="test", skip_if="$inputs.y == False")
    assert step.skip_if == "$inputs.y == False"

def test_step_def_mutually_exclusive_conditions():
    with pytest.raises(ValidationError, match="Cannot specify both 'when' and 'skip_if'"):
        StepDef(id="test", when="True", skip_if="False")
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/models/test_usecase.py -v`
Expected: FAIL (ValidationError not raised or fields missing)

**Step 3: Write minimal implementation**
Modify `src/ucf/models/usecase.py`:
```python
# Add to StepDef class
    when: str | None = Field(default=None, description="Expression to evaluate. Step runs if true.")
    skip_if: str | None = Field(default=None, description="Expression to evaluate. Step is skipped if true.")

    @model_validator(mode='after')
    def check_mutually_exclusive_conditions(self) -> 'StepDef':
        if self.when is not None and self.skip_if is not None:
            raise ValueError("Cannot specify both 'when' and 'skip_if' on the same step.")
        return self
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/models/test_usecase.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/ucf/models/usecase.py tests/models/test_usecase.py
git commit -m "feat(models): add when and skip_if fields to StepDef"
```

---

### Task 2: Implement Expression Translator

**Files:**
- Modify: `src/ucf/generator/pytest_plugin.py`
- Modify/Create: `tests/generator/test_expression_translator.py`

**Step 1: Write the failing test**
```python
# Create tests/generator/test_expression_translator.py
from ucf.generator.pytest_plugin import _translate_expression

def test_translate_expression():
    assert _translate_expression("$inputs.amount > 100") == "inputs.get('amount') > 100"
    assert _translate_expression("$steps.check.score == 5") == "check_result.score == 5"
    assert _translate_expression("$inputs.type == 'A' and $steps.foo.bar") == "inputs.get('type') == 'A' and foo_result.bar"
```
*(Note: adjust expected `step_var` suffix based on how generator creates variables. If `step.id == 'check'`, does it create `check` or `check_result`? Assume `_to_snake(step_id)` for now, so `check`)*

Let's refine the test based on actual `_to_snake` behavior:
```python
def test_translate_expression():
    assert _translate_expression("$inputs.amount > 100") == "inputs.get('amount') > 100"
    assert _translate_expression("$steps.check-fraud.score == 5") == "check_fraud.score == 5"
    assert _translate_expression("$inputs.type == 'A' and $steps.foo.bar") == "inputs.get('type') == 'A' and foo.bar"
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/generator/test_expression_translator.py -v`
Expected: FAIL (ImportError, function not defined)

**Step 3: Write minimal implementation**
Modify `src/ucf/generator/pytest_plugin.py`. Add at module level:
```python
import re

def _translate_expression(expr: str) -> str:
    """Translates YAML bindings in expressions to Python variables."""
    def replacer(match):
        binding = match.group(0)
        parts = binding.split(".")
        if parts[0] == "$inputs" and len(parts) >= 2:
            field = parts[1]
            # assuming inputs dict is available in scope
            return f"inputs.get('{field}')"
        elif parts[0] == "$steps" and len(parts) >= 3:
            step_var = _to_snake(parts[1])
            fields = ".".join(_to_snake(p) for p in parts[2:])
            return f"{step_var}.{fields}"
        return binding

    # Regex to find bindings starting with $
    pattern = r'\$[a-zA-Z0-9_\-\.]+'
    return re.sub(pattern, replacer, expr)
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/generator/test_expression_translator.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/ucf/generator/pytest_plugin.py tests/generator/test_expression_translator.py
git commit -m "feat(generator): add _translate_expression helper"
```

---

### Task 3: Update Test Generator AST Logic

**Files:**
- Modify: `src/ucf/generator/pytest_plugin.py`
- Modify: `tests/test_pytest_plugin.py` (or whatever the main generator test is)

**Step 1: Write the failing test**
Create a test that generates code for a use case with `when` and asserts the generated `test_orchestrator.py` contains the `if/else` block.
```python
# Add to tests/generator/test_pytest_plugin.py or similar
# Need to setup a mock usecase with when field and check generated output
```

**Step 2: Run test to verify it fails**
Run test
Expected: FAIL (generated code lacks if/else)

**Step 3: Write minimal implementation**
Modify `_generate_orchestrator` (or equivalent method) in `src/ucf/generator/pytest_plugin.py`:
Find where `step_var = uc.{method_name}({args})` is generated.
```python
# Replace:
# lines.append(f"    {step_var} = uc.{method_name}({', '.join(args)})")

# With:
if step.when:
    py_expr = _translate_expression(step.when)
    lines.append(f"    if {py_expr}:")
    lines.append(f"        {step_var} = uc.{method_name}({', '.join(args)})")
    lines.append(f"    else:")
    lines.append(f"        {step_var} = None")
elif step.skip_if:
    py_expr = _translate_expression(step.skip_if)
    lines.append(f"    if not ({py_expr}):")
    lines.append(f"        {step_var} = uc.{method_name}({', '.join(args)})")
    lines.append(f"    else:")
    lines.append(f"        {step_var} = None")
else:
    lines.append(f"    {step_var} = uc.{method_name}({', '.join(args)})")
```
*Note: Also need to ensure `inputs` dict exists in the test scope if we are using `inputs.get()`. If the orchestrator currently doesn't define `inputs = {...}`, we need to add `inputs = kwargs` or similar at the top of the test function.*

**Step 4: Run test to verify it passes**
Run tests
Expected: PASS

**Step 5: Commit**
```bash
git add src/ucf/generator/pytest_plugin.py
git commit -m "feat(generator): support when and skip_if code generation"
```

---

### Task 4: Update Tracer Output and Warnings

**Files:**
- Modify: `src/ucf/cli/tracer.py`

**Step 1: Write the failing test**
Add a test in `tests/cli/test_tracer.py` with a conditional step and verify output has `[?]` prefix.

**Step 2: Run test to verify it fails**
Run test
Expected: FAIL

**Step 3: Write minimal implementation**
Modify `src/ucf/cli/tracer.py`:
When building the tree string for a step:
```python
# Before
# step_node = tree.add(f"{step.id}")

# After
if step.when:
    step_node = tree.add(f"[?] {step.id}  (when: {step.when})")
elif step.skip_if:
    step_node = tree.add(f"[?] {step.id}  (skip_if: {step.skip_if})")
else:
    step_node = tree.add(f"{step.id}")
```
*(Optional for now: adding context tracking for optional fields if it gets too complex, focus on visual display first)*

**Step 4: Run test to verify it passes**
Run test
Expected: PASS

**Step 5: Commit**
```bash
git add src/ucf/cli/tracer.py
git commit -m "feat(tracer): visually mark conditional steps"
```

---

### Task 5: End-to-End Verification (Dogfooding)

**Files:**
- Create: `specs/use-cases/test-conditional-flow.yaml`
- Create: `specs/actions/step-a.yaml`, `step-b.yaml`

**Step 1: Write the Spec**
Create a test spec using `when` and `skip_if`.
```yaml
kind: usecase
name: test-conditional-flow
actor: system
steps:
  - id: step-a
    use: actions/step-a
    output:
      value: value
  - id: step-b
    when: $steps.step-a.value > 10
    use: actions/step-b
```

**Step 2: Trace it**
Run `ucf trace specs`
Verify it shows the `[?]` marker.

**Step 3: Generate it**
Run `ucf generate specs`
Verify `tests/generated/test_conditional_flow/test_orchestrator.py` contains valid Python if/else logic.

**Step 4: Implement and Pytest**
Fill in the `impl.py` and run pytest to prove the framework successfully routes logic at runtime.

**Step 5: Commit**
```bash
git add specs/ tests/generated/
git commit -m "test: verify conditional execution end-to-end"
```
