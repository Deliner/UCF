# Import optional sanitized runtime evidence without claim promotion

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After BRN-004, a team can explicitly import a previously recorded runtime or
contract observation through an out-of-process adapter and attach the
sanitized result to an exact Behavior IR document as observed evidence. The
import is off by default: UCF starts no collector, intercepts no traffic, and
reads no runtime recording unless the caller invokes the command with an
explicit environment and data-handling policy.

The observable proof will use a small unchanged fixture recording that contains
both allowed behavior data and forbidden secret/personal-data sentinels. A
fixture adapter will sanitize and normalize it before any result crosses the
adapter boundary. Repeated imports must produce byte-identical observed-only
evidence, retain exact source, adapter, sampling, environment, and policy
coordinates, contain none of the forbidden bytes, and create no declaration,
mapping, tested, or verified claim. Missing capability, incomplete policy,
unsafe data, or forged output must fail without replacing prior output.

BRN-004 is not live telemetry collection, arbitrary OpenTelemetry query
support, a trace store, tested-claim promotion, evidence authenticity, or
selective staleness. Those broader capabilities remain outside this package.

## Foundational Assumption

The root assumption was that the accepted adapter protocol and Trust IR already
provide the right architectural boundaries for this package: a named runtime
evidence profile can travel through the existing `ucf.verify` operation while
the adapter owns recording-format semantics, and the accepted result can be a
strict observed-only Trust IR overlay rather than a new intent model or a
mutation of Behavior IR.

The cheapest useful falsification experiment will run a real child process
against the accepted BRN-003 Behavior IR fixture and compare three
interpretations:

1. parse raw OpenTelemetry/contract recording shapes in the Python core;
2. add a new adapter protocol method or mutate Behavior/Trust IR `1.0.0`;
3. negotiate both `org.ucf.adapter.verification` and a proposed
   `org.ucf.adapter.runtime-evidence` profile, send one closed neutral import
   request through `ucf.verify`, and require the external adapter to return a
   Trust IR overlay containing only exact `source_record` and `observed_fact`
   records.

The experiment must prove or falsify all of the following with retained bytes:

- the current protocol can negotiate the extra profile and carry the bounded
  request/result without changing protocol `1.0.0`;
- the result can preserve source revision, adapter name/version/procedure,
  explicit environment digest, sampling description, and sanitization policy
  without placing transport- or vendor-specific fields in core IR;
- a fixed allowlist can exclude a secret sentinel and a personal-data sentinel
  before the result frame crosses into the core;
- the normalized output is deterministic across repeated processes and
  `PYTHONHASHSEED` values;
- `validate_trust_against_behavior` accepts the overlay while no claim or
  declaration record is present;
- partial sampling is represented as scope evidence and never interpreted as
  complete behavior coverage.

Alternative 1 violates the language-neutral core boundary and would require a
new production parser dependency. Alternative 2 expands a stable public
protocol/IR before demonstrating that existing extension points are
insufficient. The retained experiment accepted the transport half of
alternative 3 and falsified its result-model half. A real child process carried
the request and observed-only Trust overlay through `ucf.verify`, but the
generic Trust model also accepted missing import coordinates, opaque values,
and an otherwise valid `Claim`. Trust IR has no typed document-level home for
procedure, environment, sampling, data policy, or sanitization scope.

The selected boundary is therefore an additive, closed
`RuntimeEvidenceDocument 1.0.0` carried as `AdapterPayload` through the
unchanged protocol. The specialized client requires both verification and
runtime-evidence capabilities, validates the exact document against caller
coordinates and the supplied Behavior IR, and only then projects its
observations to a Trust IR containing `SourceRecord` and `ObservedFact`
records. The runtime document remains authoritative for import scope. This
adds no production dependency and does not reinterpret protocol, Behavior IR,
or Trust IR `1.0.0`, so it is not a human decision gate.

Before implementation the data boundary is fixed conservatively:

- import is recorded-only and invoked explicitly; live capture is absent;
- an explicit allowlist is required and raw attributes are not retained;
- secret and personal-data handling is `reject` by default, with no
  auto-redaction claim stronger than the executable policy;
- sampling metadata and an exact environment digest are mandatory, and
  sampled absence never proves behavioral absence;
- source bytes stay outside the core result; only their digest, normalized
  allowed observations, producer/procedure identity, and a bounded
  sanitization summary may cross;
- failure messages and retained test logs must not echo forbidden values.

No production dependency, hosted service, collector, exporter, or background
process is authorized by this plan.

