# VER-001 Deterministic Executable Generation

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect the current
truth.

## Purpose / Big Picture

After this package, a user can give UCF one exact accepted behavior plus
explicit generation inputs, invoke one supported backend through the
out-of-process adapter boundary, and receive a deterministic, inspectable
generated file set whose tests execute without editing generator-owned output.
Repeating the same request produces byte-identical artifacts. Regeneration
updates only files explicitly owned by that generator and never overwrites
user-owned implementation code.

The observable proof uses one end-to-end Python backend because Python is
already a verified ecosystem and the repository has executable pytest
generation evidence. The contract itself remains language-neutral: ownership,
paths, content digests, backend identity, source behavior, and generation
procedure cross the stable adapter protocol as serialized data. Python
templates and pytest semantics remain outside the core.

## Foundational Assumption

The root assumption was that the accepted `ucf.generate` adapter operation plus
`AdapterPayload` can carry a separate exact, versioned generation
request/result profile without changing protocol `1.0.0` or Behavior IR
`1.0.0`. The current Python generator and FND-001 executable fixture may be
reused as implementation evidence only if they can be moved or wrapped behind
an external adapter while keeping user-owned files outside generator writes.

The cheapest useful falsification experiment makes no production edit:

1. run the current real generator twice from the same immutable input under two
   hash seeds and compare complete regular-file manifests;
2. insert an unmistakable user-owned implementation sentinel, regenerate, and
   prove whether it is preserved, rejected, or overwritten;
3. install only the declared dependencies in a temporary source copy and run
   the generated tests without editing generated output or monkey-patching
   imports at runtime;
4. frame the minimum request and result as existing `AdapterPayload` values and
   send a control payload through the accepted protocol/sample adapter to
   determine whether protocol evolution is actually required;
5. inspect whether current output paths, ownership, input values, templates,
   diagnostics, and atomic publication are explicit enough to validate before
   writes.

Compare four alternatives: an additive language-neutral generation profile
executed by an external Python adapter; extending Behavior IR with generation
semantics; hardening the in-process Python generator as the public boundary;
or treating checked-in generated tests as the contract. Select the first only
if the probe shows that protocol and IR remain sufficient and the existing
backend can be isolated. Extending Behavior IR is acceptable only if a
language-neutral fact required by all backends is genuinely absent.
In-process Python generation cannot satisfy the architecture guardrail, and
checked-in artifacts alone cannot prove regeneration safety.

If the experiment requires reinterpreting an accepted wire value, selecting a
new production dependency, weakening ownership protection, or choosing between
materially different public generation semantics not fixed by
`TARGET_STATE.md`, record a human decision gate before implementation.

The experiment accepted the protocol/IR half of the assumption and falsified
reuse of the current writer. A real external stdio process negotiated both
generic and Python-profile capabilities and returned byte-identical
content-bearing results under hash seeds 1 and 777 without a protocol or
Behavior IR change. The existing in-process writer is deterministic on the
minimal fixture and preserves an ordinary `impl.py`, but root and independent
counter-probes prove directory-symlink and hard-link writes outside the
declared tree, deletion of a pre-existing interface on late failure, partial
publication, and normalized-name collision. The selected architecture is
therefore an additive exact language-neutral profile, one external
Python/pytest pure renderer, and a separate manifest-validated generated-only
publication transaction. No existing wire value is reinterpreted and no human
decision gate is reached.

## Progress

- [x] 2026-07-20: Accept CHG-002 with independent, all-profile, diff, and
  physical clean-source evidence; create this self-contained plan and set
  VER-001 active.
- [x] 2026-07-20: Revalidate the generation foundation with root and three
  independent read-only probes; record deterministic manifests, execution
  behavior, ownership counterexamples, alternatives, and select an additive
  generation profile plus external Python/pytest renderer and a new
  generated-only publication boundary.
- [x] 2026-07-20: Freeze exact positive and negative
  request/result/manifest fixtures,
  including stale context, unknown fields, duplicates, unsafe paths,
  ownership collisions, unsupported capabilities, incompatible versions, and
  noncanonical ordering.
- [x] 2026-07-20: Implement one external Python generation backend and the
  smallest
  language-neutral core orchestration one acceptance behavior at a time under
  retained Red-Green-Refactor evidence.
- [x] 2026-07-20: Prove safe deterministic publication, executable generated
  tests,
  regeneration preservation, failure atomicity, no Trust promotion, and
  installed-package behavior.
