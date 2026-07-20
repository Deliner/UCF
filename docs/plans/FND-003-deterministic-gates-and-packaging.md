# Stabilize deterministic developer and release gates

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After this package, contributors and CI select the same named quality gates
from one repository-owned manifest. The complete profile builds the Python
distribution reproducibly, installs the wheel into an empty environment, and
proves the installed CLI and packaged data work without source-tree leakage.
A repository-scoped Codex Stop hook runs affected gates during ordinary work
and the complete profile for release work, and a deliberate failing fixture is
reported with the same stable gate identity locally and in the CI contract.

This package stabilizes delivery mechanics for the existing pre-release
control plane. It does not define the language-neutral behavior IR, adapters,
or release policies owned by later packages.

## Foundational Assumption

The root assumption is that `tools/quality_gates.py` can remain the single
executable gate manifest for local, CI, packaging, and hook consumers, while
Hatch can produce a byte-reproducible wheel containing every runtime asset.
Consumers should select profiles or affected gates by stable identity rather
than copy command lists.

The cheapest falsification experiment is to:

1. serialize the current gate identities, commands, and working directories
   and compare them with `.github/workflows/quality.yml`;
2. build two wheels from the same clean source and compare hashes and archive
   inventories;
3. install the wheel into a newly created environment outside the repository,
   run `ucf --help`, load the published schema and generator templates through
   installed-package paths, and validate a minimal copied spec directory;
4. verify the current official Codex hook contract and simulate both an
   ordinary affected run and a release/full run without relying on editor-only
   behavior.

If the runner cannot expose one safe contract for all consumers, prefer a
small versioned data manifest loaded by the runner over parsing Python or
duplicating commands in YAML. If Hatch output is not reproducible, identify
the changing archive metadata or generated content before adding normalization.
If Codex has no repository-scoped Stop-hook contract that can safely enforce
gates, record the official evidence and update this plan before selecting the
smallest supported repository automation boundary.

## Progress

- [x] (2026-07-19) Revalidate the foundational assumption and retain manifest,
  wheel, clean-install, reproducibility, and hook-contract probes under
  `.artifacts/quality/fnd003-start-20260719/` and
  `.artifacts/agents/fnd003-*-probe/`. CI already selects the Python runner's
  `all` profile; two Hatch wheels are byte-identical; an external `uv`
  environment imports only from site-packages and executes the CLI, schema,
  templates, and copied-spec validation. The falsification probes exposed
  missing machine manifest/identity validation, an unpinned Hatchling build
  backend, and the absence of a Codex-provided release flag.
- [x] (2026-07-19) Add RED contract tests for a single canonical local/CI gate
  manifest, then make CI consume and mechanically verify the same profile and
  stable gate identities. The runner now exposes a deterministic versioned
  JSON manifest with tokenized commands and working directories, rejects
  duplicate/unsafe identities before output, and pins every CI action to an
  immutable official tag commit. Evidence: `manifest-contract-red.log`,
  `manifest-contract-green2.log`, and `ci-action-pin-red/green2.log`.
- [x] (2026-07-19) Add RED packaging tests, pin Hatchling 1.31.0, and add the
  `packaging-contract` complete-profile gate. It builds two byte-identical
  wheels, verifies required assets, installs into an external `uv` environment,
  executes the installed CLI, reads schema/templates, validates a copied
  minimal spec, and rejects source-tree imports. Evidence:
  `packaging-gate-red.log`, `packaging-gate-green.log`, and
  `package-contract-green.log`.
- [x] (2026-07-19) Add a RED deliberate-failure parity fixture and prove local
  and CI contracts block it with the same `automation-tests` identity and exit
  19 while retaining separate summaries. The fixture uses temporary commands
  and leaves the repository green. Evidence:
  `.artifacts/agents/fnd003-manifest-probe/failure-parity-scratch.log` and
  `tests/automation/test_quality_gates.py`.
- [x] (2026-07-19) Add and test the repository-scoped official Codex `Stop`
  hook: affected gates for ordinary work and the complete profile only for an
  active `REL-*` package or explicit `UCF_STOP_PROFILE=all`. Tests cover
  configuration, selection, failed-gate continuation, sanitized evidence
  paths, exact JSON stdout, and `stop_hook_active` loop prevention. Evidence:
  `stop-hook-red.log`, `stop-hook-green.log`, and
  `affected-manifest-green.log`.
