# VER-002 Exact Evidence Loop

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect the current
repository evidence. Maintain it according to `PLANS.md`.

## Purpose / Big Picture

After this package, a user can attach one reproducible verification result to
the exact behavior, source revision, adapter version, environment, and checked
procedure that produced it. Drift comparison then marks only genuinely
affected evidence stale: an unrelated source or specification edit does not
erase valid evidence, while a relevant change does. Re-running the named check
against the new coordinates restores a `tested` claim without promoting it to
`verified`.

## Foundational Assumption

The root assumption is that the accepted Behavior IR `1.0.0`, Trust IR
`1.0.0`, adapter protocol `1.0.0`, and implementation-evidence profiles already
carry sufficient neutral coordinates; the missing product behavior is an exact
evidence-envelope and drift projection rather than a protocol or Behavior IR
redesign.

Challenge this before production edits with the cheapest useful experiment:
construct one existing passed execution/mapping result and its Trust
projection, then replay current drift functions across four snapshots:
unchanged, unrelated-source change, target-source change, and target-behavior
change. Inventory which exact coordinates survive serialization and whether
the current code can name the affected behavior without path-wide or
document-wide guessing. Retain byte-level inputs, outputs, and a
field-sufficiency matrix under
`.artifacts/quality/ver002-start-20260720/`.

Alternatives are: conservatively invalidate every claim for any repository
change; add a separate versioned verification-evidence document while keeping
Trust IR unchanged; or revise Trust IR itself. Select the smallest alternative
that can reject stale context and preserve unrelated evidence. If the probe
requires reinterpreting an accepted serialized field, record a compatibility
decision and stop at the applicable human decision gate before implementation.

## Progress

- [x] 2026-07-20: Verify VER-001 with independent audits, a post-hardening
  seven-gate profile, main-agent scope review, and physical clean-source replay;
  create this plan and set VER-002 active.
- [x] 2026-07-20: Revalidate the foundational assumption with root and independent
  read-only probes; record exact field sufficiency, false-invalidation
  counterexamples, alternatives, and the selected boundary.
- [x] 2026-07-20: Freeze positive and negative resources for revision-, behavior-,
  producer-, adapter-, environment-, procedure-, mapping-, and result-bound
  evidence plus selective staleness and refresh.
- [x] 2026-07-20: Implement one acceptance behavior at a time under retained
  Red-Green-Refactor evidence, then integrate installed CLI/package behavior.
- [x] 2026-07-20: Publish only the bounded evidence-loop claim; complete independent
  contract/security/correctness audits, affected suites, all seven gates,
  complete diff review, and physical clean-source replay.

## Surprises & Discoveries

Existing green ecosystem checks prove adapter-attested `tested` claims for
frozen fixtures, but they do not by themselves prove selective invalidation or
refresh across revisions.

Root repeated the independent four-snapshot probe under `PYTHONHASHSEED=1` and
`777`; both canonical outputs are byte-identical at SHA-256
`04a7d397ed3a3b0ad771f989b18035edab7cbffaf0a7166a1540d976695f1caa`.
The current legacy drift detector reports no stale mapping for either relevant
or unrelated changes. Historical Trust alone remains valid after target-source
drift (false fresh); rebinding it to a new repository-wide revision or Behavior
document invalidates unrelated changes (false stale).

The exact implementation mapping and execution result retain all raw neutral
coordinates, but their current validators intentionally bind whole Behavior
and inventory documents. The Trust projection drops typed mapping/result
references, selected capability, adapter procedure, structured environment,
and bound inventory records. Therefore neither weakening existing validation
nor reinterpreting Trust IDs can close the loop.

The first complete implementation audit exposed two trust-boundary bypasses:
exact Pydantic model instances could carry hidden state through `model_copy`,
and an assessment validator returned the untrusted instance rather than its
canonical reparse. Focused retained REDs now require recursive outbound
revalidation before identity, comparison, or publication.

There is no valid `1.0.0` transition in which a selected capability version
changes while the same accepted capability remains supported. Publishing a
`capability_changed` reason would therefore promise an unreachable state.
The final closed reason taxonomy omits it; adapter, mapping-adapter, and
supported version mismatches remain explicit context failures or exact
reachable adapter-change reasons.

Atomic replacement alone was insufficient for first publication: two
concurrent writers could both observe an absent path. The accepted local
POSIX boundary publishes a flushed same-directory temporary file with a
no-replace hard link, accepts an identical winner idempotently, rejects a
different winner, and fsyncs the directory. The documentation does not claim
this guarantee for Windows or network filesystems.

## Decision Log