- [x] 2026-07-20: Run the post-hardening all-profile acceptance snapshot: 71
  automation tests, 1,713 Python tests at 89% coverage, every other gate, and
  reproducible wheel SHA-256
  `d98f3fcfd6b8ce7493e98b10a2dcd85a35d4a98dbc74da5014e027538cb9b91a`
  pass under `.artifacts/quality/ver001-final3-20260720/`.
- [x] 2026-07-20: Publish the bounded capability/documentation claim, run independent
  contract/security/distribution audits, all seven gates, scope/diff review,
  and a physical clean-source replay before advancing to VER-002.

## Surprises & Discoveries

The accepted wire needs no version change. A real `AdapterProcess` control run
carried a complete illustrative profile through `ucf.generate`, selected
`org.ucf.adapter.generation@1.0.0` and
`org.ucf.adapter.generation.python-pytest@1.0.0`, and returned identical
SHA-256
`74e9f92fd8280fbc70dfd7d31630626f578a55da6393460bc1fa10ff92088bf4`
under hash seeds 1 and 777. Request/result frames were 9,027/12,748 bytes, so
the accepted 1 MiB bounded frame is sufficient for this slice but does not
prove large or binary generation. Root replay is
`.artifacts/quality/ver001-start-20260720/root-framed-probe.log`.

The current generator is deterministic only as a renderer, not safe as a
publisher. Its two complete minimal output manifests are byte-identical at
SHA-256
`2c6042701caa3732bbb865eb29e9678366591b7a72a300987caa8d64bee162f0`.
Raw output collects but fails honestly because concrete inputs and
implementation are user-owned; after supplying those two user artifacts, the
generated test passes 1/1 without editing generated output or runtime
monkey-patching, and regeneration changes no user byte. Evidence is
`.artifacts/agents/ver001-generator-contract/` and root replay
`.artifacts/quality/ver001-start-20260720/root-generator-probe.log`.

The legacy `GeneratorEngine` resolves a generated path and then writes
directly, while rollback unlinks every path it wrote even when that path
existed before the run. Root reproduced four true counterexamples:
directory-symlink outside write, hard-link outside overwrite, deletion of a
prior interface after a later error, and a leftover partial `__init__.py`.
Independent analysis also reproduced a post-resolution alias and
`same-flow`/`same_flow` collision. Evidence is
`.artifacts/quality/ver001-start-20260720/root-ownership-counterprobe.log` and
`.artifacts/agents/ver001-ownership-behavior/report.md`.

The Python `AdapterDispatcher` currently normalizes a backend profile
validation exception to `adapter_failure/operation_failed`. This is a local
typed-error API gap, not a wire gap. Freeze its negative behavior before
deciding whether the bounded backend needs a safe typed invalid-parameter
signal; do not allow arbitrary adapter-selected protocol errors.

The first independent contract audit found four acceptance blockers after the
initial green slice: noncanonical embedded Behavior IR could acquire a
different request identity, semantically valid results could exceed the
protocol frame, Windows trailing-period aliases were accepted, and outbound
encoders trusted structurally invalid `model_copy` values. Retained REDs now
reject them as `non_canonical_order`, `frame_budget_exceeded`,
`invalid_structure`, and exact outbound type/structure failures. The negative
wire matrix now contains 21 parse-invalid resources plus two contextual stale
resources and two positives.

The first publication/security audit falsified the broad claim that every
reported failure can preserve the prior tree. Parent and staging names can be
substituted by a callback unless inode identities are rechecked, and after a
successful directory exchange it is unsafe to roll a partially cleaned prior
tree back over the complete new tree. Publication now identity-binds the real
parent and stage, revalidates source on exact no-op, never deletes an
unverified replacement, and distinguishes pre-commit rejection from
`committed_cleanup_failed` and `committed_durability_unknown`. The latter two
are explicit complete-visible post-commit outcomes, not atomic rollback
claims.

The final publication consistency review found one additional exact-tree gap:
the scanner compared manifested files but omitted empty directories, so an
unmanifested directory-only hierarchy could be accepted and removed by an
update. Four retained REDs cover unchanged and updated publication with flat
and nested empty directories. The scanner now records directory entries and
the expected set derives only the required ancestors of manifested files.
Focused re-audit accepts 25 tests and scoped Ruff with no remaining finding;
evidence is under
`.artifacts/agents/ver001-publication-consistency/recheck/`.

A later dynamic publication re-audit found that stable root identity alone did
not bind staged descendants: the callback could edit a generated file, add an
entry, or replace all descendants under the same stage inode. The first two
could commit bytes contradicted by the receipt; abort cleanup could delete
moved-in unrecognized content. It also found that update cleanup began before
the exchange was flushed. Seven retained REDs now require complete staged-tree
revalidation before rename and before recursive abort cleanup, preserve any
unrecognized stage for inspection, flush the committed exchange before
touching the prior tree, and distinguish complete, possibly partial, and absent
residues. The independent bounded probes and 31 focused tests now ACCEPT under
`.artifacts/agents/ver001-publication-correctness/recheck/`.

