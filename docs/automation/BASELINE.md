# Repository quality baseline

Observed on 2026-07-21 from `/home/deliner/projects/ucf`. Counts and digests are
command evidence, not allowances to reset when they regress.

## REL-002 accepted release-readiness evidence

REL-002 and all nineteen dependencies are verified. CAP-214 is implemented for
the bounded `0.1.x` CPython 3.12/Linux x86_64 production-preview control plane,
not a stable API or general adapter/platform claim.

The authoritative ignored evidence is:

- `.artifacts/quality/rel002-final-ci-closure-20260721/` — the exact final
  published revision's release evidence and all eight local gates;
- `.artifacts/agents/rel002-final-ci-closure/` — public-HTTPS clean clone,
  fresh locked installs, complete all-profile replay, and independent final
  release/dependency/claims audits;
- `.artifacts/ci/rel002-final/` — public GitHub Actions run metadata proving the
  canonical workflow is green on the same exact revision.

The earlier candidate evidence is retained as superseded history:

- `.artifacts/quality/rel002-final-20260721/release-evidence.json` — strict
  `git_commit` source snapshot, exact local/public remote `main`, identical
  source distributions, wheel-from-sdist, ordinary and supported-floor clean
  installs, installed package and three-stack scenarios, dependency/advisory/
  license review, public Issues, and enabled Private Vulnerability Reporting;
- `.artifacts/quality/rel002-final-20260721/quality-gates-all-final.log` — all
  eight canonical local/CI gates on that same published revision;
- `.artifacts/agents/rel002-final-clean-source/` — public-HTTPS clean clone,
  fresh locked Python and frontend installs, complete all-profile replay, and
  source/status checks;
- the final independent claims, dependency-order, and release-readiness audits
  under `.artifacts/agents/rel002-final-*/`.

The immediately preceding all-profile attempt is retained as
`quality-gates-all-final-benchmark-drift-red.log`: seven gates passed, while
the REL-001 replay correctly rejected a stale checked wheel digest after final
README metadata changed the wheel. The report was regenerated only by the
three-repetition runner; every non-runtime field except wheel SHA-256 remained
identical, static validation passed, and
`rel001-verify-after-refresh.log` records a second complete green replay. The
accepted wheel identity is
`5cefc153b94b52292d58ff0c3768500ea91621017a5867bd0f1ec2191dedd160`.

`quality-gates-all-final-go-harness-red.log` retains the next rejected full
profile: the Go cleanup unit fixture waited ten minutes on a parent-held
`O_RDWR` FIFO after its helper and bounded cleanup had already returned. It was
not treated as a retryable flake. The test-only correction uses directional
pipes and a self-executing signal helper, retains the existing production
deadlines and signal behavior, and bounds marker waits against cleanup
completion. Evidence includes 100 focused normal repetitions, 20 focused
race-instrumented repetitions, 20 complete Go-package repetitions, Go vet, and
54 affected ecosystem tests. A fresh three-repetition REL-001 run has an exact
match for every non-runtime report field, so no benchmark identity was hidden
or manually rewritten.

Published candidate `d91e57b` was subsequently rejected by GitHub Actions run
`29839039561`. Exact hosted logs require authentication, but public check
metadata proves the canonical all-profile step exited 1. Independent diagnosis
found no production cleanup defect: the remaining test fixture compressed the
real 1-second/2-second cleanup policy to 100/500 ms and left readiness without
an OS read deadline. The accepted correction adds a focused real-pipe timeout
RED, applies read deadlines to both markers, and uses the unchanged production
bounds. It passes 200 normal and 100 race focused repetitions, 20 full package
runs, full-package race, Go vet, all 54 ecosystem tests, and Ubuntu 24.04 root/
non-root container replay. A fresh three-repetition benchmark matches every
non-runtime field exactly, including structural/lifecycle, wheel, and adapter
identities; no checked benchmark output was rewritten.

The earlier strict governance candidate is retained at
`.artifacts/quality/rel002-final-20260721/release-evidence-governance-candidate-0f10681.json`.
It passed with exact local/remote revision `0f10681`, a 1,050-file selected
source snapshot, byte-identical 1,491,281-byte/1,051-member sdists, zero-known-
advisory dependency review, both install profiles, and the reproducible
230-file wheel SHA-256
`87c7012f7a9a36d85d3cbf6394ea8da192bf4e50a356c2e96b9276d114dee505`.
It is precursor evidence, not the final revision marker.

## REL-002 pre-acceptance evidence — historical

The following evidence predates final acceptance and is retained as the
hardening audit trail. It was not an accepted release baseline at the time:
`.artifacts/quality/rel002-rgr-20260721/`:

- `python-full.log`: 2,107 tests passed at 90% source coverage before one final
  documentation-only automation test was added;
- `automation-post-hardening.log`: all 169 automation contracts pass;
- `ruff-post-hardening.log`, `spec-validation.log`, `web-build.log`, and
  `web-lint.log`: Ruff is clean, 113 specs load with zero errors/warnings, and
  the frontend build/lint passes;
- `distribution-only-evidence.json`: pre-audit diagnostic in which source-only
  and dependency-populated sdists were byte-identical, the wheel built from the source distribution
  and exact supported-floor install passed CLI smoke. The
  exact-index and archive-boundary re-audits supersede this as acceptance
  evidence;
- `dependency-audit-actual-green.log`: pre-audit diagnostic for locked Python,
  npm, and Go inventories. It did not audit both actual installed environments
  and is superseded as acceptance evidence;
