# Prove TypeScript HTTP framework support through one external adapter

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After ECO-001, an unchanged pre-existing TypeScript HTTP application can enter
the same UCF brownfield flow already accepted for Python: native checks remain
green, an external adapter passes the public conformance suite, inventory and
discovery produce strict observed/candidate evidence, explicit review
materializes the shared language-neutral quote-order Behavior IR, mapping binds
that intent back to exact source evidence, and one real HTTP verification
produces reproducible `tested` evidence without teaching the Python core about
TypeScript, a web framework, npm, or Node.

Support is intentionally bounded to one selected mainstream TypeScript HTTP
framework, one frozen legacy fixture, one package-manager/build layout, and one
executable quote-order path. It is not a claim for all JavaScript runtimes,
frameworks, package managers, monorepos, transpilers, test runners, or HTTP
applications.

## Foundational Assumption

The root assumption was that the accepted protocol, inventory/onboarding
profiles, Behavior/Trust IR, and conformance kit already form a sufficient
language-neutral control plane. All TypeScript source/build/framework and HTTP
execution semantics should fit in an independently built adapter process; the
Python core should need no protocol-method, IR-version, adapter import, or
language-specific branch.

The cheapest useful falsification experiment compared Express and Fastify
using current official primary documentation, then exercised both candidates
with equivalent disposable TypeScript quote services:

1. install from a lockfile and run its native build/test without UCF;
2. compile a minimal TypeScript adapter entry point and run the existing
   installed conformance kit against the resulting Node process;
3. send the existing neutral inventory/discovery and generic operation shapes
   through that process and determine whether the accepted profiles can
   describe exact TypeScript source/build/test/HTTP evidence without a core
   edit;
4. execute real HTTP requests and attempt to express exact source mapping and
   caller-bound verification evidence tied to the shared quote-order Behavior
   IR.

The comparison will record release/support status, TypeScript integration,
runtime/build prerequisites, lockfile footprint, license, route-discovery
surface, and the smallest reproducible native test. Popularity alone will not
select the framework.

The experiment partially falsified the assumption. Protocol `1.0.0`,
`AdapterPayload`, inventory/discovery, and Behavior/Trust IR are sufficient
transport and representation boundaries. Existing operation-specific
contracts are not sufficient for two exact exchanges:

- current Trust `mapping` reconciles declaration and observation only for the
  same `Effect` slot; it cannot represent a reviewed use-case/action binding
  to exact inventory source evidence;
- a bare Behavior IR verification request serializes none of the
  caller-expected target, check, environment, source revision, or procedure.
  Returning evidence changes the Behavior digest and invalidates the immutable
  onboarding Trust identity.

The selected boundary keeps protocol, Behavior IR, and Trust IR `1.0.0`
unchanged and adds narrowly versioned, language-neutral implementation-mapping
and execution-verification request/result profiles carried through the existing
`ucf.map` and `ucf.verify` operation families. Contextual validators will bind
them to an exact OnboardingBundle, Behavior entity, inventory revision/records,
check, environment, initialized producer, capability, and procedure.
Verification materializes an explicit successor evidence document/Trust
overlay; it never rewrites or silently rebinds the accepted onboarding bundle.

This additive boundary is the demonstrated minimum, not a framework branch or
protocol reinterpretation, so it is not a human decision gate. No core
production dependency is selected. The Fastify/TypeScript packages are exact
locked dependencies of the frozen external fixture and adapter build only;
the shipped adapter runtime must have no third-party runtime dependency.

## Progress

- [x] 2026-07-19: Verify BRN-004 through the complete seven-gate profile and
  independent contract/projection, privacy/evidence-scope, and
  distribution/claims acceptance; create this self-contained ExecPlan before
  ECO-001 production changes.
- [x] 2026-07-19: Record the pre-edit toolchain and focused protocol,
  conformance, inventory, onboarding, IR, claim, and gate baseline. Node
  `22.22.3`, npm `10.9.8`, the repository-locked frontend TypeScript `5.9.3`,
  and 501 focused Python tests are green under
  `.artifacts/quality/eco001-start-20260719/`.
- [x] 2026-07-19: Compare Express `5.2.1` and Fastify `5.10.0` from official
  sources and equivalent locked TypeScript `7.0.2` probes. Select Fastify after
  an independent root experiment confirms documented `hasRoute`/`findRoute`
  on the unchanged app with identical source/lock hashes. Record the exact
  Node `22`/`@types/node` `22` compatibility boundary and the rejected Node-26
  typing combination.
- [x] 2026-07-19: Falsify bare mapping/verification payload sufficiency with a
  real accepted onboarding bundle. Retain `mapping_basis_mismatch`, identical
  frames for distinct verification expectations, changed successor digest,
  and stale onboarding-Trust evidence. Select additive neutral mapping and
  verification profiles before production code.
