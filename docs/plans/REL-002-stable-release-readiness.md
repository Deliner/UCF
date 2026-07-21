# REL-002 Stable Release Readiness

The filename and work-package title are historical. The owner accepted a
bounded `0.1.x` production preview, not a stable API; this plan does not promote
the package to `1.0.0` or broaden its support promise.

This ExecPlan is a living document. `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must always reflect current
repository evidence. Maintain it according to `PLANS.md`.

## Purpose / Big Picture

After this package, an adopter can evaluate, install, operate, upgrade, and
deprecate the bounded UCF release without guessing which contracts are stable,
which platforms and adapters are supported, how security or privacy reports are
handled, what licenses apply, or how a release is reproduced. One executable
release checklist must build the distribution from a clean source tree, install
and exercise it outside the checkout, validate public claims against the
capability matrix, and reject a release when a critical obligation is missing.

This package does not broaden the capabilities accepted through REL-001. It
turns the exact proved scope into an honest release boundary and leaves every
remaining limitation named, owned, justified, and non-misleading.

## Foundational Assumption

The root assumption is that the dependency-ordered implementation is complete
enough for a bounded release and that REL-002 is primarily closure of
policy, distribution, dependency, CI, and public-claim contracts rather than a
hidden core redesign or new production dependency.

Challenge this before production edits with the cheapest useful experiment:
inventory every release surface and compare it with executable evidence. Check
project metadata, root licensing, wheel and source-distribution contents,
locked Python and npm dependency advisories and licenses, CI operating-system
and toolchain coverage, clean-install commands, supported serialized versions,
migration paths, public stability wording, security/privacy reporting, support
and deprecation promises, hooks, and all capability-matrix limitations. Retain
the inventory and command output under
`.artifacts/quality/rel002-start-20260721/`. Classify each gap as a critical
release blocker, an explicitly supportable limitation, or a non-release future
capability; do not silently convert missing evidence into support.

The alternatives are:

1. ship a bounded `0.1.x` release with exact Linux/x86_64 and pinned-toolchain
   evidence, stable compatibility rules for the published serialized
   contracts, and explicit experimental adapter/profile labels;
2. expand this package to cross-platform execution, artifact signing, and a
   broader support promise before any release, which costs substantially more
   and is not justified unless the inventory finds it necessary for an already
   published claim;
3. defer release readiness and retain prototype status if a critical security,
   licensing, migration, or packaging blocker cannot be closed honestly.

Select the smallest complete supported boundary only after the experiment. A
new production dependency or license, a reinterpretation of a published wire
contract, a weaker gate, destructive migration, or materially different
support promise is a human decision gate under `AGENTS.md`.

Result: partly confirmed and partly falsified. Root and three independent
read-only audits found no hidden core redesign or required production
dependency. The current wheel and package contract are reproducible and green,
and a clean Git snapshot produces a reproducible sdist whose isolated wheel
build and installation succeed. However,
the ordinary dependency-populated checkout produces an environment-dependent
30,144,882-byte sdist with 6,655 members, including 5,617 `node_modules`
members; the package has no license grant or release metadata; declared
dependency floors do not install/run; fresh frontend audits report ten
advisories including seven high; and there is no executable release profile or
aggregate policy set. These are bounded REL-002 closure, not a core redesign.

The experiment also falsified the assumption that `0.1.x` can be called the
requested stable release without an explicit owner decision. SemVer describes
major version zero as initial development whose public API should not be
considered stable. License selection, licensor identity, confidential security
intake, public support channel, and the release/deprecation commitment are
human decisions. REL-002 was blocked on those decisions before policy or
metadata implementation; the owner resolved all three and technical work
resumed without broadening the accepted preview boundary.

## Progress

- [x] 2026-07-21: Accept REL-001 with an independently reviewed three-stack,
  three-fixture benchmark, all eight gates, and a physical clean-source replay.
- [x] 2026-07-21: Create this self-contained ExecPlan and activate REL-002.
- [x] 2026-07-21: Run and retain the release-surface inventory and foundational
  falsification through root plus three independent audits. Reproduce missing
  license metadata, the 30.1 MB/6,655-entry contaminated sdist, 5,617 bundled
  `node_modules` entries, false PyYAML/Typer dependency floors, fresh per-lock
  npm advisories, stale public docs, and the absent release profile.
- [x] 2026-07-21: Record the license/identity, security/support-channel, and
  release/deprecation human decision gates; set automation state to
  `blocked_on_decision` before production edits.
- [x] 2026-07-21: Record the project owner's selections: Apache-2.0 with
  copyright holder `Deliner`; bounded `0.1.x` production preview rather than a
  stable-API claim; canonical repository `https://github.com/Deliner/UCF` with
  `Deliner` responsible, GitHub private vulnerability reporting, and Issues
  support without an SLA. Resume REL-002 without changing the requested
  evidence bar or promoting experimental adapters.
- [x] 2026-07-21: Add one failing release-readiness contract at a time, implement the
  smallest closure, and keep each focused slice green through refactoring.
- [x] 2026-07-21: Publish and machine-check compatibility, migration, security, privacy,
  packaging, licensing, support, and deprecation policies and limitations.
- [x] 2026-07-21: Close the local distribution boundary: exact Git-index source
  manifest, identical source-only/dependency-populated sdists, wheel-from-sdist,
  ordinary and supported-floor installs, one package/CLI version, installed
  three-stack package scenarios, strict dependency/license audits, actionable
  install guidance, and credential-aware ignore/exclusion policy. Retain every
  focused RED and GREEN under `.artifacts/quality/rel002-rgr-20260721/`.
- [x] 2026-07-21: Complete three independent pre-acceptance audits and accept
  their exact-index-byte, evidence-publication, installed-environment audit,
  vulnerable-floor, standalone-adapter licensing, archive-expansion, remote
  source-binding, and preview-wording findings. Reproduce every accepted issue
  with a focused RED and implement the smallest correction. The corrected
  installed package contract is green; aggregate and re-audit remain pending.