- `full-release-pre-pvr.log`: historical aggregate output that passed the first
  local implementation and then failed because Private Vulnerability Reporting
  was disabled. Independent review subsequently invalidated that implementation
  as an acceptance boundary, so this log is diagnostic only.
- `git-index-bytes-red.log`, `release-evidence-stale-red.log`,
  `installed-environment-audit-wiring-red.log`,
  `supported-floors-advisory-red.log`, `adapter-license-artifacts-red.log`,
  `sdist-uncompressed-limit-red.log`, `hosted-main-revision-red.log`, and their
  corresponding green logs preserve the accepted independent-audit fixes.
- `package-contract-adapter-licenses.log`: the corrected installed package and
  three-stack artifact contract passes, including root UCF `LICENSE`/`NOTICE`
  in standalone TypeScript and Go distributions, at deterministic evidence
  SHA-256
  `87c7012fc84bd4f8f81ef7996514403778d990a63a2e797d8c71320301108894`.
- `release-reaudit-findings-red.log` preserves ten independently reproduced
  failures covering filtered source export, archive members/paths, commit
  binding, evidence scope/publication, audit skips, and ignore policy;
  `release-reaudit-findings-green-attempt2.log` passes all 24 focused release
  tests after correction.
- `release-third-reaudit-red.log` preserves four focused failures for complete
  gzip-stream validation, incompatible inventory/evidence scope, and
  commit-snapshot dependency-audit inputs; its green counterpart passes all
  four. `release-claims-third-reaudit-red.log` preserves the historical/current
  claim contradiction and its green counterpart passes.
- `release-third-reaudit-affected.log` passes all 124 release/quality/claim
  contracts; `automation-third-reaudit-green.log` passes all 183 automation
  contracts; `ruff-third-reaudit-green.log` is clean.
- `release-atomicity-final-red.log` preserves publisher and snapshot-cleanup
  fault injection; `release-atomicity-final-green.log` passes all five selected
  atomic/create-only scenarios. `release-final-affected.log` passes all 127
  affected contracts, `automation-final-reaudit-green.log` passes all 186
  automation contracts, and `ruff-final-reaudit-green.log` is clean.
- `release-rollback-race-red.log` preserves the reproduced concurrent
  destination replacement; `release-rollback-race-green.log` passes all six
  selected publication/cleanup scenarios. `release-race-final-affected.log`
  passes all 128 affected contracts, `automation-race-final-green.log` passes
  all 187 automation contracts, and `ruff-race-final-green.log` is clean. A
  later stat-then-unlink counterexample supersedes its rollback-safety claim.
- `.artifacts/quality/rel002-final-20260721/release-post-commit-race-red.log`
  preserves that final name-based rollback race. The focused
  `.artifacts/quality/rel002-final-20260721/release-post-commit-green.log`
  proves the replacement design: an anonymous staged inode is published at a
  create-only commit point, and `committed_durability_unknown` never starts
  name-based rollback.
  `.artifacts/quality/rel002-final-20260721/release-post-commit-affected-green.log`
  passes all 129 affected contracts,
  `.artifacts/quality/rel002-final-20260721/release-post-commit-automation-green.log`
  passes all 188 automation contracts, and
  `.artifacts/quality/rel002-final-20260721/release-post-commit-ruff-green.log`
  is clean.
- `.artifacts/quality/rel002-final-20260721/release-collision-reader-red.log`
  preserves the blocking FIFO and concurrent-append counterexamples; its green
  counterpart passes both. `release-collision-affected-green.log` passes all
  131 affected contracts, `release-collision-automation-green.log` passes all
  190 automation contracts, and `release-collision-full-ruff-green.log` is
  clean.
- `distribution-raw-index-streaming-green.log` passes the complete corrected
  staged raw-index distribution path, including identical 1,050-member sdists,
  wheel built from the source distribution, ordinary and safe-floor installs,
  exact environment/license inventories, and CLI smoke. It is affected evidence,
  not final committed/published acceptance.
- `distribution-third-reaudit-green.log` repeats that staged-source path after
  complete-gzip and commit-bound dependency-source hardening. The later
  `distribution-final-precommit-green.log` repeats the staged path after
  atomicity corrections: both 1,050-member sdists are byte-identical, and
  ordinary/supported-floor installs, CLI smoke, and exact license/environment
  inventories pass. Exact changing pre-commit digests remain in retained output;
  dependency audits remain for the final aggregate run.
- `.artifacts/quality/rel002-final-20260721/release-check.log` is the first
  aggregate against
  published `fe271f8`: distribution, wheel/package contract, three stacks,
  ordinary/floor installs, dependency advisories, and license alignment passed;
  the hosted phase rejected GitHub `size` cache `0`, and no final evidence file
  was published.
  `.artifacts/quality/rel002-final-20260721/github-surface-after-push.log`
  records the simultaneous exact `main` branch revision from REST and Git
  transport. The focused
  `.artifacts/quality/rel002-final-20260721/hosted-size-cache-red.log` and
  `.artifacts/quality/rel002-final-20260721/hosted-size-cache-green.log`
  correction makes that exact branch identity the direct nonempty proof and
  retains size only as nonnegative telemetry.

The historical 30,144,882-byte, 6,655-member sdist, false PyYAML/Typer floors,
ten frontend advisories, missing license/policy metadata, stale pytest 9.0.2
generation coordinate, and absent CLI version diagnostic are resolved by the
current implementation. Independent review additionally caught and corrected
working-tree-byte substitution, stale/non-atomic evidence, vulnerable
Pydantic/Jinja floors, audit coverage that omitted actual install environments,
missing standalone-adapter project licensing, unbounded sdist expansion, and
acceptance of an empty hosted repository. None is accepted debt. At this
intermediate milestone PVR was enabled and candidate `20ea17e` was published to
remote `main`. Its all-profile and physical clean-source executions were green,
while CAP-214 stayed planned until governance/public claims and the exact final-
revision replay were complete. The accepted section above supersedes that
transitional status.

