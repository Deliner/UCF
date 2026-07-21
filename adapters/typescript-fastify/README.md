# UCF TypeScript/Fastify adapter

This independently built Node 22 process implements the UCF adapter protocol
`1.0.0` control surface and the inventory `1.0.0` request/page profile for the
checked TypeScript 7.0.2, Fastify 5.10.0, Node 22.22.3, and npm 10.9.8
legacy-quote fixture on Linux/x64. It passes the public conformance profile by
negotiating all five standard operation families.

Inventory, static discovery, reviewed quote-order implementation mapping, and
one real quote-order execution check have narrow non-control implementations
in this package. Generation remains a conformance control surface; a
non-control generation payload is rejected with `operation_failed`. None of
these operations is a claim that this package broadly discovers, maps,
generates, or verifies TypeScript, Fastify, or user implementation code.

Inventory is read-only, deterministic, paginated, and deliberately narrow. It
uses non-following symlink handling, portable path identities, exact manifest
and source classifiers, provenance with half-open source spans, bounded
resources and frames, and a cancellable worker thread. An unsupported layout,
unsafe path, stale cursor, filesystem failure, or classification failure is an
explicit operation failure with no raw exception written to stderr. A single
completed snapshot is retained for cursor continuation; cancellation cannot
publish a partial snapshot.

Discovery accepts only the exact completed snapshot retained by the same
adapter session. It emits deterministic, language-neutral candidate proposals
for the four classified exported business functions in the checked fixture,
keeps `buildApp` and the literal Fastify route explicitly uncovered, and labels
all candidates as inferred evidence rather than verified behavior. A rebound,
changed, malformed, or noncanonical inventory is rejected without a partial
result.

Mapping accepts an independently reviewed, language-neutral implementation
mapping request only after a completed current inventory in the same adapter
session. It binds the reviewed `use-case.quote-order` root to the exact three
build-manifest facts, exported `quoteOrder` interface, and literal Fastify
route used as its discovery evidence. The content-identified result echoes the
request and carries no Trust claim or claim promotion. Bundle/candidate review
context remains validated by UCF core; the adapter neither hard-codes a
reviewer-specific bundle digest nor treats the binding as verified behavior.

Verification requires the exact successful mapping retained by the current
session and the fixed checked inputs `quantity=2` and
`unit-price-cents=1250`. It loads only the regular, non-symlinked
`<cwd>/dist/service.js`, calls its exported `buildApp`, listens on an
ephemeral IPv4 loopback port, and uses Node's built-in `fetch` for the fixed
`POST /quote-order` procedure. Execution and response reads are bounded and
run in a cancellable worker. The application is closed and the worker is
reaped before the adapter publishes a minimal `passed`, `failed`, or `error`
result. Only `passed` may be projected by UCF to a `tested` claim; the adapter
does not produce `mapped` or `verified` claims. This is adapter-attested
evidence for the exact Node 22.22.3/Linux/x64 loopback fixture and procedure.
It is not independent attestation or formal verification.
This is not general Fastify support.

The checked runtime has no third-party dependencies. TypeScript `7.0.2` and
Node declarations `22.20.1` are exact build-only development dependencies.
The standalone private npm tarball declares `Apache-2.0` and carries the root
UCF `LICENSE` and `NOTICE`; those terms cover UCF project code and do not
relicense Node.js, build dependencies, generated output, or inspected legacy
projects.
The canonical status and limitation claim is
[`docs/CAPABILITIES.md`](../../docs/CAPABILITIES.md).

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm test
uv run --locked --extra dev ucf adapter conformance --cwd . \
  -- node dist/main.js
```