- [x] 2026-07-19: Freeze the selected pre-existing legacy fixture, its native
  build/test/HTTP behavior, exact manifest, and shared neutral quote-order
  semantics before adapter implementation. Independent and root replays install
  the exact lock, compile with strict TypeScript and `skipLibCheck: false`, pass
  three native tests including two real loopback HTTP paths, and preserve all
  seven fixture inputs byte-for-byte. Root evidence is under
  `.artifacts/quality/eco001-start-20260719/`; the isolated freeze report is
  `.artifacts/agents/eco001-fixture-freeze/report.md`.
- [x] 2026-07-19: Complete strict RED/GREEN/refactor for four closed
  implementation-evidence `1.0.0` documents: mapping request/result and
  verification request/result. Exact wire profiles, content identities,
  bundle/inventory/candidate/mapping contextual checks, typed behavior-port
  values, passed-only successor projection, and four generated schemas are
  green in 106 focused checks; the affected IR/onboarding slice is green in
  194 checks under `.artifacts/quality/eco001-start-20260719/`.
- [x] 2026-07-19: Complete the public-kit portion of adapter protocol/control
  with an exact
  dependency-free runtime build. Package tests pass 3/3 and three independent
  root public-kit runs pass 17/17 with identical canonical SHA-256
  `fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`,
  including a zero-stderr wrapper. This establishes kit conformance, not yet
  the broader protocol resource/semantic acceptance below or a domain claim.
- [x] 2026-07-19: Close the independent broader-protocol REDs omitted by the
  17-case kit: pending/session limits, oversized-frame resynchronization,
  recursive tagged values, ASCII-canonical output, qualified identities,
  capability ordering, and terminal shutdown behavior. A final independent
  audit then caught one additional generic/profile ordering mismatch: the
  adapter rejected valid unique unsorted generic `IRValue` records. Root
  retained the exact two-method RED, separated generic record validation from
  canonical inventory-profile decoding, and reran 26/26 package checks,
  1/1 exact inventory acceptance, and the unchanged 17/17 conformance digest.
  Focused independent reacceptance is ACCEPT.
- [x] 2026-07-19: Reproduce and close an independent adversarial RED against
  the neutral profiles. Six `model_copy` structural bypasses and five
  context-forged projection variants failed for the intended reason. Public
  projection now performs the complete trusted-context validation itself;
  independent reacceptance is ACCEPT. A final focused RED normalizes an
  otherwise safe malformed in-memory target to explicit `invalid_structure`;
  118 focused tests and Ruff are green.
- [x] 2026-07-19: Add strict TypeScript inventory evidence through the external
  adapter. Exact 42-record output is repeatable across page sizes, provenance
  and spans match the frozen vectors, generated trees are explicit ignores,
  unsafe paths/layouts/collisions/stale cursors fail with zero stderr, frames
  remain bounded, and real Worker cancellation terminates before its sole
  acknowledgement and permits same-session reuse. Runtime dependencies remain
  empty and the frozen seven-file manifest is unchanged.
- [x] 2026-07-19: Retain the focused TypeScript discovery RED and implement
  only the exact four-candidate, six-eligible/two-uncovered result through the
  existing onboarding payloads. Discovery is bound to the exact completed
  same-session inventory snapshot, preserves candidate provenance/confidence,
  rejects rebound or noncanonical profiles, and remains byte-identical across
  page sizes and hash seeds. Root clean replay passes 30/30 adapter checks,
  2/2 ecosystem checks, and two 17/17 conformance runs at the unchanged digest;
  the frozen fixture aggregate is unchanged. Independent final audit is ACCEPT
  under `.artifacts/agents/eco001-discovery-final-audit/`.
- [x] 2026-07-19: Revalidate the mapping-profile assumption with the accepted
  TypeScript discovery and an explicit review that materializes only the shared
  quote-order behavior. The existing neutral profile binds the reviewed bundle,
  Behavior target, current source revision, and five candidate evidence refs in
  a bounded frame while baseline `mapped` remains empty. Retain the focused
  ecosystem RED: the valid request reaches `ucf.map` and fails only with
  `adapter_failure/operation_failed` because non-control mapping is not yet
  implemented. Evidence is
  `.artifacts/quality/eco001-start-20260719/typescript-fastify-mapping-red.log`;
  design audit is `.artifacts/agents/eco001-mapping-red-design/`.
- [x] 2026-07-19: Close focused mapping RED/GREEN/refactor for the explicitly
  reviewed quote-order materialization. The adapter requires a completed
  current inventory, validates the exact supported neutral one-root/six-entity
  graph, and returns one content-identified binding to the five reviewed source
  records without Trust promotion. Root final review retained a
  self-consistent broken-step RED with a recomputed Behavior digest; the narrow
  graph validator closes it. Node checks pass 34/34, the affected ecosystem
  plus implementation-evidence slice passes 121/121, conformance remains
  byte-identical, and independent final mapping audit is ACCEPT under
  `.artifacts/agents/eco001-mapping-final-audit/`.
