# Build read-only inventory and evidence capture

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After BRN-001, UCF can ask an out-of-process adapter to inventory an existing
repository without inventing behavior intent or modifying the source tree. The
result is an exact-version, language-neutral snapshot containing repository
entries, build manifests, public interfaces, tests, available API
descriptions, explicit ignore decisions, deterministic diagnostics,
provenance, and confidence.

An adapter author carries inventory pages through the accepted
`ucf.inventory` operation and neutral `AdapterPayload`; the Python control
plane validates and reassembles the generic profile but does not import a
scanner or recognize a language, framework, or build tool. A checked external
fixture adapter demonstrates repeatable scans, safe ignore and symlink
behavior, bounded transport, and an unchanged fixture. BRN-001 records
observed inventory only. Candidate generation, human reconciliation, Trust IR
import, and a real Python onboarding workflow remain BRN-002.

## Foundational Assumption

The root assumption is that pre-spec repository facts can cross the existing
serialized adapter boundary as a closed, content-derived inventory profile
without fabricating a Behavior IR subject, importing ecosystem semantics into
core, or exceeding the protocol frame bound.

The cheapest useful comparison tested three available paths:

1. put raw inventory in Trust IR;
2. wrap the current in-process `ASTScanner` or `SourceScanner`;
3. carry an independently versioned `inventory_snapshot` profile through
   `AdapterPayload` and `ucf.inventory`.

Trust IR rejected the pre-behavior candidate because both its document and
observed facts require exact Behavior IR subjects. Inventing those subjects
would turn observation into intent. The generic adapter payload accepted the
same neutral data without an IR change. Disposable filesystem probes then
falsified scanner reuse: both legacy scanners read generated/vendor content
and followed a file symlink outside the root; one double-counted overlapping
patterns, one crashed on unreadable/self-loop inputs, and the other silently
omitted failures.

A real stdio probe also falsified a one-frame snapshot: a result above
1,048,576 bytes made the adapter exit `4` while the core could report only
`process_exited`. Therefore profile-level deterministic paging is required in
version `1.0.0`; silent truncation and a generic process failure are not
acceptable inventory outcomes.

The retained comparisons are
`.artifacts/agents/brn001-foundation-inventory/report.md`,
`.artifacts/agents/brn001-contract-design/report.md`, and
`.artifacts/agents/brn001-fs-threat/report.md`. No human decision gate is
present: the independent inventory profile is the only candidate that
preserves the accepted architecture and complete brownfield outcome.

## Progress

- [x] 2026-07-19: Compare Trust IR, legacy scanner reuse, and an independent
  adapter payload; retain exact representation, filesystem, and frame-bound
  evidence.
- [x] 2026-07-19: Run and retain the smallest focused baseline for protocol, legacy
  scanners, and package-owned fixture integrity.
- [x] 2026-07-19: Add RED tests and exact models/codecs/schema for inventory request,
  page, snapshot, record, provenance, confidence, policy, coverage,
  diagnostic, cursor, and reference invariants.
- [x] 2026-07-19: Add RED tests and the minimum deterministic page assembler for bounded
  frames, stable cursors, exact headers, contiguous order, cross-page refs,
  and final digest verification.
- [x] 2026-07-19: Add the neutral mixed brownfield fixture and an external reference
  adapter whose traversal prunes ignored roots before opening content, never
  follows symlinks, and emits deterministic partial diagnostics.
- [x] 2026-07-19: Prove two unchanged scans are byte-identical and leave a complete
  pre/post tree manifest unchanged; prove included and ignored mutations,
  unsafe paths, collisions, read failures, races, non-regular entries, and
  oversized inventories have explicit outcomes.
- [x] 2026-07-19: Publish the profile schema, public adapter-inventory command, package
  contract, documentation, and a capability claim limited to observed
  read-only inventory evidence.
