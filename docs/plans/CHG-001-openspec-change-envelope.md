# CHG-001 OpenSpec-Compatible Change Envelope

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect the current
truth.

## Purpose / Big Picture

After this package, a team can describe why one accepted behavior changes,
exchange that change with an existing OpenSpec-style workspace, bind an exact
language-neutral behavior delta, derive an ordered implementation task graph,
attach implementation and verification evidence, and archive the change with
its final Behavior IR snapshot. The observable proof is one unchanged
before-document plus one reviewed change that modifies a use case and completes
proposal -> delta -> tasks -> evidence -> verification -> archive through
installed UCF commands without turning prose into executable truth.

UCF will provide a typed, versioned lifecycle boundary for executable
coordinates and state transitions. It will not create a second prose project
manager, interpret arbitrary Markdown as verified behavior, or require an
existing OpenSpec user to abandon their current front end.

## Foundational Assumption

The root assumption is that accepted Behavior IR, Trust IR, canonical digests,
and implementation-evidence references already provide the executable objects
needed by a change lifecycle. CHG-001 should therefore add one separate
language-neutral lifecycle profile and a narrow filesystem import/export
boundary; it should not modify Behavior IR, reuse brownfield
`CandidateProposal` semantics, or embed OpenSpec Markdown structure inside the
core model.

The cheapest useful falsification experiment is no-production-edit and has
three parts:

1. inspect the current official OpenSpec primary documentation and sample
   repository to record the real proposal, delta-spec, task, and archive
   artifacts without relying on memory;
2. construct one canonical before/after Behavior IR pair for a single changed
   use case and a temporary OpenSpec-style change directory, then map proposal
   prose, ADDED/MODIFIED/REMOVED behavior, ordered tasks, evidence,
   verification, and archive coordinates in both directions;
3. compare four alternatives: a standalone UCF lifecycle envelope with
   import/export, reusing onboarding `CandidateProposal`, embedding prose in
   Behavior/Trust IR, or taking a new OpenSpec runtime dependency.

The probe passes only if the standalone envelope can preserve stable change
identity, exact before/after behavior digests, subject-level delta membership,
task order/dependencies, evidence references, archive state, and original
prose files without interpreting prose as Behavior IR. Unknown or lossy
official constructs must remain explicit diagnostics or opaque preserved
artifacts, never silently disappear. If lossless import/export requires a new
dependency, public-contract reinterpretation, or materially different archive
semantics, record the evidence and stop at the corresponding human decision
gate before implementation.

## Progress

- [x] 2026-07-20: Verify ECO-003, create this self-contained ExecPlan, preserve
  its full-gate and clean-source evidence, and set CHG-001 active.
- [x] 2026-07-20: Inspect current official OpenSpec artifacts, run the no-edit
  before/after mapping experiment, compare the boundary alternatives, and
  select one standalone six-resource lifecycle profile plus a bounded
  filesystem import/export profile; no decision gate was reached.
- [x] 2026-07-20: Freeze 37 generated positive, negative, and supporting
  context fixtures, six exact schemas, eight CLI commands, and the installed
  package contract through retained focused RED/GREEN slices.
- [x] 2026-07-20: Implement proposal, exhaustive behavior delta, ordered task
  graph, context-validated implementation evidence, accepted verification,
  immutable archive, and bounded OpenSpec import/export one acceptance
  behavior at a time under Red-Green-Refactor.
- [x] 2026-07-20: Close strict decoding, semantic Behavior IR revalidation,
  predecessor references, version/profile rejection, transition ordering,
  deterministic hash-seed replay, filesystem transaction preservation, and
  non-promotion negatives. Removed behavior is represented in the delta but
  explicitly cannot use old-subject execution evidence.
- [x] 2026-07-20: Close the final independent-audit findings with an
  iterative deterministic OpenSpec walk, explicitly owned Go verification
  pipes, and one root graceful-termination attempt. Retained deterministic
  regressions, Go suite/vet, 128/128 installed stress, and the independent
  re-audit all pass.
