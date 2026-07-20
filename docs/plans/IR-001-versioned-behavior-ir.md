# Define the minimum versioned behavior IR

This ExecPlan is a living document and must be maintained according to
`PLANS.md`. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must always reflect the current truth.

## Purpose / Big Picture

After this package, UCF can exchange a strict, deterministic JSON document that
describes behavior without naming a programming language, framework, build
tool, transport, or runtime implementation. The document contains stable
identities, use cases, actions, bindings, effects, observations, invariants,
provenance, verification evidence, and capability requirements. Golden
fixtures round-trip byte-deterministically, broken identities and incompatible
versions fail clearly, and the published JSON Schema is shipped in the wheel.

This is the serialized center that later out-of-process adapters will exchange.
It does not implement discovery reconciliation, claim-level promotion, adapter
transport, or a second prose change-management system.

## Foundational Assumption

The root assumption is that one strict JSON envelope with explicitly tagged,
small entity records can represent the minimum shared behavior graph without
copying the current YAML source model or embedding Python execution semantics.
The Python package may provide the reference parser, but the wire contract must
remain usable by ordinary JSON tooling in other runtimes.

The cheapest falsification experiment is to:

1. write one candidate JSON object containing every required entity and edge;
2. parse and re-emit it with Python's standard JSON library and Node.js,
   compare canonical content, and scan every key/value for Python module,
   class, decorator, AST, import, pytest, or framework concepts;
3. prototype strict Pydantic schema emission for the tagged records and check
   whether unknown fields, non-finite numbers, duplicates, broken/wrong-kind
   references, and unsupported versions can all fail at an explicit boundary;
4. mutate only major, minor, and patch version components to determine the
   smallest honest compatibility rule before publishing v1.

If a single envelope forces transport-specific fields or ambiguous open
dictionaries, prefer a graph of explicit entity records and typed references.
If Pydantic cannot produce a truthful language-neutral schema, keep it as the
runtime implementation and publish a small deterministic schema facade with
parity tests. Do not extend the existing source YAML schema and call it the IR.

## Progress

- [x] (2026-07-19) Revalidate the foundational assumption and retain
  candidate-envelope, cross-runtime, terminology, number, strictness, duplicate
  member, and version probes under
  `.artifacts/quality/ir001-start-20260719/` and
  `.artifacts/agents/ir001-*-probe/`. Separate closed tagged graphs containing
  all ten required entity kinds canonicalize identically in Python and Node
  for the restricted value profile and contain no prohibited structural
  terminology. Direct source-model serialization, generic JSON values,
  untyped refs, raw floats, and default JSON decoders are falsified.
- [x] (2026-07-19) Specify v1 identities, exact compatibility rules, canonical JSON
  serialization, and strict envelope/entity boundaries with golden positive
  and negative fixtures. The retained raw-boundary, model, canonicalization,
  and fixture evidence is under
  `.artifacts/quality/ir001-start-20260719/`.
- [x] (2026-07-19) Add RED tests for actions, use cases, ordered steps, value bindings,
  language-neutral effects, invariants, observations, provenance, evidence,
  and capability requirements; implement the minimum typed records. The RED
  import failure and 14-test initial GREEN are in `models-codec-red.log` and
  `models-codec-green.log`; the affected IR suite now covers recursive values,
  semantic collection ordering, qualified capabilities, and a Node JSON
  round-trip.
- [x] (2026-07-19) Add RED semantic tests for duplicate identities, broken references,
  wrong-kind targets, unsupported versions, unknown fields, invalid numbers,
  and non-deterministic serialization; make every failure explicit.
  `semantic-red.log` retains the missing-boundary RED and
  `semantic-green.log` retains the 11-test semantic GREEN.
- [x] (2026-07-19) Generate and check a deterministic Draft 2020-12 IR v1 JSON Schema,
  package it, and validate golden fixtures with an independent evaluator. The
  checked schema hash is retained in `schema-sha256.log`; schema parity,
  hash-seed, structural-negative, runtime-only semantic, wheel-asset, and
  installed parser/CLI assertions are executable.
