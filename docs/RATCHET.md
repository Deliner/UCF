# Baseline and ratchet profile 1.0.0

UCF has an experimental, language-neutral baseline-and-ratchet boundary for
incremental brownfield adoption. It distinguishes unchanged accepted legacy
debt from new or touched-behavior regressions, records resolved debt as a
protected improvement, and requires an explicit immutable successor before
the accepted floor changes. The canonical support claim and its limits are in
`docs/CAPABILITIES.md`.

This boundary compares exact reviewed behavior and assessment documents. It
does not execute policy rules, capture runtime traces, or turn discovered
candidates into truth. In particular, it does not create verified evidence.

## Exact documents

The installed wheel publishes four closed Draft 2020-12 resources:

- policy: `urn:ucf:ratchet:policy:1.0.0`;
- assessment: `urn:ucf:ratchet:assessment:1.0.0`;
- baseline: `urn:ucf:ratchet:baseline:1.0.0`;
- evaluation report:
  `urn:ucf:ratchet:evaluation-report:1.0.0`.

The policy selects the exact capability `org.ucf.ratchet.baseline` version
`1.0.0` and contains versioned rule coordinates. UCF evaluates already
produced violation records; BRN-003 does not add an expression language or
embed language, build-tool, source-path, framework, or transport semantics in
the core.

An assessment binds:

- the exact policy and onboarding-bundle digests;
- the assessor producer, versioned procedure, environment, and capture time;
- complete or partial subject and per-rule coverage;
- stable behavior subjects scoped by repository subject URI, root kind, and
  root ID;
- separate versioned semantic and observed fingerprints;
- exact trace coordinates for the bundle, behavior reference, inventory
  revision, candidate, and human decision;
- stable violation keys made from rule coordinate, subject, and finding slot.

Message text is not violation identity. Semantic fingerprints cover the
resolved non-provenance behavior closure. Observed fingerprints cover resolved
local evidence semantics and confidence while excluding path-only and
revision-only churn. Exact paths, revisions, candidates, and decisions remain
in trace; they are not discarded to obtain rename neutrality.

## Evaluation semantics

An accepted initial baseline records the current subject snapshots and current
violations as explicit legacy allowances. Evaluation is pure and recomputable:
it never edits that baseline.

Classification precedence is closed:

1. a present protected violation is `reintroduced` and fails;
2. a present violation absent from allowances is `new_regression` and fails;
3. an allowed violation on a semantically or observationally changed subject
   is `touched_legacy` and fails;
4. an allowed violation on an unchanged subject is `unchanged_legacy` and
   passes;
5. an allowed violation absent under complete subject and rule coverage is
   `resolved`;
6. missing evidence under partial coverage is `unknown`, never an
   improvement.

Any partial subject or rule coverage makes an otherwise non-regressing
evaluation `inconclusive`, including when every previously allowed violation
that was observed still appears unchanged. A definitely observed new,
reintroduced, or touched violation remains a failing regression even when
other coverage is partial.

A valid regression report includes a reviewable weakening delta naming the
exact added allowance or removed protection that a weaker baseline would
require. UCF exposes that data but never accepts weakening. There is no reset
or accept-regressions command.

`advance` accepts only an exact complete passing report. It creates a new
baseline with generation `n + 1`, exact predecessor and evaluation references,
retained unchanged allowances, and every resolved allowance moved to the
protected set. It cannot add an allowance, remove a protection, change policy,
or mutate its predecessor. Protected tombstones may refer to a behavior
subject no longer present in the current revision so later reintroduction
still fails.

## Author an assessment

Rule execution remains outside this comparison core. A caller or adapter-owned
assessor uses the installed `ucf.ratchet` API to construct:

- `RatchetPolicy` and content-derived policy ID;
- `ViolationInput` values over `BehaviorSubjectKey`;
- `build_ratchet_assessment(...)`;
- `canonical_ratchet_json(...)`.