- [x] (2026-07-19) Update CAP-201 and developer documentation, run affected
  suites and the complete profile, review the entire diff, obtain independent
  clean-snapshot acceptance, update baseline, and advance state to `IR-001`.
  The accepted locked profile is
  `.artifacts/quality/fnd003-final2-20260719/`: 25 automation tests, 408 Python
  tests at 86% coverage, 113 specs with zero errors/warnings, the reproducible
  packaging contract, and both web gates all pass. Independent locked-snapshot
  evidence under `.artifacts/agents/fnd003-final-audit-locked/` reproduces all
  seven gates and confirms that the lockfile is unchanged.

## Surprises & Discoveries

- Observation: CI already invokes the same `tools/quality_gates.py --profile
  all` authority as local release work and duplicates none of its six
  commands. However, `--list` omits working directories and has no
  deterministic machine representation. Duplicate gate identities also run
  and overwrite the same evidence log.
  Evidence:
  `.artifacts/agents/fnd003-manifest-probe/report.md`.
- Observation: two current wheels are byte-identical at
  `d722940192eecb59325d49636b05a6a019c7e27f145238f718a705da8292a545`,
  contain the schema and all three templates, and work from an external
  `uv`-created environment with no checkout path in `sys.path`. Reproducibility
  is not yet durable because `pyproject.toml` accepts any Hatchling version;
  the observed wheel was built by Hatchling 1.31.0.
  Evidence:
  `.artifacts/agents/fnd003-packaging-probe/summary.log` and
  `build-tool-version-risk.log`.
- Observation: the current host's standard-library `venv` cannot bootstrap
  pip because `ensurepip` is absent. This is a host limitation, not a wheel
  defect; the repository already pins and installs `uv`, which can create the
  required isolated environment.
  Evidence:
  `.artifacts/agents/fnd003-packaging-probe/report.md`.
- Observation: official Codex supports stable trusted project hooks in
  `.codex/hooks.json` and a turn-scoped `Stop` event. `Stop` ignores matchers
  and its documented payload has no release-work field. It provides
  `stop_hook_active` for loop prevention and requests continuation after a
  failed check with `{"decision":"block","reason":"..."}`.
  Evidence:
  `.artifacts/quality/fnd003-start-20260719/codex-hook-contract.log`,
  the official `https://learn.chatgpt.com/docs/hooks#stop` section, and
  `.artifacts/agents/fnd003-hook-probe/report.md`.
- Observation: three GitHub Actions references used mutable major tags even
  though CI's executable gate selection was already canonical. The official
  tag refs resolve to immutable commits and can be pinned without changing
  action providers or behavior.
  Evidence: `checkout-v7-tag.log`, `setup-node-v6-tag.log`,
  `upload-artifact-v7-tags-expanded.log`, and
  `ci-action-pin-green2.log`.
- Observation: `uv run` resolves the project before executing a gate and,
  without `--locked`, may refresh an outdated lockfile instead of rejecting
  the non-reproducible input. All five project-environment gates now require
  the checked lockfile; the independent clean-snapshot profile leaves
  `uv.lock` byte-identical.
  Evidence: `locked-gates-red.log`, `locked-gates-green.log`, and
  `.artifacts/agents/fnd003-final-audit-locked/report.md`.

## Decision Log

- Decision: begin with the existing Python gate runner as the candidate
  authority, subject to the foundational experiment.
  Rationale: CI already invokes its `all` profile and it streams stable named
  phases with retained logs. Extending one authority is smaller and safer than
  introducing a second workflow DSL before evidence shows one is needed.
  Date/Author: 2026-07-19 / Codex.
- Decision: keep `PROFILES` as the sole executable manifest and expose a
  versioned deterministic JSON view instead of adding a second data file.
  Rationale: local and CI already select the same profile. Machine-readable
  identities, tokenized commands, and working directories plus duplicate/safe
  identity validation close the observable contract gap without duplicating
  command ownership.
  Date/Author: 2026-07-19 / Codex.
