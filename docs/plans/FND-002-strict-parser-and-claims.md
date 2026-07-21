# Make parser boundaries and public claims strict

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After this package, users receive an explicit error instead of silent
acceptance when a specification contains an unknown field, duplicate identity,
unresolved reference, or currently unsupported feature. Versioned JSON Schemas
describe the same accepted documents as the runtime parser. A public capability
matrix distinguishes implemented, experimental, and planned behavior and links
every implemented claim to a reproducible command.

This package tightens the current specification boundary; it does not introduce
the future language-neutral behavior IR or adapter protocol.

## Foundational Assumption

The root assumption is that the current Pydantic v2 specification models,
`parse_spec`, loader, registry, and validator form one usable boundary that can
be made strict without duplicating the model or invalidating repository-owned
specifications.

The cheapest falsification experiment is to:

1. submit unknown root and nested fields through `parse_spec`;
2. register the same `(kind, metadata.name)` twice;
3. validate a use case with an unresolved step and a declared feature that has
   no execution support;
4. emit JSON Schema from every current spec model and validate all repository
   YAML documents against the emitted schema.

If valid repository specs depend on ignored fields, or Pydantic's emitted
schema cannot express the runtime union and strictness consistently, update
this plan before implementation. Alternatives are a shared strict model base,
per-model strict configuration, or an explicit schema facade. Prefer the first
option that keeps one authoritative model and does not pre-empt `IR-001`.

Maintenance revalidation on 2026-07-22 challenged the narrower assumption that
Pydantic's alias-only JSON validation remains stable across the declared
`pydantic>=2.4.0` range. The cheapest useful experiment installed the same wheel
with the declared floor `2.4.0`, locked `2.12.5`, and ordinary resolver-selected
`2.13.4`, then submitted an optional Python field name. It falsified the
assumption twice: `2.13.4` silently discarded `assert_condition`, while `2.4.0`
did not support the call-time alias flags. Alternatives were to narrow the
dependency range, rely on version-specific Pydantic flags, or enforce the wire
contract after floor-compatible strict validation. The selected approach keeps
the declared range and checks the concrete validated model graph, avoiding a
version branch or a duplicate schema model.

## Progress

- [x] (2026-07-19) Revalidate the foundational assumption and retain the
  focused probe under `.artifacts/quality/fnd002-start-20260719/`. All 41
  existing boundary tests pass, but unknown root, metadata, and HTTP-binding
  fields are silently dropped; an unknown FieldDef type falls through as an
  arbitrary dictionary; duplicate registration warns and overwrites the first
  spec. All 113 repository specs still load.
- [x] (2026-07-19) Add negative fixtures for unknown root and nested fields,
  then make the Pydantic specification boundary reject them. Five RED cases
  covered root, metadata, HTTP binding, unknown FieldDef option, and unsupported
  FieldDef type. A shared strict base plus typed field, requirement, and
  invariant alternatives makes them green; 113 repository specs validate.
- [x] (2026-07-19) Add duplicate-identity RED tests and make registry/CLI
  registration fail without overwriting either source silently.
  `DuplicateSpecError` names the identity and both paths before mutation; the
  CLI reports it as a load error and exits one without a traceback.
- [x] (2026-07-19) Inventory accepted reference forms, add missing/wrong-kind
  negative tests, and reject unresolved references at the loader or
  registry-aware validator boundary. Missing identities are `BROKEN_REF`,
  resolved identities of the wrong kind are `TYPE_MISMATCH`, and both are
  errors. The default loader now discovers `.yaml` and `.yml`, rejects
  non-string references, preserves singular registry aliases, and prevents a
  canonical logical `$ref` from silently loading a document with a different
  kind or name. Focused evidence: 37 tests pass in
  `references-expanded-green.log`; all 113 repository specs have no reference
  or type errors.
- [x] (2026-07-19) Define the current unsupported-feature boundary and prove
  explicit rejection without embedding future adapter or platform semantics
  in core models. The pytest generator rejects retry declarations before any
  output, including a whole-run preflight; `ucf generate` also refuses mixed
  parse/duplicate errors and registry validation errors before writing. Other
  advanced source fields remain explicitly experimental, declaration-only
  intent unless the capability matrix names a consumer. Evidence:
  `unsupported-retry-red.log`, `unsupported-retry-green.log`,
  `generate-invalid-preflight-red.log`,
  `generate-invalid-preflight-green.log`, and
  `unsupported-generator-affected-green.log` (151 passed).
