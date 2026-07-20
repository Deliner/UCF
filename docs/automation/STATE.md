---
schema_version: 1
project: ucf
target_state: docs/automation/TARGET_STATE.md
active_work_package: REL-001
active_exec_plan: docs/plans/REL-001-end-to-end-adoption-benchmark.md
status: blocked_on_decision
last_updated: 2026-07-20
---

# Automation handoff state

`VER-002` is independently verified. `REL-001` is blocked on a genuine public-
semantics decision: accepted TypeScript and Go discovery is honestly partial,
while Ratchet `1.0.0` forbids establishing or advancing a partial baseline.
Completing the three-fixture workflow requires a versioned coverage-debt
contract or an explicit narrowing of the requested product outcome.

## Resume instruction

Invoke the repository skill with:

    Use $ucf-ultrawork. Resume the active work package from
    docs/automation/STATE.md and continue until it is verified or a decision
    gate is reached.

For a long-running Codex session, set the same objective with `/goal` if that
surface supports goals. The skill name is repository-defined; `ultrawork` is
not an official Codex execution mode.

## Current truth

- Active package: `REL-001`
- Current plan:
  `docs/plans/REL-001-end-to-end-adoption-benchmark.md`
- Decision gate: choose how partial discovery becomes enforceable legacy debt.
  Root recommends a parallel Ratchet `2.0.0` dual ledger that preserves v1,
  keeps unresolved coverage separate from Behavior/claims, permits only exact
  inherited uncertainty, blocks new/changed/reintroduced uncertainty, and
  protects resolved debt. Alternatives and consequences are recorded in the
  active ExecPlan and
  `.artifacts/agents/rel001-foundation/decision.md`.
- REL-001 foundation evidence passes 480 focused tests plus Ruff under
  `.artifacts/quality/rel001-start-20260720/`. Python completes ratchet.
  TypeScript and Go complete native checks, conformance, onboarding, mapping,
  real HTTP/CLI/event verification, tested projection, and fresh evidence, but
  reproducibly fail ratchet establishment with
  `incomplete_coverage` at `$.source_assessment.coverage`.
- VER-002 is verified. Exact evidence envelope/assessment `1.0.0` resources,
  selective staleness, passed-only refresh, strict contextual replay, installed
  CLI/schema assets, and no-`verified` promotion pass independent contract,
  CLI/documentation, packaging, and final acceptance reviews.
- VER-002 final local evidence is
  `.artifacts/quality/20260720T155500Z/`: 75 automation tests, 1,880 Python
  tests at 90% coverage, Ruff, 113 specifications with zero errors/warnings,
  installed packaging, frontend build, and frontend lint all pass. The
  reproducible wheel SHA-256 is
  `7311760bf249ad195dbb30ad563cafeddbfee77921851ba5a154ea91ef9cb2ec`.
- VER-002 physical clean-source acceptance is
  `.artifacts/agents/ver002-clean-source-snapshot/20260720T160959Z-ver002/`.
  Fresh locked installs repeat all seven gates from 996 regular source files;
  checkout and snapshot bytes remain identical before/after at manifest
  SHA-256
  `d392c673ca85ff30319acd13e674136f43e7c0c8dcd0854ea7ad10cefbc83e1c`.
- VER-001 is verified. Its final local profile passes 71 automation and 1,713
  Python tests at 89% coverage plus all other gates under
  `.artifacts/quality/ver001-final3-20260720/`; the reproducible wheel SHA-256
  is
  `d98f3fcfd6b8ce7493e98b10a2dcd85a35d4a98dbc74da5014e027538cb9b91a`.
- VER-001 physical clean-source acceptance is
  `.artifacts/agents/ver001-clean-source-snapshot/20260720T132838Z-ver001/`.
  Fresh locked installs repeat all seven gates from 937 regular source files,
  and checkout/snapshot manifests stay byte-identical at SHA-256
  `52013a5c0957410a1c8819a14c9314415015a55d19150d54aedac98f0a552712`.
- VER-002 pre-edit baseline passes 254 implementation-evidence/IR/drift tests
  and scoped Ruff under
  `.artifacts/quality/ver002-start-20260720/`.
- VER-002 root and three independent foundation probes reproduce the same
  coarse-comparison defect: historical Trust cannot see target-source drift,
  while replacing whole inventory/Behavior identities invalidates unrelated
  changes. The two-seed root output is byte-identical at SHA-256
  `04a7d397ed3a3b0ad771f989b18035edab7cbffaf0a7166a1540d976695f1caa`.
- VER-002 selects an additive evidence envelope and freshness assessment
  `1.0.0`, with core-derived reviewed Behavior, mapping, and transitive source
  projections plus exact execution coordinates. Behavior IR, Trust IR,
  adapter protocol, and implementation-evidence versions do not change; no
  decision gate is reached.
- VER-001 foundation selected additive generation request/result `1.0.0`
  resources over protocol and Behavior IR `1.0.0`, with all Python/pytest
  semantics confined to the external adapter. No protocol or Behavior IR
  version change and no human decision gate were required.
- VER-001 implementation currently passes 99 generation/CLI tests and scoped
  Ruff. Exact schemas, 25 wire resources, deterministic two-seed generation,
  clean pytest execution, source/no-op revalidation, generated-only ownership,
  and stable-inode publication are retained under
  `.artifacts/quality/ver001-start-20260720/`.
- Independent contract and publication audits found noncanonical identity,
  frame-budget, path-alias, outbound-revalidation, wrapper-direction, and
  filesystem substitution/post-commit/exact-tree/staged-content gaps. All
  reported findings have focused retained regressions. The contract,
  publication consistency, and dynamic publication rechecks ACCEPT;
  post-commit cleanup/durability uncertainty is explicit without unsafe
  rollback or unverified recursive cleanup.
- The post-hardening all-profile snapshot passes 71 automation and 1,713
  Python tests at 89% coverage, all other gates, and reproducible wheel
  SHA-256
  `d98f3fcfd6b8ce7493e98b10a2dcd85a35d4a98dbc74da5014e027538cb9b91a`
  under `.artifacts/quality/ver001-final3-20260720/`. This run includes the
  final exact staged-content and durability-ordering fixes.