- [x] 2026-07-21: Run the first independent follow-up re-audit. Reject the
  still-unsound boundary on filtered `checkout-index` bytes, late HEAD binding,
  uncounted directory/PAX expansion, scoped passed evidence, evidence-path
  races, stale/contradictory claims, and missing audit-validator defense in
  depth. Preserve the new REDs, replace checkout export with raw commit/index
  blobs, stream-bound the archive, bind final artifacts to a revalidated commit
  tree, harden evidence publication, reconcile the policy/state baseline, and
  rerun 121 affected plus 180 automation tests and Ruff green.
- [x] 2026-07-21: Run the second independent follow-up re-audit. Reject three
  remaining fail-open paths: dependency audits reading the mutable checkout,
  tar parsing that did not drain concatenated/corrupt gzip members, and hidden
  inventory mode preserving stale final evidence. Add four focused REDs,
  materialize audit inputs from captured commit blobs, drain and validate the
  complete bounded gzip stream, reject conflicting evidence scope, and
  reconcile historical/pending claims. Rerun 124 affected and 183 automation
  tests plus Ruff green, then repeat the complete staged distribution path with
  byte-identical 1,050-member sdists and both install profiles green. Final
  acceptance re-audit remains pending.
- [x] 2026-07-21: Continue the release atomicity audit and reject publication
  before temporary-snapshot cleanup plus post-link failures that left this
  invocation's evidence marker behind. Add three fault-injection regressions,
  finish commit-snapshot cleanup before hosted/final publication, roll back
  only a destination created by the failing publisher, and preserve an
  identical concurrent publisher's file. Rerun 127 affected and 186 automation
  tests plus Ruff green.
- [x] 2026-07-21: Recheck rollback identity and reject its boolean-only
  ownership flag: a concurrent replacement between link and failure could be
  deleted. Add a failing replacement race, bind rollback to the created
  regular-file device/inode with a no-follow recheck, and rerun 128 affected
  and 187 automation tests plus Ruff green.
- [x] 2026-07-21: Commit the accepted local closure as `fe271f8`, publish it to
  canonical remote `main`, and run the first revision-bound aggregate. All
  distribution, package-contract, three-stack, installed-environment,
  dependency, advisory, and license phases passed. Hosted validation alone
  rejected GitHub's still-zero `size` cache even though the branch endpoint and
  Git transport returned the exact `main` branch revision `fe271f8`.
- [x] 2026-07-21: Replace the falsified hosted nonempty heuristic through a
  focused RED/GREEN. A present, well-formed exact `main` branch revision is the
  nonempty/published proof; the GitHub `size` cache remains recorded telemetry
  and must be a nonnegative integer, but is not acceptance authority.
- [x] 2026-07-21: Close the final publisher TOCTOU re-audit. The foundational
  assumption that a device/inode `stat` followed by name-based `unlink` can
  safely roll back a post-link failure was falsified by replacing the entry
  between those calls. Another metadata check and quarantine/restore both keep
  a name race. Test the accepted Linux boundary instead: an anonymous staged
  inode is fully written and flushed, create-only publication is the commit
  point, and post-commit directory durability uncertainty is reported without
  deleting or replacing any visible entry. Rerun 129 affected and 188 automation
  contracts plus Ruff green.
- [x] 2026-07-21: Close the collision-reader follow-up. Its assumptions that
  `O_RDONLY` cannot block before type validation and that exact bytes plus inode
  identity establish a stable exact collision were falsified by a FIFO and an
  append during the final entry check. Require nonblocking open, regular-file
  type, exact size/content, and stable descriptor/entry metadata before an
  idempotent collision can pass. Rerun 131 affected and 190 automation tests
  plus Ruff green.
- [x] 2026-07-21: Refresh the published REL-001 benchmark only through its
  executable runner. The first full eight-gate run falsified the assumption
  that the checked report still matched the release lock: its setup also hit
  one bounded 600-second Go-test timeout, while an immediate exact Go probe
  passed in under two seconds; a complete retry then reached comparison and
  rejected `published_report_drift`. A fresh three-repetition candidate kept
  structural digest
  `c0ef71a90d671d29adabd3c705903244b5cbde9351f51e39da675264ebd6746a`
  and changed only sampled runtimes plus the exact current Click, Pygments,
  runtime-lock, installed-environment, and wheel identities. Promote that
  generated candidate without editing its JSON; static validation, 18 focused
  tests, and an independent three-run replay pass.
- [x] 2026-07-21: Commit and publish candidate `20ea17e`, then run all eight
  gates locally and from a physical public-HTTPS clone with fresh locked Python
  and frontend installs. Both executions pass 190 automation tests, 2,129
  Python tests at 90% coverage, Ruff, 113 specification checks, the three-run
  benchmark, packaging, frontend build, and frontend lint.
- [x] 2026-07-21: Complete independent contract/claims, dependency-order, and
  release-readiness closure re-audits. Accept their governance findings: add a
  canonical backlog status ledger, enforce one complete ExecPlan per package,
  archive two superseded non-ExecPlan proposals, and retain final
  exact-revision acceptance as the sole remaining barrier.
- [x] 2026-07-21: Commit and publish the governance/public-claim closure, run
  explicit revision-bound evidence plus all eight gates and a physical clean
  clone on the resulting exact revision, obtain final independent acceptance,
  and mark REL-002 verified without broadening the preview claim.
- [x] 2026-07-21: Reject a final all-profile run after the public README change
  made the checked REL-001 wheel identity stale. Preserve the exact identity
  check instead of weakening the replay projection, regenerate the report only
  through the three-repetition benchmark runner, and confirm that the sole
  non-runtime change is wheel SHA-256
  `5cefc153b94b52292d58ff0c3768500ea91621017a5867bd0f1ec2191dedd160`;
  static validation and a second complete three-repetition replay pass.
