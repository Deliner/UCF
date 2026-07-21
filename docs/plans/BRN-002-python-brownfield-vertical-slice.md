# Deliver the Python brownfield vertical slice

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After BRN-002, a team can point UCF at an unchanged representative legacy
Python application, collect the accepted BRN-001 inventory through an external
adapter, receive provenance-bearing behavior candidates, make explicit
accept/edit/reject decisions, materialize one accepted use case as exact
Behavior IR, and freeze a first honest onboarding baseline. The application
continues to run before and after onboarding without source changes.

The observable result is a deterministic onboarding bundle whose layers remain
separate:

1. immutable inventory and discovery evidence;
2. reviewable candidates with confidence and provenance;
3. explicit human dispositions, including unresolved candidates;
4. accepted Behavior IR intent;
5. Trust IR observations, declarations, mappings, and claims bound to that
   exact behavior document;
6. a baseline snapshot that records current known and unknown coverage without
   enforcing the BRN-003 ratchet.

The Python control plane must not import the Python adapter or learn Python,
framework, route, decorator, or test-discovery semantics. Those remain in the
out-of-process fixture adapter.

## Foundational Assumption

The root assumption to test is that pre-reconciliation candidate semantics can
cross the existing generic adapter payload without fabricating Behavior IR,
while the accepted Behavior IR and current Trust IR can represent the
post-reconciliation result without a new claim hierarchy.

The cheapest useful experiment compares:

1. writing candidates directly as current Trust IR records;
2. generating a provisional Behavior IR document and binding Trust IR to it;
3. carrying a separately versioned discovery/review profile in
   `AdapterPayload`, then creating Behavior and Trust IR only after an explicit
   decision.

The current code inspection already shows material pressure: every
`ObservedFact`, `Declaration`, and `Claim` requires an exact
`BehaviorEntityRef`, and every `TrustIR` requires an exact behavior document.
`BehaviorCandidate` currently represents only a possible mapping between trust
records, not a proposed use case. A direct pre-behavior Trust IR import would
therefore invent a subject or reinterpret trust IR `1.0.0`.

The retained probe under `.artifacts/agents/brn002-foundation/` falsified the
first two alternatives. Direct Trust IR cannot validate without fabricating a
Behavior document, exact entity subjects, declarations, and a document digest;
its existing `BehaviorCandidate` also accepts only a proposed trust-record
mapping. A provisional Behavior document validates only by prematurely turning
discovery into accepted intent. The generic `AdapterPayload` preserves the
candidate exactly without either promotion, but its intentionally generic
codec also accepts profile-specific unknown fields. BRN-002 therefore needs an
independently versioned, exact, closed discovery/review profile carried in the
generic payload. This result does not reinterpret or version Behavior IR,
Trust IR, or adapter protocol `1.0.0`.

The scanner-boundary experiment also rejected reuse of `ASTScanner` and
`SourceScanner`: the former walks itself, has no generated/vendor/test policy,
and follows an out-of-root symlink, while the latter discovers no behavior in
the unchanged unmarked fixture. Only the Python `ast.parse` algorithm may be
used inside the external reference adapter against exact inventory file bytes.
The accepted fixture boundary is the dependency-free
`tests/fixtures/brownfield/python_legacy_quote/` application proposed in the
retained report.

No human decision gate is currently present. If the experiment proves that
Behavior IR or Trust IR must change incompatibly, stop and record the exact
versioning options rather than silently reinterpreting `1.0.0`.

## Progress

- [x] 2026-07-19: Revalidate the candidate-representation assumption with serialized
  direct-Trust, provisional-Behavior, and independent-profile probes; retain
  scanner-boundary evidence. See
  `.artifacts/agents/brn002-foundation/representation-report.md`,
  `.artifacts/agents/brn002-foundation/probe-results.json`, and
  `.artifacts/agents/brn002-foundation/fixture-boundary-report.md`.
- [x] 2026-07-19: Retain the smallest relevant baseline and prove the chosen legacy Python
  fixture runs before onboarding with a complete unchanged-source manifest.
  The checked `python_legacy_quote` fixture passes three native checks and its
  eight-entry non-following manifest remains byte-identical at
  `654fe6c58854f11f910ef21a19d1098ddda8b9d20196862783493fc6561d228d`;
  see `.artifacts/agents/brn002-fixture-create/report.md`.