- [x] 2026-07-19: Run affected and full gates, inspect the complete diff, obtain
  independent contract/filesystem/distribution/clean-snapshot acceptance,
  update baseline, and advance to `BRN-002`.

## Surprises & Discoveries

The existing scanner tests establish useful Python-specific behavior but not a
brownfield trust boundary. `ASTScanner` resolves candidates before reading,
which lets an in-root file symlink expose outside content under an inside path.
`SourceScanner` also follows matching file symlinks and increments its scanned
count before a read that it may silently discard. Both enumerate generated
and vendor roots because neither accepts an ignore policy.

An empty category is not the same as an unsupported category. Advertising
inventory capability `1.0.0` must mean the adapter supports all five generic
fact categories; a complete category with zero records is valid, while parse
or read failures produce partial coverage and diagnostics.

Read-only observation is not an OS sandbox or atomic filesystem snapshot.
The reference adapter can prove that its measured fixture ended byte-for-byte
unchanged and that ignored content was not opened. It cannot prove an
arbitrary third-party adapter has no write authority, that no transient write
was restored, or that a same-privilege malicious writer cannot race final
metadata checks.

Canonical inventory bytes cannot contain a wall-clock capture time. BRN-002
will create a timestamped Trust IR `SourceRecord` when it imports the immutable
snapshot into discovery and reconciliation. Mixing that capture event into
stage-one inventory would make unchanged scans differ.

The package-start slice passed 64 tests across both legacy scanner suites and
the accepted process runner. The state transition also passed all 31
automation contracts; logs are under
`.artifacts/quality/brn001-start-20260719/`.

The first adversarial model audit rejected the initial shapes because they
still admitted missing parents, evidence below ignored roots, non-file
classification refs, false completeness, unsafe portable paths, forged IDs,
and contradictory provenance digests. Each finding became a focused RED. The
corrected model derives record IDs and source revision from canonical semantic
bytes and validates topology, ignore, reference, digest, coverage, cursor, and
page coordinates. The logical request/page/snapshot schema is generated from
the authoritative models, recursively closed, and hash-seed independent. The
focused inventory slice reached 36 passing tests before the external-process
RED was opened.

An independent process review found that the provisional 100,000-page ceiling
exceeded the protocol's 65,536-request session ceiling. Initialize and
shutdown leave exactly 65,534 successful page calls. A focused RED now binds
both maximum pages and maximum records to that reachable limit; the generated
schema was refreshed and the test is green.

The first complete-profile run was insufficient acceptance evidence. Independent
audits found schema/runtime mismatches for portable paths, canonical tuples,
page/cursor coordinates, repository-entry branches, provenance spans, and
source-span ordering. Expressible rules moved into the generated schemas;
sibling span ordering is now the exact documented
`source-span-order:1.0.0` algorithm. The final contract re-audit accepts 72
focused tests and all original and follow-up differential vectors.

The first bounded-traversal audit also falsified the apparent output ceiling:
directory names and classification facts were materialized before the limit.
Traversal now consumes at most the remaining entry budget plus one overflow
probe, checks cancellation during enumeration, and accounts for entries,
provenance, classifications, ignores, and diagnostics in one output budget.
Parser `RecursionError` and parser-induced `MemoryError` originally escaped as
`internal_error`; four real-process REDs now return deterministic
fact-category `classification-failed` partial snapshots.

Global pytest collection initially imported a Python evidence fixture and
created `__pycache__` inside the inventoried root, changing its snapshot by two
records. Renaming the evidence module to a non-test name removed collection
side effects. The final clean audit also found an extra EOF blank line in an
untracked source file that ordinary changed-hunk `git diff --check` could not
see. A whole-file whitespace scan now covers all 39 BRN-001 files.

## Decision Log

- **2026-07-19 — use a separate inventory profile through the accepted
  adapter payload.** Trust IR cannot represent facts before a behavior
  document without a fabricated subject. Adding inventory to the protocol
  payload union would reinterpret protocol `1.0.0`. A schema-specific profile
  inside existing `AdapterPayload` preserves both boundaries.