- Verified dependencies: `FND-001`, `FND-002`, `FND-003`, `IR-001`,
  `IR-002`, `ADP-001`, `ADP-002`, `BRN-001`, `BRN-002`, `BRN-003`,
  `BRN-004`, `ECO-001`, `ECO-002`, `ECO-003`, `CHG-001`, `CHG-002`,
  `VER-001`, and `VER-002`.
- BRN-003 foundation accepted: root and independent probes reject
  whole-document/file-status touch and accept stable
  `(subject_uri, root kind, root ID)` identity with separate versioned semantic
  and rename-neutral observed projections. Four top-level documents (Policy,
  Assessment, Baseline, EvaluationReport), nested WeakeningDelta, protected
  resolutions, and `establish/evaluate/advance` are recorded in the plan. A
  real CLI counter-probe selects existing exit classes `0`/`1`/`3`.
- BRN-003 pre-edit baseline: 216 onboarding/IR/CLI/claim tests pass under
  `.artifacts/quality/brn003-start-20260719/focused-baseline.log`. Foundation
  evidence is under `.artifacts/quality/brn003-start-20260719/` and
  `.artifacts/agents/brn003-foundation/`.
- BRN-003 accepted implementation: four exact closed `1.0.0`
  documents/schemas, stable semantic/observed touch projection, pure
  evaluation, immutable protected successors, strict contextual validation,
  and installed atomic `establish`/`evaluate`/`advance`. Any otherwise
  non-regressing partial assessment is inconclusive; definite regressions fail.
  Path and same-file aliases are rejected before output replacement.
- BRN-003 final local profile: all seven gates pass under
  `.artifacts/quality/brn003-final3-20260719/` with 42 automation tests, 989
  Python tests at 89% coverage, clean Ruff, 113 specs with zero errors and
  warnings, installed packaging, frontend build, and frontend lint. The final
  affected slice has 138 passing tests and `git diff --check` is clean.
- BRN-003 independent acceptance: contract and CLI/security audits pass 72
  core and 13 CLI tests plus adversarial, partial-coverage, filesystem-alias,
  contextual-forgery, and hash-seed probes. See
  `.artifacts/agents/brn003-final-contract/` and
  `.artifacts/agents/brn003-final-cli-security/`.
- BRN-003 clean distribution: a newly installed physical 602-file source-only
  snapshot repeats all seven gates and stays byte-identical at manifest
  SHA-256
  `7b649f66bb7f90fd3caf7832a1e15e9a68ad15ae01ef1b8e119b37fc2f9d7cdd`.
  Three wheel builds agree at SHA-256
  `3f2d752ac588b5ba5f20ef9ba1d31714f2d8dbd58a4a5b1b0d5e4ff3a045501d`;
  exactly 16 schemas install, the external adapter remains outside the wheel,
  and the unchanged fixture passes three native checks before and after. See
  `.artifacts/agents/brn003-clean-distribution/`.
- BRN-004 foundation is accepted with no production dependency or stable
  protocol/IR change. Root replay and three independent probes accept existing
  `ucf.verify` plus `AdapterPayload` as transport and reject a bare Trust IR
  result as insufficiently strict. The selected additive
  `RuntimeEvidenceDocument 1.0.0` binds exact environment, sampling, policy,
  procedure, source, adapter, and Behavior coordinates; core then derives only
  `SourceRecord` and `ObservedFact`. The dedicated client requires both
  verification and runtime-evidence capabilities.
- BRN-004 privacy boundary is fixed: recorded-only explicit invocation, exact
  allowlist, reject-only selected unsafe values, partial sampling, no raw
  recording in canonical output, zero-retained adapter stderr, category/code
  diagnostics, typed policy rejection, and no declaration/mapping/tested/
  verified promotion. The claim is limited to values not retained, persisted,
  or emitted by UCF; adapters are not sandboxed.
- BRN-004 pre-edit baseline passes 474 focused tests. Root foundation replay
  produced canonical Trust SHA-256
  `947051f01cffcc1e9822de1eadb9c9b65cf59971b529ecd9c5593fab5323acb7`;
  the strict counter-model produced
  `a20cdace4de04229a2c6777c55f0ac51edf6c8d4891f7de830e7c91f18a0fff1`.
  Evidence is under `.artifacts/quality/brn004-start-20260719/` and
  `.artifacts/agents/brn004-foundation/`.
- BRN-004 contract/transaction milestone is green: four exact closed generated
  profile schemas, strict codecs and contextual validation, authoritative
  accepted/rejected results, pure observed-only Trust projection, a
  two-capability zero-retained-stderr client, and an external fixture adapter
  now exist. The explicit atomic CLI passes repeatability, input/output safety,
  typed rejection, and sanitized peer/stderr behavior. The refactored
  runtime/process/CLI slice passes 106 tests; retained CLI RED/GREEN evidence
  is under `.artifacts/quality/brn004-start-20260719/`.
- BRN-004 privacy hardening is green after independent audit: singleton and
  multi-rule unsafe selection return typed sorted rejection codes, growing
  recording reads stop at the byte limit plus one detection byte, malformed/
  oversized inputs fail safely, cancellation and timeout reap the child, and
  two hash seeds produce identical sanitized authoritative result plus
  observed-only projection. The latest runtime/process/CLI slice passes 113
  tests and focused boundary coverage passes 28.
- BRN-004 distribution/claim implementation is green: the package contract
  expects exactly 20 schemas, keeps the recording/reference adapter and
  forbidden fixture values outside the wheel, installs into a clean
  environment, and runs deterministic external import plus typed rejection.
  CAP-206 is now narrowly `experimental` and `docs/RUNTIME_EVIDENCE.md`
  records the exact privacy, sampling, trust, authenticity, and no-sandbox
  limits. The final affected slice passes 156 tests.
