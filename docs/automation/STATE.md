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

REL-001 is verified and REL-002 is active. The immediate next step is the
foundational release-surface inventory defined in the active ExecPlan. Do not
make a stable release claim or select a project license before that experiment
is recorded. Continue automatically through release closure unless a human
decision gate in `AGENTS.md` is reached.

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

## REL-002 known inputs, not accepted conclusions

Revalidate every item instead of copying old counts into release claims:

- `pyproject.toml` currently declares version `0.1.0` and runtime dependency
  ranges. Preliminary inventory found no root `LICENSE` and no project license
  metadata. Choosing a license is a human decision gate.
- `.github/workflows/quality.yml` currently proves one Ubuntu/Linux job with
  pinned Python/Node/Go setup. Hosted patch-label drift, other operating
  systems/architectures, signing, sdist behavior, and registry publication are
  not yet accepted.
- `docs/automation/BASELINE.md` previously recorded ten npm vulnerabilities,
  including five high severity. Obtain fresh advisory output separately for
  every lock; old counts are not current evidence.
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

## Immediate execution sequence

1. Read the active ExecPlan, inspect `git status`, and create
   `.artifacts/quality/rel002-start-20260721/`.
2. Inventory metadata, license/notices, workflows, locks/advisories, package
   formats/contents, clean installs, compatibility/migration tables, public
   stability claims, security/privacy reporting, support, and deprecation.
3. Build wheel and sdist and run the current package profile without changing
   release behavior. Record the foundational result and alternatives in the
   active ExecPlan.
4. If license selection, a new production dependency, a wire reinterpretation,
   a weaker gate, destructive migration, or materially broader support promise
   is required, record options/evidence/recommendation and set
   `status: blocked_on_decision` before asking the project owner.
5. Otherwise proceed one acceptance behavior at a time through strict
   Red-Green-Refactor, independent audits, all eight gates, clean source and
   clean distribution, final diff/claim review, and REL-002 completion.

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