## Progress

- [x] 2026-07-19: Verify BRN-003 through the final local seven-gate profile and
  independent contract, CLI/security, and physical clean-distribution ACCEPT
  reports; create this self-contained ExecPlan before BRN-004 production
  changes.
- [x] 2026-07-19: Revalidate the foundational assumption with independent
  real-process, contract-sufficiency, and privacy probes. Accept the existing
  protocol transport; reject bare Trust IR as the authoritative result; select
  an additive strict runtime document followed by observed-only Trust
  projection. Root replay passes with canonical Trust SHA-256
  `947051f01cffcc1e9822de1eadb9c9b65cf59971b529ecd9c5593fab5323acb7`
  and strict counter-model SHA-256
  `a20cdace4de04229a2c6777c55f0ac51edf6c8d4891f7de830e7c91f18a0fff1`.
- [x] 2026-07-19: Run and retain the smallest relevant pre-edit baseline for protocol,
  Trust/Behavior IR, onboarding/ratchet, CLI, schemas, packaging, and claims.
  The selected 474-test slice passes under
  `.artifacts/quality/brn004-start-20260719/focused-baseline.log`.
- [x] 2026-07-19: Add retained RED/GREEN closed-contract tests and the minimum
  implementation for four exact generated documents (policy, environment,
  request, result), strict wire/context validation, content identities,
  bounded rule references, and pure observed-only Trust projection.
- [x] 2026-07-19: Add retained privacy and evidence-scope RED/GREEN tests for
  single and multi-rule secret/personal-data rejection, allowlisting, partial
  sampling, exact environment/source/adapter/procedure coordinates,
  cross-process/hash-seed determinism, observed-only non-promotion, malformed
  and oversized inputs, bounded growing-file reads, sanitized stderr/peer/
  timeout failures, and cancellation/process cleanup.
- [x] 2026-07-19: Implement the minimum two-capability out-of-process import
  client and external fixture adapter with bounded non-symlink recording
  hashing, zero-retained stderr, exact result binding, typed rejection, and
  sanitized category/code failures.
- [x] 2026-07-19: Add an installed atomic CLI scenario with capture off by
  default, immutable external inputs, hash-seed repeatability, failure
  sentinel preservation, typed rejection, observed-only projection, and
  unchanged external fixture/adapter. The package contract now requires
  exactly 20 schemas and proves the raw fixture, adapter, and forbidden values
  remain outside the wheel.
- [x] 2026-07-19: Publish generated resources, CAP-206 as a narrowly bounded
  experimental claim, and exact runtime-evidence/privacy documentation without
  claiming live collection, universal secret detection, tested evidence,
  authenticity, sandboxing, or ecosystem breadth.
- [x] 2026-07-19: Run the final 156-test affected slice, schema freshness,
  full Ruff scope, refreshed clean-install package contract, and all seven
  quality gates; inspect the scoped and repository diffs with
  `git diff --check`; obtain independent contract/projection,
  privacy/evidence-scope, and clean-distribution/claims ACCEPT reports. Update
  baseline/state and advance directly to `ECO-001`.

## Surprises & Discoveries

The accepted foundation already has two useful but deliberately separate
coordinates. Behavior IR `VerificationEvidence` can support a later exact
`tested` claim, while Trust IR `ObservedFact` represents evidence without claim
promotion. BRN-004 acceptance asks for observed enrichment, not test
attestation, so emitting new `VerificationEvidence` or `TestedClaimBasis`
prematurely would overstate the fixture recording. The foundation probe must
confirm that an observed-only overlay is sufficient.

The adapter protocol's generic `ucf.verify` operation gates only
`org.ucf.adapter.verification`. A real counter-probe successfully invoked it
when runtime evidence was merely optional and unnegotiated. The specialized
BRN-004 client must request
`org.ucf.adapter.runtime-evidence` as required and verify both negotiated
capabilities itself; putting a runtime schema URI in `AdapterPayload` is not a
capability gate.

A bare observed-only Trust overlay preserves exact Behavior subjects, source
records, and neutral facts, but its generic validator intentionally accepts
other trust records and has no typed run-level procedure, environment,
sampling, policy, or sanitization fields. The contract-sufficiency probe
demonstrated acceptance of a genuine observed `Claim`, missing coordinates,
and a 100,000-byte opaque coordinate value. A separate strict runtime document
is therefore required before projection to Trust IR.

