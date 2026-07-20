# Publish an adapter conformance kit

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After this package, an adapter author can implement UCF protocol `1.0.0`
without importing Python or reading core source. A versioned, installed
black-box command launches an adapter, runs positive and negative fixtures,
checks capability/lifecycle/correlation/cancellation/error behavior, and
returns a deterministic machine-readable report. One minimal adapter outside
the Python ecosystem passes; deliberately faulty variants prove that the kit
rejects violations rather than merely replaying a happy transcript.

This package publishes protocol conformance only. It does not implement source
discovery, choose a framework, claim TypeScript ecosystem support, or accept an
arbitrary adapter as safe. Those outcomes remain BRN-001, ECO-001, and later
packages.

## Foundational Assumption

The root assumption is that conformance can be judged entirely at the
serialized process boundary: a runner needs only a command, protocol fixtures,
finite deadlines, and observable stdout/stderr/process outcomes. An adapter
must not import the Python core, and the runner must not inspect implementation
language or source.

Before production code, retain two comparable artifact-only candidates:

1. a black-box fixture driver that launches a dependency-free Node adapter and
   validates exact request/response exchanges and failure classes;
2. an in-process Python contract wrapper around the existing dispatcher.

Both candidates must exercise initialize, a successful operation, unsupported
capability, targeted cancellation, malformed output, and shutdown. Measure
adapter imports, fixture portability, case determinism, implementation size,
failure localization, and whether an intentionally faulty adapter can
accidentally pass. Select the black-box design only if it identifies every
case without Python imports in the adapter. If it cannot express lifecycle or
cancellation without embedding runner-specific timing assumptions, first
replace timing with explicit fixture synchronization; do not fall back to
source inspection.

## Progress

- [x] 2026-07-19: Revalidate the black-box portability assumption with comparable
  artifact-only Node and in-process candidates.
- [x] 2026-07-19: Freeze a versioned conformance manifest, case result model, exit codes,
  and compatibility rules without changing adapter protocol `1.0.0`.
- [x] 2026-07-19: Add RED tests for positive cases, each negative category, deterministic
  reports, bounded teardown, installed assets, and an adapter with no Python
  import.
- [x] 2026-07-19: Implement the smallest black-box runner and public documented command.
- [x] 2026-07-19: Publish language-neutral positive/negative fixtures, a minimal sample
  adapter, and deliberately faulty variants.
- [x] 2026-07-19: Run affected and full gates, inspect the complete diff, obtain
  independent contract/distribution/clean-snapshot acceptance, update
  baseline, and advance to `BRN-001`.

## Surprises & Discoveries

ADP-001 already publishes a structural protocol schema and one canonical
transcript, but its reference adapter lives under Python test fixtures and its
tests call Python codec/process APIs. That is evidence for the protocol, not a
consumer-facing conformance kit. The installed wheel currently exposes no
command that accepts an arbitrary adapter command and produces a versioned
conformance report.

The executable comparison confirmed that the process boundary is material,
not merely an implementation preference. The serialized candidate observed
all six required cases, rejected malformed output, localized an adapter that
accepted an unnegotiated operation, and reaped every child. The in-process
wrapper could not observe malformed bytes and let the semantic fault appear to
pass because the Python dispatcher rejected the request before invoking the
adapter. Main independently reproduced the byte-identical normalized reports:
black-box SHA-256
`e374f856d641b66d8a233d4d51da77649c48adf5c70f422cb352719c6c1bf5a7`
and in-process SHA-256
`7350db2ff0570418f87791cc1344a022a917fbba47a6e8567c6018ca01ce9d50`.

The protocol intentionally leaves operation payload semantics opaque. A
universal suite can therefore judge framing, negotiation, lifecycle,
correlation, errors, and cleanup, but cannot demand a domain-specific success
result. Positive operation and cancellation cases need a fixed, independently
versioned, test-only conformance payload profile. The retained Node probe uses
only ordinary IR values and proves cancellation readiness with a Boolean
derived from the active request ID before the runner sends `ucf.cancel`; no
sleep is the ordering oracle.

Distribution inventory found that the accepted wheel contains the adapter
protocol schema but not the transcript described as packaged by CAP-203.
ADP-002 must turn the public manifest, fixtures, schema, and dependency-free
sample into one package-owned source of truth and add an isolated-wheel RED
contract. Until that becomes green, the current phrase is an overclaim rather
than package evidence.

The first runner candidate incorrectly treated waiting and process ownership
as separate phases. Independent probes found that a successful leader could
leave an inherited POSIX descendant, a valid child could block on 2 MiB of
stderr during write or shutdown, and LF placement changed the oversized-output
coordinate. Retained RED regressions drove selector-based write/read/drain,
bounded stderr retention, a clean-completion process-group check, and one
`frame_too_large` coordinate.

Changing every process cwd to its scratch directory stopped a state-pollution
probe but broke ordinary `python adapter.py` and `node dist/adapter.js` argv.
The corrected contract preserves the explicit launch cwd and gives every case
fresh `HOME`/`TMPDIR`/`TEMP`/`TMP` scratch. This is deterministic for an
unchanged launch tree, not filesystem isolation; a candidate that mutates the
launch directory changes the next run's input.