- BRN-004 final local profile passes all seven gates under
  `.artifacts/quality/brn004-final-20260719/`: 46 automation tests, 1,075
  Python tests at 89% coverage, clean Ruff, 113 specs with zero errors and
  warnings, packaging, frontend build, and frontend lint. The clean package
  has exactly 20 schemas and reproducible wheel SHA-256
  `b9acd3d3204f5325228241d39dcf66e1b7957ac70882b49183cb64a669965a5d`.
- BRN-004 independent contract/projection, privacy/evidence-scope, and
  distribution/claims reacceptance all report ACCEPT under
  `.artifacts/agents/brn004-contract-projection-reacceptance/`,
  `.artifacts/agents/brn004-privacy-scope-reacceptance/`, and
  `.artifacts/agents/brn004-distribution-claims-reacceptance/`. The root final
  retained scan covered 9 artifact roots and 219 files with zero forbidden
  matches. The accepted scope remains one synthetic recording and fixture
  adapter, not live capture, universal data detection, authenticity, or broad
  OpenTelemetry support.
- ECO-001 foundation is accepted with a recorded counterexample. Equal locked
  Express `5.2.1` and Fastify `5.10.0` probes pass strict TypeScript `7.0.2`,
  two real HTTP checks, and a compiled stdio child on Node `22.22.3`.
  Official-source comparison plus an independent root replay select Fastify:
  documented `hasRoute`/`findRoute` confirm the statically visible route while
  source/lock hashes stay unchanged. The accepted compatibility boundary pins
  `@types/node` `22.20.1`; the Fastify transitive declaration failure with
  Node-26 typings is retained as a non-supported combination.
- ECO-001 protocol transport and accepted IR remain sufficient, but bare
  operation semantics are not. Exact onboarding source mapping fails existing
  same-Effect-slot Trust reconciliation with `mapping_basis_mismatch`, and two
  different verification expectations serialize to the same bare Behavior-IR
  frame. The active plan therefore selects additive language-neutral
  implementation-mapping and execution-verification request/result profiles
  through existing `AdapterPayload`, with contextual validation and explicit
  evidence successor; protocol/Behavior/Trust IR `1.0.0` remain unchanged.
  Evidence is under `.artifacts/agents/eco001-foundation/` and
  `.artifacts/quality/eco001-start-20260719/`; the focused pre-edit baseline is
  501 passing tests.
- ECO-001 fixture and neutral profile milestone is green. The seven-file
  Fastify application has immutable aggregate manifest SHA-256
  `5d4ba538a2ef468eaeeb119c49d4bf791a8453a0641f8adb41b50261f83799e8`;
  independent and root strict builds plus three native tests preserve it.
  Four closed implementation-evidence schemas now bind reviewed mapping and
  execution verification, including exact typed Behavior port inputs/expected
  outputs, without transport fields or Trust `mapped` promotion. Mapping,
  verification, wire, schema, contextual-negative, and passed-only successor
  tests total 106 green checks, including direct rejection of duplicate and
  noncanonical nested IR values; 194 affected IR/onboarding checks are also
  green. Evidence is under
  `.artifacts/agents/eco001-fixture-freeze/` and
  `.artifacts/quality/eco001-start-20260719/`.
- ECO-001 adapter protocol/control kit evidence is independently root-replayed:
  the exact build has no runtime dependencies, package tests pass 3/3, and three public
  conformance runs pass 17/17 with identical SHA-256
  `fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`,
  including zero stderr. This does not yet claim domain operations. An
  adversarial profile audit then produced eleven retained REDs for
  `model_copy` structural bypass and context-free claim promotion; all are
  green and independently reaccepted. A twelfth error-normalization RED is
  also green, the full profile is 118/118, and projection now validates the
  entire trusted execution context before deriving `tested`.
- ECO-001 external adapter protocol and inventory are now independently
  accepted. Every broader-protocol RED omitted by the 17-case kit is closed,
  package checks pass 26/26, exact root inventory passes 1/1, runtime
  dependencies are empty, and public conformance remains byte-identical at
  SHA-256
  `fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`.
  The final audit first rejected a valid unique unsorted generic `IRValue`
  record; root retained the two-method RED and separated generic decoding from
  canonical inventory-profile decoding. Duplicate generic records and
  unsorted inventory-profile records still fail. Focused independent
  reacceptance is ACCEPT under
  `.artifacts/agents/eco001-adapter-final-audit/recheck/`.
- Strict TypeScript inventory now assembles the same exact 42-record snapshot
  across page sizes with source revision
  `3edbe720c9cc3f47b2dfdd2283c94c13a954931c6d3cde7fdb95ec48b0646e9e`,
  exact spans and IDs, bounded frames, and zero stderr. Generated ignores,
  leaf-symlink non-following, ancestor-symlink rejection, collision, unsafe
  filename, unreadable source, unsupported layout, depth, stale cursor, and
  same-session recovery are green. Independent `/proc` evidence records Worker
  tasks `7 -> 8 -> 7` before the sole cancellation response; root
  `AdapterProcess` cancellation returns `cancelled/request_cancelled`, remains
  alive, and reuses the session. The frozen fixture manifest remains
  `5d4ba538a2ef468eaeeb119c49d4bf791a8453a0641f8adb41b50261f83799e8`.
- ECO-001 TypeScript discovery is independently accepted. The adapter requires
  the exact completed same-session inventory snapshot and emits exactly four
  deterministic contextual candidates with the accepted cross-language
  semantic digests, six eligible interfaces, and explicit uncovered
  `buildApp` plus `POST /quote-order`. Rebound source/producer/facts,
  malformed or recursively noncanonical profiles, and discovery before
  inventory fail with exact error-only frames; same-session recovery is exact.
  Root clean replay passes 30/30 adapter checks, 2/2 ecosystem checks, and two
  byte-identical 17/17 conformance runs; independent ACCEPT is under
  `.artifacts/agents/eco001-discovery-final-audit/`.
