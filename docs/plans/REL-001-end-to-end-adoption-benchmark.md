# REL-001 End-to-End Adoption Benchmark

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect current
repository evidence. Maintain it according to `PLANS.md`.

## Purpose / Big Picture

After this package, a prospective adopter can inspect one reproducible report
showing the complete UCF workflow against three unchanged legacy applications:
Python, TypeScript/Fastify, and Go. The report names what was discovered,
which candidates required scripted review, what was rejected, what behavior
was tested, how HTTP/CLI/event checks were covered, how long each phase took,
and how much UCF material was added outside the applications. Claims remain at
their actual observed/declared/mapped/tested levels.

## Foundational Assumption

The root assumption is that the accepted fixture-specific inventory,
discovery, reconciliation, baseline/ratchet, mapping, verification,
evidence-status, and lifecycle surfaces can be composed into one comparable
benchmark without changing a stable core schema or adapter protocol. The
benchmark itself should be repository/release proof, not a new product IR.

Challenge this before production edits with the cheapest useful experiment:
copy each frozen fixture, run its existing native check plus the smallest
accepted inventory/discovery/mapping/verification path, and inventory which
canonical outputs and timings are already available. Compare fixture manifests
before/after and build a field-sufficiency table for candidates emitted,
review decisions, accepted/rejected candidates, tested claims, platform
procedures, elapsed runtime, source size, and UCF artifact size. Retain the
probe under `.artifacts/quality/rel001-start-20260720/` and independent
read-only findings under `.artifacts/agents/rel001-*/`.

Alternatives are: orchestrate existing public CLIs from a release-only runner;
add an internal Python benchmark API; or publish three unrelated manual
transcripts. Select the smallest repeatable option that uses installed public
boundaries and produces machine-checked measurements. If comparable output
requires reinterpreting an accepted serialized field or choosing new product
semantics, record a decision gate before implementation.

Result: the assumption is false for the required complete workflow. Python
composes through ratchet. TypeScript and Go compose through real mapping,
verification, tested projection, and fresh evidence, including HTTP, CLI, and
event procedures, but their honest discovery coverage is `partial`. Ratchet
`1.0.0` copies that coverage exactly and rejects both baseline establishment
and advancement. No runner glue can change the result without changing a
public contract, changing accepted adapter semantics, or narrowing the target.

The human decision on 2026-07-21 selects a parallel Ratchet `2.0.0` dual
ledger. The continuation assumption was narrower and testable: current
inventory and onboarding evidence contains enough language-neutral semantics
to derive a conservative coverage-state key and separate semantic/observed
fingerprints while retaining exact provenance as trace. The cheapest
falsification compared exact-record identity, a projected stable key plus
fingerprints, and reconciliation state against unchanged reruns, path renames,
semantic edits, new interfaces, adapter-version changes, resolution,
reintroduction, and collision counterexamples in the Python, TypeScript, and
Go lanes. The projection succeeds for the three frozen fixtures and raw refs
are conclusively trace-only. The stronger universal-uniqueness assumption is
false: a valid inventory can contain two interfaces with the same path-free
logical coordinates. V2 therefore proceeds with an explicit
`ambiguous_coverage_identity` rejection rather than inventing a path-derived
identity or narrowing the advertised comparison domain.

## Progress

- [x] 2026-07-20: Accept VER-002 through independent reviews, complete local
  profile, complete diff hygiene, and physical clean-source replay; create this
  plan and activate REL-001.
- [x] 2026-07-20: Revalidate the composition assumption across all three frozen
  fixtures; reproduce the partial-coverage ratchet blocker independently,
  retain metric inputs and immutable manifests, and open the required public-
  semantics decision gate.
- [x] 2026-07-21: Record the project owner's selection of Ratchet `2.0.0`
  dual-ledger semantics, preserve v1, resume REL-001, and retain a fresh
  24-test v1 compatibility anchor under
  `.artifacts/quality/rel001-ratchet-v2-20260721/`.
- [x] 2026-07-21: Falsify coverage-state identity alternatives across all
  three lanes. Freeze the path-independent key and qualification domain,
  require explicit duplicate rejection, preserve exact refs only as trace,
  and correct the v1 migration rule so uncertain decisions are imported as
  debt. Root evidence is
  `.artifacts/quality/rel001-ratchet-v2-20260721/identity-projection-root-attempt2.log`;
  independent lane evidence is retained alongside it.
- [x] 2026-07-21: Freeze the exact v2 resource graph, granular debt identity,
  transition matrix, migration boundary, outcomes, namespace, and CLI version
  dispatch after three independent threat/surface audits.
- [x] 2026-07-21: Add a green v1 public/schema freeze manifest, retain the
  first isolated Ratchet v2 policy contract RED, and make that policy/strict
  codec boundary green without touching v1. Evidence is under
  `.artifacts/quality/rel001-ratchet-v2-20260721/`.
- [x] 2026-07-21: Make v2 assessment, dual-ledger baseline, evaluation,
  successor, and source-complete v1 migration green through 112 combined v1/
  v2 tests. Close independent findings for omitted debt, forged derived
  semantics, non-comparable reintroduction precedence, reviewed recurrence,
  and silent baseline replacement with retained RED/GREEN evidence under the
  same artifact root.
- [x] 2026-07-21: Complete Ratchet v2 strict closed schemas, projection,
  evaluation, successor, migration, explicit CLI, and clean installed package
  boundary while preserving v1. The affected v1/v2 suite passes 162 tests,
  six CLI v2 scenarios pass, and the reproducible wheel SHA-256 is
  `6f871ef887a2383dfb76088fdde4975c8f3a6c9178872bc9bf7ffc9ee232a61b`.