- [x] 2026-07-19: Define exact closed discovery, decision, and baseline bundle contracts
  with deterministic codecs/schemas and negative fixtures. The 61-test core
  onboarding slice covers discovery request/result, complete-inventory
  binding, candidate content identities, typed evidence references, exact
  coverage, stale-safe discriminated decisions, materialization, Trust import,
  bundle recomputation, wire conversion, and four published closed schemas.
- [x] 2026-07-19: Implement the minimum external Python adapter discovery operation
  through the accepted process protocol. One dependency-free process now
  negotiates inventory plus discovery, binds discovery to its exact completed
  same-session snapshot, emits four deterministic candidates, and exposes
  three localized negative modes without advertising `ucf.map`.
- [x] 2026-07-19: Implement explicit reconciliation that preserves accepted, edited,
  rejected, and uncertain candidates and materializes one accepted use case.
- [x] 2026-07-19: Import exact post-decision declarations, observations, mappings,
  provenance, and claim levels into Behavior/Trust IR without promotion.
- [x] 2026-07-19: Publish deterministic installed `adapter discover` and `adapter onboard`
  commands and documentation; prove repeatability, stale/adapter-failure
  atomicity, exact packaged schemas, native behavior, and a complete unchanged
  application manifest from a clean external wheel environment.
- [x] 2026-07-19: Run the affected integration suite and all seven quality gates. The
  affected slice passes 384 tests; the accepted local profile passes 38
  automation tests, 900 Python tests at 89% coverage, Ruff, 113 specs with
  zero errors/warnings, the installed package contract, frontend build, and
  frontend lint under `.artifacts/quality/brn002-final2-20260719/`.
- [x] 2026-07-19: Inspect the complete diff, obtain independent
  contract/process/distribution/clean-snapshot acceptance, update
  baseline/state, and advance to `BRN-003`.

## Surprises & Discoveries

BRN-001 intentionally stops before candidate generation. Its inventory
snapshot has content-derived identity and observed facts but no capture time.
The later discovery import must receive an explicit reproducible capture
context rather than inserting the current wall clock into canonical output.

Trust IR `1.0.0` is behavior-bound. Its `BehaviorCandidate` is a mapping
candidate whose subjects are existing trust records; it is not a container for
an inferred use case. This makes direct pre-reconciliation Trust IR the first
foundational hypothesis to falsify.

The protocol already has exact `ucf.discover` and `ucf.map` operation families
and capability gates, but their generic payload has no published
operation-specific semantic profile yet. BRN-002 must define the smallest
independently versioned profile rather than changing protocol `1.0.0`.

The external adapter owns inventory-to-candidate discovery, but no distinct
adapter-owned candidate-to-intent mapping exists in this package. Calling
`ucf.map` would duplicate the explicit human reconciliation decision and blur
ownership. Post-decision trust mapping remains available only when a real
Declaration-to-ObservedFact semantic mapping exists; the chosen fixture does
not justify inventing an Effect merely to exercise that record.

The inventory `source_revision` does not bind every classification and policy
detail in a complete inventory snapshot. A discovery request must therefore
bind both that source revision and the SHA-256 digest of the exact canonical
snapshot bytes. The measured fixture is small enough to embed the complete
snapshot in one bounded request. Paging is not justified by current evidence.

Both generic process launch paths were found to inject
`PYTHONDONTWRITEBYTECODE=1` and `PYTHONUTF8=1` into every candidate process:
`AdapterProcess.start()` and the conformance runner's minimal environment.
That is a hidden Python-runtime assumption in core. The first implementation
RED will require an undeclared language runtime environment to be absent while
also proving that a caller may still provide explicit environment entries.

The first RED reproduced both violations independently: the general process
child observed undeclared Python keys and the conformance candidate exited
when it saw them. Removing only the two implicit injections made both focused
tests green, preserved explicit caller-supplied `PYTHONUTF8`, and left all 169
adapter tests plus touched Ruff checks green. Evidence is retained in
`.artifacts/quality/brn002-start-20260719/runtime-environment-red.log`,
`runtime-environment-green.log`, and
`runtime-environment-affected-green.log`.

The inventory process driver originally owned profile-value conversion and the
whole inventory session internally. Reusing those private details for a
single-process inventory-plus-discovery workflow would duplicate a trust
boundary. The touched code now exposes one neutral profile-value codec and one
collector over an already initialized process; the existing inventory command
continues to use the same validation path.

