# OpenSpec-Compatible Change Lifecycle

The canonical capability status and evidence boundary is
`docs/CAPABILITIES.md`, row CAP-210. The current lifecycle is experimental,
not a stable change-management or release claim.

UCF lifecycle profile `1.0.0` provides this immutable sequence:

`proposal → delta → tasks → implementation → verification → archive`

Each lifecycle stage writes a new canonical JSON resource and retains exact
content-derived references to the required prior stage or stages. Task
completion returns a new canonical `TaskGraph`; task status is declared current
workflow state, not authenticated command history, and v1 does not represent
successive task graphs as a revision chain. No transition modifies predecessor
documents or turns proposal prose into executable behavior.

## Interoperability boundary

The supported import profile is
`fission-ai.openspec/spec-driven@1`, tested against OpenSpec 1.6.0. Import
accepts one direct `<root>/changes/<change-id>` directory plus an exact base
Behavior IR. It reads the OpenSpec workspace without changing it and preserves
supported project config, base specs, proposal, design, tasks, delta specs,
change metadata, and other regular bounded files as byte/digest-addressed
artifacts.

The selected change metadata (preferred) or project config must declare
`schema: spec-driven` with unique YAML keys. Delta specs use exactly
`changes/<change-id>/specs/<capability>/spec.md`; a preserved base spec is
accepted only when the same capability has a delta spec. When change metadata
is present, an overridden project config is preserved byte-for-byte but is not
interpreted as the selected profile declaration.

This is compatibility with that exact artifact shape, not general OpenSpec
runtime compatibility. A custom selected schema, duplicate keys in the
selected declaration, unsafe paths, filesystem aliases and hard links that are
present when inspected, non-regular files, invalid UTF-8 in text artifacts,
identity changes detected during guarded reads, and oversized artifacts fail
explicitly.

Export publishes only to an absent directory. An existing byte-identical tree
is an identity no-op; any extra, missing, or changed entry returns a conflict.
UCF never merges into or deletes a populated user workspace. Publication uses
a complete private sibling stage and rename. Neither import nor export is
sandbox isolation against a hostile same-UID process replacing filesystem
entries between checks.

## Resources

| Resource | Meaning |
| --- | --- |
| `ChangeProposal` | Stable change ID, exact base Behavior IR reference, and preserved OpenSpec artifacts |
| `BehaviorDelta` | Exhaustive canonical added, modified, and removed entity/root changes |
| `TaskGraph` | Explicit numbered tasks, source coordinates, subjects, order, dependencies, and status |
| `ImplementationRecord` | Exact supported delta-subject bindings to context-validated imported evidence |
| `VerificationRecord` | Accepted state only after all tasks complete and every supported result passes |
| `ArchiveRecord` | Exact predecessor references plus the accepted final Behavior IR snapshot |

All six resources reject unknown fields, duplicate JSON members, unsupported
versions/schema URIs, non-canonical structures, and malformed references.
Contextual validators additionally reject stale predecessor digests, incomplete
delta/task/evidence coverage, cycles, wrong transition order, non-passing
evidence, and semantically invalid Behavior IR.

## Impact and decision overlay

The separate change-governance profile `1.0.0` consumes an exact proposal,
exhaustive delta, base Behavior IR, and final Behavior IR. It does not change
the six lifecycle resources or interpret OpenSpec prose. Its four closed
resources are:

| Resource | Schema URI | Meaning |
| --- | --- | --- |
| `ImpactReport` | `urn:ucf:change-governance:impact-report:1.0.0` | Recomputed structural changes, language-neutral graph edges and bounded witnesses, compatibility basis, and unresolved meaning |
| `DecisionAssessment` | `urn:ucf:change-governance:decision-assessment:1.0.0` | Exactly one derived or declared disposition for every fixed decision class |
| `DecisionDeclaration` | `urn:ucf:change-governance:decision-declaration:1.0.0` | Human-authored outcomes for exactly the applicable class set |
| `GateEvaluation` | `urn:ucf:change-governance:gate-evaluation:1.0.0` | Pure recomputation of the pass or block result from the complete predecessor chain |

The structural compatibility procedure is intentionally narrow:

- `backward_compatible_graph_extension` requires every base entity to remain
  byte-exact, every base root to remain a root, and no new document-level
  required capability;
- `breaking_base_root_contract` reports loss of an accepted base root;
- `breaking_required_capability` reports a stricter document-level capability
  requirement;
- `compatibility_unresolved` covers every other modification or removal
  instead of guessing producer/consumer variance, source-language meaning, or
  opaque rule semantics.

Direct delta subjects are definite structural facts. Reverse paths use only
canonical Behavior IR roots, entity references, exact port selections, step
port definitions, and required-capability edges. Each edge records the base or
final graph side, source, target, field location, and reason. Whole-entity and
opaque semantic relations remain `may_affect` or unresolved; they are not
reported as verified semantic impact.

