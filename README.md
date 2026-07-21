# Use Case-Driven Development Framework (UCF)

> **Current status — `0.1.x` production preview; not a stable API.** The
> supported control plane is CPython 3.12 on Linux/x86_64 with no SLA. The
> canonical statement of implemented, experimental, and planned support is
> [docs/CAPABILITIES.md](docs/CAPABILITIES.md). Accepting a source document
> records declared intent; it does not prove execution or formal verification.

## Purpose

UCF is being built as a language-neutral behavior and change control plane. The
current repository provides strict YAML source parsing, source-level
composition and graph analysis, and an experimental Python pytest contract
skeleton. It also provides exact-version, language-neutral behavior IR and
trust IR `1.0.0` boundaries with conflict-preserving reconciliation and exact
claim evidence checks. It also has an experimental exact-version
out-of-process adapter protocol and installed cross-runtime conformance kit.
An experimental exact observed-inventory profile and installed
`ucf adapter inventory` command establish the read-only first stage of
brownfield adoption. One checked Python vertical slice now adds exact
candidate review, explicit reconciliation, and a non-enforcing baseline through
installed `ucf adapter discover` and `ucf adapter onboard` commands. A separate
experimental ratchet `1.0.0` boundary now establishes explicit legacy
allowances, blocks new or touched regressions, and protects improvements through
installed `ucf ratchet establish`, `evaluate`, and `advance`. Parallel Ratchet
`2.0.0` adds a separate unresolved-coverage-debt ledger, protects resolved
coverage debt, and provides an exact v1 migration without changing v1. A separately
packaged private TypeScript/Fastify adapter now proves the same
neutral inventory, discovery, explicit review, mapping, and one real HTTP
`tested` path on a single frozen Node/Linux fixture. A separately built Go
standard-library adapter provides a second, narrow ecosystem proof on one
unchanged six-file Go/Linux fixture: exact inventory, four reviewed candidates,
one exact mapping, and one passed-only loopback HTTP `tested` path. Its separate
ECO-003 profile now proves one real CLI procedure and one temporally decoupled
local file-spool event procedure on a second frozen Go/Linux fixture through
the same neutral mapping and tested-only evidence rules. Broader Go, other
compiled ecosystems, and platforms beyond those exact procedures remain
outside the claim. An exact experimental generation `1.0.0` profile now drives
one external Python/pytest function-test backend, publishes a deterministic
generated-only tree, and executes its output from a clean wheel environment.
Revision-bound evidence and the three-fixture benchmark are implemented with
the exact limits in the capability matrix. Production-preview release
acceptance remains pending until CAP-214's complete executable checklist is
proved.

## Install and inspect a preview artifact

From a reviewed checkout, build both candidate artifacts and install the wheel
into a fresh supported environment:

```bash
uv build --sdist --wheel --clear
python3.12 -m venv /tmp/ucf-0.1-preview
/tmp/ucf-0.1-preview/bin/python -m pip install dist/ucf-0.1.0-py3-none-any.whl
/tmp/ucf-0.1-preview/bin/ucf --version
/tmp/ucf-0.1-preview/bin/ucf --help
```

Do not treat an arbitrary local build as an accepted release. Published
artifacts are immutable and must come with their recorded SHA-256 values. The
complete release check also reproduces the source distribution, builds the
wheel from it, tests supported dependency floors, runs installed ecosystem
scenarios, audits exact dependencies and licenses, and verifies the selected
GitHub security/support surfaces. See the
[packaging policy](docs/release/PACKAGING.md) and exact capability limits before
using an adapter or evidence claim in production.

## Philosophy

### Principle 1: Use Case is the Unit of Software

The minimal unit of software value is not a function, class, or endpoint — it's a **Use Case**: a complete user scenario. Everything else (code, tests, infrastructure) exists only to make Use Cases work.

### Principle 2: Compose, Don't Duplicate

Any specification element is described once and reused via references. Duplication is a spec bug.

### Principle 3: Claims Follow Evidence

