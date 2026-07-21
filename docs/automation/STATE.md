---
schema_version: 1
project: ucf
target_state: docs/automation/TARGET_STATE.md
active_work_package: REL-002
active_exec_plan: docs/plans/REL-002-stable-release-readiness.md
status: in_progress
last_updated: 2026-07-21
---

# Automation handoff state

REL-001 is verified. REL-002 remains the only active package. Its owner
decisions, policy set, release metadata, dependency/advisory remediation,
distribution boundary, executable release checker, and every accepted
independent-audit correction are committed and published. The hardened
publisher uses an anonymous staged inode and a create-only link commit point,
never name-based rollback; its collision reader rejects FIFO blocking and
concurrent content or metadata mutation. The exact `main` branch revision is
the publication authority, while GitHub's asynchronous `size` cache is retained
only as telemetry.

Commit `20ea17e` is a green clean-source release candidate on local and remote
`main`. A local all-profile run and a physical public-HTTPS clone with fresh
locked Python and frontend installs both passed all eight gates: 190 automation
tests, 2,129 Python tests at 90% coverage, Ruff, 113 specification checks, the
three-run benchmark, packaging, frontend build, and frontend lint. The
dependency-ordered governance ledger and final public claim transition are now
being closed. Final revision-bound acceptance evidence remains pending until
that metadata is committed, pushed, and replayed from the resulting exact
revision; CAP-214 therefore remains planned at this stopping point.

Candidate command evidence is retained in
`.artifacts/quality/rel002-final-20260721/quality-gates-all-benchmark-refreshed.log`
and the physical replay directory
`.artifacts/agents/rel002-clean-source-snapshot/20260721T130000Z-20ea17e/`.
The final aggregate target remains
`.artifacts/quality/rel002-final-20260721/release-evidence.json`.

## Resume instruction

Invoke the repository skill with:

    Use $ucf-ultrawork. Resume the active work package from
    docs/automation/STATE.md and continue until it is verified or a decision
    gate is reached.

The skill name is repository-defined; `ultrawork` is not an official Codex
execution mode.

## Current truth

- Active package: historical `REL-002 — Stable release readiness`; the accepted
  result is a bounded `0.1.x` production preview, not a stable API.
- Active plan: `docs/plans/REL-002-stable-release-readiness.md`.
- Verified dependency order: `FND-001`, `FND-002`, `FND-003`, `IR-001`,
  `IR-002`, `ADP-001`, `ADP-002`, `BRN-001`, `BRN-002`, `BRN-003`,
  `BRN-004`, `ECO-001`, `ECO-002`, `ECO-003`, `CHG-001`, `CHG-002`,
  `VER-001`, `VER-002`, and `REL-001`.
- `REL-002` is the last dependency-ordered work package. Completion requires
  compatibility, migration, security, privacy, packaging, licensing, support,
  and deprecation policy; critical-blocker disposition; release checklist;
  clean wheel/source-distribution scenarios; honest public claims; all gates;
  independent review; and physical clean-source evidence.
- Canonical branch is local `main`; `origin` is
  `https://github.com/Deliner/UCF.git`. The hosted repository is public, Issues
  and Private Vulnerability Reporting are enabled. Commit `20ea17e` is the
  current exact `main` branch revision locally and remotely. It is a verified
  technical candidate; the remaining source changes are governance and public
  claim closure followed by one exact-revision replay.

## Binding Ratchet decision

On 2026-07-21 the project owner selected Ratchet `2.0.0` with a separate
coverage ledger. This decision is fully recorded in the REL-001 ExecPlan and
is binding:

- Ratchet and Onboarding `1.0.0` remain unchanged; v2 is a parallel explicit
  contract and CLI boundary.
- Accepted Behavior violations and unresolved discovery coverage are separate.
  Uncovered interfaces and uncertain candidates are non-claim coverage debt.
- Exact inherited debt may remain. Added, semantically or observationally
  changed, or reintroduced debt blocks. Comparable resolution is protected.
- Partial rule coverage or an unenumerated inventory domain cannot establish
  or advance. Scoped success cannot hide global partial coverage.
- Stable identity is language-neutral and versioned; exact IDs, paths,
  revisions, adapter/procedure coordinates, and environment are trace.
  Ambiguous keys fail explicitly.
