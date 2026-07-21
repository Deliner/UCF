# ECO-003 Non-HTTP Platform Proof

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect the current
truth.

## Purpose / Big Picture

After this package, UCF can drive real executable checks for HTTP, command-line,
and asynchronous message/event behavior through the same versioned
language-neutral Behavior IR and implementation-evidence concepts. Users can
inspect three exact behavior documents, run the platform fixtures without
modifying their source, execute the checks through external adapters, and see
unsupported platform capability requests fail explicitly during negotiation.

The result is deliberately bounded. It proves three exact platform fixtures
and procedures; it does not claim universal HTTP servers, shells, brokers,
delivery guarantees, or arbitrary event frameworks. Platform invocation,
framing, process/runtime, and discovery knowledge remain adapter-owned. The
Python core must not gain HTTP method/path, argv/exit-code, broker/topic,
consumer-group, acknowledgement, or framework-specific fields.

## Foundational Assumption

The root assumption is that the accepted core already has the two abstractions
needed for platform breadth:

1. `BehaviorIR` expresses use cases, actions, ports, bindings, effects,
   observations, invariants, and opaque `CapabilityRequirement` entities
   without transport fields.
2. `ExecutionVerificationRequest` binds a reviewed behavior, exact mapping and
   source, typed inputs/expected outputs, environment, check, and adapter
   procedure, while the adapter protocol negotiates arbitrary qualified
   capability names in addition to operation-family capabilities.

The cheapest useful falsification experiment is a no-production-edit probe.
Build three canonical behavior documents with the same entity/port topology
and distinct opaque required capability names for HTTP, CLI, and event
execution. Round-trip them through the current codec, compare their
transport-neutral semantic projection, scan their serialized shapes for
platform field names, then call `validate_required_capabilities` with exact,
missing, and too-old capability maps. In parallel, initialize a current
external adapter with an unsupported required platform capability and retain
the exact `unsupported_capability` outcome. This must happen before a fixture
or adapter implementation is selected.

If the probe passes, retain Behavior IR, Trust IR, adapter protocol, and
implementation-evidence profile `1.0.0`; platform semantics live behind opaque
capabilities and versioned adapter procedure URIs. If it fails because the
verification request cannot bind the chosen procedure unambiguously, consider
one additive language-neutral capability binding in a new profile version. A
transport union or HTTP/CLI/event enum in core is rejected unless a retained
counterexample proves every neutral alternative inadequate. Any required
reinterpretation or break of an accepted serialized contract is a human
decision gate.

The retained probe passes. HTTP, CLI, and event documents have distinct exact
canonical SHA-256 values but the same normalized neutral-topology SHA-256
`57cdee9787191c80405363a723a3f3d8735e49df79389864f0ebe7649c4ffae1`.
All three round-trip canonically with zero platform-specific field keys;
missing and `0.9.9` capabilities fail with `unsupported_capability`. A real
external reference-adapter process also rejects required
`org.ucf.platform.event` as
`protocol_failure/unsupported_capability`. The foundation therefore retains
all accepted `1.0.0` serialized contracts; fixture selection is the next
experiment.

The probe and independent audit also expose one boundary that must remain
explicit: `ucf.verify` dispatch is automatically gated only by
`org.ucf.adapter.verification`; the shared verification validator does not
infer a platform capability from an opaque adapter procedure. ECO-003 will
therefore require the exact platform capability during process initialization
and enforce the capability/procedure cross-product inside the external
adapter before fixture invocation. If a future reviewed Behavior document
contains required capability entities, the core's existing
`validate_required_capabilities` remains the trust-boundary check. No
transport-specific field or protocol method is justified by this gap.

## Progress

- [x] 2026-07-19: Verify `ECO-002`, create this self-contained ExecPlan, and
  preserve the accepted Go/TypeScript HTTP evidence as the dependency
  baseline.
