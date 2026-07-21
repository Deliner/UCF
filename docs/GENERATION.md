# UCF generation profile 1.0.0

This document defines the current experimental deterministic-generation
boundary. The canonical support claim and its limits remain
`docs/CAPABILITIES.md`, CAP-211. Generation renders an executable test
artifact; it does not prove that an application satisfies the behavior.

## Exact resources and capabilities

The language-neutral core accepts two closed, independently versioned
resources:

| Resource | Schema URI |
| --- | --- |
| `GenerationRequest` | `urn:ucf:generation:request:1.0.0` |
| `GenerationResult` | `urn:ucf:generation:result:1.0.0` |

The generic capability is `org.ucf.adapter.generation@1.0.0`. A request also
names a distinct exact profile capability and adapter procedure. The checked
backend selects
`org.ucf.adapter.generation.python-pytest@1.0.0` and
`urn:ucf:python-pytest:function-test:1.0.0`.

A request content-binds:

- the complete accepted Behavior IR `1.0.0` document and one action subject;
- every required input port and at least one expected output port;
- a declared environment identity and digest;
- the generic and profile capabilities, procedures, and canonical opaque
  profile configuration.

A complete result embeds the exact request, initialized producer coordinates,
selected capabilities, adapter procedure, a bounded canonical generated-file
manifest, and verification instructions. Every file has a portable relative
path, generator-only ownership, media type, UTF-8 content, byte size, and
SHA-256 digest. Unknown fields, duplicate JSON members, incompatible versions,
stale content IDs, broken action or port references, missing required values,
noncanonical values, unsupported capabilities, unsafe paths, case-folded path
collisions, file/directory ancestor collisions, and forged content fail
explicitly.

The environment coordinate is caller-declared input. Its digest is identity
binding, not an attestation that UCF measured the executing machine.

## Checked Python/pytest backend

`adapters/python-pytest/adapter.py` is an external adapter and is deliberately
absent from the Python wheel. Its exact configuration contains a dotted module
name, a function name, and a complete input-port-to-keyword mapping. It supports
one Behavior IR action, JSON-compatible concrete values, and one direct
expected output. It returns content only and performs no filesystem write.

The installed CLI can drive a separately obtained adapter:

```bash
ucf generation run request.json \
  --destination generated-contracts \
  --adapter-cwd . \
  --operation-timeout 5 \
  -- python3 -I -B -X utf8 /absolute/path/to/adapter.py
```

Success prints exactly `created`, `unchanged`, or `updated`. Any invalid input,
adapter/protocol failure, stale source, unsafe publication, or unsupported
platform uses exit `3`. A rejection before commit leaves an accepted prior
destination unchanged and never publishes a partial destination. Two explicit
post-commit errors are different: `committed_cleanup_failed` means the complete
new destination is visible and its exchange was flushed, but a possibly
partial residue of the prior tree remains under a uniquely named stage.
`committed_durability_unknown` means the complete new destination is visible
but a post-commit parent-directory flush failed. If the exchange flush fails,
cleanup has not begun and the complete prior tree remains under the stage
name; if only the final stage-removal flush fails, no residue may remain. A
caller receiving either code must inspect the canonical receipt and resolve
the named operational condition; UCF does not misreport the operation as an
unchanged pre-commit rejection. The request is read through a stable bounded
snapshot and is rechecked immediately before commit, including on an exact
no-op.

The command does not execute result-supplied argv. For this exact checked
backend, the result declares:

```text
python3 -B -m pytest -q {generated_root}
```

The clean-package contract installs only the wheel and `pytest==9.1.1`, copies
the external adapter and request into a workspace outside the checkout,
generates under Python hash seeds `1` and `777`, compares the complete trees,
runs the declared test, and repeats generation as an exact no-op. No
`pytest-cov` plugin is required.

## Ownership and publication

The destination is a generated-only tree. User implementation stays beside
it, outside generator ownership. First publication requires an absent
destination. An update requires a valid canonical
`.ucf-generation-result.json` receipt and a complete byte-exact prior tree.
An edited, missing, extra, symbolic, hard-linked, or non-regular entry is a
conflict; UCF never silently adopts or overwrites it.

Publication stages a complete tree on the destination filesystem, flushes its
files, revalidates the exact staged tree plus source, parent, and destination
identities, and commits with Linux `renameat2`. After an update, UCF
flushes the committed exchange before cleanup of the prior tree. A kernel-owned POSIX
advisory lock on the real parent directory serializes cooperating publishers
and is released automatically when its file descriptor or process closes.
Symbolic parent aliases and callback-time parent, stage-name, or staged-content
changes are rejected. Abort cleanup recursively removes the stage only after
the complete generated receipt and tree are revalidated; otherwise it leaves
the unrecognized stage content for inspection. Exact retry returns `unchanged`
only after the same source and destination revalidation.

This publication proof is Linux/POSIX-only. It is not a portable Windows or
macOS claim. The adapter and CLI run with the current OS user authority and
are not a sandbox. They do not isolate filesystem, process, network, CPU, or
memory access, and do not protect against a malicious same-UID process that
ignores advisory locking. A filesystem failure during pre-commit staging
cleanup is reported explicitly and may require removal of the uniquely named
uncommitted stage after identity inspection. After an update exchange, UCF
never attempts to roll a partially cleaned prior tree back over the complete
new tree; it reports `committed_cleanup_failed` and retains the residue for
inspection. That possibly partial residue must not be treated as a recoverable
intact prior tree. A post-commit parent flush failure is
`committed_durability_unknown`, not proof that the visible complete tree is
durable across a host crash.

## Evidence and Trust boundary

Generation binds declared intent and produces generator-owned content. It does
not execute application behavior, does not create verification evidence, and
does not create or promote any Trust claim. A later passed, revision-bound
verification procedure is required before a `tested` claim can be evaluated;
`verified` remains unavailable under the current Trust contract.

Run the focused and installed evidence with:

```bash
uv run --locked --extra dev pytest -q \
  tests/generation tests/cli/test_generation.py \
  tests/automation/test_quality_gates.py --no-cov
uv run --locked python tools/package_contract.py
```

The two schemas can be reproduced with
`uv run --locked python tools/generate_generation_schema.py --check`; the
positive and negative wire fixtures are checked by
`python -m tests.generation._fixture_factory --check`.
