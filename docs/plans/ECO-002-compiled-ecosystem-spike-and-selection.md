# ECO-002 Compiled-Ecosystem Adapter Spike and Selection

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect the current
truth.

## Purpose / Big Picture

After this package, UCF has evidence-backed support for one compiled ecosystem,
selected from comparable Java/Spring and Go spikes rather than preference. The
selected adapter runs as an external compiled process through the accepted
protocol, passes the public conformance kit, and drives one unchanged legacy
quote-order fixture through read-only inventory, candidate discovery, explicit
review/reconciliation, implementation mapping, and one real executable
verification path. The same language-neutral Behavior IR semantics used by the
accepted Python and TypeScript fixtures remain unchanged.

The observable result is a reproducible build plus a clean external workflow
whose source manifest is identical before and after. Public claims name the
exact selected language, framework/library, build tool, operating system,
architecture, adapter version, frozen fixture, and verified path. The result is
not a general claim for the selected ecosystem.

## Foundational Assumption

The root assumption is that the accepted protocol, conformance kit, inventory,
onboarding, implementation-mapping, and execution-verification profiles are
already sufficient for both Java/Spring and Go. Language, framework, build, and
runtime knowledge should fit entirely in external spike processes; the Python
core and Behavior/Trust IR should need no ecosystem-specific change.

The cheapest useful falsification experiment is two deliberately comparable,
artifact-only probes. Each probe uses the same neutral quote-order behavior,
one statically declared real HTTP route, one positive and one invalid request,
strict compilation, native tests, a compiled LF-stdio process, and the same
public adapter initialize/inventory/discovery/map/verify capability shapes.
Before production adapter work, record:

- exact toolchain acquisition, versions, build inputs, dependency graph,
  licenses, cold/warm build time, artifact size, and source mutation;
- protocol/conformance behavior and frame/process constraints;
- exact observable source/build/route/test facts, false candidates, uncovered
  subjects, and evidence spans;
- implementation and maintenance complexity using checked source/manifest
  counts and measured workflow steps;
- current demand indicators from dated primary or clearly attributed sources,
  with demand kept separate from technical suitability.

Alternatives are: select Java/Spring, select Go, or reject the assumption and
first version a genuinely language-neutral profile gap. A profile or IR change
is permitted only after a retained counterexample proves that both honest
external implementations cannot express required evidence. A convenience gap
in one ecosystem is not permission to contaminate the core.

No human decision gate is currently open. The comparison and selection are
explicitly delegated by `ECO-002`; neither spike may add a Python production
dependency. If selection would require a new shipped dependency/license,
reinterpret a public serialized contract, or choose materially different
product semantics, record the evidence and stop at the decision gate defined
by `AGENTS.md`.

## Progress

- [x] 2026-07-19: Complete and independently accept `ECO-001`, then create
  this self-contained ExecPlan before any compiled-ecosystem production change.
- [x] 2026-07-19: Record the pre-edit repository baseline, exact available
  host/container toolchains, and source-only gate evidence under
  `.artifacts/quality/eco002-start-20260719/`. The affected predecessor slice
  passes 465 tests; the host has Docker 29.1.3 and no global Java, Maven,
  Gradle, or Go executable.
- [x] 2026-07-19: Run equal, time-bounded Java/Spring and Go foundation probes; retain all
  comparable measurements, official-source ledger, counterexamples, and
  recommendation before selecting an implementation. Independent replay
  accepts Go 1.26.5/`net/http` for the exact Linux/amd64, CGO-disabled proof
  slice; the root comparison is
  `.artifacts/quality/eco002-start-20260719/selection-comparison.md`.
- [x] 2026-07-19: Freeze the selected unchanged six-file Go legacy fixture and
  retain exact native build/test/HTTP behavior plus a regular-file manifest.
  The manifest is
  `.artifacts/quality/eco002-start-20260719/go-fixture-final-manifest.tsv`,
  SHA-256
  `bbd1f5d9491207d920e4ac2bff82d0e73c572b0764bb7da9530ae43bc31732dd`.
- [x] 2026-07-19: Retain the first focused conformance and inventory REDs,
  implement the minimum compiled control surface and exact read-only
  filesystem inventory, then refactor with 16 affected ecosystem tests,
  Ruff, Go vet/native tests, and unchanged 17/17 conformance green.
- [x] 2026-07-19: Retain the focused Go-fact RED, then classify the frozen
  module with standard-library `go/parser`/`go/token`: one build manifest,
  twelve observed interfaces over eleven distinct half-open spans, three
  native tests, and honest `api_description complete/0`. Two fresh runs
  produce the same valid 51-record snapshot and unchanged source revision.