- [x] 2026-07-19: Record `git status`, re-read target/backlog/state, run the
  smallest
  relevant neutral IR/protocol/verification baseline, and retain the
  foundational falsification probe under
  `.artifacts/quality/eco003-start-20260719/`. The baseline passes 413
  IR/protocol/implementation-evidence checks and five existing real HTTP
  verification checks. The no-edit probe round-trips all three capability
  variants, produces one common neutral projection, rejects six missing/old
  combinations, and obtains the exact external unsupported-required outcome.
- [x] 2026-07-19: Compare the accepted Python, TypeScript, and Go fixtures and
  adapter reuse options. None has a real CLI/event boundary. Select a new
  zero-external-module Go standard-library platform fixture plus an explicit
  exact profile in the existing Go adapter; retain the original HTTP fixture
  unchanged.
- [x] 2026-07-19: Create and freeze the exact nine-file
  CLI/asynchronous-event fixture before adapter production edits. The first
  native RED fails only on missing `QuoteOrder`, spool, and `run` symbols.
  Minimum fixture implementation passes all three native packages, Go vet,
  zero-module verification, strict real command positive/negative behavior,
  and separate enqueue -> unavailable observation -> dispatch -> observation
  processes without sleeps. Two deterministic binaries agree at SHA-256
  `f54ab3d5dfc50b5bf57610da6ec081aa3b4f700a71064fdaf041ebc56ac7cff4`;
  the source manifest stays byte-identical at SHA-256
  `7b563b0296cb40498b984edc1ea3eb96b9fb8e96c8225aa695bc50b8b0889d2d`.
- [x] 2026-07-20: Retain focused REDs proving the exact executable CLI and event paths do
  not yet exist. Treat the public conformance kit's unsupported-required case
  and the foundation subprocess outcome as inherited GREEN. Invalid early
  manual probes remain labeled as such; corrected startup, attested
  capability, inventory, CLI-procedure, and event-procedure REDs fail at the
  intended boundaries.
- [x] 2026-07-20: Implement the minimum external inventory/mapping/verification support
  and real CLI behavior, then refactor while focused and affected tests stay
  green. One reviewed neutral quote-order candidate and mapping feed an exact
  real CLI verification; the unchanged HTTP/conformance and full affected Go
  ecosystem slice pass 42/42.
- [x] 2026-07-20: Implement the minimum real asynchronous event behavior with a
  deterministic completion/observation boundary. The adapter runs four
  separate bounded processes against an external temporary spool with no
  sleeps, checks absence before dispatch, observes the correlated result, and
  removes runtime state.
- [x] 2026-07-20: Close profile capability/procedure mismatch, timeout, cancellation,
  cleanup, duplication, unexpected-output, source-drift, and non-promotable
  evidence negatives. All HTTP, CLI, and event procedures now require their
  exact platform capability before snapshot or spawn. Cleanup failures from
  process, event spool, and both early and post-run executable-snapshot paths
  return result-less `operation_failed`, outrank cancellation, and leave the
  session reusable.
- [x] 2026-07-20: Prove the same neutral use-case concepts and claim rules across the
  accepted HTTP, CLI, and event fixtures; publish exact capability and
  limitation claims without promoting adapter-attested `tested` evidence to
  `verified`. The neutral comparison passes 9/9, the complete affected slice
  passes 483/483, and CAP-209 is experimental at only the frozen
  Linux/amd64 procedures.
- [x] 2026-07-20: Update `docs/automation/BASELINE.md`, `docs/ONBOARDING.md`, affected-gate
  selection, and claim-audit coverage so accepted ECO-001/ECO-002/ECO-003
  evidence and installed fixture dependencies are current and enforceable.
  Automation passes 63/63, including root/nested wheel-leak and stale-claim
  ratchets.
