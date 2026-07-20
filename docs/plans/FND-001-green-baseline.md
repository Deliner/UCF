# Restore a trustworthy green repository baseline

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After lockfile-faithful dependency installation, a contributor can run one
command from a clean checkout and see Python tests, lint, specification
validation, and frontend checks all pass. A freshly generated test skeleton
collects, and its intended tests execute after the contributor supplies the
deliberately user-owned implementation and concrete input fixture without
editing generator-owned files. This gives every later architecture package a
trustworthy regression signal.

## Foundational Assumption

The root assumption is that the current failures are repairable inconsistencies
in implemented behavior, not evidence that the existing public UCF model must
be redesigned. Falsify that assumption before broad edits: reproduce each gate,
write the smallest regression test for its failure mode, and inspect whether a
fix would reinterpret a serialized spec or generated-code ownership contract.

If a fix requires changing what a valid UCF use case means, stop at a decision
gate with alternatives. If the issue is a template/interface mismatch, invalid
repository fixture, unused import, or mechanical lint defect, fix it within
this package under a failing test.

## Progress

- [x] (2026-07-19) Record the initial failures in
  `docs/automation/BASELINE.md`.
- [x] (2026-07-19) Revalidate the foundational assumption with a fresh
  complete gate run. The same six gate identities produced the same one-green,
  five-red shape, and every failure remains attributable to a template/spec
  fixture or behavior-preserving source defect rather than a required public
  model reinterpretation. Evidence:
  `.artifacts/quality/fnd001-start-20260719/`.
- [x] (2026-07-19) Add an observable unified quality-gate test before its
  implementation.
- [x] (2026-07-19) Implement and verify the unified quality-gate runner; its
  unit test and focused Ruff check pass, and a full red run retained all six
  phase logs.
- [x] (2026-07-19) Reproduce the generated-suite collection failure with a
  fresh isolated generation regression test. The first RED failed because the
  generated orchestrator imported a fixture absent from the generated
  non-overwritten implementation stub. The second RED failed because
  `$inputs` was a hidden module global instead of an explicit pytest fixture
  dependency.
- [x] (2026-07-19) Make a fresh generated package collect, and make generated
  orchestration execute with explicit user-owned implementation and input
  fixtures. Focused and affected generator tests pass (32 tests).
- [x] (2026-07-19) Make fresh generated source pass repository Ruff rules,
  including a regression that regenerates all repository use cases. Template
  fixes removed fixture-name collisions, hidden globals, unused result
  captures/imports, and non-deterministic manual formatting pressure. The
  affected generator suite passes 35 tests.
- [x] (2026-07-19) Close two additional generated-contract gaps found while
  executing the checked-in suite. Alternative-flow-only actions are now part
  of the generated interface and implementation contract, required component
  parameters are forwarded explicitly, and missing input keys fail directly
  instead of becoming `None`. Three focused RED failures preceded the change;
  the affected generator suite now passes 37 tests.
- [x] (2026-07-19) Rechallenge the generated contract with an independent
  repository-wide probe. Five reproduced RED behaviors exposed unsafe
  action-reference reuse, hash-seed-dependent prerequisite ordering, ignored
  explicit dependencies, raw-order component setup, and normalized step-name
  collisions. Generation now uses one exact method contract per step
  occurrence, topologically orders component and action prerequisites,
  rejects unrepresentable normalized collisions, and has a repository-wide
  interface/call compatibility regression. The affected generator suite passes
  43 tests.
- [x] (2026-07-19) Make fresh and checked-in generated suites collect and
  execute under the documented ownership contract. The raw generated skeleton
  collects; a regression supplies only the user-owned implementation and input
  fixture and then executes it without changing generated-owned files. The
  checked-in suite passes 109 tests, including exact contract checks for all 27
  generated packages.
- [x] (2026-07-19) Repair repository spec parse and reference failures without
  weakening validation. A RED test now requires missing step references to be
  errors, all 113 specs load, and the CLI reports zero errors and zero warnings.
- [x] (2026-07-19) Make Python lint green through scoped source formatting and
  explicit Python 3.12 string-enum migration. Independent review found no
  semantic change outside generator behavior, unresolved-reference severity,
  and the recorded enum stringification correction.
- [x] (2026-07-19) Make frontend build and lint green. Removing the single
  unused type import cleared both source failures; a lockfile-faithful
  `npm ci` also repaired the incomplete local optional Rollup installation.