- [x] (2026-07-19) Generate deterministic versioned JSON Schemas from the
  authoritative models and validate every repository spec against them.
  Public parsing now uses strict JSON-mode types and public aliases only. The
  checked-in Draft 2020-12 schema has a six-kind discriminator, requires
  `kind`, carries runtime expression constraints not emitted automatically by
  Pydantic, validates all 113 repository documents, rejects the same eight
  structural negative fixtures, and is byte-identical across hash seeds.
  Evidence: `runtime-schema-parity-red.log`,
  `runtime-schema-parity-green.log`, `published-schema-red.log`,
  `published-schema-green.log`, and `published-schema-check.log`.
- [x] (2026-07-19) Publish `docs/CAPABILITIES.md` as the machine-checked
  capability/status matrix and correct public claims that exceed executable
  evidence. Four automation tests enforce the status vocabulary, evidence
  links, backlog ownership, and status notices on historical/proposal
  documents.
- [x] (2026-07-19) Run affected suites, the complete quality profile, diff
  review, and independent acceptance audit. The local profile under
  `.artifacts/quality/fnd002-final-20260719/` and the clean-snapshot audit under
  `.artifacts/agents/fnd002-final-audit/` both pass all six gates. The accepted
  profile has 5 automation tests, 388 Python tests at 86% coverage, 113 specs
  with zero errors and warnings, clean Ruff/build/lint results, and a clean
  `git diff --check`. The audit also proves the schema is included in the
  wheel. Baseline and state now advance to `FND-003`.
- [x] (2026-07-22) Reproduce BUG-001 with the same wheel under Pydantic 2.4.0,
  2.12.5, and 2.13.4. Retain both intended RED failures and prove the public
  parser contract on all three coordinates after the minimum correction.
- [x] (2026-07-22) Add internal-only, public/internal duplicate, public-alias,
  free-form-map, union-context, and source-provenance parser regressions for all
  current aliases. Strengthen the clean installed-wheel contract so its import
  origin, module/distribution version, inventory coordinate, and exact floor
  are bound rather than inferred from CLI startup.
- [x] (2026-07-22) Regenerate REL-001 evidence with the exact CI uv and managed
  CPython build after rejecting a structurally different local candidate. The
  only non-runtime report change is wheel identity; an independent
  three-repetition replay retains the structural digest.
- [x] (2026-07-22) Run the affected and complete eight-gate profiles and obtain
  independent parser, release-contract, and claims reviews. Technical parser
  and release findings are closed; premature final-evidence claims are removed
  and the maintenance work is recorded in this ExecPlan.

## Surprises & Discoveries

- Observation: Pydantic's default `extra="ignore"` silently accepts unknown
  fields at every modeled layer. The generated schemas omit
  `additionalProperties`, which means they describe the same permissive
  default rather than the target strict contract.
  Evidence:
  `.artifacts/quality/fnd002-start-20260719/foundational-probe.log`.
- Observation: a shared strict base is necessary but not sufficient.
  `FieldDef | dict[str, Any]` accepts invalid field types and unknown field
  options by falling through to the untyped branch. Repository inventory shows
  all 252 action input/output entries conform to `FieldDef`; thirteen component
  parameter/provide entries also have the same shape even though the current
  union selects `dict`.
  Evidence:
  `.artifacts/quality/fnd002-start-20260719/fallback-shape-inventory.log`.
- Observation: `SpecLoader` eagerly expands a dictionary containing only
  `$ref`, so the 39 use-case invariant references become inline invariant
  dictionaries before `UseCaseSpec` validation. This explains the broad
  `Ref | dict` runtime type and means strict source shape cannot be restored by
  deleting that branch without representing the resolved form explicitly.
  No repository spec uses a `.yaml` file-reference suffix.
  Evidence: the fallback inventory and repository `$ref` search recorded in
  the session.
- Observation: duplicate registration retains only the second definition and
  its path, so `SpecValidator._check_duplicates` can never observe the
  duplicate it claims to detect.
  Evidence:
  `.artifacts/quality/fnd002-start-20260719/foundational-probe.log`.
