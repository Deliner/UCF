# Migration and rollback policy

UCF migrations are explicit, version-bound transformations. Never edit a
generated resource, reset a baseline, discard stale evidence, or reinterpret an
older schema merely to make an upgrade pass.

## Package preview upgrade

Before moving between `0.1.x` releases:

1. retain the exact installed artifact/hash, source inputs, accepted Ratchet
   tip IDs, generated-output receipts, and verification evidence needed to
   reproduce the current state;
2. read the target release notes, compatibility changes, deprecations, and
   security advisories;
3. install the target wheel in a clean CPython 3.12/Linux x86_64 environment;
4. validate source specifications and every persisted versioned UCF resource
   with the target CLI before mutation;
5. run named migrations into new output paths, inspect their canonical diff,
   then run the affected and full quality/behavior checks;
6. advance an accepted baseline only from a complete passing evaluation and
   independently preserve the accepted successor ID.

Rollback means reinstalling the retained older artifact and restoring its
unchanged compatible inputs. Newer-version resources are never passed to an
older parser unless a separately documented down-migration exists. At present,
UCF publishes no general down-migration.

## Ratchet v1 to v2

Ratchet `1.0.0` is unchanged. Ratchet `2.0.0` is a parallel dual-ledger
contract that keeps Behavior violations separate from unresolved coverage debt.
The only supported conversion is:

```text
ucf ratchet v2 migrate-from-v1 \
  --target-policy TARGET_V2_POLICY.json \
  --source-policy SOURCE_V1_POLICY.json \
  --source-baseline SOURCE_V1_BASELINE.json \
  --source-assessment SOURCE_V1_ASSESSMENT.json \
  --onboarding-bundle ONBOARDING_BUNDLE.json \
  --accepted-source-baseline-id BASELINE_ID \
  --output NEW_V2_BASELINE.json
```

The command requires the exact target v2 policy, source Policy, source Baseline,
source Assessment, and OnboardingBundle plus the independently stored
`--accepted-source-baseline-id`. It validates their complete relationship,
requires a complete public-interface inventory domain, preserves generation,
Behavior allowances and protections, records all source references, and
imports uncertain decisions as inherited unresolved coverage debt. It writes a
new v2 lineage root; it does not mutate the v1 source.

Missing/mismatched source resources, a wrong accepted tip, an incompatible
target policy, incomplete comparison domain, ambiguous identity, or output
alias fails with exit `3` and preserves existing output. There is no v2-to-v1 downgrade.
TypeScript and Go profiles with no accepted v1 baseline establish v2
directly; they must not invent a v1 history.

## Baseline safety

Unchanged inherited debt can pass only under the exact policy and comparable
qualification. New, touched, changed, reintroduced, or protected debt blocks.
Missing partial evidence is inconclusive, never a resolution. `advance` cannot
add an allowance, remove a protection, reset generation, or replace the
authoritative accepted-tip decision. An improved baseline cannot be silently
weakened during migration or rollback.

Schema, lifecycle, generation, and evidence-status changes follow the same
rule: validate exact source coordinates, produce a separate target artifact,
retain provenance, and publish a named migration before removing the old path.
The evidence and breadth limits in
[docs/CAPABILITIES.md](../CAPABILITIES.md) continue to control before and after
a migration.