- [x] 2026-07-21: Reject the next full profile when the Go adapter's
  `TestVerificationCleanupDoesNotRepeatGracefulTermination` blocks for its
  ten-minute package timeout. Preserve the timeout trace, prove that production
  cleanup and `Wait` had already returned, and fix only the test harness: use a
  self-executing Go signal helper with directional pipes, close inherited ends,
  and bound marker waits against cleanup completion. Do not retry, enlarge a
  cleanup deadline, or alter production signalling. The focused test passes 100
  normal repetitions and 20 race-instrumented repetitions; the whole Go package
  passes 20 repetitions, Go vet passes, and all 54 affected Go ecosystem tests
  pass. A fresh three-run benchmark has an identical non-runtime projection.
- [x] 2026-07-21: Reopen REL-002 after querying the actual hosted check for
  published candidate `d91e57b`: GitHub Actions run `29839039561` failed the
  canonical all profile. Reclassify the prior local, clean-clone, and
  revision-bound release evidence as candidate history; do not call the
  package accepted while hosted CI is red.
- [x] 2026-07-21: Challenge the new root assumption before another patch.
  Two independent reviews correlate the hosted duration with the Go cleanup
  fixture and identify its artificial 100/500 ms timing window; exact Go
  1.26.5 CI-like runs, 200 focused repetitions, and fresh Ubuntu 24.04 root and
  non-root container runs falsify a deterministic production defect. Retained
  race-instrumented REDs reproduce `signal: killed` under the compressed test
  grace. The exact hosted artifact remains authentication-gated.
- [x] 2026-07-21: Add a focused RED requiring a real pipe whose writer remains
  open to fail with `os.ErrDeadlineExceeded`. Implement deadline-bound
  readiness and termination marker reads, use the unchanged production
  1-second graceful and 2-second absolute cleanup bounds in the integration
  fixture, and keep its real subprocess/SIGTERM/no-repeat assertion. Focused
  normal/race stress, full Go package/race/vet, and all 54 Go ecosystem tests
  pass.
- [x] 2026-07-21: Regenerate and independently replay the benchmark after the
  adapter test change, then publish candidate `c76bc50`. Its local and public
  clean-clone all profiles pass, but actual GitHub Actions run `29844155406`
  exits 1; reject its release evidence instead of substituting local success.
- [x] 2026-07-21: Reproduce the hosted-class failure in two independent fresh
  environments. Exact workflow uv 0.11.29 selects managed CPython 3.12.13 and
  produces seven green gates plus sole `rel001-benchmark` exit 3
  `published_report_drift`; a 3.12.3 control matches. The old report differs at
  exactly Python version and three derived structural digests, while Go and PVR
  pass.
- [x] 2026-07-21: Add a focused RED for one exact shared repository/CI Python
  pin. Set `.python-version` and the workflow install to CPython 3.12.13,
  regenerate the checked report only through the complete three-repetition
  runner, prove the four expected non-runtime changes, and replay it green.
- [x] 2026-07-21: Publish the exact-pin replacement, require its actual GitHub
  Actions run to pass, then regenerate strict release evidence and repeat the
  local plus public clean-clone all profile on the same exact revision.
- [x] 2026-07-21: Obtain independent release, dependency-order, and public-claim
  acceptance on that exact final published revision; inspect the final diff and
  only then return REL-002, the backlog, and automation state to verified.

## Surprises & Discoveries

At activation, the repository has one Linux CI job and an accepted reproducible
wheel workflow, but `pyproject.toml` has no declared project license, classifiers,
readme metadata, authors, or project URLs, and no root `LICENSE` file was found.
These are inventory inputs, not yet accepted conclusions: REL-002 must inspect
the actual built wheel and source distribution and must not choose a license on
the project owner's behalf.

The accepted REL-001 boundary is intentionally narrower than a general stable
ecosystem claim. Python, TypeScript/Fastify, and Go are proved only on exact
frozen Linux/x86_64 fixtures and procedures; no fixture has a `verified` claim.
Release wording must preserve that distinction even if the Python control-plane
package itself becomes supported.

Hatch's default source-distribution discovery follows the physical working
tree, not the Git index. Consequently a clean `git status` did not mean a clean
sdist: ignored frontend and adapter dependencies were redistributed. Root
reproduced the independent result exactly—30,144,882 bytes, 6,655 archive
members, and 5,617 paths below `node_modules`. A Git-archive build is only 1.4
MB/1,038 members. REL-002 needs an explicit bounded sdist inclusion contract
and equality checks from both dependency-populated and source-only trees.

Declared lower bounds are not demonstrated support bounds. On CPython 3.12.3,
`PyYAML==6.0` fails to build; substituting `6.0.1` allows installation, but
`typer==0.12.0` crashes before root help with `Type not yet supported:
pathlib.Path | None`. Both failures were reproduced independently outside the
checkout. Fixing floors is ordinary compatibility work; changing the supported
Python/platform promise or adding an upper bound is a public-contract decision.

Fresh npm registry output differs from the old baseline: the web lock has ten
findings—seven high, one moderate, and two low—and the production-only tree has
two high findings in React Router. The TypeScript adapter and frozen fixture
locks each report zero. Every web finding currently reports a fix, so severity
cannot be converted to a waiver; update or record an exact non-affected
disposition and rerun behavior.

The README still says revision-bound evidence and the three-fixture benchmark
are pending, and the product Ratchet guide describes only v1 despite accepted
Ratchet v2 and migration. The root CLI lacks `--version`; four independent
`0.1.0` literals have no synchronization check; only 2 of 28 capability rows
name an explicit limitation owner. These are claim/checklist gaps rather than
evidence that REL-001 failed.

