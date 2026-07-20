# UCF agent instructions

## Mission

Bring UCF to a trustworthy, incrementally adoptable behavior-engineering
framework. Two product requirements are non-negotiable:

1. The same core must support multiple languages, frameworks, and execution
   platforms without embedding their semantics in the Python core.
2. An existing project must be able to adopt UCF gradually. UCF must discover
   evidence from a brownfield codebase, establish an explicit baseline, and
   ratchet quality forward without requiring a rewrite or complete specs first.

Read `docs/automation/TARGET_STATE.md`, `docs/automation/STATE.md`, and the
active ExecPlan before changing code. `docs/automation/BACKLOG.md` is the
dependency-ordered delivery map. `docs/automation/BASELINE.md` records known
failures; re-check evidence instead of assuming it is still current.

## Golden Flow

1. Challenge the foundation before implementation. State the root assumption
   and test it with the cheapest useful experiment. Record alternatives and the
   result in the active ExecPlan.
2. Optimize for the end-to-end user outcome, not the convenience of the
   current layer.
3. Add no hidden workaround or unrelated refactor. If a pre-existing problem
   appears, follow the decision policy below and record it.
4. Keep work observable. Stream command output to the terminal and a log file.
   Do not hide a running phase behind `tail`, buffered capture, or a final-only
   summary.
5. Use clear names, small single-purpose functions, minimal side effects, and
   no duplication. Improve touched code without expanding the task.
6. Use strict Red-Green-Refactor. First run a focused test that fails for the
   intended reason, make the smallest production change, run it green, then
   refactor while it stays green.
7. Say no to unsafe or contradictory work. Never call work done without fresh
   test, lint, build, and behavior evidence appropriate to the change.
8. Prefer the smallest complete solution. Add an abstraction only when a real
   boundary, duplication, or demonstrated change pressure requires it.

## Architecture guardrails

- The canonical behavior model and serialized intermediate representation
  (IR) are language-neutral and versioned.
- Language, framework, build-tool, and runtime knowledge belongs in
  capability-declaring adapters. The core communicates with adapters through a
  stable serialized protocol; it must not import adapter implementations.
- Treat declared specifications as intent and discovered code/runtime facts as
  evidence. Reconciliation is explicit; neither silently overwrites the other.
- Brownfield analysis must preserve provenance and confidence. Generated
  candidates are never presented as verified truth.
- Adoption is baseline-and-ratchet: unchanged legacy debt may be recorded;
  touched or new behavior must meet the current policy.
- Use an OpenSpec-style proposal/delta/tasks/archive lifecycle for change
  management. Do not rebuild a second prose-only change system inside the
  behavior IR.
- Do not claim formal verification unless the checked property, assumptions,
  and proof or exhaustive procedure are named and reproducible.

## Work protocol

For a complex feature, migration, or cross-cutting refactor, create or resume an
ExecPlan in `docs/plans/` and maintain it according to `PLANS.md`.

At the start of a work session:

1. Inspect `git status` and preserve unrelated user changes.
2. Read `docs/automation/STATE.md` and the active ExecPlan.
3. Revalidate the plan's foundational assumption.
4. Run the smallest relevant baseline check and save its output under
   `.artifacts/`.

During implementation:

1. Work on one acceptance behavior at a time.
2. Record the failing test and why it fails.
3. Implement the minimum change and rerun the focused test.
4. Refactor only the touched design, then run the affected suite.
5. Update the ExecPlan at every stopping point.

At the end:

1. Run `python3 tools/quality_gates.py --profile all`.
2. Review `git diff --check` and the complete diff for scope and regressions.
3. Update the ExecPlan, `docs/automation/STATE.md`, and baseline evidence.
4. Move to the next ready work package without asking for routine next steps.
   Stop only at a decision gate or when the requested package is verified.

## Decision policy for discovered debt

Fix a discovered problem in the same change only when it is required for the
active acceptance behavior, is covered by a failing test, and does not create a
new public-contract or migration decision.

Record it and continue when it is unrelated and non-blocking. Do not modify it.

Stop at a human decision gate when the choice would:

- break or reinterpret a public specification, serialized format, or CLI;
- select a new production dependency, license, or hosted service;
- discard data or require a non-reversible migration;
- weaken security, privacy, correctness, or an existing quality gate;
- choose between materially different product semantics;
- expand the active work package to hide a pre-existing failure.

Write the decision, options, evidence, and recommendation in the active
ExecPlan and set `docs/automation/STATE.md` to `blocked_on_decision`.

## Verification commands

- Automation tests:
  `uv run --extra dev pytest -q tests/automation --no-cov`
- Full quality gates:
  `python3 tools/quality_gates.py --profile all`
- Python tests:
  `uv run --extra dev --extra web pytest -q --disable-warnings`
- Python lint:
  `uv run --extra dev ruff check src tests tools`
- Specification validation:
  `uv run --extra web ucf validate specs`
- Frontend build:
  `(cd web && npm run build)`
- Frontend lint:
  `(cd web && npm run lint)`

The repository currently has known red gates. They are failures to remove, not
checks to skip or mark allowed. See `docs/automation/BASELINE.md`.

## Review guidelines

Review behavior and public contracts before style. Check for silent schema
acceptance, Python-specific assumptions in the core, false confidence in
brownfield inference, non-deterministic generation, missing negative tests, and
claims stronger than the evidence. A generated artifact must be reproducible
and either executable or explicitly labeled a non-executable draft.
