# Prove an out-of-process adapter protocol

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After this package, UCF can launch an adapter as a separate process, negotiate
an exact protocol version and named capabilities, exchange language-neutral
inventory, discovery, mapping, generation, and verification messages, cancel
an in-flight request, and receive stable structured errors. The Python core
does not import an adapter implementation or contain language, framework,
build-tool, or runtime semantics.

This package proves the protocol and one minimal reference process. It does not
publish the full ecosystem-facing conformance kit, perform real source
discovery, select a framework, or claim production support for a language
stack; those outcomes belong to ADP-002 and later brownfield/ecosystem
packages.

## Foundational Assumption

The root assumption is that a deliberately small request/response protocol over
standard input/output can provide deterministic framing, capability
negotiation, cancellation, and structured failures without embedding transport
or adapter implementations in the behavior/trust IR.

Before production code, compare two dependency-free executable prototypes over
the same subprocess pipe:

1. a strict JSON-RPC 2.0 subset with request IDs, method names, result/error
   exclusivity, notifications, and a cancellation notification;
2. a simpler custom newline-delimited envelope with explicit
   `request|response|error|cancel` message kinds.

Each prototype must perform initialize/negotiation, one successful operation,
one unsupported-capability request, one malformed request, and cancellation of
a deliberately blocked request. Retain exact bytes, implementation size,
failure classification, framing behavior, and shutdown behavior. JSON-RPC is
selected only if its standard identity/error/cancellation vocabulary removes
more ambiguity than its additional validation costs. The custom envelope is
selected if it proves the same behavior with a materially smaller and equally
precise contract. If neither survives truncated output, unsolicited stdout, or
cancellation without deadlock, test length-prefixed framing before changing
production code.

## Progress

- [x] Revalidate the foundational assumption with comparable JSON-RPC and
  custom-envelope subprocess probes.
- [x] Specify an exact-version closed protocol, stable method/capability names,
  correlation rules, structured errors, lifecycle, and compatibility policy.
- [x] Add RED transport-independent codec/dispatcher contract tests, including
  malformed, unknown, duplicate, incompatible, and unsupported inputs.
- [x] Add RED process-runner tests for negotiation, deterministic exchange,
  cancellation, timeout/termination, stderr isolation, and clean shutdown.
- [x] Implement the smallest reference adapter process without importing it
  into the core and prove every required operation through declared
  capabilities.
- [x] Publish schema/fixtures/API/CLI or test-runner documentation with exact
  limitations, package assets, and CAP-203 evidence appropriate to ADP-001.
- [x] Run affected and full gates, inspect the complete diff, obtain
  independent protocol/security and clean-snapshot acceptance, update
  baseline, and advance to `ADP-002`.

## Surprises & Discoveries

Repository inspection found no existing adapter, RPC, subprocess protocol, or
capability-negotiation implementation. `src/ucf/models/protocol.py` is a source
declaration model for application protocols, not an adapter control-plane
transport and must not be reused as one by convention.

Behavior IR and trust IR already provide exact serialized document identities,
evidence coordinates, and capability requirements. The adapter protocol should
carry or reference those public documents; it must not reinterpret their
semantics or add language-specific fields to them.

The retained dependency-free subprocess comparison found that both newline
candidates failed closed and reaped the child after unsolicited stdout,
classified truncated input as a parse failure, correlated a blocked request
with its cancellation, and shut down without deadlock. The custom envelope was
not materially smaller: its candidate-specific codec was 90 executable lines
and the common 13-frame transcript was 1,202 bytes, versus 89 lines and 1,138
bytes for JSON-RPC. The result removes the reason to invent independent
request/response/error correlation semantics. See
`.artifacts/quality/adp001-start-20260719/protocol-candidate-probe.log`.

An independent comparison reached the same conclusion using separate
standalone workers and twice-reproduced byte artifacts. Its custom envelope
saved only 4.19% implementation lines, 5.26% validation lines, and 6.25% wire
bytes. See `.artifacts/agents/adp001-wire-probe/report.md`.

The independent threat probe reproduced two non-obvious failures: a child that
fills stderr before replying deadlocks a stdout-only parent, and ordinary
environment inheritance exposes a sentinel secret. It also demonstrated
partial output at EOF and a stdout log preceding a syntactically valid frame.
The runner therefore must drain stderr concurrently, launch with an explicit
minimal environment and working directory, reject protocol contamination
instead of resynchronizing, and terminate its dedicated process group under
finite bounds. See `.artifacts/agents/adp001-threat-review/report.md`.