- [x] 2026-07-20: Run native checks, ecosystem and implementation-evidence suites,
  packaging/install proof, all seven canonical gates, complete scope/diff
  review, independent architecture/process/claims acceptance, and a physical
  source-only clean replay before advancing to `CHG-001`. Root gates pass
  under `.artifacts/quality/eco003-final2-20260720/`; independent audits and
  the 742-file physical replay all report ACCEPT.

## Surprises & Discoveries

The no-edit experiment confirms that adapter initialization permits arbitrary
qualified capabilities while method dispatch separately enforces the five
operation-family capabilities. Distinct platform capability values do not
change Behavior topology or introduce platform field keys. This removes the
need for a shared contract change, but executable CLI/event fixture evidence
is still required.

The legacy source-model layer under `src/ucf/models/` contains historical
platform declarations, including HTTP-specific fields. Those declarations are
not the canonical Behavior IR and cannot be reused as the cross-platform
execution contract merely because they already exist.

Read-only fixture comparison rejects reuse of every accepted frozen fixture
as the missing proof. The Python fixture exposes business functions and a
native test runner, not a product CLI. The TypeScript fixture exposes only one
Fastify HTTP route. The Go fixture's `--listen` argument configures its HTTP
server; it is not command behavior. Adapter worker queues and asynchronous HTTP
handlers are implementation internals, not observed legacy event behavior.
Calling any of these CLI/event support would overstate the evidence.

The smallest honest path is a new dependency-free Go standard-library legacy
fixture with one shared quote-order function, a real CLI entry, and a
filesystem-spool event entry. Separate enqueue, dispatch, and observe
processes give temporal decoupling without a hosted broker or sleep. The
existing Go adapter can add an explicit exact platform-fixture profile while
reusing its accepted protocol, inventory, mapping, runner, cancellation, and
cleanup boundaries. The original six-file HTTP fixture remains immutable.

The frozen fixture's real binary emits canonical quote output, persists one
event after its producer exits, returns exit 3 and no stdout when observation
is requested before dispatch, then lets independent dispatch and observe
processes return the correlated total. Runtime files exist only below a
temporary external spool. A duplicate event, invalid/traversal ID, and
symlinked spool root fail in native tests. This proves only the exact local
file-spool temporal boundary; crash recovery and hostile concurrent dispatch
are not inferred.

The external-adapter RED sequence exposed one evidence-quality pitfall: a
manual Go build carrying VCS settings is intentionally rejected by the strict
binary-coordinate validator. The first capability probes using that build
were therefore confounded and remain labeled invalid. Repeating with
`-buildvcs=false` isolated the missing capability name before the minimum
implementation. The accepted session harness always builds two independent
byte-identical adapter and fixture binaries with the exact frozen flags.

The new adapter profile now observes 14 exact filesystem entries, classifies
one manifest, nine public/process interfaces, and seven native tests, emits
only one quote-order candidate, requires explicit reconciliation, and reuses
the same neutral mapping topology for CLI and event verification. Platform
procedure selection and its capability gate occur before binary/environment
inspection or fixture invocation. CLI and event receipts differ only in
opaque procedure, check, capability, and execution-environment coordinates;
no transport field was added to Behavior IR.

The first implementation leaked selected capabilities from a failed
initialization attempt. A retained retry test forced initialization to
accumulate selections locally and publish them atomically only after complete
validation.

Executing the live fixture path after hashing left a path-swap window. The
accepted path copies exact bytes through a no-follow descriptor into a private
snapshot, validates build information and the receipt from that snapshot,
executes only the snapshot, and rechecks the live original afterward.

Process groups alone did not contain a descendant that called `setsid`.
Linux subreaper ownership plus `/proc` PID/start-time identities, TERM-to-KILL
escalation, adopted-child reaping, and a single cleanup deadline close the
frozen proof. Repeated execution also exposed benign `/proc` `ESRCH` races and
an obsolete ownerless test helper; disappeared identities are now benign and
all cleanup tests exercise the production ownership path.

