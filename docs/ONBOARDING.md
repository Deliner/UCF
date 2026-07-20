# Brownfield onboarding 1.0.0

This document describes UCF's experimental, evidence-backed Python brownfield
CLI vertical slice. It inventories one unchanged legacy fixture through an
external process, exports reviewable behavior candidates, accepts an exact
human decision document, and creates a self-contained non-enforcing baseline
bundle. The canonical support claim and its limits are in
`docs/CAPABILITIES.md`.

A separate private TypeScript/Fastify adapter reuses these neutral profiles in
one frozen-fixture packaging proof. Its exact versions, executable HTTP
evidence, and narrower support limits are documented in
`adapters/typescript-fastify/README.md`; it does not broaden the Python CLI
measurements below into general ecosystem support.

The separately built Go adapter also reuses the same neutral inventory,
candidate review, mapping, and execution-verification profiles for one frozen
Go/Linux platform fixture. It runs an exact CLI process and a local file-spool
enqueue/unavailable-observe/dispatch/observe sequence, and projects only
passed adapter-attested `tested` evidence. This is an installed-wheel
integration proof, not a new general onboarding CLI, shell abstraction, hosted
broker, or platform guarantee. Exact capabilities, procedures, process
containment, and limitations are documented in
`adapters/go-stdlib/README.md` and CAP-209.

This is not general Python or framework support. The measured adapter
recognizes four top-level functions in one checked Python fixture. It is not a
sandbox, it runs as the current OS user, and its read-only protocol intent
cannot prevent arbitrary adapter code from writing files or using the network.

## Exact profiles

The installed wheel publishes four closed Draft 2020-12 resources:

- discovery request:
  `urn:ucf:adapter:discovery-request:1.0.0`;
- discovery result:
  `urn:ucf:adapter:discovery-result:1.0.0`;
- human decision set:
  `urn:ucf:onboarding:decision-set:1.0.0`;
- self-contained bundle:
  `urn:ucf:onboarding:bundle:1.0.0`.

Discovery negotiates `org.ucf.adapter.discovery` version `1.0.0` together
with inventory `1.0.0`. The request embeds and hashes the complete assembled
inventory. The result carries the exact inventory binding, adapter producer,
versioned procedure, confidence, candidate proposals, diagnostics, and
complete or partial coverage. Unknown fields, duplicate identities,
non-canonical ordering, broken or wrong-kind references, incompatible
versions, and unsupported capabilities fail explicitly.

## 1. Export review material

Keep the policy and output outside the legacy root. Put `--` before the
adapter executable so adapter options cannot be mistaken for UCF options.

```text
ucf adapter discover ROOT \
  --policy POLICY.json \
  --output DISCOVERY.json \
  --subject-uri urn:example:repository:legacy-app \
  --page-record-limit 256 \
  --operation-timeout 30 \
  -- ADAPTER [ADAPTER_ARG...]
```

The command uses one external process for inventory and discovery and writes
one canonical `DiscoveryResult` by atomic replacement. Repeating it with the
same source, policy, subject, adapter, and procedure produces identical bytes.
It writes no UCF artifact below `ROOT`.

For source-location review, retain a canonical `ucf adapter inventory` output
and verify that its SHA-256 equals
`DiscoveryResult.inventory_binding.canonical_digest`. UCF deliberately does
not add an unversioned review envelope around those two exact documents.

## 2. Record human review

A human review produces one exact `DecisionSet`. It contains:

- the canonical discovery digest and exact inventory binding;
- an explicit reviewer and capture context;
- exactly one sorted `accepted`, `edited`, `rejected`, or `uncertain`
  decision for every current candidate;
- each candidate ID and semantic digest;
- a complete replacement proposal and digest for an edited candidate;
- a content-derived decision ID.

The installed `ucf.onboarding` API exports the decision models,
`canonical_onboarding_digest`, `derive_candidate_semantic_digest`,
`derive_decision_id`, `canonical_onboarding_json`, and
`validate_decision_set`. The executable authoring example is
`tests/onboarding/test_decisions.py`; the exact JSON grammar is the installed
decision-set schema.

Candidate confidence never decides a disposition. Candidates remain review
material and are not intent, declarations, mappings, tested evidence, or
verified claims. In short, a discovered candidate is not verified.

## 3. Freeze the first baseline

```text
ucf adapter onboard ROOT \
  --policy POLICY.json \
  --decisions DECISIONS.json \
  --output ONBOARDING_BUNDLE.json \
  --subject-uri urn:example:repository:legacy-app \
  --page-record-limit 256 \
  --operation-timeout 30 \
  -- ADAPTER [ADAPTER_ARG...]
```

`onboard` repeats inventory and discovery instead of trusting an old export.
It then requires the DecisionSet to match the new discovery digest, inventory
revision, producer/procedure context, candidate IDs, semantic digests,
replacement digests, and decision IDs. A stale, missing, duplicate, unknown,
or forged decision fails before output replacement.

Only accepted and edited candidates materialize into Behavior IR. Rejected and
uncertain candidates remain distinguishable in the bundle and baseline. Trust
IR contains only the independently supported `observed` and `declared` claims;
`mapped`, `tested`, and `verified` remain empty. Behavior-bound observations
trace the exact human reconciliation decision, which binds the underlying
discovery.

The resulting bundle embeds inventory, discovery, decisions, Behavior IR,
Trust IR, capture context, exact document digests, all four disposition
summaries, materializations, coverage, and claim-level summaries. Its parser
recomputes and validates the self-contained cross-document result.

## Safety, privacy, and current limits

- Both commands validate all inputs before their sole output replacement and
  preserve an existing output on adapter, stale-decision, or validation
  failure.
- Output must be outside the legacy root, must not be a symbolic link, and
  must differ from policy and decision inputs.
- Runtime capture is not part of this flow and remains off. Inventory and
  static discovery may still expose repository paths, interface names, and
  build metadata; review outputs using the same handling rules as source code.
- The adapter process is not a sandbox and runs as the current OS user.
  Execute only adapters you trust in an appropriately isolated environment.
- The embedded onboarding baseline does not enforce a ratchet. It records
  current accepted, edited, rejected, uncertain, and uncovered state without
  calling legacy debt verified. The separate exact comparison and immutable
  successor boundary is documented in `docs/RATCHET.md`.
- Evidence proves one checked Python fixture on the measured POSIX path. It
  does not establish framework breadth, hostile-adapter safety, Windows
  parity, runtime evidence, or production Python ecosystem support.

## Reproducible evidence

```text
uv run --locked --extra dev pytest -q tests/onboarding --no-cov
uv run --locked --extra dev pytest -q \
  tests/cli/test_adapter_discover.py \
  tests/cli/test_adapter_onboard.py --no-cov
uv run --locked python tools/package_contract.py
```

The package contract builds two identical wheels, installs one into a clean
external environment, copies the unchanged legacy fixture and dependency-free
adapter outside the checkout, repeats discovery and onboarding byte-for-byte,
replays stale and adapter-failure paths, reruns native behavior, and compares
the complete legacy manifest.