The generic process runner drains and retains a raw 65,536-byte stderr tail,
and peer-authored protocol error prose can reach existing CLI diagnostics.
BRN-004 needs an additive command-local zero-retention mode that still drains
and counts stderr, plus category/code-only local error mapping. The truthful
privacy boundary is that forbidden values are not retained, persisted, or
emitted by UCF; an untrusted peer can still place bytes transiently in OS pipes
and process memory and is not sandboxed by this package.

Official OpenTelemetry material confirms that telemetry can contain
context-specific sensitive data, sampling can happen at several stages, and
hashing predictable identifiers is not reliable anonymization. The fixed
first profile therefore uses explicit allowlist projection and reject-only
handling for selected unsafe values, retains partial scope, and does not add an
OTel SDK, Collector, generic receiver, hash, redaction, or tokenization mode.

An independent privacy audit rejected the first green slice on two executable
edge cases. A valid two-rule policy selecting both unsafe categories fell
through the fixture adapter's singleton-set branches to a generic adapter
failure, and a recording that grew after `lstat` could be read beyond the
declared byte limit before mutation detection. Retained REDs now require all
sorted typed rejection codes and cap reads at the remaining allowance plus
one detection byte; both are green.

The wheel already auto-included generated schemas under `src/ucf`, so the
first package RED was the intended closed-inventory mismatch: 20 actual
schemas versus 16 expected. The packaging contract now names all 20, validates
their installed identities/parsers, copies the raw fixture and adapter only
into an external clean environment, and scans decompressed wheel members
rather than assuming compressed ZIP bytes reveal forbidden content.

The final contract audit confirmed that all 65 reachable object nodes in the
four generated schemas are closed. It also made two boundaries explicit:
standalone JSON Schema validates the generic capability shape while the exact
profile selection remains a named runtime semantic, and pure offline Trust
projection preserves producer traceability without authenticating it.
Authoritative imports use the full process-context validator. Neither limit
promotes a claim, and both match the published schema metadata and
authenticity disclaimer.

During concurrent independent audits, one temporary clean-install workspace
briefly retained a copied raw input under `.artifacts`. The owning audit
removed the workspace before completion. The root post-audit scan then covered
all nine retained `brn004*` artifact roots, 219 files, and 621,536 bytes with
zero forbidden-value matches. Future audits must likewise delete raw copied
inputs before retaining their evidence tree.

## Decision Log

- **2026-07-19 — start with recorded import, not live capture.** Author: root
  agent. The backlog requires optional evidence and says runtime capture needs
  an explicit environment/data decision. A caller-invoked recorded fixture is
  the smallest complete proof and keeps capture off by default.

- **2026-07-19 — reject secrets and personal data by default.** Author: root
  agent. Silent best-effort redaction would create an unverifiable privacy
  claim. The first profile must require an allowlist, fail closed on forbidden
  categories, and prove that output, errors, and logs contain no sentinels.

- **2026-07-19 — do not promote imported runtime observations.** Author: root
  agent. An adapter observation may create observed facts only. It cannot
  create declarations, mappings, tested/verified claims, or baseline
  allowances; later reconciliation and verification packages own those
  transitions.

- **2026-07-19 — keep protocol and accepted IR contracts unchanged; add an
  authoritative runtime document.** Author: root agent. Real-process evidence
  proves `ucf.verify` plus `AdapterPayload` is sufficient transport, while
  contract counterexamples prove a bare Trust document cannot strictly carry
  all import-scope coordinates. The adapter returns an exact
  `RuntimeEvidenceDocument 1.0.0`; core validates it contextually and derives
  an observed-only Trust overlay. No adapter implementation or recording
  format enters the core.

- **2026-07-19 — require the runtime capability explicitly.** Author: root
  agent. Method-level dispatch checks only the base verification capability.
  The dedicated client requests both capabilities as required, confirms both
  negotiated versions, and has no optional fallback.

- **2026-07-19 — use typed policy rejection and sanitized local failures.**
  Author: root agent. Policy rejection is a closed result status with bounded
  enum reason codes and maps to exit `1` without output replacement. Malformed,
  process, protocol, and peer failures map to category/code-only local
  diagnostics and exit `3`; peer prose and raw stderr are neither retained nor
  rendered by this command.

- **2026-07-19 — keep runtime fixtures external to the distribution.** Author:
  root agent. The wheel ships only the four generated schemas and profile
  implementation. Clean-install proof copies the raw recording and reference
  adapter outside site-packages, runs them with the installed interpreter, and
  explicitly rejects fixture names or forbidden values in decompressed wheel
  members.