Independent review found two gaps after initially green focused tests: HTTP
verification did not require its already advertised loopback capability, and
real snapshot/spool cleanup errors could be overwritten by cancellation or
turned into non-passing evidence. Retained RED/GREEN coverage now gates all
three procedures before spawn and routes early and late cleanup failures
through one precedence rule.

The event implementation initially offered a fresh timeout to each phase. One
overall deadline now bounds enqueue, unavailable observation, dispatch, and
final observation together. Packaging also exposed a script/package dual
import path and a root-level binary-name ratchet gap; both are covered without
putting Go source or binaries in the wheel.

## Decision Log

- **2026-07-19 — challenge neutral capability binding before adding a
  platform model.** Author: root agent. The first experiment uses only current
  `CapabilityRequirement`, adapter negotiation, and
  `ExecutionVerificationRequest`. A transport-discriminated core union would
  violate the target architecture and is not justified by backlog wording.

- **2026-07-19 — require real invocation boundaries.** Author: root agent.
  HTTP evidence remains a real loopback exchange. CLI evidence must execute a
  real argv/stdin/stdout/exit boundary owned by an external adapter, and event
  evidence must cross a real asynchronous enqueue/dispatch/observation
  boundary. Direct function calls, sleeps, hand-edited output, or synchronous
  callbacks labeled as events do not satisfy acceptance.

- **2026-07-19 — retain the accepted `1.0.0` neutral contracts.** Author: root
  agent. Three exact documents share one neutral projection, strict core
  validation rejects missing and old platform requirements, and a real
  external process rejects an unsupported required platform capability. No
  Behavior IR, Trust IR, adapter protocol, or implementation-evidence schema
  change is justified. External adapters will own exact platform procedure
  semantics.

- **2026-07-19 — add a new frozen Go platform fixture and an exact profile to
  the existing Go adapter.** Author: root agent. None of the three frozen
  fixtures has a real CLI/event boundary. Extending the TypeScript/Fastify
  fixture would couple platform proof to its exact HTTP classifier; publishing
  the test-only Python reference adapter would require a new distribution and
  duplicate mapping/verification/process work; a second Go adapter would
  duplicate the accepted protocol runner. A new zero-module fixture plus a
  selected adapter profile preserves predecessor manifests, adds no dependency
  or hosted service, and reuses the already adversarially accepted process
  cleanup. The event claim is exactly a local durable file-spool
  enqueue/dispatch/observe procedure, not a broker, ordering, durability,
  delivery, or exactly-once guarantee.

- **2026-07-19 — keep platform semantics in an explicit adapter profile.**
  Author: root agent. The existing Go adapter now accepts
  `--platform-fixture-executable <absolute-path>`, advertises exact
  `org.ucf.platform.cli-process@1.0.0` and
  `org.ucf.platform.file-spool-event@1.0.0` capabilities only for the
  attested platform binary, and rejects HTTP/platform cross-profile
  negotiation. The shared operation methods and serialized
  implementation-evidence contracts are unchanged. Exact CLI/event
  procedure/check/environment coordinates remain adapter-owned opaque
  values.

- **2026-07-20 — gate every procedure by its exact platform capability.**
  Author: root agent. General `org.ucf.adapter.verification` authorizes the
  method family but not a runtime boundary. HTTP, CLI, and file-spool event
  procedures therefore require `org.ucf.platform.http-loopback`,
  `org.ucf.platform.cli-process`, and
  `org.ucf.platform.file-spool-event` respectively before snapshot or spawn.
  This enforces an application profile without changing the serialized
  protocol.

- **2026-07-20 — execute a private attested snapshot and own Linux
  descendants.** Author: root agent. The exact proof uses no-follow snapshot
  copying, snapshot-derived receipts, post-run live revalidation, a Linux
  child subreaper, PID/start-time tracking, and one cleanup deadline. A cleanup
  failure rejects the operation and cannot be replaced by cancellation.
  Sandbox/cgroup isolation and hostile same-UID or kernel D-state containment
  remain explicitly unclaimed.