- Observation: strict parsing exposed 52 values at 50 nested object locations
  across 27 repository files that had previously been accepted and silently
  discarded. Language-neutral descriptions and written resource fields are
  now modeled. Two Python-framework flags and seven opaque HTTP
  request/response/status fragments had no executable consumer and were
  removed rather than laundering them through `dict[str, Any]`.
  Evidence:
  `.artifacts/agents/fnd002-schema-spike/strict-repository-extra-inventory.log`
  and
  `.artifacts/quality/fnd002-start-20260719/strict-model-affected-2.log`.
- Observation: once invariant references became typed instead of arbitrary
  dictionaries, the graph correctly exposed a constraint cycle between
  `invariant/spec-has-implementation` and
  `usecase/detect-spec-code-drift`. The declared acyclicity property applies
  only to `depends_on` edges, not the multi-relation graph; three checked-in
  user implementations had asserted the stronger false property.
  Evidence:
  `.artifacts/quality/fnd002-start-20260719/strict-model-broader-affected.log`
  and `typed-invariant-graph-green.log`.
- Observation: eager singleton `$ref` expansion previously discarded the
  written logical identity. A file at `components/worker.yaml` could declare
  `component/impostor`, be embedded successfully, and leave the validator no
  evidence that `components/worker` had been retargeted. The loader now checks
  canonical extensionless identities before expansion while explicit
  `.yaml`/`.yml` file includes retain file-include semantics.
  Evidence:
  `.artifacts/quality/fnd002-start-20260719/logical-ref-identity-red.log`
  and `references-expanded-green.log`.
- Observation: reference validation had inconsistent severity and kind
  semantics. Main steps and `extends` were errors, while invariant/action
  bindings and event triggers were warnings or information and several
  identity-bearing fields were unchecked. Wrong-kind identities were also
  indistinguishable from missing identities in the first implementation.
  Negative fixtures now cover requirements, invariants, emissions, both event
  trigger forms, protocol implementations, action/use-case invariant bindings,
  step kinds, and flow-local dependencies. A positive event/protocol fixture
  protects against over-restriction because the repository corpus currently
  has no event or protocol documents.
  Evidence:
  `references-validator-red.log`, `references-category-red.log`,
  `usecase-event-trigger-red.log`, and `references-semantic-green.log`.
- Observation: Pydantic's generated union schema correctly emits `oneOf` and
  a discriminator, but direct-model defaults make `kind` optional and model
  validators for nonblank/mutually-exclusive step conditions are not emitted.
  The runtime boundary also accepted internal Python field names and primitive
  coercion that JSON Schema rejects. Public parsing now validates strict JSON
  using aliases only; the schema generator applies only the runtime
  constraints Pydantic cannot emit.
  Evidence:
  `.artifacts/agents/fnd002-schema-spike/report.md`,
  `runtime-schema-parity-red.log`, and `published-schema-green.log`.
- Observation: the repository retry example is declaration evidence, not
  generator evidence. Its checked-in orchestrator invokes slug generation
  once while user-owned implementation code manually performs five attempts.
  Fresh generation now rejects `steps.generate-slug.retry` instead of
  producing a misleading ordinary flow.
  Evidence:
  `.artifacts/agents/fnd002-unsupported-audit/summary.md` and
  `unsupported-retry-green.log`.
- Observation: generator capability preflight prevents retry output, but a
  later render failure across multiple supported use cases can still leave
  partial files and cannot restore overwritten generated files. This is
  unrelated, non-blocking debt for the current FND-002 claim because
  generation is explicitly experimental; transactional rendering and
  ownership are owned by VER-001.
  Evidence:
  `.artifacts/agents/fnd002-unsupported-audit/render-time-partial-write.log`.
- Observation: current and historical documentation mixed implemented paths
  with future architecture. A single canonical matrix plus machine checks was
  sufficient to make current claims precise without turning prose into a
  second capability model.
  Evidence: `docs/CAPABILITIES.md`,
  `tests/automation/test_capability_claims.py`, and the independent claim
  review in `.artifacts/agents/fnd002-final-audit/report.md`.