The builder derives subject snapshots from an exact validated
`OnboardingBundle`, resolves every accepted/edited materialization and local
evidence reference, checks coverage and violations, and derives the assessment
identity. The executable examples are under `tests/ratchet/`.

## Installed transaction

Keep all ratchet documents outside the inspected legacy project. Establish the
first accepted baseline:

```text
ucf ratchet establish \
  --policy POLICY.json \
  --onboarding-bundle ONBOARDING_BUNDLE.json \
  --assessment INITIAL_ASSESSMENT.json \
  --output BASELINE.json
```

Evaluate a current assessment without changing the baseline:

```text
ucf ratchet evaluate \
  --policy POLICY.json \
  --onboarding-bundle CURRENT_ONBOARDING_BUNDLE.json \
  --baseline BASELINE.json \
  --assessment CURRENT_ASSESSMENT.json \
  --output REPORT.json
```

Explicitly advance through the exact passing report:

```text
ucf ratchet advance \
  --policy POLICY.json \
  --onboarding-bundle CURRENT_ONBOARDING_BUNDLE.json \
  --baseline BASELINE.json \
  --assessment CURRENT_ASSESSMENT.json \
  --evaluation REPORT.json \
  --output NEXT_BASELINE.json
```

The transaction uses these exit classes:

- Exit `0`: establishment, a passing evaluation, or a successful advance.
- Exit `1`: a valid failing or inconclusive evaluation. `evaluate` first
  writes its complete canonical report; `advance` preserves its output.
- Exit `2`: command-line usage error handled by the CLI parser.
- Exit `3`: malformed, duplicate, incompatible, forged, stale, unsafe-path,
  I/O, or contextual validation failure. Existing output is preserved.

Every successful output is fully built and validated before one same-directory
atomic replacement. Output must name a regular non-symlink path with an
existing parent and must differ from every input. A command never rewrites its
policy, bundle, assessment, evaluation, or accepted-baseline input.

## Trust, security, and current limits

- The selected baseline file is a caller-controlled trust anchor. Hash-linked
  predecessors expose discontinuity, but a local chain cannot prove the
  authoritative baseline tip. Anchor the accepted digest in reviewed version
  control or CI policy.
- A weakening delta is review data, not an approval mechanism. BRN-003 has no
  signed approval, mutable baseline service, or hosted state.
- The file transaction assumes its existing output parent is not concurrently
  replaced by a hostile local process. It rejects path aliases, symbolic-link
  leaves, hard links to inputs, and non-file destinations, but it is not a
  sandbox against an actor that can mutate the parent directory during the
  command.
- Partial subject or rule coverage cannot establish or advance a baseline and
  cannot claim that missing debt was resolved.
- Fingerprint change selects touched behavior; tested/verified evidence
  staleness remains a separate later capability.
- The installed workflow is proven on one checked Python fixture. The core
  documents are language-neutral, but this evidence does not establish
  TypeScript, compiled-language, framework, or transport support.
- The workflow imports static onboarding evidence only. It does not capture
  runtime data, prove behavior execution, or grant a formal-verification
  claim.
- Ratchet outputs contain behavior names, evidence digests, producers, and
  trace coordinates. Handle them with the same confidentiality controls as
  the reviewed onboarding bundle.

## Reproducible evidence

```text
uv run --locked --extra dev pytest -q tests/ratchet --no-cov
uv run --locked --extra dev pytest -q tests/cli/test_ratchet.py --no-cov
uv run --locked --extra dev pytest -q \
  tests/automation/test_capability_claims.py \
  tests/automation/test_quality_gates.py --no-cov
uv run --locked python tools/package_contract.py
```

The package contract builds two byte-identical wheels, installs one outside
the checkout, verifies exactly four ratchet schema resources, runs all three
installed commands over the unchanged onboarding fixture, checks pass,
regression, tightening, reintroduction, malformed-input, and blocked-output
paths, reruns the fixture's native checks, and compares its complete manifest.
