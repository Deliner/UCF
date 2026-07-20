# Optional recorded runtime evidence

The canonical current support claim is
[docs/CAPABILITIES.md](CAPABILITIES.md), row CAP-206. This document describes
the exact experimental `1.0.0` boundary; it is not a live telemetry or broad
OpenTelemetry support claim.

## Scope and trust boundary

Runtime import is off by default and recorded-only. UCF starts no collector,
intercepts no traffic, and reads no recording until a caller explicitly runs
`ucf adapter import-runtime-evidence`. Recording-format semantics remain in an
external adapter. The Python core exchanges a language-neutral payload through
the existing adapter protocol and requires both capabilities:

- `org.ucf.adapter.verification` at a compatible version;
- `org.ucf.adapter.runtime-evidence` exactly `1.0.0`.

The adapter is a process running as the current OS user. It is not a sandbox:
UCF does not restrict its filesystem, network, process, or operating-system
authority. Only adapters and recordings trusted for that authority should be
invoked.

## Exact documents

The installed wheel contains four closed Draft 2020-12 schemas:

| Document | Schema URI |
|---|---|
| allowlist policy | `urn:ucf:runtime-evidence:policy:1.0.0` |
| environment identity | `urn:ucf:runtime-evidence:environment:1.0.0` |
| import request | `urn:ucf:adapter:runtime-evidence-request:1.0.0` |
| accepted/rejected result | `urn:ucf:adapter:runtime-evidence-result:1.0.0` |

The request procedure is fixed at
`urn:ucf:runtime-evidence:recorded-import:1.0.0`. It binds the canonical
Behavior IR digest, recording digest and capture time, exact environment
document and digest, partial sampling procedure, policy, capability, and
expected adapter procedure. The result echoes that exact request and adds the
initialized adapter producer. Unknown fields, incompatible versions,
duplicates, non-canonical order, broken references, forged summaries or
identities, unsupported values, and missing capabilities are errors.

An accepted result names only policy rule references. The rule owns the exact
Behavior observation subject and assertion, so an adapter cannot smuggle a
new claim or arbitrary value through an observation result. A rejected result
contains only sorted closed reason codes.

## Command

The complete invocation is:

```text
ucf adapter import-runtime-evidence \
  --recording recording.json \
  --policy policy.json \
  --environment environment.json \
  --behavior-ir behavior.json \
  --source-uri urn:example:runtime-recording:revision-1 \
  --captured-at 2026-07-19T08:30:00Z \
  --sampling-procedure-uri urn:example:sampling:recorded-partial:1.0.0 \
  --adapter-procedure-uri urn:example:adapter:runtime-import:1.0.0 \
  --adapter-cwd /path/to/adapter-workdir \
  --output runtime-evidence.json \
  --operation-timeout 30 \
  -- adapter-executable adapter-arguments
```

The `--` separator is required before adapter argv. Success emits no console
output and atomically replaces `--output` only after complete validation.
Inputs must be bounded non-symbolic-link regular files and remain unchanged
through the transaction. Output aliases to inputs, malformed peers, stderr,
timeouts, cancellation, and input mutation preserve an existing output and
leave no UCF temporary file.

- Exit `0`: a canonical accepted authoritative result was written.
- Exit `1`: the adapter returned a valid typed policy rejection; no result was
  written.
- Exit `3`: local input, protocol, adapter, process, timeout, or output
  validation failed; diagnostics contain only local category/code values.

## Privacy and sampling

The `1.0.0` policy is an explicit allowlist. Selected secret or personal-data
categories are rejected, unselected attributes are omitted, and raw retention
is `none`. In the checked fixture workflow, UCF does not retain, persist, or
emit the forbidden fixture bytes in canonical output, diagnostics, retained
stderr, logs, or wheel assets. Adapter stderr is drained but not retained for
this command, and any stderr byte invalidates the result.

This is a precise tested boundary, not automatic data-loss prevention. UCF
does not universally detect secrets or personal data, anonymize arbitrary
values, or validate every recording format. Policy authorship and adapter
selection are part of the trust boundary, and raw bytes necessarily reach the
external adapter and may exist transiently in operating-system pipes or
process memory.

Sampling is always represented as partial sampling with an unknown total.
Missing observations therefore provide no evidence of absence, complete
coverage, or unchanged behavior.

## Evidence level and authenticity

The runtime result is authoritative for import scope. A separate pure
projection creates exactly a Trust IR `SourceRecord` plus one `ObservedFact`
per accepted rule. The projection is observed only: it creates no declared,
mapped, tested, or verified claim, no intent mutation, no ratchet allowance,
and no completeness inference.

Source revisions, environment digests, producer versions, and procedure URIs
provide traceability, not authenticity. BRN-004 does not sign recordings,
attest adapter binaries, or prove that a producer told the truth.

## Measured support and verification

Current evidence covers one bounded synthetic recorded trace and one external
fixture adapter. It does not establish live collection, a collector/exporter,
arbitrary OpenTelemetry compatibility, hostile-adapter isolation, ecosystem
support, or production operations.

Run:

```text
uv run --locked --extra dev pytest -q \
  tests/runtime_evidence \
  tests/cli/test_runtime_evidence.py \
  tests/adapters/test_process_runner.py --no-cov
uv run --locked python tools/package_contract.py
```

The package contract builds byte-identical wheels, installs one into a clean
environment, keeps the recording and adapter external, repeats the import
under two `PYTHONHASHSEED` values, checks observed-only projection, exercises
typed rejection, and scans decompressed wheel members for the forbidden
fixture values.