- [x] 2026-07-20: Publish exact capability/compatibility limits, integrate
  affected and installed-package gates, and complete independent
  contract/process/claims re-audit. The final focused integration slice passes
  292 tests and all 14 former-blocker adversarial cases pass.
- [x] 2026-07-20: Run all seven canonical gates, complete scope/diff review,
  and repeat a physical source-only clean replay. Both all-profile runs pass;
  the 830-file source manifest remains byte-identical at SHA-256
  `466939848e4f8ca81e495203e26c20446d77776cebb941684e799c850cceeaf7`.

## Surprises & Discoveries

The existing onboarding `CandidateProposal` is a discovery candidate for human
reconciliation, not a user-authored change proposal. Its confidence,
provenance, and materialization semantics are evidence-specific; reusing it as
the change envelope would conflate inferred code facts with intended change.
The foundation experiment confirmed this mechanically: the model has only
`kind`, `root`, and proposed entities and rejects exact base/final behavior,
removed subjects, tasks, evidence, verification, and archive coordinates.

The latest published OpenSpec release on the research date is
`@fission-ai/openspec==1.6.0`, release commit
`e1b51d111ab446b54dee2d6159ac245f0339ae52`, with built-in profile
`spec-driven@1`. Its current unreleased `main` differs and must not be folded
into that compatibility claim.

OpenSpec implements four delta headings, including `RENAMED`, but persists no
exact behavior base, typed task dependency graph, implementation evidence, or
verification receipt. The root probe also reproduced a successful published
CLI archive with three unchecked tasks and no durable verification. Therefore
an external archived directory is declared provenance, not UCF verified or
archived state.

A directory transaction cannot portably replace a populated destination with
one atomic rename. Export must publish to an absent directory (or accept an
exact existing manifest as a no-op), never merge into or delete an existing
user workspace.

An independent evidence audit found that accepting a typed `BehaviorIR`
object without reparsing it let `model_copy` bypass semantic reference checks;
the resulting broken final graph could reach archive. Lifecycle boundaries
now revalidate canonical Behavior IR, and archive wire decoding revalidates
its embedded final snapshot.

The same audit falsified ordinary execution evidence for `RemovedBehavior`.
A passed check against the old base subject proves that the old behavior ran,
not that it is absent from the final source. CHG-001 therefore rejects that
evidence profile explicitly. A later final-state absence/tombstone profile
must bind final inventory/source, a named absence check, producer, procedure,
and environment before removal can be accepted as implemented.

Adapter initialization and negotiation are runtime assertions, while the
original implementation record retained only the adapter result. The record
now carries a deterministic `context_validated_import` receipt containing
exact result, mapping, onboarding, and inventory digests plus both producer
identities, capability selections, and the UCF validation procedure. This
makes CHG contextual validation replayable; it does not authenticate that an
adapter process ran. Live session/operation evidence remains VER-002 scope.

The final predecessor audit falsified the assumption that content-addressing
the delta alone was sufficient downstream. A canonical caller could fabricate
delta subjects that do not exist in either referenced Behavior IR, recompute
the delta and task digests, and reach task/evidence validation because those
transitions had no documents against which to recompute exhaustive coverage.
Document digests provide identity only when the exact documents are supplied;
they are not an attestation that an earlier UCF command ran.

The final public-boundary audit also found that reference helper annotations
were insufficient at runtime: a different lifecycle resource could supply the
shared `change_id` and be hashed into a valid-looking wrong-kind reference,
while `None` leaked `AttributeError`. All five exported reference constructors
now require their exact declared document type before accessing fields or
computing a digest.

Recursive filesystem traversal failed with raw `RecursionError` before the
closed OpenSpec profile could classify a sufficiently deep tree. A first
repair added a 128-component filesystem bound, but an independent round-trip
probe falsified it: import counted from the change root while export counted
the added `changes/<change-id>` prefix, so a proposal accepted by import was
not exportable. The correct boundary is an iterative walk plus the existing
portable-path, 1024-character, count, byte, type, alias, and stable-read
limits; no new wire-level depth restriction is justified.