- [x] 2026-07-19: Retain pagination, detached-route, and failed-restart REDs;
  assemble the same 51-record snapshot at page sizes seven and one; reject
  stale/unknown cursors and source drift without partial evidence; invalidate
  an old run before every new initial scan; and reject malformed, changed,
  unexpectedly exported, or detached-route syntax without writing the target.
  The complete focused inventory file passes 10/10 with zero stderr.
- [x] 2026-07-19: Retain the first real discovery RED and a non-monotonic
  completion-state RED, then emit four bounded contextual candidates from the
  exact completed same-session inventory. Their neutral proposal digests match
  Python and TypeScript; all 12 interfaces are eligible, eight are explicitly
  uncovered, evidence retains exact inventory provenance, and invalid/unbound/
  noncanonical profiles fail with same-session recovery. The focused discovery
  file passes 3/3 and the affected Go ecosystem suite passes 28/28.
- [x] 2026-07-19: Reuse the accepted core-owned reconciliation lifecycle for
  explicit Go review: accept only `QuoteOrder`, reject two out-of-scope
  candidates, retain `LegacyDiscountHint` as uncertain, materialize one
  behavior, and derive a deterministic partial baseline. No rejected or
  uncertain candidate materializes; trust contains only one observed and one
  declared claim, while mapped/tested/verified remain empty. The focused
  bundle/staleness checks pass 2/2 without a production core change.
- [x] 2026-07-19: Retain the exact production-capability and mapping REDs,
  isolate all-family conformance controls behind explicit `--conformance`,
  and implement the existing neutral mapping profile for the sole reviewed
  `QuoteOrder` materialization. Two page sizes produce exact result
  `mapping.1ac553e103d8a887e1fa971788cf6f32784ba81265498de5474353313f3274c6`
  over the same ten candidate evidence refs. Before/incomplete inventory,
  seven malformed or unbound profiles, and live source drift fail explicitly;
  the session recovers only after a fresh current inventory. Mapping still
  creates no mapped/tested/verified claim. The focused mapping file passes
  3/3 and the discovery/reconciliation/mapping slice passes 8/8.
- [x] 2026-07-19: Retain the first exact execution-verification RED and
  implement one real compiled HTTP check without a core/profile change. The
  adapter preflights exact adapter and fixture build metadata/digests, derives
  a versioned canonical environment receipt, launches the unchanged fixture on
  ephemeral IPv4 loopback, performs `POST /quote-order`, validates bounded
  output, and returns one authoritative passed result. Wrong artifacts,
  environment/check/source/mapping bindings, failed checks, source drift,
  timeout, and cancellation fail without partial evidence; only a
  reproducibly passed result projects one `tested` claim and never
  `verified`. Public mapping/verification acceptance passes 15/15 and the full
  current Go ecosystem slice passes 33/33.
- [x] 2026-07-19: Close the real-operation process/resource requirement with
  one bounded FIFO worker, serialized writes, deterministic checkpoints,
  queued and running cancellation, cleanup-before-terminal acknowledgement,
  late-cancel single-terminal behavior, process-group reaping, and session
  reuse. Native runner tests pass 50 consecutive repetitions; Go vet and the
  full package tests remain green. A focused host probe shows the transient
  post-exit `ETXTBSY` inode deny-write window also occurs outside UCF; the
  negative replaces the executable atomically and retains `/proc` proof that
  no adapter-owned child survives.
- [x] 2026-07-19: Complete strict inventory, discovery, explicit review/reconciliation,
  mapping, real verification, deterministic/negative/process/resource tests,
  and prove no claim promotion beyond reproducible evidence.
- [x] 2026-07-19: Integrate the exact Go 1.26.5 toolchain in CI and the
  existing seven-gate graph, then close the installed distribution contract.
  Two wheel builds are byte-identical at SHA-256
  `8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`;
  the Python wheel physically excludes Go source, binaries, and notices. Two
  external lanes produce byte-identical adapter/fixture binaries with exact
  build metadata and zero external modules; the adapter distribution contains
  only its executable and exact upstream Go notices. Installed UCF runs two
  identical 17/17 conformance reports and the full source-to-`tested` workflow.
  CAP-208 documents only this experimental boundary. The post-package
  ecosystem suite passes 49/49, automation 55/55, and Ruff is clean.
- [x] 2026-07-19: Re-open process/resource acceptance after an independent
  audit reproduced two exact-source counterexamples: readiness retained
  524,288 bytes before applying its 65,536-byte limit, and cleanup returned
  after the leader exited while a TERM-ignoring descendant remained. Retained
  REDs now bound incremental readiness without hiding prefetched trailing
  output and require both one leader `Wait` and process-group extinction before
  return. Cleanup uses one absolute TERM-to-KILL deadline, and a cleanup
  failure outranks a cancellation acknowledgement. The event-driven
  cancellation fixture no longer races `/dev/null`. Independent reacceptance
  passes 30/30 adversarial repetitions, 550/550 native test repetitions,
  16/16 verification/resource/projection checks, Go vet, and a stable source
  manifest under
  `.artifacts/agents/eco002-final-process/recheck/`.