- Decision: pin the already selected Hatchling 1.31.0 build backend and use
  repository-pinned `uv` for isolated-install evidence.
  Rationale: current artifact bytes and runtime behavior pass, but an
  unconstrained PEP 517 backend can change clean-build output independently of
  the source revision. Exact pinning makes intentional backend upgrades
  reviewable. `uv` works on the accepted environment even where `ensurepip` is
  unavailable and is already part of local/CI setup.
  Date/Author: 2026-07-19 / Codex.
- Decision: select full Stop-hook gates only from explicit UCF-owned release
  state, never Codex transcript or assistant prose.
  Rationale: `Stop` supplies no release flag and documents transcript format as
  unstable. The hook will default to `affected`, select `all` when
  `docs/automation/STATE.md` names an active `REL-*` package or an explicit
  validated environment override requests it, and use `stop_hook_active` to
  prevent continuation loops. Explicit CI/release commands remain
  authoritative because project hooks require trust and can be disabled.
  Date/Author: 2026-07-19 / Codex.
- Decision: pin every existing GitHub Action reference to the commit resolved
  by its selected major tag and retain the major version as a review comment.
  Rationale: moving action tags are external executable inputs. Exact commits
  close the known CI reproducibility gap without selecting a new action,
  license, or hosted service.
  Date/Author: 2026-07-19 / Codex.
- Decision: add `--locked` to every canonical `uv run` gate.
  Rationale: a quality check must reject dependency-manifest drift rather than
  mutate the lockfile while deciding whether the checkout passes. Clean
  installation of the built wheel intentionally remains a separate
  declared-dependency test, outside the project environment.
  Date/Author: 2026-07-19 / Codex.

## Outcomes & Retrospective

FND-003 is complete. The runner now has one versioned machine-readable
local/CI manifest, immutable and unique gate identities, lock-enforced project
environments, affected selection, and pinned CI action inputs. A deliberate
temporary exit-19 fixture produces the same `automation-tests` failure identity
for local and CI selections.

The complete profile builds two byte-identical wheels with pinned Hatchling,
checks runtime assets, installs outside the checkout, executes the installed
CLI, reads the schema and templates, and validates a copied source spec. The
official trusted-project Codex Stop hook uses affected gates during ordinary
packages and full gates only for explicit UCF release state, with exact JSON
output and continuation-loop prevention.

Local and independent clean-snapshot profiles pass all seven gates with 25
automation tests, 408 Python tests at 86% coverage, 113 specifications with
zero errors and warnings, and green Ruff/frontend checks. Four independently
observed wheel builds share SHA-256
`d722940192eecb59325d49636b05a6a019c7e27f145238f718a705da8292a545`;
the post-audit locked delta preserves that hash and leaves `uv.lock`
unchanged.

CAP-201 limits this evidence to the current Python 3.12 wheel workflow. Hosted
runtime patch labels, npm advisories, sdist/cross-platform/signing policy, and
the fact that project hooks require explicit trust remain visible release
inputs for REL-002 rather than being presented as solved by this package.

## Context and Orientation

`tools/quality_gates.py` declares `Gate` objects, named profiles, live output,
and retained per-gate logs. `.github/workflows/quality.yml` installs locked
Python/frontend tooling and invokes its `all` profile. Automation tests live in
`tests/automation/`.

Python packaging is configured by `pyproject.toml` and `uv.lock` using Hatch.
The import package is beneath `src/ucf`; runtime assets include
`src/ucf/schemas/` and `src/ucf/generator/templates/`. The clean-install test
must run from a temporary directory outside the checkout with an environment
whose interpreter has only the built wheel and its declared dependencies.

Repository automation configuration must be checked in and non-interactive.
The hook is a convenience enforcement boundary, not evidence by itself:
release acceptance still requires a fresh explicit
`python3 tools/quality_gates.py --profile all` run.

## Plan of Work

First retain the four falsification probes without production changes and
record which assumptions hold. Read the supported Codex hook contract from
official primary documentation before creating configuration. Update this
plan if repository-level Stop hooks are unsupported or their event payload
cannot distinguish ordinary and release work safely.