The external reference adapter can retain the completed inventory snapshot in
the process session and independently rebuild the exact candidate identities
without importing UCF. The main-agent reproduction passes 23 focused
inventory/process tests and 158 affected onboarding/inventory tests; its
procedure is deliberately limited to the four measured top-level functions,
and unsupported or ambiguous interfaces remain explicit uncovered evidence.

The first independent core audit rejected the apparently green contract:
diagnostics bypassed duplicate/reference/order validation, the public Trust
builder trusted caller-forged materializations, the self-contained bundle
parser stopped at structure, and the published schema omitted the runtime
versioned-procedure constraint. Retained negative tests close all four. The
same review also exposed provenance stronger than its evidence: an observation
bound to a post-decision Behavior root traced discovery alone. Behavior-bound
observations now trace the exact DecisionSet, which transitively binds the
discovery and candidate; the separate discovery source remains preserved.

The installed decision-authoring smoke initially failed because direct strict
Python-model validation correctly rejects JSON strings/lists where enum/tuple
instances are required. Parsing the transformed replacement through
`model_validate_json` exercises the public JSON boundary and made the complete
external flow green without loosening model strictness.

## Decision Log

- **2026-07-19 — keep BRN-002 behind the adapter boundary.** The package must
  use `ucf.inventory`, `ucf.discover`, and, if the foundational probe confirms
  it is semantically distinct, `ucf.map` against an external process. The core
  may validate language-neutral profiles and reconciliation decisions; it may
  not import Python discovery code or legacy scanners.

- **2026-07-19 — do not treat a candidate as intent or evidence promotion.**
  Candidate output remains review material until an explicit decision creates
  exact Behavior IR. Rejection is retained, uncertainty remains unresolved,
  and confidence never creates a `mapped`, `tested`, or `verified` claim.

- **2026-07-19 — establish but do not enforce the first baseline.** BRN-002
  records current dispositions, evidence coordinates, and known/unknown
  coverage. Touched-behavior computation, anti-weakening rules, and regression
  enforcement belong exclusively to BRN-003.

- **2026-07-19 — accept a dedicated discovery/review payload profile.** The
  serialized comparison proves that pre-reconciliation use-case candidates
  cannot honestly inhabit current Behavior or Trust IR. Define an exact closed
  `1.0.0` onboarding profile in `AdapterPayload`; do not change the accepted IR
  or protocol versions. Candidate records carry no declaration, trust mapping,
  tested evidence, or verified claim.

- **2026-07-19 — omit `ucf.map` from the BRN-002 minimum.** The adapter-owned
  transformation is exact inventory evidence to candidate proposals through
  `ucf.discover`. Accepted/edited/rejected/uncertain disposition is a human
  reconciliation decision, not an adapter mapping operation. Add no capability
  merely to make the vertical slice look broader.

- **2026-07-19 — bind discovery to the complete inventory.** The request binds
  the exact canonical inventory snapshot by SHA-256 as well as
  `source_revision`, embeds it in one explicitly bounded frame, and rejects a
  mismatch atomically. Candidate and decision identities are content-derived
  and sorted; one exact disposition is required for every candidate.

- **2026-07-19 — use a new unchanged Python legacy fixture.** Keep
  `inventory_mixed` as the BRN-001 adversarial fixture. The BRN-002 proof uses
  `python_legacy_quote`, whose native command has three dependency-free checks
  and whose four discovered functions exercise accepted, edited, rejected,
  and uncertain review outcomes without UCF annotations or source changes.

- **2026-07-19 — make runtime environment configuration explicit.** Generic
  core launchers must pass only allowlisted ambient entries and entries
  explicitly supplied by their caller. Python fixture commands may use
  interpreter flags or explicit environment values, but core must not insert
  Python-specific keys.

- **2026-07-19 — publish adapter discovery coordinates, not draft IR
  coordinates.** Use
  `urn:ucf:adapter:discovery-request:1.0.0` and
  `urn:ucf:adapter:discovery-result:1.0.0` for the two profiles that cross
  `ucf.discover`; reserve `urn:ucf:onboarding:*` for human decision and final
  bundle documents. This follows the existing inventory/profile namespace
  without changing adapter protocol `1.0.0`.

- **2026-07-19 — make discovery coverage auditable.** The result names the
  exact canonical set of eligible public-interface evidence and the explicit
  uncovered subset. Complete coverage requires a candidate for every eligible
  subject; partial coverage preserves uncovered subjects rather than implying
  success. Coverage still makes no verification claim.