- [x] (2026-07-19) Expose the smallest public parse/validate/serialize boundary and update
  the capability matrix and documentation without claiming IR-002 promotion
  semantics or adapter execution. CAP-108 is implemented and automation
  checks that CAP-202 remains planned under IR-002.
- [x] (2026-07-19) Run affected suites and the complete profile, review the entire diff,
  obtain independent clean-snapshot acceptance, update baseline, and advance
  state to `IR-002`. The accepted local profile is
  `.artifacts/quality/ir001-final2-20260719/`; independent contract, package,
  re-audit, and clean-snapshot evidence is under
  `.artifacts/agents/ir001-{contract-audit,package-audit,contract-reaudit,final-clean-audit}/`.

## Surprises & Discoveries

- Observation: the current source models are not a viable IR authority. They
  contain transport records, open `Any`/mapping values, floating numbers,
  string-only and implicitly rewritten references, and unlabelled expression
  syntax. These are valid source-intent inputs but would leak implementation
  and platform assumptions into a universal wire contract.
  Evidence:
  `.artifacts/agents/ir001-shape-probe/report.md` and
  `.artifacts/agents/ir001-neutrality-probe/source-model-leakage.log`.
- Observation: separate candidate graphs cover all ten required entity kinds
  with globally unique IDs and typed refs. Python and Node produced identical
  canonical candidate bytes with zero prohibited structural terms; the root
  candidate hash is
  `0341ce8990c25b5daa7cef926e1fc7dddc29c558454664051e4a4caba17eca24`.
  Two independent alternatives report the same viability with different
  candidate layouts.
  Evidence: `cross-runtime-hashes.log`,
  `.artifacts/agents/ir001-shape-probe/report.md`, and
  `.artifacts/agents/ir001-neutrality-probe/REPORT.md`.
- Observation: unrestricted JSON numbers are not a cross-runtime canonical
  value model. Python and Node differ for `1.0`, negative zero, exponent
  formatting, and integers outside the exact IEEE-754 range. V1 must use safe
  JSON integers plus canonical decimal strings and reject raw fractions,
  non-finite constants, and unsafe integers.
  Evidence:
  `.artifacts/agents/ir001-neutrality-probe/number-cross-runtime.log`.
- Observation: default Python, Node, and Pydantic JSON decoding silently keeps
  the last duplicate object member. Pydantic's built-in `JsonValue` also
  accepts raw `NaN` despite `allow_inf_nan=False` and may serialize it as
  `null`. Duplicate-member and non-standard-number checks therefore belong
  before schema/model validation, and wire values require a closed recursive
  tagged union.
  Evidence: `pydantic-boundary-probe.log`,
  `.artifacts/agents/ir001-schema-probe/REPORT.md`, and
  `.artifacts/agents/ir001-neutrality-probe/json-duplicate-member.log`.
- Observation: Pydantic can still be the authoritative structural model. It
  emits closed Draft 2020-12 records, exact const versions, and discriminated
  unions deterministically across hash seeds. Duplicate identities and
  cross-record reference semantics remain runtime-only checks.
  Evidence:
  `.artifacts/agents/ir001-schema-probe/probe.log` and `hash-seed.log`.
- Observation: the generated Draft 2020-12 schema truthfully covers every
  closed record and exact version but cannot express global uniqueness,
  reference resolution, or port compatibility. Publishing those checks as
  schema annotations while always running them in `parse_ir_json` avoids a
  false schema-only validation claim.
  Evidence: `schema-red.log`, `schema-green.log`,
  `tests/ir/test_schema.py`, and
  `src/ucf/schemas/ir/v1/schema.json`.