- **2026-07-20 — challenge coordinate sufficiency before selecting a new
  resource.** Author: root agent. Existing Trust and implementation-evidence
  documents are accepted dependencies, not evidence that they model a durable
  verification ledger. No schema or version change is selected until a real
  four-snapshot counterexample shows the smallest missing boundary.
- **2026-07-20 — add a separate evidence envelope and freshness assessment
  `1.0.0`; preserve every accepted upstream version.** Author: root agent.
  Root and three independent probes agree that the immutable mapping/result
  resources contain sufficient historical inputs while Trust alone is too
  lossy and whole-document comparison is too coarse. The new core-derived
  boundary will freeze an explicit reviewed Behavior-materialization closure,
  the selected mapping binding and transitive content-addressed inventory
  records, exact adapter/capability/procedure/environment/check coordinates,
  and typed result/claim references. Assessment compares the same projections
  from a separately validated current mapping/request and returns `fresh`,
  `stale`, or `indeterminate` with closed exact reasons. Whole Behavior,
  inventory, and source-revision digests remain trace coordinates, not
  standalone stale predicates. This is additive, uses no new dependency, and
  reaches no human decision gate.
- **2026-07-20 — keep the v1 status vocabulary reachable and exact.** Author:
  root agent. Remove the unreachable `capability_changed` status rather than
  exposing an untestable public reason. Valid selected-capability context is
  revalidated exactly; supported producer changes remain represented by the
  adapter-specific reasons.
- **2026-07-20 — bound first-publication concurrency to a local POSIX
  filesystem.** Author: root agent. Use a same-directory no-replace hard-link
  commit with file and directory durability, and document the operating-system
  boundary. Cross-platform/network-filesystem atomicity is not inferred from
  Linux test evidence.

## Outcomes & Retrospective

VER-002 is complete. It delivers exact closed evidence-envelope and freshness-
assessment `1.0.0` resources, deterministic identities, selective behavior/
source/mapping/execution projections, passed-only refresh, historical stale
retention, and installed `ucf evidence record|assess` behavior. Unknown state,
duplicates, broken or forged references, incompatible versions, unsupported
capabilities, partial contexts, output aliases, and conflicting concurrent
publication fail before replacing output. No path emits a `verified` claim.

The retained Red-Green-Refactor and audit evidence is under
`.artifacts/quality/ver002-start-20260720/` and
`.artifacts/agents/ver002-contract-review/`. The final working-tree profile at
`.artifacts/quality/20260720T155500Z/` passes 75 automation tests, 1,880 Python
tests at 90% coverage, Ruff, 113 specifications with zero errors/warnings,
clean installed packaging, frontend build, and frontend lint. The two wheel
builds are byte-identical at SHA-256
`7311760bf249ad195dbb30ad563cafeddbfee77921851ba5a154ea91ef9cb2ec`.

Physical acceptance under
`.artifacts/agents/ver002-clean-source-snapshot/20260720T160959Z-ver002/`
copies 996 regular source files into a fresh source-only directory, installs
both dependency locks, repeats all seven gates, and preserves identical
checkout/snapshot manifests before and after. The source manifest SHA-256 is
`d392c673ca85ff30319acd13e674136f43e7c0c8dcd0854ea7ad10cefbc83e1c`.
The two earlier pre-copy orchestration attempts are explicitly rejected and
were not used as acceptance evidence. Behavior IR, Trust IR, adapter protocol,
and implementation-evidence `1.0.0` remain unchanged; no human decision gate
was reached.

## Context and Orientation

Canonical Behavior and Trust models live under `src/ucf/ir/`. Trust records
separate declared intent, observed facts, mappings, tested claims, and verified
claims; their schema assets are under `src/ucf/schemas/trust/`.
Adapter-produced mapping and verification request/result resources live under
`src/ucf/implementation_evidence/`, with process orchestration in
`src/ucf/adapter_protocol/` and ecosystem-specific execution in `adapters/`.
Current drift utilities are under `src/ucf/drift/`; the older public CLI
surface is assembled in `src/ucf/cli.py`.

“Fresh” means every coordinate needed to reproduce the checked property still
matches: exact behavior subject/revision, observed source revision, mapping,
adapter name/version and selected capability, environment, procedure, and
verification result. “Stale” is a derived comparison outcome, never deletion
or silent claim promotion. A digest provides identity and traceability, not
signing or authenticity.

## Plan of Work

First, inventory the existing serialized coordinates and execute the
four-snapshot falsification probe. Compare precise per-behavior invalidation
with coarse repository-wide invalidation and a new resource. Record the
selected boundary before writing a failing production test.

Second, freeze exact canonical positive and negative fixtures. Cover unchanged
replay, unrelated source/spec changes, target source/spec changes, adapter and
environment changes, broken references, duplicates, unknown fields,
incompatible versions, noncanonical order, unsupported capabilities, forged
claim levels, and refresh with a new passed result.