- [x] 2026-07-21: Re-run the composition falsification against clean copies of
  all three fixtures. TypeScript and Go compose through conformance,
  onboarding, Ratchet v2, mapping, real verification, tested projection, and
  fresh evidence. The real Python adapter is only 12/17 conformant and has no
  MAP/VERIFY implementation; record this prerequisite instead of substituting
  the generic echo sample or overstating native command evidence.
- [x] 2026-07-21: Complete the real Python out-of-process adapter's common
  conformance, four-way reconciliation, mapping, real-process verification,
  selective tested/fresh evidence, and one evidence-backed change lifecycle.
  The adapter passes all 17 common conformance cases in its explicit control
  profile while production mode honestly rejects generation; the combined
  Python evidence/lifecycle slice passes 38 tests and scoped Ruff. The clean
  installed package contract also executes the Ratchet v2 transaction and
  v1-to-v2 migration with reproducible wheel SHA-256
  `755d7fff2e9698401ce66079ef0c5efdd806b9f394b9ce258a447adf78522057`.
- [x] 2026-07-21: Close the independent pre-benchmark audit counterexamples:
  reviewed
  recurrence must beat qualification drift, v1 migration must reject partial
  public-interface inventory, the backing entry digest must make a body-only
  implementation edit observable without making unrelated files semantic,
  and real Python MAP/VERIFY must honor the selected root and cancellation.
  Root verification passes 155 combined Ratchet v1/v2 tests and 114 Python
  adapter/onboarding tests with scoped Ruff; retained RED/GREEN evidence is
  under `.artifacts/quality/rel001-ratchet-v2-20260721/`.
- [x] 2026-07-21: Retain the closed-report RED, implement four installed lane
  evidence producers, execute three complete repetitions, and publish the
  first checked report. All twelve native-before/workflow/native-after runs
  pass and the repeated structural digest is
  `c4251f0f01194cce8e4c7f5bd66924552d25196c857c07701bea1a5e849d1b0b`.
  The first full attempt exposed a virtual-environment symlink assumption;
  the second exposed an in-memory-vs-wire model comparison error; the third
  completed. Evidence is under
  `.artifacts/quality/rel001-benchmark-20260721/`.
- [x] 2026-07-21: Close the post-publication independent audit with retained negative
  contracts for provenance replay, exact runtime/transport/version identity,
  complete review and per-component overhead accounting, installed-wheel
  compilation, bounded I/O, typed failure recovery, and release-gate routing;
  regenerate and independently recheck the report only after those contracts
  are green. The accepted structural digest is
  `c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a`.
- [x] 2026-07-21: Prove unchanged fixtures, native behavior, all required platforms,
  complete adoption/change/evidence flow, deterministic structural results,
  and bounded measured runtime across three complete repetitions. The checked
  report records 13 candidates, 7 false candidates, 13 candidate decisions,
  5 tested claims, 0 verified claims, 18 uncovered interfaces, and 20
  unresolved coverage-debt entries without mutating any fixture.
- [x] 2026-07-21: Publish results and limitations, complete independent audits,
  affected suites, all eight gates, complete diff review, and physical
  clean-source replay before advancing to REL-002. The clean snapshot passes
  141 automation and 2,080 Python tests plus Ruff, specification validation,
  benchmark replay, package contract, frontend build, and frontend lint.

## Surprises & Discoveries

REL-001 starts with three already frozen fixture families under
`tests/fixtures/brownfield/`: `python_legacy_quote`,
`typescript_fastify_legacy_quote`, and the selected Go fixtures. Existing
tests prove their slices independently, but no single release artifact yet
proves a comparable complete workflow or publishes the required measurements.

The three-lane probe found a real asymmetry. Python discovery is complete and
the existing Ratchet transaction works. TypeScript retains 2 uncovered of 6
eligible public interfaces; Go HTTP retains 8 of 12 and the auxiliary
CLI/event root retains 8 of 9. These partial results are accepted, evidence-
preserving adapter behavior. `build_ratchet_assessment` must copy the partial
status, contextual validation rejects forged escalation, and
`establish_ratchet_baseline` returns `incomplete_coverage`.

Everything before that boundary is composable. TypeScript produces one real
HTTP tested claim and fresh assessment. Go produces real HTTP, CLI, and
temporally decoupled event tested claims and fresh assessments. Fixtures remain
byte-identical. The auxiliary Go platform root is one platform proof inside
the Go lane, not a fourth ecosystem fixture.

Metric categories also require exact separation: an oracle false candidate is
not synonymous with a rejected disposition; an uncertain candidate remains
separate. Review work must report candidate dispositions, ambiguity
resolutions, mapping approvals, and change approvals independently. Persisted
artifact bytes must separate authored and derived material because resources
embed earlier resources.

The decision review exposed an identity constraint that the original option
summary did not make explicit. Inventory record IDs bind complete record and
provenance content, while candidate IDs also bind the inventory, producer, and
procedure. They are exact trace coordinates, not demonstrated rename-neutral
cross-revision keys. Ratchet v2 therefore needs the same separation already
used for Behavior subjects: stable key, semantic fingerprint, observed
fingerprint, and exact trace. It must also retain four reconciliation states
without conflation: accepted/edited materializations belong to the Behavior
ledger; rejected candidates remain explicit reviewed non-materializations;
uncertain candidates and uncovered interfaces are unresolved coverage state.
A rejected proposal is neither verified absence nor automatically unresolved,
and a later transition cannot erase its reviewed history silently.

