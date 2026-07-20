# CHG-002 Impact and Approval Gates

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect the current
truth.

## Purpose / Big Picture

After this package, a team can inspect exactly which accepted behaviors a
proposed change affects and why, distinguish a backward-compatible example
from a breaking example, and require an explicit human decision only when the
change reaches one of the decision classes defined in `AGENTS.md`. The
observable proof is two changes over the same accepted Behavior IR: the
compatible change advances without a fabricated approval, while the breaking
change cannot advance until a human-authored decision bound to its exact
proposal, delta, impact, and context is supplied.

Impact is evidence, not inferred product intent. UCF will expose the changed
subjects, dependency paths, classification basis, and any unresolved
coordinates. It will not infer licenses, migrations, security consequences,
or product semantics from prose or language-specific source, and it will not
turn an OpenSpec checkbox into approval.

## Foundational Assumption

The root assumption is that exact Behavior IR plus the exhaustive CHG-001
BehaviorDelta already contains enough language-neutral structure to compute a
deterministic changed-subject and behavior-dependency impact closure. The core
should not need language, framework, build-tool, or transport semantics.
Information that is not present in those documents—such as selecting a new
dependency/license, authorizing a destructive migration, weakening security,
or choosing between materially different product meanings—must remain an
explicit human-authored decision classification rather than an inferred core
claim.

The cheapest useful falsification experiment makes no production edit:

1. construct one canonical base Behavior IR and two reviewed finals: a
   backward-compatible additive example and a breaking removal or contract
   tightening example;
2. derive the current exhaustive deltas and use only existing neutral
   references to calculate direct subjects plus reverse dependency paths;
3. map every `AGENTS.md` decision class to facts present or absent in the
   serialized inputs, and try to distinguish the two examples without prose,
   file names, Python types, or adapter knowledge;
4. compare four alternatives: separate immutable impact and approval
   resources, extending BehaviorDelta, reusing TaskGraph/OpenSpec task state,
   or delegating impact classification to adapters.

The probe passes only if structural impact is exact and reproducible, every
reason is inspectable, compatible input needs no approval, decision-class
input cannot advance without an exact decision, and absent semantic
information remains explicitly unresolved or declared rather than guessed.
If compatibility semantics require reinterpreting accepted Behavior IR or
CHG-001 wire values, or if the package must choose materially different public
semantics not fixed by `TARGET_STATE.md`, record the alternatives and stop at
the corresponding human decision gate before implementation.

The experiment partially falsified the broad assumption. Exact documents are
sufficient for deterministic structural facts, field differences, graph
edges, and the deliberately narrow compatibility profile selected below; they
are insufficient for exact semantic impact or five decision classes. The
architecture therefore separates derived evidence from caller declarations
and represents unsupported meaning as unresolved. This result does not require
a human decision because it preserves every accepted contract and refuses the
broader interpretations.

## Progress

- [x] 2026-07-20: Accept CHG-001 with independent, all-profile, diff, and
  physical clean-source evidence; create this self-contained plan and set
  CHG-002 active.
- [x] 2026-07-20: Inspect the exact existing Behavior IR, lifecycle,
  dependency, and claim boundaries; run root plus three independent
  no-production-edit compatibility/impact counter-probes under multiple hash
  seeds; compare alternatives and select a separate four-resource governance
  profile with conservative structural compatibility and explicit unresolved
  semantics.
- [x] 2026-07-20: Freeze 29 positive, negative, compatibility, and
  stale-context fixtures; retain focused RED/GREEN/REFACTOR evidence for
  direct impact, graph edges, unresolved meaning, codecs, assessment, gate,
  schemas, fixtures, determinism, and CLI publication.
- [x] 2026-07-20: Implement deterministic inspectable impact over the complete
  supported Behavior IR graph, with exact port facets, canonical shortest
  witnesses, side-specific edges, conservative precision, and no
  language/platform semantic rule.