- **2026-07-19 — keep projection pure and authenticity claims narrow.**
  Author: root agent. Offline projection can revalidate exact Behavior,
  environment, content identity, and rule references, but cannot reconstruct a
  past initialized process identity. The authoritative client therefore owns
  producer/capability/source contextual validation; projection emits
  traceability-only `SourceRecord` and `ObservedFact` records. Signing and
  producer attestation remain explicitly unavailable.

## Outcomes & Retrospective

BRN-004 is complete with no decision gate. The accepted result is four exact
closed profile documents, an external reference adapter, a bounded
two-capability process client, pure observed-only projection, an explicit
atomic CLI, clean-wheel execution, and a narrowly experimental public claim.

The final affected slice passes 156 tests. The complete profile under
`.artifacts/quality/brn004-final-20260719/` passes all seven phases: 46
automation tests, 1,075 Python tests at 89% coverage, clean Ruff, 113 specs
with zero errors and warnings, installed packaging, frontend build, and
frontend lint. The refreshed package contract builds byte-identical wheels at
SHA-256
`b9acd3d3204f5325228241d39dcf66e1b7957ac70882b49183cb64a669965a5d`,
installs exactly 20 schemas, and executes the external import and typed
rejection outside the checkout.

Independent contract/projection, privacy/evidence-scope, and
distribution/claims reacceptance all report ACCEPT. They independently prove
65 closed reachable schema objects, bounded growth reads, typed combined
unsafe rejection, process cleanup, two-seed deterministic installed output,
observed-only projection, exact wheel inventory, unchanged inputs, and zero
forbidden values in retained artifacts, package source, or decompressed wheel
members. The deliberately narrow residuals are documented: one synthetic
recording and fixture adapter do not establish live collection, broad
OpenTelemetry support, universal data detection, hostile-adapter isolation,
producer authenticity, or complete sampling. Dependency-ordered work now
continues at `ECO-001`.

## Context and Orientation

The stable adapter protocol lives under `src/ucf/adapter_protocol/`.
`Method.VERIFY` and `OperationKind.VERIFY_REQUEST`/`VERIFY_RESULT` carry a
Behavior IR, Trust IR, or a closed-profile `AdapterPayload` through a real
child process. The method currently requires negotiated
`org.ucf.adapter.verification`; initialization may negotiate additional named
capabilities without importing an implementation into the core.

Behavior and Trust contracts live under `src/ucf/ir/`. A
`VerificationEvidence` entity records a named check, outcome, source revision,
environment, and provenance for later tested-claim evaluation.
`ObservedFact` instead binds an exact behavior subject and neutral assertion to
an immutable `SourceRecord`. BRN-004 must not confuse those two trust levels.

The existing installed adapter workflows and atomic output conventions are in
`src/ucf/cli.py`, with external fixture adapters under
`tests/fixtures/adapters/`. Generated schemas are checked by dedicated
generators under `tools/` and installed by `tools/package_contract.py`.
Capability claims are bounded in `docs/CAPABILITIES.md`.

BRN-003 ratchet assessment imports static onboarding evidence only. BRN-004 may
produce additional observed Trust evidence, but it must not alter the accepted
ratchet baseline, infer a violation, or reinterpret touched-behavior
fingerprints.

## Plan of Work

First, retain the dependency proof, run the real-process foundation probe, and
record whether the existing verify/profile/Trust boundary is sufficient. This
milestone selected the existing protocol as transport and a separate strict
runtime document as authority. Probe adapters remain artifacts or test
fixtures; they are not core imports.

Second, run the focused pre-edit baseline. Add one strict contract behavior at
a time in Red-Green-Refactor order: fixed data policy and request/result
models, strict codec and contextual validation, deterministic Trust projection,
specialized adapter client, then privacy and scope enforcement. Generated
resources follow their generator, never manual JSON edits.

Third, add an explicit installed CLI import transaction. The command must
require recording source, data policy, exact Behavior IR, output path,
environment identity, and adapter argv. It launches no process unless invoked,
accepts only a negotiated runtime-evidence profile, validates the complete
observed-only overlay, and atomically replaces output only after success.

Finally, publish exact privacy/trust limits and a narrowly evidenced capability
row. Prove deterministic sanitized import from the unchanged fixture in a
clean wheel, run affected suites and all seven gates, review the full diff, and
obtain independent contract/privacy/clean-source acceptance before advancing.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream commands and retain logs.

