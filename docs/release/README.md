# UCF release policy index

UCF follows a bounded `0.1.x production preview` release model. It is not a
stable API and has no SLA. The supported control plane tier is CPython 3.12 on
Linux/x86_64. Language/framework adapters remain experimental exact proofs over
the fixtures and coordinates named in `docs/CAPABILITIES.md`; passing one such
proof is not general ecosystem support.

These documents are the public policy boundary selected by project owner
Deliner:

- [COMPATIBILITY.md](COMPATIBILITY.md) — independent version axes, strict wire
  handling, and the exact compatibility matrix;
- [MIGRATION.md](MIGRATION.md) — preview upgrades, Ratchet v1-to-v2 migration,
  downgrade rejection, and rollback rules;
- [PRIVACY.md](PRIVACY.md) — local data flow, trust, logging, retention, and
  sensitive-data responsibilities;
- [PACKAGING.md](PACKAGING.md) — wheel/source-distribution contents,
  installation, licenses, notices, and artifact integrity;
- [SUPPORT.md](SUPPORT.md) — supported control plane, experimental proofs,
  unsupported environments, and public support;
- [VERSIONING.md](VERSIONING.md) — preview versioning, artifact immutability,
  deprecation, and urgent security withdrawal;
- [../../SECURITY.md](../../SECURITY.md) — confidential vulnerability
  reporting and advisory handling;
- [../../LICENSE](../../LICENSE) and [../../NOTICE](../../NOTICE) — Apache-2.0
  grant and project attribution.

The policies constrain releases; they do not themselves prove one. CAP-214 is
implemented only because the executable release checklist also proves exact
published source, metadata, dependency/advisory disposition, reproducible wheel
and source distribution, clean installation, installed resources, policy
consistency, hosted reporting surfaces, and the complete quality profile. The
canonical evidence-backed capability statement remains
`docs/CAPABILITIES.md`.

## Decision ownership and residual risk

Deliner owns the release boundary and every documented residual limitation.
The capability matrix keeps limitations because their broader meanings are not
proved by executable evidence. A future release may remove a limitation only
after the corresponding reproducible proof and claim review; silence is never
treated as support. Promotion from preview to a stable API is a separate owner
decision and is not implied by completing REL-002.
