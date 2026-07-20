# UCF Go standard-library adapter

This adapter is the experimental compiled-ecosystem proof selected by ECO-002
and implements the exact CLI/event platform proof for ECO-003. It is a
separately built out-of-process Go executable and communicates with the Python
control plane only through the LF-delimited adapter protocol `1.0.0`. The
canonical status and limitations are in
[`docs/CAPABILITIES.md`](../../docs/CAPABILITIES.md).

## Evidence-backed boundary

The HTTP profile covers one unchanged six-file legacy fixture:

- `.gitignore`;
- `README.md`;
- `go.mod`;
- `cmd/server/main.go`;
- `quote/service.go`;
- `quote/service_test.go`.

Both the adapter and HTTP fixture declare Go directive 1.26.0 and
`toolchain go1.26.5`. Qualification uses exactly go1.26.5 on Linux/amd64 with
`GOAMD64=v1` and `CGO_ENABLED=0`. The fixture uses standard-library `net/http`
and a literal route on the `ServeMux` returned by its `Handler` function.

The separate platform profile covers one unchanged nine-file fixture:

- `.gitignore`;
- `README.md`;
- `go.mod`;
- `cmd/platform/main.go`;
- `cmd/platform/main_test.go`;
- `quote/service.go`;
- `quote/service_test.go`;
- `spool/spool.go`;
- `spool/spool_test.go`.

That fixture has the same Go/toolchain/runtime coordinates and zero external
Go modules. Its frozen source-manifest SHA-256 is
`7b563b0296cb40498b984edc1ea3eb96b9fb8e96c8225aa695bc50b8b0889d2d`;
two clean builds of `./cmd/platform` are byte-identical at SHA-256
`f54ab3d5dfc50b5bf57610da6ec081aa3b4f700a71064fdaf041ebc56ac7cff4`.

The adapter passes protocol and public conformance profile 1.0.0 in explicit
`--conformance` mode. Its normal HTTP product mode uses
`--fixture-executable`; the exact platform mode uses
`--platform-fixture-executable`. Against an external copy of the unchanged
HTTP fixture it requires `org.ucf.platform.http-loopback@1.0.0` for the HTTP
procedure and produces:

- exactly 51 inventory records;
- four deterministic candidates;
- an explicit review with one accepted, two rejected, and one uncertain
  decision;
- one exact `use-case.quote-order` implementation mapping,
  `mapping.1ac553e103d8a887e1fa971788cf6f32784ba81265498de5474353313f3274c6`,
  bound to ten source records;
- one bounded loopback `POST /quote-order` check with fixed inputs.

Against the platform fixture it negotiates exact
`org.ucf.platform.cli-process@1.0.0` and
`org.ucf.platform.file-spool-event@1.0.0` capabilities, inventories 14 exact
filesystem entries, emits one quote-order candidate, requires explicit review,
and uses one neutral mapping for both procedures. CLI verification crosses one
real process boundary. Event verification uses four separate bounded processes
for enqueue, unavailable observation, dispatch, and final correlated
observation against a temporary external spool; the producer exits before
dispatch begins.

Only a passed check can create exactly one tested claim. Failed, error,
cancelled, stale, or mismatched results create no claim. The evidence remains
adapter-attested, and this adapter never creates a `verified` claim.
Inventory and discovery retain record-level provenance and confidence;
provenance can include source paths, symbols, half-open spans, and content
digests. Mapping and verification remain tied to the exact source revision,
adapter version, execution environment, and procedure coordinates.
Generation is unsupported in normal product mode.

## Trust, security, and privacy boundary

The executable and fixture binary are checked by digest and exact Go build
information before verification. Each run executes a private attested
executable snapshot and rechecks the original path afterward, so a path swap
cannot substitute unbound bytes. Process cleanup uses an overall deadline,
process groups, a Linux child subreaper, PID/start-time identities, and
TERM-to-KILL escalation; it does not return successful or cancelled evidence
while a tracked adapter-owned descendant remains. Those checks reject a
changed binary or unsupported build coordinate; digests provide traceability,
not signing or publisher authenticity. The resulting evidence is
adapter-attested, not independent attestation or formal verification.

The adapter and fixture processes run with the current user authority and no
sandbox. The HTTP procedure binds an ephemeral IPv4 loopback listener, but
loopback confinement does not constrain filesystem or process access. The
platform procedure declares disabled network use but is not a kernel network
sandbox. Descendant cleanup is not isolation from a malicious same-UID process,
an independently launched external daemon, or an unkillable kernel D-state
task. Use only adapters and fixture binaries that the caller trusts.

UCF does not universally discover, redact, or anonymize secrets or personal
data in paths, symbols, spans, source content, diagnostics, or returned
evidence. The checked fixtures contain synthetic data; that is not a general
secret or PII safety claim.

## Unsupported breadth

This is not broad Go, router, shell, broker, compiled-ecosystem, platform, or
production support. HTTP recognition is limited to the literal returned
`ServeMux` and the fixed quote-order procedure. CLI support is one exact
argument/output/exit contract. Event support is one local file-spool
enqueue/dispatch/observe procedure; it does not claim broker ordering,
durability, delivery, exactly-once behavior, hostile concurrent dispatch, or
crash recovery. The proof does not cover cgo, Windows, other architectures,
other Go toolchains, build tags, workspaces, monorepos, generated routes,
dynamic routes, custom routing, other frameworks, or arbitrary applications.
Broader CAP-209 platform breadth and CAP-214 release acceptance remain
unproven.

The exact pin is the qualification boundary. Any change to the Go directive,
toolchain, operating system, architecture, build flags, adapter, fixture,
capability, or procedure coordinates requires requalification. There is no
supported version range, SLA, compatibility window, support term, or
deprecation promise.

## Distribution and licensing

The adapter is reproducibly built as a standalone distribution outside the
Python wheel. Both fixture binaries are separately reproduced only as external
verification artifacts; no Go source or Go binary is a wheel payload. All
three modules have zero external Go modules. That statement does not mean the
static binaries contain only UCF-authored code: they include the Go runtime,
standard library, and GOROOT-vendored code. The adapter distribution therefore
carries the exact upstream Go `LICENSE` and `PATENTS` files under
`third_party/go/`.

Those upstream notices cover the bundled Go implementation components only.
Project-wide licensing remains a REL-002 decision, so this proof makes no
general claim that UCF as a whole is redistributable.

## Reproducible evidence

```bash
uv run --locked --extra dev pytest -q \
  tests/ecosystems/test_go_stdlib_fixture.py \
  tests/ecosystems/test_go_stdlib_harness.py \
  tests/ecosystems/test_go_stdlib_conformance.py \
  tests/ecosystems/test_go_stdlib_inventory.py \
  tests/ecosystems/test_go_stdlib_discovery.py \
  tests/ecosystems/test_go_stdlib_reconciliation.py \
  tests/ecosystems/test_go_stdlib_mapping.py \
  tests/ecosystems/test_go_stdlib_verification.py \
  tests/ecosystems/test_platform_neutrality.py \
  tests/ecosystems/test_go_stdlib_platform_fixture.py \
  tests/ecosystems/test_go_stdlib_platform_adapter.py \
  --no-cov
uv run --locked python tools/package_contract.py
```