## Pre-final technical baseline — historical

From public HTTPS clone `20ea17e`, after fresh locked Python and frontend
installs, the command:

    python3 tools/quality_gates.py --profile all

exited zero after running all eight phases:

    PASS automation-tests         exit=0
    PASS python-tests             exit=0
    PASS python-lint              exit=0
    PASS spec-validation          exit=0
    PASS rel001-benchmark         exit=0
    PASS packaging-contract       exit=0
    PASS web-build                exit=0
    PASS web-lint                 exit=0

Detailed observations:

- automation contracts: 190 passed;
- Python: 2,129 passed and 90% source coverage;
- Ruff over `src`, `tests`, `tools`, and the project Stop hook: no findings;
- specifications: 113 loaded, 0 errors, and 0 warnings;
- the checked REL-001 report replayed three complete real-stack repetitions at
  structural digest
  `c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a`;
- packaging built two byte-identical wheels and exercised the installed UCF
  contracts, Ratchet v2 and migration, Python, TypeScript/Fastify, Go HTTP,
  Go CLI/event, generation, lifecycle, governance, and evidence-status lanes
  outside checkout imports; candidate wheel SHA-256 is
  `87c7012f7a9a36d85d3cbf6394ea8da192bf4e50a356c2e96b9276d114dee505`;
- frontend TypeScript/Vite production build and ESLint passed;
- `git diff --check` reported no whitespace errors.

The packaging phase produced byte-identical 1,050-member sdists with selected
source manifest SHA-256
`bf3b077b83088bee665018c68b29ce2c110db2caed18ffbbddd710e62539e197`
and object manifest SHA-256
`bbe0d593eb822a4541e758ce28243fdf58269144c9efc61719b643ca97938a34`.
Exact local output is
`.artifacts/quality/rel002-final-20260721/quality-gates-all-benchmark-refreshed.log`;
the physical replay is
`.artifacts/agents/rel002-clean-source-snapshot/20260721T130000Z-20ea17e/quality-gates-all.log`.
This was a green technical candidate, not the final acceptance marker.

## Prior VER-002 green baseline

From a checkout with Python and frontend dependencies installed from the
repository manifests, the command:

    python3 tools/quality_gates.py --profile all \
      --log-dir .artifacts/quality/20260720T155500Z

exited zero after running all seven phases:

    PASS automation-tests         exit=0
    PASS python-tests             exit=0
    PASS python-lint              exit=0
    PASS spec-validation          exit=0
    PASS packaging-contract       exit=0
    PASS web-build                exit=0
    PASS web-lint                 exit=0

Detailed observations:

- automation contracts: 75 passed;
- Python: 1,880 passed and 90% source coverage;
- Ruff over `src`, `tests`, `tools`, and the project Stop hook: no findings;
- specifications: 113 loaded, 0 errors, 0 warnings, 2 informational orphan
  findings;
- packaging: two byte-identical wheels, all thirty-eight public schemas, the exact
  19-asset adapter kit, and all required templates present; an external clean
  `uv` environment executes the installed source, behavior-IR, trust-IR,
  adapter-conformance, and inventory CLI surfaces, validates both IR contracts
  and cross-document binding, extracts the kit, repeats the sample
  byte-for-byte, localizes all seven faults, verifies exactly three inventory
  and four onboarding plus four ratchet schema resources, completes installed
  discovery, DecisionSet authoring, and stale-checked onboarding against an
  external copied adapter and unchanged fixture, then executes deterministic
  ratchet establishment, unchanged/regression evaluation, protected
  improvement, reintroduction, and malformed-input preservation. It
  additionally validates all four installed runtime-evidence resources, copies
  the recording/reference adapter outside the wheel, repeats explicit import
  under two hash seeds, verifies observed-only projection, exercises typed
  rejection with output preservation, and finds no raw fixture, adapter, or
  forbidden value in decompressed wheel members. It also reproduces the
  private TypeScript distribution plus two independent offline Go
  adapter/HTTP/platform build lanes, runs installed HTTP and platform smokes
  through external binaries, and keeps all Go assets outside the wheel. It
  also installs all six lifecycle schemas and runs the complete pinned
  OpenSpec import/export, exhaustive delta, ordered task, implementation,
  verification, and archive workflow under two hash seeds outside the
  checkout. It additionally installs all four change-governance schemas,
  executes compatible and breaking impact/assessment/decision/gate lanes
  under two hash seeds, preserves a blocked-output sentinel, and revalidates
  the complete exact context in isolated Python. It additionally installs both
  evidence-status schemas and runs deterministic record/fresh/stale/
  indeterminate/refresh lanes, negative output preservation, and a concurrent
  first-publication race from the clean environment.
  Accepted SHA-256 is
  `7311760bf249ad195dbb30ad563cafeddbfee77921851ba5a154ea91ef9cb2ec`;
- frontend: TypeScript and Vite production build passed with 611 modules;
- frontend ESLint: no findings;
- `git diff --check`: no whitespace errors.