- **2026-07-20 — keep Go delivery external to the Python wheel.** Author: root
  agent. Two offline lanes reproduce the adapter plus both fixture binaries,
  while the installed wheel drives them from an isolated external directory.
  Basename ratchets reject root or nested binary leakage. This preserves the
  existing packaging boundary and introduces no production dependency.

## Outcomes & Retrospective

ECO-003 is verified at its exact experimental boundary. Behavior IR, Trust IR,
adapter protocol, and implementation-evidence remain at `1.0.0`; no
transport-specific core field or Python production dependency was added. One
frozen nine-file Go fixture now proves a real CLI process and a temporally
decoupled four-process file-spool event procedure beside the accepted real
HTTP procedures. Exact capabilities fail before spawn, only exact passed
evidence can derive `tested`, and no path derives `verified`.

Fresh root evidence is 483 affected tests, 63 automation tests, 1,280 full
Python tests at 90% coverage, Ruff, 113 specs with zero errors/warnings,
reproducible clean-install packaging, and both frontend gates. The wheel
remains byte-identical at SHA-256
`8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`.
Architecture/process and distribution/claims re-audits report ACCEPT under
`.artifacts/agents/eco003-final-architecture-process-reaudit/` and
`.artifacts/agents/eco003-final-distribution-claims-reaudit/`.

The physical source-only replay contains 742 regular source files and passes
all seven gates with before/after manifest SHA-256
`a973ed929f41d0b5b8afcc746d51cdfe9c13559490c6a20fbdb2a2b47a256a2c`.
Its exact evidence is under
`.artifacts/agents/eco003-clean-source-snapshot/20260719T225711Z-eco003/`.
The honest remaining boundary is one frozen Linux/amd64 proof with current-user
authority, no sandbox/cgroup, no hosted broker or delivery guarantees, and ten
frontend advisories retained for REL-002. CHG-001 is the next ready package.

## Context and Orientation

The canonical language-neutral model is in `src/ucf/ir/models.py`; strict
reference and capability validation is in `src/ucf/ir/validation.py`.
`CapabilityRequirement` names opaque external semantics, and
`validate_required_capabilities` rejects missing or too-old required
capabilities.

The out-of-process protocol is in `src/ucf/adapter_protocol/`. Initialization
selects qualified capabilities, while operation methods use the stable
inventory/discovery/mapping/generation/verification families. The protocol
must remain platform-neutral.

Exact mapping and executable evidence profiles are in
`src/ucf/implementation_evidence/`. An
`ExecutionVerificationRequest` binds a reviewed Behavior entity, mapping,
current source records, typed input/output port values, exact environment,
check, and versioned adapter procedure. A passed result can project only a
`tested` claim through the existing validation path.

Accepted HTTP examples live in
`tests/fixtures/brownfield/typescript_fastify_legacy_quote/`,
`tests/fixtures/brownfield/go_stdlib_legacy_quote/`,
`adapters/typescript-fastify/`, and `adapters/go-stdlib/`. The accepted Python
brownfield fixture is
`tests/fixtures/brownfield/python_legacy_quote/`; inspection proves it has no
product CLI/event boundary and it remains unchanged. The selected new frozen
fixture will live at
`tests/fixtures/brownfield/go_stdlib_legacy_platforms/`; the existing external
adapter at `adapters/go-stdlib/` receives an explicit profile rather than a
second protocol implementation. New external implementation code belongs
below `adapters/`, never inside `src/ucf`.

Cross-platform acceptance belongs in `tests/ecosystems/`. Public status and
limits are in `docs/CAPABILITIES.md`, especially CAP-209. Installed and
source-only behavior is enforced through `tools/package_contract.py`,
`tools/quality_gates.py`, and `.github/workflows/quality.yml`.

## Plan of Work

