# REL-001 End-to-End Adoption Benchmark

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect current
repository evidence. Maintain it according to `PLANS.md`.

## Purpose / Big Picture

After this package, a prospective adopter can inspect one reproducible report
showing the complete UCF workflow against three unchanged legacy applications:
Python, TypeScript/Fastify, and Go. The report names what was discovered,
which candidates required scripted review, what was rejected, what behavior
was tested, how HTTP/CLI/event checks were covered, how long each phase took,
and how much UCF material was added outside the applications. Claims remain at
their actual observed/declared/mapped/tested levels.

## Foundational Assumption

The root assumption is that the accepted fixture-specific inventory,
discovery, reconciliation, baseline/ratchet, mapping, verification,
evidence-status, and lifecycle surfaces can be composed into one comparable
benchmark without changing a stable core schema or adapter protocol. The
benchmark itself should be repository/release proof, not a new product IR.

Challenge this before production edits with the cheapest useful experiment:
copy each frozen fixture, run its existing native check plus the smallest
accepted inventory/discovery/mapping/verification path, and inventory which
canonical outputs and timings are already available. Compare fixture manifests
before/after and build a field-sufficiency table for candidates emitted,
review decisions, accepted/rejected candidates, tested claims, platform
procedures, elapsed runtime, source size, and UCF artifact size. Retain the
probe under `.artifacts/quality/rel001-start-20260720/` and independent
read-only findings under `.artifacts/agents/rel001-*/`.

Alternatives are: orchestrate existing public CLIs from a release-only runner;
add an internal Python benchmark API; or publish three unrelated manual
transcripts. Select the smallest repeatable option that uses installed public
boundaries and produces machine-checked measurements. If comparable output
requires reinterpreting an accepted serialized field or choosing new product
semantics, record a decision gate before implementation.

Result: the assumption is false for the required complete workflow. Python
composes through ratchet. TypeScript and Go compose through real mapping,
verification, tested projection, and fresh evidence, including HTTP, CLI, and
event procedures, but their honest discovery coverage is `partial`. Ratchet
`1.0.0` copies that coverage exactly and rejects both baseline establishment
and advancement. No runner glue can change the result without changing a
public contract, changing accepted adapter semantics, or narrowing the target.

## Progress

- [x] 2026-07-20: Accept VER-002 through independent reviews, complete local
  profile, complete diff hygiene, and physical clean-source replay; create this
  plan and activate REL-001.
- [x] 2026-07-20: Revalidate the composition assumption across all three frozen
  fixtures; reproduce the partial-coverage ratchet blocker independently,
  retain metric inputs and immutable manifests, and open the required public-
  semantics decision gate.
- [ ] After the human decision, update this plan with the selected versioned
  architecture and freeze the final metric definitions.
- [ ] Retain a failing end-to-end benchmark acceptance test, then implement
  the smallest installed/public orchestration and report boundary.
- [ ] Prove unchanged fixtures, native behavior, all required platforms,
  complete adoption/change/evidence flow, deterministic structural results,
  and bounded measured runtime across repeated runs.
- [ ] Publish results and limitations, complete independent audits, affected
  suites, all seven gates, complete diff review, and physical clean-source
  replay before advancing to REL-002.

## Surprises & Discoveries

REL-001 starts with three already frozen fixture families under
`tests/fixtures/brownfield/`: `python_legacy_quote`,
`typescript_fastify_legacy_quote`, and the selected Go fixtures. Existing
tests prove their slices independently, but no single release artifact yet
proves a comparable complete workflow or publishes the required measurements.

The three-lane probe found a real asymmetry. Python discovery is complete and
the existing Ratchet transaction works. TypeScript retains 2 uncovered of 6
eligible public interfaces; Go HTTP retains 8 of 12 and the auxiliary
CLI/event root retains 8 of 9. These partial results are accepted, evidence-
preserving adapter behavior. `build_ratchet_assessment` must copy the partial
status, contextual validation rejects forged escalation, and
`establish_ratchet_baseline` returns `incomplete_coverage`.

Everything before that boundary is composable. TypeScript produces one real
HTTP tested claim and fresh assessment. Go produces real HTTP, CLI, and
temporally decoupled event tested claims and fresh assessments. Fixtures remain
byte-identical. The auxiliary Go platform root is one platform proof inside
the Go lane, not a fourth ecosystem fixture.