The accepted VER-002 clean snapshot is the latest complete physical
source-tree reproduction. It contains 996 regular source files with manifest
SHA-256
`d392c673ca85ff30319acd13e674136f43e7c0c8dcd0854ea7ad10cefbc83e1c`.
It reproduced all seven gates after fresh locked Python/frontend installs,
kept all source files byte-identical before/after and against the checkout,
reproduced the accepted wheel and external ecosystem hashes, and ran installed
HTTP, platform, lifecycle, governance, generation, and evidence-status
workflows only against external inputs/binaries. Exact evidence is
under
`.artifacts/agents/ver002-clean-source-snapshot/20260720T160959Z-ver002/`.

`uv` creates or updates the Python environment from `pyproject.toml` and
`uv.lock`. A bare checkout must install frontend dependencies with
`(cd web && npm ci)` before the profile; CI performs that lockfile-faithful
step explicitly. The quality runner does not silently install or mutate
dependencies.

The prior IR-002 independent clean snapshot included tracked and intended untracked source
while excluding `.git`, `.venv`, `web/node_modules`, build output, caches,
coverage, and artifacts. After `npm ci`, it produced the same 537 tests,
88% coverage, 113-spec result, wheel hash, and seven passing gates. It
reproduced installed behavior/trust schemas and CLIs, validated the complete
12-record trust fixture pair, and left `uv.lock` unchanged. Evidence is under
`.artifacts/agents/ir002-clean-snapshot/`.

The initial independent contract audit rejected a green snapshot on
adversarial integer, nesting, timestamp, semantic-duplicate, and unguarded
opaque-rule failures. Every issue received a retained RED test and correction;
the re-audit accepted 74 focused IR tests, schema freshness, Unicode/emoji
cross-runtime canonical bytes, and a clean neutrality scan. Evidence is under
`.artifacts/agents/ir001-contract-audit/` and
`.artifacts/agents/ir001-contract-reaudit/`.

## Historical red baseline and resolution

The initial retained run under
`.artifacts/quality/preparation-20260719/` exited one with only automation
green. A confirming work-package start run is under
`.artifacts/quality/fnd001-start-20260719/`.

Those failures were removed rather than accepted:

- fresh and checked-in generated suites now collect; a focused regression
  executes fresh orchestration after supplying the deliberately user-owned
  implementation and concrete input fixture;
- generated interface and orchestrator files reproduce deterministically, and
  checked-in implementations are checked against all 27 generated interfaces;
- repository lint fell from 796 findings to zero without exclusions,
  suppressions, skips, or expected failures;
- the two invalid HTTP fixtures were completed and two missing referenced
  actions were added; missing use-case step references are errors;
- specification validation rose from 109 to 113 loaded specs and now has zero
  errors and zero warnings;
- the unused frontend import was removed and the incomplete local Rollup
  installation was restored through `npm ci`.

The original focused core slice had 186 passing tests at 68% coverage, and the
FND-001 accepted profile had 325 tests at 82%. They were useful milestone
evidence, but both are superseded by the complete 408-test, 86%-coverage
profile and must not be quoted as current status.

## Strict-boundary and claim resolution

FND-002 removed the parser and claim gaps recorded by the FND-001 baseline:

- modeled source objects reject unknown fields, primitive coercion, internal
  Python aliases, malformed alternatives, and missing discriminators;
- duplicate identities fail atomically and identify both sources;
- supported logical and file references reject missing, retargeted, and
  wrong-kind targets;
- unsupported retry generation and invalid generation input fail before
  output;
- the deterministic Draft 2020-12 source schema validates all repository specs
  and rejects the shared structural negative fixtures;
- `docs/CAPABILITIES.md` is the automation-checked current claim boundary, and
  historical/proposal documents are labeled accordingly.

## Deterministic gate and packaging resolution

FND-003 removed the delivery-mechanics gaps recorded by the FND-002 baseline:

- local and CI select one versioned manifest of stable gate IDs, tokenized
  commands, and working directories;
- duplicate or unsafe IDs fail before subprocess or log mutation;
- project-environment gates require `uv.lock`, and CI action inputs are pinned
  to immutable commits;
- the complete profile includes byte-reproducible wheel builds and a
  source-independent installation/asset/CLI smoke;
- the project Codex Stop hook uses the official event contract, affected gates
  for ordinary work, explicit full release selection, and loop prevention.

## Versioned behavior IR resolution

IR-001 removed the language-neutral wire-contract gap recorded by FND-003:

- exact IR `1.0.0` has closed tagged records for use cases, actions, ordered
  steps, bindings, effects, observations, invariants, provenance,
  verification evidence, and capability requirements;
- raw decoding rejects duplicate members, ambiguous/non-finite numbers,
  unsafe integers, invalid encodings, and excessive nesting with stable codes;
- semantic validation rejects global identity, reference-kind, port, binding,
  set-duplicate, capability-name, and opaque-capability errors;
- canonical JSON is byte deterministic with explicit set/order rules and
  Unicode parity in Python and Node;
- the checked Draft 2020-12 schema and `ucf ir validate` ship in the wheel;
- CAP-108 claims only structural/semantic validation. Claim promotion,
  reconciliation, adapter execution, and formal verification are not silently
  inferred from behavior-IR acceptance.

## Intent/evidence trust resolution

IR-002 removed the intent/evidence conflation gap recorded by IR-001:

- exact trust IR `1.0.0` retains immutable declarations, observed facts,
  uncertain candidates, explicit mappings, source records, and claims without
  changing behavior IR;
- behavior references bind exact document/version/kind/ID identity to the
  SHA-256 of canonical behavior-IR bytes, while artifact source revisions
  remain separate coordinates;
- reconciliation preserves both facts and returns only a revalidatable
  same-slot `match` or `conflict`; different subjects or targets fail;