The cross-stack identity probe found no collision in the frozen domains:
Python has 4/4 unique keys, TypeScript/Fastify 6/6, Go HTTP 12/12, and Go
CLI/event 9/9. A valid synthetic inventory can nevertheless contain duplicate
path-free coordinates because Inventory v1 uniqueness also considers entry
and declaration content. Ratchet v2 must reject that ambiguity explicitly;
path, source span, raw IDs, source revision, and whole-file content cannot be
added to the key without turning benign trace churn into new debt. The frozen
key is `(subject_uri, public_interface, interface_kind_uri, container, name)`.
The predecessor-bound qualification domain includes inventory/discovery
schema and capability versions, producers and procedures, path identity,
ignore/eligibility profile, and key/fingerprint algorithm versions. Source
revision remains exact trace, not domain identity.

The probe also falsified one migration sentence from the initial decision
record. Complete discovery does not imply zero unresolved coverage debt: the
current complete Python review contains one uncertain candidate. A v1 baseline
alone cannot reconstruct it because it retains only the assessment reference.
Migration must therefore receive and validate the exact source Assessment and
OnboardingBundle, import every uncertain decision as inherited coverage debt,
and permit an empty coverage ledger only when the validated source contains no
uncertain decision. Missing or mismatched source resources are an explicit
migration error, never a generation reset.

The transition audit found that a content-derived baseline ID detects
accidental corruption but is not by itself an acceptance root: a caller could
rewrite debt fingerprints and recompute the ID. V2 evaluation and advancement
therefore require the independently pinned accepted baseline ID, and v1
migration requires the independently pinned accepted v1 tip ID. A changed
document with a newly self-consistent ID is rejected before classification.
The same audit confirmed that a protected exact recurrence remains a definite
failure even when the adapter qualification changes, and that an exact
previously reviewed candidate becoming uncertain is a reintroduction rather
than first-seen debt.

The v1 and v2 Behavior observed-fingerprint algorithms intentionally have
different versioned projections. Migration therefore validates the complete
v1 Policy/Baseline/Assessment/OnboardingBundle source, preserves stable keys,
semantic fingerprints, allowances, protections, and generation, then
reprojects v2 observed fingerprints from the exact bundle. Copying the v1
observed digest under a v2 algorithm URI was rejected as false provenance.

The post-Ratchet benchmark probe falsified the stronger composition assumption
for the Python lane. A clean four-file Python fixture passes native behavior,
produces 24 inventory records, four complete candidates, explicit 1/1/1/1
accepted/edited/rejected/uncertain decisions, two materialized Behavior roots,
and a qualified Ratchet v2 baseline with one inherited coverage debt. However,
its actual inventory/discovery adapter passes only 12 of 17 common conformance
cases and declares no mapping or verification capability. The generic sample
adapter is conformant but only echoes generic payloads; it cannot stand in for
Python implementation evidence. TypeScript and Go independently compose
through real mapping, verification, tested projection, and fresh evidence.

The pre-benchmark independent audit then falsified four narrower implementation
assumptions that the first green slices did not exercise. A reviewed candidate
which recurred as uncertain after producer qualification drift was classified
`unknown` instead of the decision's required `reintroduced` failure. A valid
v1 source with partial public-interface inventory migrated even though a direct
v2 establishment rejects that same incomplete domain. A body-only change to
the file backing a `PublicInterfaceFact` changed source revision but not the v2
observed fingerprint, so inherited debt passed unchanged. Finally, the real
Python adapter used process cwd instead of the accepted inventory root and did
blocking MAP/VERIFY preflight outside the registered cancellable operation.
The existing focused suite remained green, proving these were missing negative
witnesses rather than already enforced behavior. REL-001 cannot compose or
publish its benchmark until each counterexample is retained RED then green.

The first published report then passed all twelve real lane executions, its
closed codec, and three-run structural comparison, but the required independent
acceptance audit falsified the stronger provenance claim. Static `check`
accepted a one-phase runtime matrix, transport labels reassigned between
components, arbitrary overhead, and unsupported identity-version strings.
It also mislabeled one mapping result per component as a mapping approval,
discarded per-component overhead, omitted explicit zero ambiguity/change/
mapping approval categories, and did not identity-bind the benchmark drivers.
The source runner compiled Ratchet/lifecycle state in the checkout process even
though lane workflows used the clean-installed wheel. These are release-proof
contract gaps, not evidence that the executed lane results are false. The
TypeScript scalar-`tested_trust` audit finding is independently disproved by
the current producer's one-element array, its retained negative shape test,
and three successful real compiler repetitions; it requires no production
change.

The final lifecycle projection audit found one real determinism defect after
the report was otherwise green: the benchmark structural digest included the
runtime-generated execution-result ID and timestamp. Full lifecycle resources
still require strict contextual validation, but the report now hashes a
versioned semantic projection that removes only those runtime coordinates and
recomputes the dependent implementation, verification, and archive digests.
Two independent complete replays and a third security-audit replay agree on
the accepted structural digest; changing the verification outcome still
changes it.

The physical clean-source replay exposed two test-harness assumptions hidden
by a long-lived checkout. One Python mapping test hard-coded a trace-bound
candidate ID whose exact value legitimately changes with the complete
inventory; it now checks the public derivation algorithm while retaining exact
semantic and source-interface constants. A runtime-process test treated PID
file existence as publication even though `write_text` may briefly expose an
empty file; readiness now requires a complete decimal payload. Both defects
were retained RED, fixed without weakening production behavior, and replayed
green in the physical snapshot.

## Decision Log