- [x] 2026-07-20: Implement the exact six-class assessment, immutable
  content-bound decisions, and pure gate recomputation without prose/task
  inference, authentication claims, or Trust promotion.
- [x] 2026-07-20: Close bypass, stale-reference, ambiguity, non-promotion,
  determinism, installed-package, and documentation boundaries. Independent
  audits found and root-reproduced negative witness-index, concurrent
  publication-alias, and extra-fixture freshness gaps; each received a
  retained focused RED, minimum correction, GREEN, and affected-suite replay.
- [x] 2026-07-20: Run affected suites, all seven canonical gates, scope/diff
  review, and a physical source-only clean replay; accept CHG-002 and advance
  to VER-001.

## Surprises & Discoveries

CHG-001 deliberately leaves impact and approval outside its six-resource
lifecycle. The foundation probes confirmed that its exhaustive delta contains
exact changed entity coordinates but only `definition` and `root_membership`
aspects. Opposite optional/required port examples have the same projected
delta shape; classification requires exact base/final fields and a named
procedure.

A naïve reverse-reference closure is deterministic but not exact semantic
impact. Changing only one use-case output requiredness reaches an unrelated
binding that selects an unchanged input port, then its step. An invariant
reference reaches an opaque `DeclaredRule` whose strength the core is
deliberately unable to interpret. Whole-entity closure must therefore be
reported as conservative `may_affect` or unresolved evidence, never as
definite semantic impact.

The existing `src/ucf/graph/dependency.py` is a legacy YAML/spec graph with
NetworkX, hand-coded legacy kinds, silent missing-target success, no canonical
paths, and no Behavior IR bindings/effects/evidence/capabilities. Ratchet touch
projection measures reviewed onboarding semantic/observed fingerprints, not
change dependency. Their small algorithmic patterns are useful, but neither
contract is reusable for CHG-002.

Five of the six `AGENTS.md` decision classes are indistinguishable from
Behavior IR and delta bytes. The exact same serialized change may use only an
already accepted implementation or select a new production dependency and
license. Capability names, effect tokens, invariant prose, task text/status,
file names, and adapter output cannot close that information gap. Missing
classification must block as unresolved; it cannot default to
`does_not_apply`.

Independent adversarial review found that witness validation accepted negative
Python indexes, although the wire contract defines non-negative edge
coordinates. The focused RED is
`.artifacts/quality/chg002-start-20260720/governance-negative-witness-red.log`;
validation now rejects every negative or out-of-range witness with a typed
contract error.

The first publication helper could accept an exact-content destination that
appeared as a symlink or hard link to an input after the initial snapshot
check. The deterministic race RED is
`.artifacts/quality/chg002-start-20260720/governance-publication-alias-race-red.log`.
All four commands now share stable existing-output inspection, reject
non-regular and multiply-linked destinations, and verify identity and metadata
stability across the read.

Fixture freshness originally compared only expected paths and therefore did
not reject an extra checked-in fixture. The retained RED is
`.artifacts/quality/chg002-start-20260720/governance-fixture-extras-red.log`;
`--check` now compares the complete actual fixture tree, including symlinks,
to the exact generated set.

## Decision Log

- **2026-07-20 — challenge impact sufficiency before selecting a wire
  resource.** Author: root agent. No impact model, approval receipt, schema, or
  CLI will be selected until the smallest compatible/breaking counterexample
  proves which facts are derivable and which require explicit human input.
- **2026-07-20 — preserve CHG-001 and add a separate change-governance
  profile.** Author: root agent. `BehaviorDelta 1.0.0` remains the exhaustive
  factual entity difference and `TaskGraph` remains declared implementation
  order. CHG-002 will add four immutable, closed, versioned resources:
  `ImpactReport`, `DecisionAssessment`, `DecisionDeclaration`, and
  `GateEvaluation`. This separates derived structural evidence, caller
  assessment, human-authored decision, and recomputed gate outcome while
  binding each step to exact proposal/delta/base/final bytes. Extending delta
  would mix policy with fact and churn accepted references; task status is not
  approval; adapter-authoritative classification would leak ecosystem
  semantics into the core.