- claim levels are independent predicates, never an ordinal or mutable
  promotion chain; candidate confidence is a bounded canonical decimal string
  and never executable evidence;
- `tested` requires passed evidence matching the exact subject, current
  artifact revision, check ID/version/procedure, environment, and producer
  resolved through evidence provenance;
- `failed`, `error`, stale, mismatched, candidate, and circular bases are
  rejected with stable errors; `verified` is explicitly unavailable;
- the generated closed schema, complete fixtures, `ucf trust validate
  --behavior-ir`, installed APIs, and CAP-202 evidence ship in the wheel.

The initial independent contract audit rejected a reconciliation API that
could return a mapping the validator would not accept. A retained RED mutation
and shared disposition derivation fixed it; contract, distribution, and clean
snapshot re-audits accepted the result. Evidence is under
`.artifacts/agents/ir002-contract-audit/`,
`.artifacts/agents/ir002-distribution-audit/`, and
`.artifacts/agents/ir002-clean-snapshot/`.

## Out-of-process adapter protocol resolution

ADP-001 removes the in-process semantic-coupling gap recorded by IR-002:

- exact protocol `1.0.0` uses one strict LF-delimited JSON-RPC object per
  frame, eight closed methods, exact request IDs, a deterministic packaged
  schema, and a repository-owned canonical transcript;
- initialize negotiates unique named capabilities and canonical versions
  without converting unbounded decimal segments to Python integers;
- inventory, discovery, mapping, generation, and verification cross a real
  child-process boundary with Behavior IR, Trust IR, or a tagged neutral
  payload; the core imports no adapter implementation;
- error category, symbolic code, and JSON-RPC numeric code are mutually
  consistent; peer responses cannot forge local timeout/process outcomes or
  cancellation the client did not request;
- pending requests, completed-ID history, stderr retention, frames, nesting,
  deadlines, and process teardown have explicit bounds; the final session
  request slot is reserved for shutdown;
- coroutine cancellation cannot abandon startup, shutdown, one-shot calls,
  futures, or child processes; POSIX teardown covers an inherited grandchild
  even after its leader exits;
- a real pipe regression proves a detached response-write failure exits the
  standalone server with code 4 while stdin remains open.

The initial contract/process audits rejected green implementations on
lifetime-ID reuse, unbounded retention, mutable cancellation provenance,
local-only peer errors, long-version conversion, coroutine cancellation
leaks, and detached server-task failure. Every item has a retained RED test.
Final audit evidence is under
`.artifacts/agents/adp001-contract-reaudit/`,
`.artifacts/agents/adp001-process-reaudit/`, and
`.artifacts/agents/adp001-distribution-audit/`.

## Adapter conformance kit resolution

ADP-002 removes the public cross-runtime conformance gap recorded by ADP-001:

- exact kit `1.0.0` publishes a closed manifest, schema, 17 canonical
  transcripts, 19 digest-indexed assets, a dependency-free Node sample, and
  stable report/exit contracts for protocol `1.0.0`;
- the installed black-box runner launches argv without a shell, uses one fresh
  process and scratch environment per case, drains bounded stdout/stderr
  during write, receive, and shutdown, and reaps its owned POSIX process group;
- success expectations accept only initialize, five operation, and shutdown
  results with result-specific payload/capability coordinates; the only
  published isolation mode is the implemented `fresh_process`;
- exact JSON negatives include duplicate members and non-JSON NBSP
  whitespace; malformed output, correlation, capability, error-coordinate,
  cancellation, timeout, and shutdown faults each fail only their named case;
- canonical reports exclude argv, cwd, environment values, timing, PID, and
  raw stderr, and repeated installed sample runs are byte-identical;
- public documentation states that the current-user process is not sandboxed,
  POSIX cleanup is not Windows parity, and passing this exact profile is not
  ecosystem, framework, domain-semantic, brownfield, or production support.

The first reliability audit rejected missing receive-phase stderr saturation
evidence. Retained RED tests now cover write, receive, and clean shutdown.

## Read-only brownfield inventory resolution

BRN-001 removes the pre-spec evidence-capture gap recorded by ADP-002:

- exact request, bounded page, and assembled snapshot profile `1.0.0`
  resources are independently addressable, closed, generated, and installed;
- every fact is observed-only and binds canonical confidence, provenance,
  producer/procedure identity, content-derived record identity, and source
  revision;
- all five generic inventory categories report complete or partial coverage,
  while read, classification, mutation, unsafe-path, collision, non-regular,
  cancellation, and resource outcomes remain explicit diagnostics;
- deterministic paging fits the actual protocol frame and reachable 65,534
  request/session record ceiling, with exact cursor, header, order, count, and
  digest validation;
- the external reference adapter prunes only the explicit ignore policy before
  access, never follows symlinks on the measured Linux path, bounds directory
  enumeration and all output categories, and localizes parser exhaustion;
- `ucf adapter inventory` validates before spawn, preserves argv without a
  shell, writes only a caller-selected outside-root destination, and replaces
  completed canonical output atomically;
- the core imports no legacy scanner, fixture adapter, or language/framework/
  build-tool semantics, and public CAP-204 claims only the measured
  experimental observed-inventory boundary.

Initial independent audits rejected schema/runtime local-coordinate gaps,
unbounded directory/classification accumulation, parser-exhaustion
`internal_error`, collection-induced fixture bytecode, and an untracked-file
EOF whitespace defect. Every finding received retained RED/GREEN evidence.
Final contract, external-reference, distribution, and corrected clean-snapshot
audits report ACCEPT under:

