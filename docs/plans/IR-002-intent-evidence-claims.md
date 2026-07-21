# Separate declared intent from observed evidence

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After this package, UCF can retain declared intent, observed facts, candidate
inference, explicit mappings, conflicts, confidence, and graduated claims
without one category overwriting another. Every displayed claim traces to an
immutable source revision and producer version. An independent claim evaluator
rejects unsupported bases, so an uncertain discovered candidate cannot become
`tested` merely because it resembles a declaration.

This package defines trust semantics around the accepted behavior IR. It does
not implement repository discovery, an adapter process, runtime capture,
baseline ratcheting, formal proof, or OpenSpec change management.

## Foundational Assumption

The root assumption is that a small versioned trust/evidence overlay can
reference immutable IR-001 document/entity identities and express declarations,
observations, mappings, candidates, confidence, conflicts, and claims without
mutating the accepted behavior records or publishing IR `1.1.0` prematurely.

The cheapest useful falsification experiment is to:

1. create one language-neutral candidate overlay referencing the SHA-256 of the
   IR-001 complete fixture and stable entity IDs;
2. retain one declaration and one conflicting observation as separate records,
   map them explicitly, and canonicalize the result in Python and Node;
3. enumerate the five claim levels against the minimum required evidence and
   attempt to promote an uncertain candidate directly to `tested`;
4. verify that every candidate, mapping, and claim can identify source
   revision, producer name/version, and exact evidence records without copying
   or rewriting the underlying intent.

Compare that overlay with two alternatives: adding new entity kinds in a new
behavior-IR version, and overloading the existing `observation` record. If the
overlay cannot preserve typed traceability or creates a second mutable fact
authority, publish a properly versioned IR extension with explicit
compatibility fixtures instead. Overloading existing records is acceptable
only if it does not conflate desired and observed state.

## Progress

- [x] 2026-07-19: Revalidate the foundational assumption and retain overlay/versioning,
  conflict-survival, promotion-matrix, document-identity, and cross-runtime
  probes.
- [x] 2026-07-19: Specify immutable declaration, observed-fact, candidate, mapping,
  conflict, confidence, and claim records with closed schemas and stable IDs.
- [x] 2026-07-19: Add RED reconciliation tests proving declared and observed facts survive
  disagreement and no operation silently overwrites either record.
- [x] 2026-07-19: Add RED promotion tests for `observed`, `declared`, `mapped`, `tested`,
  and `verified`; require reproducible evidence and reject uncertain,
  failed, stale, mismatched, or circular evidence.
- [x] 2026-07-19: Publish deterministic fixtures/schema/API/CLI boundaries and document
  exact semantics without claiming adapter discovery or formal proof.
- [x] 2026-07-19: Run affected and complete gates, review the full diff, obtain independent
  adversarial and clean-snapshot acceptance, update baseline, and advance to
  `ADP-001`.

## Surprises & Discoveries

IR-001 already preserves language-neutral observations, provenance, and
verification-evidence records, but those records intentionally assign no
claim level. The new layer must reference them rather than reinterpret parser
acceptance as truth.

The representation probe showed that adding trust records to behavior IR is
not a compatible minor extension: the exact `1.0.0` reader correctly rejects
new entity kinds. Overloading `observation` either hides categories in naming
conventions or fails closed-schema validation. A separate exact-version
overlay retained every category and canonicalized to byte-identical output in
Python and Node without changing behavior IR.

A raw source-file digest is too sensitive to insignificant JSON formatting to
serve as behavior-document identity. The accepted complete fixture and a
reformatted equivalent had different raw SHA-256 values,
`2db85fe7aad3e9a04ae22001273b87eae1450b5be27e5dd386000c020c50b037`
and `8df6be112f466a64bf0f1b9dbf3606881985de821e650620f30a497955d32bba`,
but the same canonical IR digest,
`5e6063cff77f19a238418c3275ea50a73b1960e285f616c5ee995e0a05f24e9a`.
Behavior references must therefore bind to the canonical content digest;
source revision remains a separate exact artifact coordinate.

The promotion probe falsified a numeric or mutable promotion chain. The five
labels have independent evidence predicates: an observed fact does not become
declared intent, a declaration does not become a passing check, and a passing
check does not become a proof. The evaluator must return the exact supported
set or an immutable decision, never the maximum enum member.