- **2026-07-20 — select a deliberately narrow structural compatibility
  procedure.** Author: root agent. A change is a
  `backward_compatible_graph_extension` only when every base entity remains
  byte-exact, every base root remains a root, and no new required capability
  raises document execution requirements. Loss of a base root or a stricter
  document-level required capability is structurally breaking and derives the
  first decision class. Every other modified/removal/port/rule/provenance or
  graph case is `compatibility_unresolved`; CHG-002 will not select general
  producer/consumer variance or interpret opaque rules.
- **2026-07-20 — report structural evidence without semantic overclaim.**
  Author: root agent. Direct delta subjects are definite structural changes.
  Reverse edges are derived from base for removals, final for additions, and
  both for modifications; exact `PortRef` selectors may exclude unrelated
  facets, while whole-entity and opaque-rule relations remain `may_affect` or
  unresolved. The report retains exact graph side, source/target, field
  location, reason, and a deterministic bounded edge graph rather than
  pretending every reachable node is affected.
- **2026-07-20 — approvals are content-bound declarations, not authenticated
  people or single-use tokens.** Author: root agent. The assessment contains
  exactly the six fixed classes with `applies`, `does_not_apply`, or
  `unresolved` and derived/declared basis. Unresolved blocks. Applicable
  classes require an exact matching decision; extra, partial, stale, or
  cross-change decisions fail. Digests prove bytes only. Exact-byte retries
  remain idempotent, and CHG-002 will make no identity, signature,
  authorization, non-repudiation, or one-time-use claim.

## Outcomes & Retrospective

CHG-002 foundation is accepted without a human decision gate or production
edit. The root baseline passes 466 IR/lifecycle/ratchet/CLI tests and Ruff
under `.artifacts/quality/chg002-start-20260720/`. Root and independent probes
prove deterministic structural change/edge derivation, falsify exact semantic
reverse closure and coarse-delta compatibility, and map all six decision
classes. Evidence is under `.artifacts/agents/chg002-architecture-map/`,
`.artifacts/agents/chg002-decision-threat-model/`, and
`.artifacts/agents/chg002-foundation-probe/`.

The selected boundary is a separate four-resource change-governance `1.0.0`
profile with a narrow graph-extension/root-contract/required-capability
procedure and explicit unresolved semantics. It does not change CHG-001,
interpret prose, authenticate a reviewer, or claim general API compatibility.
The accepted CHG-001 baseline remains 65 automation tests, 1,555 Python tests
at 90% coverage, all seven gates green, wheel SHA-256
`a831ad5e5dc7023fef9691a28d8f6005d62df18c1a6b4dee6104ebc20eb70b1d`,
and an 830-file clean-source manifest SHA-256
`466939848e4f8ca81e495203e26c20446d77776cebb941684e799c850cceeaf7`.

CHG-002 is accepted. The final implementation provides four generated closed
schemas, strict codecs and contextual replay, exact structural impact and
decision resources, four installed commands, 29 generated fixtures, and
CAP-216 as the bounded public claim. Post-audit affected integration passes
384 tests under
`.artifacts/quality/chg002-start-20260720/governance-post-audit-affected-green.log`.
Independent contract/correctness and final integrated audits report ACCEPT
under `.artifacts/agents/chg002-contract-correctness-recheck/` and
`.artifacts/agents/chg002-final-integrated-recheck/`; the distribution/claim
audit is under `.artifacts/agents/chg002-distribution-claims-audit/`.

