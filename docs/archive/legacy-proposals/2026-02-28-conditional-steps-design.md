# Design Document: Conditional Execution in UCF (Bottle Neck #13)

> **Historical proposal — superseded and rejected.** This document is not an
> ExecPlan, capability claim, or implementation authorization. Its raw
> expression/`eval()` design violates the current strict parsing and execution
> boundaries. It is retained only as historical context; current behavior is
> defined by executable contracts and `docs/CAPABILITIES.md`.

**Date:** 2026-02-28  
**Feature:** Conditional Steps (`when` and `skip_if`)  
**Status:** Superseded / not accepted

## 1. Overview
The UCF framework currently executes all steps sequentially. This design document outlines the implementation of conditional execution (if/else branching) to allow expressing business logic like Feature Flags and Approval Workflows directly in YAML specifications.

## 2. Architecture & Approach
We will use the **"Eval-Expression"** approach. YAML files will contain string expressions that are translated into Python boolean expressions during test generation.

### 2.1 YAML Syntax (Pydantic Models)
Two mutually exclusive fields will be added to `StepDef` in `src/ucf/models/usecase.py`:
- `when: str` - Step executes only if expression evaluates to `True`.
- `skip_if: str` - Step is skipped if expression evaluates to `True`.

**Example:**
```yaml
steps:
  - id: auto-approve
    use: actions/approve-order
    when: $steps.check-fraud.score < 50
```

### 2.2 Generator Implementation (`pytest_plugin.py`)
The orchestrator generator will translate YAML bindings (`$steps.foo.bar`) into local Python variables and wrap the action call in an `if/else` block.

**Translation Algorithm:**
A new helper `_translate_expression(expr: str)` will parse the string. 
- `$steps.check-fraud.score` → `check_fraud.score`
- `$inputs.amount` → `inputs.get('amount')`

**Generated Output:**
```python
if check_fraud.score < 50:
    auto_approve = uc.action_approve_order()
else:
    auto_approve = None
```
*Note: We must initialize the variable to `None` in the `else` branch to prevent `UnboundLocalError` in subsequent steps that might reference it.*

### 2.3 Tracer & Validation (`tracer.py`)
The static analyzer (`ucf trace`) cannot evaluate runtime expressions. Therefore:
1. Steps with `when`/`skip_if` will be visually marked as `[?]` (conditional) in the CLI tree.
2. Data produced by conditional steps becomes "Optional".
3. If an unconditional step requires data from a conditional step, the tracer should emit a warning: `Warning: Step depends on optional field from conditional step.`

## 3. Trade-offs & Security
- **Security (historical conclusion rejected):** Committed specifications and
  local/CI execution do not make raw expression evaluation safe. The proposed
  `eval()` boundary is not accepted and must not be implemented from this note.
- **Expressiveness vs Magic:** We chose string expressions over strict YAML dicts to allow complex logic (`A and (B or C)`).

## 4. Implementation Steps
1. Update Pydantic models with `when` and `skip_if` (with `@model_validator` for mutual exclusivity).
2. Implement expression translation logic in `pytest_plugin.py`.
3. Update AST generation in `pytest_plugin.py` to output `if/else` blocks.
4. Update `tracer.py` to handle visual formatting and dependency warnings for conditional steps.
5. Create a test use case to verify end-to-end functionality.