- [x] 2026-07-19: Complete final integration and independent acceptance.
  Current-source gates pass 55 automation tests, 1,251 Python tests at 90%
  coverage, Ruff, 113 specifications with zero errors/warnings, reproducible
  packaging, frontend build, and frontend lint under
  `.artifacts/quality/eco002-final-post-process-20260719/`. Independent
  architecture, process, and distribution/claims audits accept the bounded
  result under `.artifacts/agents/eco002-final-architecture/`,
  `.artifacts/agents/eco002-final-process/recheck/`, and
  `.artifacts/agents/eco002-final-distribution-claims/`. Scope review records
  30 added and 9 changed ECO-002 paths with no removed path, and
  `git diff --check` is clean. The physical source-only replay at
  `.artifacts/agents/eco002-clean-source-snapshot/20260719T210814Z-3886818/`
  repeats all seven gates and preserves the exact 723-file source, 12-file Go
  adapter, and 6-file fixture manifests byte-for-byte.

## Surprises & Discoveries

The host preflight immediately after ECO-001 found no `java`, `javac`, `mvn`,
`gradle`, or `go` executable on `PATH`. The equal spike must therefore include
reproducible toolchain acquisition or a checked container/tool wrapper and
must not treat a developer-machine global installation as evidence.

The two artifact-only compiled processes both pass the full 17-case public
conformance profile twice and produce the same canonical report SHA-256
`fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`.
This falsifies the idea that either language needs a protocol or core change
for the accepted control surface. It does not establish inventory, discovery,
mapping, verification, or general ecosystem support.

The first two Spring Boot fat JAR builds from unchanged source differed until
the build manifest fixed `project.build.outputTimestamp`. The retained RED
digests are in `java-jar-a.sha256` and `java-jar-b.sha256`. Two subsequent
offline clean builds of that then-current 171-entry application JAR agreed at
SHA-256
`9501fc00ae63e20b52d675fbf02346fff8b344b738f404a0421f0a6ea2e5b5cb`,
but the protocol source was added later and the current JAR has 173 entries.
The older digest is therefore intermediate evidence, not proof for the current
source. A root `zipinfo` counter-check under
`.artifacts/quality/eco002-start-20260719/` retained the exact two-entry
difference. Two independent offline current-source builds now produce the
same 173-entry, 19,882,182-byte JAR containing `AdapterServer`, SHA-256
`f2b256e1fc01eb5b35959d8d994ff6bd087933fe646d1d9b0be743bfbcedc185`.
The current Go adapter binary reproduced directly from the checksum-verified
official Go 1.26.5 archive and from the pinned container build at SHA-256
`de29c5e8fcfe25057a1a07a1aec5e20f0435aa637727b695a2c974167d360d15`.
Reproducibility remains an explicit build input in both branches, not an
assumed language property.

Comparable compiler-AST discovery is an exact tie: each spike emits four
candidates for one externally observable oracle behavior, giving
TP/FP/FN `1/3/0`, precision `0.250`, recall `1.000`, five minimum review
decisions, eleven distinct evidence spans, and one explicit ambiguity. This
corrected measurement prevents either fixture-shaped analyzer from being
presented as false-candidate-free or as general ecosystem discovery.

The accepted implementation-evidence profile can distinguish exact compiled
executions without a contract change. The selected adapter must retain a
versioned canonical execution receipt whose digest is the
`ExecutionEnvironment.revision`, bind both executable digests plus the exact
toolchain/build/dependency/runtime/source coordinates, and reject a requested
receipt that does not match the artifacts it actually launches. This provides
traceability, not authenticity or independent attestation.

The frozen production fixture is intentionally six regular files and four
directories. It builds and tests with the checksum-verified Go 1.26.5 archive,
serves one literal `POST /quote-order` route on an ephemeral IPv4 loopback
address, emits one readiness line, exits cleanly on termination, and preserves
the exact source manifest before and after. The adapter and fixture build from
separate closed copies with zero external Go modules and byte-identical
repeated executables.

