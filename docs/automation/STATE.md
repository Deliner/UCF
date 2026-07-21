---
schema_version: 1
project: ucf
target_state: docs/automation/TARGET_STATE.md
active_work_package: REL-002
active_exec_plan: docs/plans/REL-002-stable-release-readiness.md
status: blocked_on_decision
last_updated: 2026-07-21
---

# Automation handoff state

REL-001 is verified. The REL-002 foundational release-surface inventory is
complete and found a bounded technical closure path, but production edits are
blocked on three project-owner decisions: license/licensor identity, stable
release/deprecation commitment, and authorized confidential security/public
support channels. Exact options, consequences, evidence, and recommendations
are in the active ExecPlan. No stable release claim has been made.

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

## Pending human decisions

The active ExecPlan is authoritative. The recommended combined choice is:

1. Apache-2.0, with owner-confirmed contribution rights and exact copyright
   holder/year.
2. Release bounded control-plane `1.0.0`: supported CPython 3.12 on
   Linux/x86_64, exact documented contracts/install paths, external adapters
   still experimental; SemVer; no SLA; deprecations retained for at least one
   minor and 180 days and removed only in a major with migration, except an
   explicitly documented urgent security withdrawal.
3. Supply a canonical public repository URL, enable its private vulnerability
   reporting, use its Issues/Discussions for public support, and name the
   responsible maintainer/entity. Alternatively provide dedicated private
   security and public support addresses.

Do not infer the licensor, expose the local Git email, create a hosted
repository, enable external features, or select weaker/different terms.

## Immediate execution sequence

1. Obtain and record the project owner's answers to DG-REL002-001 through 003
   in the active ExecPlan; set `status: in_progress` only after all required
   coordinates are concrete.
2. Proceed one acceptance behavior at a time through strict
   Red-Green-Refactor: release inventory/check, license+metadata, sdist closure,
   dependency/advisory closure, policy/docs/version synchronization, and clean
   wheel/sdist/adapter release artifacts.
3. Complete independent audits, all eight gates, clean source and
   clean distribution, final diff/claim review, and REL-002 completion.
4. If a new production dependency, wire reinterpretation, weaker gate,
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