- Observation: Hatch includes the checked schema data in the wheel even
  without a separate force-include rule because it is located beneath the
  packaged `src/ucf` tree. This is package-content evidence only; clean
  installation and reproducibility remain FND-003 acceptance behaviors.
  Evidence:
  `.artifacts/agents/fnd002-final-audit/wheel-schema.log`.
- Observation: Pydantic 2.13.4 accepts an optional Python field name during
  alias-only JSON validation and silently drops it, while Pydantic 2.4.0 lacks
  the newer call-time alias arguments entirely. A post-validation walk beside
  the concrete model graph is stable across the tested floor, lock, and current
  ordinary coordinates.
  Evidence: `.artifacts/quality/bug001-pydantic-range-20260722/`.
- Observation: regenerating REL-001 with local uv 0.10.10 and a different
  managed CPython build changed environment-derived structural identities.
  Exact CI uv 0.11.29 and the retained CPython executable restored every
  structural, lifecycle, and overhead identity; only the changed wheel identity
  remained outside runtime observations.
  Evidence: `rel001-report-ci-regeneration.log` and
  `rel001-report-independent-replay-green.log` in the BUG-001 artifact root.
- Observation: a list or object supplied as `kind` leaks a pre-existing raw
  `TypeError` before model validation. It is unrelated to alias acceptance and
  is recorded in `docs/automation/BASELINE.md` for a separate focused fix under
  the discovered-debt policy.

## Decision Log

- Decision: harden the existing specification boundary before defining the new
  behavior IR.
  Rationale: `FND-002` must remove silent acceptance and misleading claims, but
  designing versioned IR identities, evidence, and adapter capabilities belongs
  to dependency-ordered packages `IR-001` and later.
  Date/Author: 2026-07-19 / Codex.
- Decision: treat runtime models as the candidate single source for published
  schemas, subject to the foundational experiment.
  Rationale: hand-maintained schemas would create two acceptance contracts and
  allow runtime/schema drift. If the experiment falsifies this, record the
  smallest explicit facade and its parity test here before implementing it.
  Date/Author: 2026-07-19 / Codex.
- Decision: use one shared strict Pydantic base for modeled schema objects and
  replace catch-all schema unions with the explicit types demonstrated by
  repository evidence.
  Rationale: this keeps one runtime/schema authority. Open mappings that carry
  user data or expressions remain mappings; schema objects such as field
  definitions and requirements do not fall through to arbitrary dictionaries.
  Eagerly resolved invariant references will use an explicit typed resolved
  alternative rather than changing the documented `$ref` loading behavior in
  this package.
  Date/Author: 2026-07-19 / Codex.
- Decision: distinguish declarative syntax support from executable capability.
  Rationale: a platform declaration is intent and must not be presented as
  verified execution. Unknown or malformed schema fields fail parsing;
  operations that request an unavailable executor must fail at that consumer's
  capability boundary. Until adapters exist, the capability matrix must label
  declarations without executable evidence as experimental or planned rather
  than embedding adapter semantics in the Python model.
  Date/Author: 2026-07-19 / Codex.
- Decision: preserve only previously ignored fields that are typed,
  language-neutral parts of the current public model.
  Rationale: metadata/error descriptions and resource-write field names carry
  useful intent. Framework flags and opaque HTTP payload/status fragments were
  neither parsed into behavior nor used by generation, so removing them from
  repository fixtures is more truthful than expanding transport-specific
  Python core models or adding an unbounded schema escape hatch.
  Date/Author: 2026-07-19 / Codex.
- Decision: preserve the current dual singleton `$ref` behavior in FND-002 but
  make its identity consequences explicit and safe.
  Rationale: changing logical references into a new include syntax would
  reinterpret the published format and belongs at a public-contract decision
  boundary. Typed resolved alternatives retain compatibility; loader checks
  ensure canonical logical refs cannot silently change kind or name. Explicit
  file paths remain includes. Both singular and plural canonical prefixes are
  resolved consistently.
  Date/Author: 2026-07-19 / Codex.