The accepted kit has 17 manifest cases, 19 digest-indexed assets, and seven
fault profiles. Each faulty mode fails only its named case. The Node sample
and Python reference pass the same manifest. The installed wheel extracts the
kit outside the checkout, compares two exact sample reports, and runs every
fault profile; accepted wheel SHA-256 is
`0d6e7a24f4fa75735ef302cec7bddf62aba53e081b66e433b612757810db79c5`.

The first final reliability audit rejected the evidence even though the runner
suite was green: write and shutdown stderr saturation were explicit, but
receive-phase saturation was only apparent from source. A retained missing-test
RED and a 2 MiB pre-response stderr fixture closed the gap; the runner suite
now proves bounded drain in all three phases.

The checked fixture model initially admitted result coordinates that no
adapter could satisfy, including an unknown result kind and an operation
without a payload. It also advertised `shared_session` although the runner
only owns fresh processes. Retained model/schema REDs narrowed kit `1.0.0` to
the seven protocol result kinds, result-specific data, and
`isolation="fresh_process"`.

The dependency-free sample's JSON scanner used JavaScript `\s`, which accepts
NBSP even though JSON whitespace is only space, tab, LF, and CR. Replacing the
single parse-error frame with a canonical NBSP negative first made the sample
non-conformant; the exact scanner fix made both Node and Python references
green without requiring a second request after the Python server's terminal
parse error.

## Decision Log

- **2026-07-19 — select a serialized black-box conformance boundary.** The
  dependency-free Node candidate has no imports and exposes wire corruption,
  lifecycle, semantic faults, deterministic cancellation, and process
  cleanup. The in-process Python candidate imports UCF and masks both malformed
  output and a deliberately faulty adapter behind dispatcher behavior. Exact
  artifacts and twice-repeated outputs are under
  `.artifacts/agents/adp002-foundation-probe/`; main reproduction is under
  `.artifacts/quality/adp002-start-20260719/`.

- **2026-07-19 — separate universal protocol cases from a test-only operation
  profile.** Universal cases never assume opaque domain semantics. Operation
  success, blocking, readiness, release, and cancellation use one closed
  language-neutral conformance payload schema carried through the existing
  `adapter_payload` union. It changes neither protocol `1.0.0` nor behavior IR
  and is required only while an adapter is invoked for conformance.

- **2026-07-19 — preserve launch cwd and isolate declared scratch.** A fresh
  cwd prevented one deliberately stateful probe but broke relative
  interpreter-script argv, whose path cannot be generically inferred without
  rewriting user arguments. The runner preserves the declared launch cwd,
  supplies fresh per-case home/temp paths, and documents that arbitrary
  candidates remain unsandboxed.

- **2026-07-19 — use one process-ownership/drain strategy across phases.**
  Clean-shutdown and write-phase probes falsified bounded `wait()` plus later
  drain. The runner now drains while writing and waiting, bounds retained
  diagnostics, rejects surviving POSIX groups after leader exit, and maps
  both oversized response forms to `frame_too_large`.

- **2026-07-19 — publish only executable fixture coordinates.** Kit `1.0.0`
  accepts exactly initialize, five operation, and shutdown result kinds;
  validates result-specific payload/capability fields; and permits only the
  implemented fresh-process isolation mode. Future result or isolation modes
  require a new compatible contract rather than being silently ignored.

- **2026-07-19 — make non-JSON whitespace a conformance boundary.** The one
  parse-error fixture uses NBSP at an otherwise plausible member separator.
  It preserves the accepted terminal-error behavior of the Python stdio
  server while distinguishing an exact JSON scanner from JavaScript's broader
  whitespace class.

## Outcomes & Retrospective

ADP-002 is complete. An adapter author can extract the versioned manifest,
schema, 17 transcripts, dependency-free sample, and digest index from an
installed wheel, then run an arbitrary argv through the documented black-box
command. Reports are canonical and redact volatile launch data; exit classes
separate conformance, non-conformance, and runner failure. Both Node and
Python pass the same profile, and seven intentional faults fail only their
declared case.

The frozen local profile under
`.artifacts/quality/adp002-final-freeze2-20260719/` passed all seven gates:
31 automation tests, 710 Python tests at 87% coverage, Ruff, 113 specs with no
errors or warnings, reproducible packaging, and both frontend gates. The wheel
SHA-256 is
`0d6e7a24f4fa75735ef302cec7bddf62aba53e081b66e433b612757810db79c5`;
`git diff --check` is clean.

Independent contract, process, strict-JSON, distribution, and clean-snapshot
audits accepted the final result. The final source-only snapshot contains 501
files with identical pre/post manifest SHA-256
`2957ad6a8f6bfe05b41358c937489f81d1dccc68c55bdc4808ba2fb79af6ed95`.
It independently rebuilt the same wheel, ran the installed sample twice at
17/17 with byte-identical reports, localized all seven faults, and found no
whitespace or conflict markers in the 45 package-owned files.

