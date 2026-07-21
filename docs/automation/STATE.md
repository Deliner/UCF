---
schema_version: 1
project: ucf
target_state: docs/automation/TARGET_STATE.md
active_work_package: null
active_exec_plan: null
status: complete
last_updated: 2026-07-21
---

# Automation handoff state

REL-002 is verified. All twenty dependency-ordered work packages are verified,
their canonical ExecPlans contain outcomes, and no active package remains. The
bounded result is a `0.1.x` production preview for the CPython 3.12/Linux x86_64
control plane, not a stable API. CAP-214 is implemented at that exact boundary;
all external adapters and ecosystem/platform profiles retain their experimental
fixture-scoped status.

Candidate `d91e57b` was explicitly rejected after GitHub Actions run
`29839039561` failed the canonical all profile despite local and clean-clone
success. The replacement keeps production cleanup unchanged: its test harness
uses deadline-bound directional pipe markers and the real 1-second graceful/
2-second absolute cleanup bounds. Retained evidence includes the focused RED,
200 normal and 100 race repetitions, Ubuntu 24.04 root/non-root replay, full Go
package/race/vet, all 54 Go ecosystem tests, and an exact non-runtime REL-001
benchmark replay.

Published candidate `c76bc50` was also rejected: GitHub Actions run
`29844155406` completed the canonical step with exit 1. Two independent exact
environment reproductions isolated `rel001-benchmark` as the sole failing gate.
The workflow's floating `uv python install 3.12` selected managed CPython
3.12.13, while the checked report was bound to 3.12.3; Python identity and three
derived structural digests therefore changed exactly as the strict evidence
contract requires. The accepted replacement pins CPython 3.12.13 in both
`.python-version` and CI and regenerates the report only through the complete
three-repetition runner. The supported package promise remains CPython 3.12;
the exact patch pin is the reproducible repository/CI evidence coordinate.

Exact-pin candidate `e895c6e` was then rejected by GitHub Actions run
`29849357054`: local and fresh public-HTTPS-clone all profiles pass 8/8, but the
canonical hosted step exits 1. Public metadata exposes only the aggregate step
failure, and retained artifact `8503126276` requires authentication. No gate or
product conclusion is inferred from that opaque result. The replacement adds a
bounded GitHub annotation containing only the failed gate ID and integer exit
code; it does not expose gate output, retry a command, or change acceptance.
RED/GREEN evidence is under
`.artifacts/quality/rel002-ci-observability-20260721/`, and rejected-run metadata
plus the public page are under
`.artifacts/ci/rel002-final-python-pin/`.

The cheapest exact runner-environment experiment then reproduced the red gate:
with `GITHUB_ACTIONS=true`, two CLI tests compared ANSI-styled Rich help as raw
bytes, so style boundaries split `--base-behavior`, `--final-behavior`, and
`--behavior-ir`. Both tests pass without that variable. The correction keeps
colored CLI output intact and compares its unstyled semantic text in tests;
focused RED/GREEN covers both CI-colored and ordinary output.

Published candidate `c27e63a` was rejected by GitHub Actions run
`29852283557`. The new bounded annotation proves `python-tests` exited 1 while
all setup steps succeeded. The exact revision independently passes 8/8 both in
the source checkout and in a new public HTTPS clone under
`GITHUB_ACTIONS=true`; therefore neither those passes nor the prior Rich fix is
treated as hosted acceptance. Public logs and the retained artifact still
require authentication. A second focused RED/GREEN extends diagnostics only
for the Python gate: it emits deduplicated, ASCII-whitelisted pytest node IDs
from summary lines, capped at twenty, while excluding exception messages and
all other log content. Evidence is under
`.artifacts/quality/rel002-pytest-observability-20260721/` and
`.artifacts/agents/rel002-final-cli-help/`.

Independent threat review rejected the first node-ID parser at candidate
`f9f8fbd` before it could become accepted release machinery: fabricated lines
could consume the cap, a huge ID was accepted, and ordinary path reopening
followed symlinks or blocked on a FIFO. The hardened diagnostic reads at most
the final 64 KiB from a nonblocking, no-follow regular-file descriptor, uses
only the last canonical pytest short-summary block, caps each static node ID at
512 characters, strips parameter values, deduplicates, and fails closed on
open/read errors. Focused adversarial RED/GREEN evidence and the independent
rejection are retained under `.artifacts/quality/rel002-pytest-observability-20260721/`
and `.artifacts/agents/rel002-pytest-identity/security-audit/`.

Before that implementation was superseded, published run `29855245163`
identified the sole hosted failure as
`tests/cli/test_generate.py::test_generate_rejects_mixed_parse_errors_before_writing`.
The cheapest exact experiment reproduced it with a long pytest base path: Rich
may wrap inside both `Parse errors` and `invalid.yaml`, while the test required
each rendered token to remain contiguous. A deterministic width-10 console is
the RED regression; the corrected test removes ANSI styling and renderer line
breaks before checking semantic text. Production output and parse behavior are
unchanged. Evidence is under
`.artifacts/quality/rel002-pytest-observability-20260721/` and
`.artifacts/agents/rel002-pytest-identity/hosted/`.