- V1 migration validates exact source Policy/Baseline/Assessment/Onboarding,
  preserves lineage and generation, and imports uncertain state. Reset,
  downgrade, and claim promotion are forbidden.

## REL-001 accepted evidence

- The public benchmark is `docs/benchmarks/rel001-report.json`; explanatory
  limits are in `docs/benchmarks/REL-001.md` and CAP-213.
- Three complete repetitions agree on structural digest
  `c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a`
  and lifecycle digest
  `83e7187bfe60982a11929237ba8696c5534f1b3c3bcaaa38de0a3e72ed7d0d38`.
- The checked totals are 13 candidates, 7 oracle false candidates, 13
  candidate decisions, 1 ambiguity resolution, 0 mapping approvals, 0 change
  approvals, 4 mappings, 5 materializations, 5 tested claims, 0 verified
  claims, 18 uncovered interfaces, and 20 unresolved coverage-debt entries.
- The exact Python, TypeScript/Fastify, and Go frozen fixtures pass common
  conformance and brownfield onboarding. The checked platform procedures are
  HTTP, CLI process, and local file-spool event. This is not broad ecosystem or
  cross-platform support.
- The lifecycle benchmark projection removes only runtime execution-result ID
  and timestamp after full contextual validation, then recomputes transitive
  references. Semantic outcome changes remain digest-visible. Independent
  final security review accepted the corrected projection.
- Local all-profile evidence is under
  `.artifacts/quality/rel001-benchmark-20260721/`.
- Physical clean-source evidence is
  `.artifacts/agents/rel001-clean-source-snapshot/20260721T034500Z-rel001/`.
  Fresh locked Python and Node installs pass all eight gates: 141 automation
  tests, 2,080 Python tests at 90% coverage, Ruff, 113 specification checks,
  three-run benchmark replay, installed package contract, frontend build, and
  frontend lint.
- The 1,034-file checkout/snapshot manifest is unchanged before and after at
  SHA-256
  `c8dd5c83796d2db24be725149546a44c0d6d227a60ee42946387169ea64c8858`.
  The reproducible wheel SHA-256 is
  `17cc39364e513d1f0cf6f5d94508146de8da5748ee7928d11e8dd2d8cd105489`.

## REL-002 activation foundation evidence — historical

At activation, root and three independent audits agreed that no core redesign
or new production dependency was required. The observations below describe the
2026-07-21 activation snapshot, not the current tree; their dispositions are in
the implementation milestone and independent-audit sections that follow:

- The repository had no root license, SPDX project metadata, license-bearing
  wheel member, authorized security intake, public support channel, or
  aggregate release policy. Those owner-controlled choices were decision gates.
- A build from the dependency-populated clean-status checkout reproducibly
  yielded a 30,144,882-byte sdist with 6,655 members, 5,617 below
  `node_modules`. A clean Git snapshot yields about 1.4 MB/1,038 members. The
  sdist therefore required an explicit allowlist and equality gate.
- On CPython 3.12.3 the declared `PyYAML==6.0` floor failed to build. With
  `6.0.1`, the declared `typer==0.12.0` floor installed but `ucf --help` failed
  on `pathlib.Path | None`; the supported floors required correction and proof.
- Fresh npm audit evidence for `web/package-lock.json` reported 10 findings: 7
  high, 1 moderate, and 2 low; the runtime-only tree had 2 high React Router
  findings. The TypeScript adapter and frozen fixture locks each had zero.
  Every web finding reported a fix.
- The then-current wheel/package contract was green and reproducible at SHA-256
  `17cc39364e513d1f0cf6f5d94508146de8da5748ee7928d11e8dd2d8cd105489`.
  A clean-snapshot sdist was inspected and built into a wheel; that wheel's CLI
  and schema smoke also passed.
- `.github/workflows/quality.yml` proved one Ubuntu/Linux job with
  pinned Python/Node/Go setup. Hosted patch-label drift, other operating
  systems/architectures, signing, sdist behavior, and registry publication are
  outside the accepted boundary.
- `tools/quality_gates.py` exposed `automation`, `affected`, and `all`; the
  initial ExecPlan's assumed `package` profile did not exist and was corrected.
  No executable release checklist existed.
- README and Ratchet guidance were stale relative to CAP-212/CAP-213 and the
  accepted v2 migration. Four `0.1.0` literals lacked a synchronization check;
  the root CLI had no `--version`; only 2/28 capability rows named an owner.
