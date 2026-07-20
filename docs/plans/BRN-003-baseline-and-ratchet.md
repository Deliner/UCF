# Add a language-neutral baseline-and-ratchet policy

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After BRN-003, a team can adopt UCF while known legacy violations remain
visible and explicitly bounded. Evaluating the same unchanged behavior does not
fail merely because the legacy debt still exists. A new violation or a
regression on new or semantically touched behavior fails. When debt is fixed,
that improvement becomes the new floor and cannot silently return. Any request
to widen the accepted debt produces a deterministic, reviewable delta rather
than resetting history.

The observable proof will compare exact, versioned, language-neutral ratchet
documents around the accepted BRN-002 onboarding bundle. It will demonstrate
all four backlog acceptance behaviors:

1. unchanged legacy debt is classified separately and passes;
2. a new violation is classified as a regression and fails;
3. a resolved violation is protected and its reintroduction fails;
4. a proposed weaker baseline is never applied implicitly and exposes the
   exact added allowance for review.

The Python core may compare neutral serialized identities, fingerprints,
rules, evidence coordinates, and policy outcomes. It must not learn Python
paths, AST nodes, decorators, frameworks, or file-creation heuristics.

## Foundational Assumption

The root assumption is that "touched behavior" can be calculated from stable
language-neutral behavior subjects and their semantic/evidence fingerprints,
without treating every repository revision or new file as a touch.

The cheapest useful experiment will use the accepted BRN-002 bundle shape and
compare three alternatives:

1. whole onboarding- or Behavior-IR document digests;
2. source file paths and created/modified status;
3. a stable behavior subject key plus separate semantic and observed-evidence
   fingerprints over the subject's exact materialization/candidate closure.

The experiment must exercise at least: identical input; changed capture or
provenance only; a semantic change under the same behavior identity; an
observed implementation/candidate change under the same behavior identity; and
an unrelated behavior change. It succeeds only if the selected representation
touches the affected subject, does not touch an unrelated subject, and does not
interpret a file rename or creation as behavior semantics.

Current code inspection gives reasons to distrust the first two alternatives.
`BehaviorEntityRef.canonical_digest` intentionally binds the entire Behavior
IR document, so a document-level digest invalidates every reference even when
one subject changes. The BRN-002 materialized entity graph also includes
decision provenance, so raw entity bytes can over-report capture-only change.
Conversely, file status is absent from the language-neutral Behavior and Trust
contracts and cannot represent generated, database, remote, or event behavior.
The third alternative appears viable because materializations retain stable
behavior root kind/ID separately from exact candidate and document
coordinates, but that is not accepted until the retained probe falsifies the
edge cases above.

If the experiment shows that current BRN-002 materialization cannot identify a
behavior across revisions without ambiguity, stop before defining a public
format and record whether the fix requires an additive onboarding profile or
an incompatible public-contract decision. No human decision gate is currently
present.

## Progress

- [x] 2026-07-19: Verify BRN-002 dependency acceptance from the final local
  profile and three independent contract/process/distribution reports; create
  this self-contained ExecPlan before BRN-003 production changes.
- [x] 2026-07-19: Retain the cheapest representation experiment and decide the
  exact behavior-subject, semantic-fingerprint, and evidence-fingerprint
  boundary. The root probe and three independent foundation reports accept a
  scoped stable root plus separately versioned semantic and observed
  projections; evidence is under
  `.artifacts/quality/brn003-start-20260719/` and
  `.artifacts/agents/brn003-foundation/`.
- [x] 2026-07-19: Run and retain the smallest relevant focused baseline for
  onboarding, IR/trust, CLI, package assets, and public claims.
  The selected 216-test slice passes under
  `.artifacts/quality/brn003-start-20260719/focused-baseline.log`.
- [x] 2026-07-19: Define exact closed versioned ratchet policy, assessment,
  baseline,
  evaluation report, and weakening-delta contracts with generated schemas and
  strict duplicate/reference/version/capability rejection. Four deterministic
  Draft 2020-12 resources and runtime/schema parity pass under
  `.artifacts/quality/brn003-start-20260719/schema-green.log`.