The release checker itself exposed two deeper closure gaps after the initial
implementation. First, a source-only copy based on the physical checkout could
silently admit untracked files, so the release source manifest now comes from
the Git index and the archived manifest must match it byte-for-byte. Second,
the older package contract installed its own generation pytest coordinate;
fresh Python advisory output identified `pytest 9.0.2` as affected by
`PYSEC-2026-1845`, so the exact executable generation coordinate and lock moved
to `9.1.1`. The resulting Python, npm, and Go audits report zero known
advisories without skips or waivers.

The first full release checker passed both sdist builds, wheel-from-sdist,
ordinary and minimum-floor installation, the complete installed package
contract, all three ecosystem lanes, and its dependency/license inventories.
Independent review nevertheless rejected it: it copied working-tree bytes
after selecting index paths, could leave stale evidence, audited the locked
tool environment instead of both installed environments, admitted vulnerable
Pydantic/Jinja floors, omitted UCF licensing from standalone adapter artifacts,
did not bound uncompressed sdist expansion, and accepted an empty hosted
repository. That earlier green result is superseded rather than grandfathered.

The owner subsequently enabled GitHub Private Vulnerability Reporting. Focused
RED/GREEN slices now export exact index objects, invalidate then atomically
create evidence, capture both actual install inventories and environment
coordinates, and require the aggregate checker to audit them independently.
They use `pydantic>=2.4.0` and `jinja2>=3.1.6`, package UCF
`LICENSE`/`NOTICE` with TypeScript and Go artifacts, bound per-member and total
sdist expansion, and require final evidence source HEAD to equal nonempty
remote `main`. Final aggregate evidence remains deliberately unavailable until
the corrected committed revision is pushed and rechecked.

The first follow-up re-audit falsified two of those corrections: Git
`checkout-index` may apply clean/smudge/EOL conversion, and a late clean-HEAD
check does not bind an earlier mutable index export. It also demonstrated more
than 3,000 directory headers bypassing the file-only member limit, a scoped
distribution command publishing top-level passed evidence, a collision
`lstat`/read race, and several cross-document contradictions. Raw blob export,
commit-tree snapshots, streaming all-member/tar-byte limits, final-scope-only
evidence, descriptor-bound publication, and executable claim consistency now
replace the rejected design. The earlier green is again superseded rather than
treated as debt.

The second follow-up re-audit found that a clean final HEAD check still did not
bind dependency audits that read the mutable checkout, tar iteration stopped at
the first end marker without draining later gzip members, and hidden inventory
mode returned before stale final evidence was invalidated. Dependency review
now runs against a source tree materialized from the captured commit blobs, the
bounded reader consumes and validates the complete gzip stream, and every mode
invalidates then rejects an incompatible final-evidence request. The associated
four REDs, 124 affected tests, 183 automation tests, and Ruff result are retained
under `.artifacts/quality/rel002-rgr-20260721/`.

The final atomicity pass then showed that temporary-snapshot cleanup and a
post-link directory durability failure could occur after final evidence became
visible. Local snapshot verification now exits its managed directory before
hosted/final publication. The first correction attempted to roll back the
destination inode created by its own failed call.

Independent recheck then replaced the newly linked entry before an injected
durability failure and proved that boolean ownership was insufficient. A second
correction captured device/inode identity, but the final audit replaced the
entry after `stat` and before `unlink`, proving that name-based rollback was
still unsafe. Publication now writes and flushes an anonymous staged inode,
uses create-only `linkat` as the commit point, and performs no name-based
rollback afterward. A parent-directory flush failure reports
`committed_durability_unknown` while preserving the complete visible entry;
acceptance still requires command exit zero.

The first aggregate run against published `fe271f8` falsified the assumption
that GitHub repository `size > 0` is a synchronous publication fact. The GitHub
`size` cache remained zero after push while the REST branch endpoint and Git
transport both returned the exact `main` branch revision. A repository without
that branch cannot pass because the endpoint fails; exact branch identity is
therefore the direct nonempty proof, while cached size remains nonnegative
telemetry. The failed aggregate left no final evidence file.

The first all-profile replay after final public-claim editing then rejected
`published_report_drift`. The structural and lifecycle digests, fixtures,
toolchains, dependency lock, and all measured outcomes were unchanged; the only
non-runtime difference was the wheel digest because README content is embedded
in wheel metadata. Regenerating the canonical report through its executable
runner and replaying it three more times closed the drift without excluding
artifact identity from verification.

The subsequent full Python suite exposed an unrelated intermittent deadlock in
a Go test harness. Its parent opened marker FIFOs `O_RDWR`, then waited
synchronously for a termination marker before observing that both the helper
and bounded cleanup goroutines had already exited. The parent's own FIFO writer
prevented EOF forever. Production cleanup remained bounded and sent the root
graceful signal only once. Directional anonymous pipes, a self-executing Go
signal helper, and marker waits selected against cleanup completion remove the
deadlock and shell scheduling dependency without changing a protocol,
production timeout, or retry policy.

The next hosted candidate exposed a separate deterministic environment drift.
The repository supported CPython 3.12 but did not pin the patch used to create
environment-bound benchmark evidence. GitHub's exact setup-uv flow selected
managed 3.12.13, while the checked report recorded 3.12.3. Two independent
fresh-clone reproductions passed every other gate and isolated exactly four
non-runtime differences: Python version, the Python component digest, the
aggregate structural digest, and the lifecycle digest. An initially conflicting
probe was traced to an inherited 3.12.3 virtual environment and retracted after
a clean-environment replay. This is evidence that the exact patch is a required
benchmark coordinate, not a reason to erase Python identity from comparison.

## Decision Log