- The adapter protocol/conformance kit and ecosystem profiles were labeled
  experimental. Support is limited to exact frozen fixtures, versions,
  capabilities, procedures, Linux/x86_64, and the recorded toolchains.
- Generation was proved only for the documented direct Python/pytest function
  profile. TypeScript/Go generation and broader backend semantics are
  unsupported and were not implied.
- `stale_mappings` existed as a drift concept but was not populated. Runtime
  authenticity, producer identity, and the accepted ratchet tip remained
  caller/VCS/CI trust anchors rather than signed services.
- External adapters, hooks, and generated commands ran as the current user;
  they were not hostile-process sandboxes. Runtime evidence had an explicit
  allowlist/redaction/no-raw-retention boundary but does not promise universal
  sensitive-data detection.
- No fixture produced a formal `verified` claim. Public wording had to keep
  `observed`, `declared`, `mapped`, `tested`, and `verified` distinct.

Evidence is retained under `.artifacts/quality/rel002-start-20260721/` and:

- `.artifacts/agents/rel002-security-licensing/report.md`;
- `.artifacts/agents/rel002-packaging-ci/audit-summary.md`;
- `.artifacts/agents/rel002-policy-claims/report.md`.

## Accepted REL-002 owner decisions

The active ExecPlan contains the complete alternatives and consequences. The
binding selections made by project owner `Deliner` are:

1. Apache-2.0 with exact project notice `Copyright 2026 Deliner`. Preserve all
   third-party notices in their artifact boundaries.
2. Keep package `0.1.x` as a production preview. Supported tier is CPython 3.12
   on Linux/x86_64 with no SLA; exact published artifacts/contracts are
   immutable; ordinary deprecation lasts at least one subsequent minor preview
   and 90 days with migration guidance. External adapters remain experimental.
   `1.0.0` stable-API promotion is explicitly deferred and owned by `Deliner`.
3. Canonical repository `https://github.com/Deliner/UCF`, responsible
   maintainer `Deliner`, GitHub private vulnerability reporting for confidential
   intake, and GitHub Issues for public support without an SLA.

Do not expose the local Git email, silently promote the preview to stable,
broaden adapter support, or select weaker/different terms.

## REL-002 implementation milestone

- Apache-2.0 `LICENSE`, `NOTICE`, package SPDX metadata, maintainer/project URLs,
  preview classifiers, `SECURITY.md`, and the compatibility, migration,
  privacy, packaging, support, and versioning policies are implemented and
  machine-checked.
- `tools/release_check.py` is the packaging gate. It selects release source from
  the exact Git-index object bytes, builds source-only and
  dependency-populated sdists, requires identical exact manifests/bytes and
  bounded compressed/member/uncompressed sizes, builds the wheel from the
  extracted sdist, proves the wheel built from the source distribution at
  ordinary and exact supported floors,
  checks `ucf --version` and `--help`, and runs the existing installed package
  contract from the extracted source distribution.
- The bounded sdist has 1,050 members rather than the rejected 6,655-member
  dependency-contaminated artifact. Candidate `20ea17e` produced byte-identical
  1,488,617-byte sdists at SHA-256
  `3a0b611165f4d9fb6d9e8c20ae1458af5fdc1490fa01628e0e6b8772e8318d54`;
  these candidate coordinates do not substitute for final-revision evidence.
- The checker is wired to audit runtime/release-tool, build, ordinary-install,
  and supported-floor Python coordinates and match them to exact installed
  license/environment inventories; it also separates web full/runtime,
  TypeScript adapter, TypeScript fixture, and zero-external-module Go review.
  Candidate `20ea17e` captured, installation-tested, and independently audited
  both actual environment inventories with zero known advisories. Final
  revision-bound acceptance evidence remains pending after metadata closure.
  The accepted floors are `pydantic>=2.4.0`, `jinja2>=3.1.6`,
  `pyyaml>=6.0.1`, and the previously accepted Typer floor; the locked pytest
  coordinate was raised from the advisory-bearing 9.0.2 to 9.1.1.
- React Router and Vite were upgraded through their exact locks. Frontend
  `npm ci`, full/runtime audits, build, and lint are green.