First, capture the inherited baseline and run the foundational probe. Use one
canonical neutral quote-order behavior topology so platform comparison does
not accidentally compare different business semantics. Prove that only
opaque capability identities and adapter procedure coordinates differ, and
that missing or incompatible platform capability versions fail explicitly.
If the existing contracts cannot express this honestly, update this plan and
record the counterexample before any schema change.

Second, freeze the selected dependency-free Go fixture before adapter edits.
Its one binary exposes an exact quote-order CLI and three separate event
commands: enqueue to an external temporary spool, dispatch one retained
message, and observe the correlated result. The producer must exit before the
dispatcher starts, and absence of an observation is checked immediately
without a timing delay. Record the regular-file manifest, exact Go
toolchain/build inputs, positive and negative native checks, deterministic
canonical outputs, external-only runtime side effects, and source
immutability.

Third, add one acceptance behavior at a time under strict
Red-Green-Refactor. Start with platform capability negotiation, then CLI
verification, then event verification. Reuse the existing neutral reviewed
Behavior/mapping/request/result contracts. Adapter code validates the exact
fixture shape, source revision, mapping, environment, procedure, typed ports,
and expected outputs before execution. Both platform procedures use one
reviewed quote-order Behavior and mapping; their capability and procedure
coordinates differ outside Behavior IR. Every failure returns a structured
error or non-passing result without partial promotable evidence.

Fourth, close process and evidence boundaries. Exercise wrong/missing/old
capabilities, unknown platform procedures, malformed and noncanonical
payloads, wrong source/mapping/environment/check bindings, fixture drift,
unexpected stdout/stderr/event multiplicity, nonzero exit, timeout,
cancellation, and descendant cleanup. A failed, cancelled, stale, or ambiguous
run must not derive `tested`; no path derives `verified`.

Here, fixture drift means an exact live source/request mismatch for the
executed fixture and mapping. Selective invalidation across a broader evidence
graph belongs to `VER-002` and is not an ECO-003 claim.

Finally, prove all three platform classes through one shared acceptance table
and installed workflow. Keep adapter implementations outside the Python wheel
unless the existing packaging policy explicitly includes them as separate
artifacts. Update CAP-209 with exact runtime, fixture, procedure, and limits,
correct CAP-209 to adapter-attested `tested` rather than `verified`, update
BASELINE/ONBOARDING and affected-gate selection, run affected and full gates,
inspect the complete diff, obtain independent architecture/process/claims
review, and repeat from a physical source-only snapshot.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream output to the terminal and named
logs under `.artifacts/quality/eco003-start-20260719/` or dedicated
`.artifacts/agents/eco003-*/` audit directories.

Record the baseline:

    git status --short
    uv run --locked --extra dev pytest -q \
      tests/ir tests/adapters tests/implementation_evidence \
      tests/ecosystems --no-cov
    uv run --locked --extra dev ruff check src tests tools

Run the first no-edit probe against:

    src/ucf/ir/models.py
    src/ucf/ir/validation.py
    src/ucf/implementation_evidence/models.py
    src/ucf/adapter_protocol/dispatcher.py
    src/ucf/adapter_protocol/process.py

The retained output must name the three canonical document digests, confirm
the common neutral topology/projection, show missing and too-old capability
rejections, show a real unsupported-required initialization rejection, and
report zero transport-specific Behavior IR fields.

For each production slice, first run one focused test that fails for the
intended missing behavior, implement the minimum change, rerun it green, and
refactor only touched code. Before package completion run:

    <exact native CLI and event fixture checks>
    <exact external adapter checks and conformance twice>
    uv run --locked --extra dev pytest -q \
      tests/ir tests/adapters tests/implementation_evidence \
      tests/ecosystems --no-cov
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/eco003-final-20260719
    git diff --check

## Validation and Acceptance

ECO-003 is accepted only when fresh executable evidence proves:

1. HTTP, CLI, and asynchronous event checks use the same Behavior IR entity
   kinds, port/value model, mapping, verification request/result, and claim
   transition rules;