- [x] 2026-07-19: Revalidate the execution-verification profile against the
  accepted real mapping and an external clean fixture copy. The neutral request
  binds exact typed values, mapping/source, Node-22 Linux loopback environment,
  and check/procedure; locked fixture install/build succeeds after inventory
  without changing the frozen source. Retain the focused RED: the valid request
  reaches `ucf.verify` and fails only with
  `adapter_failure/operation_failed` because non-control verification is absent.
  Evidence is
  `.artifacts/quality/eco001-start-20260719/typescript-fastify-verification-red.log`;
  design is `.artifacts/agents/eco001-verification-red-design/`.
- [x] 2026-07-19: Add and independently accept the real HTTP verification
  path with exact source, adapter, environment, check, and revision evidence.
  The adapter executes only the fixed quote-order procedure through a bounded
  loopback Worker, reaps it before completion/cancellation acknowledgement,
  and permits only a passed result to project one `tested` claim. A final
  Node-20 counterexample exposed false Node-22 environment attestation; the
  retained RED now fails before preflight/Worker unless the runtime is exactly
  Node `22.22.3` on Linux/x64. The external clean harness builds once outside
  the checkout, gives every ecosystem test a fresh seven-file fixture, and
  passes 46 Node plus 7 ecosystem checks. Independent verification acceptance
  is ACCEPT under
  `.artifacts/agents/eco001-verification-acceptance/`.
- [x] 2026-07-19: Complete explicit review/onboarding against the unchanged
  fixture, deterministic repeated/hash-seed runs, negative fixtures,
  packaging and clean-install execution, documentation/capability claims,
  full gates, diff review, and independent acceptance. The final root profile
  passes all seven gates with 52 automation and 1206 Python tests. A physical
  696-file source-only snapshot repeats all seven gates, preserves both its
  source manifest and the frozen fixture byte-for-byte, and installs the
  reproducible wheel plus private adapter tarball outside the checkout.
  Independent verification, distribution, claims/architecture, and
  clean-source audits all return ACCEPT.

## Surprises & Discoveries

Repository inventory initially showed no TypeScript brownfield fixture or
ecosystem adapter. The current Node asset was the dependency-free conformance
sample, which is explicitly not TypeScript ecosystem evidence. The frozen
fixture and separately distributable adapter now establish exactly one
unchanged Fastify application boundary; they do not establish broader
TypeScript, Fastify, Node, operating-system, or hostile-adapter support.

The existing Python brownfield fixture expresses quote-order behavior as plain
functions rather than HTTP. Sharing IR must mean sharing language-neutral
behavior identity and assertions, not copying the Python transport shape into
the TypeScript application.

An initial `npx --yes tsc --version` probe resolved the unrelated deprecated
`tsc` package from the registry instead of the TypeScript compiler. It changed
no repository manifest but demonstrates why ECO-001 commands must use an exact
locked package manifest and local `node_modules/.bin/tsc`, never an implicit
`npx` package-name resolution. The repository frontend's locked compiler is
TypeScript `5.9.3`.

The two equal locked probes both pass strict compilation, two real loopback
HTTP checks, and a compiled LF-stdio child process with TypeScript `7.0.2` and
runtime-matched `@types/node` `22.20.1`. Express resolves 99 lock locations and
Fastify 72; install size is not aligned with that count. With
`@types/node` `26.1.1`, Express still compiles while Fastify's transitive
`thread-stream` declaration fails without `skipLibCheck`. This does not
override the runtime-matched Node-22 proof, but it fixes the accepted
compatibility claim and requires an explicit future upgrade test.

Official-source and local recommendations initially conflicted. The root
tie-breaker rebuilt the retained Fastify app from its exact lock, used only the
documented public `hasRoute`/`findRoute` APIs to confirm the statically visible
`POST /quote-order` route, and reproduced all four manifest/source hashes.
Fastify is selected for evidence quality—built-in types, exact route queries,
and fewer lock locations—not popularity or benchmark claims. Printed route
trees and registration monkey-patching remain forbidden contracts.

The contract counter-probe found that an OnboardingBundle fits comfortably in
the existing frame bound, so the wire protocol is not the gap. The gap is
semantic: coercing source implementation mapping into a Trust `Effect` mapping
would lie, while two different caller verification expectations serialize to
the same bare Behavior-IR frame. A language-neutral operation profile is
therefore required even though the generic transport remains unchanged.

The frozen fixture contains seven source/config/lock inputs with aggregate
manifest SHA-256
`5d4ba538a2ef468eaeeb119c49d4bf791a8453a0641f8adb41b50261f83799e8`
and lock SHA-256
`45a07317fb5d806f665bf679a3c36fc88baeb2c0526391bb2f4186e1c5d88437`.
Both independent and root runs install 53 packages, compile, and pass three
native tests while leaving that manifest unchanged. Generated `node_modules`
and `dist` trees were removed after each proof.

