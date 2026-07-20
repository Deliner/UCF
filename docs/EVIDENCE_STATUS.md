# Verification evidence status 1.0.0

UCF can preserve one exact passed execution-verification result and later
recompute whether that evidence is `fresh`, selectively `stale`, or
`indeterminate` because current context was not supplied. This is an
experimental traceability contract, not formal verification.

The two closed JSON resources are:

- `urn:ucf:evidence-status:envelope:1.0.0`
- `urn:ucf:evidence-status:assessment:1.0.0`

Their checked schemas are packaged under
`ucf/schemas/evidence_status/v1/`. Strict decoding rejects duplicate JSON
members, unknown fields, wrong versions or kinds, malformed content IDs,
broken references, noncanonical order, and unsupported or unselected
capabilities.

## Record an exact result

`ucf evidence record` consumes artifacts already produced and reviewed by the
caller:

```text
ucf evidence record \
  --result execution-result.json \
  --mapping-result mapping-result.json \
  --onboarding-bundle onboarding-bundle.json \
  --inventory current-inventory.json \
  --mapping-adapter-name org.example.mapping \
  --mapping-adapter-version 1.0.0 \
  --verification-adapter-name org.example.verification \
  --verification-adapter-version 1.0.0 \
  --mapping-capability-version 1.0.0 \
  --verification-capability-version 1.0.0 \
  --output verification-envelope.json
```

Recording accepts only an exact `completed` and `passed` verification result
whose request, implementation mapping, onboarding bundle, inventory, adapter
identities, and negotiated capability versions validate together. The
envelope binds the tested Trust claim emitted by that exact verification
projection, but it does not create a `verified` claim.

Publication is create-only. A same-byte retry, including an identical
concurrent winner, is idempotent and keeps the existing file. Different
existing or concurrently created content, aliases to an input, symbolic or
additional hard links, and source drift are rejected.
The command writes a fully flushed same-directory temporary file and commits
with an atomic no-replace operation, then flushes the parent directory. This
is a current-user filesystem boundary, not protection from arbitrary hostile
same-UID mutation before or after the command.

## Assess recorded versus current context

`ucf evidence assess` always receives the original recorded coordinates:

```text
ucf evidence assess \
  --envelope verification-envelope.json \
  --recorded-result execution-result.json \
  --recorded-mapping-result mapping-result.json \
  --recorded-onboarding-bundle onboarding-bundle.json \
  --recorded-inventory current-inventory.json \
  --recorded-mapping-adapter-name org.example.mapping \
  --recorded-mapping-adapter-version 1.0.0 \
  --recorded-verification-adapter-name org.example.verification \
  --recorded-verification-adapter-version 1.0.0 \
  --recorded-mapping-capability-version 1.0.0 \
  --recorded-verification-capability-version 1.0.0 \
  --output assessment.json
```

Omitting every `--current-*` option produces `indeterminate` with
`current_context_unavailable`. To compare current state, the corresponding
`--current-result`, `--current-mapping-result`,
`--current-onboarding-bundle`, `--current-inventory`, adapter-name,
adapter-version, and capability-version options are an all-or-none group.
Supplying only part of that group is invalid.

The result and process exit are:

- `fresh`, with no reasons: exit `0`;
- `stale`, with exact recorded/current coordinate digests: exit `1`;
- `indeterminate`, when all current context is omitted: exit `1`;
- invalid input, incomplete context, unsupported capability, unsafe output, or
  publication failure: exit `3`.

Assessment first reconstructs the original envelope from the recorded
artifacts, so replay against different historical context fails. It then
validates the complete current result and compares four deterministic
projections:

- behavior subject and exact Behavior IR members;
- source revision, inventory, onboarding, and source bindings;
- implementation mapping and mapped targets;
- request inputs, expected outputs, check, environment, adapter, capability,
  procedure, and result coordinates.

Only changed coordinates appear as reasons. This selective invalidation keeps
unrelated evidence usable while naming the exact stale dimension. Historical
stale evidence is retained; assessment never rewrites or deletes its envelope.
A refresh is explicit: run the real check again, record its new passed result
into a new envelope, and assess that new immutable envelope.

## Trust, security, and current limits

The caller supplies all artifacts and producer names. UCF validates their
internal identities and relationships but does not execute an adapter, build,
test, or check in these two commands. It provides no authentication, signing,
authorization, transparency ledger, independent attestation, exhaustive
procedure, or formal proof. Content digests provide traceability, not
authenticity.

Current end-to-end evidence covers one bounded fixture/profile, Linux with a
local POSIX filesystem, and the exact 1.0.0 contracts. It does not claim
Windows, network filesystems, arbitrary ecosystems, distributed storage,
multi-user coordination, hostile-process isolation, or stable support. A
`tested` basis remains scoped to its exact reproducible check; `verified`
remains unavailable.

The canonical bounded capability claim and commands are in
`docs/CAPABILITIES.md`.