## Decision Log

- **2026-07-20 — challenge the existing generator boundary before selecting a
  profile or backend layout.** Author: root agent. Existing Python templates
  and green generated tests are evidence, not permission to put Python
  semantics into the core. No wire resource, output ownership rule, external
  adapter layout, or CLI change is selected until the cheapest experiment
  proves which accepted contracts are sufficient.
- **2026-07-20 — preserve protocol and Behavior IR; add an independently
  versioned generation profile.** Author: root agent. Exact request/result
  resources cross existing `AdapterPayload` through `ucf.generate`, bind both
  generic and backend-profile capability selections, and carry complete
  content. Protocol and Behavior IR already contain every neutral coordinate;
  putting paths/templates into Behavior IR or bumping the protocol would add
  migration without closing a demonstrated gap.
- **2026-07-20 — use the legacy renderer only as parity evidence, not as the
  publisher or final adapter import.** Author: root agent. Python naming,
  templating, pytest imports, and callable mapping move to a separately
  distributed adapter. The Python core may validate the neutral profile and
  publish its complete manifest, but it will not import the adapter or retain
  Python/Jinja/pytest semantics in the new profile boundary.
- **2026-07-20 — isolate all generated-owned output in one replaceable tree.**
  Author: root agent. The bounded backend produces only generator-owned test
  artifacts. User implementation and concrete runtime inputs remain outside
  that destination. First publication requires an absent destination;
  regeneration requires an exact prior UCF receipt and unchanged complete
  tree, making unmanifested or edited files collisions rather than silently
  adopted content. This gives a recoverable staged directory transaction
  without seed-once ownership ambiguity.
- **2026-07-20 — specify pre-commit preservation and post-commit uncertainty
  separately.** Author: root agent. Before `renameat2`, every rejection keeps
  an accepted prior destination unchanged. Once a new tree is atomically
  visible, UCF never rolls a partially cleaned exchanged tree back over it.
  Cleanup failure and final directory-flush failure return the exact
  `committed_cleanup_failed` and `committed_durability_unknown` codes while
  preserving the complete visible new destination. This is the smallest safe
  Linux/POSIX contract and avoids falsely claiming rollback after commit.
- **2026-07-20 — bind cleanup authority to exact staged content, not only its
  root inode.** Author: root agent. A stable directory identity does not prove
  that its current descendants are still generator-owned. UCF re-reads the
  complete receipt, file set, directory set, link/type constraints, and bytes
  after the callback and immediately before update rename. Abort cleanup is
  refused if that exact result no longer matches. Updates flush the atomic
  exchange before destructive prior-tree cleanup, so cleanup failure no longer
  also skips the first namespace-durability boundary.

## Outcomes & Retrospective

VER-001 is verified. Its accepted dependency baseline is CHG-002: all seven gates
pass with 68 automation tests, 1,611 Python tests at 89% coverage, and wheel
SHA-256
`9a664d50e6eabf85292175acf302977744457d61e89915fbe7caed5155b5d997`.
Physical clean-source evidence is
`.artifacts/agents/chg002-clean-source-snapshot/20260720T104843Z-chg002/`,
covering 886 regular source files at manifest SHA-256
`d8d9035c52dffdd7bac99782cd5018e911b1d1dd5368057d26d42d5aba7e816e`.
The foundation is accepted with no decision gate. The exact profile, external
Python/pytest adapter, CLI, deterministic receipt-backed publication, schemas,
25 wire resources, documentation, and installed-package scenario are
implemented. The current generation/CLI slice passes 99 tests and scoped Ruff;
publication/CLI consistency coverage passes 31 tests. Focused evidence is under
`.artifacts/quality/ver001-start-20260720/`. Foundation reports are
`.artifacts/agents/ver001-protocol-architecture/report.md`,
`.artifacts/agents/ver001-generator-contract/report.md`, and
`.artifacts/agents/ver001-ownership-behavior/report.md`. The selected boundary
is a new exact generation profile over the accepted protocol, one external
Python/pytest renderer, and a generated-only receipt-backed transaction.
Independent final contract and both publication re-audits now ACCEPT under
`.artifacts/agents/ver001-contract-reaudit/` and
`.artifacts/agents/ver001-publication-consistency/recheck/` plus
`.artifacts/agents/ver001-publication-correctness/recheck/`. The
post-hardening all-profile snapshot under
`.artifacts/quality/ver001-final3-20260720/` passes all seven gates with 71
automation tests, 1,713 Python tests at 89% coverage, and reproducible wheel
SHA-256
`d98f3fcfd6b8ce7493e98b10a2dcd85a35d4a98dbc74da5014e027538cb9b91a`.
The `ver001-final2` snapshot is retained only as historical evidence because
it predates the final staged-content authority fix. Main-agent scope review
found no Python, pytest, template, or adapter implementation dependency in
`src/ucf/generation/`, and `git diff --check` is clean. A fresh physical
source-only snapshot then installed from both lockfiles and repeated all seven
gates from 937 regular files without changing any source byte. Its manifest
SHA-256 is
`52013a5c0957410a1c8819a14c9314415015a55d19150d54aedac98f0a552712`,
and its two wheels match the local wheel at
`d98f3fcfd6b8ce7493e98b10a2dcd85a35d4a98dbc74da5014e027538cb9b91a`.
Evidence is
`.artifacts/agents/ver001-clean-source-snapshot/20260720T132838Z-ver001/`.
The delivered claim remains experimental and deliberately limited to the
documented Linux/POSIX publication boundary and one direct Python/pytest
backend; generation creates no Trust claim. No decision gate or deferred
VER-001 acceptance item remains.