- [x] (2026-07-19) Run all gates, review the complete diff, and update state
  and evidence. The final profile passes all six phases with 325 Python tests;
  `git diff --check` is clean. Evidence:
  `.artifacts/quality/fnd001-final2-20260719/`.

## Surprises & Discoveries

- Observation: the focused core suite is green while full collection fails
  before tests execute.
  Evidence: `docs/automation/BASELINE.md`.
- Observation: generated output has both a fixture-name mismatch and an
  undefined `inputs` reference, so repairing only checked-in generated files
  would hide the template defect.
  Evidence: fresh generation review recorded on 2026-07-19.
- Observation: the previous count of 94 lint findings covered only `src`; the
  repository contract over `src`, `tests`, and `tools` reports 796.
  Evidence: `.artifacts/quality/preparation-20260719/python-lint.log`.
- Observation: 23 checked-in orchestrators referenced an undeclared `inputs`
  global, while three implementation modules lacked the imported pytest
  fixture entirely. The specification names inputs but does not provide safe
  executable values, so inventing generated defaults would fabricate evidence.
  Evidence:
  `.artifacts/quality/fnd001-start-20260719/generator-input-fixture-red.log`
  and the generator probe under `.artifacts/agents/fnd001-generator/`.
- Observation: the two invalid HTTP action fixtures already had canonical
  routes in their corresponding request actions, and the other two broken refs
  were genuinely absent framework action specs. Adding the known paths and
  minimal referenced actions resolves all step refs without interpreting the
  currently ignored response-only fields.
  Evidence:
  `.artifacts/quality/fnd001-start-20260719/repository-specs-green.log`
  and `spec-validation-green.log`.
- Observation: executing checked-in generated tests exposed contract loss
  beyond the original collection error: alternative-flow-only steps were
  invoked without being declared by the generated interface, component
  requirement parameters were discarded, and `inputs.get(...)` silently
  converted absent required keys to `None`.
  Evidence:
  `.artifacts/quality/fnd001-start-20260719/generator-contract-red.log`.
- Observation: repository lint fell from 796 findings to 81 after safe fixes
  and formatting. A focused RED/GREEN test established that wire enums render
  their language-neutral values; migrating the eleven affected enums to
  `StrEnum` kept 84 parser, expression, tracer, validator, and completeness
  tests green.
  Evidence:
  `.artifacts/quality/fnd001-start-20260719/str-enum-red.log` and
  `str-enum-green.log`.
- Observation: action-reference reuse was not a valid ownership simplification.
  Seven repository orchestrator calls had argument sets incompatible with the
  generated interface method they reused. Set iteration also produced two
  different prerequisite orders across hash seeds, reverse-ordered component
  declarations used values before definition, explicit `depends_on` edges
  disappeared from alt replay, and distinct IDs such as `foo-bar`/`foo_bar`
  silently collapsed.
  Evidence:
  `.artifacts/agents/fnd001-generator-review/` and
  `.artifacts/quality/fnd001-start-20260719/generator-review-regressions-red.log`.
- Observation: a raw generated implementation stub is intentionally
  non-executable because it raises `NotImplementedError`, and concrete input
  values cannot be inferred honestly from type declarations. Collection is a
  generator-owned guarantee; execution additionally requires user-owned
  implementation and input evidence. The regression exercises that workflow
  without editing generated-owned files.
  Evidence:
  `tests/unit/test_generator.py::TestGeneratorEngine::test_generated_package_executes_with_explicit_input_fixture`
  and `.artifacts/agents/fnd001-final-generator-audit/`.
- Observation: independent implementation/interface inspection found one
  incorrect alternative-flow result type plus four call-compatible but
  inexact method signatures in checked-in user implementations. A focused RED
  probe reproduced them; the corrected contracts and all 27 generated package
  contracts now pass.
  Evidence:
  `.artifacts/quality/fnd001-contract-fix-20260719/` and
  `tests/generated/test_interface_contracts.py`.
- Observation: `StrEnum` changes only Python `str()` and formatting for the
  eleven migrated enum classes. Equality, hashing, JSON, Pydantic schema and
  serialization, graph values, pickle, and explicit CLI rendering remain
  equivalent to `(str, Enum)`. All 70 members now have an explicit value
  stringification regression.
  Evidence: `.artifacts/agents/fnd001-enum-compat-spike/` and
  `tests/unit/test_string_enums.py`.