- The next mapping assumption is revalidated without a contract change. An
  explicit review materializes only shared quote-order behavior; the existing
  neutral mapping request fits the protocol frame, binds the reviewed bundle
  and current inventory, resolves five exact candidate evidence refs, and
  leaves baseline `mapped` claims empty. The retained ecosystem RED reaches
  `ucf.map` and fails only with
  `adapter_failure/operation_failed: unsupported conformance control payload`;
  see
  `.artifacts/quality/eco001-start-20260719/typescript-fastify-mapping-red.log`.
- ECO-001 implementation mapping is independently accepted. The adapter
  requires a completed current inventory, the exact supported neutral
  quote-order graph, and returns one content-derived binding to the three
  manifests plus `POST /quote-order` and `quoteOrder`. Root retained and closed
  a self-consistent broken-step attack with a recomputed Behavior digest;
  closed fields and all supported graph references are now resolved. Mapping
  creates no Trust claim or `mapped` promotion. Node passes 34/34 and the
  ecosystem plus implementation-evidence slice passes 121/121; final ACCEPT is
  `.artifacts/agents/eco001-mapping-final-audit/`.
- The real verification assumption is revalidated without a core/profile
  change. An external temp copy installs the exact 53-package lock and builds
  after the accepted inventory/mapping; a neutral request binds
  quantity/unit-price values, expected total, exact mapping/source,
  Node-22 Linux loopback environment, and versioned check/procedure. The
  retained RED reaches `ucf.verify` and fails only with
  `adapter_failure/operation_failed: unsupported conformance control payload`;
  see
  `.artifacts/quality/eco001-start-20260719/typescript-fastify-verification-red.log`.
- ECO-001 real HTTP verification is independently accepted. The bounded Worker
  loads only the regular built fixture module, invokes its exported `buildApp`,
  uses the fixed IPv4-loopback quote-order request, closes the application,
  and is reaped before result or cancellation acknowledgement. Passed/failed
  outcomes are distinct and only passed projects one reproducible `tested`
  claim; no `mapped` or `verified` promotion occurs. An independent Node
  `20.20.2` counterexample first proved that the declared Node-22 environment
  was not being checked. The adapter now rejects before preflight/Worker unless
  the real runtime is exactly Node `22.22.3` on Linux/x64; independent
  RED-to-GREEN replay and the Node-22 12/12 profile are retained under
  `.artifacts/agents/eco001-verification-acceptance/`.
- The clean ecosystem harness is root-replayed. It copies only regular exact
  source inputs to an external temporary build, runs locked adapter install,
  build, and all 46 Node checks once, and gives each inventory/discovery/
  mapping/verification behavior a fresh seven-file fixture. Root passes all 7
  ecosystem checks with observable output under
  `.artifacts/quality/eco001-start-20260719/typescript-fastify-clean-harness-root-green.log`;
  independent focused verification passes both behaviors with zero stderr and
  preserves fixture aggregate
  `5d4ba538a2ef468eaeeb119c49d4bf791a8453a0641f8adb41b50261f83799e8`.
- ECO-001 packaging and clean-gate integration are accepted. The unfiltered
  Python gate builds an exact external adapter copy and runs 46 Node plus 7
  ecosystem checks against fresh fixture copies. The package contract builds
  byte-identical wheels and private npm tarballs, checks exact bounded
  inventories, installs the adapter tarball offline without scripts, and runs
  the installed wheel plus installed adapter under `python -I` outside the
  source tree. The Python wheel contains exactly 24 neutral schemas and no
  adapter implementation.
- ECO-001 final root evidence under
  `.artifacts/quality/eco001-final-20260719/` passes all seven canonical gates:
  52 automation tests, 1206 unfiltered Python tests at 90% coverage, Ruff, 113
  specifications with zero errors/warnings, packaging, frontend build, and
  frontend lint. The accepted wheel SHA-256 is
  `8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`;
  the private adapter tarball SHA-256 is
  `a4138ab2901b014f6015a2bb514d3009a4e6b42c0de95461038e3fc8e674ee0c`.
- ECO-001 independent verification, distribution, and claims/architecture
  audits return ACCEPT under
  `.artifacts/agents/eco001-verification-acceptance/`,
  `.artifacts/agents/eco001-distribution-acceptance/`, and
  `.artifacts/agents/eco001-claims-architecture-audit/`. The physical
  source-only audit at
  `.artifacts/agents/eco001-clean-source-snapshot/20260719T170708Z-1929746/`
  repeats all seven gates from 696 files, with identical source manifests and
  frozen fixture aggregate
  `5d4ba538a2ef468eaeeb119c49d4bf791a8453a0641f8adb41b50261f83799e8`.
- ECO-001 public scope remains experimental and exact: TypeScript `7.0.2`,
  Fastify `5.10.0`, Node `22.22.3`, npm `10.9.8`, Linux/x64, one frozen
  quote-order fixture, and adapter-attested `tested` evidence only. It does not
  claim independent/formal verification, general framework support, hostile
  adapter safety, or release readiness. The clean snapshot's 10 frontend
  dependency audit findings are retained for `REL-002` security disposition.
- ECO-002 foundation preflight found no host `java`, `javac`, `mvn`, `gradle`,
  or `go` executable. Comparable spikes must therefore acquire exact
  toolchains reproducibly outside source and must measure that integration
  cost rather than relying on developer-machine globals.
- ECO-002 foundation is accepted. Current Java/Spring and Go processes each
  pass the full 17-case conformance profile three times with canonical SHA-256
  `fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`.
  Current Java source reproducibly yields the 173-entry JAR
  `f2b256e1fc01eb5b35959d8d994ff6bd087933fe646d1d9b0be743bfbcedc185`;
  the old `9501fc00...` digest is explicitly excluded as a pre-adapter
  intermediate artifact.
- Comparable discovery is tied at TP/FP/FN `1/3/0`, precision `0.250`, recall
  `1.000`, five review decisions, eleven evidence spans, and one ambiguity for
  each candidate. Root and independent selection therefore choose Go 1.26.5,
  standard-library `net/http`, Linux/amd64, `CGO_ENABLED=0` based on the closed
  zero-external-module graph and smaller distribution, update, and
  license-disposition surface. Exact evidence is
  `.artifacts/quality/eco002-start-20260719/selection-comparison.md` and
  `.artifacts/agents/eco002-selection-acceptance/report.md`.
