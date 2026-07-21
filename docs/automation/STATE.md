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

REL-001 is verified. REL-002 remains active after completing its owner
decisions, policy set, release metadata, local distribution boundary,
dependency/advisory remediation, and executable release checker. Fresh local
Python, lint, specification, frontend, wheel/sdist, supported-floor, installed
three-stack, dependency, and license evidence is green. The aggregate checker
fails only because GitHub reports Private Vulnerability Reporting disabled for
`https://github.com/Deliner/UCF`; the failure correctly publishes no final
release evidence. Continue local integration and independent review, then
repeat the aggregate and clean-source acceptance as soon as the repository
owner enables that selected confidential reporting surface.

## Resume instruction

Invoke the repository skill with:

    Use $ucf-ultrawork. Resume the active work package from
    docs/automation/STATE.md and continue until it is verified or a decision
    gate is reached.

The skill name is repository-defined; `ultrawork` is not an official Codex
execution mode.

## Current truth

- Active package: `REL-002 — Stable release readiness`.
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

## REL-002 accepted foundation evidence

Root and three independent audits agree that no core redesign or new production
dependency is required, but the current tree is not release-ready:

- No root license, SPDX project metadata, license-bearing wheel member,
  authorized security intake, public support channel, or aggregate release
  policy exists. These owner-controlled choices are decision gates.
- Building from the dependency-populated clean-status checkout reproducibly
  yields a 30,144,882-byte sdist with 6,655 members, 5,617 below
  `node_modules`. A clean Git snapshot yields about 1.4 MB/1,038 members. The
  sdist requires an explicit allowlist and equality gate.
- On CPython 3.12.3 the declared `PyYAML==6.0` floor fails to build. With
  `6.0.1`, the declared `typer==0.12.0` floor installs but `ucf --help` fails
  on `pathlib.Path | None`. Supported floors must be corrected and tested.
- Fresh npm audit evidence for `web/package-lock.json` is 10 findings: 7 high,
  1 moderate, and 2 low; the runtime-only tree has 2 high React Router
  findings. The TypeScript adapter and frozen fixture locks each have zero.
  Every web finding reports a fix; update or prove exact non-impact.
- The current wheel/package contract remains green and reproducible at SHA-256
  `17cc39364e513d1f0cf6f5d94508146de8da5748ee7928d11e8dd2d8cd105489`.
  Clean-snapshot sdist installation, CLI, and schema smoke also pass.
- `.github/workflows/quality.yml` currently proves one Ubuntu/Linux job with
  pinned Python/Node/Go setup. Hosted patch-label drift, other operating
  systems/architectures, signing, sdist behavior, and registry publication are
  not yet accepted.
- `tools/quality_gates.py` exposes `automation`, `affected`, and `all`; the
  initial ExecPlan's assumed `package` profile does not exist and was corrected.
  There is no executable release checklist yet.
- README and Ratchet guidance are stale relative to CAP-212/CAP-213 and the
  accepted v2 migration. Four `0.1.0` literals lack a synchronization check;
  root CLI has no `--version`; only 2/28 capability rows name an owner.
- The adapter protocol/conformance kit and ecosystem profiles remain labeled
  experimental. Support is limited to exact frozen fixtures, versions,
  capabilities, procedures, Linux/x86_64, and the recorded toolchains.
- Generation is proved only for the documented direct Python/pytest function
  profile. TypeScript/Go generation and broader backend semantics are
  unsupported, not implied.
- `stale_mappings` exists as a drift concept but is not populated. Runtime
  authenticity, producer identity, and the accepted ratchet tip remain
  caller/VCS/CI trust anchors rather than signed services.
- External adapters, hooks, and generated commands run as the current user;
  they are not hostile-process sandboxes. Runtime evidence has an explicit
  allowlist/redaction/no-raw-retention boundary but does not promise universal
  sensitive-data detection.
- No fixture produces a formal `verified` claim. Public wording must keep
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
  the Git index, builds source-only and dependency-populated sdists, requires
  identical exact manifests/bytes, builds the wheel from the extracted sdist,
  installs it ordinarily and at exact supported floors, checks `ucf --version`
  and `--help`, and runs the existing installed package contract from the
  extracted source distribution.
- The bounded sdist is about 1.46 MB with 1,050 members rather than the rejected
  30.1 MB/6,655-member dependency-contaminated artifact. Exact digests must be
  refreshed after the final documentation/state commit and are not yet release
  claims.
- Runtime/release-tool and build Python coordinates are audited and matched to
  installed license inventories; web full/runtime, TypeScript adapter, and
  TypeScript fixture locks are audited separately; the Go boundary confirms
  zero external modules and exact upstream LICENSE/PATENTS. Current counts are
  zero known advisories with no skip, waiver, severity threshold, or baseline
  reset. The discovered pytest 9.0.2 advisory was removed by qualifying 9.1.1.
- React Router and Vite were upgraded through their exact locks. Frontend
  `npm ci`, full/runtime audits, build, and lint are green.
- Package, root CLI, web metadata, adapter producer, generation environment,
  and documentation now share the package `0.1.0`/pytest `9.1.1` coordinates;
  drift is rejected by tests and the clean-install check.
- `.gitignore` and sdist exclusions cover local environment, registry, SSH,
  private-key, keystore, cache, build, and dependency-tree state while retaining
  `.env.example`; the archived manifest must still match every selected source
  byte, so exclusions cannot conceal a tracked required release file.
- Fresh evidence under `.artifacts/quality/rel002-rgr-20260721/` includes 2,107
  passing Python tests at 90% coverage before the final documentation-only
  test, 169 current automation tests, clean Ruff, 113 specs with zero errors or
  warnings, frontend build/lint, distribution-only proof, full dependency and
  license audits, and the aggregate pre-PVR failure. The requested
  `full-release-evidence.json` is absent by design.
- GitHub API verifies the exact public repository, default `main` branch, and
  enabled Issues. It reports Private Vulnerability Reporting disabled. This is
  the only known release-check failure and must not be downgraded to a warning.

## Immediate execution sequence

1. Finish the current documentation-hardening affected suite, review and commit
   the coherent local release-boundary milestone, and rename the local branch
   from `master` to the repository's canonical `main` before publication.
2. Complete independent read-only contract/claims, security/privacy/licensing,
   and packaging/clean-install audits; reproduce and close every accepted
   finding through retained RED/GREEN evidence.
3. When GitHub Private Vulnerability Reporting is enabled, rerun the aggregate
   release checker with explicit evidence output, all eight gates, and a
   physical clean-source/clean-distribution replay. Then update CAP-214,
   BACKLOG, BASELINE, this state, and every final public claim from fresh output.
4. Inspect the complete diff and source manifests, commit final closure, rename
   or confirm `main`, and push only the verified history to the configured
   canonical repository. Do not create a package release/tag until the checked
   release artifacts and hashes are the ones being published.
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