The clean-clone verification's first complete attempt separately hit GitHub's
unauthenticated REST quota in `packaging-contract`; its summary identified that
different gate and exact 403. A later complete 8/8 replay is retained rather
than accepting a single-gate retry. This is an operational release-check risk,
not evidence for the hosted `python-tests` failure.

The final revision-bound acceptance evidence is retained at
`.artifacts/quality/rel002-final-ci-closure-20260721/release-evidence.json`.
The same published revision passes the canonical GitHub Actions workflow and
all eight gates locally; output is retained in that directory. A fresh public
HTTPS clone with locked Python/frontend installs repeats the complete profile
under `.artifacts/agents/rel002-final-ci-closure/`.

The hardened evidence publisher uses an anonymous staged inode and a
create-only link commit point, never name-based rollback; its collision reader
rejects FIFO blocking and concurrent content or metadata mutation. The exact
`main` branch revision is publication authority, while GitHub's asynchronous
`size` cache is retained only as telemetry. A durability result of
`committed_durability_unknown` is nonzero and cannot support acceptance.

## Resume instruction

Invoke the repository skill with:

    Use $ucf-ultrawork. Resume the active work package from
    docs/automation/STATE.md and continue until it is verified or a decision
    gate is reached.

The skill name is repository-defined; `ultrawork` is not an official Codex
execution mode.

## Current truth

- Active package and ExecPlan: none; repository delivery state is complete.
- Final package: historical `REL-002 — Stable release readiness`; its accepted
  result is a bounded `0.1.x` production preview, not a stable API.
- Verified dependency order: `FND-001`, `FND-002`, `FND-003`, `IR-001`,
  `IR-002`, `ADP-001`, `ADP-002`, `BRN-001`, `BRN-002`, `BRN-003`,
  `BRN-004`, `ECO-001`, `ECO-002`, `ECO-003`, `CHG-001`, `CHG-002`,
  `VER-001`, `VER-002`, `REL-001`, and `REL-002`.
- `docs/automation/BACKLOG.md` is the executable completion ledger and maps each
  verified package to exactly one canonical ExecPlan.
- Canonical branch is local `main`; `origin` is
  `https://github.com/Deliner/UCF.git`. The hosted repository is public, Issues
  and Private Vulnerability Reporting are enabled. The retained final evidence
  records the exact matching local and remote `main` revision without embedding
  a self-invalidating commit hash in this source file.

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
  `4f0e77045ca5c0cf4994d3059585aefa549854eee2897c2b7968b35f1881854b`
  and lifecycle digest
  `b315a73a701304448edd63ed955fe9de45040df343e76fd1ede424f5adb78260`.
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
  Published governance candidate `0f10681` captured, installation-tested, and
  independently audited both actual environment inventories with zero known
  advisories in strict evidence-publishing mode. The final retained evidence
  repeats that mode on the completed source revision.
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
  190-test automation, 2,129-test Python, all-profile, and physical clean-source
  candidate evidence is historical green input. The final exact published
  revision is accepted through
  `.artifacts/quality/rel002-final-20260721/release-evidence.json`,
  `quality-gates-all-final.log`, and the `rel002-final-clean-source` replay.
- GitHub API now verifies the exact public repository, default `main`, enabled
  Issues, and enabled Private Vulnerability Reporting. Final evidence also
  requires a clean committed checkout whose local HEAD exactly equals remote
  `main`; the retained final evidence records that equality.

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
  checkout; the retained final evidence repeats strict evidence-publishing mode
  at the completed exact revision;
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
collision handling. Independent closure re-audits accepted the implementation
boundary, the canonical dependency ledger, the public-claim limits, and the
final exact-revision command evidence.

## Completed acceptance sequence

1. The executable backlog ledger maps all twenty verified packages to complete
   canonical ExecPlans; superseded proposals are archived outside
   `docs/plans/` and explicitly rejected.
2. The explicit aggregate checker publishes final evidence only from exact
   clean source already present on remote `main` and proves PVR, installations,
   audits, artifacts, and package scenarios.
3. CAP-214, BACKLOG, BASELINE, this state, the REL-002 outcome, README, and
   release policies state the same bounded production-preview claim.
4. All eight gates and a physical clean-source replay pass from fresh locked
   installs, and independent reviewers accept claims, dependency closure, and
   release evidence.

## Handoff contract

- Preserve unrelated user changes and avoid destructive Git operations.
- Stream command output to the terminal and retained logs; never replace
  failing evidence or hand-edit generated output.
- Do not skip, xfail, warn away, exclude, reset a baseline, or weaken a check.
- Do not import adapters into Python core or add Python-specific meaning to IR.
- Do not call the project or API stable: CAP-214 proves only the bounded
  production-preview readiness claim even though the release checklist,
  policies, clean distribution, gates, state, baseline, and reviews agree.
- At every stop update this file and the active ExecPlan so a stateless session
  can continue without inference.