- Decision: treat source declarations separately from execution capability.
  Rationale: parsing platform, event, protocol, concurrency, advanced
  invariant, or other intent must not imply an executor. The capability matrix
  labels these forms experimental and non-executable. Retry is rejected by the
  pytest generator because silently reducing it to one call changes the
  requested control flow. The optional plugin preflight extension preserves
  the existing generator plugin protocol for third-party implementations.
  Date/Author: 2026-07-19 / Codex.
- Decision: publish one generated source schema at
  `src/ucf/schemas/spec/v1/schema.json`.
  Rationale: Pydantic models remain authoritative. A small deterministic
  generator patches only runtime constraints that Pydantic does not emit:
  required discriminators, nonblank conditional expressions, and mutual
  exclusion of `when`/`skip_if`. The independent Draft 2020-12 evaluator is a
  development/test dependency, not a production parsing dependency.
  Date/Author: 2026-07-19 / Codex.
- Decision: make `docs/CAPABILITIES.md` the canonical current-claim boundary
  and validate its evidence links in automation.
  Rationale: accepting a declaration, generating a draft, and verifying
  behavior are different claims. The matrix names the exact implemented
  subset, labels incomplete paths experimental, and assigns absent behavior to
  dependency-ordered backlog owners without duplicating the future behavior
  IR.
  Date/Author: 2026-07-19 / Codex.
- Decision: resume this FND-002 strict-parser plan for BUG-001 rather than add a
  second dependency-backlog package.
  Rationale: the work crosses parser, installed-distribution evidence, and
  claims boundaries and therefore requires an ExecPlan; it is maintenance of
  the exact FND-002 public contract, while the twenty-package dependency ledger
  remains completed and machine-enforced as one canonical plan per package.
  Date/Author: 2026-07-22 / Codex.
- Decision: keep `pydantic>=2.4.0` and use one floor-compatible strict JSON
  validation followed by an explicit internal-name check over the concrete
  validated model graph.
  Rationale: narrowing the range would hide a supported-floor failure, and
  branching on Pydantic versions would leave boundary correctness dependent on
  changing library flags. The model-guided check preserves intentional
  free-form mappings and every public alias without adding a second model.
  Date/Author: 2026-07-22 / Codex.
- Decision: qualify schema generation at the locked build coordinate while
  proving the shipped schema and public runtime parser at the dependency floor.
  Rationale: Pydantic 2.4.0 emits different schema bytes, but the shipped schema
  remains valid and closed. Claiming byte-identical generation across an
  open-ended runtime range would exceed the demonstrated contract.
  Date/Author: 2026-07-22 / Codex.
- Decision: bind installed parser evidence to environment-prefix imports and
  the exact Pydantic module, distribution, inventory, and floor coordinate.
  Rationale: a clean environment or successful CLI alone does not prove the
  wheel's public parser ran against the dependency version named by evidence.
  Date/Author: 2026-07-22 / Codex.

## Outcomes & Retrospective

FND-002 is complete. Unknown modeled fields and coercions now fail, typed
repository intent is preserved, and duplicate identities fail atomically in
both registry and CLI workflows. Unresolved, retargeted, and wrong-kind
identities fail at the boundary that has enough evidence, including positive
and negative event/protocol forms absent from the repository corpus.

Unsupported retry generation and invalid generation inputs fail before
output. Runtime parsing and the published versioned schema share strict
structural negative fixtures, and fresh schema output is deterministic. The
canonical capability matrix separates implemented, experimental, and planned
claims and points each implemented row to executable evidence. Historical
documents now carry status notices instead of silently overriding that matrix.

The final local profile and an independent clean-snapshot profile pass all six
gates with 5 automation tests, 388 Python tests at 86% coverage, 113
specifications with zero errors and warnings, and green Ruff/frontend checks.
The audit also confirms the versioned schema is present in the built wheel and
found no skip/xfail weakening or current-document overclaim.

This package deliberately does not claim the future language-neutral IR,
adapter protocol, execution of advanced declarations, or transactional
generation. The multi-use-case render rollback gap is retained for VER-001;
clean installation, artifact reproducibility, local/CI manifest parity, and
the stop hook are the next package, FND-003.