- **2026-07-20 — measure review work without pretending automation is a human
  usability study.** Author: root agent. Report exact candidate counts,
  accept/edit/reject decisions, and review actions as machine-countable review
  work. Wall-clock measurements describe execution runtime only. Do not label
  scripted review duration as human effort.
- **2026-07-20 — keep the benchmark outside the core contracts unless the
  falsification probe disproves composability.** Author: root agent. Release
  evidence may orchestrate stable public CLIs and parse their versioned
  resources; it must not add benchmark fields to Behavior, Trust, or adapter
  protocol resources.
- **2026-07-20 — block on partial-coverage ratchet semantics.** Author: root
  agent. This is a human decision gate under `AGENTS.md`: the safe options
  change a closed serialized contract and the alternative narrows required
  product semantics. Root and independent probes reject every no-contract
  workaround. Options:

  1. add Ratchet `2.0.0` with a dual ledger: accepted Behavior debt remains in
     existing violation allowances while unresolved discovery coverage is
     separate non-claim legacy debt; unchanged exact debt may remain, added/
     changed/reintroduced debt blocks, resolved debt becomes protected, and
     partial rule coverage still cannot establish or advance;
  2. add Onboarding v2 decisions for every uncovered interface plus Ratchet v2,
     requiring explicit promote/exclude/defer review at substantially higher
     brownfield review cost;
  3. add a scoped Ratchet v2 whose pass applies only to explicit accepted
     Behavior scope while global coverage remains partial, with a material risk
     of overstated project-wide claims;
  4. narrow/defer REL-001 to Python-only ratchet and publish TypeScript/Go as
     incomplete, which is honest but does not meet the requested final state.

  Recommendation: option 1. Preserve Ratchet `1.0.0` byte-for-byte and add a
  major-version dual ledger derived from existing uncovered references and
  uncertain decisions. It keeps unknowns out of Behavior/claims, permits
  unchanged legacy uncertainty, blocks new uncertainty, and protects
  improvements without hiding accepted inventory evidence.

- **2026-07-21 — human decision: select Ratchet `2.0.0` dual ledger.**
  Decision owner: project owner; recorded by root agent. The recommendation is
  accepted with the following binding semantics:

  - Ratchet `1.0.0`, Onboarding `1.0.0`, their schemas, CLI behavior, installed
    assets, and existing Python result remain byte-for-byte and semantically
    unchanged. Ratchet v2 is a parallel major-version contract, not an in-place
    reinterpretation.
  - The Behavior ledger retains violation allowances and protected
    resolutions. A separate coverage ledger records the complete known
    comparison domain and its reviewed/unresolved states without creating a
    Behavior entity or Trust claim.
  - Accepted and edited candidates materialize into the Behavior ledger.
    Rejected candidates remain distinguishable reviewed non-materializations
    and cannot be treated as verified absence. Uncertain candidates and
    uncovered public interfaces are unresolved coverage debt. Exact wire
    spellings may be selected by the first contract RED, but these semantic
    partitions may not be merged.
  - Exact inherited unresolved debt may remain. Added, semantically or
    observationally changed, or reintroduced debt blocks. A comparable
    resolved entry becomes a protected tombstone. Absence under partial,
    changed, or non-comparable evidence is `inconclusive`, never resolution.
  - Enumerated partial subject discovery may establish and advance v2 only
    when the complete eligible comparison domain and every coverage state are
    represented. Partial rule coverage or an unenumerated/partial inventory
    domain still cannot establish or advance.
  - Cross-revision identity is a versioned language-neutral stable key with
    separate semantic and observed fingerprints; exact inventory, candidate,
    decision, path, source revision, adapter, capability, and procedure
    coordinates remain trace. Raw refs alone are not accepted as stable keys.
  - Adapter, capability, procedure, eligibility-profile, or comparison-domain
    changes require explicit requalification/migration. They cannot appear as
    an ordinary passing `advance` or silently resolve/add legacy debt.
  - V2 reports separate `behavior_outcome`, `coverage_outcome`, and
    `combined_outcome`. Partial global coverage can only produce an explicitly
    qualified result such as `pass_with_legacy_coverage_debt`; no output,
    documentation, capability claim, or UI may shorten it to project-wide
    `pass`, `tested`, or `verified`.
  - Scoped Behavior status is a subordinate v2 view. Its scope identity is
    predecessor-bound, may expand explicitly, and cannot silently shrink.
    Global coverage state remains visible and participates in the combined
    outcome, so scoped success is never a substitute for project state.
  - A deterministic v1-to-v2 migration must preserve generation, allowances,
    protections, predecessor history, and an exact `migrated_from` coordinate.
    It must validate the exact source Assessment and OnboardingBundle and
    import uncertain decisions as inherited unresolved coverage debt; an empty
    coverage ledger is valid only when that source has no uncertain decision.
    Missing/mismatched source resources, a generation-zero reset, or downgrade
    from v2 to v1 are forbidden. TypeScript and Go, which have no accepted v1
    baseline, may establish v2 directly.
  - No ratchet document promotes `observed`, `declared`, `mapped`, `tested`, or
    `verified`. Agents may derive and compare evidence, prepare review, and
    enforce transitions, but may not invent human product dispositions.
  - Mandatory decisions for every uncovered interface are deferred as a
    possible future strict/compliance onboarding profile, not the REL-001
    default. Python-only narrowing is rejected. If the stable-identity probe
    fails, return to an explicit decision gate rather than weakening these
    rules.