- [x] 2026-07-19: Add RED acceptance tests for unchanged debt, new regression, protected
  improvement, reintroduction, touched behavior, unrelated behavior,
  deterministic ordering, and explicit weakening review. Retained RED/GREEN
  logs cover policy, assessment, initial baseline, evaluation, successor,
  coverage escalation, broken rule references, and internal report
  consistency.
- [x] 2026-07-19: Implement the minimum pure comparison/evaluation core and keep policy
  state immutable; refactor only after the focused tests are green.
  Fifty-plus core tests now prove stable subject projection, unchanged/new/
  touched/resolved/reintroduced/unknown classification, exact evaluation
  recomputation, immutable predecessor-bound successors, historical protected
  tombstones, and cross-process hash-seed determinism.
- [x] 2026-07-19: Add an installed atomic CLI workflow and one unchanged
  BRN-002 fixture scenario without source mutation or hidden baseline
  replacement. Twelve command transaction tests and the clean-wheel package
  contract exercise `establish`, `evaluate`, and `advance`, including valid
  exit `1`, invalid exit `3`, sentinel preservation, and unchanged native
  behavior.
- [x] 2026-07-19: Publish exact documentation and CAP-205 evidence without claiming
  runtime verification, arbitrary policy analysis, or ecosystem breadth.
  `docs/RATCHET.md`, the capability matrix, onboarding boundary, and README
  are guarded by 14 executable claim tests.
- [x] 2026-07-19: Run affected and full gates, inspect the complete diff, obtain
  independent contract/policy/distribution/clean-snapshot acceptance, update
  baseline/state, and advance to `BRN-004`. The final 138-test affected slice,
  all seven local gates, `git diff --check`, contract, CLI/security, and
  physical clean-distribution audits pass under
  `.artifacts/quality/brn003-final3-20260719/` and
  `.artifacts/agents/brn003-{final-contract,final-cli-security,clean-distribution}/`.

## Surprises & Discoveries

BRN-002's `OnboardingBaseline` is a deterministic summary embedded in one
onboarding bundle. It intentionally has no policy, prior-baseline link,
violation identity, comparison result, or enforcing outcome. Reinterpreting
that `1.0.0` object as a mutable ratchet would silently change an accepted
contract. BRN-003 therefore needs a separately versioned comparison boundary
unless the foundational experiment proves that no new serialized state is
required.

The current Behavior reference is exact-document-bound rather than a stable
cross-revision subject key. Exact document binding remains necessary for trust
claims, but it is too coarse by itself for touched-subject selection. A ratchet
must preserve both coordinates instead of weakening `BehaviorEntityRef`.

The retained root probe first failed on its execution/import harness and an
incorrect assumption about the wire enum representation; those failures are
kept in `foundation-probe.log`, `foundation-probe-green.log`, and
`foundation-probe-green2.log`/`green3.log`. The corrected probe proves the
actual design pressure: a capture-only DecisionSet change changes both bundle
and Behavior document digests but changes no per-subject semantic/evidence
projection; a same-ID reviewed semantic edit touches only
`use-case.render-receipt`; a local confidence/evidence change touches only
`use-case.quote-order`; and a changed unrelated rejected candidate touches
neither accepted behavior. A simulated path rename produces a file-status
false positive, while a semantic change with no file-status delta produces a
false negative. The passing evidence is
`.artifacts/quality/brn003-start-20260719/foundation-probe-green4.log`.

The independent identity probe adds one important scope coordinate and one
negative result: stable identity is
`(inventory.subject_uri, root.target_kind, root.target_id)`, and the existing
inventory `_semantic_fact_identity` is not rename-neutral because it retains
the entry reference. BRN-003 must publish a new exact observed projection,
resolve local evidence records, and preserve raw paths/revisions only as trace.

The independent acceptance matrix requires protected-resolution tombstones.
Without them, removing an allowance would look like improvement once but a
later reintroduction could be mistaken for new adoptable legacy debt. Partial
subject or rule coverage likewise cannot prove resolution or permit baseline
advance.