Metric categories also require exact separation: an oracle false candidate is
not synonymous with a rejected disposition; an uncertain candidate remains
separate. Review work must report candidate dispositions, ambiguity
resolutions, mapping approvals, and change approvals independently. Persisted
artifact bytes must separate authored and derived material because resources
embed earlier resources.

## Decision Log

- **2026-07-20 — measure review work without pretending automation is a human
  usability study.** Author: root agent. Report exact candidate counts,
  accept/edit/reject decisions, and review actions as machine-countable review
  work. Wall-clock measurements describe execution runtime only. Do not label
  scripted review duration as human effort.
- **2026-07-20 — keep the benchmark outside the core contracts unless the
  falsification probe disproves composability.** Author: root agent. Release
  evidence may orchestrate stable public CLIs and parse their versioned
  resources; it must not add benchmark fields to Behavior, Trust, or adapter
  protocol resources.
- **2026-07-20 — block on partial-coverage ratchet semantics.** Author: root
  agent. This is a human decision gate under `AGENTS.md`: the safe options
  change a closed serialized contract and the alternative narrows required
  product semantics. Root and independent probes reject every no-contract
  workaround. Options:

  1. add Ratchet `2.0.0` with a dual ledger: accepted Behavior debt remains in
     existing violation allowances while unresolved discovery coverage is
     separate non-claim legacy debt; unchanged exact debt may remain, added/
     changed/reintroduced debt blocks, resolved debt becomes protected, and
     partial rule coverage still cannot establish or advance;
  2. add Onboarding v2 decisions for every uncovered interface plus Ratchet v2,
     requiring explicit promote/exclude/defer review at substantially higher
     brownfield review cost;
  3. add a scoped Ratchet v2 whose pass applies only to explicit accepted
     Behavior scope while global coverage remains partial, with a material risk
     of overstated project-wide claims;
  4. narrow/defer REL-001 to Python-only ratchet and publish TypeScript/Go as
     incomplete, which is honest but does not meet the requested final state.

  Recommendation: option 1. Preserve Ratchet `1.0.0` byte-for-byte and add a
  major-version dual ledger derived from existing uncovered references and
  uncertain decisions. It keeps unknowns out of Behavior/claims, permits
  unchanged legacy uncertainty, blocks new uncertainty, and protects
  improvements without hiding accepted inventory evidence.

## Outcomes & Retrospective

REL-001 is blocked on the recorded partial-coverage Ratchet decision. Its
dependency baseline is accepted VER-002: the working
tree and physical clean-source profiles pass all seven gates with 75 automation
tests, 1,880 Python tests at 90% coverage, and reproducible wheel SHA-256
`7311760bf249ad195dbb30ad563cafeddbfee77921851ba5a154ea91ef9cb2ec`.
The fresh REL-001 dependency slice passes 480 tests and scoped Ruff under
`.artifacts/quality/rel001-start-20260720/`. Three fixture probes plus two
independent decision audits are summarized under
`.artifacts/agents/rel001-foundation/`. No production code or accepted
serialized resource was changed after the falsification.

## Context and Orientation

Frozen legacy applications live under `tests/fixtures/brownfield/`. Python
onboarding behavior is exercised through the external reference adapter and
`src/ucf/onboarding/`; TypeScript/Fastify and Go adapter implementations live
under `adapters/` with ecosystem contracts in `tests/ecosystems/` and
`tools/*_adapter_contract.py`. Baseline/ratchet resources are in
`src/ucf/ratchet/`; exact execution mapping/results are in
`src/ucf/implementation_evidence/`; freshness is in
`src/ucf/evidence_status/`; the OpenSpec-compatible lifecycle is in
`src/ucf/change_lifecycle/` and `src/ucf/change_governance/`.

For this package, a false candidate is an emitted candidate that the frozen
review oracle rejects or must materially edit before acceptance. Review effort
is the explicit number of candidate decisions and mapping/change approvals,
reported by decision class; it is not elapsed human time. Runtime is measured
per named phase with a monotonic clock and multiple repetitions. Spec overhead
reports generated/accepted UCF bytes and logical records relative to immutable
legacy source bytes and files, while keeping generated artifacts outside the
fixture.

## Plan of Work

First, freeze source manifests and native commands for all fixtures. Compose
the smallest existing public workflow in disposable copies, enumerate missing
coordinates, and record whether all metrics can be computed without contract
changes.