- **2026-07-19 — expose review as an explicit two-phase CLI.** A final
  `adapter onboard` command cannot be the whole usable flow because the exact
  discovery digest, candidate IDs, and semantic digests do not exist before
  the adapter runs. Add a read-only `adapter discover` canonical export, let a
  human author the existing exact DecisionSet, then make `adapter onboard`
  repeat discovery and reject any stale binding before its sole atomic bundle
  write. Do not add a draft-review schema. `DecisionSet.capture_context` is the
  explicit capture context; a duplicate CLI file or option would add only a
  mismatch branch. See
  `.artifacts/agents/brn002-review-workflow-audit/report.md`.

- **2026-07-19 — validate every public onboarding ingress at its available
  semantic boundary.** Discovery exchange validation owns diagnostic
  identities/order/references as well as candidates and coverage; the public
  Trust builder accepts only the exact deterministic Behavior/materialization
  result of current decisions; and the self-contained bundle parser runs full
  cross-document validation. Schema constraints must match runtime constraints.
  This closes the independent findings under
  `.artifacts/agents/brn002-core-contract-audit/report.md`.

## Outcomes & Retrospective

BRN-002 is complete. The foundational assumption was accepted only for a separate
exact discovery/review profile. The focused pre-edit baseline passes 380 tests
under `tests/inventory`, `tests/ir`, and `tests/adapters`; the checked unchanged
fixture passes all three native checks with an identical complete manifest.
The first process-boundary RED is closed with all 169 adapter tests green.
The remediated onboarding contract, reconciliation, materialization, Trust
import, baseline bundle, schema, wire, and real-process discovery slice passes
73 focused tests; schema freshness and touched Ruff checks are green, and the
canonical bundle has identical
`5ad7c8d667579beabe021cc3ebbef30453724db3650d3beee55779fd298671ab`
SHA-256 under `PYTHONHASHSEED=1` and `987654`. Installed CLI/distribution
behavior is now green: two wheel builds are byte-identical at
`6ea6d8557897c9c51a764a2608e9064c5207d6765de91963bc3a1b17dbab404e`,
all four exact onboarding schemas import from isolated site-packages, and the
copied external adapter/legacy fixture complete repeatable discovery,
review, onboarding, stale-review, adapter-failure, and unchanged native
behavior checks. All seven local gates subsequently passed under
`.artifacts/quality/brn002-final2-20260719/`: 38 automation tests, 900 Python
tests at 89% coverage, clean Ruff, 113 specs with zero errors and warnings,
the installed package flow above, and both frontend gates. Complete diff review
found no scope, whitespace, conflict-marker, or neutrality regression.

Independent contract/trust and process/CLI reviews report ACCEPT with 73 and
83 focused tests respectively. The independent distribution review copied the
complete intended source into a 573-file source-only snapshot, reproduced all
seven gates, built the same wheel twice at
`6ea6d8557897c9c51a764a2608e9064c5207d6765de91963bc3a1b17dbab404e`,
proved isolated imports and exactly 12 schemas including all four onboarding
resources, and confirmed that the external Python fixture adapter is absent
from the wheel. Its installed two-phase flow was byte-deterministic, preserved
the existing output on stale-review and adapter failures, and left the
eight-entry legacy manifest unchanged at
`654fe6c58854f11f910ef21a19d1098ddda8b9d20196862783493fc6561d228d`.
The normalized source manifest stayed unchanged at
`b264257996b85a6ecc90e3f155ffad757cfa5805ef0a60119f7a66fc340c756e`.
Evidence is retained in
`.artifacts/quality/brn002-start-20260719/focused-baseline.log`,
`.artifacts/quality/brn002-start-20260719/foundation-representation-probe.log`,
`.artifacts/quality/brn002-start-20260719/proposed-fixture-native-reproduction.log`,
`.artifacts/quality/brn002-start-20260719/onboarding-core-current.log`, and
`.artifacts/quality/brn002-start-20260719/installed-onboarding-package-contract-green.log`.
Independent reports are under
`.artifacts/agents/brn002-contract-reacceptance/`,
`.artifacts/agents/brn002-process-cli-reacceptance/`, and
`.artifacts/agents/brn002-distribution-clean-acceptance/`.

The original user-visible purpose is met for the one measured unchanged
dependency-free Python fixture: evidence, candidates, all four human
dispositions, materialized intent, Trust IR, and an honest non-enforcing
baseline remain distinct and reproducible. The public claim remains
experimental. Product-level baseline enforcement remains BRN-003, optional
runtime evidence remains BRN-004, and broader Python framework/ecosystem
support is not claimed.

