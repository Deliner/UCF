# Support policy and matrix

UCF `0.1.x` is a production preview, not a stable API. Deliner is the
responsible maintainer. Public questions and non-sensitive defects use
GitHub Issues in `https://github.com/Deliner/UCF`. Community support has no SLA for
response, resolution, compatibility work, or release frequency. Sensitive
reports follow the root [SECURITY.md](../../SECURITY.md), never a public issue.

## Support matrix

| Surface | Status | Exact boundary |
|---|---|---|
| Python control plane | supported preview | CPython 3.12 on Linux/x86_64, installed from the release wheel or source distribution and exercised by the release checklist |
| serialized UCF resources | supported preview | only the exact schema URIs/versions implemented and shipped by that release; strict rejection and deprecation policies apply |
| source YAML and legacy in-process features | supported preview only where capability rows say `implemented` | executable evidence and limitations in [docs/CAPABILITIES.md](../CAPABILITIES.md) control |
| Python, TypeScript/Fastify, and Go adapters | experimental | exact fixture, adapter, toolchain, OS/architecture, capability, and procedure proofs named in the matrix; not general ecosystem support |
| HTTP, CLI, and file-spool event behavior | experimental | exact local procedures in CAP-209, not a hosted transport or broker guarantee |
| web catalog | experimental development surface | build/lint and named repository tests only; no supported deployment, authentication, or multi-user service |

Windows, macOS, Linux architectures other than x86_64, Python versions other
than CPython 3.12, PyPy, arbitrary Node/Go versions, hosted brokers, unlisted
frameworks, unreviewed adapters, and arbitrary legacy applications are
explicitly not supported. Successful installation or a passing narrow fixture elsewhere does
not promote that environment to support.

## Issue handling

An actionable public issue should name the UCF version and artifact digest,
platform/tool versions, exact command, minimal reproduction, expected and
actual behavior, and sanitized output. Maintainer acknowledgment or a proposed
patch is not a promise of delivery. Unsupported environments may still receive
community help, but any expansion of this matrix requires reproducible evidence
and an explicit policy update.

The exact limitations are intentional: they prevent experimental adapters,
adapter-attested `tested` evidence, hashes, or scripted fixture review from
being presented as broad production support, independent attestation, formal
verification, or authenticity.