Create the evidence directory and run the foundation probe before production
edits:

    mkdir -p .artifacts/quality/brn004-start-20260719
    <real-process runtime-evidence boundary probe> 2>&1 | \
      tee .artifacts/quality/brn004-start-20260719/foundation-probe.log

Retain the selected focused baseline:

    uv run --locked --extra dev pytest -q \
      tests/adapters tests/ir tests/onboarding tests/ratchet \
      tests/cli/test_adapter_conformance.py \
      tests/automation/test_capability_claims.py \
      tests/automation/test_quality_gates.py \
      --no-cov 2>&1 | \
      tee .artifacts/quality/brn004-start-20260719/focused-baseline.log

For each accepted behavior, first run the narrow new test and retain RED, then
make the minimum production change and rerun it green. Exact paths will be
recorded after the foundation selects the public boundary. Expected groups are:

    uv run --locked --extra dev pytest -q tests/runtime_evidence --no-cov
    uv run --locked --extra dev pytest -q \
      tests/cli/test_runtime_evidence.py --no-cov
    uv run --locked --extra dev pytest -q \
      tests/automation/test_capability_claims.py \
      tests/automation/test_quality_gates.py --no-cov
    uv run --locked python tools/package_contract.py

Before completion:

    uv run --locked --extra dev pytest -q <affected paths> --no-cov
    uv run --locked --extra dev ruff check src tests tools
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/brn004-final-20260719
    git diff --check

Expected observations are deterministic repeated observed-only bytes, no
forbidden sentinel anywhere in output/error/log evidence, explicit failures
for missing policy/environment/capability or forged output, unchanged input
recording/Behavior IR, and no process or output when import is not invoked.

## Validation and Acceptance

BRN-004 is accepted only when executable evidence proves:

1. runtime recording semantics stay in a capability-declaring out-of-process
   adapter; the Python core imports no adapter, OpenTelemetry SDK, framework,
   transport, or vendor implementation;
2. import is explicit and recorded-only, and ordinary validation/onboarding/
   ratchet commands start no runtime collector or evidence adapter;
3. strict versioned profile boundaries reject duplicate/unknown fields,
   incompatible versions, unsupported capability, malformed values, broken
   exact Behavior references, forged summaries, excessive bounds, and
   non-canonical order;
4. source revision, adapter name/version/procedure, exact environment digest,
   sampling description, data policy identity, and sanitization counts remain
   reproducible and traceable;
5. the reference adapter excludes unselected sentinels before its successful
   result frame and rejects selected unsafe values; forbidden bytes are not
   retained, persisted, or emitted by UCF and never appear in canonical
   output, CLI diagnostics, retained logs, or wheel assets;
6. sanitized fixture observations enrich exact subjects only as observed
   facts; no declaration, mapping, tested/verified claim, intent mutation,
   ratchet allowance, or completeness inference is emitted;
7. repeated imports and at least two `PYTHONHASHSEED` values produce
   byte-identical canonical output; sampled input is explicitly partial;
8. invalid/failed/cancelled adapter or I/O paths preserve prior output and
   clean temporary/process resources;
9. the installed wheel executes the scenario outside the checkout while the
   fixture adapter and raw recording remain external;
10. affected suites, all seven gates, full diff review, and independent
    contract/privacy/clean-source acceptance are green.

No test may use skip, xfail, warning-only enforcement, path exclusion,
baseline reset, secret replacement after import, or manual generated-output
correction.

## Idempotence and Recovery

Import must be pure for exact recording, policy, Behavior IR, environment, and
adapter coordinates. The CLI builds and validates complete canonical output
before one same-directory atomic replacement. Malformed, unsafe,
privacy-rejected, unsupported, timeout, cancellation, process, and I/O
failures leave existing output and every input unchanged and remove
package-owned temporary files.

Tests operate on copied fixtures and unique temporary directories. The raw
fixture contains recognizable sentinels solely to prove fail-closed handling;
it must never be copied into installed assets or canonical output. Generated
schemas are reproducible from their generator. Evidence directories are
append-only by milestone.

If the foundation rejects the candidate boundary, update this plan before any
public model/schema edit. At a breaking contract, production dependency, data
retention, or materially different privacy-semantics decision, stop, record
options/evidence/recommendation, and set `docs/automation/STATE.md` to
`blocked_on_decision`.

## Artifacts and Notes

Starting evidence belongs under:

- `.artifacts/quality/brn004-start-20260719/`;
- `.artifacts/agents/brn004-foundation/`.