- The neutral implementation-evidence profile remains unchanged. Production
  must retain a versioned canonical execution receipt in the existing
  `ExecutionEnvironment` coordinate, bind adapter/application digests plus
  toolchain/build/dependency/runtime/source coordinates, and reject an
  artifact mismatch. This is adapter-attested traceability, not authenticity.
- The selected six-file Go fixture is frozen at manifest SHA-256
  `bbd1f5d9491207d920e4ac2bff82d0e73c572b0764bb7da9530ae43bc31732dd`.
  It passes strict native tests and real ephemeral-loopback HTTP behavior,
  while separate external copies reproduce the adapter and fixture binaries
  with zero external Go modules and unchanged source manifests.
- The compiled Go adapter passes the public conformance kit at the unchanged
  canonical SHA-256
  `fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`
  and closes the first real inventory RED. Its exact read-only `os.Root`
  snapshot has 10 provenance records, 10 repository entries, four honest
  error-backed partial classification diagnostics, source revision
  `8c95d059aef410657d42e4544d34935c5f422efa9394f1242ee858e02a1c3ff8`,
  zero stderr, and no source mutation. The affected Go ecosystem slice passes
  16 tests plus Ruff, Go vet, and native tests. Evidence is under
  `.artifacts/quality/eco002-start-20260719/go-inventory-filesystem-*.log`.
- Go syntax classification is now green without a core/profile change. The
  exact snapshot has one module manifest, twelve public-interface facts over
  eleven distinct half-open spans, three native test assets, no diagnostics,
  `api_description complete/0`, and 51 total records. Two fresh processes
  produce byte-identical canonical snapshots with unchanged source revision,
  zero stderr, and no fixture mutation. The focused RED/GREEN/refactor logs are
  `.artifacts/quality/eco002-start-20260719/go-inventory-facts-*.log`.
- Go pagination and strict inventory negatives are green. Page sizes 7 and 1
  assemble the same 51-record snapshot; stale/unknown cursors, source drift,
  failed restart, malformed/changed/exported syntax, and a route detached from
  the returned mux fail without partial output or writes. The retained REDs
  include typed-nil cursor encoding, failed-restart run retention, and the
  detached-route false positive; the focused file passes 10/10. Evidence is
  `.artifacts/quality/eco002-start-20260719/go-inventory-pagination-*.log`,
  `go-inventory-failed-restart-*.log`, and
  `go-inventory-detached-route-*.log`.
- A cancellation foundation probe proves the synchronous Go frame loop cannot
  process `ucf.cancel` during real inventory; the control `block` case proves
  wire/correlation only. The plan now requires an adapter-wide asynchronous
  real-operation boundary with checkpoints and cleanup-before-ack during the
  process/resource slice. No mid-scan inventory cancellation claim is made.
- Go discovery is green without a core/profile change. Four function
  candidates have the exact accepted Python/TypeScript proposal digests,
  adapter-contextual IDs, inventory-backed provenance/confidence, 12 eligible
  interfaces, and eight explicit uncovered HTTP/field/effect interfaces. A
  focused RED made terminal completion monotonic across deterministic page
  replay. Valid discovery before completed inventory and stale, forged,
  binding-only, unknown-field, or recursively noncanonical requests fail
  without poisoning the session. Discovery passes 3/3; all current Go
  ecosystem tests pass 28/28 with unchanged conformance SHA and zero stderr.
  Evidence is
  `.artifacts/quality/eco002-start-20260719/go-discovery-*.log`.
- Explicit Go review/reconciliation is green through the existing neutral
  core lifecycle: one accepted, two rejected, one uncertain, one deterministic
  materialization, eight baseline uncovered subjects, and only observed/
  declared trust claims. A stale candidate reference is rejected. Focused
  evidence is
  `.artifacts/quality/eco002-start-20260719/go-reconciliation-baseline.log`.
- Product and conformance capabilities are now separated. Default mode
  advertises only implemented inventory, discovery, and mapping; explicit
  `--conformance` retains the all-family control surface. The focused product
  negotiation test is green; the post-mapping public conformance replay is
  still required before package acceptance.
- Go mapping is green through the unchanged neutral profile. The sole reviewed
  `QuoteOrder` target binds the exact ten discovery evidence refs and produces
  deterministic result
  `mapping.1ac553e103d8a887e1fa971788cf6f32784ba81265498de5474353313f3274c6`
  at page sizes seven and one. Before/incomplete inventory, seven malformed or
  unbound profiles, and live source drift fail explicitly; source drift clears
  the run and requires a fresh inventory. Mapping does not promote Trust
  claims. The focused mapping file passes 3/3 and the current
  discovery/reconciliation/mapping slice passes 8/8 with zero stderr.
- Go execution verification is green through the unchanged neutral profile.
  The adapter binds exact adapter/fixture digests and Go build/runtime/source
  coordinates into a canonical environment receipt, launches the unchanged
  server on ephemeral IPv4 loopback, performs one bounded real
  `POST /quote-order`, and reaps its process group. Wrong artifacts,
  environment/check/source/mapping bindings, failed checks, drift, timeout,
  and cancellation produce no promotable evidence; only passed evidence
  derives one `tested` claim and never `verified`. Public
  mapping/verification acceptance passes 15/15 and the complete current Go
  ecosystem slice passes 33/33. Evidence includes
  `.artifacts/quality/eco002-start-20260719/go-verification-conformance-green-attempt3.log`
  and `go-full-ecosystem-attempt1.log`.
- The general asynchronous real-operation runner is green: one bounded FIFO
  worker, serialized output, queued/running cancellation,
  cleanup-before-terminal acknowledgement, single-terminal late cancellation,
  process-group reaping, and session reuse. Native tests pass 50 repeats under
  `go-runner-repeat-50.log`. A narrow `strace` and independent host reproducer
  identify the transient post-exit `ETXTBSY` overwrite window as a Linux host
  behavior; atomic replacement preserves the artifact-drift negative while
  `/proc` confirms no surviving child.