The final local all-profile run under
`.artifacts/quality/chg002-final-20260720/` passes 68 automation tests, 1,611
Python tests at 89% coverage, Ruff, 113 specifications with zero errors and
warnings, installed packaging, frontend build, and frontend lint. The clean
package contains exactly 34 schemas and produces two byte-identical wheels at
SHA-256
`9a664d50e6eabf85292175acf302977744457d61e89915fbe7caed5155b5d997`.
Its external workflow produces identical compatible/breaking results under
hash seeds 1 and 777, preserves a blocked-output sentinel, and revalidates the
accepted chain in isolated Python.

Physical clean-source acceptance is
`.artifacts/agents/chg002-clean-source-snapshot/20260720T104843Z-chg002/`.
Fresh locked Python and frontend installs repeat all seven gates from 886
regular source files. The source manifest is byte-identical before and after
at SHA-256
`d8d9035c52dffdd7bac99782cd5018e911b1d1dd5368057d26d42d5aba7e816e`;
a checksum dry-run confirms the checkout and snapshot files are identical.
Only directory modification times changed during test execution and are
correctly excluded from content parity. `git diff --check`, the complete
CHG-002 scope review, neutrality scan, and skip/xfail/suppression scan are
clean. No human decision gate was reached.

## Context and Orientation

Canonical language-neutral behavior entities, references, ports, bindings,
effects, invariants, observations, and capability requirements live in
`src/ucf/ir/`. CHG-001 lifecycle resources, exhaustive delta derivation,
ordered tasks, evidence, verification, archive, and the pinned OpenSpec
boundary live in `src/ucf/change_lifecycle/`.

The older `src/ucf/graph/dependency.py` and `src/ucf/completeness/` operate on
loaded YAML specification models. They may provide algorithmic evidence, but
they are not automatically the canonical Behavior IR impact contract.
Brownfield touch projection in `src/ucf/ratchet/` answers whether evidence
changed for baseline enforcement; it must not silently become change approval
semantics.

Installed commands are assembled in `src/ucf/cli.py`. Generated schemas live
under `src/ucf/schemas/`, package inventory is enforced by
`tools/package_contract.py`, public truth is `docs/CAPABILITIES.md`, and the
current lifecycle limitations are in `docs/CHANGE_LIFECYCLE.md`.

## Plan of Work

First, run the foundation probe over canonical documents and record a
field-by-field derivability matrix for impact and every human decision class.
Measure existing dependency algorithms against the same examples. Reject any
path that depends on Python source semantics, OpenSpec prose, task completion,
or hidden heuristics.

Second, freeze the selected four-resource wire fixtures before production
edits. `ImpactReport` is derived structural evidence; `DecisionAssessment`
exhaustively classifies the six fixed classes and cannot downgrade derived
requirements; `DecisionDeclaration` exists only for the exact applicable class
set; `GateEvaluation` is the pure recomputed pass/block result. Unknown fields,
duplicate JSON members, incompatible versions, broken or wrong-kind
references, stale proposal/delta/behavior/procedure/policy context, ambiguous
classification, approval reuse, and decision bypass must fail before
implementation.

Third, implement one acceptance behavior at a time. Begin with exact direct
impact, then deterministic reverse dependency paths and compatibility basis,
then unresolved/declared decision classes, then the approval transition. Each
slice starts with a focused failure for the intended missing behavior, receives
the minimum production change, returns green, and is refactored only while the
affected suite remains green.

Fourth, integrate installed commands and packaging, publish the exact
capability boundary, and prove that no impact result or approval raises a Trust
claim. Run independent contract/architecture and bypass/security audits before
full gates.

Finally, run all seven canonical gates, inspect the complete admitted diff,
verify generated fixtures/schemas are fresh, and repeat the source-only clean
snapshot protocol used by CHG-001.

## Concrete Steps

Work from `/home/deliner/projects/ucf`. Retain observable output under
`.artifacts/quality/chg002-start-20260720/`:

    git status --short
    uv run --locked --extra dev pytest -q \
      tests/change_lifecycle tests/ir tests/ratchet \
      tests/cli/test_change_lifecycle.py --no-cov
    uv run --locked --extra dev ruff check src tests tools