Two read-only blueprints disagreed on whether a versioned `Check` alone was an
exact caller expectation. A root counterexample changed the desired neutral
input while retaining target, source, check, environment, and procedure; the
request could not change without a serialized value binding. The accepted
profile therefore carries canonical typed `IRValue` bindings to Behavior input
and expected-output ports. Context validation resolves every port and value
kind. No method, path, status, header, host, or other transport coordinate
entered the core contract.

Canonical IR encoding sorts entities by `(kind, id)`, so a successor cannot
preserve base entities as a byte-prefix. The actual invariant is stronger and
order-independent: every original entity is equal by identity and the
successor adds exactly one derived Provenance plus one VerificationEvidence.

Direct Pydantic construction of a verification request initially accepted
duplicate or non-canonically ordered entries inside a nested `RecordValue`.
The focused negative test failed twice for the intended reason. Structural
validation now applies the existing IR-value semantic validator and recursively
requires canonical record-entry order before identity or wire encoding; the
complete 106-test implementation-evidence slice is green.

The first independent profile audit rejected the public composition boundary,
not the external JSON parser: callers could project a re-identified forged
result without supplying the trusted request/context, and `model_copy` could
bypass after-model validators. Eleven retained counterexamples now require the
same closed JSON profile at public validation boundaries, while preserving
more specific contextual failure codes by checking trusted coordinates first.
Projection has no context-free overload and invokes full result validation
before any `tested` claim can be derived.

The re-audit also distinguished generic `SourceRecord` trace metadata from the
canonical execution proof. Mutating the former cannot promote a claim: the
successor's immutable `VerificationEvidence` and `Provenance` retain the exact
source URI/revision, producer/time, check, environment, and executed time, and
the tested basis resolves those records. This is a documentation distinction,
not a Trust `1.0.0` schema reinterpretation.

The public 17-case kit did not exercise every normative protocol limit. An
independent process probe accepted 65 blocked requests, resumed after an
oversized unterminated prefix, echoed a nested duplicate record, emitted raw
non-ASCII JSON, accepted an invalid producer name, and preserved noncanonical
requested capability order. These are confirmed adapter defects against
`docs/ADAPTER_PROTOCOL.md`, not reasons to weaken the kit or its claims; their
negative tests are now part of the active adapter milestone.

The first root inventory adversarial replay retained the intended mixed
result under
`.artifacts/quality/eco001-start-20260719/adapter-inventory-threat-root-red.log`.
Generated-directory ignores preserve the clean source revision, a leaf
symlink is hashed without following it, path collisions fail explicitly, and
a stale cursor fails with zero stderr. Unsupported layouts, unreadable files,
and invalid raw-byte filenames instead escaped as Node exceptions with
nonzero stderr; a symlinked root ancestor was followed; and cancellation of a
real scan timed out and terminated the process. Those are implementation REDs,
not accepted platform limitations. The happy-path inventory remains green at
42 exact records in the unchanged root test.

The first ecosystem test also exposed a clean-checkout integration dependency:
it names repository-local `dist/main.js`, while the canonical `python-tests`
gate runs before `packaging-contract`. Root independently listed the unchanged
seven-gate graph and confirmed that both ignored `dist/` and `node_modules/`
were present during the interim green run. The accepted integration direction
is therefore a self-contained external temporary build harness discovered by
the existing unfiltered Python gate, plus an installed local npm-tarball proof
inside the existing packaging contract. A new eighth gate would duplicate the
same test or preserve a hidden cross-gate artifact dependency. Evidence is
`.artifacts/quality/eco001-start-20260719/gate-graph-root.log` and the
read-only audit at
`.artifacts/agents/eco001-gate-integration-audit/report.md`.

The first independent verification acceptance ran the exact Node-22-labelled
request under Node `20.20.2` and still received a valid passed result. The
serialized environment identity was therefore only caller text, not an
attested execution condition. The adapter now compares the real runtime to
Node `22.22.3`, Linux, and x64 after strict request/context decoding and before
filesystem preflight or Worker creation; any mismatch is an explicit
`operation_failed`. Independent replay retains the original Node-20 pass and
the guarded rejection, while Node `22.22.3` remains 12/12 green.

Moving the ecosystem proof to clean external copies exposed one test-only path
assumption: direct profile tests passed an absolute fixture root to a traversal
contract that intentionally accepts portable relative roots. A dedicated
test-only fixture locator now validates the configured absolute directory but
derives the relative traversal value separately. The resulting unfiltered
Python slice performs one external locked adapter build and uses a distinct
unchanged seven-file target per behavior; it no longer consumes ignored
checkout `dist/` or `node_modules/` trees.