- **2026-07-19 — do not wrap or refactor the legacy scanners.** Their current
  Python behavior is separately tested and user-visible, while their path,
  ignore, failure, provenance, and determinism semantics fail BRN-001. The
  generic core will validate inventory records; repository walking and all
  ecosystem recognition stay in the external fixture adapter.

- **2026-07-19 — make deterministic paging part of inventory `1.0.0`.** A
  real oversized stdio result collapses to process failure. Every page must
  fit the actual JSON-RPC frame, repeat exact snapshot coordinates, use a
  revision-bound monotonic cursor, and reassemble to one canonical digest with
  no gaps, overlaps, mixed revisions, or truncation.

- **2026-07-19 — separate content snapshot identity from capture time.**
  Canonical bytes derive from profile, explicit policy, normalized paths,
  content, producer, and extraction procedures. Timestamp and discovery
  environment belong to the later import event, not the repeatable snapshot.

- **2026-07-19 — bind profile paging to the reachable process session.**
  Inventory permits at most 65,534 pages and records so a caller using the
  minimum page limit can still complete between one initialize and one
  shutdown request. A larger logical ceiling would be unusable through the
  accepted process boundary.

- **2026-07-19 — make local schema parity explicit.** Repository entry and
  provenance coordinate branches are Draft 2020-12 conditionals. Portable
  path identity, ignore uniqueness, cursor binding, page terminal state, and
  sibling source-span order use named versioned algorithms where portable JSON
  Schema cannot express the complete comparison.

- **2026-07-19 — use one bounded traversal output budget.** Enumeration stops
  before unbounded sorting, and every emitted record category consumes the same
  60,000-record fixture budget with one reserved diagnostic slot. Exhaustion
  produces a valid partial snapshot rather than a client-error lie.

- **2026-07-19 — localize parser exhaustion as classification evidence.**
  TOML, JSON, and Python parser recursion or parser-induced memory exhaustion
  is caught only at the classifier boundary and marks the relevant fact
  category partial. Arbitrary process-wide OOM remains outside the claim.

## Outcomes & Retrospective

BRN-001 is complete. UCF now has exact request, page, and snapshot profile
`1.0.0` resources; a strict language-neutral model and page assembler; an
installed `ucf adapter inventory` command; and an external POSIX reference
adapter that demonstrates deterministic, bounded, read-only evidence capture
without importing scanner or ecosystem semantics into core.

The final local profile under
`.artifacts/quality/brn001-final5-20260719/` passes all seven gates with 34
automation tests, 810 Python tests at 88% coverage, zero Ruff findings, 113
valid specs with no errors or warnings, reproducible packaging, and green
frontend build/lint. Its wheel SHA-256 is
`42f7e9ccb55e57b12b311abd44159dc4aef09b0b8dd9b039904a2e868bbeec5b`.

The independent corrected source-only snapshot contains 534 files with
pre/post manifest SHA-256
`162edcb64f3803277130f79f0f93ec4d24ccdd24a1a4dbe8bd03bd36b4e3ea5d`.
It reproduced all seven gates and the wheel hash, found no source drift,
whitespace/conflict findings, or fixture cache, and ran the installed CLI
through the copied external adapter. The 14,973-byte result contains 26
records and 15 observed facts while the complete legacy-root manifest remains
unchanged.

Independent contract, reference-process, distribution, and clean-snapshot
reviews all report ACCEPT. The original purpose is met at the observed
inventory boundary. Candidate generation, human reconciliation, Trust IR
import, and a first baseline deliberately remain BRN-002; ratchet enforcement
remains BRN-003.

## Context and Orientation

Adapter protocol `1.0.0` is implemented under
`src/ucf/adapter_protocol/`. It already defines `Method.INVENTORY`,
capability `org.ucf.adapter.inventory`, exact negotiation, bounded
LF-delimited frames, neutral `AdapterPayload`, targeted cancellation, and
owned child processes. `AdapterPayload.value` is a tagged `IRValue`; generic
IR validation does not interpret the schema named by `schema_uri`.

