---
name: ucf-ultrawork
description: Run the repository's persistent, evidence-driven delivery loop for completing UCF work packages. Use when asked to continue, finish, autonomously implement, or resume the UCF roadmap across sessions. Do not use for a read-only review, a single isolated explanation, or work outside this repository.
---

# UCF Ultrawork

Continue UCF from durable repository state until the requested outcome is
verified or an explicit human decision gate is reached. Treat "ultrawork" as
this repository workflow, not as a native Codex mode.

## Orient

1. Read `AGENTS.md` completely.
2. Read `docs/automation/STATE.md`, `docs/automation/TARGET_STATE.md`, and the
   active ExecPlan named in state.
3. Inspect `git status`. Preserve unrelated and user-owned changes.
4. Set state to `in_progress` when starting a ready package.
5. If the active plan is missing or not self-contained, repair it according to
   `PLANS.md` before production changes.

## Challenge the foundation

State the work package's root assumption and run the cheapest useful
falsification experiment first. Compare at least two interpretations when the
product meaning is ambiguous. Judge the result against the complete target
state, especially language neutrality and brownfield adoption.

Record the experiment and evidence in the ExecPlan. Do not build around a failed
assumption.

## Execute one acceptance behavior

Use a strict loop:

1. Select the smallest incomplete acceptance behavior in the active ExecPlan.
2. Add or refine a focused test.
3. Run it and confirm it fails for the intended reason. Save meaningful output
   under `.artifacts/`.
4. Make the minimum production change.
5. Run the focused test green.
6. Refactor touched code for names, cohesion, duplication, and side effects.
7. Run the affected suite and update ExecPlan progress and discoveries.

Never batch several unproved production changes behind one late test run.
Never repair checked-in generated output without first repairing and testing
its generator.

## Handle discoveries

Apply the decision policy in `AGENTS.md`.

- Fix in scope only with a failing test.
- Record unrelated non-blocking debt and leave it untouched.
- At a decision gate, stop changing production code, document options,
  trade-offs, evidence, and a recommendation, then set state to
  `blocked_on_decision`.

Do not use a baseline, warning, skip, expected failure, broad exception, or
configuration exclusion to turn a regression green.

## Keep execution observable

Use commands that stream output as they run. For complete verification use:

    python3 tools/quality_gates.py --profile all

The runner retains per-gate logs under `.artifacts/quality/` and continues
through later phases after a failure. For other long commands, use `tee` with
`set -o pipefail`; do not use `tail` as the live progress view.

## Verify and hand off

Before declaring a work package complete:

1. Demonstrate its user-visible acceptance behavior.
2. Run the focused, affected, and full quality gates required by its ExecPlan.
3. Run `git diff --check` and review the complete diff for scope and risk.
4. Update the ExecPlan's progress, evidence, decisions, and retrospective.
5. Update `docs/automation/BASELINE.md` with fresh changed evidence.
6. Advance `docs/automation/STATE.md` to the next dependency-ready package.

If the request is to continue the whole project, immediately orient on the next
ready package. Do not ask for routine next steps. If execution must end because
the session or context ends, leave the state and active ExecPlan sufficient for
a stateless Codex session to resume without guessing.

Use the word "done" only when the documented acceptance commands pass. Otherwise
report the exact verified subset and the remaining or blocked state.