The foundation evidence must include canonical base/final/delta digests,
direct and transitive impact coordinates, compatible/breaking outcomes, the
decision-class derivability matrix, counterexamples, alternative comparison,
and the selected boundary. Run the first production RED only after that result
is recorded.

Before package acceptance run:

    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/chg002-final-20260720
    git diff --check

## Validation and Acceptance

CHG-002 is accepted only when fresh executable evidence proves:

1. direct and transitively affected behavior subjects are deterministic,
   complete for the supported graph, and accompanied by inspectable paths and
   reasons;
2. backward-compatible and breaking examples produce different exact gate
   outcomes from the same versioned procedure;
3. only decision classes defined in `AGENTS.md` can require human approval,
   and unrepresented semantic facts are never guessed from prose or source;
4. a required decision cannot be bypassed, fabricated by task status, reused
   for different bytes, or accepted against stale proposal, delta, impact,
   behavior, policy, or decision-class context;
5. a compatible change advances without a meaningless approval artifact, and
   supplying an approval where none is required cannot strengthen a Trust
   claim;
6. unknown fields, duplicate members, broken refs, incompatible versions,
   ambiguous classification, unsupported capabilities, and non-canonical
   ordering fail explicitly;
7. repeated input and at least two hash seeds produce byte-identical impact,
   gate, and installed-command output;
8. the Python core imports no adapter implementation and contains no language,
   framework, build-tool, runtime, or transport-specific impact rule;
9. documentation and capability claims match the proven boundary, affected
   and full gates pass, independent audits accept, and a physical clean-source
   replay is green.

No acceptance may use skip, xfail, warning-only enforcement, path exclusions,
baseline reset, hand-edited generated output, broad exception swallowing,
prose inference, or an approval default that weakens a required decision.

## Idempotence and Recovery

Foundation probes are read-only and write only retained evidence under
`.artifacts/`. Impact and gate computation must be pure and canonical.
Installed commands write one completed output by same-directory atomic
replacement only after full validation. A failed or rejected decision leaves
all accepted lifecycle inputs and existing outputs untouched and can be
retried from the same immutable bytes.

If the foundation reaches a public-contract break, new production dependency,
destructive migration, security/correctness weakening, or materially different
product semantics, record options, evidence, consequences, and a
recommendation here and set `docs/automation/STATE.md` to
`blocked_on_decision`.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/chg002-start-20260720/`;
- `.artifacts/agents/chg002-architecture-map/`;
- `.artifacts/agents/chg002-decision-threat-model/`;
- `.artifacts/agents/chg002-foundation-probe/`;
- `.artifacts/agents/chg002-clean-source-snapshot/`.

Do not retain credentials, private approval text, raw sensitive evidence,
dependency caches, unbounded command output, or temporary workspaces.

## Interfaces and Dependencies

Accepted upstream contracts are exact `1.0.0` Behavior IR, Trust IR,
CHG-001 lifecycle, adapter protocol, onboarding, implementation evidence,
runtime evidence, and ratchet resources. CHG-002 may reference them but must
not reinterpret their accepted semantics.

The selected `change_governance` profile has its own exact `1.0.0` version,
schema URIs, procedure URI, and six-class policy/taxonomy URI. Its four
resources are language-neutral, closed, canonical, schema-backed, and
content-bound to exact predecessors. It may import CHG-001 and Behavior IR
types, but CHG-001 must not import governance or change its accepted
resources/functions.

Human decisions name only the six classes defined by `AGENTS.md` and must not
be presented as authenticated identity without a separately selected
authentication mechanism. Selecting a production dependency, hosted approval
service, signing scheme, general language/API compatibility policy, or
materially different approval semantics is outside the selected boundary and
reaches the applicable decision policy.