- **2026-07-21 — freeze conservative coverage identity and repair migration.**
  Author: root agent after root plus three independent falsification lanes.
  Use `(subject_uri, public_interface, interface_kind_uri, container, name)` as
  the versioned stable key, normalized local declaration/evidence and
  reconciliation projections as separate fingerprints, and exact refs,
  revisions, paths, spans, digests, adapter coordinates, and environment only
  as trace. Reject duplicate stable keys as
  `ambiguous_coverage_identity`; never merge, ordinally disambiguate, or add a
  path to the key. Bind comparability to the explicit qualification domain and
  require requalification when it changes. Correct the v1 migration rule as
  described above; this follows the already accepted principles that uncertain
  is debt and migration cannot erase history, so it does not introduce a new
  product choice.

- **2026-07-21 — freeze the implementable Ratchet v2 contract graph.** Author:
  root agent after independent surface, transition, CLI/migration, Python,
  TypeScript, and Go reviews. These are the exact implementation constraints:

  - V2 lives only at `ucf.ratchet.v2`; `ucf.ratchet`, its 65 exports, four
    Ratchet v1 schemas, two dependent Evidence Status schemas, and the three
    existing CLI commands remain frozen. The additive CLI is
    `ucf ratchet v2 {establish,evaluate,advance,migrate-from-v1}`. There is no
    `--version`, parser auto-detection, fallback, default change, or downgrade.
  - The four top-level resources remain Policy, Assessment, Baseline, and
    EvaluationReport with exact `2.0.0` coordinates. Assessment and Baseline
    contain visibly separate Behavior and coverage ledgers; a standalone
    migration document, configurable coverage policy, Onboarding v2, and
    coverage Trust claims are unnecessary.
  - Coverage is grouped by stable public-interface key but debt is granular.
    One group contains zero candidates (`uncovered`) or one-or-more exact
    reconciliation snapshots. An uncertain debt key is the coverage subject
    plus candidate semantic digest; uncovered debt is the coverage subject
    plus the literal uncovered slot. Candidate semantic collisions inside a
    group and duplicate subject keys fail as `ambiguous_coverage_identity`.
    This preserves independent progress when one of several candidate
    uncertainties is resolved.
  - The qualification domain binds the subject, inventory/discovery schema,
    capability, producer and procedure coordinates, public-interface
    provenance procedure set, path-identity algorithm, applied ignore-policy
    digest, and the coverage key/reconciliation/fingerprint algorithm
    versions. Source revision, environment, paths, spans, raw record/candidate/
    decision IDs, whole-file digests, and exact bundle coordinates remain
    trace. A changed qualification is explicit inconclusive/
    requalification-required and cannot advance; generic automatic
    requalification is outside REL-001.
  - Behavior keeps v1-shaped subject, rule, violation, allowance, and protected
    semantics behind v2-owned models. Coverage Baseline retains every current
    group plus exact unresolved allowances and protected resolved debt; keeping
    reviewed groups is required to distinguish later uncertainty from a first
    appearance.
  - Exact unresolved debt and fingerprints are `unchanged_legacy`. A new debt,
    changed semantic/observed fingerprint, or protected/reviewed
    reintroduction fails. A fully reviewed current group resolves prior debt on
    that subject and protects the exact old keys; in a mixed group, only exact
    remaining uncertainties inherit and each resolved debt is protected.
    Partial public-interface inventory, partial rule coverage, or changed
    qualification is inconclusive unless a definite regression exists, which
    retains fail precedence.
  - Missing unresolved subjects are not automatically accepted as deletion in
    REL-001. Inventory v1 cannot distinguish deletion from a move beneath an
    unchanged ignore prefix, so absence without an explicit current
    reconciliation remains `unknown`/inconclusive. This conservative rule
    avoids a silent baseline weakening; reconciliation-based resolutions still
    prove and protect the required ratchet improvement.
  - Wire outcomes are `behavior_outcome = pass|fail|inconclusive`,
    `coverage_outcome` and `combined_outcome =
    pass|pass_with_legacy_coverage_debt|fail|inconclusive`. Priority is definite
    fail, then inconclusive, then qualified pass, then plain pass. Only plain or
    qualified pass may advance.
  - V1 migration takes exact source Policy, Baseline, Assessment, and
    OnboardingBundle plus an explicit compatible target v2 Policy. It validates
    all reconstructable context, copies generation and Behavior state, imports
    uncertain decisions, and records all four v1 refs in `migrated_from`. A
    nonzero v1 tip becomes a v2 lineage root at the same generation; the next
    successor increments it. The content-addressed v1 chain is preserved, not
  falsely reverified without its full archive.

- **2026-07-21 — pin accepted lineage at every mutating v2 boundary.** Author:
  root agent after independent transition falsification. A self-consistent
  content ID is not proof that a baseline is the one previously accepted.
  `evaluate` and `advance` therefore require an independently stored accepted
  baseline ID; `migrate-from-v1` requires the accepted v1 tip ID. CLI inputs
  must expose these pins explicitly and may not derive them from the baseline
  being checked. Protected or reviewed exact recurrence is evaluated before a
  generic qualification mismatch, so definite failure keeps precedence.
  V1 observed fingerprints are never relabeled as v2: exact source evidence
  is used to reproject them under the v2 algorithm while preserving semantic
  state and lineage.

  New v2 error codes are `ambiguous_coverage_identity`,
  `incomplete_comparison_domain`, `incomplete_rule_coverage`,
  `non_comparable_coverage_domain`, `migration_source_mismatch`,
  `unsupported_ratchet_version`, `unsupported_capability`,
  `ratchet_downgrade_forbidden`, and `resource_limit_exceeded`, alongside
  isolated v2 equivalents of the strict v1 structural errors.