- Observation: actual canonical golden output survives a Node parse and
  recursively key-sorted re-emit byte-for-byte. Capability and producer names
  require lowercase qualified namespaces, while effects remain opaque
  semantic operations whose executability is controlled by explicit
  capability requirements.
  Evidence: `portability-green.log` and
  `tests/ir/test_models_and_codec.py`.
- Observation: the first independent contract audit rejected the otherwise
  green snapshot because adversarial integers and nesting escaped the public
  error boundary, early common-era timestamps depended on platform
  `strftime`, and semantic-set/capability duplicates plus unguarded opaque
  rules remained accepted. Dedicated RED tests reproduced every issue. The
  corrected snapshot maps hostile size/depth inputs to stable codes, validates
  calendar dates without formatting round trips, rejects semantic duplicates,
  requires namespaced capabilities for opaque effects/rules, and produces
  identical Unicode/emoji canonical bytes in Python and Node.
  Evidence: `.artifacts/agents/ir001-contract-audit/report.md`,
  `adversarial-boundary-red.log`, `adversarial-boundary-green.log`,
  `semantic-duplicates-red.log`, `semantic-duplicates-green.log`,
  `audit-fixes-green.log`, and
  `.artifacts/agents/ir001-contract-reaudit/report.md`.

## Decision Log

- Decision: create a separate `ucf.ir` boundary rather than rename or
  serialize the current source models.
  Rationale: source declarations include historical platform and
  generator-facing shapes. The target requires declared intent, observed facts,
  mappings, and evidence to remain separable and requires external ecosystems
  to exchange a contract that does not inherit Python-source assumptions.
  Date/Author: 2026-07-19 / Codex.
- Decision: keep IR-001 structural evidence records neutral and defer claim
  levels, reconciliation, and promotion rules to IR-002.
  Rationale: IR-001 must carry observations, provenance, and verification
  evidence, but deciding when those facts justify `mapped`, `tested`, or
  `verified` is the next acceptance package and must not be implied by parsing.
  Date/Author: 2026-07-19 / Codex.
- Decision: use one envelope containing a globally identified, top-level tagged
  entity set and ordered typed-reference edges.
  Rationale: global IDs make duplicate, missing, and wrong-kind diagnostics
  unambiguous. Top-level action, use-case, step, binding, effect, invariant,
  observation, provenance, verification-evidence, and
  capability-requirement entities form a neutral graph. A use case's step-ref
  array retains behavioral order; set-like entity/ref arrays use explicit
  stable ordering.
  Date/Author: 2026-07-19 / Codex.
- Decision: initially support exactly IR `1.0.0`.
  Rationale: strict unknown-field rejection means a `1.0.0` reader cannot
  honestly promise forward-minor or patch acceptance without an explicit
  retained schema and compatibility suite. The supported-version set is
  finite and checked before structural validation. Future versions require
  fixtures, compatibility rules, and migration evidence rather than a relaxed
  regex.
  Date/Author: 2026-07-19 / Codex.
- Decision: define a repository-owned canonical JSON profile instead of
  adding an RFC 8785 production dependency.
  Rationale: the required v1 value space can avoid the demonstrated
  cross-runtime number ambiguities. Canonical output is compact UTF-8 JSON
  without BOM, ASCII-escaped strings, lexicographically sorted structural
  object keys, field-aware sorting for semantically unordered collections,
  preserved ordering for steps/value lists/path segments, and exactly one
  trailing newline. Values are a closed tagged union; raw fractions,
  non-finite constants, and unsafe integers are invalid.
  Date/Author: 2026-07-19 / Codex.
- Decision: preserve unavoidable declared rules as opaque text with an exact
  dialect identifier and required capability reference.
  Rationale: inventing an expression evaluator would be speculative and could
  embed one language's semantics. The core can preserve exact intent and
  validate its declared capability without parsing or executing it.
  Date/Author: 2026-07-19 / Codex.
