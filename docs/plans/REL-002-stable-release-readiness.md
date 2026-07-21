# REL-002 Stable Release Readiness

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect current
repository evidence. Maintain it according to `PLANS.md`.

## Purpose / Big Picture

After this package, an adopter can evaluate, install, operate, upgrade, and
deprecate the bounded UCF release without guessing which contracts are stable,
which platforms and adapters are supported, how security or privacy reports are
handled, what licenses apply, or how a release is reproduced. One executable
release checklist must build the distribution from a clean source tree, install
and exercise it outside the checkout, validate public claims against the
capability matrix, and reject a release when a critical obligation is missing.

This package does not broaden the capabilities accepted through REL-001. It
turns the exact proved scope into an honest release boundary and leaves every
remaining limitation named, owned, justified, and non-misleading.

## Foundational Assumption

The root assumption is that the dependency-ordered implementation is complete
enough for a bounded `0.1.x` release and that REL-002 is primarily closure of
policy, distribution, dependency, CI, and public-claim contracts rather than a
hidden core redesign or new production dependency.

Challenge this before production edits with the cheapest useful experiment:
inventory every release surface and compare it with executable evidence. Check
project metadata, root licensing, wheel and source-distribution contents,
locked Python and npm dependency advisories and licenses, CI operating-system
and toolchain coverage, clean-install commands, supported serialized versions,
migration paths, public stability wording, security/privacy reporting, support
and deprecation promises, hooks, and all capability-matrix limitations. Retain
the inventory and command output under
`.artifacts/quality/rel002-start-20260721/`. Classify each gap as a critical
release blocker, an explicitly supportable limitation, or a non-release future
capability; do not silently convert missing evidence into support.

The alternatives are:

1. ship a bounded `0.1.x` release with exact Linux/x86_64 and pinned-toolchain
   evidence, stable compatibility rules for the published serialized
   contracts, and explicit experimental adapter/profile labels;
2. expand this package to cross-platform execution, artifact signing, and a
   broader support promise before any release, which costs substantially more
   and is not justified unless the inventory finds it necessary for an already
   published claim;
3. defer release readiness and retain prototype status if a critical security,
   licensing, migration, or packaging blocker cannot be closed honestly.

Select the smallest complete supported boundary only after the experiment. A
new production dependency or license, a reinterpretation of a published wire
contract, a weaker gate, destructive migration, or materially different
support promise is a human decision gate under `AGENTS.md`.

Result: pending. Do not implement release-policy changes until the inventory
and cheapest falsification are recorded here.

## Progress

- [x] 2026-07-21: Accept REL-001 with an independently reviewed three-stack,
  three-fixture benchmark, all eight gates, and a physical clean-source replay.
- [x] 2026-07-21: Create this self-contained ExecPlan and activate REL-002.
- [ ] Run and retain the release-surface inventory and foundational
  falsification; record alternatives, findings, and any human decision gate.
- [ ] Add one failing release-readiness contract at a time, implement the
  smallest closure, and keep each focused slice green through refactoring.
- [ ] Publish and machine-check compatibility, migration, security, privacy,
  packaging, licensing, support, and deprecation policies and limitations.
- [ ] Prove wheel and source-distribution builds, clean installation, installed
  schemas/CLIs, dependency/advisory policy, and the complete release checklist.
- [ ] Complete independent contract/claims, security/privacy/licensing, and
  packaging/clean-install reviews; close accepted findings with retained REDs.
- [ ] Run affected suites and all eight gates, inspect the complete diff, repeat
  physical clean-source and clean-distribution scenarios, update automation
  state/baseline, and record the final outcome.

## Surprises & Discoveries

At activation, the repository has one Linux CI job and an accepted reproducible
wheel workflow, but `pyproject.toml` has no declared project license, classifiers,
readme metadata, authors, or project URLs, and no root `LICENSE` file was found.
These are inventory inputs, not yet accepted conclusions: REL-002 must inspect
the actual built wheel and source distribution and must not choose a license on
the project owner's behalf.

The accepted REL-001 boundary is intentionally narrower than a general stable
ecosystem claim. Python, TypeScript/Fastify, and Go are proved only on exact
frozen Linux/x86_64 fixtures and procedures; no fixture has a `verified` claim.
Release wording must preserve that distinction even if the Python control-plane
package itself becomes supported.