The first process RED contract incorrectly assumed that stdout response arrival
implies all earlier stderr bytes have already reached the parent's retained
counter. An independent 40-run probe observed stdout after 786,432 of
1,048,576 stderr bytes every time; distinct pipes provide no cross-stream
ordering. The acceptance test now asserts the complete count only after
shutdown/EOF drain. The same review caught an attempted conflation of non-zero
exit with ordinary unexpected EOF; these remain distinct
`process_exited`/`unexpected_eof` outcomes. See
`.artifacts/agents/adp001-runner-review/report.md`.

Nested Behavior IR and Trust IR models perform structural Pydantic validation
but do not automatically run their graph/reference validators. A RED payload
test demonstrated that broken Behavior roots, broken Trust traces, and
duplicate adapter record entries crossed the first wrapper. Operation
params/results now call the accepted semantic validators (and a public
standalone IR-value validator), so carrying a document cannot bypass the same
trust boundary as parsing it directly.

The first independent post-implementation contract audit rejected four
apparently green behaviors. The dispatcher forgot completed IDs and therefore
violated the already selected lifetime-unique identity rule. Peer error
validation checked only local-only categories, allowing a local code to hide
under another category. Both sides accepted `request_cancelled` without proof
that the exact request had received a client cancellation. Finally, teardown
only signalled a POSIX process group while its leader was still running, so an
early-exited leader could leave a pipe-holding descendant alive. Each finding
was reproduced by a focused RED test before changing production code. The
dispatcher now retains session IDs and checks the cancellation event; error
data enforces a one-to-one category/code matrix; the client records
cancellation on each pending operation; and teardown probes and terminates the
dedicated process group even after the leader exits. The same audit also
exposed that IEEE `NaN` and positive infinity passed a positivity-only timeout
check, so all configured and per-call deadlines now require finite positive
numbers.

The re-audit then found three deeper contract/runtime assumptions that the
initial suite had not challenged. Converting arbitrarily long canonical
version segments to Python integers made negotiation depend on CPython's digit
limit; comparison now uses decimal segment length and lexical order without a
machine integer. Exact lifetime ID retention was linearly unbounded; protocol
1.0.0 now accepts at most 65,536 requests per process and reserves the final
slot for shutdown. Finally, the standalone stdio server discarded detached
write failures and could wait forever on an unrelated open stdin. A bounded
one-frame handoff from a single fd-reading daemon thread lets the event loop
race input against fatal task completion, while a real-pipe regression proves
exit code 4 with stdin deliberately held open.

Asyncio task cancellation exposed a separate ownership invariant: cancelling
startup, shutdown, or a one-shot call stranded live children or pending
correlations. RED probes now cover all three lifecycle points, invalid
deadlines before send, invalid environment names before spawn, inaccessible
future cleanup, repeated public close, and early-exited process-group leaders.
The final process re-audit records zero pending slots, zero unhandled loop
contexts, and no surviving child for every cancellation path.

The first clean-snapshot attempt rejected CAP-203 because its documentation
named only the aggregate adapter test directory while the automation contract
requires the exact protocol codec test path. Restoring the literal focused
command made the retained 29-test automation suite green before a completely
new snapshot was created. A stronger empty-tree whitespace probe then exposed
143 historical findings in 39 unrelated files. The normative changed-line
check and a whole-file scan over every ADP-001-owned path pass, so the
historical findings are recorded as unrelated debt rather than rewritten in
this package.

## Decision Log

- **2026-07-19 — select a strict JSON-RPC 2.0 subset over newline-delimited
  UTF-8 stdio.** Both executable candidates satisfied the same initialization,
  success, unsupported-capability, malformed-input, cancellation, contaminated
  stdout, truncated-input, and shutdown scenarios. The custom candidate saved
  neither implementation surface nor wire bytes, while JSON-RPC supplies
  standardized request IDs, notification semantics, result/error exclusivity,
  and parse/request/method/params error codes. The authoritative JSON-RPC 2.0
  specification is `https://www.jsonrpc.org/specification`; the official
  Language Server Protocol documentation at
  `https://microsoft.github.io/language-server-protocol/` is primary precedent
  for adding cancellation to a JSON-RPC protocol. Newline framing, finite size
  and depth limits, UCF protocol-version negotiation, and the `ucf.cancel`
  notification are UCF contracts rather than claims about JSON-RPC itself.
  JSON-RPC batch requests, numeric or null request IDs, array parameters, and
  arbitrary notifications are outside this package. Length-prefix framing is
  rejected for now because both newline candidates detected malformed frames
  and contamination without ambiguity or deadlock; it would add a binary
  framing state machine without evidence of need.