Second, add one failing automation test for a release benchmark command or
runner that consumes the frozen fixtures and external adapters. Require a
closed versioned report shape, exact fixture and tool identities, complete
phase results, honest claim counts, metric denominators, immutable source
manifests, no embedded absolute/temp paths, and explicit limitations.

Third, implement only the release-proof orchestration selected by the probe.
Keep runtime samples separate from deterministic structural identities.
Execute native pre/post checks, read-only inventory, evidence-bearing
discovery, explicit review/reconciliation, baseline, ratchet, mapping,
verification, evidence record/assessment, and one compatible proposal through
archive wherever the accepted adapter capabilities support them. Represent
unsupported steps as bounded named limitations, never as passes.

Fourth, publish the generated checked report in documentation and update
CAP-213 only to the evidence level actually demonstrated. Add freshness tests
that regenerate structural results and validate measured fields without
requiring byte-identical wall-clock durations.

Finally, complete independent metric/claims, ecosystem/integration, and
security/reproducibility reviews; close accepted findings with retained REDs;
run affected and full profiles; inspect the complete diff; and repeat the
physical source-only snapshot protocol.

## Concrete Steps

Work from `/home/deliner/projects/ucf` and retain streamed evidence:

    mkdir -p .artifacts/quality/rel001-start-20260720
    git status --short | tee \
      .artifacts/quality/rel001-start-20260720/git-status-start.log
    uv run --locked --extra dev pytest -q \
      tests/onboarding tests/ratchet tests/ecosystems \
      tests/implementation_evidence tests/evidence_status \
      --no-cov --capture=tee-sys | tee \
      .artifacts/quality/rel001-start-20260720/focused-baseline.log
    uv run --locked --extra dev ruff check \
      src tests tools | tee \
      .artifacts/quality/rel001-start-20260720/focused-ruff.log

Before acceptance run:

    uv run --locked --extra dev pytest -q tests/automation \
      --no-cov --capture=tee-sys
    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all
    git diff --check

## Validation and Acceptance

REL-001 is accepted only when fresh executable evidence proves:

1. three immutable, unchanged legacy fixtures cover Python, TypeScript/Fastify,
   and Go through the same named adoption stages;
2. native behavior passes before and after, and fixture manifests are unchanged;
3. common adapter conformance plus brownfield inventory/discovery/
   reconciliation/baseline/ratchet/mapping/verification is exercised at the
   exact capability level each selected adapter declares;
4. HTTP, CLI, and asynchronous message/event procedures are tested without
   transport fields entering core IR;
5. false-candidate counts and denominators, explicit review actions, runtime
   samples, and spec-overhead bytes/records are measured per fixture with
   definitions in the report;
6. candidate, observed, declared, mapped, tested, stale, and verified counts
   are not promoted beyond reproducible evidence; verified remains zero;
7. one proposal-to-archive behavior change is linked to exact implementation
   and verification evidence without mutating the legacy fixture;
8. report regeneration validates deterministic structure while treating
   measured durations as samples, and all limitations are explicit;
9. installed/clean-source execution, affected suites, all seven gates,
   independent audits, complete diff review, and documentation claim checks
   pass.

## Idempotence and Recovery

All fixture work occurs in new temporary copies and writes benchmark output
outside the fixture roots. A failed phase preserves its typed report and
never advances later claims. Re-running structural phases with the same inputs
must produce the same canonical resources; runtime samples may differ and are
compared only through declared bounds/statistics. Failed or partial benchmark
publication uses a new output path and cannot replace accepted release
evidence.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/rel001-start-20260720/`;
- `.artifacts/agents/rel001-foundation/`;
- `.artifacts/agents/rel001-metrics-claims-review/`;
- `.artifacts/agents/rel001-integration-review/`;
- `.artifacts/agents/rel001-clean-source-snapshot/`.

Do not retain credentials, private repositories, raw sensitive runtime
payloads, dependency caches, or unbounded process output.

## Interfaces and Dependencies

REL-001 consumes accepted Behavior/Trust IR, adapter protocol/conformance,
inventory, onboarding, ratchet, runtime evidence, implementation evidence,
generation, lifecycle/governance, and evidence-status contracts without
changing their versions. Any benchmark report or runner must have an explicit
version, closed fields, deterministic structural identity, exact fixture/tool
provenance, and a clearly non-normative release-evidence status. No new
production dependency is authorized.