- Go distribution and installed-wheel integration are green. The exact Go
  1.26.5 resolver is portable and CI installs a checksum-verified toolchain.
  Two closed offline lanes pass module/vet/tests and produce byte-identical
  adapter/fixture binaries with exact `go version -m`; the adapter distribution
  contains only its executable plus exact upstream Go `LICENSE`/`PATENTS`.
  Two reproducible wheels agree at SHA-256
  `8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`
  and physically exclude Go assets. Installed UCF passes two canonical 17/17
  Go conformance reports and the full 51-record inventory, 1/2/1 review, exact
  mapping, real verification, and tested-only projection. CAP-208 is bounded
  to that experimental proof. Evidence is
  `.artifacts/quality/eco002-start-20260719/go-installed-package-contract-attempt2.log`;
  the first attempt retains the incorrect local evidence-order assertion.
- Post-package root replay passes all 49 ecosystem tests, all 55 automation
  tests, claims 18/18, full Python Ruff, and `git diff --check`.
- The first independent final process audit rejected two exact-source defects:
  readiness consumed 524,288 bytes before applying its 65,536-byte limit, and
  cleanup returned after the leader exited while a TERM-ignoring descendant
  remained. Focused RED/GREEN changes now read readiness incrementally without
  hiding prefetched trailing output, require both one leader `Wait` and
  process-group extinction, escalate within one absolute deadline, and make
  cleanup failure outrank cancellation acknowledgement. Independent
  exact-source reacceptance passes 30/30 adversarial repetitions, 550/550
  native repetitions, 16/16 verification/resource/projection checks, Go vet,
  and stable source SHA-256
  `13a5c013d6f21c99e9cb404764352acc45e97daecb288afd39c7026b6a53f600`.
  Evidence is `.artifacts/agents/eco002-final-process/recheck/`.
- ECO-002 final current-source profile passes all seven gates under
  `.artifacts/quality/eco002-final-post-process-20260719/`: 55 automation
  tests, 1,251 Python tests at 90% coverage, Ruff, 113 specifications with
  zero errors/warnings, reproducible packaging, frontend build, and frontend
  lint. The current wheel SHA-256 is
  `8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`;
  current Go adapter and fixture executable SHA-256 values are
  `a807f5a85b1dc2400e7004c6b4a7021165a2baf2e410627059a167a8cd2ab72c`
  and
  `2a0e99b3030e6dc6111dc91c37b40599a5ff69bd7441876bb9261363ce0b1693`.
- ECO-002 independent architecture, process, and distribution/claims audits
  accept the bounded result under
  `.artifacts/agents/eco002-final-architecture/`,
  `.artifacts/agents/eco002-final-process/recheck/`, and
  `.artifacts/agents/eco002-final-distribution-claims/`. Root scope review
  records 30 added, 9 changed, and 0 removed ECO-002 paths; `git diff --check`
  is clean.
- ECO-002 physical clean-source acceptance is
  `.artifacts/agents/eco002-clean-source-snapshot/20260719T210814Z-3886818/`.
  All seven gates repeat from 723 regular source files; before/after source
  manifests agree at SHA-256
  `c6c8303c0ac8e250edddc11b25ac0a383b9208b8878bdbf009cee981f9955150`.
  The 12-file Go adapter and frozen 6-file fixture manifests are also
  byte-identical. The run retains 2 low, 3 moderate, and 5 high frontend
  dependency findings for explicit REL-002 disposition.
- ECO-003 foundation is accepted without a shared-contract change. The
  baseline passes 413 IR/protocol/implementation-evidence checks and five
  existing real HTTP verification checks. Three canonical Behavior documents
  with opaque HTTP/CLI/event requirements share neutral projection SHA-256
  `57cdee9787191c80405363a723a3f3d8735e49df79389864f0ebe7649c4ffae1`,
  contain zero platform-specific field keys, and reject missing/old
  requirements. A real external process returns
  `protocol_failure/unsupported_capability` for required
  `org.ucf.platform.event`. Evidence is
  `.artifacts/quality/eco003-start-20260719/focused-baseline.log`,
  `http-verification-baseline.log`, and `foundation-probe.log`.
- ECO-003 foundation audit confirms that `ucf.verify` dispatch automatically
  gates only `org.ucf.adapter.verification`; opaque platform capability and
  procedure compatibility must be requested explicitly and checked by the
  external adapter before fixture invocation. This needs no serialized
  contract change. The public unsupported-required conformance case is
  inherited GREEN, not a new RED.
- Read-only fixture comparison rejects the frozen Python test runner, the
  TypeScript Fastify route, the Go HTTP `--listen` flag, and adapter-internal
  workers as false CLI/event evidence. The selected path is a new
  zero-external-module Go standard-library platform fixture with real CLI and
  separate file-spool enqueue/dispatch/observe processes, implemented as an
  explicit exact profile in the existing Go adapter. The original six-file Go
  HTTP fixture remains immutable. No dependency, hosted service, or decision
  gate is introduced.
- The selected nine-file fixture is frozen at manifest SHA-256
  `7b563b0296cb40498b984edc1ea3eb96b9fb8e96c8225aa695bc50b8b0889d2d`.
  The retained RED fails only on absent fixture implementation symbols; all
  three native packages, Go vet, zero-module checks, real CLI and
  enqueue/unavailable-observe/dispatch/observe processes are green. Two
  deterministic binaries agree at SHA-256
  `f54ab3d5dfc50b5bf57610da6ec081aa3b4f700a71064fdaf041ebc56ac7cff4`,
  and before/after source manifests are byte-identical. Evidence is
  `.artifacts/quality/eco003-start-20260719/go-platform-fixture-*.log` and
  `go-platform-fixture-manifest.*`.