- Decision: distinguish structural JSON Schema acceptance from runtime graph
  semantics in the published contract.
  Rationale: Draft 2020-12 can close and type every local record but cannot
  resolve globally identified entities or step-derived ports. The schema
  names those runtime checks explicitly, the CLI always runs them, and tests
  prove a broken-reference fixture is structurally valid yet rejected by the
  runtime.
  Date/Author: 2026-07-19 / Codex.
- Decision: require producer and capability names to be lowercase qualified
  namespaces.
  Rationale: adapter-owned semantics need collision-resistant stable names
  without importing an implementation registry into the core. Qualified
  opaque names plus minimum versions provide that boundary while leaving
  execution to later adapters.
  Date/Author: 2026-07-19 / Codex.
- Decision: set the IR v1 maximum decoded JSON nesting depth to 128 and reject
  larger documents as `invalid_structure`.
  Rationale: recursive host limits vary and leaked `RecursionError` from a
  public trust boundary. An explicit generous bound is reproducible across
  runtimes, prevents interpreter-specific failure, and is published as a
  runtime semantic check rather than falsely encoded in recursive JSON
  Schema.
  Date/Author: 2026-07-19 / Codex.
- Decision: treat repeated references as invalid in semantic sets and allow
  repeats only in the explicitly ordered `use_case.steps` sequence.
  Rationale: sorting a set without enforcing uniqueness leaves ambiguous
  duplicate requirements and subjects. Ordered step repetition can carry
  behavioral meaning and must not be collapsed or rejected without a separate
  execution/topology contract.
  Date/Author: 2026-07-19 / Codex.

## Outcomes & Retrospective

IR-001 is accepted. The production boundary is a separate exact-version tagged
entity graph with a strict raw decoder, closed values, typed references, a
semantic index, explicit capability checking, deterministic canonical JSON, a
packaged schema, and an installed CLI validator. The final local and
independent clean-snapshot profiles passed all seven gates with 486 Python
tests at 87% coverage, 113 specs with zero errors/warnings, byte-identical
wheels at SHA-256
`a592ddb54d158ed76139d5ea96e19d6f4f89a502d2268cae807268b57620c3a3`,
and an unchanged `uv.lock`.

The most valuable retrospective result was the initial independent REJECT:
green happy-path gates had missed host-limit and semantic-duplicate failures.
Adversarial reproductions became permanent tests and the re-audit then
accepted every corrected boundary. CAP-108 deliberately claims only
structural/semantic IR validation. Claim promotion, reconciliation,
cross-use-case execution topology, circular-evidence promotion rules,
adapters, and behavior execution remain owned by later packages.

## Context and Orientation

Current source-document models are under `src/ucf/models/`; their public parser
is `src/ucf/models/spec.py::parse_spec`. Loading, source reference expansion,
and registry validation live under `src/ucf/parser/` and
`src/ucf/validator/`. These remain source-intent boundaries.

IR implementation belongs in a new `src/ucf/ir/` package. Checked schemas
belong under `src/ucf/schemas/ir/v1/`; deterministic generation tools belong
under `tools/`; golden fixtures and tests belong under `tests/fixtures/ir/v1/`
and `tests/ir/`. The package contract already includes data beneath
`src/ucf`, but IR-001 must add an explicit installed-schema assertion.

An identity is a stable opaque record ID plus a declared entity kind. A
reference carries both expected kind and ID so wrong-kind and missing targets
are distinguishable. Provenance says where a record came from and which tool
produced it; it does not make the record true. Verification evidence names the
check and outcome; it does not itself assign a claim level in this package.

## Plan of Work

First retain a handwritten candidate envelope and exercise it with Python and
Node without importing UCF. Record which shapes survive canonical JSON and
which terms or open mappings violate the target. Decide and document exact v1
compatibility before production models exist.

Add golden fixtures and one failing behavior at a time. Start with envelope
version and identity records, then actions/use cases/steps, bindings/effects,
invariants, observations/provenance/evidence, and capability requirements.
Use explicit tagged unions and strict finite JSON-compatible primitives. Keep
ordered step arrays ordered; canonicalize object keys and any semantically
unordered collections at serialization.