The completed adapter replay closed every retained inventory and protocol RED,
but an independent final audit rejected integration for one case absent from
the 17-case kit. Core accepts unique generic `IRValue` record entries in any
order, while the adapter initially imposed the canonical profile-record order
before semantic dispatch. Root reproduced `invalid_params` for both inventory
and verification echo controls, added the focused regression, and split
generic decoding from inventory-profile decoding. Duplicate records and
unsorted inventory-profile records still fail; unique generic `["z", "a"]`
records now round-trip in exact order. The full package is 26/26, exact root
inventory is 1/1, conformance remains byte-identical at
`fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`,
and the focused re-audit is ACCEPT under
`.artifacts/agents/eco001-adapter-final-audit/recheck/`.

The initial discovery acceptance checked candidate identities and semantic
digests but did not assert the exact candidate count. A counterexample showed
that the core correctly accepts multiple distinct candidates for one subject,
so fixture-specific false-positive control belongs in the ecosystem
acceptance, not a new core uniqueness rule. The retained acceptance now
requires exactly four candidates. Final threat review also distinguished
top-level profile ordering from recursive ordering: generic tagged records
remain order-neutral, while nested discovery-profile records are permanently
covered as canonical and rejected when reordered.

The first mapping GREEN validated the Behavior document digest and outer
quote-order use case but did not resolve its internal action/binding/step
graph. A raw client could change `step.action` to a missing action, recompute
the target digest, and receive `map_result`. Root retained that exact RED.
Mapping now validates the complete supported one-root/six-entity neutral graph,
closed kind-specific fields, canonical ports/references, and one structurally
valid dynamic provenance. This remains a narrow supported graph validator, not
a second general Behavior IR implementation.

The audit also asked whether a result should repeat observed output values or
an execution-artifact digest. The cheapest adversarial check is the existing
structurally valid fixture result: a producer can assert `passed` without a
runtime, and the same producer could equally copy expected values or invent a
digest. Those extra self-reported fields do not strengthen authenticity. The
actual trust boundary is therefore explicit: a named/versioned external
adapter attests to a versioned procedure, and ECO-001 must separately reproduce
that procedure against the real unchanged application. Documentation must not
describe this as independent attestation or formal verification.

Building the fixture before inventory changed the exact observed tree from 42
to 44 records because compiled output became evidence. The accepted workflow
therefore inventories and maps the unchanged source first, then installs and
builds only for native and executable verification. This is sequencing
evidence, not an ignore rule for generated output.

The final physical clean snapshot reported 10 frontend dependency audit
findings while every configured gate remained green. ECO-001 makes no
vulnerability-disposition or release-readiness claim; the findings remain
explicit input to the dependency-ordered release/security work in `REL-002`.

## Decision Log

- **2026-07-19 — compare Express and Fastify before selecting the fixture
  framework.** Author: root agent. Both are plausible mainstream TypeScript HTTP
  choices, but their type/build/runtime and route-introspection boundaries
  differ. ECO-001 will use official evidence and the same minimal probe for
  both rather than selecting from memory.

- **2026-07-19 — preserve the accepted protocol/IR until a real counterexample
  exists.** Author: root agent. Adapter payloads and capability negotiation are
  intended to own language/framework semantics. A public core change before
  the subprocess experiment would be speculative.

- **2026-07-19 — select Fastify 5.10.0 on an exact Node-22 toolchain
  boundary.** Author: root agent. Both candidates pass the same strict build
  and real HTTP checks. Fastify additionally exposes documented structured
  route queries and owns its types; a root replay confirms those APIs against
  unchanged source. Pin TypeScript `7.0.2` and `@types/node` `22.20.1`, retain
  the Node-26 declaration failure as a compatibility limitation, and make no
  Express or broad Fastify claim.

- **2026-07-19 — add operation profiles, not fake Trust mappings or argv
  conventions.** Author: root agent. Exact source binding is not the existing
  same-Effect-slot `TrustMapping`, and a bare Behavior IR cannot carry caller
  verification expectations. Add closed mapping and verification
  request/result profiles through `AdapterPayload`, bind them contextually, and
  derive an explicit evidence successor. Keep protocol/Behavior/Trust
  `1.0.0` unchanged and do not promote source binding to a Trust `mapped` claim.

- **2026-07-19 — keep adapter runtime dependency-free.** Author: root agent.
  The fixture owns Fastify at runtime; the adapter uses exact TypeScript/Node
  types only to build. Its published JavaScript runtime uses Node built-ins and
  declares no third-party runtime dependency, avoiding a new UCF production
  dependency while keeping framework semantics out of Python.

- **2026-07-19 — freeze the app before writing the ecosystem adapter.**
  Author: root agent. The exact Fastify lock, strict compiler configuration,
  legacy helpers, real positive/invalid HTTP behavior, and seven-file hash
  manifest are now immutable test input. Adapter output may be generated only
  outside this tree; before/after manifests will enforce the boundary.