The successor review found that a predecessor reference alone was
insufficient: the accepted matrix also requires an exact passing evaluation
reference, adjacent generation, complete subject and per-rule coverage, and
historical protections that may outlive a removed current subject. The public
baseline now enforces all four conditions. `SafeInteger` is reused for both
generation fields so model construction, JSON Schema, and the shared
cross-runtime decoder agree on the exact numeric range.

Structural parsing initially checked only report identity and ordering. An
adversarial RED showed that an attacker could recompute the report ID after
changing outcome, weakening-delta members, or an internal subject reference.
The parser now derives outcome and delta from classifications, resolves every
classification subject within the report, and leaves full external
classification recomputation to the contextual validator.

The installed package contract grew from exactly 12 to exactly 16 schemas.
It builds two byte-identical wheels at SHA-256
`3f2d752ac588b5ba5f20ef9ba1d31714f2d8dbd58a4a5b1b0d5e4ff3a045501d`,
imports the four ratchet resources from isolated site-packages, and executes
the complete transaction against the unchanged BRN-002 fixture. The
authoritative baseline tip remains a caller/VCS/CI trust anchor; a local hash
chain exposes discontinuity but is not a signed state service.

The final independent audits found two real acceptance gaps after the first
green profile. An existing output hard-linked to an input passed pathname-only
alias checks; retained RED/GREEN evidence now makes same-file identity exit
`3` while preserving both links. Separately, a present legacy allowance under
partial rule coverage returned `pass`; the evaluator now makes every otherwise
non-regressing partial assessment `inconclusive`, while a definitely observed
regression still takes precedence and fails. The exact RED/GREEN logs are
`hardlink-alias-{red,green}.log` and
`partial-current-{red,green}.log` under the BRN-003 start evidence directory.

The final physical clean snapshot contains 602 source files and remains
byte-identical before and after locked installs and all gates at manifest
SHA-256
`7b649f66bb7f90fd3caf7832a1e15e9a68ad15ae01ef1b8e119b37fc2f9d7cdd`.
Three independent wheel builds agree at SHA-256
`3f2d752ac588b5ba5f20ef9ba1d31714f2d8dbd58a4a5b1b0d5e4ff3a045501d`.

Two reviews disagreed on valid-regression exit `1` versus `4`. The retained
real CLI probe at
`.artifacts/quality/brn003-start-20260719/exit-class-probe.log` confirms the
existing UCF conformance convention: a valid failing policy result exits `1`,
while invalid/configuration processing exits `3`. BRN-003 uses that existing
class rather than inventing `4`.

## Decision Log

- **2026-07-19 — do not mutate or reinterpret onboarding baseline `1.0.0`.**
  Author: root agent. BRN-002 explicitly published a non-enforcing derived
  summary. Enforcement, history, and review deltas require their own versioned
  boundary if retained.

- **2026-07-19 — distinguish touch selection from evidence staleness.**
  Author: root agent. A behavior can be selected as touched because its
  semantic or observed fingerprint changed, while exact tested-evidence
  invalidation remains VER-002. BRN-003 must not fabricate runtime evidence or
  promote claims.

- **2026-07-19 — baseline weakening is data, never an evaluation side
  effect.** Author: root agent. Evaluation may produce a proposed baseline
  delta, but it must not overwrite the accepted baseline or turn regressions
  into legacy debt. Any eventual acceptance command must be explicit and
  reviewable.

- **2026-07-19 — accept a separate four-document ratchet profile.** Author:
  root agent. Publish exact `1.0.0` Policy, Assessment, Baseline, and
  EvaluationReport documents. Policy remains declared intent; Assessment
  remains producer-bound observations; Baseline is immutable accepted state;
  Report is a recomputable comparison. WeakeningDelta is nested in Report
  because it has no independent lifecycle or trust anchor.

- **2026-07-19 — scope stable subjects and version both fingerprint
  projections.** Author: root agent. Cross-revision equality uses repository
  `subject_uri`, materialized root kind, and root ID. The semantic fingerprint
  hashes the resolved non-provenance behavior closure. The observed fingerprint
  hashes rename-neutral resolved local fact semantics and confidence. Exact
  document/candidate/decision/source/provenance coordinates remain mandatory
  trace but do not select touch. Tool-version staleness remains VER-002.