- Observation: an independent clean-copy run without the source checkout's
  `.venv` or `node_modules` passed after `npm ci`. That install reported ten
  dependency vulnerabilities, including five high-severity findings; this is
  retained security debt for release readiness rather than hidden FND-001
  debt.
  Evidence:
  `.artifacts/agents/fnd001-final-acceptance-audit/clean-copy-quality/` and
  `clean-copy-npm-ci.log`.

## Decision Log

- Decision: restore a fully green baseline before implementing the new IR or
  adapter architecture.
  Rationale: otherwise later failures cannot be attributed to new work and the
  automation would normalize pre-existing breakage.
  Date/Author: 2026-07-19 / Codex.
- Decision: treat checked-in generated tests as reproducible artifacts and
  repair their generator first.
  Rationale: direct edits alone would be a silent workaround and would fail on
  the next generation.
  Date/Author: 2026-07-19 / Codex.
- Decision: render `$inputs` as an explicit pytest fixture dependency only for
  generated tests that use it; keep concrete values on the user-owned side.
  Rationale: input mappings are declarations, not executable examples, so
  generated `None` or guessed values would produce misleading test evidence.
  Date/Author: 2026-07-19 / Codex.
- Decision: make required generated bindings use mapping subscription and
  forward component parameters through setup methods.
  Rationale: a missing required input must fail at the boundary, while a
  declared component dependency must receive the exact binding supplied by the
  use case. Silent `None` and discarded parameters fabricated executable
  confidence.
  Date/Author: 2026-07-19 / Codex.
- Superseded decision: include alternative-flow-only actions in the generated
  interface and reuse a method when the same action reference already has one.
  Superseded because: independent signature probes demonstrated that the same
  action can be bound with different parameter sets in distinct steps, making
  reuse unsound.
  Date/Author: 2026-07-19 / Codex.
- Decision: generate one exact method contract per step occurrence, order
  prerequisite execution by declared dependencies and spec order, and reject
  step identifiers that collide after Python-name normalization within one
  flow.
  Rationale: step bindings, not action identity alone, determine the executable
  signature. Stable topological ordering removes hash-seed variation, while an
  explicit rejection is safer than emitting ambiguous variables or overwritten
  abstract methods.
  Date/Author: 2026-07-19 / Codex.
- Decision: define generated ownership explicitly: interface and orchestrator
  files are deterministic generator-owned artifacts, while executable action
  behavior and concrete input examples are user-owned evidence.
  Rationale: emitting guessed values or passing stubs would fabricate
  verification. The generator must guarantee collection and a safe handoff;
  the execution regression must supply real user-owned inputs and behavior.
  Date/Author: 2026-07-19 / Codex.
- Decision: retain Python 3.12 `StrEnum` value stringification for all eleven
  migrated enums and record it as a pre-1.0 direct-module compatibility
  correction.
  Rationale: serialized formats, Pydantic schemas, graph data, and explicit CLI
  output are unchanged, while diagnostics no longer expose Python class names.
  The enums are neither documented nor exported from the package top-level,
  but direct consumers using `str()`, f-strings, or snapshots can observe the
  correction; tests pin the chosen value semantics for all members.
  Date/Author: 2026-07-19 / Codex.
- Decision: enforce exact method shapes and resolved return annotations between
  checked-in generated interfaces and every user implementation.
  Rationale: Python abstract classes do not reject compatible-looking but
  semantically wrong overrides, as demonstrated by the partial-validation
  result mismatch. A repository-wide regression prevents silent drift after
  regeneration.
  Date/Author: 2026-07-19 / Codex.

## Outcomes & Retrospective

FND-001 is complete. The unified runner executes all six phases even when an
earlier phase fails and retains one complete log per phase. The final profile
passes automation, 325 Python tests at 82% coverage, repository Ruff,
validation of 113 specs with zero errors and zero warnings, frontend build, and
frontend lint. `git diff --check` is clean. An independent clean-copy run of
the final executable state passed the same six gates after lockfile-faithful
frontend installation; evidence is under
`.artifacts/agents/fnd001-final-acceptance-audit-2/`.

The generated-code result is intentionally narrower than “raw stubs execute”:
fresh generator-owned output collects and is deterministic, while execution
becomes meaningful only after user-owned action implementations and concrete
input fixtures are supplied. The checked-in realization passes 109 tests and
all 27 implementation/interface contracts. Remaining parser strictness,
packaging, dependency security, and product architecture gaps belong to later
dependency-ordered packages and remain visible in
`docs/automation/BASELINE.md`.