The accepted implementation boundary follows four ordered validators: shared
strict JSON/model validation, internal global identity and typed-reference
validation, canonical Behavior IR binding, then independent claim predicates.
This separation is necessary because Behavior IR correctly retains
well-formed `failed`, `error`, stale, and mismatched evidence; only the claim
evaluator decides whether that evidence is sufficient for `tested`.

The first independent contract audit rejected an otherwise green candidate:
the public reconciliation API treated a different behavior slot as a
`conflict`, even though the semantic validator correctly rejected the returned
mapping. A retained RED mutation now proves that the API raises
`mapping_basis_mismatch` before returning. Derivation and validation share one
disposition function, so every returned mapping revalidates.

## Decision Log

- **2026-07-19, representation boundary:** publish a separate, immutable,
  exact-version `trust_ir` overlay at `1.0.0`. It references behavior IR by
  exact IR version, canonical SHA-256 digest, entity kind, and entity ID.
  Alternatives rejected: a behavior-IR extension requires a new compatibility
  contract and couples independent trust semantics; observation overloading
  either creates hidden semantics or violates the accepted closed schema.
- **2026-07-19, document identity:** use SHA-256 over canonical behavior-IR
  bytes for behavior-document identity. Preserve a source revision separately
  on provenance records and tested-claim requests. This makes semantically
  identical formatting stable without conflating IR identity with the
  checked artifact revision.
- **2026-07-19, claim semantics:** implement independent finite predicates for
  `observed`, `declared`, `mapped`, `tested`, and `verified`; do not expose
  ordinal strength or mutable promotion transitions. Candidate confidence is
  a canonical decimal string in `[0,1]`, useful only for review routing and
  never executable evidence.
- **2026-07-19, verified scope:** keep `verified` explicitly unavailable in
  IR-002. The accepted behavior IR does not yet name a checked property,
  explicit assumptions, finite bounds/proof artifact, and reproducible
  proof/exhaustive procedure. Treating an ordinary passed test as formal
  verification would exceed the evidence; `VER-002` may introduce that
  contract under its own acceptance tests.
- **2026-07-19, tested coordinates:** a `tested` basis names exact
  verification evidence, an immutable current artifact source, check
  ID/version/procedure, environment digest, and producer name/version. The
  evaluator resolves the producer through evidence provenance and compares
  every coordinate; parser acceptance alone never yields a claim.
- **2026-07-19, reconciliation consistency:** derive and validate
  `same-behavior-slot` disposition through one function. A value disagreement
  within the same target slot is `conflict`; a different subject or target is
  not a conflict mapping and fails with `mapping_basis_mismatch`.

## Outcomes & Retrospective

IR-002 is accepted after independently verified IR-001. Exact trust IR `1.0.0`
ships immutable source, declaration, observed-fact, candidate, mapping, and
claim records; strict internal/external refs; canonical behavior-document
binding; pure reconciliation; and independent claim evaluation. Candidate
confidence is bounded canonical metadata only. `tested` requires the exact
passed/current subject, revision, check, environment, and producer
coordinates; `verified` is explicitly unavailable.

Strict RED/GREEN evidence is retained under
`.artifacts/quality/ir002-red-20260719/`. The first contract audit found a
reconciliation API inconsistency; the retained negative test and shared
derivation fixed it, and re-audit accepted 47 focused trust tests and all 121
IR tests. The final local profile at
`.artifacts/quality/ir002-final-20260719/` passes all seven gates with 27
automation tests, 537 Python tests at 88% coverage, 113 specs with zero errors
or warnings, Ruff, frontend build/lint, and a byte-reproducible clean-installed
wheel SHA-256
`684c37b54b62b00b85356c52da3c3d686ef87da9de3f8f76d32736d9fca04c50`.

Independent contract, distribution, and post-fix clean-snapshot audits all
accepted. The clean snapshot reproduced all seven gates, the same counts and
wheel hash, schema freshness, and the complete 12-record trust CLI pair.
IR-002 adds no production dependency and makes no adapter, discovery,
authenticity, runtime-capture, baseline, or formal-verification claim. The
known frontend advisory inventory remains release work for `REL-002`.

## Context and Orientation

The accepted wire model is under `src/ucf/ir/`; its checked schema is
`src/ucf/schemas/ir/v1/schema.json`. `Observation`, `Provenance`, and
`VerificationEvidence` are retained facts/evidence, not promotion rules.
Golden behavior fixtures live under `tests/fixtures/ir/v1/`.