- **2026-07-19 — freeze the ADP-001 logical surface.** Protocol `1.0.0`
  contains exactly `ucf.initialize`, `ucf.inventory`, `ucf.discover`,
  `ucf.map`, `ucf.generate`, `ucf.verify`, `ucf.cancel`, and `ucf.shutdown`.
  The five operation methods require, respectively,
  `org.ucf.adapter.inventory`, `.discovery`, `.mapping`, `.generation`, and
  `.verification`. Initialize requests carry unique qualified capability
  names, minimum normalized versions, and required/optional status; the
  immutable selected set is a duplicate-free subset that meets every required
  minimum. Additional qualified semantic capabilities remain opaque to the
  core. Operation params/results use closed, operation-specific discriminator
  values around one of three payloads: an accepted Behavior IR document, an
  accepted Trust IR document, or a tagged adapter payload with independent
  schema URI/version and a closed IR value. This keeps language/framework
  content out of the control plane while avoiding a second undocumented
  protocol inside an arbitrary JSON object. The independent surface analysis
  and negative matrix are retained at
  `.artifacts/agents/adp001-surface-review/report.md`.

- **2026-07-19 — use exact protocol compatibility and bounded resource
  ownership.** `1.0.0` accepts only `1.0.0`; capability minimum versions,
  adapter implementation versions, payload schema versions, Behavior IR, and
  Trust IR remain independent coordinates. Frames are exactly one UTF-8 JSON
  object ending in LF and at most 1,048,576 bytes including LF; empty,
  partial-at-EOF, BOM, invalid UTF-8, duplicate-member, noncanonical-number,
  array/batch, unknown-field, and contaminated stdout input fail closed.
  Request IDs are core-created ASCII strings of at most 64 bytes, unique for
  the child lifetime, and never reused; at most 64 requests are pending.
  Stderr is continuously drained by chunks with total byte count and only its
  final 65,536 bytes retained. Initialize, write, operation, cancellation,
  shutdown, TERM, KILL, and reap waits are always finite. On POSIX the child
  starts in a dedicated session and teardown targets that process group before
  awaiting the direct child. The boundary is not an OS sandbox and capability
  declaration is not implementation proof; ADP-001 launches only the
  repository-owned reference process.

- **2026-07-19 — distinguish peer errors from local process outcomes.**
  JSON-RPC base numeric codes retain their standard meanings and
  `error.data.ucf_code` is the normative stable UCF code. Peer-originated
  outcomes can be protocol, adapter, or cancellation failures. Only the local
  runner may report timeout, EOF, invalid adapter output, start/exit, I/O, or
  termination failures; a peer cannot forge them. Human messages are bounded
  diagnostics, not the machine contract.

## Outcomes & Retrospective

ADP-001 delivers an exact experimental adapter protocol `1.0.0`: eight closed
JSON-RPC methods over single-LF frames, five opaque language-neutral operation
families, exact capability negotiation, canonical request/result/error
coordinates, transport-independent dispatch, targeted cancellation, and a
bounded separately launched process client/server. The Python core imports no
adapter implementation; the repository reference adapter is a launched test
fixture. The deterministic Draft 2020-12 schema and complete transcript ship
in the wheel.

The settled local profile under
`.artifacts/quality/adp001-settled-full-20260719/` passes all seven gates with
641 Python tests at 87% coverage, 113 accepted specs with zero errors or
warnings, and reproducible wheel SHA-256
`94fba0a69b79078fb9f030a1598a70fb1045358729808b838bf2a427949cfd51`.
The focused adapter contract has 102 tests. Independent contract,
distribution, and process audits accept the wire semantics,
schema/package/docs, and lifecycle/resource ownership. The independent clean
snapshot under `.artifacts/agents/adp001-clean-snapshot/` accepts the exact
470-file manifest
`99e402b599aabffeaca79b7ff8b90cb7bac6b78a0cbaa3e48e65bd3b707f76e0`;
all seven gates reproduce the same counts and wheel hash, schema generation
is current, protocol imports remain neutral, and the pre/post source manifests
are byte-identical.

The most valuable result was the rejected-green feedback loop. Existing green
tests missed runtime-specific version conversion, unbounded completed-ID
retention, forged cancellation, coroutine cancellation leaks, early-leader
process groups, and a real-pipe server deadlock. Retained RED cases now make
those constraints executable. ADP-001 deliberately does not claim a public
conformance kit, arbitrary adapter sandbox, cross-runtime implementation,
Windows process-tree parity, or ecosystem support; those boundaries remain
ADP-002 and later work.