Behavior and trust contracts live under `src/ucf/ir/`. Trust IR requires an
existing Behavior IR subject, so it is an import target for BRN-002 rather
than the raw inventory format. The Python-only historical scanners are
`src/ucf/scaffold/scanner.py` and `src/ucf/drift/scanner.py`; they remain
unchanged by this package.

The new language-neutral profile belongs under `src/ucf/inventory/`, its
generated schema under `src/ucf/schemas/inventory/v1/`, and focused tests
under `tests/inventory/`. The external reference traversal belongs under
`tests/fixtures/brownfield/` and must be launched through the protocol rather
than imported by core tests. Installed asset enforcement is owned by
`tools/package_contract.py`; the public command belongs under the existing
`ucf adapter` CLI group.

## Plan of Work

First retain a focused baseline and create the mixed fixture with ordinary
source, a build manifest, a test, an OpenAPI document, generated/vendor decoys,
and safe symlink metadata. Create hostile variants only in temporary copies so
the checked fixture is portable and unchanged.

Define closed logical models before traversal. Inventory `1.0.0` needs exact
request/page/snapshot coordinates; normalized relative paths; an
exclusion-only versioned policy; five coverage rows; a closed record union;
stable provenance and canonical confidence; deterministic diagnostics; and
typed references. Encode/decode those logical documents through the existing
tagged `IRValue` carried by `AdapterPayload`. Reject unknown fields, duplicate
members/identities/normalized paths, broken or wrong-kind refs, unsupported
versions/capabilities, unsafe paths, noncanonical order, and incompatible page
coordinates before presenting a snapshot.

Build the page assembler independently of filesystem scanning. RED cases cover
changed headers, cursor reuse, gaps, overlap, mixed revisions, premature
terminal pages, oversized records, final count mismatch, broken cross-page
refs, and digest mismatch. The canonical assembled snapshot must be identical
regardless of a caller's permitted page record limit.

Then implement only the reference fixture adapter traversal needed to prove
the package. It lexically normalizes and sorts entries, applies ignore rules
before descent or content open, records but never follows symlinks, streams
regular-file digests through non-following opens where available, checks
ordinary pre/post mutation, and emits stable diagnostics rather than
localized exceptions or silent omissions. Language/tool recognition stays in
that external adapter.

Finally add a public command that launches an adapter, negotiates inventory
`1.0.0`, requests all pages, validates the assembled snapshot, and writes
canonical output outside the scanned root. Package the schema, document exact
security/privacy/non-atomicity limits, update CAP-204 only to the demonstrated
inventory scope, and run independent audits plus the complete quality profile.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Retain the starting baseline under
`.artifacts/quality/brn001-start-20260719/`:

    uv run --locked --extra dev pytest -q \
      tests/unit/test_scaffold.py tests/unit/test_drift.py \
      tests/adapters/test_process_runner.py --no-cov

Each acceptance behavior gets its own RED and GREEN log. The expected focused
package commands are:

    uv run --locked --extra dev pytest -q tests/inventory --no-cov
    uv run --locked --extra dev ruff check \
      src/ucf/inventory tests/inventory \
      tests/fixtures/brownfield tools

Before acceptance:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/brn001-final-20260719
    git diff --check

Long-running commands must stream to the terminal and retained log files.
Fixture outputs and audit logs are written outside the scanned repository root.

## Validation and Acceptance

BRN-001 is accepted only when:

1. exact inventory/profile versions and schema URIs are published, and raw
   duplicate members, unknown fields, unsafe values, incompatible versions,
   and unsupported capabilities fail explicitly;
2. every fact has `observed` level, canonical confidence, stable provenance,
   producer/procedure identity, and a current content-derived revision;