The first real `ucf.inventory` counterexample failed only with
`adapter_failure/operation_failed: unsupported conformance control payload`.
The minimum GREEN keeps the Python core unchanged and accepts only the exact
fixture subject, root, complete canonical fact-kind request, and empty ignore
policy. A confined `os.Root` scan rejects an unexpected path, symlink,
non-regular entry, type mismatch, oversized file, or observed mutation. The
valid snapshot contains ten provenance records, ten repository entries, and
four classification error diagnostics; repository coverage alone is complete.
The exact source revision is
`8c95d059aef410657d42e4544d34935c5f422efa9394f1242ee858e02a1c3ff8`.
This proves read-only filesystem observation, not Go classification or
pagination. The next RED then proved the four non-repository fact kinds were
still `partial/0`. The accepted syntax classifier consumes only the verified
bytes retained by the scan, rejects a different module/export/route/request/
response/test shape, emits exact raw-declaration digests and half-open
`go/token` spans, and leaves the source revision unchanged. It reports no API
description because this fixture has no separate API-description artifact;
the literal route, handler, two request fields, three response fields, response
write, and four candidate functions remain observed adapter-owned interface
facts. At that stopping point, pagination and cursor/process negatives were
the next RED behaviors.
The pagination RED initially exposed a typed-nil encoding error: Go encoded the
first page's absent request cursor as an empty record instead of `null`. The
corrected same-session run returns the identical snapshot at page sizes seven
and one. Independent adversarial replay then found that a failed new initial
filesystem scan retained the previous run; moving invalidation before any
filesystem access closes that state leak. A detached route registered on a
mux that `Handler` does not return was also initially misclassified as
observed; route evidence now requires the registration receiver to be the
returned handler object.

The cheapest real-inventory cancellation experiment falsified the assumption
that the current synchronous Go serve loop is sufficient. It completes an
operation before reading the next stdin frame, so the accepted control
`block` case proves cancellation wire/correlation only, not cooperative
inventory cancellation. The frozen fixture has no honest deterministic
long-running inventory operation; adding a delay or hidden blocking branch
would manufacture evidence. Before ECO-002 process/resource acceptance, the
adapter therefore needs a general asynchronous real-operation runner,
serialized output, per-request cancellation state, and bounded checkpoints.
Inventory cancellation may be accepted compositionally with deterministic
checkpoint tests and real verification cleanup; no mid-scan inventory claim
exists yet.

The first real `ucf.discover` request then failed only at the unimplemented Go
operation boundary. The existing onboarding profile expresses the same four
function proposals without a core or IR change. `QuoteOrder`, `FormatReceipt`,
`NormalizeCoupon`, and `LegacyDiscountHint` have the exact accepted
cross-language semantic digests, while their contextual IDs differ because
the Go subjects, evidence, producer, procedure, confidence basis, and inventory
binding differ. Coverage is honestly partial: every one of the twelve public
interfaces is eligible, four are candidate subjects, and the route, handler,
request fields, response fields, and response-write fact remain eight explicit
uncovered subjects while also contextualizing `QuoteOrder`. A replay of an
earlier valid page after terminal inventory initially downgraded the cached
run; completion is now monotonic, so deterministic page replay cannot revoke a
completed snapshot. Valid discovery before inventory or before a terminal page
fails, stale/forged/binding-only/unknown/noncanonical profiles fail, and the
same session recovers to the exact result.

The existing core reconciliation lifecycle also accepts the Go evidence
without an ecosystem branch. A deterministic four-decision set makes review
effort explicit: one accepted, two rejected, one uncertain, zero edited. Only
the accepted `QuoteOrder` proposal materializes, while the eight uncovered
interfaces remain in the baseline and neither rejection nor uncertainty is
presented as behavior truth. A stale candidate reference fails before bundle
construction. The resulting trust graph contains observed and declared claims
only; mapping, testing, and verification remain later evidence transitions.

An independent discovery audit identified a package-completion risk outside
the accepted discovery output: the current default compiled process negotiates
all five protocol-family capabilities so the public conformance control
profile can exercise every method, even though production mapping and
verification are not implemented yet and no production generation profile is
planned in ECO-002. A conformance echo is not a product capability claim.
Before distribution acceptance, default negotiation must advertise only real
product operations; the all-family control surface must be isolated to an
explicit conformance mode (or an equally testable truthful boundary) without
changing the canonical conformance result.

The capability counterexample is now closed at the process boundary. Default
mode negotiates only implemented product operations; the full five-family echo
surface exists only under explicit `--conformance`. Mapping then reuses the
accepted closed neutral request/result profile without adding environment to
the mapping stage or hard-coding review state in the adapter. The adapter
requires a completed live inventory, validates the exact supported neutral
Behavior graph and target, and emits the same ten inventory refs selected by
discovery through one shared evidence function. A changed live source clears
the cached run before any result; restoring bytes alone cannot resurrect stale
evidence. The exact mapping ID above is stable across page sizes one and seven.
The post-mapping public conformance replay remains required before package
acceptance.