The 2026-07-22 BUG-001 maintenance continuation restores the alias-only public
parser boundary at Pydantic 2.4.0, locked 2.12.5, and resolver-selected 2.13.4.
Every current wire alias has positive and negative coverage; the installed
release contract proves it imports from the clean environment and binds the
actual Pydantic coordinate. The exact-CI REL-001 refresh preserves all
deterministic structural/lifecycle/overhead semantics, and the local complete
profile passes all eight current gates. Exact commit, remote-main, clean-clone,
and hosted acceptance remain release-time properties and are not inferred from
the retained pre-commit profile.

## Context and Orientation

`src/ucf/models/` contains the Pydantic models for actions, components, events,
invariants, protocols, and use cases. Modeled source objects inherit the strict
`SpecModel` base. `src/ucf/models/spec.py::parse_spec` selects a model from the
document's `kind` and applies strict public-alias JSON validation.

For BUG-001, `_find_internal_field_name` walks normalized input beside the
concrete model returned by Pydantic. It rejects Python field names only where a
structured model exposes a different public alias, while leaving keys in true
`dict[str, Any]` payloads untouched. `tools/release_check.py` executes the same
black-box parser contract from ordinary and exact-floor wheel environments and
binds its report to each installed dependency inventory.

`src/ucf/parser/loader.py::SpecLoader` reads YAML and resolves file `$ref`
values. `src/ucf/parser/registry.py::SpecRegistry` indexes loaded specs and
resolves logical references. `src/ucf/validator/core.py::SpecValidator`
performs graph-aware checks after registration. Strictness must be placed at
the earliest boundary that has enough information: model shape in Pydantic,
file references in the loader, and cross-spec identities/references in the
registry plus validator.

Repository specifications live under `specs/`. Parser, loader, registry, and
validator tests live primarily in `tests/unit/test_parse_spec.py`,
`test_loader.py`, `test_registry.py`, and `test_validator.py`. Public prose is
spread across root Markdown documents; the evidence-linked matrix introduced
here will be the canonical status summary rather than another product model.

## Plan of Work

First run the falsification probe and focused current tests without changing
production. Inventory every Pydantic model and every accepted extension point
so strictness does not accidentally reject deliberate mapping keys such as
action inputs or platform configuration.

For each boundary, add one minimal negative test that fails for the intended
silent behavior. Make the smallest production change, run the focused test
green, and then run parser/loader/registry/validator affected suites. Do not
combine unknown fields, duplicate identities, reference failures, and
unsupported features into one catch-all error.

Once runtime acceptance is strict, add deterministic schema generation and a
parity test: checked-in schemas must equal fresh output, reject the same
negative fixtures, and validate all repository specs. Only then inventory
public claims, create the capability matrix with exact verification commands,
and revise unsupported prose claims.

Finally run the full quality profile, review generated schema diffs and the
complete package diff, obtain an independent acceptance audit, update the
baseline, complete this retrospective, and advance state.

For BUG-001, first reproduce the optional-alias acceptance at the current
resolver and the call incompatibility at the declared floor. Add one acceptance
behavior at a time, use floor-compatible validation, and then strengthen the
installed distribution contract so source/editable leakage or inventory drift
cannot create a false pass. Refresh REL-001 only through its full runner under
the exact CI toolchain, compare deterministic sections independently, then run
the affected and complete profiles and review all public claims.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream and retain the foundational probe:

    mkdir -p .artifacts/quality/fnd002-start-20260719
    uv run --extra dev --extra web pytest -q \
      tests/unit/test_parse_spec.py tests/unit/test_loader.py \
      tests/unit/test_registry.py tests/unit/test_validator.py --no-cov

Each RED/GREEN command must use `tee` or another observable retained log under
the same artifact directory. Expected focused suites are parser/model,
loader/registry/validator, schema generation/parity, and documentation claim
checks.

Before acceptance run:

    uv run --extra dev --extra web pytest -q --disable-warnings
    uv run --extra dev ruff check src tests tools
    uv run --extra web ucf validate specs
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/fnd002-final-<date>
    git diff --check

BUG-001 range and installed-distribution checks run from the repository root:

    <pydantic-2.4.0-python> -m pytest -q -o addopts='' \
      tests/unit/test_parse_spec.py --no-cov
    <pydantic-2.12.5-python> -m pytest -q -o addopts='' \
      tests/unit/test_parse_spec.py --no-cov
    <pydantic-2.13.4-python> -m pytest -q -o addopts='' \
      tests/unit/test_parse_spec.py --no-cov
    uv run --locked python tools/release_check.py --distribution-only
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/bug001-pydantic-range-20260722/all-final-staged