A specification is declared intent. A generated verification method is a
user-owned obligation. UCF reserves stronger labels such as `tested` and
`verified` for reproducible evidence with an explicitly recorded scope.

## Current Scope

| Area | Current evidence-backed scope |
|---|---|
| Source model | Six strict YAML document kinds and a generated JSON Schema |
| Behavior IR | Exact IR 1.0.0 closed entity graph, canonical JSON, typed semantic validation, published schema, and `ucf ir validate` |
| Trust IR | Exact trust IR 1.0.0 immutable declarations, observations, candidates, mappings, independent claims, published schema, and complete `ucf trust validate --behavior-ir` |
| Adapter protocol | Experimental exact protocol 1.0.0 plus conformance kit 1.0.0: strict serialized cases, closed schema/manifest/fixture inventory, digest-indexed extraction, deterministic reports, and a dependency-free sample |
| Brownfield inventory | Experimental observed-only inventory 1.0.0: three exact schemas, deterministic bounded paging, explicit provenance/confidence/coverage/diagnostics, an installed atomic-output command, and a checked external POSIX fixture adapter |
| Brownfield onboarding | Experimental onboarding 1.0.0 on one checked Python fixture: deterministic candidate export, explicit accept/edit/reject/uncertain review, Behavior/Trust materialization, and a non-enforcing baseline bundle |
| Baseline and ratchet | Experimental language-neutral Ratchet 1.0.0 plus parallel Ratchet 2.0.0 dual ledgers: exact Behavior allowances, unresolved coverage debt, semantic/observed touch selection, protected improvements, immutable successors, and strict v1 migration |
| TypeScript/Fastify proof | Experimental external adapter on one frozen TypeScript 7.0.2/Fastify 5.10.0 fixture under Node 22.22.3/Linux/x64: exact inventory, four review candidates, explicit quote-order mapping, real loopback HTTP execution, and passed-only `tested` evidence |
| Go standard-library proof | Experimental external adapter on one unchanged six-file fixture with Go directive 1.26.0, toolchain go1.26.5, `net/http`, and Linux/amd64: 51 exact inventory records, four reviewed candidates, one exact quote-order mapping, and one passed-only loopback HTTP `tested` claim |
| CLI/event platform proof | Experimental exact Go 1.26.5/Linux/amd64 profile on one frozen nine-file fixture: 14 filesystem entries, one reviewed quote-order candidate and mapping, one real CLI process, four-process local file-spool enqueue/observe/dispatch/observe behavior, and passed-only adapter-attested `tested` evidence |
| Change lifecycle | Experimental exact lifecycle 1.0.0 with six immutable resources, eight installed commands, and byte-preserving import/export for the pinned `fission-ai.openspec/spec-driven@1` profile tested against OpenSpec 1.6.0 |
| Composition and graph | `extends` plus relationships declared in loaded specs |
| Generation | Experimental exact request/result 1.0.0 plus one external Python/pytest action-function backend, deterministic receipt-backed generated-only publication, clean pytest 9.1.1 execution, and protected user implementation; the legacy source-YAML skeleton remains separate |
| Verification evidence status | Experimental evidence-status 1.0.0: exact passed-result envelopes plus deterministic `fresh`, selectively `stale`, or missing-context `indeterminate` assessments through installed create-only commands; no `verified` promotion |
| Source platform fields | Declaration-only HTTP, gRPC, GraphQL, UI, CLI, Kafka, event, and protocol intent unless an exact executable capability row separately names a checked procedure |
| Analysis | Experimental declared-data-flow, completeness, Python marker drift, and web catalog features |
| Delivery | Canonical local/CI gate manifest, reproducible Python wheel, isolated install smoke, and a trusted project Codex Stop hook |
| Release boundary | `0.1.x` production preview on CPython 3.12/Linux x86_64 with no SLA; release acceptance remains CAP-214 work, adapters remain experimental exact proofs, and formal `verified` claims are unavailable |

Exact limits and the command evidence for every row are maintained in
[docs/CAPABILITIES.md](docs/CAPABILITIES.md).