- Package, root CLI, web metadata, adapter producer, generation environment,
  and documentation now share the package `0.1.0`/pytest `9.1.1` coordinates;
  drift is rejected by tests and the clean-install check.
- `.gitignore` and sdist exclusions cover local environment, registry, SSH,
  private-key, keystore, cache, build, and dependency-tree state while retaining
  `.env.example`; the archived manifest must still match every selected source
  byte, so exclusions cannot conceal a tracked required release file.
- Standalone TypeScript and Go adapter artifacts now carry the root Apache-2.0
  `LICENSE` and `NOTICE`; the Go artifact separately preserves upstream Go
  `LICENSE`/`PATENTS`. The complete current package contract passes with
  deterministic evidence SHA-256
  `87c7012fc84bd4f8f81ef7996514403778d990a63a2e797d8c71320301108894`.
- The 2,107-test Python run, 169-test automation run, distribution-only proof,
  dependency/license output, and aggregate pre-PVR run under
  `.artifacts/quality/rel002-rgr-20260721/` are pre-audit and superseded; they
  remain diagnostics, not proof of the corrected path. Focused RED/GREEN logs
  and the corrected package-contract result are historical diagnostics. The
  current 190-test automation, 2,129-test Python, all-profile, and physical
  clean-source candidate evidence is green. The requested final
  `.artifacts/quality/rel002-final-20260721/release-evidence.json` remains
  reserved for the exact final published revision and is absent by design.
- GitHub API now verifies the exact public repository, default `main`, enabled
  Issues, and enabled Private Vulnerability Reporting. Final evidence also
  requires a clean committed checkout whose local HEAD exactly equals remote
  `main`; candidate `20ea17e` satisfies that condition, and the final metadata
  revision must prove it again.

## Independent pre-acceptance audit findings

The contract/claims, packaging/CI, and security/licensing reviewers rejected
the first locally green release checker. The accepted findings and dispositions
are:

- source-only builds listed the index but copied mutable working-tree bytes;
  source export now reads raw Git blobs and has adversarial staged/unstaged and
  clean/smudge-filter regressions;
- the first correction still used `checkout-index`, which applies filters, and
  final HEAD binding happened only after artifacts were built; development
  checks now snapshot raw index object IDs, while final evidence snapshots raw
  objects from one clean commit tree, builds from that snapshot, records its
  object/source manifests, and revalidates the same HEAD/tree before publish;
- failed runs could leave old evidence and successful publication was not
  atomic/create-only; a run invalidates its target before work and publishes an
  exact JSON file from an anonymous staged inode through a create-only
  `linkat` transaction;
- the locked verification environment was audited instead of the two
  environments users actually install; ordinary and supported-floor exact
  inventories are now captured and installation-tested, and the aggregate
  checker requires their independent advisory/license alignment. Candidate
  `20ea17e` passes those full install/audit phases from a clean published
  checkout; final metadata must repeat the strict evidence-publishing mode at
  its own exact revision;
- `pydantic==2.0` and `jinja2==3.1.0` were known-vulnerable supported floors;
  floors were raised to the first accepted safe versions and locked tests cover
  the policy;
- standalone TypeScript/Go artifacts omitted project licensing; exact artifact
  tree tests now require the project license/notice alongside upstream notices;
- compressed-size checks did not bound archive expansion; per-member and total
  uncompressed limits now fail closed. Follow-up review found directories were
  not counted and parsing occurred before the limit; streaming inspection now
  bounds every member, raw/canonical path, file sizes, and the decompressed tar
  stream before extraction;
- an empty GitHub repository could satisfy the hosted check; final evidence now
  requires nonempty remote `main` at the exact clean local source revision;
- the first published-revision aggregate showed that GitHub `size` cache may
  remain zero after `main` exists. A present exact `main` branch revision is now
  the direct nonempty/publication proof; nonnegative cached size is retained
  only as evidence metadata;
- historical “stable release” wording overstated the accepted `0.1.x`
  production preview and the source-install wording overstated direct archive
  installation; both claims are narrowed and machine-checked.
- scoped `--distribution-only` runs could publish an unqualified passed JSON;
  retained final evidence is now forbidden for that scope;
- dependency audits read mutable checkout locks after artifact construction;
  final audit inputs are now materialized from the same captured commit blobs;
