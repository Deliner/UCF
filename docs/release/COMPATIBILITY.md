# Compatibility policy

UCF is a `0.1.x production preview`, not a stable API. Compatibility is stated
per exact coordinate; a similar name or newer number is not evidence of
compatibility.

## Independent version axes

The following axes are independent and must remain separately visible:

| Axis | Compatibility rule |
|---|---|
| package version | The installed Python distribution and CLI share one `0.1.x` preview version. Only an exact published artifact is immutable; compatibility with another package version follows release notes and this policy, never version proximity alone. |
| schema URI and schema version | Every versioned serialized resource names its exact schema URI/version. Parsers accept only explicitly implemented coordinates. A new resource version is side-by-side unless a documented migration says otherwise. |
| adapter protocol version | The core and process must negotiate an implemented protocol coordinate. No cross-major or undeclared protocol compatibility is inferred. |
| capability version | Every required capability is negotiated independently of the protocol. A protocol match does not make a missing or differently versioned capability usable. |
| adapter implementation version | Evidence is bound to the exact producing adapter. A changed adapter requires fresh qualification/evidence even when protocol and capability versions are unchanged. |
| source revision | Inventory, mappings, verification, and evidence status bind an exact source revision or digest. A changed revision is reassessed through the relevant profile. |
| environment | Runtime/toolchain/platform coordinates are evidence inputs. A changed environment requires reassessment; it is not silently equivalent. |
| package platform | The supported control plane tier is CPython 3.12 on Linux/x86_64. Installability elsewhere is not a support claim. |

## Strict serialized boundary

Unknown fields, duplicate JSON members, unsupported versions, unsupported capabilities,
malformed values, broken references, identity conflicts, and
non-canonical inputs covered by a profile are rejected explicitly. There is no
parser auto-detection, permissive fallback, or no implicit downgrade. A
successful structural parse proves only that the document satisfies that exact
shape; it does not create observed, mapped, tested, or verified evidence.

Published schema and protocol artifacts are immutable. A correction that would
change accepted bytes or semantics receives a new version and an explicit
migration/compatibility entry. Exact earlier resources remain available for the
normal deprecation window. UCF publishes no implicit compatibility range for
schema, adapter protocol, capability, Ratchet, lifecycle, generation, or
evidence-status coordinates.

## Compatibility classes

- Additive documentation, diagnostics, tests, or a new side-by-side version is
  compatible when existing accepted inputs and outputs keep their meaning.
- Adding an optional capability is compatible only when absence preserves the
  prior behavior; required capabilities need an explicit new profile/version.
- Changing canonical bytes, identity derivation, required fields, rejection
  behavior, outcome semantics, command names/options, or exit classes is a
  breaking change for that exact contract.
- A migration is compatible only with the named source/target versions and
  checked preconditions. It never authorizes a generic downgrade.

Because the package is a preview, normal public Python/CLI changes may still
occur, but [VERSIONING.md](VERSIONING.md) requires notice, a migration, and the
minimum deprecation interval. The exact adapter and fixture proofs in
[docs/CAPABILITIES.md](../CAPABILITIES.md) remain experimental exact proofs and
do not expand the supported matrix.