- **2026-07-19 — preserve improvements through immutable successors.**
  Author: root agent. An initial baseline records current allowances. A passing
  advance creates a new predecessor-bound baseline, removes resolved
  allowances, and adds the same keys to protected resolutions. It may never add
  an allowance, remove protection, change policy, or mutate its predecessor.
  Partial coverage cannot resolve debt.

- **2026-07-19 — use exit `1` for a valid blocking evaluation and exit `3`
  for invalid processing.** Author: root agent. The existing conformance CLI
  was executed with one faulty candidate and returned `1`. `evaluate` writes
  its complete canonical pass/fail report atomically before returning `0`/`1`.
  Invalid input returns `3` and preserves output. `advance` writes no successor
  on either a valid fail or invalid processing.

- **2026-07-19 — make incomplete assessment coverage globally
  inconclusive.** Author: root agent. A known present allowance is still
  classified honestly as `unchanged_legacy`, but partial subject or per-rule
  coverage can hide other regressions. Therefore any otherwise non-regressing
  partial assessment is `inconclusive`; a definitely observed regression
  remains `fail`. Structural report validation permits externally justified
  inconclusive outcomes, while contextual validation recomputes them from the
  exact referenced Assessment.

- **2026-07-19 — reject filesystem identity aliases and disclose the parent
  trust boundary.** Author: root agent. Output path equality includes
  same-file identity so hard links to inputs fail before evaluation. Atomic
  replacement assumes a hostile local process cannot concurrently replace the
  existing parent directory; the public document names that residual boundary
  rather than claiming sandboxing.

## Outcomes & Retrospective

BRN-003 is accepted. It delivers the intended language-neutral,
baseline-and-ratchet boundary as four exact `1.0.0` documents and schemas, a
pure recomputable evaluator, immutable predecessor/evaluation-bound
successors, protected improvements, explicit weakening review data, and
installed atomic `establish`/`evaluate`/`advance` commands. Unchanged debt
passes only with complete evidence, new/touched/reintroduced violations fail,
partial coverage is inconclusive, and no path silently weakens the accepted
baseline.

Fresh local evidence is all seven gates with 42 automation tests, 989 Python
tests at 89% coverage, clean Ruff, 113 specs with zero errors/warnings,
installed packaging, and frontend build/lint under
`.artifacts/quality/brn003-final3-20260719/`. The installed workflow carries
exactly 16 schemas, executes the whole ratchet transaction, and preserves the
unchanged fixture. Independent contract and CLI/security audits accept 72 core
and 13 CLI tests plus adversarial probes. The clean-distribution audit repeats
the seven-gate profile from a newly installed 602-file source snapshot,
matches the local wheel SHA, and proves the source manifest unchanged.

The retrospective design lesson is that a standalone report cannot infer
coverage hidden behind its exact Assessment reference, and a pathname is not
a filesystem identity. Contextual recomputation and same-file checks close
those boundaries without copying adapter semantics into the core. Remaining
runtime evidence authenticity, signed/multi-writer baseline authority,
ecosystem breadth, and hostile-parent sandboxing are explicitly outside
BRN-003 and remain assigned to later dependency-ordered packages.

## Context and Orientation

BRN-002 onboarding contracts live under `src/ucf/onboarding/`. An
`OnboardingBundle` embeds the exact inventory, discovery, DecisionSet,
materialized Behavior IR, imported Trust IR, and a derived
`OnboardingBaseline`. `src/ucf/onboarding/bundle.py::_derive_baseline` rebuilds
that summary and `validate_onboarding_bundle` rejects any mismatch.

`BehaviorMaterialization` in `src/ucf/onboarding/models.py` connects one
accepted or edited candidate and decision to a Behavior root and its complete
materialized entity set. Its `BehaviorEntityRef` records exact behavior
document ID/version/digest plus target kind/ID. Discovery candidates separately
retain a content-derived candidate ID, semantic digest, evidence references,
and a proposed neutral entity graph. These are the existing inputs to the
foundational touch experiment.