## Decision Log

- **2026-07-21 — do not broaden product capability during release closure.**
  Author: root agent. REL-002 may add policy, checks, package metadata, CI and
  distribution proof required for the accepted scope. New adapters, general
  cross-platform semantics, signing infrastructure, hosted services, and new
  generation backends remain outside scope unless the foundational experiment
  proves an existing release claim cannot be made honestly without them.

- **2026-07-21 — treat policy text as an executable release contract.** Author:
  root agent. Every required policy must be discoverable from the README,
  internally consistent with the capability matrix, and covered by a release
  checklist or documentation-claim test. Prose alone does not close a critical
  blocker.

## Outcomes & Retrospective

REL-002 is active. REL-001 supplies the accepted functional and evidence
boundary; no stable release claim has been made. The first milestone is the
foundational release inventory. Completion requires comparison with the purpose
above, fresh release/clean-install evidence, independent review, and an explicit
accounting of every remaining limitation and owner.

## Context and Orientation

`pyproject.toml` and `uv.lock` define the Python control-plane package and lock;
`src/ucf/schemas/` contains installed serialized contracts. `web/package.json`
and its lock define the frontend. The TypeScript adapter has its own private
package and lock under `adapters/typescript-fastify/`; the selected Go adapter
and third-party notices are under `adapters/go-stdlib/`. The only current CI
workflow is `.github/workflows/quality.yml`.

`tools/quality_gates.py` is the canonical eight-gate local/CI runner.
`tools/package_contract.py` proves a wheel outside the checkout, including all
four installed REL-001 lanes. `docs/CAPABILITIES.md` is the canonical public
claim matrix; `README.md` is the entry point. `docs/automation/BASELINE.md`
records known release-review inputs, and `docs/benchmarks/` contains the checked
REL-001 proof.

For this package, compatibility means the explicit accept/reject and migration
rules for each published wire/CLI contract; support means the environments and
response boundary the project commits to maintain. A limitation is releasable
only when it is truthful, discoverable, assigned to an owner (project, adapter
maintainer, caller/operator, or future backlog), and cannot be mistaken for a
passing capability. A critical blocker is an unresolved issue that makes the
published package unsafe, unlawful, uninstallable, irreproducible, or materially
misleading within its claimed scope.

## Plan of Work

First, snapshot the release surfaces and run the cheapest falsification. Build
both wheel and source distribution, inspect their metadata and file manifests,
install each into a clean environment, inventory dependency advisories/licenses
from locked inputs, inspect CI/toolchain and platform claims, and trace every
public capability statement to a test or checked report. Record findings before
changing behavior.

Second, define one machine-readable release-readiness manifest and/or focused
validator only if the probe shows it is the smallest way to keep policy and
claims synchronized. Start with a failing automation test for each required
property: required policy discoverability, exact capability status, package
metadata and license inclusion, supported artifact formats, migration and
deprecation coverage, clean installation, and advisory disposition. Avoid a
second prose-only release system.

Third, write the minimal policies and migration/compatibility tables around
already published versions. Security and privacy text must state threat and
trust boundaries, reporting paths, supported fixes, data retention, external
adapter/process risks, and known deferrals. Packaging/licensing/support text
must state artifact scope, platform/toolchain matrix, dependency and notice
handling, supported install path, response ownership, versioning, and
deprecation windows. Any choice reserved to the owner becomes an explicit
decision gate before edits.

Fourth, extend the release checklist and clean package contract only where the
new REDs require it. Prove wheel and sdist reproducibility/contents as supported,
fresh isolated installation, installed CLI/schema operation, all three adapters'
bounded scenarios, frontend build/lint, and failure on stale or inflated public
claims. Keep adapters out of the Python core and do not weaken existing gates.

Finally, commission independent policy/claims, security/privacy/licensing, and
packaging/release audits. Reproduce every accepted finding, retain its RED,
close it minimally, and rerun affected suites. Then run all eight gates locally
and from a physical clean-source snapshot with fresh locked installs, inspect
the complete diff, update `BASELINE.md`, this plan, `STATE.md`, and CAP-214, and
commit the accepted release boundary.

## Concrete Steps