- `.artifacts/agents/brn001-contract-reaudit/`;
- `.artifacts/agents/brn001-reference-acceptance/`;
- `.artifacts/agents/brn001-distribution-acceptance/`;
- `.artifacts/agents/brn001-clean-snapshot-final/`.
Further retained REDs removed impossible success coordinates, the unimplemented
`shared_session` schema value, and JavaScript's overly broad `\s` acceptance.
Final evidence is under
`.artifacts/quality/adp002-final-freeze2-20260719/`,
`.artifacts/agents/adp002-final-contract/`,
`.artifacts/agents/adp002-final-reliability-rerun/`,
`.artifacts/agents/adp002-final-isolation-audit/`,
`.artifacts/agents/adp002-json-whitespace-audit/`, and
`.artifacts/agents/adp002-clean-snapshot-final2/`.

## Python brownfield onboarding resolution

BRN-002 removes the candidate-to-baseline vertical-slice gap recorded by
BRN-001 for one unchanged dependency-free Python fixture:

- exact discovery request/result, human DecisionSet, and final onboarding
  bundle profiles `1.0.0` are closed, generated, installed, and validated at
  both structural and cross-document semantic boundaries;
- one external adapter process completes inventory before discovery in the
  same negotiated session and owns all Python parsing semantics; the core
  imports no adapter implementation, scanner, framework, or language-specific
  discovery code;
- candidates bind complete inventory bytes, provenance, confidence, coverage,
  content identity, and deterministic semantic proposals without becoming
  intent or verified truth;
- the explicit two-phase CLI preserves accepted, edited, rejected, and
  uncertain decisions, repeats discovery to reject stale review, and replaces
  a final bundle only after complete validation;
- only accepted and edited proposals materialize Behavior IR; Trust IR retains
  exact decision-bound declarations and observations without mapped, tested,
  or verified promotion;
- the first baseline is deterministic and explicitly non-enforcing. BRN-003
  owns touched-behavior calculation, anti-weakening rules, and regression
  enforcement;
- installed repeated discovery/onboarding is byte-identical, failure paths
  preserve existing output, and the unchanged fixture retains its eight-entry
  manifest SHA-256
  `654fe6c58854f11f910ef21a19d1098ddda8b9d20196862783493fc6561d228d`.

An initial independent contract audit rejected diagnostic-validation bypasses,
a forgeable Trust-builder input, a structural-only bundle parser, a
schema/runtime procedure mismatch, and discovery-only provenance for
post-decision observations. Each finding received retained negative RED/GREEN
coverage. Final contract/trust, process/CLI, and distribution/clean-snapshot
audits report ACCEPT under:

- `.artifacts/agents/brn002-contract-reacceptance/`;
- `.artifacts/agents/brn002-process-cli-reacceptance/`;
- `.artifacts/agents/brn002-distribution-clean-acceptance/`.

## Baseline-and-ratchet resolution

BRN-003 removes the silent baseline-reset and false-regression gap recorded by
BRN-002:

- exact Policy, Assessment, Baseline, and EvaluationReport `1.0.0` resources
  are closed, generated, installed, and contextually recomputable;
- stable language-neutral behavior subject identity is separated from exact
  trace coordinates, with independently versioned semantic and observed
  fingerprints so capture-only or unrelated changes do not touch behavior;
- unchanged accepted debt passes only under complete evidence, while new,
  semantically/observationally touched, and protected reintroduced violations
  fail with exact reviewable weakening data;
- any partial subject or per-rule coverage makes an otherwise
  non-regressing evaluation inconclusive, and definitely observed regressions
  retain fail precedence;
- an immutable successor binds its exact predecessor, assessment, passing
  evaluation, and adjacent generation, removes only proven resolutions, and
  preserves them as tombstones that cannot silently return;
- installed `ucf ratchet establish`, `evaluate`, and `advance` transactions
  use `0`/`1`/`3` exits, validate before same-directory atomic replacement,
  reject path/symlink/hard-link aliases, preserve failure sentinels, and never
  mutate accepted inputs;
- the current clean wheel carries exactly sixteen schemas and executes the
  complete flow outside the checkout while the external Python fixture adapter
  remains outside the distribution.

The final contract, CLI/security, and physical clean-distribution audits report
ACCEPT under:

- `.artifacts/agents/brn003-final-contract/`;
- `.artifacts/agents/brn003-final-cli-security/`;
- `.artifacts/agents/brn003-clean-distribution/`.

## Optional runtime-evidence resolution

BRN-004 removes the optional observed-runtime import gap recorded by BRN-003
for one bounded synthetic recording and one external fixture adapter:

- exact Policy, Environment, Request, and accepted/rejected Result `1.0.0`
  resources are closed, generated, installed, and validated structurally and
  against exact Behavior, source, environment, adapter, capability, procedure,
  policy, and content identities;
- import is recorded-only and explicit, requires both verification and
  runtime-evidence capabilities, keeps recording-format semantics outside the
  core, retains no adapter stderr, and fails on any stderr byte;
- the policy is allowlist-only with reject handling for selected secret or
  personal-data categories, omitted unselected data, no raw retention, partial
  sampling with unknown total, and no absence inference;
- accepted results name only exact policy-rule references; pure projection
  creates one `SourceRecord` plus `ObservedFact` records and cannot create a
  declaration, mapping, candidate, tested/verified claim, intent mutation, or
  ratchet allowance;
- the installed atomic CLI binds immutable inputs, rejects path/symlink/
  hard-link aliases, uses sanitized code-only diagnostics and `0`/`1`/`3`
  exits, preserves prior output on every failure, and reaps timed-out or
  cancelled child processes;