The real verification counterexample also closes without a shared-contract
change. The adapter binds its own and the fixture executable's exact Go-build
metadata, SHA-256 digests, source revision, toolchain, build mode,
architecture, CGO setting, runtime, and loopback boundary into the canonical
`ExecutionEnvironment` revision. It launches the unchanged server as an owned
process group, waits for one bounded readiness record, performs the exact
typed quote-order check, and reaps the group on every terminal path. A passed
adapter-attested check can derive one `tested` claim; failed, cancelled, stale,
or mismatched evidence cannot project a successor, and no result derives
`verified`.

The asynchronous runner foundation is now implemented once for all real
operations rather than as a verification-only timing branch. One FIFO worker
owns request execution, the read loop remains able to receive cancellation,
writes are serialized, queued work is removable, running work acknowledges
cancellation only after handler cleanup, and terminal completion is recorded
once. A 50-repeat native test and real descendant-process cancellation close
the intended invariants. During negative replay, overwriting a just-executed
binary intermittently returned Linux `ETXTBSY` after the child was already
reaped. A narrow `strace` plus an independent non-UCF reproducer measured the
same delayed inode release; atomic same-directory replacement removes that
host race while preserving the artifact-drift negative and `/proc` cleanup
assertion.

The first final process audit correctly falsified the initial cleanup claim.
`stopVerificationProcess` returned as soon as the fixture leader's `Wait`
completed, even when a TERM-ignoring descendant still occupied the owned
process group, and `ReadBytes` accumulated an entire unterminated readiness
stream before checking its limit. The focused REDs are
`go-process-boundaries-red.log` and
`go-cancel-cleanup-precedence-red.log`. Incremental `ReadSlice` handling now
retains at most 65,536 bytes while leaving post-newline bytes in the shared
reader. Cleanup observes leader completion and group extinction separately,
escalates within one absolute deadline, consumes `Wait` once, and cannot report
successful cancellation after cleanup failure. Independent exact-source
replay inverted both counterexamples without sleeps, skip, or fixture delay.

The final source-only replay contains 723 regular source files rather than the
earlier scope-review count of 726 because the normalized clean-copy policy
counts only retained regular source inputs and excludes generated/cache state.
Its before/after payload is byte-identical at SHA-256
`c6c8303c0ac8e250edddc11b25ac0a383b9208b8878bdbf009cee981f9955150`.
The same replay retains the unresolved web dependency audit signal from
`npm ci`: 2 low, 3 moderate, and 5 high findings. Green build and lint do not
dispose those findings; they remain explicit `REL-002` security work.

The distribution foundation now has a retained full installed acceptance.
Two fresh closed adapter/fixture copies use the exact Go 1.26.5 toolchain with
local toolchain selection, disabled network module resolution, external
caches, strict native module/vet/test checks, deterministic flags, and exact
`go version -m` metadata. Adapter and fixture executables are byte-identical
across lanes; the standalone adapter directory contains only the executable
and the exact upstream Go `LICENSE`/`PATENTS`, while the verification fixture
binary remains a test artifact. The first installed driver replay exposed only
an incorrect local assertion that placed the canonical manifest reference
last; the adapter had correctly emitted manifest-first canonical ordering.
The corrected driver consumes the unmodified result and passes two page sizes
through exact 1/2/1 review, mapping, real verification, and tested-only
projection. Stable inputs and pre-execution artifacts are byte-identical;
runtime result/projection timestamps remain truthful whole-second capture
facts and are validated canonically rather than replaced with a fake clock.

## Decision Log

- **2026-07-19 — compare equivalent executable slices before selecting a
  compiled ecosystem.** Author: root agent. Both spikes must implement the
  same behavior and evidence shapes, run on the same host boundary, and report
  the same measurements. Framework popularity, familiarity, or an easier
  hand-written parser is not selection evidence.

- **2026-07-19 — keep spike toolchains and generated output outside the
  repository source tree.** Author: root agent. Toolchains, dependency caches,
  compiled classes/binaries, and disposable probes belong in bounded
  `.artifacts` or temporary workspaces. Only the selected frozen fixture,
  adapter sources, exact build manifests, tests, and documentation may become
  checked source after the selection is recorded.

- **2026-07-19 — the accepted neutral protocol remains sufficient for both
  foundation probes.** Author: root agent. Java/Spring and Go each pass all 17
  public conformance cases twice with byte-identical canonical reports and zero
  adapter stderr. No shared IR, implementation-evidence profile, Python
  dependency, or language branch is justified by the wire experiment. The
  ecosystem selection remains open until comparable discovery, dependency,
  distribution, and runtime measurements are complete.