## Validation and Acceptance

The package is accepted only when:

1. negative fixtures prove unknown root and nested fields fail with precise
   locations;
2. duplicate identities fail before data is overwritten and identify both
   sources when paths are available;
3. every supported reference form has positive and broken-reference tests, and
   broken references cause a non-zero public validation result;
4. every currently accepted but unimplemented feature is either rejected at
   the correct boundary or explicitly represented as experimental with a
   non-executable status; no parser path silently implies support;
5. deterministic, versioned JSON Schemas validate all repository specs and
   reject the same structural negative fixtures as runtime parsing;
6. every public capability is labeled `implemented`, `experimental`, or
   `planned` and every implemented entry links to a command exercised by a
   test or gate;
7. all six repository quality gates and `git diff --check` pass with fresh
   retained evidence.

BUG-001 maintenance additionally requires the same installed wheel to reject
every current Python alias name and public/internal duplicate at Pydantic 2.4.0
and the ordinary resolver coordinate, accept every public wire alias, preserve
free-form alias-like keys, retain source provenance, and bind imports plus
version evidence to each environment. The current eight-gate complete profile,
benchmark replay, and `git diff --check` must pass without dependency narrowing,
skips, warning downgrades, or hand-edited generated evidence.

## Idempotence and Recovery

Focused tests use temporary directories and do not mutate `specs/`. Schema
generation writes deterministic content to explicit checked-in paths and must
be safe to repeat; a parity test detects partial or stale output. Never resolve
duplicates by last-write-wins, reset a baseline, or weaken a validator severity.
If strictness rejects a repository spec, retain the failing fixture, determine
whether the field is intended or stale, and record any public-contract decision
before changing either side.

The BUG-001 checks build in temporary or ignored artifact paths and are safe to
repeat. A failed REL-001 regeneration is never promoted; rerun with the exact
recorded CI toolchain and require deterministic-section equality. Release
evidence uses create-only output and must target an absent path. Do not recover
by pinning away the failing Pydantic version or by resetting the benchmark.

## Artifacts and Notes

FND-001 accepted evidence is in
`.artifacts/quality/fnd001-final2-20260719/`. FND-002 foundational and
RED/GREEN logs belong under
`.artifacts/quality/fnd002-start-20260719/`. Keep raw claim inventories concise;
the durable result belongs in the capability matrix and this plan's decisions.
Final local acceptance is under
`.artifacts/quality/fnd002-final-20260719/`; independent clean-snapshot
acceptance and the wheel-content check are summarized in
`.artifacts/agents/fnd002-final-audit/report.md`.

BUG-001 RED/GREEN, installed-wheel, benchmark, affected, and complete-profile
evidence is under
`.artifacts/quality/bug001-pydantic-range-20260722/`. Independent parser,
release-contract, benchmark, and claims reports are under
`.artifacts/agents/bug001-*/`. The local complete profile is staged-source
evidence and is not labeled an exact committed or hosted release result.

## Interfaces and Dependencies

Existing public boundaries in scope are:

- `ucf.models.spec.parse_spec` and `SpecParseError`;
- `ucf.parser.loader.SpecLoader` and `RefResolutionError`;
- `ucf.parser.registry.SpecRegistry.register` and `resolve_ref`;
- `ucf.validator.core.SpecValidator` and `ValidationIssue`;
- the `ucf validate` CLI exit contract;
- new versioned JSON Schema files and their deterministic generation command;
- the public capability/status matrix and its verification-command links.

BUG-001 changes no serialized source format or production dependency. It
clarifies that `parse_spec` accepts public wire aliases only, while direct
Python construction of Pydantic models remains a separate API. The release
checker now treats its installed parser result and Pydantic inventory/floor
binding as a closed evidence object. The runtime range remains
`pydantic>=2.4.0`; schema generation remains qualified at the locked build
coordinate.

No new production dependency, hosted service, IR representation, adapter
protocol, or framework-specific capability model is authorized by this plan.
The package must remain compatible with Python 3.12 and the dependencies
already locked in `uv.lock`.