- The existing Go adapter now has one explicit platform profile without a
  core/schema/protocol change. Corrected REDs retain absent startup,
  attested capability, platform inventory, CLI procedure, and event procedure
  failures. The GREEN profile negotiates exact CLI/file-spool capabilities,
  observes 14 exact entries, produces one quote-order candidate, maps one
  reviewed neutral Behavior, and executes real CLI plus four-process
  enqueue/unavailable-observe/dispatch/observe checks. The full affected Go
  ecosystem and unchanged HTTP/conformance regression passes 42/42 under
  `.artifacts/quality/eco003-start-20260719/go-stdlib-affected-regression-attempt1.log`.
  Focused RED/GREEN evidence is in the
  `go-platform-{adapter,inventory,cli-verification,event-verification}-*.log`
  files in the same directory.
- The closed platform harness is accepted at 5/5 with two byte-identical
  fixture builds and source immutability under
  `.artifacts/quality/eco003-start-20260719/go-platform-harness-green-attempt2.log`.
  A first concurrent-copy attempt was correctly rejected and is not counted
  as GREEN.
- ECO-003 exact platform proof is verified. HTTP, CLI, and file-spool event
  procedures require their exact platform capability before spawn; process,
  spool, and executable-snapshot cleanup failures reject without evidence and
  outrank cancellation. The complete affected slice passes 483/483 and the Go
  suite passes ten full repetitions.
- ECO-003 root final profile passes all seven gates under
  `.artifacts/quality/eco003-final2-20260720/`: 63 automation tests, 1,280
  Python tests at 90% coverage, Ruff, 113 specs with zero errors/warnings,
  reproducible packaging/clean install, frontend build, and frontend lint.
  The wheel SHA-256 remains
  `8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`.
- Independent architecture/process and distribution/claims re-audits report
  ACCEPT under
  `.artifacts/agents/eco003-final-architecture-process-reaudit/` and
  `.artifacts/agents/eco003-final-distribution-claims-reaudit/`.
- ECO-003 physical source-only acceptance is
  `.artifacts/agents/eco003-clean-source-snapshot/20260719T225711Z-eco003/`.
  All seven gates repeat from 742 regular source files; before/after source
  manifests agree at SHA-256
  `a973ed929f41d0b5b8afcc746d51cdfe9c13559490c6a20fbdb2a2b47a256a2c`.
  The 16-file adapter, six-file HTTP fixture, and frozen nine-file platform
  fixture manifests are byte-identical. Ten frontend advisories remain an
  explicit REL-002 input.
- CHG-001 foundation accepted with no decision gate. The exact Behavior IR
  probe changes only `use-case.reserve-item` output requiredness, retaining
  stable coordinates while moving canonical digest from
  `5e6063cff77f19a238418c3275ea50a73b1960e285f616c5ee995e0a05f24e9a`
  to
  `a2fde64efd3e4cf76f8caa3d76e77190931d859924d200e343e3a495e21cf768`.
  Evidence:
  `.artifacts/quality/chg001-foundation-20260720/foundation-result.md`.
- The named interoperability profile is
  `fission-ai.openspec/spec-driven@1`, tested against the published
  `@fission-ai/openspec==1.6.0` release commit
  `e1b51d111ab446b54dee2d6159ac245f0339ae52`. Official prose/files remain
  declared opaque artifacts. Root reproduced that OpenSpec archives three
  unchecked tasks without persisted verification, so its archive can never
  satisfy the stricter UCF archive transition.
- CHG-001 filesystem boundary is read-only import to one canonical file,
  staged export only to an absent tree or exact-manifest no-op, and pure
  immutable UCF archive. It never merges into or deletes a populated user
  workspace. Independent evidence is under
  `.artifacts/agents/chg001-openspec-foundation/`.
- An independent resource-shape counter-probe selected six immutable closed
  stage resources over one aggregate: proposal, delta, task graph,
  implementation, verification, and archive. This adds five schema assets but
  removes 27 runtime-only aggregate field combinations, preserves predecessor
  digests, and still writes one output file per transition. Evidence:
  `.artifacts/quality/chg001-foundation-20260720/resource-shape-counterprobe.json`.
- CHG-001 implementation evidence is explicitly
  `context_validated_import`: the immutable receipt retains result, mapping,
  onboarding, and inventory digests, producer identities, capability
  selections, and validation procedure. It is replayable traceability, not
  adapter-session authenticity, and lifecycle transitions emit no Trust
  claim. VER-002 owns live session/operation evidence.
- CHG-001 represents `RemovedBehavior` exactly in the delta but rejects
  old-base-subject execution evidence with
  `unsupported_evidence_profile`; a final-state absence/tombstone profile is
  required before removal may be accepted as implemented. Typed and embedded
  Behavior IR is now semantically revalidated so broken refs cannot archive.
- Every accepting post-delta transition now receives the exact base and final
  Behavior IR and recomputes exhaustive delta coverage; a canonical digest is
  identity, not proof that an earlier command ran. All five exported lifecycle
  reference helpers also reject wrong-kind and `None` inputs with stable typed
  errors before field access or hashing.
- CHG-001 final focused integration passes 292 tests. Iterative OpenSpec
  traversal preserves a 128-component import/export/reimport canonical
  round-trip and classifies a 1,100-level tree with a typed profile error.
  Explicitly owned Go pipes plus one root graceful-termination attempt close
  both retained process races; deterministic regression repetitions, the full
  Go suite/vet, and installed 128/128 stress pass. Independent ACCEPT is under
  `.artifacts/agents/chg001-final-reaudit2/`.
- CHG-001 final local profile passes all seven gates under
  `.artifacts/quality/chg001-final2-20260720/`: 65 automation tests, 1,555
  Python tests at 90% coverage, Ruff, 113 specs with zero errors/warnings,
  reproducible clean packaging, frontend build, and frontend lint. The
  accepted wheel SHA-256 is
  `a831ad5e5dc7023fef9691a28d8f6005d62df18c1a6b4dee6104ebc20eb70b1d`;
  the accepted Go adapter SHA-256 is
  `e3a8e3848fe9736cec603258ab99d4ccb3bc678d1996b05b4ccc719002ab4440`.