- tar iteration stopped at the first tar end marker without consuming later
  gzip members; inspection now drains the complete gzip stream through the
  decompression bound and rejects corrupt trailers;
- hidden installed-inventory mode returned before stale evidence invalidation;
  every requested evidence path is invalidated first and incompatible scoped
  modes then fail closed;
- temporary-snapshot cleanup could happen after final evidence became visible;
  cleanup now precedes hosted/final publication;
- two successive name-based rollback designs were unsafe: a boolean ownership
  flag deleted a pre-check replacement, and a device/inode check still deleted
  a replacement made between `stat` and `unlink`. The final design performs no
  name-based rollback after commit. It writes and flushes an anonymous staged
  inode, publishes it with create-only `linkat`, and reports
  `committed_durability_unknown` without removing the complete visible entry if
  the parent-directory flush fails;
- evidence collision verification followed a path after `lstat`, and stale
  symlinks survived invalidation; invalidation now unlinks non-directory entries
  without following them, collision comparison uses `O_NOFOLLOW` plus an open
  descriptor and inode recheck, and publication requires Linux `O_TMPFILE`/
  `linkat` support from the evidence filesystem;
- collision validation could block while opening a FIFO and could accept bytes
  appended between its bounded read and entry check; it now uses `O_NONBLOCK`,
  rejects non-regular entries before reading, repeats the bounded exact read,
  and requires stable descriptor/entry identity, size, and modification
  metadata;
- historical BASELINE text, source-install wording, remote-write authority,
  adapter-license scope, embedded-hash wording, and root ignore coverage were
  contradictory; cross-document tests now enforce the corrected boundary.

Focused RED/GREEN logs are under
`.artifacts/quality/rel002-rgr-20260721/`. The earlier aggregate green file was
pre-audit and is superseded; it must not be used as final release evidence.
The latest affected contract is 131/131, the complete automation suite is
190/190, Ruff is clean, and
`distribution-raw-index-streaming-green.log` proves the corrected staged-source
distribution path. The later `distribution-third-reaudit-green.log` repeats it
after complete-gzip and commit-bound dependency-source hardening. The current
`distribution-final-precommit-green.log` repeats the staged path after the
atomicity corrections: both 1,050-member sdists are byte-identical and both
ordinary and supported-floor installations pass. Exact evolving pre-commit
digests remain in retained command output rather than becoming self-referential
source claims. The later
`.artifacts/quality/rel002-final-20260721/release-post-commit-affected-green.log`
and `release-post-commit-automation-green.log` prove the final no-rollback
publisher correction. The subsequent `release-collision-reader-green.log`,
`release-collision-affected-green.log`, and
`release-collision-automation-green.log` prove nonblocking, stable exact
collision handling. The independent closure re-audits accepted the
implementation boundary and identified only the governance/status and final
exact-revision closure now in progress. A final read-only audit remains
required after the last replay.

## Immediate execution sequence

1. Complete the executable backlog/ExecPlan governance ledger and move
   superseded non-ExecPlan proposals out of `docs/plans/`; retain focused
   RED/GREEN evidence.
2. Commit and push that metadata candidate, then run the aggregate checker with
   an explicit absent evidence path to prove exact local/remote revision,
   PVR, installations, audits, artifacts, and package scenarios.
3. Update CAP-214, BACKLOG, BASELINE, this state, the REL-002 outcome, and final
   public claims from that fresh output; commit and push the closure.
4. From the final remote revision, repeat explicit release evidence, all eight
   gates, and a physical clean-source/clean-distribution replay. Inspect the
   complete final diff, manifests, Git status, and remote revision, then obtain
   independent final claims/dependency/release audits.
5. If a new production dependency, wire reinterpretation, weaker gate,
   destructive migration, hosted write, or broader support promise appears,
   open a new explicit decision gate before acting.

## Handoff contract

- Preserve unrelated user changes and avoid destructive Git operations.
- Stream command output to the terminal and retained logs; never replace
  failing evidence or hand-edit generated output.
- Do not skip, xfail, warn away, exclude, reset a baseline, or weaken a check.
- Do not import adapters into Python core or add Python-specific meaning to IR.
- Do not call the project stable until CAP-214, the release checklist, policy
  set, clean distribution, full gates, state, baseline, and final independent
  reviews all agree.
- At every stop update this file and the active ExecPlan so a stateless session
  can continue without inference.