- **2026-07-19 — serialize neutral port values in verification requests.**
  Author: root agent. A versioned opaque check URI does not make
  per-invocation caller values observable in the transcript. Add closed,
  canonical input and expected-output bindings using existing Behavior
  `PortRef` and language-neutral `IRValue`; validate required ports and value
  kinds contextually. Keep all HTTP execution details in the external adapter.

- **2026-07-19 — keep execution results minimal and state the adapter trust
  boundary.** Author: root agent. Repeating observed values or an artifact
  digest reported by the same adapter cannot prove execution; a dishonest
  adapter can echo or forge either. Retain the exact request, outcome,
  producer, capability, versioned procedure, and execution time, then require
  an independently replayed real-process acceptance scenario. Call the result
  adapter-attested tested evidence, never independent or formal verification.

- **2026-07-19 — preserve the seven canonical gates and make ecosystem tests
  self-contained.** Author: root agent. `python-tests` already discovers
  `tests/ecosystems/**` before packaging runs, so a repository-local adapter
  build is an invalid prerequisite and a new gate would duplicate execution.
  Build adapter and fixture from locked clean copies in an external temporary
  workspace during the existing Python gate; prove the installed wheel and
  dependency-free local npm tarball separately in `packaging-contract`.

- **2026-07-19 — distinguish generic tagged-value validity from canonical
  operation-profile encoding.** Author: root agent. Generic protocol
  `IRValue` records require valid unique entries but do not require
  lexicographic input order. Inventory and onboarding JSON-profile payloads do
  require canonical record order at their own decoding boundary. Keep these
  checks separate in the adapter; do not narrow the generic protocol or
  broaden the strict operation profiles.

- **2026-07-19 — bind discovery to the completed same-session inventory
  snapshot.** Author: root agent. A caller-supplied self-consistent snapshot
  cannot replace the evidence the adapter actually observed. Discovery
  therefore requires the exact cached inventory document, binding digest,
  record identities, producer, capability, and supported facts before it
  emits candidates. This is a narrow checked-fixture classifier, not a claim
  of general TypeScript or Fastify inference.

- **2026-07-19 — let review cross process sessions but require current source
  evidence for mapping.** Author: root agent. Human review need not keep an
  adapter process alive. The mapping request therefore carries the reviewed
  bundle digest, Behavior, inventory, and materialized target; core validates
  their full review context. The mapping adapter independently inventories the
  current source in its own session and accepts only an exact embedded snapshot
  plus the supported neutral quote graph. It does not hard-code reviewer,
  decision, candidate, or bundle identities.

- **2026-07-19 — verify the exact runtime before attesting its environment.**
  Author: root agent. A valid caller request can name the supported Node-22
  environment even when the adapter is actually running under Node 20.
  Verification therefore rejects unless `process.versions.node`, platform,
  and architecture exactly match Node `22.22.3` on Linux/x64. This closes the
  retained counterexample without broadening the supported profile.

- **2026-07-19 — inventory the unchanged source before any fixture build.**
  Author: root agent. Building first adds two compiled records and changes the
  observed inventory from 42 to 44. The accepted onboarding order is read-only
  inventory, discovery, review, materialization, and mapping before native
  build/verification. Generated records remain observable when present; no
  exclusion or baseline reset hides them.

- **2026-07-19 — distribute the ecosystem adapter separately and preserve the
  seven canonical gates.** Author: root agent. The Python wheel ships exactly
  the neutral core and 24 schemas, while a deterministic private npm tarball
  ships only the dependency-free adapter JavaScript, README, and package
  metadata. The existing unfiltered Python and packaging gates build and test
  clean external copies, so adding an eighth gate would duplicate rather than
  strengthen the dependency graph.

## Outcomes & Retrospective

ECO-001 is complete with no decision gate. A separately packaged
TypeScript `7.0.2`/Fastify `5.10.0` adapter on exact Node `22.22.3`, npm
`10.9.8`, Linux/x64 passes the public 17-case conformance kit at canonical
report SHA-256
`fea45d4c1f1a1c5f56db9053e2b1e1c0695f5bff4d0609e1619e378e1dff1384`.
One frozen seven-file legacy fixture completes the shared neutral quote-order
inventory, discovery, explicit review, reconciliation, mapping, and real
loopback HTTP verification flow while preserving aggregate SHA-256
`5d4ba538a2ef468eaeeb119c49d4bf791a8453a0641f8adb41b50261f83799e8`.
Only a passed adapter-attested check derives `tested`; no result derives
`mapped` or `verified`.

The final root profile under
`.artifacts/quality/eco001-final-20260719/` passes all seven gates: 52
automation tests, 1206 unfiltered Python tests at 90% coverage, Ruff, 113
specifications with zero errors or warnings, clean packaging, frontend build,
and frontend lint. The reproducible wheel SHA-256 is
`8bd20ae4ed748f43aec01f79cdb67a527deaa1b30889aa9013ec9d9e55e0df89`;
the reproducible private npm tarball SHA-256 is
`a4138ab2901b014f6015a2bb514d3009a4e6b42c0de95461038e3fc8e674ee0c`.
The physical clean-source audit independently repeats the profile from a
696-file source-only copy with identical before/after manifests.