- **2026-07-21 — publish v2 as an explicit parallel installed boundary.**
  Author: root agent after independent codec, CLI, and packaging audits. Every
  v2 parser preflights exact version, kind, and schema coordinates; the policy
  schema and runtime both bind the exact evaluator capability. Evaluation
  publishes deterministic fail or inconclusive evidence with exit `1`, but
  advance preserves any existing output and cannot publish a successor for
  either result. Invalid inputs and lineage pins exit `3` without replacing
  output. The wheel exposes v2 only through `ucf.ratchet.v2` and the additive
  `ucf ratchet v2` CLI; v1 imports, leaf commands, schemas, and semantics stay
  unchanged.

- **2026-07-21 — complete the real Python adapter before publishing the
  benchmark.** Author: root agent after three independent clean-fixture
  composition probes. The required three-stack claim means each selected
  stack's actual adapter must pass the same conformance kit and brownfield
  flow. The generic reference sample cannot substitute for Python, and native
  test success cannot be promoted to a `tested` claim without exact mapping
  and verification evidence. Complete the existing external Python adapter
  over the stable protocol, using exact fixture-bound mapping and native
  verification procedures analogous to the accepted TypeScript and Go lanes.
  Keep all Python/framework semantics outside core; do not change the adapter
  protocol or Behavior/Trust IR versions.

- **2026-07-21 — correct implementation-observation and operation-boundary
  assumptions before benchmark composition.** Author: root agent after an
  independent adversarial audit. Keep the path-free stable coverage key and
  keep unrelated repository-entry digests out of it. However, include the
  content digest of the exact `RepositoryEntryFact` referenced by a public
  interface in that interface's versioned observed fingerprint. This detects a
  body-only edit to the implementation being classified without making a
  change in an unrelated file semantic. Exact path, record IDs, source spans,
  and source revision remain trace. Preserve the already selected precedence:
  an exact previously reviewed recurrence is a definite failure before generic
  qualification mismatch. Apply the same complete public-interface inventory
  prerequisite to v1 migration as to direct v2 establishment. For the Python
  adapter, resolve the validated request root beneath cwd and register every
  blocking MAP/VERIFY phase with one cancellation event before work begins.
  These are corrections to the unshipped v2/profile implementation, not new
  public semantics or a v1 change.

- **2026-07-21 — keep Python execution-environment identity selective.**
  Author: root agent after the evidence-status audit. The environment revision
  binds the actual interpreter, command/environment profile, and exact
  artifacts loaded by the native check. It must not also bind the whole
  inventory source revision: that would classify an unrelated repository file
  as `environment_changed` even though the executed environment and selected
  source records are identical. The verification request and evidence-status
  trace still retain the exact inventory/source revision, while selective
  source and mapping projections invalidate the result when a bound artifact
  changes. Require a real Python fresh assessment plus negative target drift
  and positive unrelated-file drift witnesses before lifecycle composition.

- **2026-07-21 — reject self-consistent benchmark evidence as sufficient
  release provenance.** Author: root agent after three independent
  post-publication audits and reproduced counterexamples. Keep the first
  report as development evidence, but do not accept REL-001 or update public
  capability claims from it. The accepted report boundary must additionally:

  - bind the exact compiler, scenario runner, four lane drivers, adapters,
    conformance reports, wheel, dependency lock, installed distributions,
    host OS/architecture, and toolchains;
  - derive transports from exact verification procedure URIs, bind successor
    Behavior and tested Trust resources into the repeated structural
    projection, and require the exact four-lane by five-phase runtime matrix;
  - report candidate dispositions, edited-candidate ambiguity resolutions,
    and explicit mapping/change approval counts separately. Absence of an
    approval artifact is reported as zero; a mapping result is never renamed
    to an approval and scripted work is never called human effort;
  - publish authored/derived bytes and top-level canonical resource counts per
    fixture, with separate shared-policy and lifecycle buckets plus a
    versioned accounting definition;
  - compile Ratchet, evidence-status, and lifecycle results under the same
    clean-installed wheel used by the lanes, preserve a closed typed failure
    receipt on failure, reject embedded POSIX/Windows absolute paths, and
    bound command and lane-evidence reads before allocation;
  - add an observable release gate that reruns all three repetitions and
    compares every deterministic/provenance section with the checked report,
    excluding only measured runtime samples. Static `check` remains a codec
    check and cannot substitute for replay.

  These are corrections to the unaccepted non-normative report/runner, not a
  new core or adapter contract and not a human product-semantics gate.

- **2026-07-21 — normalize only runtime lifecycle coordinates in benchmark
  identity.** Author: root agent after independent determinism review. Parse
  and contextually validate the complete lifecycle first, then replace only
  `ExecutionVerificationResult.id` and `executed_at` with a versioned stable
  projection and recompute every transitive lifecycle reference used by the
  benchmark digest. Keep procedure, environment, mapping, result, outcome,
  and all other semantic coordinates digest-sensitive. This makes repeated
  evidence comparable without presenting runtime identity as deterministic.

- **2026-07-21 — treat discovery candidate IDs as trace coordinates in
  cross-snapshot tests.** Author: root agent after the physical clean-source
  counterexample. A candidate ID binds the exact inventory and provenance by
  design, so tests must recompute it from the current accepted inputs rather
  than freeze a literal across different complete inventories. Continue to
  freeze the semantic digest and exact selected public-interface ID, ensuring
  the assertion still detects semantic or mapping drift.

- **2026-07-21 — define PID publication as a complete decimal payload.**
  Author: root agent after a clean-source race reproduction. File existence is
  not a readiness boundary because truncation precedes content publication.
  The observer retries empty or partial content and returns only a decimal PID;
  timeout and child-reaping requirements remain unchanged.