## Current Architecture

```text
strict YAML source documents
          |
          v
parser + validator -> registry -> source composition + spec-only graph
                               -> experimental analysis and web catalog
                               -> experimental Python pytest skeleton

behavior IR 1.0.0 JSON
          |
          v
strict raw decoder -> closed records -> typed graph/port validation
                                   -> canonical JSON / published schema

trust IR 1.0.0 JSON + exact behavior IR
          |
          v
strict raw decoder -> immutable intent/evidence records -> explicit mapping
                  -> exact claim predicates / canonical JSON / published schema

Python control plane -- strict adapter protocol 1.0.0 --> external process
                    <-- typed result/error + stderr diagnostics --

repository + explicit ignore policy
          |
          v
external inventory adapter -> bounded observed pages -> strict assembly
                                                   -> canonical snapshot

reviewed onboarding bundle + exact assessment + accepted ratchet baseline
          |
          v
stable subject fingerprints -> Behavior + coverage ledgers -> explicit successor
                  unchanged / touched / resolved / unresolved / regression

passed verification result + exact recorded context
          |
          v
immutable evidence envelope -> current-context projection comparison
                            -> fresh / selective stale / indeterminate
```

There is deliberately no implicit source-spec-to-IR promotion. Trust
reconciliation consumes explicitly supplied immutable records. The
capability-negotiated out-of-process boundary now has a public experimental
conformance kit. Candidate commands still run as the current user; conformance
is not an adapter sandbox, ecosystem support, or production-readiness claim.
See [docs/ADAPTER_PROTOCOL.md](docs/ADAPTER_PROTOCOL.md) and
[docs/ADAPTER_CONFORMANCE.md](docs/ADAPTER_CONFORMANCE.md). The narrower
observed-inventory contract, command, and privacy limits are documented in
[docs/INVENTORY.md](docs/INVENTORY.md). The exact two-phase candidate review
and baseline boundary is documented in
[docs/ONBOARDING.md](docs/ONBOARDING.md). The v1 and v2 baseline comparisons,
dual-ledger coverage semantics, exact v1 migration, atomic transactions, and
trust-anchor limits are documented in
[docs/RATCHET.md](docs/RATCHET.md). Explicit recorded-only runtime evidence,
privacy, sampling, and observed-only projection are documented in
[docs/RUNTIME_EVIDENCE.md](docs/RUNTIME_EVIDENCE.md).
Exact passed-result recording, selective invalidation, refresh, and trust
limits are documented in
[docs/EVIDENCE_STATUS.md](docs/EVIDENCE_STATUS.md).
The exact single-fixture TypeScript/Fastify proof and its distribution,
runtime, authenticity, and breadth limits are in
[adapters/typescript-fastify/README.md](adapters/typescript-fastify/README.md).
The exact single-fixture Go standard-library proof and its distribution,
runtime, licensing, authenticity, and breadth limits are in
[adapters/go-stdlib/README.md](adapters/go-stdlib/README.md).

## Documentation Index