## Context and Orientation

The accepted inventory core is under `src/ucf/inventory/`; it validates exact
request/page/snapshot profile `1.0.0` and drives an external process without
ecosystem semantics. The checked inventory fixture and adapter are under
`tests/fixtures/brownfield/inventory_mixed/` and
`tests/fixtures/adapters/inventory_reference_adapter.py`. BRN-002 uses the
separate representative `python_legacy_quote` application fixture rather than
reinterpreting the neutral mixed inventory fixture as an ecosystem proof.

Adapter protocol types and process ownership are under
`src/ucf/adapter_protocol/`. `Method.DISCOVER` requires
`org.ucf.adapter.discovery`; `Method.MAP` requires
`org.ucf.adapter.mapping`. Both can carry independently versioned
`AdapterPayload` values. The core must continue to communicate only through
those serialized types.

Behavior IR models/codecs live under `src/ucf/ir/models.py`,
`src/ucf/ir/codec.py`, and `src/ucf/ir/validation.py`. Trust records and exact
claim predicates are in `src/ucf/ir/trust_models.py` and
`src/ucf/ir/trust_validation.py`. Trust IR requires an exact behavior document
digest and entity reference. Existing trust versions and claim semantics are
accepted dependencies, not convenient containers to loosen.

The historical Python-only scaffold scanner is
`src/ucf/scaffold/scanner.py`. It may be measured as an alternative but must
not become a core import in the new workflow. Python/framework recognition
belongs in a standalone fixture adapter under `tests/fixtures/adapters/` until
later ecosystem packaging work selects a production adapter distribution.

New language-neutral onboarding models should use a dedicated package such as
`src/ucf/onboarding/` only after the foundational experiment demonstrates the
boundary. Generated exact schemas belong under `src/ucf/schemas/` and package
assets must be enforced by `tools/package_contract.py`.

## Plan of Work

First create a representative legacy Python fixture with a runnable application
and its own pre-existing tests. Do not add UCF markers, specs, wrappers, or
dependencies inside it. Record a non-following source manifest and run its
native test/entry path before any onboarding work.

Then run the foundational representation experiment. Attempt the same
candidate through current Trust IR, a provisional Behavior IR, and an exact
generic adapter profile. Record validation outcomes, the point at which intent
would be fabricated, and whether `ucf.map` adds a real adapter-owned semantic
step or merely duplicates human reconciliation. Refine this plan before code.

Define only the closed language-neutral contracts needed by the accepted
vertical slice. Candidate data needs stable content identity, source/inventory
revision, adapter producer and procedure, confidence, proposed use-case/action/
step semantics expressed in neutral Behavior IR vocabulary, and no executable
claim. A decision set needs immutable candidate binding and explicit
`accepted`, `edited`, `rejected`, or `uncertain` disposition with reviewer
input supplied as data. The baseline bundle needs exact input/output digests,
capture context, accepted Behavior/Trust documents, all dispositions, and
coverage/unknown summaries. Unknown fields, duplicates, broken references,
unsupported versions/capabilities, stale decisions, and illegal promotion must
fail atomically.

Build adapter discovery after the contracts. The adapter consumes the exact
inventory revision and recognizes only the checked Python fixture semantics.
Its output must be stable under page/request repetition and include at least
one candidate that will be accepted, one rejected, and one left uncertain.
Core receives only generic serialized candidates.

Implement reconciliation as a deterministic pure transformation over candidate
bytes plus an explicit decision document. Accepted or edited candidates
materialize exact Behavior IR entities; rejected and uncertain candidates
remain in the onboarding bundle and cannot appear as declared intent. Import
post-decision inventory/discovery provenance into Trust IR against the exact
new behavior document. Any `observed`, `declared`, or `mapped` claim must pass
the existing independent predicates. Do not create `tested` evidence unless a
named executable check actually runs against the exact artifact revision;
`verified` remains unavailable.

Finally expose one non-interactive installed command that takes explicit root,
adapter argv, policy, decision input, capture context, and outside-root output.
It validates everything before replacing output, never writes the legacy root,
and produces byte-identical output for identical inputs. Run the native legacy
behavior before and after, compare complete manifests, package exact schemas,
document the review/security/privacy limits, and complete independent audits
plus the full quality profile.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Retain the package-start baseline under
`.artifacts/quality/brn002-start-20260719/`. The first commands are:

    git status --short
    uv run --locked --extra dev pytest -q \
      tests/inventory tests/ir tests/adapters --no-cov