## Context and Orientation

The accepted language-neutral Behavior IR is under `src/ucf/ir/`. The stable
out-of-process protocol, `ucf.generate` request/response frames, process
client, and capability negotiation are under `src/ucf/adapter_protocol/`;
adapter conformance assets are under `src/ucf/adapter_conformance/`.
Implementations in `adapters/` are external assets and must remain outside the
Python wheel and outside core imports.

The legacy in-process Python generator is under `src/ucf/generator/`.
`src/ucf/generator/pytest_plugin.py` and
`src/ucf/generator/templates/` currently render Python interfaces,
implementation stubs, and pytest orchestration from repository YAML models.
`tests/unit/test_generator.py`, `tests/generator/`, and `tests/generated/`
contain FND-001 determinism, collection, contract, and executable-fixture
evidence. These paths predate the accepted adapter architecture and are not
automatically the VER-001 public contract.

Installed commands are assembled in `src/ucf/cli.py`. Exact schema assets live
under `src/ucf/schemas/`, schema generators under `tools/`, installed-package
acceptance in `tools/package_contract.py`, gate routing in
`tools/quality_gates.py`, and public claims in `docs/CAPABILITIES.md`.

## Plan of Work

First, retain a no-production-edit foundation probe. Inventory every current
generator input, output, side effect, ownership rule, nondeterministic source,
and executable dependency. Run the real generator twice, exercise
regeneration over a user sentinel, execute a fresh output in a temporary
environment, and send the smallest generation control payload through the
accepted adapter protocol. Record a field-by-field sufficiency matrix and
compare alternatives.

Second, freeze the selected serialized generation profile before production
implementation. At minimum, the request must bind exact Behavior IR,
generation procedure and version, backend capability/version, target identity,
explicit concrete test inputs, and declared ownership policy. The result must
bind the exact request and producer and list a canonical complete output
manifest with safe relative paths, ownership class, media type, content
digest, and executable verification instructions or evidence. The profile
must reject ambiguity before filesystem mutation.

Third, implement only the selected Python vertical slice. Begin with strict
decode/context validation, then an external adapter result over an isolated
temporary destination, then collision-safe publication, regeneration, and
executable proof. Each behavior starts with a focused test that fails for the
intended reason, receives the minimum production change, returns green, and
is refactored only while the affected suite remains green.

Fourth, integrate the installed CLI/package boundary and document only the
verified backend and limitations. Prove that output cannot escape its root,
symlink/hard-link/race aliases cannot overwrite input or user files, partial
adapter output cannot publish, stale result replay fails, and generation never
creates a `mapped`, `tested`, or `verified` Trust claim.

Finally, run independent contract/architecture and publication/security
audits. Close every accepted finding with a focused retained RED. Run affected
suites, all seven canonical gates, inspect the complete admitted diff, and
repeat the physical source-only clean-snapshot protocol.

## Concrete Steps

