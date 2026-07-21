# Packaging, installation, and licensing policy

The supported Python release artifacts are one wheel and one source
distribution for the exact package version. Every published artifact is
immutable: replacing bytes under an existing filename/version is forbidden.
A corrected build receives a new package version and fresh hashes.

## Required artifact contents

Both wheel and source distribution must carry the Apache-2.0 project `LICENSE`
and `NOTICE`, project metadata, README, public schemas/templates needed by the
installed commands, and the files declared by the executable release manifest.
The source distribution contains reviewable project source and required
fixtures/documentation, but must exclude VCS metadata, virtual environments,
dependency caches, build output, `.artifacts`, frontend `node_modules`, adapter
dependency trees, credentials, and local editor state.

Dependency-populated and source-only checkouts must produce the same bounded
source-distribution manifest. Two builds from the same clean source, toolchain,
and declared environment must be byte-identical where the release checklist
claims reproducibility. A manifest difference is a release failure, not a file
to remove manually from generated output.

## Installation boundary

The supported control-plane installation is a clean environment using CPython
3.12 on Linux/x86_64. The release checklist installs the built wheel and source
distribution outside the checkout, executes the installed CLI and public
resources, and runs the exact smoke/behavior procedures named in the checklist.
`uv.lock` pins repository development/release verification; published runtime
dependency constraints are package metadata and must pass their separately
checked supported-floor scenario.

Node, npm, TypeScript/Fastify, and Go binaries used by exact ecosystem fixtures
are not bundled as general UCF runtime support. Standalone adapter distributions
carry their own manifest, hashes, upstream license/notices, and exact toolchain
qualification. Those adapters remain experimental exact proofs.

## Executable release acceptance

The canonical distribution and policy check is:

```bash
uv run --locked python tools/release_check.py
```

It must reproduce dependency-populated and source-only distributions, build the
wheel from the source distribution, install it in ordinary and supported-floor
environments, run `ucf --version`, `ucf --help`, and the installed package
contract, audit the exact Python/npm/Go dependency and license inventories with
zero known advisories, and verify the canonical GitHub repository, Issues, and
GitHub Private Vulnerability Reporting. A failed phase publishes no release
evidence. The complete repository acceptance command remains:

```bash
python3 tools/quality_gates.py --profile all
```

Both commands require network access for fresh advisory and hosted-surface
verification. Network failure is an indeterminate release failure, never a
clean result or waiver.

## License and third-party obligations

UCF project code is licensed under Apache-2.0, with `Copyright 2026 Deliner` in
`NOTICE`. Distributors must comply with `LICENSE`, preserve `NOTICE`, mark
modified files as required by Apache-2.0, and preserve applicable third-party
copyright, license, patent, and attribution notices. The project license does
not relicense dependencies, adapters, generated user code, or inspected legacy
projects.

Every release must inventory direct and transitive Python, frontend, adapter,
fixture, build, and bundled-tool dependencies from the exact locks/artifacts;
record their license and security disposition; and retain required third-party
notices. Unknown or incompatible licensing is a blocker, not an implicit
Apache-2.0 grant.

Published SHA-256 hashes and internal content digests support integrity and
traceability. UCF currently makes no artifact-signing, identity-attestation,
reproducible-across-all-platforms, or supply-chain non-compromise claim.
Packaging never promotes the implementation/evidence status in
[docs/CAPABILITIES.md](../CAPABILITIES.md).