- **2026-07-19 — select Go 1.26.5 and standard-library `net/http` for the
  compiled proof.** Author: root agent. Both current candidates are
  reproducible and conformant, and their measured discovery quality and review
  burden tie exactly. Go then wins the deterministic decision rule through one
  root module, zero external modules, a static CGO-disabled executable, a
  12,148,403-byte prototype payload, and the substantially smaller
  distribution, license-disposition, and update surface. The comparable 2025
  professional-language demand question favors Java, but demand is separate
  from technical suitability and does not reverse those closure costs.
  Independent acceptance is
  `.artifacts/agents/eco002-selection-acceptance/report.md`, SHA-256
  `58ad875d31947e2336fe8bd46776da7c674e358f8cfd2d0a7fe95cc3f96b2e2c`.
  The supported proof remains exactly Linux/amd64, `CGO_ENABLED=0`, literal
  route registration, and one frozen fixture; it is not broad Go support.

- **2026-07-19 — retain implementation-evidence profile `1.0.0`.** Author:
  root agent. A four-artifact counterprobe proves the current
  `ExecutionEnvironment` coordinate distinguishes compiled artifacts while
  preserving the mapped source revision. The production adapter will bind a
  retained canonical execution receipt and enforce artifact mismatch
  negatives. A richer component-level staleness model belongs to `VER-002`
  unless a real counterexample opens a public-contract decision gate.

- **2026-07-19 — keep the first production inventory slice fixture-exact.**
  Author: root agent. The cheapest accepted implementation uses the existing
  neutral inventory profile and a closed `os.Root` scan of the frozen source
  copy. It reports unimplemented build/interface/API/test classification as
  four error-backed partial coverages instead of claiming absent facts are
  complete. A generic Go walker or core branch is not justified by this
  acceptance behavior. Classification, pagination, cancellation, and stale
  cursor behavior are separate RED/GREEN slices.

- **2026-07-19 — do not simulate inventory cancellation.** Author: root
  agent. Read-only review and a protocol/client replay show that the current
  synchronous frame loop cannot receive `ucf.cancel` while real inventory is
  executing, while the exact bounded fixture provides no deterministic
  naturally long scan. Timing races, padded inputs, sleeps, and control-only
  branches would not prove the user outcome. ECO-002 will introduce one
  adapter-wide asynchronous real-operation boundary during its required
  process/resource slice, with serialized writes, cancellation checkpoints,
  cleanup-before-acknowledgement, and session reuse. This changes no public
  protocol or neutral IR and opens no human decision gate.

- **2026-07-19 — separate product capabilities from conformance controls.**
  Author: root agent. Default negotiation advertises only operations backed by
  production profiles; `--conformance` preserves the public kit's all-family
  control surface. Mapping is now a truthful default capability, while
  generation and verification remain unavailable until real implementations
  exist. This avoids treating echo behavior as product support without
  changing the protocol or canonical conformance contract.

- **2026-07-19 — retain neutral mapping `1.0.0` for Go.** Author: root agent.
  The request already separates reviewed Behavior intent, current inventory,
  onboarding binding, and adapter procedure. The adapter can verify the exact
  graph, target, live source, and deterministic source refs; the core, which
  owns the full bundle, verifies review/context binding. Adding an execution
  environment to mapping or hard-coding one onboarding digest would violate
  that boundary and is not justified by the retained counterexample.

- **2026-07-19 — retain neutral execution verification `1.0.0` and bind an
  exact Go execution receipt.** Author: root agent. The existing profile
  already binds reviewed behavior, mapping, source, environment, procedure,
  typed inputs, and expected outputs. The selected adapter therefore derives
  the environment revision from exact adapter/fixture digests and build/runtime
  coordinates and performs one real loopback HTTP check. This is reproducible
  adapter-attested evidence, not authenticity, independent attestation, formal
  verification, or broad Go support.

- **2026-07-19 — use one asynchronous FIFO runner for real adapter
  operations.** Author: root agent. The synchronous frame loop cannot observe
  cancellation while a real operation runs. A single worker preserves
  deterministic stateful inventory ordering while allowing the read loop to
  cancel queued/running work; terminal acknowledgement follows cleanup and is
  emitted once. Hidden sleeps, padded fixtures, and control-only cancellation
  are not accepted as real-operation evidence.

- **2026-07-19 — distribute the Go adapter separately from the Python
  wheel.** Author: root agent. The selected static binary has zero external Go
  modules but includes the Go runtime, standard library, and GOROOT-vendored
  code. Its exact distribution therefore carries the upstream Go
  `LICENSE`/`PATENTS`; the Python wheel physically excludes Go source,
  binaries, and notices. This does not decide or claim a general UCF project
  license, which remains a release-package concern.