The foundational experiment and fixture-native baseline must stream output to
their own logs before any production edit. After the exact module/test names
are established, keep focused RED/GREEN logs under the same package directory.
Expected package commands will include:

    uv run --locked --extra dev pytest -q tests/onboarding --no-cov
    uv run --locked --extra dev ruff check \
      src/ucf/onboarding tests/onboarding tests/fixtures/adapters tools

Before acceptance:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/brn002-final-20260719
    git diff --check

Whole-file whitespace/conflict scans must include new untracked files. All
long-running commands stream to the terminal and retained logs.

## Validation and Acceptance

BRN-002 is accepted only when:

1. the unchanged legacy Python fixture's native behavior passes before and
   after onboarding and its complete source manifest is byte-identical;
2. inventory, discovery, and any adapter-owned mapping call cross a real
   process boundary with exact selected capabilities, and core imports no
   Python adapter/scanner/framework semantics;
3. repeated identical inputs produce byte-identical candidate and onboarding
   bundles with content-derived identities and explicit source revision,
   adapter version, procedure, capture context, provenance, and confidence;
4. candidates express neutral behavior semantics and cannot be validated as
   declarations, mappings, tested evidence, or verified claims before explicit
   reconciliation;
5. accepted, edited, rejected, and uncertain decisions bind exact candidate
   bytes, reject stale/duplicate/unknown decisions, and remain distinguishable
   in final output;
6. one accepted use case becomes valid exact Behavior IR, while rejected and
   uncertain semantics do not silently enter that document;
7. the post-decision Trust IR preserves observations and declarations,
   reconciles conflicts explicitly, and permits only claim levels supported by
   the exact reproducible evidence;
8. the baseline records current known, rejected, uncertain, and uncovered
   state without calling unknown behavior verified and without implementing
   BRN-003 ratchet policy;
9. malformed profiles, unknown fields, duplicate identities, broken/wrong-kind
   references, unsupported versions/capabilities, stale revisions, adapter
   failures, and late-page failures produce exact atomic errors and no partial
   output;
10. installed schemas/CLI, package contract, affected tests, all seven gates,
    complete diff review, independent contract/process/distribution audit, and
    a clean source-only snapshot pass with claims limited to the measured
    Python fixture.

## Idempotence and Recovery

The legacy root is read-only. Inventory, candidates, decision input, and
capture context are immutable inputs; completed output is written outside the
root through atomic replacement. Identical inputs yield identical canonical
bytes. A changed inventory/candidate revision invalidates decisions rather than
silently rebasing them.

Temporary adapter processes, fixture copies, staging files, and native-test
environments are test- or command-owned and cleaned on failure. A failed
discovery page, invalid decision, invalid Behavior/Trust document, or output
replacement leaves any previous output untouched. Generated schemas are
deterministic and checked against their generators.

## Artifacts and Notes

Foundational evidence belongs under:

- `.artifacts/agents/brn002-foundation/`
- `.artifacts/quality/brn002-start-20260719/`

Add concise RED/GREEN, independent audit, benchmark, and final profile paths as
the work progresses. Do not embed large raw logs in this plan.

## Interfaces and Dependencies

Accepted dependencies:

- inventory profile/capability `1.0.0`;
- adapter protocol `1.0.0` and `ucf.discover`;
- Behavior IR and Trust IR `1.0.0`;
- exact canonical JSON/`IRValue` rules and existing process limits.

The accepted exact profile coordinates are
`urn:ucf:adapter:discovery-request:1.0.0`,
`urn:ucf:adapter:discovery-result:1.0.0`,
`urn:ucf:onboarding:decision-set:1.0.0`, and
`urn:ucf:onboarding:bundle:1.0.0`. They use neutral identifiers and typed
references and cross through `AdapterPayload` without a protocol version
change. `ucf.map` is deliberately not an accepted dependency because human
reconciliation, rather than an adapter-owned mapping, owns candidate
disposition in this package.

No new production dependency, protocol reinterpretation, Behavior/Trust IR
loosening, runtime trace capture, baseline-ratchet enforcement, production
Python ecosystem claim, hosted service, source mutation, interactive-only
review, or `tested`/`verified` promotion is authorized by BRN-002.