Add concise foundation alternatives, RED/GREEN, privacy scan, deterministic
bytes, adapter-process cleanup, installed package, benchmark, and final profile
evidence as work progresses. Do not embed forbidden fixture values or long raw
logs in this plan.

Accepted foundation evidence:

- root real-process replay:
  `.artifacts/quality/brn004-start-20260719/foundation-probe-root.log`;
- root strict-profile replay:
  `.artifacts/quality/brn004-start-20260719/strict-profile-probe-root-green.log`;
- protocol/Trust transport audit:
  `.artifacts/agents/brn004-foundation/protocol-trust/report.md`;
- contract-sufficiency audit:
  `.artifacts/agents/brn004-foundation/contract-sufficiency/report.md`;
- privacy, sampling, fixture, and CLI threat review:
  `.artifacts/agents/brn004-foundation/privacy-fixture/report.md`.

Retained implementation evidence includes:

- exact policy/request/result, wire, projection, schema, process, and stderr
  RED/GREEN logs under
  `.artifacts/quality/brn004-start-20260719/`;
- missing-command CLI RED:
  `.artifacts/quality/brn004-start-20260719/cli-red-replay.log`;
- local atomic CLI GREEN:
  `.artifacts/quality/brn004-start-20260719/cli-green-attempt1.log`;
- refactored affected runtime/process/CLI slice (106 passing tests):
  `.artifacts/quality/brn004-start-20260719/runtime-cli-affected-green.log`.
- timeout/cancellation RED/GREEN:
  `.artifacts/quality/brn004-start-20260719/runtime-timeout-cancel-red.log` and
  `runtime-timeout-cancel-green-attempt1.log`;
- multi-rule unsafe-selection RED/GREEN:
  `.artifacts/quality/brn004-start-20260719/multi-unsafe-red.log` and
  `multi-unsafe-green.log`;
- growing-recording bound RED/GREEN:
  `.artifacts/quality/brn004-start-20260719/growing-recording-red.log` and
  `growing-recording-green.log`;
- exact wheel inventory and installed transaction RED/GREEN:
  `.artifacts/quality/brn004-start-20260719/package-contract-red.log`,
  `package-runtime-smoke-red.log`, and
  `package-contract-green-attempt1.log`;
- capability/documentation claim RED/GREEN:
  `.artifacts/quality/brn004-start-20260719/runtime-claims-red.log` and
  `runtime-claims-green-attempt1.log`;
- final affected/schema/lint/package/full-profile evidence:
  `.artifacts/quality/brn004-start-20260719/affected-final-green.log`,
  `runtime-schema-final-check.log`, `python-lint-final.log`, and
  `package-contract-final.log`, plus
  `.artifacts/quality/brn004-final-20260719/`;
- root retained-artifact privacy scan:
  `.artifacts/quality/brn004-final-20260719/root-retained-privacy-scan.log`;
- independent final contract/projection, privacy/evidence-scope, and
  distribution/claims ACCEPT reports:
  `.artifacts/agents/brn004-contract-projection-reacceptance/report.md`,
  `.artifacts/agents/brn004-privacy-scope-reacceptance/report.md`, and
  `.artifacts/agents/brn004-distribution-claims-reacceptance/report.md`.

## Interfaces and Dependencies

Accepted dependencies and boundaries:

- adapter protocol and conformance profile `1.0.0`;
- Behavior IR and Trust IR `1.0.0`;
- exact canonical JSON, strict decoding, digests, producer, procedure,
  environment, source, and Behavior reference primitives;
- current bounded child-process and atomic-output utilities, extended only
  with a command-local zero-retained-stderr option;
- BRN-002 onboarding and BRN-003 ratchet as immutable upstream evidence.

- negotiated `org.ucf.adapter.verification` plus
  `org.ucf.adapter.runtime-evidence` `1.0.0`;
- exact closed data-policy, import-request, and runtime-evidence result
  contracts encoded through `AdapterPayload`;
- a strict contextual validator binding result to initialized adapter,
  negotiated capabilities, exact Behavior document and subjects, local
  recording digest, environment, sampling, procedure, and policy;
- a deterministic projection from accepted runtime observations to a Trust IR
  containing only `SourceRecord` and `ObservedFact`; the runtime document is
  the authoritative scope record;
- one explicit installed import command with deterministic `0`/policy-fail/
  invalid-processing exits `0`/`1`/`3`.

No raw OTLP model, OpenTelemetry production dependency, live collector,
exporter, trace store, hosted service, mutable intent, claim promotion,
automatic ratchet decision, or VER-002 staleness semantics is authorized.