Add semantic indexing only after structural parsing is green. Reject duplicate
IDs before building an index, then distinguish missing from wrong-kind
references for every typed edge. Publish stable error codes suitable for a
future adapter protocol without designing that protocol now.

Generate the JSON Schema from the authoritative runtime types where truthful,
patching only constraints the generator cannot express. Validate the golden
positive fixtures and shared structural negatives with `jsonschema`, check
byte freshness and hash-seed determinism, and confirm the wheel contains the
schema.

Finally expose a small public API and CLI validation command, update
`docs/CAPABILITIES.md` with the exact structural scope, run focused/affected
tests and all gates, inspect source/schema/fixture diffs for Python-specific
leakage, and obtain an independent clean-copy audit.

## Concrete Steps

Run from `/home/deliner/projects/ucf`. Stream and retain the foundational
evidence:

    mkdir -p .artifacts/quality/ir001-start-20260719
    python3 <candidate-probe> | \
      tee .artifacts/quality/ir001-start-20260719/candidate-envelope.log
    node <cross-runtime-probe> | \
      tee .artifacts/quality/ir001-start-20260719/node-roundtrip.log

Every RED/GREEN command must retain live output under the same artifact
directory. Expected focused suites are:

    uv run --locked --extra dev pytest -q tests/ir --no-cov
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py

Before acceptance run:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/ir001-final-<date>
    git diff --check

## Validation and Acceptance

The package is accepted only when:

1. positive golden JSON fixtures include every required IR concept and
   round-trip byte-deterministically;
2. the v1 compatibility rule is documented and unsupported/incompatible
   versions produce a stable explicit error;
3. unknown fields, non-finite numbers, duplicate identities, missing
   references, and wrong-kind targets all fail through negative fixtures;
4. no serialized fixture or schema field contains a Python module, class,
   decorator, AST, import, pytest, framework, build-tool, or transport-specific
   concept;
5. the deterministic published schema validates positive fixtures, rejects
   shared structural negatives, and is present in an installed wheel;
6. public documentation distinguishes structural IR acceptance from observed,
   tested, verified, adapter, or runtime execution claims;
7. all seven repository gates, `git diff --check`, and an independent
   clean-snapshot audit pass with fresh retained evidence.

## Idempotence and Recovery

Parsing and validation are read-only. Canonical serialization and schema
generation write only explicit output paths and must be safe to repeat;
freshness tests detect partial or stale artifacts. Golden fixtures are copied
or read, never mutated by tests. Duplicate IDs and broken references fail
before a caller receives a partial graph.

If a schema generation attempt is interrupted, rerun it into the same checked
path and use the byte-freshness test to establish completion. Do not accept a
new IR version by relaxing the parser; update compatibility rules, fixtures,
schema ID, migration evidence, and this plan together.

## Artifacts and Notes

FND-003 accepted evidence is in
`.artifacts/quality/fnd003-final2-20260719/` and
`.artifacts/agents/fnd003-final-audit-locked/`. IR-001 foundational and
RED/GREEN evidence belongs under
`.artifacts/quality/ir001-start-20260719/`; final acceptance belongs in a
separate `ir001-final-*` directory.

## Interfaces and Dependencies

Expected public contracts are:

- an exact current IR version constant and compatibility checker;
- strict parse/validate and canonical serialize functions over a versioned
  document;
- stable entity kinds, typed references, and error codes;
- explicit action, use-case, step, binding, effect, invariant, observation,
  provenance, evidence, and capability-requirement records;
- a deterministic checked JSON Schema and generation/check command;
- a minimal `ucf ir validate <file>` command or an equivalently explicit
  installed public validation boundary.

The Python reference implementation may use existing Pydantic and `jsonschema`
development dependencies. No new production dependency, adapter transport,
language parser, framework field, hosted service, claim-promotion rule, or
OpenSpec lifecycle is authorized by this package.