IR-002 implementation should remain in a focused package beneath
`src/ucf/ir/` unless the experiment proves a separately named public package
is clearer. Trust fixtures belong under `tests/fixtures/ir/` and focused tests
under `tests/ir/`. Do not put discovery, language parsing, framework knowledge,
or process transport into this layer.

## Plan of Work

First retain the three competing shapes and a promotion truth table. Use one
conflicting pair and one uncertain candidate, not a broad synthetic domain.
Record whether stable external refs plus document digests make the overlay
self-contained and whether the same bytes canonicalize across runtimes. This
experiment is complete: the overlay shape was retained, raw-file identity was
replaced by canonical-content identity, and numeric promotion was rejected.

Then work one acceptance behavior at a time. Define immutable fact categories
and provenance first; add explicit mappings and conflict status next; only then
implement claim evaluation. Promotion must be a pure decision over named
records. It may derive a result but must never edit a declaration,
observation, mapping, evidence record, or prior decision. This sequence is
complete.

Represent confidence without binary floating-point ambiguity. Keep candidate
confidence distinct from claim level: confidence may influence review routing
but never substitutes for a named executable check. A `tested` result requires
passed verification evidence for the exact subject and artifact revision. A
`verified` result must remain unavailable unless the checked property,
assumptions, and reproducible proof/exhaustive procedure are explicitly
represented.

Publish deterministic schema and canonical fixtures only after runtime
semantics are green. Add the smallest CLI inspection/validation boundary and
update CAP-202 with precisely the accepted scope.

## Concrete Steps

Run from `/home/deliner/projects/ucf` and retain live output under
`.artifacts/quality/ir002-start-20260719/`:

    uv run --locked --extra dev pytest -q tests/ir --no-cov
    uv run --locked --extra dev ruff check src/ucf/ir tests/ir tools

Before acceptance:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/ir002-final-20260719
    git diff --check

## Validation and Acceptance

IR-002 is accepted only when:

1. conflicting declared and observed facts remain separately addressable after
   reconciliation and canonical round-trip;
2. mappings record relationship and conflict disposition without modifying
   either side;
3. candidates retain confidence, source revision, and producer identity and
   cannot be displayed as higher claim levels;
4. each level has explicit minimum evidence, invalid transitions have stable
   errors, and uncertain/failed/stale/mismatched/circular evidence cannot yield
   `tested`;
5. `verified` is either reproducibly scoped with assumptions/procedure or
   explicitly unavailable;
6. every derived claim traces to immutable source and tool versions;
7. fixtures/schema remain language-neutral and deterministic, all seven gates
   pass locally and in an independent clean snapshot, and public claims do not
   exceed the tests.

## Idempotence and Recovery

Reconciliation and claim evaluation are pure over immutable input records.
Canonical generation may safely replace only its explicit output path.
Interrupted schema generation is detected by byte-freshness tests. Never
repair a conflict by deleting or rewriting one side; add a new mapping or
review decision with provenance.

## Artifacts and Notes

IR-001 accepted evidence is in
`.artifacts/quality/ir001-final2-20260719/`,
`.artifacts/agents/ir001-contract-reaudit/`, and
`.artifacts/agents/ir001-final-clean-audit/`. IR-002 probe and RED/GREEN
evidence belongs under `.artifacts/quality/ir002-start-20260719/`. Independent
shape and promotion reports are retained at
`.artifacts/agents/ir002-shape-probe/report.md` and
`.artifacts/agents/ir002-promotion-probe/report.md`. Final evidence is under
`.artifacts/quality/ir002-final-20260719/`,
`.artifacts/agents/ir002-contract-audit/`,
`.artifacts/agents/ir002-distribution-audit/`, and
`.artifacts/agents/ir002-clean-snapshot/`.

## Interfaces and Dependencies

Accepted contracts are:

- immutable typed records for declaration, observed fact, candidate, mapping,
  conflict/review disposition, and claim;
- a finite claim-level enum and pure reconciliation/evaluation API;
- exact external references bound to IR document digest and entity identity;
- canonical confidence representation without raw floats;
- deterministic JSON/schema/CLI validation and inspection boundaries.

No adapter subprocess, source scanner, runtime collector, baseline policy,
formal prover, hosted service, or production dependency is authorized by this
package.