2. canonical Behavior IR contains no HTTP method/path/status/header,
   argv/stdin/stdout/exit-code, broker/topic/partition/group/ack, language,
   framework, build-tool, or runtime implementation field;
3. platform semantics are external capabilities with explicit versions, and a
   missing, too-old, unsupported, or unnegotiated required capability fails at
   the correct trust/protocol boundary;
4. CLI verification crosses a real process interface and validates exact
   input, output, exit class, source, mapping, environment, and procedure
   without modifying the fixture;
5. event verification crosses a real asynchronous enqueue/dispatch/observation
   boundary and deterministically rejects timeout, duplicate/unexpected
   observation, cancellation, cleanup failure, and source drift;
6. only exact passed evidence can derive `tested`; failed, cancelled, stale, or
   ambiguous evidence cannot, and no result is promoted to `verified`;
7. the accepted external adapters pass the exact experimental conformance
   `1.0.0` contract and
   the installed workflow does not depend on checkout-local builds or manual
   output repair;
8. CAP-209 and all public documentation name exact fixtures, runtimes,
   capabilities, evidence level, and limitations without generalizing to
   unsupported shells, brokers, delivery guarantees, or platforms;
9. native and affected suites, packaging/install checks, all seven canonical
   gates, complete scope/diff review, independent audits, and a physical
   source-only replay are green.

No acceptance may use skip, xfail, warning-only enforcement, path exclusion,
baseline reset, fixture rewriting, hidden sleeps, synchronous callbacks
labeled as asynchronous events, in-process adapter shortcuts, manually
repaired output, or weakened claim validation.

## Idempotence and Recovery

Foundation probes and fixture-native checks are read-only and may be repeated.
Builds, environments, queues, sockets, and adapter outputs use temporary
workspaces outside source. Freeze source manifests before native execution and
compare them after every acceptance run. Canonical output is emitted only
after complete validation; failed runs leave no partial evidence.

Cancellation and timeout recovery must stop and reap every adapter-owned
process or worker before returning a terminal result. A subsequent request in
the same supported session must remain usable. If a probe requires a new
dependency, hosted broker, public-contract reinterpretation, irreversible
migration, weaker security/correctness boundary, or materially different event
semantics, record options, evidence, and recommendation here and set
`docs/automation/STATE.md` to `blocked_on_decision`.

## Artifacts and Notes

Starting evidence belongs under:

- `.artifacts/quality/eco003-start-20260719/`;
- `.artifacts/agents/eco003-foundation/`;
- `.artifacts/agents/eco003-fixture-review/`;
- `.artifacts/agents/eco003-final-architecture/`;
- `.artifacts/agents/eco003-final-process-claims/`;
- `.artifacts/agents/eco003-clean-source-snapshot/`.

Retain concise command transcripts, canonical digests, source manifests,
native positive/negative behavior, RED/GREEN evidence, process/resource
outcomes, conformance reports, installed-workflow summaries, and public-claim
audit results. Do not retain credentials, raw sensitive payloads, dependency
caches, unbounded broker/event logs, or temporary execution workspaces.

## Interfaces and Dependencies

Accepted upstream public contracts begin at version `1.0.0`:

- Behavior IR and Trust IR;
- adapter protocol and conformance kit;
- inventory, onboarding, implementation-mapping, and
  execution-verification profiles;
- canonical JSON, closed decoding, content-derived identities, exact source
  and environment binding, and passed-only claim projection.

The initial implementation must add no Python production dependency and no
hosted service. Platform capability names are qualified, versioned, opaque to
the core, and interpreted only by external adapters. Adapter implementation
modules must not enter `src/ucf`, and core modules must not import adapter
implementations. Any accepted serialized change requires an explicit version
and compatibility evidence; unknown fields, duplicate identities, broken
references, incompatible versions, and unsupported capabilities remain hard
errors.