- **2026-07-21 — do not broaden product capability during release closure.**
  Author: root agent. REL-002 may add policy, checks, package metadata, CI and
  distribution proof required for the accepted scope. New adapters, general
  cross-platform semantics, signing infrastructure, hosted services, and new
  generation backends remain outside scope unless the foundational experiment
  proves an existing release claim cannot be made honestly without them.

- **2026-07-21 — treat policy text as an executable release contract.** Author:
  root agent. Every required policy must be discoverable from the README,
  internally consistent with the capability matrix, and covered by a release
  checklist or documentation-claim test. Prose alone does not close a critical
  blocker.

- **2026-07-21 — use the staged Git source set as the sdist authority.** Author:
  root agent. Hatch configuration remains the explicit include/exclude policy,
  but release selection is the Git index intersected with that policy. Both a
  source-only copy and the dependency-populated checkout must archive exactly
  that selected manifest with identical bytes. Untracked checkout files cannot
  become release input, and a tracked selected file cannot be silently omitted.

- **2026-07-21 — accept no dependency advisory or license waivers in the
  preview release checklist.** Author: root agent. The checker audits the
  hashed locked Python all-extras set, exact fully enumerated build set, all
  three npm locks plus web runtime scope, and zero-external-module Go boundary.
  Audit coordinates must equal license-inventory coordinates. Missing metadata,
  a nonzero advisory count, unknown license, or network failure blocks release.

- **2026-07-21 — hosted confidential intake is executable release state.**
  Author: root agent, implementing DG-REL002-003. The release checker verifies
  the exact public repository, default `main` branch, enabled Issues, and
  enabled GitHub Private Vulnerability Reporting through GitHub's API. Policy
  prose cannot substitute for the selected confidential route. The owner
  enabled it on 2026-07-21; final acceptance must still bind that hosted result
  to the exact clean source revision published on remote `main`.

- **2026-07-21 — reject the first green release result after independent
  audit.** Author: root agent. A passing aggregate command is insufficient when
  its source, dependency, publication, archive, or hosted-revision boundary is
  unsound. The pre-audit evidence is retained as historical diagnostic output
  but is superseded and cannot support CAP-214. Every accepted finding receives
  a focused failing test, minimal correction, affected suite, and independent
  re-audit before release acceptance.

- **2026-07-21 — bind final release evidence to published committed source.**
  Author: root agent. An explicit evidence run requires no tracked staged or
  unstaged differences and exact equality between local HEAD and canonical
  remote `main`. Ordinary CI/PR checks may validate a non-main revision without
  publishing final evidence, but they record that it is not the published
  revision. An empty repository or missing/malformed branch fails closed.

- **2026-07-21 — use exact remote branch identity, not cached repository size,
  as publication authority.** Author: root agent. The first post-push aggregate
  observed GitHub `size` cache `0` while the branch API and Git transport agreed
  on the exact `main` branch revision. Final evidence still requires a valid
  public repository, enabled Issues/PVR, a present well-formed `main`, and exact
  local/remote revision equality. Cached size is recorded but cannot veto that
  stronger direct proof.

- **2026-07-21 — keep exact wheel identity in the published benchmark.**
  Author: root agent. Final README changes legitimately alter packaged wheel
  metadata, so a prior checked wheel digest cannot remain accepted. Do not
  ignore wheel identity as volatile and do not hand-edit generated benchmark
  JSON. Preserve the failed all-profile replay, regenerate the complete report
  through the benchmark runner, require that every non-runtime field except the
  expected wheel digest is unchanged, and rerun the full installed replay.

- **2026-07-21 — correct the Go cleanup test harness, not production cleanup.**
  Author: root agent after independent diagnosis and direct stack-trace review.
  The timeout showed no live production cleanup or `Wait` goroutine; only the
  test remained blocked on a FIFO whose parent-held writer suppressed EOF.
  Preserve the existing graceful/absolute deadlines and signal semantics.
  Replace the shell/FIFO fixture with a self-executing Go helper and directional
  pipes, close unused endpoints, and select every marker wait against the
  bounded cleanup result. A missing marker now fails promptly and cannot turn
  into a ten-minute suite hang.

- **2026-07-21 — hosted green is an independent acceptance prerequisite.**
  Author: root agent after querying the public checks API. Exact local and
  clean-clone success cannot substitute for the configured GitHub Actions run.
  Candidate `d91e57b` is therefore superseded even though its local release
  evidence and three independent audits passed. A replacement revision must
  make the hosted check itself green before final release evidence is accepted.

- **2026-07-21 — pin the benchmark's managed Python patch without narrowing
  package compatibility.** Author: root agent after two independent
  fresh-environment reproductions. Keep `requires-python >=3.12` and the public
  CPython 3.12/Linux x86_64 preview tier: the package is tested at supported
  floors separately. For deterministic repository and CI evidence, pin
  CPython 3.12.13 in `.python-version` and the workflow install. Preserve the
  benchmark's interpreter identity, regenerate only through its full runner,
  and require future patch movement to be an explicit reviewed report change.

- **2026-07-21 — remove test-only scheduler compression, not production
  safety.** Author: root agent after two independent diagnoses and Ubuntu
  container replay. Production already sends one graceful group signal and
  has 1-second/2-second escalation bounds. The fixture's 100/500 ms substitute
  is not the contract and produced retained race-instrumented `signal: killed`
  failures. Use the actual constants, retain the 20 ms no-repeat observation,
  and put OS pipe read deadlines on both marker phases. Do not increase a
  production deadline, retry a failed gate, or replace the real process test
  with mocks.

- **2026-07-21 — make the create-only evidence link the publication commit
  point.** Author: root agent. A device/inode `stat` cannot make a later
  name-based `unlink` conditional, so another metadata check cannot close the
  rollback race. On the supported Linux boundary, the complete JSON is written
  and flushed as an anonymous staged inode and published with `O_TMPFILE` plus
  `linkat(AT_EMPTY_PATH)`. No destination deletion occurs after commit. A later
  directory-flush error is explicit `committed_durability_unknown`, preserves
  the complete visible entry, and remains a nonzero, non-accepted run.