| Document | Description |
|---|---|
| [docs/CAPABILITIES.md](docs/CAPABILITIES.md) | Canonical current capability, evidence, and limitation matrix |
| [docs/IR.md](docs/IR.md) | Exact behavior/trust IR 1.0.0 wire, compatibility, validation, reconciliation, and canonicalization contracts |
| [docs/ADAPTER_PROTOCOL.md](docs/ADAPTER_PROTOCOL.md) | Exact adapter protocol 1.0.0 wire, capability, lifecycle, process-safety, schema, and current limitation contract |
| [docs/ADAPTER_CONFORMANCE.md](docs/ADAPTER_CONFORMANCE.md) | Installed kit 1.0.0 commands, profile, fixtures, report, process, and security boundary |
| [docs/INVENTORY.md](docs/INVENTORY.md) | Observed inventory 1.0.0 schemas, CLI, paging, determinism, read boundary, and deferred onboarding stages |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | Exact discovery/review/bundle 1.0.0 profiles, two-phase installed CLI, trust boundary, atomicity, and measured Python-fixture limits |
| [docs/RATCHET.md](docs/RATCHET.md) | Exact Ratchet 1.0.0 and parallel 2.0.0 dual-ledger documents, migration, transactions, safety, and measured limits |
| [docs/RUNTIME_EVIDENCE.md](docs/RUNTIME_EVIDENCE.md) | Optional recorded runtime evidence 1.0.0 schemas, installed CLI, privacy/sampling boundary, and observed-only projection |
| [docs/EVIDENCE_STATUS.md](docs/EVIDENCE_STATUS.md) | Exact evidence-status 1.0.0 envelopes, assessment CLI, selective invalidation, publication, and trust limits |
| [docs/GENERATION.md](docs/GENERATION.md) | Exact generation 1.0.0 resources, external Python/pytest backend, deterministic ownership transaction, installed CLI, execution evidence, and Linux/security limits |
| [docs/release/README.md](docs/release/README.md) | Production-preview release policy index and acceptance boundary |
| [docs/release/COMPATIBILITY.md](docs/release/COMPATIBILITY.md) | Independent version axes, strict compatibility, and platform boundary |
| [docs/release/MIGRATION.md](docs/release/MIGRATION.md) | Preview upgrade/rollback and exact Ratchet v1-to-v2 migration |
| [docs/release/PRIVACY.md](docs/release/PRIVACY.md) | Local data flow, authority, minimization, logging, and retention |
| [docs/release/PACKAGING.md](docs/release/PACKAGING.md) | Distribution contents, clean installation, licensing, notices, and integrity |
| [docs/release/SUPPORT.md](docs/release/SUPPORT.md) | CPython 3.12/Linux x86_64 support tier, experimental proofs, and no-SLA channel |
| [docs/release/VERSIONING.md](docs/release/VERSIONING.md) | Preview versioning, artifact immutability, deprecation, and security withdrawal |
| [SECURITY.md](SECURITY.md) | GitHub private vulnerability reporting requirements and advisory policy |
| [LICENSE](LICENSE) and [NOTICE](NOTICE) | Apache-2.0 license and `Copyright 2026 Deliner` notice |
| [adapters/typescript-fastify/README.md](adapters/typescript-fastify/README.md) | Exact private adapter, frozen fixture, real HTTP verification, packaging evidence, and narrow TypeScript/Fastify limits |
| [adapters/go-stdlib/README.md](adapters/go-stdlib/README.md) | Exact external adapter, frozen HTTP and CLI/event fixtures, real bounded procedures, distribution notices, process boundary, and narrow Go standard-library limits |
| [SPEC_LANGUAGE.md](SPEC_LANGUAGE.md) | Current source-declaration shapes and illustrative examples |
| [CONTEXT_TRACER.md](CONTEXT_TRACER.md) | Experimental declared-data-flow analysis |
| [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) | Current spec-only graph plus historical target design |
| [GENERATORS.md](GENERATORS.md) | Experimental Python contract-skeleton generation |
| [INVARIANTS.md](INVARIANTS.md) | Invariant declaration forms and target verification design |
| [.codex/hooks.json](.codex/hooks.json) | Current trusted-project Codex Stop hook over the canonical gate runner |
| [CURSOR_HOOKS.md](CURSOR_HOOKS.md) | Historical Cursor-specific integration design; not the Codex hook contract |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Historical roadmap; current work is tracked under `docs/automation/` |
| [CRITIQUE.md](CRITIQUE.md) | Known limitations, edge cases, and mitigations |

## Conceptual Formula

```
Use Case = State Setup + Action Sequence + Verification
```

- **State Setup** declares the required initial state.
- **Action Sequence** declares ordered behavior and data mappings.
- **Verification** declares obligations that require executable evidence.

For the currently supported Python generation subset, UCF emits
generated-owned interface and orchestrator structure plus a user-owned
implementation stub. A developer must supply the implementation and fixtures.
That generator is not the separately checked adapter execution path and is not
evidence of automatic invariant verification.
