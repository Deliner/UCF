# UCF adapter conformance kit 1.0.0

The experimental UCF conformance kit judges an adapter only at its serialized
process boundary. Kit version `1.0.0`, adapter protocol version `1.0.0`,
profile `org.ucf.adapter-conformance.full`, and control payload schema
`urn:ucf:adapter-conformance:control:1.0.0` are independent exact
coordinates. This release implies no version range or forward compatibility.
The canonical claim and limitation matrix remains
`docs/CAPABILITIES.md`.

## Installed commands

Inspect the canonical asset index or extract the complete immutable kit:

```bash
ucf adapter kit
ucf adapter kit --extract ./ucf-adapter-kit
```

Run a candidate argv directly, conventionally after `--`:

```bash
ucf adapter conformance --cwd /existing/workdir \
  -- /path/to/adapter [args...]
ucf adapter conformance --cwd /existing/workdir \
  --report ./report.json -- /path/to/adapter [args...]
```

`--cwd` is the candidate's launch directory, so relative executable resources
continue to work. Each case gets a fresh process and fresh `HOME`/temporary
scratch directory, but the launch directory remains visible and writable.
The candidate may run once per case and must not rely on process state from a
previous case.

Exit `0` means every case in this exact profile passed. Exit `1` means adapter
non-conformance and still produces a complete canonical report. Exit `3`
means runner, launch, configuration, or report-write failure. A process start
failure is represented by a `runner_error` report; a CLI validation or output
write failure is written to stderr when no report can be produced.

Without `--report`, stdout is exactly one canonical UTF-8 JSON report.
`--report PATH` atomically replaces that explicitly selected path and leaves
stdout empty. Reports omit argv, cwd, environment values, timing, PID, and raw
stderr. Repeating the packaged sample produces byte-identical reports; the
runner does not make an arbitrary nondeterministic adapter deterministic.

## Published contract

The wheel contains a closed manifest, 17 positive and negative wire
transcripts, a Draft 2020-12 schema, a dependency-free `.mjs` sample, seven
named faulty modes, and a digest/size index. `adapter kit --extract` accepts
only a missing or empty non-symlink directory and never merges with existing
user content.

`universal` cases cover negotiation, lifecycle, capabilities, request
identity, cancellation no-ops, parse/envelope/parameter errors, method
rejection, and shutdown. `control_profile` cases use the kit-owned opaque
payload solely to make all five operation families, target-derived readiness,
targeted cancellation, and pending shutdown reproducibly observable. That
payload is test fixture semantics, not a domain schema added to behavior IR.

The sample and existing Python reference process pass the same manifest.
Every published faulty mode fails only its manifest-named case. The installed
wheel contract extracts the kit outside the checkout, runs the sample twice,
compares exact reports, and runs every fault profile.

## Execution and security boundary

The candidate command runs with `shell=False`, but it runs as the current OS
user and this is not a sandbox. It retains that user's filesystem and network
authority and can have arbitrary side effects, including modifying the
declared launch directory. UCF supplies a small environment allowlist and
fresh scratch paths; it does not provide filesystem, network, syscall,
CPU, memory, file-descriptor, container, provenance, or signing isolation.

On POSIX, every case owns a new process group; bounded TERM/KILL cleanup is
tested for inherited descendants and stderr is drained with bounded retention.
A process that deliberately detaches can escape that group. Windows process
tree parity and native subprocess-pipe behavior are not established. Raw
stderr is untrusted diagnostic data and is excluded from canonical reports.

Passing proves only the exact serialized profile. It does not prove that an
adapter is safe, that self-declared semantics are true, or that it is
production-ready. The Node sample is cross-runtime protocol evidence, not
TypeScript or JavaScript ecosystem support. It is not framework support,
brownfield onboarding, HTTP/CLI/event behavior support, or a compiled-language
claim; those remain separate backlog outcomes.

## Reproducible source evidence

```bash
uv run --locked --extra dev pytest -q \
  tests/adapters/test_conformance_models.py \
  tests/adapters/test_conformance_resources.py \
  tests/adapters/test_conformance_schema.py \
  tests/adapters/test_conformance_runner.py \
  tests/cli/test_adapter_conformance.py --no-cov
uv run --locked python tools/package_contract.py
```

See [ADAPTER_PROTOCOL.md](ADAPTER_PROTOCOL.md) for the underlying wire
contract and [CAPABILITIES.md](CAPABILITIES.md) for the exact current claim.