The first all-profile run exposed an intermittent installed Go verification
failure. Twenty sequential and eighty eight-way concurrent workflows passed,
while a 32-way run failed 38 of 128. Instrumentation showed that `Cmd.Wait`
closed `StdoutPipe`/`StderrPipe` before the reader goroutines completed:
twenty sampled failures were `file already closed`, none was an HTTP timeout.
A temporary explicitly owned `os.Pipe` implementation passed the Go suite and
128 of 128 equivalent stressed workflows. Increasing timeouts or ignoring
closed-pipe errors would conceal the integrity race and is rejected.

The first owned-pipe repair still failed two of 128 high-concurrency
workflows. A deterministic fixture then showed that cleanup sent `SIGTERM` to
the root process group repeatedly; a child that handled the first signal and
restored its default handler could be killed by a later retry before writing
its bounded result. Cleanup now sends one process-group graceful signal and
directly signals only tracked descendants while excluding the root, then
escalates to `SIGKILL` under the existing deadline. Both regressions pass
twenty repeated executions, the full Go suite and vet pass, and the final
installed stress passes 128 of 128.

## Decision Log

- **2026-07-20 — challenge import/export before defining a lifecycle
  schema.** Author: root agent. The package starts from official OpenSpec
  artifacts plus accepted UCF before/after documents. No production type,
  schema, CLI, or dependency will be selected until the smallest lossless
  boundary is demonstrated.
- **2026-07-20 — select one standalone immutable lifecycle profile and a
  pinned OpenSpec profile.** Author: root agent. The no-edit probe changed only
  `use-case.reserve-item` output requiredness and produced distinct exact base
  and final Behavior IR digests while retaining stable document and subject
  coordinates. A separate lifecycle profile can therefore bind proposal,
  exact delta, ordered tasks, evidence, verification, archive, and a bounded
  byte/digest artifact manifest without changing Behavior/Trust IR.
  Compatibility is named
  `fission-ai.openspec/spec-driven@1`, tested against OpenSpec 1.6.0. OpenSpec
  prose, including `RENAMED` headings, stays preserved non-executable input;
  UCF derives executable add/modify/remove operations only from reviewed
  before/after Behavior IR. A custom selected profile declaration fails
  explicitly, while overridden project config follows OpenSpec precedence and
  remains preserved but uninterpreted. No Node dependency is added.
- **2026-07-20 — use six immutable stage resources rather than one aggregate
  envelope.** Author: root agent. An independent core audit challenged the
  aggregate choice. The retained counter-probe shows that five optional stage
  payloads create 32 structural combinations but only five valid lifecycle
  combinations, leave 27 combinations to runtime-only conditionals, and churn
  the full history digest at every transition. Six closed resources
  (`ChangeProposal`, `BehaviorDelta`, `TaskGraph`, `ImplementationRecord`,
  `VerificationRecord`, `ArchiveRecord`) add five schema assets but retain the
  same one-output-file atomic transition, immutable predecessor digests, and
  direct structural closure. Evidence:
  `.artifacts/quality/chg001-foundation-20260720/resource-shape-counterprobe.json`.
- **2026-07-20 — keep UCF archive stricter than the external archive.**
  Author: root agent. OpenSpec validation/task/merge checks can be bypassed and
  its advisory verify is not persisted. UCF archive remains a pure immutable
  transition allowed only after complete tasks and accepted passing evidence.
  This is not a human decision gate because `TARGET_STATE.md` already fixes
  the required UCF semantics.