- **2026-07-21 — DG-REL002-001: project license and licensor identity.** Status:
  accepted by project owner. At the decision gate there was no root license,
  package SPDX expression, license file in the wheel, or demonstrated grant to
  copy/modify/redistribute UCF. The owner also had to confirm authority over the
  current contributions and provide the exact copyright holder/year. Options:

  1. **Apache-2.0 (recommended):** permissive source/binary use with explicit
     contributor patent terms, well suited to a multi-vendor adapter/protocol
     ecosystem. Distribution must carry the license, preserve required notices,
     and satisfy its modification/attribution conditions.
  2. **MIT:** shortest, lowest-administration permissive option and familiar to
     adopters, but it does not provide Apache-2.0's equivalent explicit patent
     grant/termination language.
  3. **Proprietary or source-available terms:** retains more owner control but
     requires exact owner-authored terms and a new compatibility/distribution
     review; it materially reduces friction-free adapter adoption.
  4. **Defer licensing:** keep the repository non-releasable. Technical work may
     continue, but REL-002 cannot be accepted.

  Primary references are the OSI Apache-2.0 and MIT texts and ASF application
  guidance. This recommendation is engineering/product guidance, not legal
  advice.

  **Owner decision:** select Apache-2.0. Use `Copyright 2026 Deliner` as the
  exact project notice. The owner's statement that this is their repository,
  made while selecting the license, is the authorization basis recorded for
  the current contribution set. Add the canonical license and notice to every
  supported source/wheel distribution while preserving third-party notices.

- **2026-07-21 — DG-REL002-002: stable release and deprecation promise.**
  Status: accepted by project owner. Package `0.1.0` cannot simultaneously follow
  SemVer and represent a stable public API: SemVer reserves major zero for
  initial development. Options:

  1. **Bounded `1.0.0` stable control plane (recommended for the requested real
     production outcome):** support CPython 3.12 on Linux/x86_64, exact
     documented wire/CLI versions and the wheel/sdist install path; retain
     external ecosystem adapters and fixture profiles as experimental exact
     proofs. Use SemVer for the package. Announce deprecations for at least one
     minor release and 180 days, whichever is longer; remove public contracts
     only in a major release with a published migration, except an explicitly
     documented urgent security withdrawal. Community support has no SLA.
  2. **Supported `0.1.x` production preview:** smaller compatibility commitment
     and faster iteration, but it must remain labeled preview/non-stable and
     therefore does not satisfy the requested stable-release result by itself.
  3. **Broaden evidence before `1.0.0`:** first add more Python minors and OS/
     architecture jobs, broad adapter artifacts, and optionally signing. This
     increases time and scope substantially; current public claims do not
     require it.

  The non-breaking implementation recommendation is to leave
  `requires-python >=3.12` installable while documenting only the exercised
  3.12/Linux support tier; untested future Python versions are unqualified, not
  promised. Exact corrected dependency floors still need automated proof.

  **Owner decision:** select option 2 and keep the package in the `0.1.x`
  production-preview line. Do not describe UCF itself or its public API as
  stable. REL-002 proves that this preview is reproducibly releasable and usable
  in the exact supported scope; promotion to `1.0.0` remains an explicit future
  owner decision and an honest limitation owned by `Deliner`. Support is
  CPython 3.12 on Linux/x86_64 with no SLA. Exact published artifacts and wire
  versions are immutable; normal deprecations remain available for at least one
  subsequent minor preview and 90 days before removal, with migration guidance.
  An urgent security withdrawal may be faster only through a published advisory
  naming the affected versions and replacement. External adapters and frozen
  ecosystem profiles remain experimental exact proofs.

- **2026-07-21 — DG-REL002-003: confidential security intake and public support
  route.** Status: accepted by project owner. No Git remote, project URL, public
  maintainer identity, or authorized confidential address is configured. Do
  not publish the local Git email or invent a hosted service. Options:

  1. **Repository-hosted channels (recommended):** owner supplies the canonical
     public repository URL, enables GitHub private vulnerability reporting, and
     designates repository administrators/security managers as responders;
     public support uses repository Issues or Discussions with no SLA.
  2. **Owner-provided mail channels:** publish a dedicated private security
     address and a separate public support address, each with an explicit
     responsible person/entity and no SLA unless the owner chooses one.
  3. **No intake/support channel:** keep release readiness blocked. A public
     issue tracker alone is not a safe default for vulnerability disclosure.

  GitHub documents that private vulnerability reporting must be enabled by an
  owner/admin and provides a private structured report path; enabling it is an
  external state change that is not authorized implicitly by this task.

  **Owner decision:** use `https://github.com/Deliner/UCF` as the canonical
  repository, `Deliner` as responsible maintainer, GitHub private vulnerability
  reporting for confidential intake, and GitHub Issues for public support with
  no SLA. The repository was supplied in direct response to this gate, so local
  remote configuration and verification of these selected repository-hosted
  channels are authorized. Do not publish the local Git email.

## Outcomes & Retrospective

The foundation, all three owner decisions, policy set, local distribution
closure, dependency/advisory remediation, release metadata, exact version
diagnostic, and executable release profile are implemented. Independent review
materially strengthened their trust boundaries; its accepted findings and
focused corrections are recorded above. The selected result remains a bounded
`0.1.x` production preview, not a stable API.

The hardening audit trail remains explicit: 131 affected and 190 complete
automation tests passed at that milestone. Its retained evidence includes
`distribution-final-precommit-green.log`, `release-atomicity-final-green.log`,
`release-rollback-race-green.log`, `release-post-commit-affected-green.log`,
and `release-collision-affected-green.log`; later counterexamples supersede
only the unsafe claims named above, never the failing-test history.