- **2026-07-19 — accept ECO-002 at the exact experimental boundary.**
  Author: root agent. Current-source and physical clean-source gates,
  independent architecture/process/distribution/claims audits, scope review,
  and immutable fixture/distribution evidence all pass. The accepted result is
  Go 1.26.5, standard-library `net/http`, Linux/amd64, `GOAMD64=v1`,
  `CGO_ENABLED=0`, one frozen six-file fixture, one literal returned
  `ServeMux`, and one adapter-attested `tested` path. Java/Spring remains only
  a comparable retained spike. The web dependency findings remain release
  debt and do not widen or weaken this bounded claim.

## Outcomes & Retrospective

ECO-002 is verified. Comparable Java/Spring and Go spikes proved the accepted
protocol and neutral profiles sufficient, and measured discovery quality tied
at TP/FP/FN `1/3/0`; the smaller deterministic distribution, dependency,
update, and license-disposition surface selected Go 1.26.5 with the standard
library. The selected external adapter now completes exact read-only
inventory, four bounded candidates, explicit 1/2/1 review, one materialized
behavior, exact mapping, real loopback verification, and passed-only `tested`
projection on an unchanged six-file fixture. Product and conformance
capabilities are separate, process cancellation waits for cleanup and whole
process-group extinction, and readiness is incrementally bounded.

Two closed build lanes reproduce the adapter and fixture binaries; installed
UCF runs canonical conformance and the complete compiled workflow while the
Python wheel contains no Go implementation or notice asset. CAP-208 states
only the exact Linux/amd64, CGO-disabled, single-fixture boundary. All seven
current-source and physical clean-source gates pass, all three final
independent audit tracks accept the result, scope/diff review is clean, and
the normalized 723-file snapshot remains byte-identical. Remaining frontend
dependency findings are explicitly retained for REL-002 rather than hidden.
Java/Spring remains a comparable counterprobe, not a supported adapter.

## Context and Orientation

The serialized process boundary is `src/ucf/adapter_protocol/`; the installed
black-box conformance kit and runner are in
`src/ucf/adapter_conformance/` and documented in
`docs/ADAPTER_CONFORMANCE.md`. Neutral observed inventory lives in
`src/ucf/inventory/`; candidate review and reconciliation live in
`src/ucf/onboarding/`; exact source mapping and executable verification
profiles live in `src/ucf/implementation_evidence/`.

The accepted Python legacy comparison is
`tests/fixtures/brownfield/python_legacy_quote/`. The accepted external
TypeScript/Fastify fixture and adapter are
`tests/fixtures/brownfield/typescript_fastify_legacy_quote/` and
`adapters/typescript-fastify/`. ECO-002 reuses their neutral quote-order
Behavior identities and semantics, not their language, route, package-manager,
or implementation-specific evidence records.

The selected compiled adapter should live under a new exact ecosystem path
below `adapters/`. Its frozen fixture should live below
`tests/fixtures/brownfield/`, focused adapter tests beside the adapter, and
cross-language acceptance below `tests/ecosystems/`. Spike-only sources and
toolchains are evidence artifacts, not production source.

## Plan of Work

First, revalidate the foundation. Capture `git status`, the exact host and
container/tool-wrapper options, a focused predecessor baseline, and official
version/support/licensing sources. Build two equal disposable fixtures and
compiled stdio probes. Run their native behavior and a minimal protocol
exchange, then publish a comparison table whose rows have identical
definitions and raw evidence. Independently replay the measurements and record
the selection in this plan.

Second, freeze only the selected fixture before adapter implementation. Hash
every regular source/build/test input and retain native compile/test plus real
HTTP results. Write one focused ecosystem acceptance that fails because the
selected adapter does not exist or lacks the required operation. Implement the
smallest external compiled process that passes the public conformance kit
without a Python import or ecosystem branch.

Third, add one acceptance behavior at a time: exact read-only inventory,
bounded deterministic discovery candidates, explicit review and
materialization of the shared neutral behavior, exact implementation mapping,
then real executable verification. Every result must bind source revision,
producer/capability, adapter version, environment, procedure, and check.
Wrong versions, unsupported layouts/capabilities, stale or forged references,
malformed/oversized frames, stderr, timeout, cancellation, partial output, and
source mutation must fail explicitly.

Finally, prove reproducible clean builds and installed-wheel execution from
outside the checkout. Integrate the selected adapter and fixture into the
existing gate graph without relying on generated checkout state. Publish the
exact compatibility/limitation row and comparison evidence, run all gates and
diff review, and obtain independent contract/process/distribution/claims plus
physical clean-source acceptance.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream each command to the terminal and
a named file under `.artifacts/quality/eco002-start-20260719/` or a dedicated
`.artifacts/agents/eco002-*/` audit directory.

