# Privacy and data-handling policy

UCF is locally operated software. It does not provide hosted storage,
UCF-managed accounts, telemetry, or a UCF-managed retention service. The
operator decides what repositories and evidence to process and remains
responsible for its role as data controller. Installing the package does not by
itself make Deliner or UCF a hosted data processor; a separate deployment or
service agreement would require its own policy.

## Data that may be processed

Inventory, onboarding, Ratchet, mapping, runtime, generation, lifecycle, and
verification flows may read or emit source paths, symbols, spans, source and
artifact digests, repository/tool/environment coordinates, producer IDs,
behavior values, diagnostics, candidate review decisions, evidence, and exact
command metadata. Depending on the inspected project, those fields can contain
confidential source information, credentials, personal data, or business
identifiers even when a payload looks structural.

UCF does not universally detect or anonymize secrets or personal data.
Recorded-runtime import only enforces the selected policy/profile; partial
sampling cannot prove absence. Hashes are traceability values, not
anonymization: low-entropy or otherwise identifiable inputs may remain
guessable or linkable.

## Authority and trust boundaries

The Python core and every external adapter run with the current OS user's
authority unless the operator supplies stronger isolation. The adapter protocol
is not a sandbox. An adapter can access whatever the operating-system identity
can access, including filesystem, process, and network resources; install and
run only reviewed adapters under least privilege. The web development surface
has no published multi-user access-control or hosted privacy claim.

Diagnostic stderr is bounded by the process client but can still contain
sensitive adapter output. UCF-generated JSON, baselines, evidence ledgers,
reports, generated trees, `.artifacts` logs, CI logs, caches, and temporary
directories inherit the sensitivity of their inputs. Do not pass credentials
on command lines, commit private evidence, or paste sensitive material into
GitHub Issues.

## Minimization, retention, and deletion

- Limit inventory roots, evidence rules, runtime recordings, and adapter
  capabilities to what the review actually needs.
- Sanitize recordings before import and inspect diagnostics before sharing.
- Store accepted baseline IDs and required provenance in access-controlled
  reviewed version control or CI policy; store raw sensitive payloads
  separately when the digest is sufficient.
- The operator owns retention periods. Keep reproducibility and audit records
  only as long as project, contractual, and legal requirements need them, then
  delete local outputs, logs, caches, CI artifacts, and backups through the
  systems that hold them.
- UCF has no remote erasure endpoint because the published package sends no
  data to a UCF-hosted service. Deleting a local output does not delete copies
  already committed, backed up, uploaded, or supplied to an adapter.

Suspected exposure is a security report. Follow the root
[SECURITY.md](../../SECURITY.md); do not use a public issue for secrets,
exploit details, private source, or personal data. The data and trust
limitations in [docs/CAPABILITIES.md](../CAPABILITIES.md) remain canonical.