Add one contract test at a time. Start with manifest parity: the test must fail
because CI or another consumer duplicates an unverifiable selection, then make
the smallest runner/workflow change that exposes and validates one canonical
profile. Next make clean install and two-build reproducibility fail for their
actual missing behavior before adding packaging gates.

Add the deliberate failing fixture through a temporary test-only gate; do not
commit a permanently failing repository fixture. Assert the stable gate name,
exit status, and retained summary locally and through the same CI profile
selection contract. Then implement the hook as a thin selector over the
canonical runner and test its event handling without invoking an editor.

Finally update `docs/CAPABILITIES.md` only to the exact accepted scope, document
the contributor commands, run the focused and affected suites, run all gates,
inspect artifact hashes and installed-package paths, review the complete diff,
and obtain an independent clean-copy acceptance audit.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream and retain the foundational
evidence:

    mkdir -p .artifacts/quality/fnd003-start-20260719
    python3 tools/quality_gates.py --profile all --list | \
      tee .artifacts/quality/fnd003-start-20260719/local-manifest.log
    uv build --wheel --out-dir \
      .artifacts/quality/fnd003-start-20260719/wheel-a
    uv build --wheel --out-dir \
      .artifacts/quality/fnd003-start-20260719/wheel-b

The experiment must also retain archive hashes/inventories, isolated install
commands and outputs, the CI selection inventory, and the official hook
contract citation or local manual evidence. RED/GREEN commands must use `tee`
or equivalent live retained logs.

Expected focused suites include:

    uv run --extra dev pytest -q tests/automation --no-cov
    uv run --extra dev ruff check src tests tools

Before acceptance run:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/fnd003-final-<date>
    git diff --check

## Validation and Acceptance

The package is accepted only when:

1. local and CI consumers select an identical canonical set of stable gate
   names, commands, and working directories;
2. the complete profile builds the wheel twice reproducibly and installs it
   into an empty external environment;
3. installed CLI, schema access, templates, and copied-spec validation work
   without importing from the checkout;
4. a deliberate failing temporary fixture blocks local and CI contracts with
   the same gate identity and non-zero result;
5. the tested repository hook selects affected gates for ordinary work and the
   complete profile for release work without weakening explicit release gates;
6. all complete-profile gates, `git diff --check`, and an independent
   clean-copy audit pass with fresh retained evidence.

## Idempotence and Recovery

Builds, manifests, and smoke tests write only beneath explicit artifact or
temporary directories. Wheel environments must be disposable and must not
reuse the repository `.venv`. Repeated hook delivery must be safe and must not
modify source files. A failed gate retains its log and summary, returns
non-zero, and never resets a baseline. Remove only package-owned temporary
directories; preserve all unrelated working-tree changes.

If an interrupted build leaves an artifact directory, use a new named
directory rather than deleting evidence. If the hook is invoked without enough
event context, default to the safer canonical affected selection and require
an explicit release signal for the complete profile.

## Artifacts and Notes

FND-002 accepted evidence is in
`.artifacts/quality/fnd002-final-20260719/` and
`.artifacts/agents/fnd002-final-audit/`. FND-003 foundational and RED/GREEN
evidence belongs under `.artifacts/quality/fnd003-start-20260719/`; final local
acceptance belongs in a separate `fnd003-final-*` directory.
Accepted local evidence is
`.artifacts/quality/fnd003-final2-20260719/`. The initial independent report is
`.artifacts/agents/fnd003-final-audit/report.md`; the exact accepted
lock-enforcement snapshot is
`.artifacts/agents/fnd003-final-audit-locked/report.md`.

## Interfaces and Dependencies

Public and repository contracts in scope are:

- `tools.quality_gates.Gate`, named profiles, CLI selection/listing, exit
  status, summaries, and retained log names;
- `.github/workflows/quality.yml` as the CI consumer;
- the built `ucf` wheel, its console entry point, schemas, and generator
  templates;
- the repository-scoped Codex automation configuration and its thin,
  directly-testable selector;
- `docs/CAPABILITIES.md` and contributor-facing gate documentation.

No new production dependency, hosted service, IR field, adapter semantic,
framework integration, or release policy is authorized. Development tooling
must remain lockfile-pinned, and any new dependency or unsupported automation
contract would require the decision policy in `AGENTS.md`.