Third, implement only the chosen language-neutral evidence loop. Parse and
contextually validate before deriving identities or mutating output. Keep
adapter semantics out of core; consume only exact serialized facts and
capabilities. Derive staleness without deleting prior evidence, and require a
fresh reproducible passed check to emit a replacement `tested` claim.

Fourth, expose the smallest installed workflow and package its schemas. Add a
clean installed scenario that records evidence, demonstrates selective stale
and unaffected outcomes, refreshes the stale behavior, and proves no
`verified` promotion.

Finally, complete independent contract and security/correctness audits, close
every accepted finding with a focused retained RED, run affected and full
gates, inspect the complete admitted diff, and repeat the physical source-only
snapshot protocol before advancing to REL-001.

## Concrete Steps

Work from `/home/deliner/projects/ucf` and stream evidence:

    mkdir -p .artifacts/quality/ver002-start-20260720
    git status --short | tee \
      .artifacts/quality/ver002-start-20260720/git-status-start.log
    uv run --locked --extra dev pytest -q \
      tests/implementation_evidence tests/ir tests/unit/test_drift.py \
      --no-cov --capture=tee-sys | tee \
      .artifacts/quality/ver002-start-20260720/focused-baseline.log
    uv run --locked --extra dev ruff check \
      src/ucf/implementation_evidence src/ucf/ir src/ucf/drift \
      tests/implementation_evidence tests/ir tests/unit/test_drift.py | tee \
      .artifacts/quality/ver002-start-20260720/focused-ruff.log

Record the root probe and independent findings beside these logs. Each
production behavior starts with a focused test that fails for the intended
missing evidence-loop behavior, followed by the minimum implementation,
focused green, touched-design refactor, and affected suite.

Before acceptance run:

    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/ver002-final-20260720
    git diff --check

## Validation and Acceptance

VER-002 is accepted only when fresh executable evidence proves:

1. one exact passed check binds behavior, source revision, adapter
   name/version, selected capability, environment, procedure, mapping, and
   result without relying on Python-specific fields;
2. unchanged replay is deterministic and an unrelated source or specification
   change leaves the unaffected behavior evidence fresh;
3. a relevant source, intent, mapping, adapter, environment, procedure, or
   result change makes only the dependent evidence stale with an inspectable
   reason;
4. stale evidence remains historical data but cannot support a current
   `tested` or `verified` display;
5. a new passed reproducible check against the current coordinates restores a
   `tested` claim, while failures and lower-level facts cannot promote it and
   no path promotes anything to `verified`;
6. unknown fields, duplicate members/identities, incompatible versions,
   broken references, noncanonical input, unsupported capabilities, and forged
   or mismatched context fail explicitly before output publication;
7. schemas, CLI behavior, package assets, documentation, and public capability
   claims are exact and installed from the wheel;
8. affected suites, all seven gates, independent audits, complete diff review,
   and physical clean-source replay pass without skips, warnings, exclusions,
   baseline resets, or hand-edited output.

## Idempotence and Recovery

The foundation probe is read-only with respect to source and writes only
evidence under `.artifacts/` and disposable temporary workspaces. Evidence
derivation is pure and deterministic. Installed commands publish only complete
canonical files through the repository's accepted atomic file boundary;
failure preserves existing output. A retry with exact inputs is byte-identical.

Staleness never destroys or rewrites old evidence. Refresh creates a new
content-bound record for current coordinates. If a public-contract,
dependency, migration, security, or product-semantics gate appears, record
options, evidence, consequences, and a recommendation here, set
`docs/automation/STATE.md` to `blocked_on_decision`, and make no speculative
migration.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/ver002-start-20260720/`;
- `.artifacts/agents/ver002-coordinate-inventory/`;
- `.artifacts/agents/ver002-drift-counterexamples/`;
- `.artifacts/agents/ver002-contract-review/`;
- `.artifacts/agents/ver002-clean-source-snapshot/`.

Do not retain credentials, private source, raw sensitive runtime payloads,
dependency caches, or unbounded process output.

## Interfaces and Dependencies

Accepted upstream contracts are Behavior IR, Trust IR, adapter protocol,
implementation-evidence mapping/verification profiles, ecosystem/platform
adapters, OpenSpec lifecycle/governance, and generation resources at their
current accepted versions. VER-002 may reference them but must not silently
reinterpret their serialized fields.

Any new resource requires its own exact kind, version, schema URI, canonical
identity, compatibility rule, closed schema, contextual validation, and
installed asset. Core code may compare neutral coordinates and derive freshness
but may not import adapter implementations, infer language/framework
semantics, treat a digest as authenticity, or claim formal verification.