Behavior and Trust IR remain under `src/ucf/ir/`. They are immutable exact
documents and must not be loosened for comparison convenience. The historical
Python-only drift scanners under `src/ucf/drift/` are not an accepted ratchet
boundary and must not be imported by a new neutral core.

The new boundary lives under `src/ucf/ratchet/`, with four generated resources
under `src/ucf/schemas/ratchet/v1/` and the generator at
`tools/generate_ratchet_schema.py`. CAP-205 is now narrowly `experimental`;
`docs/RATCHET.md` is the exact public contract and explicitly excludes runtime
capture, verified promotion, arbitrary policy execution, and ecosystem
breadth.

## Plan of Work

First, retain the representation experiment under
`.artifacts/quality/brn003-start-20260719/` and record its alternatives and
result here. In parallel, independently audit cross-revision identities,
negative-contract requirements, and the smallest end-to-end acceptance
scenario. Root reconciled those reports against the executable probe and
accepted the four-document boundary above.

Second, run the focused pre-edit baseline. Then add one acceptance behavior at
a time in strict Red-Green-Refactor order. Start with exact models/codecs and
negative format tests. Add comparison semantics only after malformed,
duplicate, broken-reference, incompatible-version, and non-canonical inputs
fail deterministically.

Third, implement a pure evaluator whose output depends only on exact serialized
inputs. It must classify current violations as unchanged debt, regression, or
resolved improvement; calculate touched subjects independently of file
creation; protect resolved debt; and emit an explicit weakening delta without
modifying the accepted baseline.

Fourth, expose installed `ucf ratchet establish`, `ucf ratchet evaluate`, and
`ucf ratchet advance` commands. Inputs and outputs must be
caller-selected files outside any inspected legacy root, validated before
replacement, and written atomically only after complete evaluation. The
unchanged `python_legacy_quote` fixture will provide the measured onboarding
bundle, but the ratchet core and documents must contain no Python-specific
coordinate.

Finally, publish generated schemas, installed package checks, documentation,
and a narrowly evidenced CAP-205 row. Run affected suites, all seven gates,
complete-diff review, and independent clean-source acceptance before advancing
to BRN-004.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream each command and retain its log.

Create the starting evidence directory and run the representation probe:

    mkdir -p .artifacts/quality/brn003-start-20260719
    <inline representation probe> 2>&1 | \
      tee .artifacts/quality/brn003-start-20260719/foundation-probe.log

Retain the focused baseline before production edits:

    uv run --locked --extra dev pytest -q \
      tests/onboarding tests/ir \
      tests/cli/test_adapter_discover.py \
      tests/cli/test_adapter_onboard.py \
      tests/automation/test_capability_claims.py \
      --no-cov 2>&1 | \
      tee .artifacts/quality/brn003-start-20260719/focused-baseline.log

For each acceptance behavior, first run the narrow new test and retain the RED,
then implement the minimum change and rerun it green. Exact test paths and
commands are:

    uv run --locked --extra dev pytest -q tests/ratchet --no-cov
    uv run --locked --extra dev pytest -q tests/cli/test_ratchet.py --no-cov
    uv run --locked --extra dev pytest -q \
      tests/automation/test_capability_claims.py \
      tests/automation/test_quality_gates.py --no-cov
    uv run --locked --extra dev python \
      tools/generate_ratchet_schema.py --check
    uv run --locked python tools/package_contract.py

Before completion:

    uv run --locked --extra dev pytest -q <affected paths> --no-cov
    uv run --locked --extra dev ruff check src tests tools
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/brn003-final3-20260719
    git diff --check

Expected final observations are zero exits for passing establish/evaluate/
advance, deterministic repeated report bytes, exit `1` plus one complete
canonical report for a valid regression, exit `3` with sentinel preservation
for invalid processing, an unchanged legacy fixture manifest, and no change to
accepted baseline input.

## Validation and Acceptance