Independent acceptance evidence is retained under
`.artifacts/agents/eco001-verification-acceptance/`,
`.artifacts/agents/eco001-distribution-acceptance/`,
`.artifacts/agents/eco001-claims-architecture-audit/`, and
`.artifacts/agents/eco001-clean-source-snapshot/20260719T170708Z-1929746/`.
The bounded result does not claim general TypeScript/Fastify support,
independent attestation, hostile-adapter safety, Windows/macOS support, or
release readiness. Ten frontend audit findings remain explicit `REL-002`
release/security work rather than an ECO-001 exception.

## Context and Orientation

The stable serialized process boundary lives under
`src/ucf/adapter_protocol/`; the public conformance resources and black-box
runner live under `src/ucf/adapter_conformance/` and are documented in
`docs/ADAPTER_CONFORMANCE.md`.

Neutral Behavior and Trust contracts live under `src/ucf/ir/`. Inventory
profiles and assembly live under `src/ucf/inventory/`. Candidate discovery,
review, materialization, and bundle validation live under
`src/ucf/onboarding/`. Their CLI transaction is in `src/ucf/cli.py`.

The accepted Python comparison fixture is
`tests/fixtures/brownfield/python_legacy_quote/`. Its external adapter is
`tests/fixtures/adapters/inventory_reference_adapter.py`, with framework and
language-specific logic below
`tests/fixtures/adapters/inventory_reference/`. ECO-001 must reuse the public
wire profiles and neutral quote-order semantics, not import that Python
implementation.

The selected frozen fixture belongs at
`tests/fixtures/brownfield/typescript_fastify_legacy_quote/`. The separately
buildable adapter belongs at `adapters/typescript-fastify/`. Generated build
output and dependency directories remain untracked and reproducible from
checked lockfiles. New neutral operation-profile code belongs under a
language-agnostic `src/ucf/implementation_evidence/` boundary with generated
schemas under `src/ucf/schemas/implementation_evidence/v1/`; exact names may be
refined by the first model RED without moving framework semantics into core.

## Plan of Work

First, retain a read-only framework/toolchain comparison and a minimal
real-process probe. This milestone selected Fastify and the additive
implementation-mapping/execution-verification profile boundary described
above.

Second, freeze the selected application as legacy input. Record a byte manifest
and native commands before UCF touches it. Add focused REDs for the exact
closed mapping/verification documents and contextual invariants, then for exact
inventory facts and deterministic discovery candidates. Implement only the
minimum neutral profile code followed by the external TypeScript adapter. The
Python core may launch it only through argv and serialized protocol frames.

Third, add exact mapping and one executable HTTP verification path.
Implementation mapping remains a separate source-binding result, not a Trust
same-slot mapping. Verification must run the real built application, issue the
real request, bind the result to the exact Behavior entity/source
revision/environment/adapter procedure, and derive only the evidence level
justified by the passed check. Wrong revisions, unsupported framework/build
layouts, malformed output, timeouts, stderr, partial evidence, and forged
coordinates must fail explicitly.

Fourth, drive the unchanged fixture through inventory, discovery, explicit
DecisionSet review, onboarding materialization, mapping, and verification.
Repeated runs must be deterministic; user source must remain byte-identical;
generated or adapter-owned output must never overwrite application code.

Finally, integrate adapter build/test/conformance and the end-to-end fixture
scenario into local/CI gates and clean-install evidence. Publish a precise
capability row, compatibility/limitation matrix, and operator documentation.
Run affected suites, all seven-or-expanded canonical gates, full diff review,
and independent contract, ecosystem, process/security, and clean-distribution
acceptance before advancing to `ECO-002`.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream command output and retain it under
`.artifacts/quality/eco001-start-20260719/` or a named independent audit tree.

Record the pre-edit repository/toolchain baseline:

    git status --short
    node --version
    npm --version
    uv run --locked --extra dev pytest -q \
      tests/adapters tests/inventory tests/onboarding tests/ir \
      tests/automation/test_capability_claims.py \
      tests/automation/test_quality_gates.py --no-cov

The foundation probe will run the same native install/build/test and minimal
adapter/conformance sequence for each viable candidate. Exact commands and
digests will be added after the official-source comparison fixes versions and
lockfiles.

For every acceptance behavior, retain a focused failing test before production
implementation, rerun it green, then refactor only the touched boundary. Before
completion run:

    uv run --locked --extra dev pytest -q <affected Python paths> --no-cov
    uv run --locked --extra dev ruff check src tests tools
    <selected adapter locked install, build, lint, test, and conformance>
    <unchanged TypeScript fixture native build/test before and after onboarding>
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/eco001-final-20260719
    git diff --check

## Validation and Acceptance