The retrospective limit is intentional: this is exact serialized protocol
conformance, not a sandbox, domain-semantic proof, ecosystem claim, or
brownfield onboarding. Those boundaries remain assigned to later packages.

## Context and Orientation

The accepted wire contract is in `src/ucf/adapter_protocol/`, documented in
`docs/ADAPTER_PROTOCOL.md`, and represented structurally by
`src/ucf/schemas/adapter_protocol/v1/schema.json`. The current transcript is
`tests/fixtures/adapters/protocol/v1/reference-transcript.json`. The
repository-only Python reference and fault adapters are
`tests/fixtures/adapters/reference_adapter.py` and `fault_adapter.py`.

The conformance runner belongs beside the protocol client but must treat the
candidate adapter only as a command and bytes. Versioned public fixture assets
must ship in the distribution rather than depend on the repository `tests/`
tree. The CLI entry point is `src/ucf/cli.py`; package asset verification is
owned by `tools/package_contract.py`.

## Plan of Work

First run the foundational comparison and record exact evidence. Then define a
closed conformance manifest and report whose version is independent from the
adapter protocol version. Cases must declare required capability, input
exchange, expected terminal outcome, deadline, and cleanup expectation without
language-specific fields.

Add one acceptance behavior at a time. Start with installed positive fixtures
and a dependency-free Node sample. Add negative adapters for framing,
correlation, capability, error-coordinate, cancellation-origin, timeout, and
shutdown failures. Make the runner launch a fresh process per isolating case
unless the manifest explicitly tests one-session lifecycle. Reports must sort
cases deterministically, redact command/environment details, and distinguish
adapter non-conformance from runner/infrastructure failure.

Finally publish the command and assets, add isolated-wheel evidence, update
CAP-203 only to the exact conformance scope, and retain ecosystem/framework
claims as planned.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Store the foundational comparison and
RED/GREEN logs under `.artifacts/quality/adp002-start-20260719/`:

    uv run --locked --extra dev pytest -q tests/adapters --no-cov
    uv run --locked --extra dev ruff check src/ucf/adapter_protocol \
      tests/adapters tools

Before acceptance:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/adp002-final-freeze2-20260719
    git diff --check

Every long-running subprocess command must stream to the terminal and its
artifact log. A failed case must still reap the exact process group it started.

## Validation and Acceptance

ADP-002 is accepted only when:

1. an adapter author can discover the installed manifest, fixtures, schema,
   sample, and command without the repository test tree;
2. the sample adapter uses no Python runtime, UCF package import, or
   implementation-language field in protocol payloads;
3. the runner passes the sample and the existing reference process through the
   same serialized cases;
4. each intentionally faulty adapter fails the exact named case and cannot be
   accepted through warning, skip, timeout ambiguity, or report rewriting;
5. repeated runs with the same command and environment produce byte-identical
   normalized reports apart from no undeclared volatile field;
6. cancellation, timeout, malformed output, stderr, and process descendants
   remain bounded and leave no child;
7. isolated installed-wheel, all seven repository gates, and an independent
   clean snapshot pass, while public claims remain protocol conformance rather
   than ecosystem support.

## Idempotence and Recovery

Each conformance case owns a fresh temporary directory and process group.
Interrupted runs terminate only their owned processes and leave published
fixtures unchanged. Generated fixture indexes and reports are deterministic
and checked byte-for-byte. The runner never edits the candidate adapter or
uses successful output from one case as hidden state for another.

## Artifacts and Notes

ADP-001 acceptance evidence is under
`.artifacts/quality/adp001-settled-full-20260719/`,
`.artifacts/agents/adp001-contract-reaudit/`,
`.artifacts/agents/adp001-process-reaudit/`,
`.artifacts/agents/adp001-distribution-audit/`, and
`.artifacts/agents/adp001-clean-snapshot/`.

ADP-002 artifacts belong under
`.artifacts/quality/adp002-start-20260719/`,
`.artifacts/quality/adp002-final-freeze2-20260719/`,
`.artifacts/agents/adp002-final-contract/`,
`.artifacts/agents/adp002-final-reliability-rerun/`,
`.artifacts/agents/adp002-final-isolation-audit/`,
`.artifacts/agents/adp002-json-whitespace-audit/`, and
`.artifacts/agents/adp002-clean-snapshot-final2/`.

## Interfaces and Dependencies

Expected contracts, subject to the foundational comparison, are:

- an independent conformance-kit version and exact adapter protocol version;
- a closed, language-neutral case manifest and deterministic result report;
- an installed black-box runner accepting an argv command without shell
  interpolation;
- versioned positive and negative fixture assets;
- a dependency-free non-Python sample adapter and deliberately faulty modes;
- stable exit classes for conformant, non-conformant, and runner-failure
  outcomes.

No framework parser, source scanner, hosted service, sandbox claim, production
dependency, protocol-version relaxation, or language-specific core field is
authorized by this package.
