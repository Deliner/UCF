# UCF adapter protocol 1.0.0

UCF's external-adapter boundary is an experimental, exact-version protocol and
installed conformance profile. The protocol proof and public kit exercise
capability negotiation, five operation families, correlation, cancellation,
bounded failures, and shutdown across separately launched processes. This is
serialized protocol evidence, not ecosystem, framework, brownfield, or
production adapter support. See
[ADAPTER_CONFORMANCE.md](ADAPTER_CONFORMANCE.md) for the public command and
profile; exact claims remain governed by `docs/CAPABILITIES.md`.

The Python control plane never imports the reference adapter. It knows only an
argument vector, an explicit working directory/environment, and the serialized
contract described here. Language, framework, build-tool, and runtime
semantics belong in adapter payload schemas and adapter processes, not in this
package.

## Wire profile

The selected binding is a strict subset of
[JSON-RPC 2.0](https://www.jsonrpc.org/specification) over stdin/stdout:

- one UTF-8 JSON object per LF-terminated frame;
- exact `"jsonrpc": "2.0"`;
- bounded nonempty ASCII string request IDs;
- object-only, closed `params`, `result`, and `error` shapes;
- exactly one of `result` or `error`;
- no batch, numeric/null request IDs, array params, server-to-client requests,
  arbitrary notifications, ignored fields, or stdout logs.

JSON-RPC supplies envelope correlation and its standard parse/request/method/
params error codes. LF framing, protocol `1.0.0`, finite limits, and
`ucf.cancel` are UCF contracts. Cancellation is not claimed as part of
JSON-RPC itself; the
[Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
is precedent for a versioned JSON-RPC cancellation extension.

The packaged Draft 2020-12 structural schema is
`src/ucf/schemas/adapter_protocol/v1/schema.json`. The runtime additionally
enforces framing, raw JSON, method/params agreement, lifecycle, capability,
correlation, error-coordinate, and embedded-IR semantics named in
`x-ucf-runtime-semantic-checks`.

## Methods and capabilities

| Method | Role | Required selected capability |
| --- | --- | --- |
| `ucf.initialize` | request/result, exactly once in `new` | none |
| `ucf.inventory` | request/result | `org.ucf.adapter.inventory` |
| `ucf.discover` | request/result | `org.ucf.adapter.discovery` |
| `ucf.map` | request/result | `org.ucf.adapter.mapping` |
| `ucf.generate` | request/result | `org.ucf.adapter.generation` |
| `ucf.verify` | request/result | `org.ucf.adapter.verification` |
| `ucf.cancel` | notification targeting one active operation ID | none |
| `ucf.shutdown` | request/result with no pending operations | none |

Initialization requests name the exact adapter protocol version, the client
producer identity/version, and unique capability requirements with qualified
name, minimum normalized version, and required/optional status. Results name
the adapter producer and a unique selected subset. Required missing or too-old
capabilities fail initialization; unsupported optional capabilities are
omitted. Only the immutable selected set gates operations.

Additional qualified semantic capabilities can be negotiated without teaching
the core their language or framework meaning. Protocol version, adapter
implementation version, capability version, payload schema version, Behavior
IR version, and Trust IR version are independent coordinates.

## Operation payloads

Every operation uses a matching `<operation>_request` or
`<operation>_result` discriminator around one of:

1. a complete Behavior IR `1.0.0` document;
2. a complete Trust IR `1.0.0` document;
3. an `adapter_payload` with an independent `schema_uri`,
   `schema_version`, and tagged language-neutral `IRValue`.

Behavior/Trust payloads run their accepted internal semantic validators, not
only nested structural validation. Adapter payload values reject duplicate
record entries and retain the IR's exact cross-runtime number/value profile.
Cross-document Trust-to-Behavior binding still requires both documents and its
existing validator; crossing the RPC boundary never establishes or promotes a
claim.

The first published operation-specific adapter payload is the observed
inventory profile `1.0.0`. Its exact request/page/snapshot resources,
deterministic paging, installed `ucf adapter inventory` command, and read/privacy
boundary are specified in [INVENTORY.md](INVENTORY.md). That fixture evidence
does not broaden the generic protocol into an ecosystem support claim.

The generation profile is another independent `adapter_payload` contract. Its
exact request/result `1.0.0` resources, external Python/pytest backend,
generated-only publication transaction, installed `ucf generation run`
command, and evidence boundary are specified in
[GENERATION.md](GENERATION.md). The core transports and validates neutral
content; it does not import the backend or interpret pytest semantics.

## Lifecycle and cancellation

The server dispatcher has the transport-independent lifecycle
`new -> ready -> closed`. Initialization is exact and atomic. Operations are
registered before their handler runs, so the reader can continue accepting
other requests and targeted cancellation. A reused lifetime ID, 65th
concurrent request, exhausted session budget, operation before initialization,
unselected capability, or shutdown with pending work fails before adapter
semantics run.

`ucf.cancel` is an idempotent notification and has no response of its own. An
active handler observes a read-only cancellation signal; the original request receives
the terminal `cancelled/request_cancelled` error. Unknown or completed targets
are no-ops. A valid result may win a cancellation race, but two terminal
responses or an unknown response ID fail the whole session.

The subprocess client uses one stdout reader, one serialized writer, and a
separate chunk-based stderr drainer. Pending requests are installed before
write, futures are shielded from timeout cancellation, and result kinds must
match their originating methods. A timeout sends targeted cancellation and
then terminates the session if the bounded grace expires; every other waiter
receives a process failure.

Cancelling the Python coroutine that owns start, close, or a one-shot call
does not abandon process ownership or correlation state. Startup and shutdown
finish bounded teardown before re-raising cancellation. A cancelled operation
sends its targeted protocol cancellation; an uncooperative adapter is
terminated before control returns.

## Stable errors

`error.data.category` and `error.data.ucf_code` are normative. English
messages are bounded diagnostics. The JSON-RPC numeric code must agree with
the symbolic code, and every symbolic code has exactly one category:

- `protocol_failure`: parse, message/params/method, version, lifecycle,
  capability, ID, frame, and correlation failures;
- `adapter_failure`: handler operation/internal failures;
- `cancelled`: the original request's cancellation outcome;
- local-only `timeout`: initialize, operation, write, cancel, or shutdown
  deadline;
- local-only `process_failure`: start, EOF/exit, I/O, invalid output, or
  termination failure.

An adapter response with a mismatched category/code pair, a local-only
timeout/process category, or a cancellation outcome for a request the client
did not cancel is invalid output. Stderr text, tracebacks, environment
contents, and command details never become wire errors or successful results.

## Resource and process limits

| Resource | Protocol/client limit |
| --- | ---: |
| Frame including LF | 1,048,576 bytes |
| JSON nesting | 128 |
| Exact JSON integer | `[-9007199254740991, 9007199254740991]` |
| Request ID | 1–64 ASCII bytes, lifetime-unique per client |
| Concurrent pending requests | 64 |
| Accepted requests per process | 65,536, including initialize and shutdown |
| Retained stderr tail | 65,536 bytes; total count saturates safely |
| Initialize / default operation | 5 s / 30 s |
| Write / cancellation / shutdown | 5 s / 1 s / 2 s |
| TERM / KILL-and-reap grace | 1 s / 1 s |
| Peer error message | 1,024 Unicode scalar values |

Tests may inject shorter positive bounds. The final accepted request slot is
reserved for `ucf.shutdown`; a client that receives
`session_request_limit` starts a new adapter process rather than weakening the
bound. Configured deadlines, retained capture, pending requests, and
lifetime-ID history are finite. The standalone server has one daemon stdin
owner with a one-frame handoff, so a broken output task can terminate the
event loop even while the peer keeps stdin open.

The client launches with `shell=False`, an explicit working directory, a
small environment allowlist, closed unrelated descriptors, and a new POSIX
session. On POSIX, teardown signals the dedicated process group and awaits the
direct child; inherited-grandchild fixtures prove group cleanup both before
and after an early leader exit.

## Security boundary and limitations

Out-of-process is protocol and failure isolation, not privilege isolation. An
adapter running as the current OS user can access that user's files and
network and can deliberately escape a process group. Capability declarations
are self-reported, not implementation proof. The conformance command accepts
arbitrary argv for explicit user-directed testing, but does not advertise that
execution as safe.

OS sandbox/container policy, CPU/memory/fd quotas, detached-descendant
handling, Windows Job Object parity, adapter artifact provenance/signing, and
diagnostic privacy/retention are release work. The retained stderr tail can
contain text emitted by the adapter and must be handled as diagnostic data.
The standalone server relies on ordinary pipe backpressure while stdout has a
reader; the supported process client drains stdout continuously and enforces
deadlines, but the server is not a general quota or hostile-peer isolation
layer.

## Reproducible evidence

The exact reference transcript is
`tests/fixtures/adapters/protocol/v1/reference-transcript.json`. Regenerate or
check the schema with:

```bash
uv run --locked python tools/generate_adapter_protocol_schema.py
uv run --locked python tools/generate_adapter_protocol_schema.py --check
```

Run the ADP-001 contract with:

```bash
uv run --locked --extra dev pytest -q tests/adapters --no-cov
```

The installed ADP-002 command, dependency-free sample, digest-indexed assets,
and intentionally faulty modes are documented in
[ADAPTER_CONFORMANCE.md](ADAPTER_CONFORMANCE.md). The transcript above remains
repository evidence rather than a packaged asset. Exact current claims and
owners remain in [CAPABILITIES.md](CAPABILITIES.md).