## Outcomes & Retrospective

REL-001 is accepted. The project-owner decision produced a parallel Ratchet
`2.0.0` dual ledger while Ratchet and Onboarding `1.0.0` remain unchanged.
Unresolved discovery coverage is explicit non-claim debt: exact inherited debt
may remain, new/changed/reintroduced debt blocks, and comparable resolution is
protected. Ambiguous identities, incomplete comparison domains, unsupported
capabilities, mixed versions, forged lineage, downgrade, and unsafe migration
all fail explicitly. The real Python, TypeScript/Fastify, and Go adapters pass
the common conformance boundary and execute their frozen brownfield flows;
the Go lane also proves the exact HTTP, CLI, and local file-spool event
procedures without adding transport fields to core IR.

The published closed report at `docs/benchmarks/rel001-report.json` is replayed
as an observable quality gate. Three complete repetitions agree on structural
digest `c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a`
and lifecycle digest
`83e7187bfe60982a11929237ba8696c5534f1b3c3bcaaa38de0a3e72ed7d0d38`.
It reports 13 candidates, 7 oracle false candidates, 13 candidate decisions,
one ambiguity resolution, zero mapping/change approvals, 4 mappings, 5
materializations, 5 tested claims, zero verified claims, 18 uncovered
interfaces, and 20 unresolved coverage-debt entries. Runtime samples and
authored/derived overhead are reported separately from deterministic identity;
scripted counts are not presented as measured human effort.

Fresh local evidence under
`.artifacts/quality/rel001-benchmark-20260721/` passes all eight quality gates.
The physical source-only snapshot at
`.artifacts/agents/rel001-clean-source-snapshot/20260721T034500Z-rel001/`
performed fresh locked Python and Node installs, passed 141 automation tests,
2,080 Python tests at 90% coverage, Ruff, 113 specification validations,
three-run benchmark replay, clean wheel installation/package scenarios,
frontend build, and frontend lint. Its 1,034-file source manifest remained
byte-identical before and after at SHA-256
`c8dd5c83796d2db24be725149546a44c0d6d227a60ee42946387169ea64c8858`;
the reproducible wheel SHA-256 is
`17cc39364e513d1f0cf6f5d94508146de8da5748ee7928d11e8dd2d8cd105489`.
Independent contract, claims, integration, reproducibility, and final
security reviews accept the corrected boundary.

The result remains deliberately bounded. No fixture yields a `verified`
claim; TypeScript and Go retain explicit legacy coverage debt; generation is
proved only for the documented Python profile; adapter support is limited to
the exact frozen capabilities and procedures; authenticity and accepted-tip
storage remain caller/VCS/CI trust anchors. REL-002 must now close release
policy, dependency/security, packaging, platform, licensing, support,
compatibility, migration, and deprecation readiness without inflating those
claims.

## Context and Orientation

Frozen legacy applications live under `tests/fixtures/brownfield/`. Python
onboarding behavior is exercised through the external reference adapter and
`src/ucf/onboarding/`; TypeScript/Fastify and Go adapter implementations live
under `adapters/` with ecosystem contracts in `tests/ecosystems/` and
`tools/*_adapter_contract.py`. Baseline/ratchet resources are in
`src/ucf/ratchet/`; exact execution mapping/results are in
`src/ucf/implementation_evidence/`; freshness is in
`src/ucf/evidence_status/`; the OpenSpec-compatible lifecycle is in
`src/ucf/change_lifecycle/` and `src/ucf/change_governance/`.

For this package, a false candidate is an emitted candidate that the frozen
review oracle rejects or must materially edit before acceptance. Review effort
is the explicit number of candidate decisions and mapping/change approvals,
reported by decision class; it is not elapsed human time. Runtime is measured
per named phase with a monotonic clock and multiple repetitions. Spec overhead
reports generated/accepted UCF bytes and logical records relative to immutable
legacy source bytes and files, while keeping generated artifacts outside the
fixture.

## Plan of Work

First, execute the approved Ratchet v2 identity falsification. Freeze source
manifests and native commands for all fixtures, compare alternative stable
coverage keys/fingerprints against exact trace identities, and reject any
projection that aliases different interfaces or treats rename/provenance churn
as new semantic debt. Freeze the v1 compatibility bytes before adding v2.

Second, retain one focused contract RED at a time and add the parallel v2
models, generated closed schemas, contextual projection, dual-ledger
evaluation, successor/migration invariants, explicit CLI version selection,
installed assets, and compatibility fixtures. Keep Onboarding v1 and Ratchet
v1 imports and bytes unchanged. Prove the exact outcome and transition matrix
before benchmark orchestration.

Before the benchmark report RED, make the actual Python adapter pass the common
conformance kit and add exact fixture-bound mapping and real native verification
through the existing protocol profiles. Project only passed contextual results
to `tested`, assess freshness against a recollected current context, and use
that evidence in one proposal-to-archive chain. This is required stack proof,
not a new core abstraction.

Third, add one failing automation test for a release benchmark command or
runner that consumes the frozen fixtures and external adapters. Require a
closed versioned report shape, exact fixture and tool identities, complete
phase results, honest claim counts, metric denominators, immutable source
manifests, no embedded absolute/temp paths, and explicit limitations.

Fourth, implement only the release-proof orchestration selected by the probe.
Keep runtime samples separate from deterministic structural identities.
Execute native pre/post checks, read-only inventory, evidence-bearing
discovery, explicit review/reconciliation, baseline, ratchet, mapping,
verification, evidence record/assessment, and one compatible proposal through
archive wherever the accepted adapter capabilities support them. Represent
unsupported steps as bounded named limitations, never as passes.