- **2026-07-20 — retain context-validated imported evidence without claiming
  execution authenticity.** Author: root agent. `ImplementationRecord`
  serializes exact context-validation coordinates and replays the full
  mapping/onboarding/inventory/result validator before verification or
  archive. Aligned user fabrication cannot be distinguished from an
  adapter-produced document without a live session receipt or trusted
  attestation, so CHG emits no Trust claim and CAP-210 must say
  context-validated, not authenticated, tested, or verified. VER-002 owns the
  live evidence loop.
- **2026-07-20 — fail closed for removed-behavior implementation evidence.**
  Author: root agent. The existing execution profile can prove the old base
  subject but cannot prove absence in final source. Reusing it would make a
  passing old test false evidence of removal. CHG-001 retains exact removed
  delta entries but raises `unsupported_evidence_profile` before
  implementation until a final-state absence profile exists. This is the
  smallest safe interpretation of the existing target and does not weaken or
  reinterpret an accepted public contract.
- **2026-07-20 — replay exact base/final Behavior IR through every accepting
  downstream transition.** Author: root agent. A retained counterexample
  forged a canonical delta subject, recomputed its task reference, and passed
  task validation without either referenced document. CHG-001 therefore
  requires the exact base and final Behavior IR when deriving or validating
  tasks, task completion, implementation, and verification; each stage
  recomputes the exhaustive delta before accepting its predecessor. Merely
  narrowing verification to “provisional” would contradict this plan's
  acceptance criteria and TARGET_STATE, while embedding duplicate Behavior IR
  snapshots in every lifecycle resource is unnecessary. The commands and
  Python surface are still active experimental work and have not been accepted
  or released, so correcting their required context now does not break an
  accepted public contract and does not reach a human decision gate.
- **2026-07-20 — treat task status as declared current state, not authenticated
  command history.** Author: root agent. An audit constructed an all-completed
  graph directly, but its bytes and semantics are identical to the state
  reached by the three pure `complete_change_task` transitions, and imported
  OpenSpec checkboxes intentionally supply the initial status. The lifecycle
  enforces dependency-reachable status, complete-before-implementation, and
  exact per-subject evidence; it emits no Trust claim for task completion and
  v1 already declares that task graph revisions are not chained. Adding event
  history or attestation would be a new speculative contract, not a CHG-001
  correctness fix.
- **2026-07-20 — keep the filesystem resource contract round-trippable.**
  Author: root agent. The temporary 128-component traversal limit classified
  deep input safely but made valid canonical resources non-exportable because
  import and export used different physical roots. CHG-001 will use an
  iterative traversal and retain the already-declared portable path, length,
  artifact-count, byte, regular-file, alias, and stable-read limits instead of
  introducing a new schema/profile rule.
- **2026-07-20 — own verification pipe lifetime independently of
  `Cmd.Wait`.** Author: root agent. Go's managed `StdoutPipe`/`StderrPipe`
  contract does not permit concurrent `Wait` before reads complete. The
  production check must create and close its own pipe endpoints around process
  start while preserving bounded readers, strict empty stderr/extra-stdout
  checks, process-group cleanup, and existing deadlines. Stress evidence
  falsified timeout inflation and error suppression as repairs.
- **2026-07-20 — attempt graceful termination of the verification root only
  once.** Author: root agent. Repeated process-group `SIGTERM` can terminate a
  cooperative root after it handles the first signal and restores the default
  handler. Cleanup therefore sends one group `SIGTERM`, excludes the root from
  the additional tracked-descendant signal, and retains bounded group
  extinction plus `SIGKILL` escalation. This preserves descendant cleanup
  without weakening cancellation, timeout, or failure precedence.

## Outcomes & Retrospective

CHG-001 is accepted. The result is a language-neutral, closed, canonical
`1.0.0` lifecycle consisting of six immutable resources and schemas:
proposal, exhaustive behavior delta, ordered task graph, implementation
record, verification record, and archive record. Thirty-seven generated
positive/negative/context documents and eight installed commands cover the
complete proposal -> delta -> tasks -> implementation -> verification ->
archive flow plus the pinned `fission-ai.openspec/spec-driven@1` import/export
boundary. Prose remains preserved declared input; it is never executable
behavior or verification evidence.

