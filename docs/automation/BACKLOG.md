# Dependency-ordered delivery backlog

Each work package must have one ExecPlan and one independently demonstrable
outcome. The order challenges the highest-risk assumptions before expanding the
feature surface.

## Foundation

### FND-001 — Restore a trustworthy green baseline

Remove current test collection failures, make newly generated tests collect and
execute, repair invalid repository specs and references, make Python lint and
frontend build/lint green, and keep the fixes behavior-preserving.

Acceptance: `python3 tools/quality_gates.py --profile all` exits zero from a
clean checkout. A fresh generation fixture is included in the test suite so the
template defect cannot return.

### FND-002 — Make parser and claims strict

Reject unknown schema fields, duplicate identities, unresolved references, and
unsupported features at the correct boundary. Generate versioned JSON Schemas.
Replace documentation claims that are not backed by executable evidence with a
capability/status matrix.

Acceptance: negative fixtures prove every rejection; published schemas validate
all repository specs; each public capability is labeled implemented,
experimental, or planned and links to a verification command.

### FND-003 — Stabilize deterministic developer and release gates

Keep local and CI commands identical, add packaging/install smoke tests, enforce
artifact reproducibility, and enable a Codex Stop hook only after the complete
baseline is green. The hook must use affected gates during normal work and full
gates for release work.

Acceptance: local and CI manifests select the same commands, a built wheel
installs in an empty environment, and a deliberate failing fixture blocks both
paths with the same gate identity.

## Language-neutral core

### IR-001 — Define the minimum versioned behavior IR

Define serialized identities, use cases, actions, bindings, effects,
observations, invariants, provenance, evidence, and capability requirements.
Specify compatibility rules before adding adapter-specific fields.

Acceptance: golden JSON fixtures round-trip deterministically; incompatible
versions fail clearly; no fixture contains a Python module, class, decorator, or
AST-specific concept.

### IR-002 — Separate declared intent from observed evidence

Model declarations, observations, mappings, confidence, and claim levels
without allowing discovery to overwrite intent.

Acceptance: tests demonstrate conflicting declared and observed facts survive
reconciliation, uncertain candidates cannot become `tested`, and every claim
can be traced to its source and tool version.

### ADP-001 — Prove an out-of-process adapter protocol

Create the smallest capability-negotiated, versioned protocol for inventory,
discovery, mapping, generation, and verification. Evaluate JSON-RPC over
stdio against one simpler alternative in the ExecPlan before selecting it.

Acceptance: a reference adapter runs in a separate process, negotiates
capabilities, handles cancellation and structured errors, and passes a
transport-independent contract suite.

### ADP-002 — Publish an adapter conformance kit

Provide language-neutral request/response fixtures, protocol tests, and a
minimal sample adapter so another ecosystem can implement support without
importing Python.

Acceptance: the sample adapter and an intentionally faulty adapter demonstrate
positive and negative conformance; the kit runs from a documented command.

## Brownfield-first adoption

### BRN-001 — Build read-only inventory and evidence capture

Inventory repository structure, build manifests, public interfaces, tests, and
available API descriptions. Every fact includes provenance and confidence.

Acceptance: repeated scans of an unchanged fixture are byte-for-byte stable,
ignore generated/vendor files by explicit policy, and make no source edits.

### BRN-002 — Deliver a Python brownfield vertical slice

Use the adapter protocol to discover a representative legacy Python application,
propose behavior candidates, reconcile one use case, and create a baseline.

Acceptance: the legacy fixture runs before and after onboarding without source
changes; accepted, rejected, and uncertain candidates remain distinguishable.

### BRN-003 — Add baseline-and-ratchet policy

Record existing violations separately from regressions and define how "touched
behavior" is calculated without relying only on file creation.

Acceptance: an unchanged legacy violation does not block adoption, a new
violation fails, an improved baseline cannot silently regress, and weakening a
baseline produces a reviewable delta.

### BRN-004 — Add optional runtime evidence

Import OpenTelemetry or recorded contract evidence through an explicit adapter.
Address secrets, personal data, sampling, and environment identity in the
ExecPlan before implementation.

Acceptance: sanitized fixture traces enrich evidence without being promoted to
intent; runtime capture is off by default and deterministic imports are tested.

## Multiple ecosystems and platforms

### ECO-001 — TypeScript framework adapter

Implement inventory, discovery, mapping, and one executable verification path
for a mainstream TypeScript HTTP framework using the conformance kit.

Acceptance: a pre-existing TypeScript fixture completes the BRN-002 onboarding
scenario and shares the same IR fixtures as Python.

### ECO-002 — Compiled-ecosystem adapter spike and selection

Run time-boxed Java/Spring and Go spikes against the adapter protocol. Select
one using measured implementation complexity, build integration, discovery
quality, and user demand rather than ecosystem preference.

Acceptance: the ExecPlan records comparable evidence and one adapter completes
inventory, mapping, and verification on a legacy fixture.

### ECO-003 — Non-HTTP platform proof

Demonstrate CLI and asynchronous message/event behaviors without adding
transport-specific fields to the core IR.

Acceptance: the same use-case concepts drive executable checks for HTTP, CLI,
and an event fixture; platform capabilities fail explicitly when unsupported.

## Change and verification lifecycle

### CHG-001 — Add proposal, delta, tasks, and archive

Implement a minimal OpenSpec-compatible change envelope around UCF behavior
deltas. Prefer import/export over cloning an existing prose workflow.

Acceptance: a proposal modifies one use case, yields an ordered task graph,
links evidence to the delta, and archives with the final behavior snapshot.

### CHG-002 — Add impact and approval gates

Compute affected behavior and require human approval only for decision classes
defined in `AGENTS.md`.

Acceptance: backward-compatible and breaking examples produce different gates;
the reasoning and affected evidence are inspectable.

### VER-001 — Make generation deterministic and executable

Define generator input/output contracts, ownership boundaries for generated
files, and stable regeneration. Implement one end-to-end backend before adding
more templates.

Acceptance: identical input produces identical output; generated tests execute
without manual monkey-patching; user-owned implementation code is never
overwritten.

### VER-002 — Close the evidence loop

Attach exact source revision, adapter version, environment, and test result to
behavior claims; make drift compare intent, observation, and evidence.

Acceptance: a source or spec change makes prior evidence stale for the correct
behavior and a fresh verification restores it.

## Release proof

### REL-001 — End-to-end adoption benchmark

Run the complete workflow on three legacy fixtures representing the selected
ecosystems and all required platforms. Measure false candidates, review effort,
runtime, and spec overhead.

Acceptance: the target-state scenarios pass, results and limitations are
published, and no claim exceeds its evidence level.

### REL-002 — Stable release readiness

This dependency ID and title are historical. Its accepted deliverable is a
bounded `0.1.x` production preview, not a stable API; a future `1.0.0` decision
is outside this backlog.

Finalize compatibility, migrations, security, packaging, licensing, support,
and deprecation policy. Remove or explicitly defer all critical blockers.

Acceptance: release checklist and clean-install scenarios are green; public
documentation matches the capability matrix; remaining limitations have owners
and non-misleading status.