Fifth, publish the generated checked report in documentation and update
CAP-213 only to the evidence level actually demonstrated. Add freshness tests
that regenerate structural results and validate measured fields without
requiring byte-identical wall-clock durations.

Finally, complete independent Ratchet contract/migration, metric/claims,
ecosystem/integration, and
security/reproducibility reviews; close accepted findings with retained REDs;
run affected and full profiles; inspect the complete diff; and repeat the
physical source-only snapshot protocol.

## Concrete Steps

Work from `/home/deliner/projects/ucf` and retain streamed evidence:

    mkdir -p .artifacts/quality/rel001-start-20260720
    git status --short | tee \
      .artifacts/quality/rel001-start-20260720/git-status-start.log
    uv run --locked --extra dev pytest -q \
      tests/onboarding tests/ratchet tests/ecosystems \
      tests/implementation_evidence tests/evidence_status \
      --no-cov --capture=tee-sys | tee \
      .artifacts/quality/rel001-start-20260720/focused-baseline.log
    uv run --locked --extra dev ruff check \
      src tests tools | tee \
      .artifacts/quality/rel001-start-20260720/focused-ruff.log

The accepted post-decision v1 anchor is:

    mkdir -p .artifacts/quality/rel001-ratchet-v2-20260721
    uv run --locked --extra dev pytest -q \
      tests/ratchet/test_baseline.py::test_initial_baseline_rejects_partial_subject_coverage \
      tests/ratchet/test_assessment.py::test_assessment_cannot_escalate_partial_discovery_coverage \
      tests/ratchet/test_evaluation.py::test_partial_coverage_with_present_allowance_is_inconclusive \
      tests/ratchet/test_evaluation.py::test_observed_regression_under_partial_coverage_still_fails \
      tests/ratchet/test_successor.py \
      tests/ratchet/test_touch_projection.py \
      --no-cov --capture=tee-sys | tee \
      .artifacts/quality/rel001-ratchet-v2-20260721/v1-compatibility-baseline-attempt2.log

Before acceptance run:

    uv run --locked --extra dev pytest -q tests/automation \
      --no-cov --capture=tee-sys
    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all
    git diff --check

## Validation and Acceptance

REL-001 is accepted only when fresh executable evidence proves:

1. three immutable, unchanged legacy fixtures cover Python, TypeScript/Fastify,
   and Go through the same named adoption stages;
2. native behavior passes before and after, and fixture manifests are unchanged;
3. common adapter conformance plus brownfield inventory/discovery/
   reconciliation/baseline/ratchet/mapping/verification is exercised at the
   exact capability level each selected adapter declares;
4. HTTP, CLI, and asynchronous message/event procedures are tested without
   transport fields entering core IR;
5. false-candidate counts and denominators, explicit review actions, runtime
   samples, and spec-overhead bytes/records are measured per fixture with
   definitions in the report;
6. candidate, observed, declared, mapped, tested, stale, and verified counts
   are not promoted beyond reproducible evidence; verified remains zero;
7. one proposal-to-archive behavior change is linked to exact implementation
   and verification evidence without mutating the legacy fixture;
8. report regeneration validates deterministic structure while treating
   measured durations as samples, and all limitations are explicit;
9. installed/clean-source execution, affected suites, all eight gates,
   independent audits, complete diff review, and documentation claim checks
   pass.
10. Ratchet v1 schemas, canonical fixtures, Python API/CLI behavior, and
    installed assets are unchanged; v2 rejects mixed or downgraded documents.
11. V2 distinguishes Behavior and coverage outcomes, allows only exact
    inherited enumerated uncertainty, blocks added/changed/reintroduced debt,
    protects comparable resolutions, and never infers resolution from missing
    partial evidence.
12. Stable coverage identity is demonstrated across unchanged rerun, rename,
    semantic/observed edit, new interface, adapter requalification,
    resolution, reintroduction, and collision counterexamples in all selected
    ecosystem lanes.

## Idempotence and Recovery

All fixture work occurs in new temporary copies and writes benchmark output
outside the fixture roots. A failed phase preserves its typed report and
never advances later claims. Re-running structural phases with the same inputs
must produce the same canonical resources; runtime samples may differ and are
compared only through declared bounds/statistics. Failed or partial benchmark
publication uses a new output path and cannot replace accepted release
evidence.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/rel001-start-20260720/`;
- `.artifacts/agents/rel001-foundation/`;
- `.artifacts/agents/rel001-metrics-claims-review/`;
- `.artifacts/agents/rel001-integration-review/`;
- `.artifacts/agents/rel001-clean-source-snapshot/`.

Do not retain credentials, private repositories, raw sensitive runtime
payloads, dependency caches, or unbounded process output.

## Interfaces and Dependencies

REL-001 consumes accepted Behavior/Trust IR, adapter protocol/conformance,
inventory, Onboarding v1, runtime evidence, implementation evidence,
generation, lifecycle/governance, and evidence-status contracts without
changing their versions. It adds a parallel Ratchet `2.0.0` profile while
freezing Ratchet `1.0.0`. V2 must expose exact closed policy, assessment,
baseline, and evaluation resources; stable coverage-state keys/fingerprints;
dual outcomes and closed classifications; immutable successor and explicit
migration references; strict codecs/contextual validation; explicit CLI
version selection; generated schemas and installed compatibility assets. Any
benchmark report or runner must have an explicit version, closed fields,
deterministic structural identity, exact fixture/tool provenance, and a
clearly non-normative release-evidence status. No new production dependency is
authorized.