REL-002 is accepted. All twenty dependency-ordered packages are verified and
the repository now exposes one canonical complete ExecPlan per package. The
bounded result remains a `0.1.x` production preview for the CPython 3.12/Linux
x86_64 control plane, not a stable API, SLA, registry publication, tag, signed
artifact, broad platform promise, or promotion of experimental adapters.

The published governance candidate `0f10681` first proved the complete strict
path with `source_snapshot.kind=git_commit`, exact local/remote `main`, enabled
Issues and PVR, identical 1,491,281-byte/1,051-member sdists, ordinary and
supported-floor installs, zero-known-advisory dependency review, installed
three-stack scenarios, and a 230-file wheel at SHA-256
`87c7012f7a9a36d85d3cbf6394ea8da192bf4e50a356c2e96b9276d114dee505`.
That precursor is retained as
`release-evidence-governance-candidate-0f10681.json`, not substituted for the
final revision.

Final revision-bound evidence is under
`.artifacts/quality/rel002-final-ci-closure-20260721/`; a fresh public clone
replay and independent final reviews are under
`.artifacts/agents/rel002-final-ci-closure/`, and hosted check metadata is under
`.artifacts/ci/rel002-final/`. These paths carry the final revision and changing
artifact identities without embedding a self-invalidating commit hash in this
plan. Independent final reviews accept the release evidence, dependency order,
diff, and public-claim boundary.
The final all-profile attempt first caught one honest REL-001 wheel-identity
drift after README metadata changed; its RED and the generated-report replay
GREEN are retained alongside the accepted aggregate rather than hidden.
The next attempt caught and retained the Go harness deadlock. Its correction is
test-only, survives normal and race-instrumented stress, and leaves the complete
REL-001 non-runtime report projection unchanged.

Published candidate `d91e57b` was then rejected because its actual GitHub
Actions run exited 1. The replacement closes the remaining fixture-only risks:
readiness and termination markers have OS pipe deadlines, the integration test
uses the unchanged production 1-second/2-second cleanup policy instead of an
artificial 100/500 ms scheduler window, and the real subprocess/SIGTERM/
no-repeat assertion remains. The accepted evidence includes the focused RED,
normal/race stress, Ubuntu 24.04 root and non-root replay, the full Go ecosystem
lane, exact REL-001 non-runtime replay, local and hosted all profiles, public
clean clone, and exact-final-revision independent audits.

Candidate `c76bc50` was also rejected when its hosted run selected managed
CPython 3.12.13 against a report recorded under 3.12.3. The final replacement
does not weaken environment binding: it makes 3.12.13 the exact repository/CI
toolchain coordinate and publishes a complete runner-generated report at
structural digest
`4f0e77045ca5c0cf4994d3059585aefa549854eee2897c2b7968b35f1881854b`
and lifecycle digest
`b315a73a701304448edd63ed955fe9de45040df343e76fd1ede424f5adb78260`.
The broader package compatibility declaration and bounded CPython 3.12 support
tier remain unchanged.

The implementation's rejected name-based rollback history remains documented.
The accepted publisher uses an anonymous staged inode and no name-based
rollback; `committed_durability_unknown` exits nonzero. The lasting lesson is
that release-readiness prose is trustworthy only when exact source, artifact,
installation, dependency, hosted-surface, claim, governance, and clean-clone
checks converge on the same published revision.

## Context and Orientation

`pyproject.toml` and `uv.lock` define the Python control-plane package and lock;
`src/ucf/schemas/` contains installed serialized contracts. `web/package.json`
and its lock define the frontend. The TypeScript adapter has its own private
package and lock under `adapters/typescript-fastify/`; the selected Go adapter
and third-party notices are under `adapters/go-stdlib/`. The only current CI
workflow is `.github/workflows/quality.yml`.

`tools/quality_gates.py` is the canonical eight-gate local/CI runner.
`tools/package_contract.py` proves a wheel outside the checkout, including all
four installed REL-001 lanes. `docs/CAPABILITIES.md` is the canonical public
claim matrix; `README.md` is the entry point. `docs/automation/BASELINE.md`
records known release-review inputs, and `docs/benchmarks/` contains the checked
REL-001 proof.

For this package, compatibility means the explicit accept/reject and migration
rules for each published wire/CLI contract; support means the environments and
response boundary the project commits to maintain. A limitation is releasable
only when it is truthful, discoverable, assigned to an owner (project, adapter
maintainer, caller/operator, or future backlog), and cannot be mistaken for a
passing capability. A critical blocker is an unresolved issue that makes the
published package unsafe, unlawful, uninstallable, irreproducible, or materially
misleading within its claimed scope.

## Plan of Work

First, snapshot the release surfaces and run the cheapest falsification. Build
the wheel and source distribution, inspect both metadata/file manifests, then
install the direct wheel and the separately built wheel from the source
distribution in clean environments. Inventory dependency advisories/licenses
from locked inputs, inspect CI/toolchain and platform claims, and trace every
public capability statement to a test or checked report. Record findings before
changing behavior.

Second, define one machine-readable release-readiness manifest and/or focused
validator only if the probe shows it is the smallest way to keep policy and
claims synchronized. Start with a failing automation test for each required
property: required policy discoverability, exact capability status, package
metadata and license inclusion, supported artifact formats, migration and
deprecation coverage, clean installation, and advisory disposition. Avoid a
second prose-only release system.

Third, write the minimal policies and migration/compatibility tables around
already published versions. Security and privacy text must state threat and
trust boundaries, reporting paths, supported fixes, data retention, external
adapter/process risks, and known deferrals. Packaging/licensing/support text
must state artifact scope, platform/toolchain matrix, dependency and notice
handling, supported install path, response ownership, versioning, and
deprecation windows. Any choice reserved to the owner becomes an explicit
decision gate before edits.

