# UCF behavior IR 1.0.0

The current public behavior intermediate representation is exactly version
`1.0.0`. It is a language-neutral JSON graph and is separate from UCF's YAML
source-declaration models. Accepting an IR document proves only that its bytes,
closed records, identities, references, ports, bindings, and declared
capability requirements are valid. It does not execute behavior, reconcile
intent with observations, or promote a claim to `tested` or `verified`.

## Public boundaries

- `ucf ir validate <document.json>` validates raw JSON, the structural model,
  and cross-record semantics.
- `ucf.ir.parse_ir_json(...)` returns the immutable typed reference model.
- `ucf.ir.canonical_ir_json(...)` emits the repository canonical profile.
- `ucf.ir.validate_required_capabilities(...)` compares an explicit
  environment capability map with required capability records.
- `src/ucf/schemas/ir/v1/schema.json` is the packaged Draft 2020-12 structural
  schema.

The JSON Schema cannot express global identity uniqueness or cross-record
reference resolution. Those checks are intentionally named in
`x-ucf-runtime-semantic-checks` and always run through the parser and CLI.

## Trust IR overlay

Intent/evidence semantics are published separately as exact trust IR `1.0.0`.
The overlay never rewrites behavior IR. It binds to one behavior document by
document ID, exact IR version, and SHA-256 of canonical behavior-IR bytes, then
references entities by both kind and ID.

Public boundaries are:

- `ucf trust validate <trust.json> --behavior-ir <behavior.json>` performs the
  complete internal, cross-document, reconciliation, and claim checks;
- `ucf.ir.parse_trust_ir_json(...)` validates the closed immutable overlay and
  all internal IDs, references, traces, and basis categories;
- `ucf.ir.validate_trust_against_behavior(...)` validates canonical document
  identity, external entity references, mappings, and claim evidence;
- `ucf.ir.canonical_trust_ir_json(...)` emits deterministic trust bytes;
- `ucf.ir.reconcile_mapping(...)` derives a new immutable `match` or `conflict`
  mapping without changing either input fact;
- `ucf.ir.supported_claim_levels(...)` returns a set of independently
  supported labels, never a highest or numerically promoted label;
- `src/ucf/schemas/trust/v1/schema.json` is the packaged Draft 2020-12
  structural schema.

Declarations reference the existing behavior entity that owns intent.
Observed facts retain a separate assertion and source record. Reconciliation
therefore preserves both sides of a disagreement. A behavior candidate retains
canonical string confidence in `[0,1]`, but confidence is review metadata and
can never serve as test evidence.

`observed`, `declared`, `mapped`, and `tested` are different evidence
predicates, not successive states. `tested` requires passed evidence for the
exact subject plus the current artifact revision, check ID/version/procedure,
environment digest, and producer resolved through evidence provenance.
Well-formed `failed`, `error`, stale, or mismatched evidence remains valid
retained Behavior IR but is rejected as a tested basis. `verified` is
explicitly unavailable: the current models do not represent a named checked
property, assumptions, and a reproducible proof or exhaustive procedure.

## Compatibility

Readers currently accept only normalized `1.0.0`; `1.0.1`, `1.1.0`, and other
major versions fail with `unsupported_version`. A future release must publish
new compatibility fixtures, a versioned schema, and migration evidence before
expanding that set. Unknown fields are never a forward-compatibility escape
hatch.

The raw decoder rejects a UTF-8 BOM, invalid UTF-8, duplicate object members,
non-finite numbers, raw JSON fractions/exponents, and integers outside the
cross-runtime exact range. Precise fractional values use canonical decimal
strings inside a tagged `decimal` value. JSON nesting deeper than 128 levels
is rejected with `invalid_structure` rather than leaking a runtime recursion
failure.

Behavior IR and trust IR have independent exact-version fields and schemas.
Adding trust records never changes behavior IR `1.0.0`; changing either public
contract requires its own versioned fixtures, compatibility decision, and
migration evidence.

## Graph model

An envelope contains globally identified, top-level records for:

- use cases, ordered step references, and actions;
- typed input/output ports and bindings;
- language-neutral effects and observations;
- opaque declared invariants with an exact dialect;
- provenance, verification evidence, and capability requirements.

Every entity reference declares both its target ID and expected kind. Missing
targets and wrong-kind targets are different stable errors. Rules remain
opaque; the Python core neither parses nor executes their dialect.

## Canonical JSON

Canonical output uses compact JSON, lexicographically sorted object keys,
ASCII-escaped strings, and exactly one trailing newline. Entity sets, ports,
record entries, and set-like reference collections have stable semantic
sorting. Behavioral step order, value-list order, and domain paths are
preserved.

The checked schema is regenerated or verified with:

```bash
uv run --locked --extra dev python tools/generate_ir_schema.py
uv run --locked --extra dev python tools/generate_ir_schema.py --check
uv run --locked --extra dev python tools/generate_trust_ir_schema.py
uv run --locked --extra dev python tools/generate_trust_ir_schema.py --check
```

Executable evidence and exact limitations are maintained in
[CAPABILITIES.md](CAPABILITIES.md).

Behavior and Trust IR may cross the separate exact-version adapter boundary,
which reruns their internal semantic validators rather than treating nested
model construction as acceptance. The adapter protocol does not reinterpret
either document or promote claims. See
[ADAPTER_PROTOCOL.md](ADAPTER_PROTOCOL.md).