BRN-003 is accepted only when executable evidence proves:

1. strict documents reject unknown fields, duplicates, broken/wrong-kind
   references, incompatible versions, non-canonical order, forged identities,
   unsupported policy capabilities, and a baseline that does not bind its
   exact source assessment;
2. identical current assessment against its accepted baseline classifies known
   legacy violations as unchanged debt and passes;
3. a newly introduced violation fails whether it is attached to a new or an
   existing behavior subject;
4. a semantic or observed-evidence change under a stable subject marks that
   subject touched, while unrelated behavior and capture-only metadata do not;
5. a resolved violation is recorded as an improvement, a passing successor
   protects its identity, and reintroduction fails rather than becoming legacy
   debt again;
6. a wider proposed allowance emits an exact reviewable delta and never
   replaces the accepted baseline as a side effect;
7. repeated canonical inputs produce byte-identical output across fresh
   processes and at least two `PYTHONHASHSEED` values;
8. installed CLI/package behavior works outside the checkout and the external
   Python fixture adapter remains outside the wheel;
9. the unchanged legacy fixture passes before and after with an identical
   complete manifest;
10. affected suites, all seven quality gates, full diff review, and independent
    clean-source acceptance are green.

No test may use skip, xfail, warning-only enforcement, baseline reset, path
exclusion, or manual output correction.

## Idempotence and Recovery

Model validation and evaluation must be pure and safe to repeat. CLI output
must use a same-directory temporary file, flush and fsync completed bytes, and
perform one atomic replacement. A valid failing `evaluate` writes its complete
canonical report and exits `1`. Parse, reference, version, configuration, I/O,
and serialization failures exit `3`, leave existing output and accepted
baseline unchanged, and remove package-owned temporary files. A blocked or
invalid `advance` never replaces its successor output.

Tests use temporary directories and copied fixtures. Evidence directories are
append-only by milestone. Generated schemas are reproduced from their
generator and checked for freshness; do not hand-edit generated JSON.

If the foundational representation fails, update this plan before any public
model or schema edit. If a public version or semantic decision meets an
`AGENTS.md` human gate, record options, consequences, evidence, and a
recommendation here and set `docs/automation/STATE.md` to
`blocked_on_decision`.

## Artifacts and Notes

Starting evidence belongs under:

- `.artifacts/quality/brn003-start-20260719/`;
- `.artifacts/agents/brn003-foundation/`.

Final acceptance evidence belongs under:

- `.artifacts/quality/brn003-final3-20260719/`;
- `.artifacts/agents/brn003-final-contract/`;
- `.artifacts/agents/brn003-final-cli-security/`;
- `.artifacts/agents/brn003-clean-distribution/`.

The retained directories include concise RED/GREEN, independent adversarial,
determinism, clean-install, package, native-fixture, manifest, and complete
profile evidence. Long raw logs remain outside this plan.

## Interfaces and Dependencies

Accepted dependencies:

- onboarding profiles and bundle `1.0.0`;
- Behavior IR and Trust IR `1.0.0`;
- inventory and adapter protocol `1.0.0`;
- exact canonical JSON, digest, identifier, URI, version, producer, and
  behavior-reference primitives;
- existing atomic output and package-asset conventions.

Accepted public boundary for the first RED:

- exact Policy, Assessment, Baseline, and EvaluationReport profile resources
  at ratchet version `1.0.0`;
- stable scoped subject snapshots with independently versioned semantic and
  observed fingerprint algorithms;
- versioned rule coordinates and stable rule/subject/finding-slot violation
  identities;
- initial allowances, immutable predecessor-bound tightening successors, and
  protected-resolution identities;
- nested weakening delta in a recomputable evaluation report;
- installed `ucf ratchet establish`, `evaluate`, and `advance` commands with
  `0`/`1`/`3` exit classes.

No production dependency, mutable baseline store, hosted service, Python path
or AST semantic, runtime trace capture, tested/verified promotion, arbitrary
policy language, source mutation, automatic weakening acceptance, or VER-002
evidence-staleness reinterpretation is authorized by BRN-003.