- the clean package carries exactly twenty schemas while the raw recording and
  reference adapter remain external. Two hash seeds produce byte-identical
  installed output, and decompressed wheel plus retained-artifact scans contain
  zero forbidden fixture values.

The final contract/projection, privacy/evidence-scope, and
distribution/claims audits report ACCEPT under:

- `.artifacts/agents/brn004-contract-projection-reacceptance/`;
- `.artifacts/agents/brn004-privacy-scope-reacceptance/`;
- `.artifacts/agents/brn004-distribution-claims-reacceptance/`.

The accepted boundary is traceability, not authenticity. It does not claim
live capture, broad OpenTelemetry compatibility, universal sensitive-data
detection, hostile-adapter isolation, signed producer identity, or complete
sampling.

## OpenSpec-compatible change-lifecycle resolution

CHG-001 removes the executable change-history gap recorded after ECO-003:

- exact Proposal, BehaviorDelta, TaskGraph, ImplementationRecord,
  VerificationRecord, and ArchiveRecord `1.0.0` resources are closed,
  generated, installed, canonical, and contextually recomputable;
- every accepting post-delta transition receives the exact base and final
  Behavior IR and recomputes exhaustive added, modified, and removed subject
  membership; a digest is identity, not proof that an earlier command ran;
- ordered tasks reject duplicate, missing, cyclic, non-canonical, or
  incomplete predecessors, while task status is explicitly declared current
  state rather than authenticated command history;
- implementation and verification records bind exact result, mapping,
  onboarding, inventory, producer, capability, procedure, environment, and
  source coordinates without producing a Trust claim or claiming live adapter
  authenticity;
- removed behavior remains representable, but old-subject execution evidence
  fails closed until a final-state absence/tombstone profile exists;
- archive is immutable and possible only after complete tasks, accepted
  passing evidence, exact predecessor validation, and final Behavior IR
  reconstruction;
- the pinned `fission-ai.openspec/spec-driven@1` boundary, tested against
  `@fission-ai/openspec==1.6.0`, preserves declared prose artifacts without
  executing them, uses bounded iterative regular-file traversal, and
  transactionally publishes only to an absent destination or an exact
  manifest no-op;
- all five public lifecycle reference helpers reject `None` and wrong-kind
  resources with typed errors, and duplicate JSON members, unknown fields,
  incompatible versions, broken refs, filesystem aliases, unstable reads,
  partial writes, invalid transitions, and stale context fail explicitly.

The final independent re-audit passes the fourteen former blockers, deep-tree
classification, canonical round-trip, Go process/pipe ownership repetitions,
full Go suite/vet, focused integration, and freshness checks under
`.artifacts/agents/chg001-final-reaudit2/`. The final local and physical-clean
all-profile runs pass under `.artifacts/quality/chg001-final2-20260720/` and
`.artifacts/agents/chg001-clean-source-snapshot/20260720T083629Z-chg001/`.

The accepted boundary is deterministic context-validated lifecycle
traceability, not authenticated task history, signed evidence, arbitrary
OpenSpec-profile compatibility, proof of removed-source absence, or broad
ecosystem/platform verification. Those limitations remain public in CAP-210
and are inputs to VER-002 and REL-002.

## Deterministic executable generation resolution

VER-001 closes the bounded generation gap with:

- exact closed generation request/result `1.0.0` resources transported through
  the accepted language-neutral adapter protocol;
- a Python/pytest renderer that remains an external adapter and is absent from
  the UCF wheel and core imports;
- deterministic two-seed canonical results and complete receipt-backed output
  trees whose generated test executes after clean wheel installation;
- explicit generated-only ownership, exact no-op regeneration, pre-commit
  prior-tree preservation, and typed complete-visible post-commit cleanup or
  durability uncertainty;
- retained negative coverage for stale context, unknown and duplicate data,
  unsupported capabilities, incompatible versions, unsafe paths, filesystem
  substitution, staged-content mutation, and unrecognized cleanup targets.

The post-hardening local and physical clean-source profiles pass under
`.artifacts/quality/ver001-final3-20260720/` and
`.artifacts/agents/ver001-clean-source-snapshot/20260720T132838Z-ver001/`.
Both produce wheel SHA-256
`d98f3fcfd6b8ce7493e98b10a2dcd85a35d4a98dbc74da5014e027538cb9b91a`;
the physical snapshot covers 937 byte-stable regular source files at manifest
SHA-256
`52013a5c0957410a1c8819a14c9314415015a55d19150d54aedac98f0a552712`.

## End-to-end adoption benchmark and Ratchet v2 resolution

REL-001 closes the three-stack adoption-proof gap without promoting evidence
levels or broadening the core IR. A parallel Ratchet `2.0.0` dual ledger keeps
accepted Behavior violations separate from unresolved coverage debt while v1
remains unchanged. Exact inherited uncertainty may remain; new, changed, or
reintroduced uncertainty blocks; comparable resolution is protected. The real
Python, TypeScript/Fastify, and Go adapters pass the common conformance boundary
and execute unchanged brownfield fixture flows. Exact HTTP, CLI, and local
file-spool event procedures produce five `tested` claims and zero `verified`
claims.

The closed published report records 13 candidates, 7 oracle false candidates,
13 candidate decisions, 1 ambiguity resolution, 0 mapping approvals, 0 change
approvals, 4 mappings, 5 materializations, 18 uncovered interfaces, and 20
unresolved debt entries. Its three-run structural digest is
`c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a`.
Runtime samples and authored/derived overhead remain separate from structural
identity, and scripted review counts are not called human effort.