Fourth, extend the release checklist and clean package contract only where the
new REDs require it. Prove wheel and sdist reproducibility/contents as supported,
fresh isolated installation, installed CLI/schema operation, all three adapters'
bounded scenarios, frontend build/lint, and failure on stale or inflated public
claims. Keep adapters out of the Python core and do not weaken existing gates.

Finally, commission independent policy/claims, security/privacy/licensing, and
packaging/release audits. Reproduce every accepted finding, retain its RED,
close it minimally, and rerun affected suites. Then run all eight gates locally
and from a physical clean-source snapshot with fresh locked installs, inspect
the complete diff, update `BASELINE.md`, this plan, `STATE.md`, and CAP-214, and
commit the accepted release boundary.

## Concrete Steps

Work from `/home/deliner/projects/ucf` and stream evidence to the terminal and
artifact files:

    mkdir -p .artifacts/quality/rel002-start-20260721
    git status --short | tee \
      .artifacts/quality/rel002-start-20260721/git-status-start.log
    git ls-files | sort | tee \
      .artifacts/quality/rel002-start-20260721/tracked-files.log
    uv build --clear 2>&1 | tee \
      .artifacts/quality/rel002-start-20260721/build-baseline.log
    uv run --locked python tools/package_contract.py 2>&1 | tee \
      .artifacts/quality/rel002-start-20260721/package-baseline.log

Record npm advisory evidence separately for each lock and do not merge severity
counts across different dependency trees. Use only primary package-manager or
registry output for current advisory facts. Do not add an audit dependency to
the production package merely to run the probe.

For every implementation slice, retain the focused failing test, its intended
failure, the minimal green change, scoped Ruff, and the affected suite. Before
acceptance run:

    uv run --locked --extra dev pytest -q tests/automation --no-cov \
      --capture=tee-sys
    uv run --locked --extra dev --extra web pytest -q --disable-warnings
    uv run --locked --extra dev ruff check src tests tools \
      .codex/hooks/stop_quality.py
    uv run --locked python tools/package_contract.py
    python3 tools/quality_gates.py --profile all
    git diff --check

## Validation and Acceptance

REL-002 is accepted only when fresh executable evidence proves:

1. compatibility and migration rules name every supported serialized/CLI
   version and reject unknown, incompatible, downgraded, or broken inputs;
2. security and privacy policies accurately name the current-user process,
   filesystem, authenticity, raw-data, secret, sandbox, hook, and reporting
   boundaries, with every critical advisory resolved or explicitly deferred by
   an authorized decision and non-misleading support status;
3. wheel and supported source distribution include required schemas, metadata,
   license/notices, and documentation; the release wheel and wheel built from the source distribution
   install in clean environments and run the advertised
   CLI and release scenarios without checkout imports;
4. dependency and license inventories are derived from exact locks/artifacts,
   and every production or bundled dependency has an accepted disposition;
5. support and deprecation policies define supported Python, Node, Go, OS/
   architecture, adapter/profile, serialized-version, response, and retirement
   boundaries without claiming more than the checked matrix;
6. the release checklist fails on missing policy, package files, stale checked
   evidence, inflated capability text, a critical unowned blocker, or a clean-
   install failure;
7. README, documentation index, capability matrix, package metadata, benchmark,
   and release policy agree; CAP-214 changes from `planned` only to the exact
   status proved by the final gates;
8. all eight quality gates, affected suites, independent audits, complete diff
   review, physical clean-source replay, and clean direct-wheel plus
   wheel-built-from-sdist release scenarios pass from fresh locked installs.

## Idempotence and Recovery

Inventory and audit commands are read-only apart from ignored artifacts and
build output. Use new timestamped artifact directories so failed evidence is
not overwritten. Build and install into disposable directories outside the
checkout; never repair generated distribution contents manually. Publication
checks must write to absent temporary paths or perform an exact no-op. A failed
release checklist publishes no acceptance marker and cannot change a baseline,
version, tag, remote repository, registry, or hosted service.

If a dependency service is unavailable, retain the typed/network failure and
repeat it; do not record a clean advisory result. If a human decision gate is
reached, record options, consequences, evidence, and recommendation here and
set `docs/automation/STATE.md` to `blocked_on_decision` before stopping.

## Artifacts and Notes

Retain concise evidence under:

- `.artifacts/quality/rel002-start-20260721/` for the foundation inventory;
- `.artifacts/quality/rel002-rgr-20260721/` for focused RED/GREEN slices;
- `.artifacts/quality/rel002-final-20260721/` for local acceptance;
- `.artifacts/agents/rel002-*/` for independent reviews and clean snapshots.

The accepted foundation reports are
`.artifacts/agents/rel002-security-licensing/report.md`,
`.artifacts/agents/rel002-packaging-ci/audit-summary.md`, and
`.artifacts/agents/rel002-policy-claims/report.md`. Root reproductions in the
start artifact include the sdist manifest/counts, wheel metadata, fresh npm
audits, missing-profile output, and dependency-floor failures.

Never retain credentials, registry tokens, private dependency metadata, raw
sensitive runtime values, unbounded command output, or dependency caches.

## Interfaces and Dependencies

REL-002 consumes every package accepted through REL-001 and must not reinterpret
their wire versions. Expected release-facing additions are documentation,
package metadata, a bounded release-readiness/checklist contract, automation
tests, and clean-distribution checks. The exact shape remains contingent on the
foundation probe; avoid a serialized product resource unless a real consumer
requires one.

The owner's accepted repository decision authorizes root to push the verified history
to `https://github.com/Deliner/UCF.git`; push to remote `main` is authorized.
No new production dependency, different license, hosted service, signing
identity, registry publication, tag/release creation, or other remote write is
authorized by this plan. The project owner must decide any such gate. Build and
audit tools used only in isolated verification must be exact-versioned or
otherwise captured in command evidence and must not silently enter the runtime
dependency set.