- CHG-001 physical source-only acceptance is
  `.artifacts/agents/chg001-clean-source-snapshot/20260720T083629Z-chg001/`.
  Fresh locked Python/frontend installs repeat all seven gates; all 830 source
  files remain byte-identical at manifest SHA-256
  `466939848e4f8ca81e495203e26c20446d77776cebb941684e799c850cceeaf7`.
  The 16-file adapter, six-file HTTP fixture, and nine-file platform fixture
  manifests are also byte-identical.
- CHG-002 foundation is accepted without a production edit or decision gate.
  Root baseline passes 466 IR/lifecycle/ratchet/CLI tests and Ruff under
  `.artifacts/quality/chg002-start-20260720/`. Three independent read-only
  probes are under `.artifacts/agents/chg002-architecture-map/`,
  `.artifacts/agents/chg002-decision-threat-model/`, and
  `.artifacts/agents/chg002-foundation-probe/`.
- Exact base/final Behavior IR plus exhaustive delta derives deterministic
  structural field changes and reverse-reference edges, but not exact semantic
  impact. A use-case output change reaches an unrelated input `PortRef` under
  naïve closure, and opaque rules cannot be strength-ordered. Legacy spec graph
  and ratchet touch contracts are not reusable; missing semantic facts remain
  `may_affect` or unresolved.
- The selected additive boundary is a separate change-governance `1.0.0`
  profile with immutable `ImpactReport`, `DecisionAssessment`,
  `DecisionDeclaration`, and `GateEvaluation`. CHG-001 delta/task resources
  remain unchanged. Compatibility is deliberately limited to byte-exact graph
  extension, base-root loss, stricter document-level required capability, and
  unresolved for every other modification.
- The assessment covers exactly the six `AGENTS.md` decision classes.
  Base-root/capability breaks derive class one; the other facts require
  explicit caller declaration and cannot be inferred from prose, tokens,
  tasks, paths, or adapters. Unresolved, omitted, stale, partial, extra, or
  cross-change decisions block. A declaration is content-bound but not an
  authenticated person, signature, authorization, or one-time token.
- CHG-002 implementation milestone is green. Four exact closed governance
  schemas, strict codecs/contextual replay, complete supported graph impact,
  exact six-class assessment, content-bound declarations, pure gates, four
  installed commands, 29 generated fixtures, and CAP-216 now exist. Retained
  Red-Green-Refactor evidence is under
  `.artifacts/quality/chg002-start-20260720/`.
- CHG-002 post-audit affected integration passes 384
  lifecycle/governance/CLI/automation tests plus Ruff, schema freshness, and
  exact fixture-tree freshness. The installed
  external two-hash-seed governance workflow passes inside the package
  contract, preserves blocked output, and replays context in isolated Python.
  The reproducible 34-schema wheel SHA-256 is
  `9a664d50e6eabf85292175acf302977744457d61e89915fbe7caed5155b5d997`.
- CHG-002 independent contract/correctness and final integrated rechecks
  report ACCEPT under
  `.artifacts/agents/chg002-contract-correctness-recheck/` and
  `.artifacts/agents/chg002-final-integrated-recheck/`; distribution/claim
  evidence is `.artifacts/agents/chg002-distribution-claims-audit/`.
- CHG-002 final local profile passes all seven gates under
  `.artifacts/quality/chg002-final-20260720/`: 68 automation tests, 1,611
  Python tests at 89% coverage, clean Ruff, 113 specs with zero
  errors/warnings, installed packaging, frontend build, and frontend lint.
- CHG-002 physical source-only acceptance is
  `.artifacts/agents/chg002-clean-source-snapshot/20260720T104843Z-chg002/`.
  Fresh locked installs repeat all seven gates from 886 regular source files;
  before/after and checkout/snapshot file content is byte-identical at
  manifest SHA-256
  `d8d9035c52dffdd7bac99782cd5018e911b1d1dd5368057d26d42d5aba7e816e`.
  Directory mtimes changed during execution but no file bytes changed.
- Independent audit findings for negative witness indexes, concurrent
  symlink/hard-link publication aliases, and untracked extra fixtures each
  have retained RED/GREEN evidence under
  `.artifacts/quality/chg002-start-20260720/`; no bypass remains in the
  accepted scope.
- VER-001 foundation is accepted without a decision gate. Focused baseline
  passes 48 tests and Ruff under
  `.artifacts/quality/ver001-start-20260720/`. Independent protocol,
  determinism/executability, and ownership reports are under
  `.artifacts/agents/ver001-protocol-architecture/`,
  `.artifacts/agents/ver001-generator-contract/`, and
  `.artifacts/agents/ver001-ownership-behavior/`.
- The real framed probe selects generic and Python-profile generation
  capabilities and returns byte-identical results under hash seeds 1 and 777
  at SHA-256
  `74e9f92fd8280fbc70dfd7d31630626f578a55da6393460bc1fa10ff92088bf4`.
  Protocol and Behavior IR remain sufficient; the selected change is an
  additive exact generation profile.
- The legacy renderer is deterministic on one minimal input and, with explicit
  user-owned implementation and inputs, executes one generated test without
  monkey-patching. It is rejected as the publication boundary: root reproduces
  symlink/hard-link outside writes, prior-file deletion on late failure, and
  partial publication. Python/pytest rendering moves to an external adapter;
  core publication uses a complete receipt-backed generated-only tree.
- REL-001 immediate step after a human decision: update the ExecPlan with the
  selected versioned semantics, retain the first failing contract test, and
  proceed Red-Green-Refactor. Do not reinterpret Ratchet `1.0.0`, hide
  uncovered interfaces, synthesize placeholder candidates, or narrow the
  target without explicit approval.
- Decision gate: partial-discovery baseline and ratchet semantics
- Next package after verified completion: `REL-002`

## Handoff contract

Before stopping, update the frontmatter, current truth, active ExecPlan
progress, and evidence paths. Use `status: ready` when work can continue,
`status: in_progress` while a package is active, `status:
blocked_on_decision` only with a recorded decision gate, and `status:
verified` only after the package acceptance commands pass.