Record the baseline:

    git status --short
    command -v java javac mvn gradle go docker podman
    uv run --locked --extra dev pytest -q \
      tests/adapters tests/inventory tests/onboarding \
      tests/implementation_evidence tests/ecosystems --no-cov
    uv run --locked --extra dev ruff check src tests tools

The foundation probe must record exact commands and equivalent results for
both candidates. Do not use floating package coordinates, implicit `latest`,
unlocked wrapper downloads, pre-existing global caches as the only evidence,
or hand-edit generated output. Capture elapsed time and peak resource data with
the same measurement method.

For each selected-adapter behavior, retain the focused RED and intended error,
then the smallest GREEN and refactor replay. Before completion run:

    <selected exact locked native build and tests>
    <selected external adapter tests and public conformance twice>
    uv run --locked --extra dev pytest -q tests/ecosystems --no-cov
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/eco002-final-20260719
    git diff --check

## Validation and Acceptance

ECO-002 is accepted only when executable evidence proves:

1. Java/Spring and Go were evaluated with the same behavior, protocol surface,
   measurement definitions, and host boundary; the selection follows recorded
   complexity, build integration, discovery quality, and demand evidence;
2. the selected adapter is an external compiled process, passes the public
   conformance kit twice with identical canonical reports, and no Python core
   module imports or branches on its language/framework/build/runtime;
3. an unchanged selected legacy fixture completes inventory, deterministic
   candidate discovery, explicit review/reconciliation, exact mapping, and one
   real executable verification while sharing the neutral Behavior IR used by
   Python and TypeScript;
4. inventory and candidates preserve provenance/confidence and exact source
   spans; false candidates and review effort are measured rather than hidden;
5. unsupported capabilities/layouts/versions, duplicate/broken/stale/forged
   references, malformed/oversized frames, stderr, timeouts, cancellation, and
   cleanup fail without partial evidence or source mutation;
6. only a reproducibly passed check can derive `tested`; no adapter result is
   presented as independent attestation, formal verification, or broad
   ecosystem support;
7. exact toolchain/build inputs reproduce from a source-only environment, the
   selected distribution and installed-wheel workflow run outside the source
   tree, and native fixture inputs remain byte-identical;
8. documentation and the capability matrix state exact measured scope,
   compatibility, licensing/support limits, and comparison evidence;
9. affected tests, all canonical gates, complete diff review, independent
   audits, and a physical clean-source replay are green.

No acceptance may use skip, xfail, warning-only enforcement, path exclusion,
baseline reset, fixture rewriting, checked generated binaries, in-process
Python adapters, or manually repaired generated output.

## Idempotence and Recovery

Both foundation probes are disposable and rerunnable from exact manifests.
Toolchains and caches must live outside source and may be removed without
changing repository inputs. Freeze manifests before any mutable native build;
perform builds in copied temporary workspaces and compare before/after source
manifests. Adapter outputs are canonical and written only after complete
validation. Failed process work must terminate owned process groups and leave
no partial evidence file.

If a spike fails, preserve its command, toolchain coordinates, source,
stderr/exit class, measurements, and cleanup result. Do not rewrite the failed
candidate into apparent parity. If a public-contract, dependency/license,
irreversible data, security, or materially different semantic choice appears,
record options, consequences, evidence, and recommendation here and set
`docs/automation/STATE.md` to `blocked_on_decision`.

## Artifacts and Notes

Starting evidence belongs under:

- `.artifacts/quality/eco002-start-20260719/`;
- `.artifacts/agents/eco002-java-spring-spike/`;
- `.artifacts/agents/eco002-go-spike/`;
- `.artifacts/agents/eco002-selection-audit/`.

Retain concise official-source notes, exact toolchain and dependency ledgers,
source manifests, build/native-test/protocol transcripts, comparison metrics,
RED/GREEN logs, deterministic report digests, negative/process evidence, and
final gate/audit summaries. Do not retain credentials, dependency caches,
toolchain archives, compiled workspaces, or raw unbounded logs as source.

## Interfaces and Dependencies

Accepted upstream contracts remain at version `1.0.0`:

- adapter protocol and conformance kit;
- Behavior IR and Trust IR;
- inventory, onboarding, mapping, and execution-verification profiles;
- canonical JSON, strict closed decoding, exact identities, bounded process
  lifecycle, and atomic output conventions.

The foundation comparison will fix exact Java/JDK, Spring, build-tool, Go,
operating-system, and architecture coordinates before production selection.
No compiled-ecosystem implementation may enter `src/ucf`; the core launches an
adapter only through argv and serialized frames. Any accepted profile addition
must remain language-, framework-, build-tool-, runtime-, and
transport-neutral, with explicit compatibility/version evidence.
