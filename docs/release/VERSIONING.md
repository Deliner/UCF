# Preview versioning and deprecation policy

The Python distribution uses semantic version syntax, but the selected release
line is a `0.1.x production preview`. Major version zero is not a stable API.
No compatibility promise is inferred merely because two releases share `0.1`
or because a serialized resource uses `1.0.0` or `2.0.0`; exact compatibility
is defined in `COMPATIBILITY.md`.

## Immutable releases

Every published package version, wheel, source distribution, schema, manifest,
adapter artifact, and release note is immutable. Never overwrite an artifact
or retag changed bytes as the same release. A correction uses a new version,
new hashes, and release notes that name superseded/affected versions.

Package, schema, adapter protocol, capability, adapter implementation,
procedure, source revision, and environment versions are independent. A package
release may add a new side-by-side resource version without reinterpreting the
old one. Preview package release notes must enumerate added, deprecated,
removed, security-affected, and migration-requiring public contracts.

## Normal deprecation

A normal deprecation must be documented in release notes with its replacement,
rationale, affected contract versions, and migration guidance. The old path
remains available for at least one subsequent minor preview and at least 90
days, whichever is longer. For example, a path first deprecated in `0.1.x`
remains available throughout the next minor preview line and cannot be removed
solely because 90 days elapsed.

Removal after that window still requires release notes and a reproducible
migration or an explicit statement that no automated migration is safe.
Deprecation must not silently weaken Ratchet baselines, discard evidence,
reinterpret immutable schemas, or broaden/narrow support claims.

## Urgent security withdrawal

An actively unsafe contract or artifact may be withdrawn faster only through a
published security advisory. The advisory must name affected versions, impact,
mitigation, and a safe replacement or state clearly when none exists. Urgency
does not authorize replacing immutable artifact bytes or concealing migration
effects.

Promotion to `1.0.0` and a stable API is a future explicit owner decision. It
requires evidence for the promised compatibility/support surface and is not a
side effect of completing release readiness for this preview.
Changing a version does not promote any status in
[docs/CAPABILITIES.md](../CAPABILITIES.md).