## Context and Orientation

`src/ucf/generator/pytest_plugin.py` prepares generation context.
`src/ucf/generator/templates/` contains the interface, implementation stub, and
orchestrator templates. `tests/generator/` covers expression translation but
does not yet protect the complete generated package contract.
`tests/generated/` contains the checked-in executable realization plus a
repository-wide interface/implementation contract regression.

`src/ucf/models/`, loader, registry, and validator code define accepted specs.
Repository-owned examples live under `specs/`. The React frontend lives under
`web/`. `tools/quality_gates.py` is the intended local/CI entry point and writes
one log per gate under `.artifacts/quality/`.

## Plan of Work

First implement the gate runner from its failing automation test and run only
that test green. Then run the complete profile to refresh the failure inventory.

For generator repair, create a temporary-output regression test that invokes the
real generator on the smallest representative spec, imports or collects the
result, and demonstrates the exact fixture failure. Make the interface,
implementation, and orchestrator templates agree on one ownership contract and
provide defined inputs. Regenerate checked-in artifacts only through the
generator.

For specs, add or improve validator tests before fixing repository files. Do
not downgrade missing platform bindings or unresolved references to warnings.
For lint and frontend errors, use focused checks, make behavior-preserving
edits, and run affected tests after each coherent batch.

Finally run the entire profile, inspect all logs and `git diff --check`, and
update this plan, baseline, and handoff state.

## Concrete Steps

Run from the repository root. Each gate streams output and writes an individual
log:

    python3 tools/quality_gates.py --profile all

Run the automation unit first while developing the runner:

    uv run --extra dev pytest -q tests/automation --no-cov

Use the most focused failing test for every product change. After each green
focused test, run the affected module suite. Do not pipe a long-running command
through `tail`; retain output with the gate runner or `tee`.

## Validation and Acceptance

The package is accepted only when:

1. the automation tests demonstrate that a failed gate does not hide later
   phases, logs contain complete output, and the final exit is non-zero;
2. a fresh generated package collects, and its intended tests execute after
   supplying only the documented user-owned implementation and concrete input
   fixture;
3. `python3 tools/quality_gates.py --profile all` exits zero;
4. `git diff --check` exits zero and the diff contains no unrelated repair;
5. `docs/automation/BASELINE.md` contains fresh green evidence and
   `docs/automation/STATE.md` advances to `FND-002`.

Expected final summary contains only `PASS` gate statuses and a zero exit code.

## Idempotence and Recovery

Gate runs create timestamped ignored artifacts and do not modify source.
Generator regression tests must use temporary directories. Regeneration must be
deterministic and safe to repeat. If a mechanical lint batch changes behavior,
revert only that batch through a reviewed patch and keep the failing test
evidence; never reset unrelated working-tree changes.

## Artifacts and Notes

Initial evidence is in `docs/automation/BASELINE.md`. The preparation run is in
`.artifacts/quality/preparation-20260719/`, with one file per named gate and a
summary. The work-package start run is in
`.artifacts/quality/fnd001-start-20260719/`: automation passed; Python tests,
Python lint, spec validation, web build, and web lint reproduced the documented
failures. Generator RED/GREEN logs in the same directory retain the collection
and explicit-input contract evidence; the affected suite passed 32 tests.
The repository-generation Ruff regression reduced 314 fresh-output findings to
zero. Repository spec validation now loads 113 specs with zero errors and zero
warnings. The accepted profile is
`.artifacts/quality/fnd001-final2-20260719/`; its six phases pass and the Python
phase reports 325 tests. Focused final contract evidence is in
`.artifacts/quality/fnd001-contract-fix-20260719/`, and independent reviews are
under `.artifacts/agents/fnd001-final-*/`. The post-fix clean-copy acceptance
run is under `.artifacts/agents/fnd001-final-acceptance-audit-2/quality/` and
reports the same 325 tests and six passing gates.

## Interfaces and Dependencies

`tools.quality_gates.Gate` declares a stable gate name, command, and working
directory. `run_gates` must return ordered results, continue after failures,
stream combined stdout/stderr, and write one log per gate. The CLI profile
`all` is the single local and CI contract.

Generator interfaces must keep user-owned implementation code separate from
deterministic generated orchestration. The exact fixture type may change only
if the regression test proves the public generation workflow remains
executable.