3. all five required categories have explicit complete/partial coverage, and
   parse/read/classification failures become sorted closed diagnostics rather
   than disappearing;
4. generated/vendor roots are excluded only by the serialized policy, are
   pruned before content open, and changing ignored bytes does not change the
   canonical snapshot;
5. symlinks are never followed, outside-root content is never exposed,
   directory cycles terminate, non-regular objects are not opened, unsafe or
   colliding paths fail, and ordinary mid-scan mutation makes the snapshot
   explicitly incomplete;
6. two out-of-process scans of unchanged input and policy produce
   byte-identical canonical snapshots and identical diagnostics, while
   changing an included file changes only the relevant records and revisions;
7. a harness-owned pre/post tree manifest proves the reference scan left
   paths, non-following kinds, link targets, modes, sizes, mtimes, and content
   digests unchanged, with all output outside the root;
8. an inventory exceeding one frame reassembles from bounded pages to the same
   canonical bytes at different page limits; gaps, overlap, mixed revisions,
   cursor misuse, truncation, and digest mismatch fail;
9. the functional path launches the adapter process and core imports no
   scanner implementation or language/framework/build-tool semantics;
10. installed schema/CLI, affected tests, all seven gates, diff review,
    independent contract/filesystem/distribution audit, and a clean snapshot
    pass with public claims limited to the measured reference behavior.

## Idempotence and Recovery

The reference scan never writes under its root; output is caller-selected
outside that root. Page requests are immutable and revision-bound. Repeating a
page or a complete scan with unchanged bytes and policy yields the same
canonical content. A changed revision invalidates the cursor rather than
mixing results.

Temporary fixture copies, adapter processes, and output staging paths are
owned by their test or command and cleaned on failure. Atomic output replaces
only the explicitly selected destination. Interrupted work leaves the checked
fixture and legacy scanners unchanged. Generated schema output is
deterministic and checked against its generator.

## Artifacts and Notes

Foundational evidence:

- `.artifacts/agents/brn001-foundation-inventory/report.md`
- `.artifacts/agents/brn001-contract-design/report.md`
- `.artifacts/agents/brn001-fs-threat/report.md`

Final acceptance evidence:

- `.artifacts/quality/brn001-final5-20260719/`
- `.artifacts/agents/brn001-contract-reaudit/report.md`
- `.artifacts/agents/brn001-reference-acceptance/report.md`
- `.artifacts/agents/brn001-distribution-acceptance/report.md`
- `.artifacts/agents/brn001-clean-snapshot-final/report.md`

Package RED/GREEN and acceptance logs belong under
`.artifacts/quality/brn001-start-20260719/` and package-specific independent
audit directories.

## Interfaces and Dependencies

The intended exact coordinates, subject to RED-driven refinement without
changing their semantics, are:

- capability `org.ucf.adapter.inventory` version `1.0.0`;
- request URI `urn:ucf:adapter:inventory-request:1.0.0`;
- page URI `urn:ucf:adapter:inventory-page:1.0.0`;
- assembled snapshot kind `inventory_snapshot`, version `1.0.0`, and schema
  `urn:ucf:schema:inventory:1.0.0`;
- closed `InventoryRequest`, `IgnorePolicy`, `InventoryPage`,
  `InventoryCursor`, `InventorySnapshot`, coverage, provenance, confidence,
  fact, ignore-match, diagnostic, and typed-reference records;
- strict tagged-`IRValue` conversion and canonical logical snapshot bytes;
- a page assembler that consumes repeated `AdapterProcess.call(
  Method.INVENTORY, ...)` results;
- an installed `ucf adapter inventory` command accepting an argv without shell
  interpolation.

BRN-001 depends on verified `IR-001`, `IR-002`, `ADP-001`, and `ADP-002`.
No protocol or behavior/trust IR version change, scanner import, hosted
service, new production dependency, runtime capture, behavior candidate,
reconciliation, baseline, generator, framework claim, or sandbox claim is
authorized.
