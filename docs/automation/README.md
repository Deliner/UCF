# Automated UCF delivery

This directory is the durable control plane for long-running Codex work. It
turns the project's desired end state into small, dependency-ordered,
independently verifiable work packages.

## Start or resume

Open Codex at the repository root and invoke:

    Use $ucf-ultrawork. Resume the active work package from
    docs/automation/STATE.md and continue until it is verified or a decision
    gate is reached.

For project-length work, use Codex's `/goal` command with the same objective
when available. The repository skill, `AGENTS.md`, `PLANS.md`, and state file
survive context compaction and new sessions.

`ultrawork` is a local workflow name. The supported Codex mechanisms underneath
it are repository skills, `AGENTS.md`, ExecPlans, goals, tests, and CI.

## Source of truth

- `TARGET_STATE.md` defines the product and architecture destination.
- `BACKLOG.md` orders independently demonstrable work packages.
- `STATE.md` points to exactly one active package and ExecPlan.
- `BASELINE.md` records current evidence and known failures.
- `../../PLANS.md` defines living ExecPlans.
- `../../AGENTS.md` defines engineering and decision policy.

Do not use roadmap status prose elsewhere to override these files. Reconcile
conflicts explicitly and update the source that owns the decision.

## Automation boundary

Codex continues autonomously through routine implementation choices. It stops
for public-contract, irreversible migration, security, dependency/license, or
material product-semantics decisions listed in `AGENTS.md`. This is intentional:
the Golden Flow requires pre-existing problems and real trade-offs to remain
visible to the human owner.

The Python runner is the only executable gate manifest. During ordinary work,
run the gates selected from tracked and untracked changed paths:

    python3 tools/quality_gates.py --profile affected

For package acceptance and release evidence, run the complete profile:

    python3 tools/quality_gates.py --profile all

The complete profile runs automation and Python tests, Ruff, specification
validation, a reproducible-wheel and isolated-install contract, and frontend
build/lint. Output remains visible, every selected phase runs, and complete
logs are retained under `.artifacts/quality/`.

CI invokes that same `all` profile; it does not copy the individual commands.
Inspect the deterministic manifest, including tokenized commands and working
directories, with:

    python3 tools/quality_gates.py --profile all --list --format json

Gate identities are safe unique slugs and are also the retained log identities.
A deliberately failing temporary fixture is covered by
`tests/automation/test_quality_gates.py` and must report the same failed
identity through the local and CI selections.

## Codex Stop hook

The trusted project hook in `../../.codex/hooks.json` uses Codex's official
case-sensitive `Stop` event and calls the canonical runner. Review and trust
the exact hook definition with `/hooks`; Codex skips new or changed
project-local hooks until trusted.

For ordinary packages, the hook selects `affected`. When `STATE.md` names an
active `REL-*` package, it selects `all`. A caller may also explicitly force
the full profile with `UCF_STOP_PROFILE=all`; no other override is accepted.
The hook never parses assistant prose or the unstable transcript to infer
release work, and `stop_hook_active` prevents a failed-gate continuation loop.

The hook is a convenience guardrail: trust settings and managed policy can
disable it. The explicit complete-profile command and CI remain the acceptance
boundaries.