## Context and Orientation

The accepted language-neutral behavior model is under `src/ucf/ir/`; its trust
overlay and exact evidence predicates are documented in `docs/IR.md`. The
Python package is the reference control plane. Adapter-owned language,
framework, build, and runtime knowledge must live in a separately launched
process.

Protocol production code should live in a clearly named package such as
`src/ucf/adapter_protocol/`, separate from both IR models and any reference
adapter fixture. Language-neutral protocol fixtures belong under
`tests/fixtures/adapters/`; focused contract/process tests belong under
`tests/adapters/`. A reference adapter may be implemented as a test fixture
executable, but the control plane may know only its command, wire contract, and
declared capabilities.

## Plan of Work

First retain the two executable protocol candidates and attack their framing,
correlation, capability, cancellation, and error behavior. Record the selected
contract and rejected alternative in this plan before writing production
models.

Then implement one acceptance behavior at a time. Start with strict decoded
messages and protocol-version negotiation. Add finite method/capability
declarations and reject calls not negotiated. Add transport-independent
dispatch before subprocess I/O. Finally add process lifecycle, concurrent
correlation, cancellation, timeout, stderr, EOF, and termination behavior.

The reference adapter implements only the minimum deterministic operations
needed to prove the five capability families. Payloads remain opaque
language-neutral JSON or accepted UCF IR documents at this layer. Do not add a
scanner, generator backend, framework parser, or runtime collector merely to
make method names appear exercised.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Retain the foundational comparison and
RED/GREEN logs under `.artifacts/quality/adp001-start-20260719/`:

    uv run --locked --extra dev pytest -q tests/ir tests/automation --no-cov
    uv run --locked --extra dev ruff check src/ucf/ir tests/ir tools

Before acceptance:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/adp001-final-20260719
    git diff --check

## Validation and Acceptance

ADP-001 is accepted only when:

1. the selected framing and compatibility rules are exact, deterministic, and
   reject unknown fields, duplicate identities, malformed messages, and
   incompatible versions with stable errors;
2. initialization negotiates a finite capability set and an operation without
   its negotiated capability fails before adapter semantics run;
3. inventory, discovery, mapping, generation, and verification requests cross
   a real process boundary without the core importing the reference adapter;
4. multiple request IDs correlate correctly, cancellation reaches the exact
   in-flight request, timeout/EOF/invalid output cannot deadlock the caller,
   and shutdown reaps the process;
5. adapter failures, protocol failures, cancellation, and process failures are
   distinguishable structured outcomes; stdout is protocol-only and stderr is
   diagnostic-only;
6. the same codec/dispatcher contract suite runs without a subprocess
   transport, proving protocol semantics are not owned by stdio;
7. all seven repository gates and an independent clean snapshot pass, and
   public claims stop at the exact reference-protocol evidence.

## Idempotence and Recovery

Protocol fixtures and probe outputs are deterministic and may be regenerated
only at their explicit artifact paths. Process tests must use bounded waits and
always terminate/reap children in cleanup. A failed or cancelled request must
not corrupt later correlation. Interrupted schema/fixture generation is caught
by byte-freshness tests. No cleanup command may kill processes outside the
specific child PID started by the test.

## Artifacts and Notes

IR-002 acceptance evidence is under
`.artifacts/quality/ir002-final-20260719/`,
`.artifacts/agents/ir002-contract-audit/`,
`.artifacts/agents/ir002-distribution-audit/`, and
`.artifacts/agents/ir002-clean-snapshot/`.

ADP-001 foundational, RED/GREEN, and final evidence belongs under
`.artifacts/quality/adp001-start-20260719/` and later package-specific audit
directories.

## Interfaces and Dependencies

Expected contracts, subject to the foundational comparison, are:

- an exact adapter-protocol version and closed request, result, notification,
  and error envelopes;
- finite operation and capability identifiers for inventory, discovery,
  mapping, generation, and verification;
- initialize/negotiation and shutdown lifecycle messages;
- correlation-safe cancellation and stable error categories;
- a transport-independent codec/dispatcher contract plus a stdio subprocess
  runner;
- a separately launched minimal reference adapter and deterministic fixtures.

No production dependency, hosted service, socket transport, adapter
implementation import, language parser, framework convention, build-tool
integration, or runtime probe is authorized without new evidence and, where
applicable, the decision policy in `AGENTS.md`.