The final root slice passes 292 focused tests. Independent re-audit passes all
14 former-blocker adversarial cases, a 128-component canonical OpenSpec
round-trip, a typed 1,100-level traversal failure, four Go ownership/race
tests over 80 executions, the complete Go suite and vet, schema/fixture
freshness, and diff/format checks. Evidence is under
`.artifacts/agents/chg001-final-reaudit2/`.

The canonical profile under `.artifacts/quality/chg001-final2-20260720/`
passes all seven phases: 65 automation tests, 1,555 Python tests at 90%
coverage, Ruff, 113 specifications with zero errors or warnings, reproducible
packaging/clean installation, frontend build, and frontend lint. The accepted
wheel SHA-256 is
`a831ad5e5dc7023fef9691a28d8f6005d62df18c1a6b4dee6104ebc20eb70b1d`;
the Go adapter SHA-256 is
`e3a8e3848fe9736cec603258ab99d4ccb3bc678d1996b05b4ccc719002ab4440`.

The physical clean replay under
`.artifacts/agents/chg001-clean-source-snapshot/20260720T083629Z-chg001/`
starts from fresh locked Python and frontend installs, repeats all seven
phases, reproduces the same wheel and Go artifacts, and leaves all 830 source
files byte-identical at manifest SHA-256
`466939848e4f8ca81e495203e26c20446d77776cebb941684e799c850cceeaf7`.
CAP-210 remains experimental and states the exact compatibility, evidence,
task-history, removal, authenticity, filesystem, and platform limitations.

## Context and Orientation

Canonical behavior structures, deterministic encoding, semantic validation,
and document digests live in `src/ucf/ir/`. Intent/evidence records and
independent claim levels live in `src/ucf/ir/trust_*`. Exact implementation
mapping and verification references live in
`src/ucf/implementation_evidence/`.

Brownfield discovery candidates and human decisions live in
`src/ucf/onboarding/`; they are evidence-to-intent reconciliation inputs, not
change-management objects. Baseline weakening data in `src/ucf/ratchet/`
describes policy consequences and likewise is not a general behavior delta.

Installed CLI assembly is in `src/ucf/cli.py`. Closed schemas are generated
under `src/ucf/schemas/`, packaging inventory is enforced by
`tools/package_contract.py`, and canonical affected/full gates are in
`tools/quality_gates.py`. Public truth is `docs/CAPABILITIES.md`; CAP-210 stays
planned until this plan is accepted.

## Plan of Work

First, capture official OpenSpec artifact semantics and run the no-edit
foundation probe. Record which information is executable UCF state, which is
free-form prose, which can round-trip opaquely, and which is unsupported.
Reject any design that clones prose workflow features or silently infers
Behavior IR from Markdown.

Second, freeze a minimal exact lifecycle `1.0.0` fixture family before
production edits. Expected documents are a change envelope, behavior delta,
ordered task graph, implementation/verification evidence links, and archive
record, but the foundation result controls whether these remain one aggregate
or several closed resources. Every identity must be content-derived or
explicitly stable, every reference exact, and every transition recomputable.

Third, implement one behavior at a time. Begin with strict proposal and
before/after delta validation; then deterministic task ordering; then evidence
and verification binding; then archive; finally OpenSpec filesystem
import/export and atomic installed commands. Each slice starts with a focused
failure for the intended missing behavior, receives the minimum production
change, returns green, and is refactored only while affected tests stay green.

Fourth, close negative and operational boundaries: duplicate JSON members,
unknown fields, incompatible versions, broken or wrong-kind refs, duplicate or
cyclic tasks, invalid lifecycle transitions, stale behavior/evidence,
non-passing verification, archive-before-verification, path aliases, symlinks,
partial output, nondeterministic ordering, lossy import/export, and prose-driven
claim promotion. Unsupported official artifacts fail explicitly or round-trip
under a named opaque policy.