Work from `/home/deliner/projects/ucf`. Retain observable output under
`.artifacts/quality/ver001-start-20260720/`:

    mkdir -p .artifacts/quality/ver001-start-20260720
    git status --short | tee \
      .artifacts/quality/ver001-start-20260720/git-status-start.log
    uv run --locked --extra dev pytest -q \
      tests/unit/test_generator.py tests/generator tests/cli/test_generate.py \
      --no-cov --capture=tee-sys | tee \
      .artifacts/quality/ver001-start-20260720/focused-baseline.log
    uv run --locked --extra dev ruff check \
      src/ucf/generator tests/unit/test_generator.py tests/generator \
      tests/cli/test_generate.py | tee \
      .artifacts/quality/ver001-start-20260720/focused-ruff.log

The foundation evidence must include the two output manifests, exact changed
paths after regeneration, the user-owned sentinel outcome, clean execution
command/result, protocol frame/result, dependency and ownership inventory,
alternatives, and selected boundary. Run the first production RED only after
that evidence and this plan are updated.

Before package acceptance run:

    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/ver001-final-20260720
    git diff --check

## Validation and Acceptance

VER-001 is accepted only when fresh executable evidence proves:

1. exact identical request/context under at least two hash seeds produces
   byte-identical canonical result and complete generated-file manifest;
2. the generated Python tests execute in a clean temporary workspace without
   editing generator-owned output or monkey-patching imports at runtime;
3. user-owned implementation and unrelated files are never overwritten,
   deleted, silently adopted, or relabeled during first generation or
   regeneration;
4. stale/mismatched behavior, request, producer, capability, procedure,
   environment, or prior-manifest context fails explicitly before publication;
5. unknown fields, duplicate members, incompatible versions, broken refs,
   unsafe/duplicate/colliding paths, noncanonical order, unsupported
   capabilities, malformed content, and ownership ambiguity fail explicitly;
6. output publication is bounded and atomic at the directory-visibility
   boundary, idempotent for exact bytes, preserves the accepted prior tree on
   every pre-commit rejection, and reports any complete-visible post-commit
   cleanup or durability uncertainty with an exact non-success code without
   rolling partial cleanup damage back over the new tree;
7. Python/template/pytest semantics exist only in the external backend; the
   core imports no adapter implementation and applies only language-neutral
   profile, context, and filesystem safety rules;
8. generation does not overwrite implementation code, fabricate evidence, or
   raise any Trust claim;
9. public documentation names only the exact supported backend and execution
   procedure, affected and full gates pass, independent audits accept, and a
   physical clean-source replay is green.

No acceptance may use skip, xfail, warning-only enforcement, path exclusions,
baseline reset, hand-edited generated output, broad exception swallowing,
runtime monkey-patching, or an ownership default that can weaken a previously
protected file.

## Idempotence and Recovery

Foundation probes are read-only with respect to repository source and write
only retained evidence under `.artifacts/` plus disposable temporary
workspaces. Generation must stage into a newly created same-filesystem
directory, validate the complete result and collision set, and publish only
the exact generator-owned transaction. Any pre-commit rejection leaves
accepted inputs, user-owned files, and prior generated output unchanged.

An exact retry may report an idempotent no-op. A different request must not
reuse a stale result, and a new output manifest must not silently claim
ownership of a path previously classified as user-owned. Recovery deletes
only a uniquely created uncommitted staging directory after stable identity
checks; it never recursively cleans a caller-owned destination.
After an update exchange, cleanup failure leaves the complete new destination
in place and reports its uniquely named prior-tree residue; final flush failure
reports that visible completeness is known but crash durability is not.

If the foundation reaches a public-contract break, new production dependency,
destructive migration, security/correctness weakening, or materially different
product semantics, record options, evidence, consequences, and a
recommendation here and set `docs/automation/STATE.md` to
`blocked_on_decision`.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/ver001-start-20260720/`;
- `.artifacts/agents/ver001-generator-contract/`;
- `.artifacts/agents/ver001-ownership-security/`;
- `.artifacts/agents/ver001-protocol-architecture/`;
- `.artifacts/agents/ver001-clean-source-snapshot/`.

Do not retain credentials, private source, generated dependency caches,
unbounded subprocess output, or temporary workspaces.

## Interfaces and Dependencies

Accepted upstream contracts are exact Behavior IR, Trust IR, adapter protocol
and conformance kit, ecosystem adapters/evidence, CHG-001 lifecycle, and
CHG-002 governance resources at their current `1.0.0` versions. VER-001 may
bind or transport them but must not reinterpret them.

Any selected generation request/result profile receives its own exact
version, schema URIs, capability URI, and procedure URI. Its records must be
language-neutral, closed, canonical, schema-backed, content-bound, and
contextually revalidated. The core may validate and safely publish a declared
manifest but may not import a Python backend, interpret pytest/templates, or
infer ecosystem semantics. External adapter implementations and fixture
applications remain outside the wheel.
