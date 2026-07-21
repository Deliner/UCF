# UCF security policy

UCF is a `0.1.x production preview`, not a stable API. The supported control
plane boundary is CPython 3.12 on Linux/x86_64. External adapters and ecosystem
profiles are experimental exact proofs, not trusted plugins or a sandbox.

## Report a vulnerability privately

Use **GitHub Private Vulnerability Reporting** in the canonical repository:
`https://github.com/Deliner/UCF`. Choose **Security**, then **Report a
vulnerability**. Do not open a public issue for a suspected vulnerability and
do not include exploit details, credentials, private source, or personal data
in GitHub Issues.

GitHub Private Vulnerability Reporting must be enabled by the repository owner
before that confidential route exists. This file does not prove activation.
The release checklist must verify that the private reporting action is
available before publishing a release. If it is unavailable, UCF has no
authorized fallback confidential channel and release is blocked; no email
address is implied or invented.

Include the affected UCF version and artifact digest, platform, reproduction
steps, impact, and the smallest safe supporting material. Deliner is the
responsible maintainer. Community support has no response-time SLA, resolution
SLA, or embargo-time promise.

## Scope and handling

Reports about the Python control plane, published schemas, release artifacts,
and repository-owned fixtures are in scope. Adapter processes run with the
current user's authority and are not a sandbox; behavior by an untrusted
adapter outside the declared protocol is not proof of a core isolation bug,
although protocol escape, unsafe cleanup, or misleading security claims remain
reportable.

Deliner will validate the report privately, minimize retained sensitive data,
coordinate a correction, and publish a GitHub security advisory when users
must act. An urgent withdrawal may shorten the normal deprecation window only
through a published advisory that names affected versions and a replacement or
mitigation. Package hashes and UCF content digests provide integrity or
traceability checks only; no artifact-signing or provenance-attestation claim
is made.

Public usage questions and non-sensitive defects belong in GitHub Issues. See
the [support policy](docs/release/SUPPORT.md),
[privacy policy](docs/release/PRIVACY.md), and
[capability matrix](docs/CAPABILITIES.md) for the exact boundaries.