ECO-001 is accepted only when executable evidence proves:

1. the selected adapter passes the public conformance profile as an external
   Node process and the Python core imports no adapter, TypeScript compiler,
   framework, package-manager, HTTP-client, or build-tool implementation;
2. the frozen TypeScript HTTP fixture installs and passes native build/test
   before and after UCF with an identical source/input manifest;
3. inventory is read-only, bounded, paged, provenance-rich, deterministic, and
   names exact TypeScript source/build/test/public-HTTP facts without claiming
   intent;
4. discovery exports uncertain candidates with reproducible confidence and
   source evidence; explicit review retains accepted, edited, rejected, and
   uncertain dispositions;
5. accepted/edited materialization shares the language-neutral quote-order
   Behavior IR shape and identifiers used by the Python scenario without
   placing Express/Fastify/npm/Node/HTTP-specific fields in core IR;
6. mapping binds exact reviewed behavior to exact source evidence and fails on
   stale, missing, duplicate, wrong-kind, or forged references;
7. one real HTTP verification executes without monkey-patching and produces
   reproducible passed evidence for the exact current source, adapter,
   environment, procedure, and check; failed/stale/error results cannot create
   a `tested` claim;
8. unsupported capabilities, layouts, versions, malformed frames, stderr,
   timeouts, cancellation, and process cleanup fail deterministically with no
   partial output or source mutation;
9. the adapter build and runtime are reproducible from checked manifests and
   lockfiles, its license/support boundary is recorded, and clean-install/CI
   executes from outside the Python source tree;
10. public docs and CAP-207 claim only the exact measured framework, fixture,
    package-manager/build layout, HTTP path, and operating-system scope;
11. affected suites, canonical gates, full diff review, and independent
    contract/ecosystem/process/distribution acceptance are green.

No test may use skip, xfail, warning-only enforcement, path exclusion,
baseline reset, fixture/source rewriting, hand-edited generated output, or an
in-process Python adapter import.

## Idempotence and Recovery

The frozen fixture is copied to isolated workspaces for mutable commands.
Native install/build output is ignored and reproducible from a lockfile.
Inventory, discovery, mapping, and verification outputs are canonical and
written only after complete validation. Failed operations preserve existing
outputs and fixture bytes and reap owned child processes.

The framework comparison and foundation probe are disposable. If either
candidate fails, retain the evidence and remove only generated dependency/build
workspaces, never user source. If a public-contract, production-dependency,
license, irreversible data, or materially different support-semantic choice is
required, record options, consequences, evidence, and recommendation here and
set `docs/automation/STATE.md` to `blocked_on_decision`.

## Artifacts and Notes

Starting evidence belongs under:

- `.artifacts/quality/eco001-start-20260719/`;
- `.artifacts/agents/eco001-foundation/`.

Accepted foundation evidence:

- official Express/Fastify comparison and source ledger:
  `.artifacts/agents/eco001-foundation/framework-research/report.md`;
- equal locked build/HTTP/stdio probes and Node-typing counterexample:
  `.artifacts/agents/eco001-foundation/toolchain-probe/report.md`;
- protocol/profile sufficiency counter-probe and 17-case conformance replay:
  `.artifacts/agents/eco001-foundation/contract-reuse/report.md`;
- root focused 501-test baseline and public Fastify route-query tie-breaker:
  `.artifacts/quality/eco001-start-20260719/focused-baseline.log` and
  `fastify-public-route-probe.log`.

Retain concise official-source notes, framework comparison, native commands,
fixture manifests, protocol transcripts/digests, RED/GREEN logs, deterministic
outputs, process cleanup, installed package evidence, benchmarks, and final
profile results. Do not retain dependency directories, build trees, raw
secrets, or long unfiltered logs.

## Interfaces and Dependencies

Accepted upstream contracts:

- adapter protocol and conformance kit `1.0.0`;
- Behavior IR and Trust IR `1.0.0`;
- inventory and onboarding profiles `1.0.0`;
- ratchet and optional runtime-evidence profiles `1.0.0`;
- canonical JSON, strict decoding, exact identities, bounded process
  lifecycle, and atomic output conventions.

Selected external boundaries:

- Node `22`, npm lockfile v3, TypeScript `7.0.2`, and
  `@types/node` `22.20.1`;
- Fastify `5.10.0` in the frozen fixture only;
- one separately launched, dependency-free-at-runtime adapter executable
  declaring inventory, discovery, mapping, and verification capabilities;
- one frozen TypeScript legacy fixture and one real quote-order HTTP check;
- additive implementation-mapping and execution-verification profiles through
  existing `AdapterPayload`, with no protocol or IR version change.

No TypeScript/framework/build/runtime parser belongs in `src/ucf`. No change to
protocol, Behavior IR, or Trust IR is authorized unless the real-process probe
demonstrates an unrepresentable required coordinate and this plan records the
versioning decision first.