Finally, publish installed schemas/commands and exact compatibility limits.
Update CAP-210 only to the evidence actually demonstrated. Run affected suites,
packaging, all seven gates, independent audits, and a physical clean-source
replay.

## Concrete Steps

Work from `/home/deliner/projects/ucf` and stream every retained command under
`.artifacts/quality/chg001-start-20260720/`:

    git status --short
    uv run --locked --extra dev pytest -q \
      tests/ir tests/implementation_evidence tests/onboarding \
      tests/ratchet tests/automation --no-cov
    uv run --locked --extra dev ruff check src tests tools

The foundation artifact must include official source references, a checked
artifact-shape inventory, before/after Behavior IR digests, a field-by-field
round-trip matrix, alternative comparison, and the selected boundary. Run the
first production RED only after that result is recorded.

Before package acceptance run:

    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/chg001-final2-20260720
    git diff --check

## Validation and Acceptance

CHG-001 is accepted only when fresh executable evidence proves:

1. one proposal names a stable change identity and exact base Behavior IR;
2. a behavior delta distinguishes added, modified, and removed subjects and
   reconstructs or exactly binds the final Behavior IR without ambiguity;
3. an ordered task graph rejects missing, duplicate, cyclic, and
   non-canonical dependencies;
4. implementation and verification evidence bind exact delta subjects,
   source, producer, procedure, environment, and result coordinates without
   promoting a non-passing result;
5. archive is allowed only after complete tasks and accepted verification and
   preserves the proposal decision plus final behavior snapshot;
6. current official OpenSpec-style proposal/delta/task/archive artifacts
   import and export through a documented boundary without making prose
   executable or silently losing unsupported constructs;
7. repeated input produces byte-identical lifecycle and exported artifacts;
8. unknown fields, duplicate members, broken refs, incompatible versions,
   stale bases, invalid transitions, filesystem aliases, and partial writes
   fail explicitly and preserve accepted inputs/outputs;
9. installed commands work outside the checkout, CAP-210 and documentation do
   not overclaim, affected/full gates and independent audits pass, and a
   physical source-only replay is green.

No acceptance may use skip, xfail, warning-only enforcement, a reset baseline,
hand-edited generated output, hidden prose inference, path exclusions, broad
exception swallowing, or a dependency that was not selected through the
decision policy.

## Idempotence and Recovery

Foundation probes and validation are read-only. Generated fixtures and
OpenSpec workspaces use temporary external directories. Serialization is
canonical; import/export writes only after complete validation and uses
same-directory atomic replacement. A failed transition or export leaves prior
accepted artifacts untouched and may be retried from the same immutable input.

If the foundation requires a public-contract break, new production dependency,
hosted service, destructive migration, weaker correctness/security boundary,
or materially different lifecycle semantics, record options, evidence, and a
recommendation here and set `docs/automation/STATE.md` to
`blocked_on_decision`.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/chg001-start-20260720/`;
- `.artifacts/agents/chg001-openspec-foundation/`;
- `.artifacts/agents/chg001-contract-audit/`;
- `.artifacts/agents/chg001-process-distribution-audit/`;
- `.artifacts/agents/chg001-clean-source-snapshot/`.

Do not retain credentials, private proposal prose, raw sensitive evidence,
dependency caches, unbounded command output, or temporary workspaces.

## Interfaces and Dependencies

Accepted upstream contracts begin at exact version `1.0.0`: Behavior IR, Trust
IR, adapter protocol, onboarding, ratchet, implementation mapping, and
execution verification. CHG-001 may reference them but must not reinterpret
their semantics.

Any new lifecycle resource must be language-neutral, closed, versioned,
canonical, and schema-backed. Unknown fields, duplicate members, broken refs,
incompatible versions, and unsupported transitions are hard errors. Free-form
proposal text remains outside executable IR and is preserved only through
explicit file/digest/format coordinates. No new production dependency or
hosted service is assumed; selecting one is a human decision gate.