The assessment taxonomy is closed to the six human decision classes from
`AGENTS.md`:

1. `public_contract_or_serialized_boundary`
2. `production_dependency_license_or_hosted_service`
3. `destructive_or_irreversible_migration`
4. `security_privacy_correctness_or_gate_weakening`
5. `material_product_semantics`
6. `scope_expansion_for_preexisting_failure`

A structurally breaking result derives the first class and callers cannot
downgrade it. The other five classes are not derivable from Behavior IR bytes:
the caller must provide an inspectable `applies`, `does_not_apply`, or
`unresolved` declaration for each one. Any unresolved class blocks. A decision
must cover exactly the applicable classes in taxonomy order and must reference
the exact proposal, delta, behaviors, impact, assessment, policy, and
procedure. Extra, partial, stale, irrelevant, or cross-change decisions fail.

Gate statuses are exact:

- `pass_no_decision` for a completely classified compatible change with no
  applicable decision class;
- `pass_approved` when every exact applicable decision is approved;
- `block_unresolved`, `block_decision_required`, or `block_rejected` for valid
  inputs that cannot advance.

Canonical digests bind content identity only. A declaration is not evidence of
an authenticated person, authorization, a signature, non-repudiation, or
one-time use. Impact, assessment, decision, and gate resources do not create or
strengthen `observed`, `declared`, `mapped`, `tested`, or `verified` Trust
claims.

## Installed workflow

The wheel exposes the eight lifecycle commands under `ucf change`:

1. `import-openspec`
2. `export-openspec`
3. `derive-delta`
4. `derive-tasks`
5. `complete-task`
6. `record-implementation`
7. `verify`
8. `archive`

The governance overlay adds four commands:

9. `ucf change impact`
10. `ucf change assess`
11. `ucf change decide`
12. `ucf change gate`

`derive-tasks` requires explicit `TASK=OPERATION:KIND:ID` subject assignments
and explicit dependencies. Markdown task text is never interpreted as behavior
semantics. `derive-tasks`, `complete-task`, `record-implementation`, `verify`,
and `archive` also require the exact `--base-behavior` and `--final-behavior`
documents. Each downstream transition re-derives the exhaustive delta from
that pair before accepting its predecessors, so a canonical but fabricated
delta or task subject fails closed. Every file-producing command validates all
inputs again immediately before publication and preserves an existing output
on failure.

`exit 0` means the transition completed or an exact destination was already
present. `exit 1` means a valid lifecycle transition is currently blocked,
such as out-of-order task completion, incomplete tasks, or non-passing
evidence. `exit 3` means malformed, stale, unsupported, unsafe, or conflicting
input.

For the governance commands, exit `0` publishes a passing, canonical result.
An exit `1` reports a valid blocked gate and preserves any existing output. An
exit `3` rejects malformed, stale, unsupported, aliased, or conflicting input
without publication. Repeated exact inputs are idempotent, and installed
package acceptance compares the full workflow under two Python hash seeds.

## Evidence assurance

`ImplementationRecord` embeds each exact execution result and a deterministic
`context_validated_import` receipt. The receipt binds:

- result and mapping-result canonical digests;
- onboarding-bundle and current-inventory canonical digests;
- mapping and verification producer identities;
- negotiated capability names and versions;
- `urn:ucf:change-lifecycle:evidence-context-validation:1.0.0`.

UCF recomputes the full mapping/onboarding/inventory/result relationship before
implementation, verification, and archive. This proves reproducible contextual
validation of imported evidence. It is not authenticated proof that an adapter
process ran, and lifecycle transitions create no `observed`, `mapped`,
`tested`, or `verified` Trust claim. VER-002 owns the live
session/operation receipt, revision-bound claim, and precise staleness loop.

A removed delta subject cannot use a passing check against its old base
subject: that would prove the old behavior ran, not that final source lacks it.
The current implementation therefore returns
`unsupported_evidence_profile` before recording removal implementation
evidence. A future final-state absence/tombstone profile must bind final
inventory/source revision, a named absence check, producer, procedure, and
environment.

## Current limits and owners

- Impact classification and human approval gates are the separate CHG-002
  overlay described above; they are not CHG-001 lifecycle resources.
- OpenSpec prose remains declared/opaque input and is never executable truth.
- Digests provide exact content identity and traceability, not signing,
  provenance authenticity, or protection from a caller deliberately forging
  all mutually consistent evidence inputs.
- The current wheel proof covers deterministic local filesystem operation and
  clean installation on the tested environment. It is not a hosted service,
  multi-user transaction coordinator, or stable-support commitment.

Run the focused contract with:

```bash
uv run --locked --extra dev pytest -q \
  tests/change_lifecycle tests/change_governance \
  tests/cli/test_change_lifecycle.py \
  tests/cli/test_change_governance.py --no-cov
uv run --locked python tools/package_contract.py
```
