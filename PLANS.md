# UCF Execution Plans

An ExecPlan is a self-contained, living implementation document for a complex
feature, migration, or significant refactor. A new contributor must be able to
resume the work using only the current repository and the ExecPlan.

## When an ExecPlan is required

Use one when work crosses module boundaries, changes a public contract, adds a
work package from `docs/automation/BACKLOG.md`, contains meaningful unknowns,
or is expected to take more than one focused session. Small isolated fixes may
use the same discipline without creating a plan file.

## Non-negotiable properties

- Explain the user-visible purpose and the observable result first.
- State and challenge the foundational assumption before committing to the
  design. Include alternatives when more than one interpretation is plausible.
- Keep the plan self-contained and update it whenever facts, progress, or
  decisions change.
- Name repository-relative files, functions, commands, working directories,
  expected output, and recovery steps precisely.
- Make every milestone independently verifiable.
- Use Red-Green-Refactor. Identify the failing test before production edits.
- Record command evidence, not predictions such as "should pass."
- Do not ask for routine next steps while ready milestones remain.
- Do not silently resolve a decision gate defined in `AGENTS.md`.

## Required structure

Every plan in `docs/plans/` must contain all sections below.

### Purpose / Big Picture

Describe what a user can do after the change and how they can see it working.

### Foundational Assumption

State the root assumption, the cheapest falsification experiment, alternatives,
and the evidence that justifies the selected approach.

### Progress

Use timestamped checkboxes. Split partially completed entries into completed and
remaining work so this section always states the truth.

### Surprises & Discoveries

Record unexpected behavior with concise evidence such as a test or command
excerpt.

### Decision Log

Record the decision, rationale, date, and author. For a human decision gate,
also record options, trade-offs, and a recommendation.

### Outcomes & Retrospective

At each major milestone and at completion, compare delivered behavior with the
original purpose and name remaining gaps.

### Context and Orientation

Explain the relevant current code as if the reader has no repository history.
Define project-specific terms and name the important paths.

### Plan of Work

Describe the sequence in prose. Keep scope minimal and distinguish production
changes, tests, documentation, and migrations.

### Concrete Steps

Give exact commands, working directories, expected observations, and how output
is streamed and retained under `.artifacts/`.

### Validation and Acceptance

Define observable behavior, focused tests, affected suites, full gates, and
what exact evidence proves completion.

### Idempotence and Recovery

Explain safe retry, cleanup, rollback, and how to recover from partial failure.

### Artifacts and Notes

Keep short relevant transcripts, diffs, measurements, and log paths.

### Interfaces and Dependencies

Name the public types, serialized contracts, functions, protocols, and
dependencies that must exist. Explain compatibility and versioning.

## Completion rule

An ExecPlan is complete only when its acceptance behavior is demonstrated, all
required gates are green, the diff has been reviewed, state files are current,
and `Outcomes & Retrospective` records the result. If a repository-wide gate was
already red and is outside the package, the plan may finish only when the
failure is unchanged, recorded with fresh evidence, and the package did not
touch its scope. Work package `FND-001` is the exception: its purpose is to
remove the current red baseline, so every repository gate must be green.