Independent reviews found and closed provenance, runtime matrix, transport,
tool identity, overhead, installed-wheel, bounded-I/O, failure-receipt,
lifecycle determinism, and clean-snapshot race defects. Retained evidence is
under `.artifacts/quality/rel001-benchmark-20260721/` and
`.artifacts/agents/rel001-*/`. CAP-213 remains experimental and bounded to the
exact frozen fixtures, Linux/x86_64 environment, pinned tools, and procedures.

## Remaining evidence-bounded product limitations

These are current product boundaries, not accepted quality-gate failures:

- platform, event, protocol, temporal, and composite declarations remain
  declaration-only unless an executable capability row explicitly names an
  exact checked procedure; CAP-209 proves only its frozen HTTP, CLI, and local
  file-spool procedures;
- the accepted generation profile proves one direct Python function contract
  with JSON-compatible values; retry declarations, TypeScript/Go generation,
  and broader backend semantics remain unsupported rather than inferred;
- drift exposes a `stale_mappings` concept that is not populated;
- the adapter protocol and conformance kit are experimental; Python,
  TypeScript/Fastify, and Go evidence remains limited to the exact frozen
  fixtures and procedures rather than broad ecosystem/framework support;
- ratchet assessments still import static reviewed onboarding facts only;
  optional runtime evidence is a separate observed-only input and does not
  automatically alter a ratchet baseline. Runtime authenticity and the
  accepted baseline tip remain caller/VCS/CI trust anchors rather than a
  signed multi-writer service;
- hosted Python/Node patch labels, declared runtime dependency ranges,
  sdist/cross-platform/signing behavior, and hook trust/policy remain explicit
  release-review inputs even though the current wheel workflow is accepted;
- release evidence remains unsigned and depends on GitHub/VCS/CI/operator trust;
  its final publication requires Linux `O_TMPFILE`/`linkat` support from the
  evidence filesystem, and a nonzero `committed_durability_unknown` outcome is
  not accepted even though its complete post-commit file is preserved without
  name-based rollback;
  supported vendor security patch status cannot be inferred from the upstream
  Python patch string alone.

Broader platform execution is outside CAP-209. REL-002 must preserve these
limitations while closing only its bounded preview-release acceptance. Future
work must update this list with fresh evidence rather than silently deleting it.

## REL-002 activation snapshot — historical red baseline

Root and independent observations made at activation on 2026-07-21 are retained under
`.artifacts/quality/rel002-start-20260721/` and `.artifacts/agents/rel002-*/`.
They explain why the package started red; the current disposition follows each
observation and the opening REL-002 section is authoritative for acceptance:

- observed: the repository and wheel had no UCF project license or authorized
  security/support route. Disposition: Apache-2.0 `LICENSE`/`NOTICE`, package
  metadata, PVR, Issues, and their executable checks are implemented;
- observed: `uv build --clear` from the dependency-populated checkout emitted
  a 30,144,882-byte sdist with 6,655 entries, including 5,617 ignored
  `node_modules` paths. Disposition: the checker exports selected raw Git object
  bytes, compares dependency-populated output, and enforces compressed,
  member-count, per-member, total-file, and tar-stream limits;
- observed: on CPython 3.12.3, the declared `PyYAML==6.0` floor failed. With
  `PyYAML==6.0.1`, the declared `typer==0.12.0` floor installs but the clean
  installed `ucf --help` failed. Disposition: corrected direct floors and both
  actual ordinary/supported-floor environments are installation-tested; the
  aggregate checker requires independent advisory/license alignment, with the
  fresh post-fix aggregate run still pending;
- observed: the web lock's fresh npm audit reported ten findings, including
  seven high and two runtime React Router findings. Disposition: compatible
  lock upgrades removed them; final fresh aggregate audit is still required;
- observed: the package contract was green and the working-tree wheel was
  reproducible at SHA-256
  `17cc39364e513d1f0cf6f5d94508146de8da5748ee7928d11e8dd2d8cd105489`,
  while clean sdists were reproducible and their isolated wheel build/install
  succeeded. Disposition: this supported the no-core-redesign decision but is
  historical, not the final artifact hash;
- observed: no release-checklist gate existed and public policy/version/owner
  metadata was not synchronized. Disposition: `tools/release_check.py`, policy
  documents, release metadata, and claim tests implement the bounded checklist;
  fresh final execution is pending the committed/published revision.

For reference, the original registry command was
`npm audit --package-lock-only --ignore-scripts --json`; at activation the web
  lock reports 10 findings: 7 high, 1 moderate, and 2 low. Runtime-only reports
2 high React Router findings, while the TypeScript adapter and frozen fixture
locks each reported zero. These counts are deliberately retained as historical
input and must not be quoted as current advisory state.

The active ExecPlan records the project owner's accepted decisions: Apache-2.0
under `Copyright 2026 Deliner`; bounded `0.1.x` production preview with
CPython 3.12/Linux x86_64 support and no SLA; and repository-hosted private
vulnerability reporting plus public Issues at `github.com/Deliner/UCF`.
Automation resumed after those decisions. The remaining work is exactly the
fresh final acceptance listed at the top of this file, not the superseded
activation observations.

## Baseline update rule

Do not edit counts to make a package appear green. Run
`python3 tools/quality_gates.py --profile all`, retain complete phase logs under
`.artifacts/quality/`, and update this file with the date, command, result, and
reason for every changed observation. A new failure is a regression until a
failing acceptance test and an in-scope fix prove otherwise.