Work from `/home/deliner/projects/ucf` and stream evidence to the terminal and
artifact files:

    mkdir -p .artifacts/quality/rel002-start-20260721
    git status --short | tee \
      .artifacts/quality/rel002-start-20260721/git-status-start.log
    git ls-files | sort | tee \
      .artifacts/quality/rel002-start-20260721/tracked-files.log
    uv build --clear 2>&1 | tee \
      .artifacts/quality/rel002-start-20260721/build-baseline.log
    python3 tools/quality_gates.py --profile package 2>&1 | tee \
      .artifacts/quality/rel002-start-20260721/package-baseline.log

Record npm advisory evidence separately for each lock and do not merge severity
counts across different dependency trees. Use only primary package-manager or
registry output for current advisory facts. Do not add an audit dependency to
the production package merely to run the probe.

For every implementation slice, retain the focused failing test, its intended
failure, the minimal green change, scoped Ruff, and the affected suite. Before
acceptance run:

    uv run --locked --extra dev pytest -q tests/automation --no-cov \
      --capture=tee-sys
    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all
    git diff --check

## Validation and Acceptance

REL-002 is accepted only when fresh executable evidence proves:

1. compatibility and migration rules name every supported serialized/CLI
   version and reject unknown, incompatible, downgraded, or broken inputs;
2. security and privacy policies accurately name the current-user process,
   filesystem, authenticity, raw-data, secret, sandbox, hook, and reporting
   boundaries, with every critical advisory resolved or explicitly deferred by
   an authorized decision and non-misleading support status;
3. wheel and supported source distribution include required schemas, metadata,
   license/notices, and documentation, install in clean environments, and run
   the advertised CLI and release scenarios without checkout imports;
4. dependency and license inventories are derived from exact locks/artifacts,
   and every production or bundled dependency has an accepted disposition;
5. support and deprecation policies define supported Python, Node, Go, OS/
   architecture, adapter/profile, serialized-version, response, and retirement
   boundaries without claiming more than the checked matrix;
6. the release checklist fails on missing policy, package files, stale checked
   evidence, inflated capability text, a critical unowned blocker, or a clean-
   install failure;
7. README, documentation index, capability matrix, package metadata, benchmark,
   and release policy agree; CAP-214 changes from `planned` only to the exact
   status proved by the final gates;
8. all eight quality gates, affected suites, independent audits, complete diff
   review, physical clean-source replay, and clean wheel/sdist release scenarios
   pass from fresh locked installs.

## Idempotence and Recovery

Inventory and audit commands are read-only apart from ignored artifacts and
build output. Use new timestamped artifact directories so failed evidence is
not overwritten. Build and install into disposable directories outside the
checkout; never repair generated distribution contents manually. Publication
checks must write to absent temporary paths or perform an exact no-op. A failed
release checklist publishes no acceptance marker and cannot change a baseline,
version, tag, remote repository, registry, or hosted service.

If a dependency service is unavailable, retain the typed/network failure and
repeat it; do not record a clean advisory result. If a human decision gate is
reached, record options, consequences, evidence, and recommendation here and
set `docs/automation/STATE.md` to `blocked_on_decision` before stopping.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/rel002-start-20260721/` for the foundation inventory;
- `.artifacts/quality/rel002-rgr-20260721/` for focused RED/GREEN slices;
- `.artifacts/quality/rel002-final-20260721/` for local acceptance;
- `.artifacts/agents/rel002-*/` for independent reviews and clean snapshots.

Never retain credentials, registry tokens, private dependency metadata, raw
sensitive runtime values, unbounded command output, or dependency caches.

## Interfaces and Dependencies

REL-002 consumes every package accepted through REL-001 and must not reinterpret
their wire versions. Expected release-facing additions are documentation,
package metadata, a bounded release-readiness/checklist contract, automation
tests, and clean-distribution checks. The exact shape remains contingent on the
foundation probe; avoid a serialized product resource unless a real consumer
requires one.

No new production dependency, license, hosted service, signing identity,
registry publication, tag, or remote write is authorized by this plan. The
project owner must decide any such gate. Build and audit tools used only in
isolated verification must be exact-versioned or otherwise captured in command
evidence and must not silently enter the runtime dependency set.
