# UCF observed inventory profile 1.0.0

UCF can collect a deterministic, observed-only repository inventory through
an external adapter. This is an experimental evidence-capture boundary, not a
complete brownfield onboarding claim. Exact current claims and limitations are
governed by `docs/CAPABILITIES.md`.

## Exact coordinates

The independently versioned contracts are:

- capability `org.ucf.adapter.inventory`, version `1.0.0`;
- request resource
  `urn:ucf:adapter:inventory-request:1.0.0`;
- bounded page resource `urn:ucf:adapter:inventory-page:1.0.0`;
- assembled snapshot resource `urn:ucf:schema:inventory:1.0.0`.

The three exact Draft 2020-12 resources are installed as
`schemas/inventory/v1/request.schema.json`,
`schemas/inventory/v1/page.schema.json`, and
`schemas/inventory/v1/schema.json`. Each resource accepts only its own document
kind and URI. The logical documents cross adapter protocol `1.0.0` inside its
neutral tagged `AdapterPayload`; the protocol is not changed by this profile.

Requests always name all five generic categories: repository entries, build
manifests, public interfaces, test assets, and available API descriptions.
Language, framework, build-tool, and runtime recognition remains adapter-owned.
The Python core validates the generic profile, page chain, references,
coverage, provenance, confidence, and content identities; it does not import a
scanner or adapter implementation.

Five versioned normative algorithms cover semantics that are partly or wholly
outside portable JSON Schema:

- `urn:ucf:inventory-algorithm:portable-path:1.0.0` requires Unicode NFC,
  relative POSIX separators, no traversal or empty segments, the published
  portable character/reserved-name rules, and ASCII case-folded path identity;
- `urn:ucf:inventory-algorithm:ignore-policy:1.0.0` requires rules in ascending
  ID order with unique IDs and unique matcher kind plus portable path identity;
- `urn:ucf:inventory-algorithm:cursor-coordinate:1.0.0` binds each record kind
  to its exact ID prefix and binds the cursor to the snapshot digest;
- `urn:ucf:inventory-algorithm:page-terminal:1.0.0` requires a null next cursor
  exactly for a complete page and a non-null advancing cursor otherwise;
- `urn:ucf:inventory-algorithm:source-span-order:1.0.0` compares
  `(end_line, end_column)` lexicographically with
  `(start_line, start_column)` and rejects an end coordinate that sorts before
  its start.

The schemas encode the expressible portions as patterns, exact tuple
`prefixItems`, uniqueness, and conditionals, including exact repository-entry
coordinate branches and the rule that a source span requires a content
digest, and name the same algorithms in `x-ucf-normative-algorithms`. Runtime
validation remains normative for NFC, sibling source-span ordering,
property-based uniqueness, cross-record references, content-derived identities,
and digest agreement.

Every emitted fact has level `observed`. An inventory snapshot contains no
declared intent and makes no `mapped`, `tested`, or `verified` claim. Empty
complete coverage is distinct from partial coverage. Read, enumeration,
classification, race, unsafe-path, collision, non-regular-entry, and resource
failures are explicit deterministic diagnostics rather than silent success.

## Installed command

The installed command writes canonical JSON only after every page has been
validated and assembled:

```console
ucf adapter inventory ./legacy-project \
  --policy ./inventory-policy.json \
  --output ../evidence/inventory.json \
  --subject-uri urn:example:repository:legacy-project \
  --page-record-limit 256 \
  --operation-timeout 30 \
  -- ./my-inventory-adapter --adapter-option
```

The exclusion policy is strict JSON. Rules are sorted by ID and are explicit;
there are no implicit `vendor`, generated, or tool-specific exclusions:

```json
{
  "kind": "ignore_policy",
  "policy_version": "1.0.0",
  "rules": [
    {
      "kind": "ignore_rule",
      "id": "ignore.generated",
      "reason": "org.example.inventory.generated",
      "matcher": {
        "kind": "path_segment",
        "segment": "generated"
      }
    }
  ]
}
```

The output parent must already exist and resolve outside the scanned root.
UCF stages the completed bytes beside the destination, flushes and fsyncs the
file, and atomically replaces the destination entry. A failed adapter,
timeout, invalid page, or incomplete assembly leaves an existing destination
unchanged. Exit `0` means a structurally and semantically valid complete or
explicitly partial snapshot was written. Configuration, adapter, protocol,
validation, and output failures exit `3`; command-line usage errors retain
Typer's exit `2`.

## Determinism and paging

Record IDs and source revision are SHA-256 digests of canonical semantic
coordinates. Capture time is deliberately absent. Unchanged input, adapter
version, and policy produce byte-identical canonical snapshots, including at
different legal page limits. A cursor binds the exact snapshot digest and last
record coordinate. Gaps, overlaps, mixed revisions, wrong profiles, premature
termination, broken references, and final digest mismatches fail without
returning a partial object.

Each protocol frame is at most 1,048,576 bytes. The reference adapter reduces
the number of logical records in a response when envelope encoding would
exceed that bound. The complete profile allows at most 65,534 pages and
records, leaving one initialize and one shutdown request inside the protocol
session budget.

## Read and process boundary

The checked reference fixture is a dependency-free external Python process
used to prove the profile. On POSIX it performs descriptor-relative,
non-following traversal, applies ignore rules before stat/open/descent, streams
regular-file hashes, never follows symbolic links, and does not open FIFOs or
sockets. It checks ordinary file and directory identity changes and marks a
non-atomic scan partial when a source changes. It also cooperatively observes
targeted cancellation so a timed-out session can remain correlated and be
closed normally.

These guarantees describe the checked reference fixture, not arbitrary
third-party adapters. An adapter command runs as the current OS user and is
not a sandbox. UCF does not remove its filesystem, network, process, or secret
access. The reference scan is read-only but is not an atomic filesystem
snapshot; a same-privilege writer can race checks, and a third-party adapter
can behave differently. Included paths, sizes, digests, interface/test names,
and diagnostics are evidence and may be sensitive. The caller owns policy,
output protection, adapter review, and any additional isolation.

The wheel installs the schemas and command but does not ship this test fixture
as a production ecosystem adapter. The reference classifier demonstrates only
the named generic fixture facts; it is not evidence of Python, TypeScript,
framework, compiled-language, or platform support.

## Deliberately deferred

BRN-001 ends at observed inventory. Candidate generation, import into trust
records, explicit reconciliation, and an unchanged Python onboarding flow
belong to BRN-002. Baseline and ratchet enforcement belongs to BRN-003.
Runtime capture, ecosystem support, transport behavior, and release claims
have their own dependency-ordered packages. No inventory record is promoted
merely because it was discovered.
