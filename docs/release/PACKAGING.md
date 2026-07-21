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
3.12 on Linux/x86_64. The release checklist inspects the source distribution,
builds a wheel from the source distribution and installs that wheel outside the
checkout, executes the installed CLI and public resources, and runs the exact
smoke/behavior procedures named in the checklist. A direct installer frontend
invocation on the `.tar.gz` is not a separate support claim; the proved source
artifact boundary is its isolated standards-based wheel build and installation.
`uv.lock` pins repository development/release verification; published runtime
dependency constraints are package metadata and must pass their separately
checked supported-floor scenario.

Node, npm, TypeScript/Fastify, and Go binaries used by exact ecosystem fixtures
are not bundled as general UCF runtime support. Standalone adapter distributions
carry root UCF `LICENSE`/`NOTICE`, applicable upstream license/notices, package
metadata where applicable, and exact toolchain qualification. Release evidence records
their exact manifest and SHA-256; the hash record is not claimed to be
an embedded artifact member. Those adapters remain experimental exact proofs.

## Executable release acceptance

The canonical distribution and policy check during development/CI is:

```bash
uv run --locked python tools/release_check.py
```

Final retained acceptance additionally uses an absent evidence path:

```bash
uv run --locked python tools/release_check.py \
  --evidence .artifacts/quality/rel002-final-20260721/release-evidence.json
```

It must reproduce dependency-populated and source-only distributions, build the
wheel from the source distribution, install it in ordinary and supported-floor
environments, run `ucf --version`, `ucf --help`, and an installed strict-parser
contract in both environments, and run the installed package contract. The
parser contract requires UCF and Pydantic imports below the new environment
prefix, binds the module/distribution Pydantic version to the installed
inventory and exact supported floor, preserves every current public alias plus
the complete free-form map, and rejects unknown fields, coercion, internal
field names, and simultaneous public/internal names at their expected paths.
The checker audits both actual installed Python
environments plus the exact locked Python/npm/Go dependency and license
inventories with zero known advisories, and verifies the canonical GitHub
repository, Issues, and GitHub Private Vulnerability Reporting.
A final evidence run additionally exports exact raw blobs from a captured clean
commit, binds its tree and selected manifest to the artifacts, and requires its
HEAD to equal nonempty remote `main` before atomic evidence publication. A
failed pre-commit phase leaves no evidence at the requested path. On the
supported Linux boundary, publication requires `O_TMPFILE` plus `linkat` with
`AT_EMPTY_PATH`: the complete file remains an anonymous staged inode until its
create-only link is the commit point. No name-based rollback follows that
commit. If the subsequent parent-directory flush fails, the command exits
nonzero with `committed_durability_unknown` and preserves the complete visible
file because deleting by name could remove a concurrent replacement. File
existence or an internal `status` field alone is therefore insufficient;
retained acceptance also requires that the producing command exit zero. A
filesystem without this publication support fails explicitly before creating
the evidence path. An existing-path collision is opened with `O_NONBLOCK` and
`O_NOFOLLOW`, so a FIFO or symbolic link cannot block or redirect validation;
only a regular file with exact content and stable descriptor/entry identity,
size, and modification metadata is an idempotent success. The complete
repository acceptance command remains:

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
copyright, license, patent, and attribution notices. UCF-authored adapters are
Apache-2.0 project code. The project license does not relicense dependencies,
third-party adapter implementations, generated user code, or inspected legacy
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
