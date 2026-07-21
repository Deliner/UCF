from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from importlib.metadata import distributions
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MAX_SDIST_BYTES = 5 * 1024 * 1024
MAX_SDIST_MEMBERS = 2_000
MAX_SDIST_MEMBER_BYTES = 5 * 1024 * 1024
MAX_SDIST_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
MAX_SDIST_TAR_STREAM_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_MEMBER_NAME_BYTES = 4096

REQUIRED_SDIST_MEMBERS = frozenset(
    {
        ".gitignore",
        "AGENTS.md",
        "LICENSE",
        "NOTICE",
        "PKG-INFO",
        "README.md",
        "SECURITY.md",
        "adapters/go-stdlib/go.mod",
        "adapters/python-pytest/adapter.py",
        "adapters/typescript-fastify/package.json",
        "docs/CAPABILITIES.md",
        "docs/automation/TARGET_STATE.md",
        "pyproject.toml",
        "specs/use-cases/validate-spec-directory.yaml",
        "src/ucf/__init__.py",
        "src/ucf/adapter_conformance/assets/v1/manifest.json",
        "src/ucf/schemas/ir/v1/schema.json",
        "tests/__init__.py",
        "tests/automation/test_release_distribution.py",
        "tools/package_contract.py",
        "tools/release_check.py",
        "uv.lock",
        "web/package.json",
    }
)

ALLOWED_SDIST_ROOTS = frozenset(
    {
        ".agents",
        ".codex",
        ".cursor",
        ".github",
        ".gitignore",
        "AGENTS.md",
        "BOTTLE_NECKS.md",
        "CONTEXT_TRACER.md",
        "CRITIQUE.md",
        "CURSOR_HOOKS.md",
        "DEPENDENCY_GRAPH.md",
        "FRAMEWORK_STRESS_TEST_SESSION_2.md",
        "GENERATORS.md",
        "IMPLEMENTATION_ROADMAP.md",
        "INVARIANTS.md",
        "LICENSE",
        "NOTICE",
        "PKG-INFO",
        "PLANS.md",
        "README.md",
        "SECURITY.md",
        "SPEC_LANGUAGE.md",
        "STRESS_TEST_REPORT.md",
        "UCF_FRAMEWORK_GUIDE.md",
        "adapters",
        "docs",
        "examples",
        "pyproject.toml",
        "specs",
        "src",
        "tests",
        "tools",
        "uv.lock",
        "web",
    }
)

FORBIDDEN_DIRECTORY_NAMES = frozenset(
    {
        ".artifacts",
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
    }
)

EXPECTED_CLASSIFIERS = frozenset(
    {
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
    }
)

EXPECTED_PROJECT_URLS = frozenset(
    {
        "Documentation, https://github.com/Deliner/UCF/tree/main/docs",
        "Repository, https://github.com/Deliner/UCF",
        "Security, https://github.com/Deliner/UCF/security/advisories/new",
        "Support, https://github.com/Deliner/UCF/issues",
    }
)

EXPECTED_RUNTIME_REQUIREMENTS = frozenset(
    {
        "jinja2>=3.1.6",
        "networkx>=3.0",
        "pydantic>=2.4.0",
        "pyyaml>=6.0.1",
        "rich>=13.0",
        "typer>=0.16.0",
    }
)

APPROVED_NPM_LICENSES = frozenset(
    {
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BlueOak-1.0.0",
        "CC-BY-4.0",
        "ISC",
        "MIT",
        "Python-2.0",
        "Unlicense",
    }
)

APPROVED_PYTHON_LICENSE_IDENTITIES = frozenset(
    {
        "Apache-2.0",
        "Apache-2.0 OR BSD-2-Clause",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSD-OSI-Approved",
        "ISC",
        "MIT",
        "MPL-2.0",
        "PSF-2.0",
    }
)

PYTHON_LICENSE_ALIASES = {
    "Apache 2.0": "Apache-2.0",
    "Apache-2.0": "Apache-2.0",
    "Apache-2.0 OR BSD-2-Clause": "Apache-2.0 OR BSD-2-Clause",
    "BSD-2-Clause": "BSD-2-Clause",
    "BSD-3-Clause": "BSD-3-Clause",
    "ISC License": "ISC",
    "MIT": "MIT",
    "MIT License": "MIT",
    "MPL-2.0": "MPL-2.0",
    "PSF-2.0": "PSF-2.0",
    "PSFL": "PSF-2.0",
}

PYTHON_LICENSE_CLASSIFIERS = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-OSI-Approved",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": (
        "MPL-2.0"
    ),
    "License :: OSI Approved :: Python Software Foundation License": (
        "PSF-2.0"
    ),
}

GITHUB_REPOSITORY = "Deliner/UCF"
GITHUB_DEFAULT_BRANCH = "main"
GITHUB_API_ROOT = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
MAX_HOSTED_RESPONSE_BYTES = 1024 * 1024

MINIMUM_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)>=(?P<version>[A-Za-z0-9][A-Za-z0-9._+-]*)$"
)
GIT_OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
GIT_REGULAR_FILE_MODES = frozenset({"100644", "100755"})


class ReleaseCheckError(RuntimeError):
    """Raised when a releasable distribution invariant is false."""


@dataclass(frozen=True)
class GitBlobEntry:
    mode: str
    object_id: str
    path: PurePosixPath


@dataclass(frozen=True)
class GitSourceSnapshot:
    entries: tuple[GitBlobEntry, ...]
    kind: str
    revision: str | None = None
    tree: str | None = None


class _ByteLimitReader:
    def __init__(self, stream: BinaryIO, *, limit: int, label: str) -> None:
        self._stream = stream
        self._limit = limit
        self._label = label
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        remaining_with_probe = self._limit - self.bytes_read + 1
        requested = remaining_with_probe if size < 0 else min(
            size, remaining_with_probe
        )
        try:
            chunk = self._stream.read(requested)
        except (EOFError, gzip.BadGzipFile) as exc:
            raise ReleaseCheckError(
                f"{self._label} has an invalid gzip stream"
            ) from exc
        self.bytes_read += len(chunk)
        if self.bytes_read > self._limit:
            raise ReleaseCheckError(
                f"{self._label} exceeds decompressed stream limit: "
                f"{self.bytes_read} > {self._limit}"
            )
        return chunk


def dependency_audit_commands(
    source_root: Path, scratch_root: Path
) -> tuple[tuple[str, ...], ...]:
    runtime_requirements = scratch_root / "python-all-extras.txt"
    runtime_report = scratch_root / "python-all-extras-audit.json"
    build_requirements = scratch_root / "python-build.txt"
    build_report = scratch_root / "python-build-audit.json"
    return (
        (
            "uv",
            "export",
            "--locked",
            "--all-extras",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--output-file",
            str(runtime_requirements),
        ),
        (
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pip-audit",
            "--requirement",
            str(runtime_requirements),
            "--require-hashes",
            "--disable-pip",
            "--strict",
            "--progress-spinner",
            "off",
            "--format",
            "json",
            "--output",
            str(runtime_report),
        ),
        (
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pip-audit",
            "--requirement",
            str(build_requirements),
            "--no-deps",
            "--disable-pip",
            "--strict",
            "--progress-spinner",
            "off",
            "--format",
            "json",
            "--output",
            str(build_report),
        ),
        (
            "npm",
            "audit",
            "--package-lock-only",
            "--ignore-scripts",
            "--json",
            "--prefix",
            str(source_root / "web"),
        ),
        (
            "npm",
            "audit",
            "--package-lock-only",
            "--ignore-scripts",
            "--json",
            "--omit=dev",
            "--prefix",
            str(source_root / "web"),
        ),
        (
            "npm",
            "audit",
            "--package-lock-only",
            "--ignore-scripts",
            "--json",
            "--prefix",
            str(source_root / "adapters/typescript-fastify"),
        ),
        (
            "npm",
            "audit",
            "--package-lock-only",
            "--ignore-scripts",
            "--json",
            "--prefix",
            str(
                source_root
                / "tests/fixtures/brownfield/typescript_fastify_legacy_quote"
            ),
        ),
    )


def validate_npm_lock_inventory(
    lock: Mapping[str, object], *, label: str
) -> dict[str, object]:
    packages = lock.get("packages")
    if not isinstance(packages, Mapping):
        raise ReleaseCheckError(f"{label} npm lock has no packages object")

    missing: list[str] = []
    unreviewed: dict[str, str] = {}
    license_counts: Counter[str] = Counter()
    for raw_path, raw_package in packages.items():
        if raw_path == "":
            continue
        if not isinstance(raw_path, str) or not isinstance(raw_package, Mapping):
            raise ReleaseCheckError(f"{label} npm lock has malformed package data")
        license_name = raw_package.get("license")
        if not isinstance(license_name, str) or not license_name.strip():
            missing.append(raw_path)
            continue
        license_name = license_name.strip()
        license_counts[license_name] += 1
        if license_name not in APPROVED_NPM_LICENSES:
            unreviewed[raw_path] = license_name

    if missing:
        raise ReleaseCheckError(
            f"{label} npm lock packages have missing license metadata: {missing}"
        )
    if unreviewed:
        raise ReleaseCheckError(
            f"{label} npm lock has unreviewed licenses: {unreviewed}"
        )
    return {
        "package_count": sum(license_counts.values()),
        "license_counts": dict(sorted(license_counts.items())),
        "status": "reviewed",
    }


def validate_python_audit_report(
    report: Mapping[str, object], *, label: str
) -> dict[str, object]:
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list):
        raise ReleaseCheckError(
            f"{label} Python audit report has no dependencies list"
        )
    vulnerable: dict[str, list[str]] = {}
    skipped: dict[str, str] = {}
    coordinates: set[str] = set()
    for dependency in dependencies:
        if not isinstance(dependency, Mapping):
            raise ReleaseCheckError(
                f"{label} Python audit report has malformed dependency data"
            )
        name = dependency.get("name")
        version = dependency.get("version")
        vulnerabilities = dependency.get("vulns")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(version, str)
            or not version
            or not isinstance(vulnerabilities, list)
        ):
            raise ReleaseCheckError(
                f"{label} Python audit report has incomplete dependency data"
            )
        coordinate = f"{name.lower()}=={version}"
        if coordinate in coordinates:
            raise ReleaseCheckError(
                f"{label} Python audit report duplicates {coordinate}"
            )
        coordinates.add(coordinate)
        skip_reason = dependency.get("skip_reason")
        if skip_reason is not None and skip_reason != "":
            skipped[coordinate] = str(skip_reason)
        if vulnerabilities:
            vulnerable[coordinate] = [
                str(item.get("id", "unknown"))
                if isinstance(item, Mapping)
                else "malformed"
                for item in vulnerabilities
            ]
    if vulnerable:
        raise ReleaseCheckError(
            f"{label} Python dependencies have known vulnerabilities: {vulnerable}"
        )
    if skipped:
        raise ReleaseCheckError(
            f"{label} Python audit has skipped dependencies: {skipped}"
        )
    return {
        "dependency_count": len(coordinates),
        "packages": sorted(coordinates),
        "status": "no_known_vulnerabilities",
    }


def python_license_identity(metadata: Message) -> dict[str, str]:
    expression = (metadata.get("License-Expression") or "").strip()
    legacy = (metadata.get("License") or "").strip()
    if expression:
        identity = PYTHON_LICENSE_ALIASES.get(expression, expression)
        basis = "License-Expression"
    elif legacy:
        identity = PYTHON_LICENSE_ALIASES.get(legacy, legacy)
        basis = "License"
    else:
        classifier_identities = {
            PYTHON_LICENSE_CLASSIFIERS[classifier]
            for classifier in metadata.get_all("Classifier", [])
            if classifier in PYTHON_LICENSE_CLASSIFIERS
        }
        if len(classifier_identities) != 1:
            raise ReleaseCheckError(
                "Python dependency has no unambiguous reviewed license: "
                f"{metadata.get('Name')!r}, classifiers={sorted(classifier_identities)}"
            )
        [identity] = classifier_identities
        basis = "Classifier"

    if identity not in APPROVED_PYTHON_LICENSE_IDENTITIES:
        raise ReleaseCheckError(
            "unreviewed Python license identity for "
            f"{metadata.get('Name')!r}: {identity!r}"
        )
    return {"basis": basis, "identity": identity}


def _normalized_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _installed_python_license_inventory() -> dict[str, object]:
    inventory: list[dict[str, str]] = []
    names: set[str] = set()
    for distribution in distributions():
        name = distribution.metadata.get("Name")
        if not name or _normalized_package_name(name) == "ucf":
            continue
        normalized_name = _normalized_package_name(name)
        if normalized_name in names:
            raise ReleaseCheckError(
                f"installed Python inventory duplicates package {normalized_name!r}"
            )
        names.add(normalized_name)
        license_evidence = python_license_identity(distribution.metadata)
        inventory.append(
            {
                "license_basis": license_evidence["basis"],
                "license_identity": license_evidence["identity"],
                "name": normalized_name,
                "version": distribution.version,
            }
        )
    if not inventory:
        raise ReleaseCheckError("installed Python dependency inventory is empty")
    inventory.sort(key=lambda item: item["name"])
    environment = {
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "openssl": ssl.OPENSSL_VERSION,
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "python_compiler": platform.python_compiler(),
        "python_version": platform.python_version(),
        "python_version_detail": sys.version,
    }
    if (
        environment["implementation"] != "CPython"
        or not str(environment["python_version"]).startswith("3.12.")
        or environment["platform_system"] != "Linux"
        or environment["machine"] not in {"AMD64", "x86_64"}
    ):
        raise ReleaseCheckError(
            f"installed Python environment is outside support: {environment}"
        )
    return {
        "dependencies": inventory,
        "dependency_count": len(inventory),
        "environment": environment,
        "status": "reviewed",
    }


def _write_installed_python_license_inventory(output_path: Path) -> None:
    evidence = _installed_python_license_inventory()
    serialized = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    print(serialized, end="", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized, encoding="utf-8")


def validate_github_release_surfaces(
    repository: Mapping[str, object],
    private_reporting: Mapping[str, object],
    branch: Mapping[str, object],
    *,
    local_revision: str,
    require_published_source: bool,
) -> dict[str, object]:
    expected = {
        "default_branch": GITHUB_DEFAULT_BRANCH,
        "full_name": GITHUB_REPOSITORY,
        "has_issues": True,
        "private": False,
    }
    mismatches = {
        field: {"actual": repository.get(field), "expected": value}
        for field, value in expected.items()
        if repository.get(field) != value
    }
    if mismatches:
        raise ReleaseCheckError(
            f"canonical GitHub repository surface differs: {mismatches}"
        )
    repository_size = repository.get("size")
    if (
        isinstance(repository_size, bool)
        or not isinstance(repository_size, int)
        or repository_size < 0
    ):
        raise ReleaseCheckError(
            "canonical GitHub repository size metadata is malformed"
        )
    commit = branch.get("commit")
    remote_revision = commit.get("sha") if isinstance(commit, Mapping) else None
    if (
        branch.get("name") != GITHUB_DEFAULT_BRANCH
        or not isinstance(remote_revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", remote_revision) is None
    ):
        raise ReleaseCheckError(
            f"canonical GitHub main branch is malformed: {branch}"
        )
    if re.fullmatch(r"[0-9a-f]{40}", local_revision) is None:
        raise ReleaseCheckError(
            f"local source revision is malformed: {local_revision!r}"
        )
    source_published = remote_revision == local_revision
    if require_published_source and not source_published:
        raise ReleaseCheckError(
            "local release source is not published to canonical main: "
            f"local={local_revision}, remote={remote_revision}"
        )
    if private_reporting.get("enabled") is not True:
        raise ReleaseCheckError(
            "GitHub Private Vulnerability Reporting is not enabled"
        )
    return {
        "default_branch": GITHUB_DEFAULT_BRANCH,
        "issues": "enabled",
        "private_vulnerability_reporting": "enabled",
        "remote_main_revision": remote_revision,
        "reported_repository_size_kib": repository_size,
        "repository": GITHUB_REPOSITORY,
        "source_published_to_main": source_published,
        "source_revision": local_revision,
        "visibility": "public",
    }


def _safe_member_path(raw_path: str) -> PurePosixPath:
    try:
        encoded_length = len(raw_path.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ReleaseCheckError(
            f"unsafe archive member: {raw_path!r}"
        ) from exc
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or encoded_length > MAX_ARCHIVE_MEMBER_NAME_BYTES
        or "\\" in raw_path
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != raw_path
    ):
        raise ReleaseCheckError(f"unsafe archive member: {raw_path!r}")
    return path


def _validate_sdist_relative_path(
    path: PurePosixPath, *, raw_path: str, is_directory: bool
) -> None:
    if not path.parts or path.parts[0] not in ALLOWED_SDIST_ROOTS:
        raise ReleaseCheckError(
            f"sdist has an unapproved root member: {raw_path}"
        )
    checked_parts = path.parts if is_directory else path.parts[:-1]
    forbidden_directory = next(
        (
            part
            for part in checked_parts
            if part in FORBIDDEN_DIRECTORY_NAMES
            or part.endswith(".egg-info")
        ),
        None,
    )
    if forbidden_directory is not None:
        raise ReleaseCheckError(
            "sdist contains forbidden directory "
            f"{forbidden_directory!r}: {raw_path}"
        )
    if not is_directory and (
        path.name == ".coverage" or path.suffix in {".pyc", ".pyo"}
    ):
        raise ReleaseCheckError(
            f"sdist contains generated local state: {raw_path}"
        )


def validate_sdist_member_paths(
    relative_paths: Sequence[str],
    *,
    archive_size: int,
    member_sizes: Mapping[str, int] | None = None,
) -> None:
    if archive_size > MAX_SDIST_BYTES:
        raise ReleaseCheckError(
            f"sdist exceeds size limit: {archive_size} > {MAX_SDIST_BYTES}"
        )
    if len(relative_paths) > MAX_SDIST_MEMBERS:
        raise ReleaseCheckError(
            "sdist exceeds member limit: "
            f"{len(relative_paths)} > {MAX_SDIST_MEMBERS}"
        )

    duplicates = sorted(
        path for path, count in Counter(relative_paths).items() if count > 1
    )
    if duplicates:
        raise ReleaseCheckError(
            f"sdist has duplicate archive members: {duplicates}"
        )

    if member_sizes is not None:
        if set(member_sizes) != set(relative_paths):
            raise ReleaseCheckError(
                "sdist uncompressed-size inventory differs from file members"
            )
        invalid_sizes = {
            path: size
            for path, size in member_sizes.items()
            if isinstance(size, bool) or not isinstance(size, int) or size < 0
        }
        if invalid_sizes:
            raise ReleaseCheckError(
                f"sdist has invalid uncompressed member sizes: {invalid_sizes}"
            )
        oversized = {
            path: size
            for path, size in member_sizes.items()
            if size > MAX_SDIST_MEMBER_BYTES
        }
        if oversized:
            raise ReleaseCheckError(
                "sdist exceeds uncompressed member size limit: "
                f"{oversized}"
            )
        uncompressed_size = sum(member_sizes.values())
        if uncompressed_size > MAX_SDIST_UNCOMPRESSED_BYTES:
            raise ReleaseCheckError(
                "sdist exceeds total uncompressed size limit: "
                f"{uncompressed_size} > {MAX_SDIST_UNCOMPRESSED_BYTES}"
            )

    normalized_paths: set[str] = set()
    for raw_path in relative_paths:
        path = _safe_member_path(raw_path)
        normalized_paths.add(path.as_posix())
        _validate_sdist_relative_path(
            path, raw_path=raw_path, is_directory=False
        )

    missing = sorted(REQUIRED_SDIST_MEMBERS - normalized_paths)
    if missing:
        raise ReleaseCheckError(
            f"sdist is missing required source members: {missing}"
        )


def validate_sdist_source_manifest(
    selected_source: Mapping[str, str],
    archived_source: Mapping[str, str],
) -> None:
    missing = sorted(set(selected_source) - set(archived_source))
    if missing:
        raise ReleaseCheckError(
            f"sdist omits selected source files: {missing}"
        )
    unexpected = sorted(set(archived_source) - set(selected_source))
    if unexpected:
        raise ReleaseCheckError(
            f"sdist includes unselected source files: {unexpected}"
        )
    changed = sorted(
        path
        for path, digest in selected_source.items()
        if archived_source[path] != digest
    )
    if changed:
        raise ReleaseCheckError(
            f"sdist changes selected source files: {changed}"
        )


def _metadata_values(metadata: Message, header: str) -> frozenset[str]:
    return frozenset(str(value) for value in metadata.get_all(header, []))


def validate_core_metadata(metadata: Message, *, expected_version: str) -> None:
    scalar_fields = {
        "Name": "ucf",
        "Version": expected_version,
        "Requires-Python": ">=3.12",
        "License-Expression": "Apache-2.0",
        "Author": "Deliner",
        "Maintainer": "Deliner",
        "Description-Content-Type": "text/markdown",
    }
    for field, expected in scalar_fields.items():
        actual = metadata.get(field)
        if actual != expected:
            raise ReleaseCheckError(
                f"package metadata {field} is {actual!r}, expected {expected!r}"
            )

    repeated_fields = {
        "License-File": frozenset({"LICENSE", "NOTICE"}),
        "Classifier": EXPECTED_CLASSIFIERS,
        "Project-URL": EXPECTED_PROJECT_URLS,
    }
    for field, expected in repeated_fields.items():
        actual = _metadata_values(metadata, field)
        if actual != expected:
            raise ReleaseCheckError(
                f"package metadata {field} is {sorted(actual)!r}, "
                f"expected {sorted(expected)!r}"
            )

    runtime_requirements = frozenset(
        value.lower()
        for value in _metadata_values(metadata, "Requires-Dist")
        if "; extra ==" not in value.lower()
    )
    if runtime_requirements != EXPECTED_RUNTIME_REQUIREMENTS:
        raise ReleaseCheckError(
            "package runtime requirements do not match supported direct floors: "
            f"{sorted(runtime_requirements)!r}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest_sha256(manifest: Mapping[str, str]) -> str:
    canonical = json.dumps(
        dict(sorted(manifest.items())),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _source_file_manifest(source_root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(source_root.rglob("*")):
        if path.is_symlink():
            raise ReleaseCheckError(
                f"selected source contains a symlink: {path.relative_to(source_root)}"
            )
        if path.is_file():
            relative_path = path.relative_to(source_root).as_posix()
            manifest[relative_path] = _sha256(path)
    return manifest


def _canonical_tar_member_path(member: tarfile.TarInfo) -> PurePosixPath:
    raw_path = member.name
    if member.isdir() and raw_path.endswith("/"):
        raw_path = raw_path[:-1]
    return _safe_member_path(raw_path)


def _read_tar_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo
) -> bytes:
    stream = archive.extractfile(member)
    if stream is None:
        raise ReleaseCheckError(f"cannot read sdist member: {member.name}")
    chunks: list[bytes] = []
    bytes_read = 0
    while bytes_read < member.size:
        chunk = stream.read(min(1024 * 1024, member.size - bytes_read))
        if not chunk:
            break
        chunks.append(chunk)
        bytes_read += len(chunk)
    if bytes_read != member.size:
        raise ReleaseCheckError(
            f"sdist member is truncated: {member.name}: "
            f"{bytes_read} != {member.size}"
        )
    return b"".join(chunks)


def _inspect_sdist_contents(
    archive_path: Path, *, expected_version: str
) -> tuple[dict[str, object], dict[str, str]]:
    archive_size = archive_path.stat().st_size
    if archive_size > MAX_SDIST_BYTES:
        raise ReleaseCheckError(
            f"sdist exceeds size limit: {archive_size} > {MAX_SDIST_BYTES}"
        )

    expected_root = f"ucf-{expected_version}"
    canonical_members: set[str] = set()
    relative_files: list[str] = []
    member_sizes: dict[str, int] = {}
    source_manifest: dict[str, str] = {}
    metadata_payloads: list[bytes] = []
    member_count = 0
    directory_count = 0
    uncompressed_file_bytes = 0
    largest_member = 0

    with gzip.open(archive_path, "rb") as compressed:
        bounded = _ByteLimitReader(
            compressed,
            limit=MAX_SDIST_TAR_STREAM_BYTES,
            label="sdist tar stream",
        )
        with tarfile.open(fileobj=bounded, mode="r|") as archive:
            for member in archive:
                member_count += 1
                if member_count > MAX_SDIST_MEMBERS:
                    raise ReleaseCheckError(
                        "sdist exceeds member limit: "
                        f"{member_count} > {MAX_SDIST_MEMBERS}"
                    )
                if not (member.isfile() or member.isdir()):
                    raise ReleaseCheckError(
                        "sdist contains a link or special file: "
                        f"{member.name}"
                    )

                path = _canonical_tar_member_path(member)
                canonical_name = path.as_posix()
                if canonical_name in canonical_members:
                    raise ReleaseCheckError(
                        f"sdist has duplicate archive member: {member.name}"
                    )
                canonical_members.add(canonical_name)
                if path.parts[0] != expected_root:
                    raise ReleaseCheckError(
                        f"unexpected sdist archive root: {path.parts[0]!r}"
                    )

                relative = PurePosixPath(*path.parts[1:])
                if not relative.parts:
                    if not member.isdir():
                        raise ReleaseCheckError(
                            "sdist archive root must be a directory"
                        )
                    directory_count += 1
                    continue
                relative_name = relative.as_posix()
                _validate_sdist_relative_path(
                    relative,
                    raw_path=relative_name,
                    is_directory=member.isdir(),
                )
                if member.isdir():
                    if member.size != 0:
                        raise ReleaseCheckError(
                            f"sdist directory has content size: {member.name}"
                        )
                    directory_count += 1
                    continue

                if member.size < 0 or member.size > MAX_SDIST_MEMBER_BYTES:
                    raise ReleaseCheckError(
                        "sdist exceeds uncompressed member size limit: "
                        f"{relative_name}={member.size}"
                    )
                uncompressed_file_bytes += member.size
                if uncompressed_file_bytes > MAX_SDIST_UNCOMPRESSED_BYTES:
                    raise ReleaseCheckError(
                        "sdist exceeds total uncompressed size limit: "
                        f"{uncompressed_file_bytes} > "
                        f"{MAX_SDIST_UNCOMPRESSED_BYTES}"
                    )
                largest_member = max(largest_member, member.size)
                payload = _read_tar_member(archive, member)
                relative_files.append(relative_name)
                member_sizes[relative_name] = member.size
                if relative_name == "PKG-INFO":
                    metadata_payloads.append(payload)
                else:
                    source_manifest[relative_name] = _sha256_bytes(payload)
        while bounded.read(1024 * 1024):
            pass

    validate_sdist_member_paths(
        relative_files,
        archive_size=archive_size,
        member_sizes=member_sizes,
    )
    if len(metadata_payloads) != 1:
        raise ReleaseCheckError(
            f"sdist must contain one PKG-INFO member: {len(metadata_payloads)}"
        )
    metadata = BytesParser(policy=default).parsebytes(metadata_payloads[0])
    validate_core_metadata(metadata, expected_version=expected_version)
    evidence = {
        "bytes": archive_size,
        "directory_members": directory_count,
        "file_members": len(relative_files),
        "largest_uncompressed_member_bytes": largest_member,
        "member_count": member_count,
        "sha256": _sha256(archive_path),
        "uncompressed_file_bytes": uncompressed_file_bytes,
    }
    return evidence, source_manifest


def inspect_sdist(
    archive_path: Path, *, expected_version: str
) -> dict[str, object]:
    evidence, _ = _inspect_sdist_contents(
        archive_path, expected_version=expected_version
    )
    return evidence


def inspect_wheel(
    wheel_path: Path, *, expected_version: str
) -> dict[str, object]:
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        for name in names:
            _safe_member_path(name.rstrip("/"))
        duplicates = sorted(
            name for name, count in Counter(names).items() if count > 1
        )
        if duplicates:
            raise ReleaseCheckError(
                f"wheel has duplicate archive members: {duplicates}"
            )
        metadata_names = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ReleaseCheckError(
                f"wheel must have one METADATA member: {metadata_names}"
            )
        metadata = BytesParser(policy=default).parsebytes(
            archive.read(metadata_names[0])
        )
        validate_core_metadata(metadata, expected_version=expected_version)
        dist_info = metadata_names[0].removesuffix("METADATA")
        required = {
            f"{dist_info}licenses/LICENSE",
            f"{dist_info}licenses/NOTICE",
            "ucf/schemas/ir/v1/schema.json",
            "ucf/adapter_conformance/assets/v1/manifest.json",
        }
        missing = sorted(required - set(names))
        if missing:
            raise ReleaseCheckError(
                f"wheel is missing required release members: {missing}"
            )
        if any("node_modules" in PurePosixPath(name).parts for name in names):
            raise ReleaseCheckError("wheel contains a node_modules member")

    return {
        "bytes": wheel_path.stat().st_size,
        "file_members": len(names),
        "sha256": _sha256(wheel_path),
    }


def _run(command: Sequence[str], *, cwd: Path) -> None:
    print(f"$ {shlex.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise ReleaseCheckError(
            f"command failed with exit {completed.returncode}: "
            f"{shlex.join(command)}"
        )


def _run_json_command(
    command: Sequence[str], *, cwd: Path
) -> Mapping[str, object]:
    print(f"$ {shlex.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        text=True,
    )
    if process.stdout is None:
        raise ReleaseCheckError(
            f"cannot read JSON command output: {shlex.join(command)}"
        )
    output_parts: list[str] = []
    for line in process.stdout:
        print(line, end="", flush=True)
        output_parts.append(line)
    returncode = process.wait()
    if returncode != 0:
        raise ReleaseCheckError(
            f"command failed with exit {returncode}: {shlex.join(command)}"
        )
    try:
        result = json.loads("".join(output_parts))
    except json.JSONDecodeError as exc:
        raise ReleaseCheckError(
            f"command returned invalid JSON: {shlex.join(command)}: {exc}"
        ) from exc
    if not isinstance(result, Mapping):
        raise ReleaseCheckError(
            f"command returned a non-object JSON result: {shlex.join(command)}"
        )
    return result


def _load_json_object(path: Path, *, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseCheckError(f"cannot read {label} JSON at {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ReleaseCheckError(f"{label} JSON must contain an object")
    return value


def _single_artifact(directory: Path, pattern: str) -> Path:
    artifacts = sorted(directory.glob(pattern))
    if len(artifacts) != 1:
        raise ReleaseCheckError(
            f"expected one {pattern} in {directory}, found {artifacts}"
        )
    return artifacts[0]


def _build_sdist(source_root: Path, output_directory: Path) -> Path:
    output_directory.mkdir(parents=True)
    _run(
        ("uv", "build", "--sdist", "--out-dir", str(output_directory)),
        cwd=source_root,
    )
    return _single_artifact(output_directory, "*.tar.gz")


def _build_wheel(source_root: Path, output_directory: Path) -> Path:
    output_directory.mkdir(parents=True)
    _run(
        ("uv", "build", "--wheel", "--out-dir", str(output_directory)),
        cwd=source_root,
    )
    return _single_artifact(output_directory, "*.whl")


def _excluded_source_names(
    directory: str, names: list[str]
) -> list[str]:
    return [
        name
        for name in names
        if name in FORBIDDEN_DIRECTORY_NAMES
        or name.endswith((".egg-info", ".pyc", ".pyo"))
        or name in {".coverage", ".DS_Store"}
        or (Path(directory).name == ".cursor" and name == "settings.json")
    ]


def _configured_sdist_inputs_from_bytes(payload: bytes) -> tuple[str, ...]:
    try:
        configuration = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseCheckError(
            f"cannot read source-distribution configuration: {exc}"
        ) from exc
    try:
        configured_inputs = configuration["tool"]["hatch"]["build"][
            "targets"
        ]["sdist"]["only-include"]
    except (KeyError, TypeError) as exc:
        raise ReleaseCheckError(
            "source-distribution configuration has no only-include list"
        ) from exc
    if not isinstance(configured_inputs, list) or not all(
        isinstance(value, str) for value in configured_inputs
    ):
        raise ReleaseCheckError(
            "source-distribution only-include must be a string list"
        )
    selected = tuple(
        dict.fromkeys([".gitignore", "pyproject.toml", *configured_inputs])
    )
    for value in selected:
        _safe_member_path(value)
    return selected


def _configured_sdist_inputs(source_root: Path) -> tuple[str, ...]:
    return _configured_sdist_inputs_from_bytes(
        (source_root / "pyproject.toml").read_bytes()
    )


def _git_output(source_root: Path, *arguments: str) -> bytes:
    command = ("git", "-C", str(source_root), *arguments)
    print(f"$ {shlex.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseCheckError(
            "cannot read Git source objects used by the release boundary: "
            f"{detail or f'exit {completed.returncode}'}"
        )
    return completed.stdout


def _decode_git_path(raw_path: bytes) -> PurePosixPath:
    try:
        decoded = raw_path.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseCheckError(
            "Git release source path is not valid UTF-8"
        ) from exc
    return _safe_member_path(decoded)


def _parse_git_index_entries(payload: bytes) -> tuple[GitBlobEntry, ...]:
    entries: list[GitBlobEntry] = []
    paths: set[str] = set()
    for record in payload.split(b"\0"):
        if not record:
            continue
        header, separator, raw_path = record.partition(b"\t")
        fields = header.split()
        if not separator or len(fields) != 3:
            raise ReleaseCheckError("Git index entry is malformed")
        raw_mode, raw_object_id, raw_stage = fields
        if raw_stage != b"0":
            raise ReleaseCheckError("Git index contains an unmerged source entry")
        path = _decode_git_path(raw_path)
        path_text = path.as_posix()
        if path_text in paths:
            raise ReleaseCheckError(f"Git index duplicates source path: {path_text}")
        paths.add(path_text)
        mode = raw_mode.decode("ascii", errors="strict")
        object_id = raw_object_id.decode("ascii", errors="strict")
        if GIT_OBJECT_ID.fullmatch(object_id) is None:
            raise ReleaseCheckError(
                f"Git index object ID is malformed: {object_id!r}"
            )
        entries.append(GitBlobEntry(mode=mode, object_id=object_id, path=path))
    return tuple(entries)


def _parse_git_tree_entries(payload: bytes) -> tuple[GitBlobEntry, ...]:
    entries: list[GitBlobEntry] = []
    paths: set[str] = set()
    for record in payload.split(b"\0"):
        if not record:
            continue
        header, separator, raw_path = record.partition(b"\t")
        fields = header.split()
        if not separator or len(fields) != 3:
            raise ReleaseCheckError("Git commit tree entry is malformed")
        raw_mode, raw_type, raw_object_id = fields
        if raw_type != b"blob":
            raise ReleaseCheckError("Git commit source entry is not a blob")
        path = _decode_git_path(raw_path)
        path_text = path.as_posix()
        if path_text in paths:
            raise ReleaseCheckError(
                f"Git commit tree duplicates source path: {path_text}"
            )
        paths.add(path_text)
        mode = raw_mode.decode("ascii", errors="strict")
        object_id = raw_object_id.decode("ascii", errors="strict")
        if GIT_OBJECT_ID.fullmatch(object_id) is None:
            raise ReleaseCheckError(
                f"Git commit object ID is malformed: {object_id!r}"
            )
        entries.append(GitBlobEntry(mode=mode, object_id=object_id, path=path))
    return tuple(entries)


def _read_git_blobs(
    source_root: Path, entries: Sequence[GitBlobEntry]
) -> dict[str, bytes]:
    command = ("git", "-C", str(source_root), "cat-file", "--batch")
    print(f"$ {shlex.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        raise ReleaseCheckError("cannot open Git object reader")
    payloads: dict[str, bytes] = {}
    total_bytes = 0
    try:
        for entry in entries:
            process.stdin.write(f"{entry.object_id}\n".encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().rstrip(b"\n")
            fields = header.split()
            if len(fields) != 3:
                raise ReleaseCheckError(
                    f"Git object response is malformed: {header!r}"
                )
            raw_object_id, object_type, raw_size = fields
            if (
                raw_object_id.decode("ascii", errors="replace")
                != entry.object_id
                or object_type != b"blob"
            ):
                raise ReleaseCheckError(
                    f"Git source object differs from index/tree: {header!r}"
                )
            try:
                size = int(raw_size)
            except ValueError as exc:
                raise ReleaseCheckError(
                    f"Git source object size is malformed: {header!r}"
                ) from exc
            if size < 0 or size > MAX_SDIST_MEMBER_BYTES:
                raise ReleaseCheckError(
                    "Git source object exceeds release member limit: "
                    f"{entry.path.as_posix()}={size}"
                )
            total_bytes += size
            if total_bytes > MAX_SDIST_UNCOMPRESSED_BYTES:
                raise ReleaseCheckError(
                    "Git selected source exceeds total release size limit: "
                    f"{total_bytes} > {MAX_SDIST_UNCOMPRESSED_BYTES}"
                )
            blob = process.stdout.read(size)
            terminator = process.stdout.read(1)
            if len(blob) != size or terminator != b"\n":
                raise ReleaseCheckError(
                    f"Git source object is truncated: {entry.object_id}"
                )
            payloads[entry.path.as_posix()] = blob
        process.stdin.close()
        stderr = process.stderr.read()
        returncode = process.wait()
        if returncode != 0:
            raise ReleaseCheckError(
                "Git object reader failed: "
                f"{stderr.decode('utf-8', errors='replace').strip()}"
            )
    except BaseException:
        process.kill()
        process.wait()
        raise
    return payloads


def _select_git_source_entries(
    source_root: Path, entries: Sequence[GitBlobEntry]
) -> tuple[GitBlobEntry, ...]:
    pyproject_entries = [
        entry for entry in entries if entry.path.as_posix() == "pyproject.toml"
    ]
    if len(pyproject_entries) != 1:
        raise ReleaseCheckError(
            "Git source must contain exactly one pyproject.toml blob"
        )
    pyproject_payload = _read_git_blobs(source_root, pyproject_entries)[
        "pyproject.toml"
    ]
    selected_inputs = _configured_sdist_inputs_from_bytes(pyproject_payload)
    selected_paths = tuple(PurePosixPath(value) for value in selected_inputs)
    included = tuple(
        sorted(
            (
                entry
                for entry in entries
                if any(
                    entry.path == selected or selected in entry.path.parents
                    for selected in selected_paths
                )
            ),
            key=lambda entry: entry.path.as_posix(),
        )
    )
    if not included:
        raise ReleaseCheckError(
            "Git source contains no selected source-distribution files"
        )
    if len(included) + 1 > MAX_SDIST_MEMBERS:
        raise ReleaseCheckError(
            "Git selected source exceeds sdist member limit: "
            f"{len(included) + 1} > {MAX_SDIST_MEMBERS}"
        )
    missing_inputs = [
        selected.as_posix()
        for selected in selected_paths
        if not any(
            entry.path == selected or selected in entry.path.parents
            for entry in included
        )
    ]
    if missing_inputs:
        raise ReleaseCheckError(
            f"Git source omits configured distribution inputs: {missing_inputs}"
        )
    unsupported = {
        entry.path.as_posix(): entry.mode
        for entry in included
        if entry.mode not in GIT_REGULAR_FILE_MODES
    }
    if unsupported:
        raise ReleaseCheckError(
            f"Git release source contains non-regular entries: {unsupported}"
        )
    return included


def _capture_git_source_snapshot(
    source_root: Path, *, require_committed_source: bool
) -> GitSourceSnapshot:
    source_root = source_root.resolve()
    if require_committed_source:
        revision, tree = _committed_source_identity(
            source_root, require_clean=True
        )
        entries = _parse_git_tree_entries(
            _git_output(
                source_root,
                "ls-tree",
                "-r",
                "-z",
                "--full-tree",
                revision,
            )
        )
        snapshot = GitSourceSnapshot(
            entries=_select_git_source_entries(source_root, entries),
            kind="git_commit",
            revision=revision,
            tree=tree,
        )
        _revalidate_git_source_snapshot(source_root, snapshot)
        return snapshot

    entries = _parse_git_index_entries(
        _git_output(source_root, "ls-files", "--stage", "-z")
    )
    return GitSourceSnapshot(
        entries=_select_git_source_entries(source_root, entries),
        kind="git_index",
    )


def _copy_source_only(
    source_root: Path,
    target_root: Path,
    *,
    source_snapshot: GitSourceSnapshot | None = None,
) -> GitSourceSnapshot | None:
    if (source_root / ".git").exists():
        snapshot = source_snapshot or _capture_git_source_snapshot(
            source_root, require_committed_source=False
        )
        payloads = _read_git_blobs(source_root, snapshot.entries)
        for entry in snapshot.entries:
            target = target_root.joinpath(*entry.path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payloads[entry.path.as_posix()])
            target.chmod(0o755 if entry.mode == "100755" else 0o644)
        return snapshot

    selected = _configured_sdist_inputs(source_root)
    for relative in selected:
        source = source_root / relative
        if not source.exists():
            raise ReleaseCheckError(
                f"configured source-distribution input does not exist: {relative}"
            )
        if source.is_symlink():
            raise ReleaseCheckError(
                f"configured source-distribution input is a symlink: {relative}"
            )

    for relative in selected:
        source = source_root / relative
        target = target_root / relative
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=_excluded_source_names,
                symlinks=True,
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return None


def _extract_sdist(archive_path: Path, target_directory: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(target_directory, filter="data")
    roots = [path for path in target_directory.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise ReleaseCheckError(
            f"expected one extracted sdist root, found: {roots}"
        )
    return roots[0]


def _venv_python(environment: Path) -> Path:
    return environment / "bin" / "python"


def _venv_ucf(environment: Path) -> Path:
    return environment / "bin" / "ucf"


def _create_environment(environment: Path, *, cwd: Path) -> None:
    _run(("uv", "venv", "--python", "3.12", str(environment)), cwd=cwd)


def _run_installed_cli(
    environment: Path, *, cwd: Path, expected_version: str
) -> None:
    clean_environment = os.environ.copy()
    clean_environment.pop("PYTHONHOME", None)
    clean_environment.pop("PYTHONPATH", None)

    version_command = (str(_venv_ucf(environment)), "--version")
    print(f"$ {shlex.join(version_command)}", flush=True)
    completed = subprocess.run(
        version_command,
        cwd=cwd,
        env=clean_environment,
        check=False,
        stdout=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise ReleaseCheckError(
            f"installed ucf --version failed with exit {completed.returncode}"
        )
    print(completed.stdout, end="", flush=True)
    expected_output = f"ucf {expected_version}\n"
    if completed.stdout != expected_output:
        raise ReleaseCheckError(
            "installed CLI version drift: "
            f"got {completed.stdout!r}, expected {expected_output!r}"
        )

    help_command = (str(_venv_ucf(environment)), "--help")
    print(f"$ {shlex.join(help_command)}", flush=True)
    completed = subprocess.run(
        help_command,
        cwd=cwd,
        env=clean_environment,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseCheckError(
            f"installed ucf --help failed with exit {completed.returncode}"
        )


def _minimum_requirements(source_root: Path) -> tuple[str, ...]:
    configuration = tomllib.loads(
        (source_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    minimums = []
    for requirement in configuration["project"]["dependencies"]:
        match = MINIMUM_REQUIREMENT.fullmatch(requirement)
        if match is None:
            raise ReleaseCheckError(
                "direct dependency is not an auditable minimum-only range: "
                f"{requirement!r}"
            )
        minimums.append(f"{match['name']}=={match['version']}")
    return tuple(minimums)


def validate_npm_audit_report(
    report: Mapping[str, object], *, label: str
) -> dict[str, object]:
    if report.get("auditReportVersion") != 2:
        raise ReleaseCheckError(
            f"{label} npm audit has unsupported report version: "
            f"{report.get('auditReportVersion')!r}"
        )
    metadata = report.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ReleaseCheckError(f"{label} npm audit has no metadata object")
    vulnerabilities = metadata.get("vulnerabilities")
    if not isinstance(vulnerabilities, Mapping):
        raise ReleaseCheckError(
            f"{label} npm audit has no vulnerability summary"
        )
    severities = ("info", "low", "moderate", "high", "critical", "total")
    counts: dict[str, int] = {}
    for severity in severities:
        count = vulnerabilities.get(severity)
        if not isinstance(count, int) or count < 0:
            raise ReleaseCheckError(
                f"{label} npm audit has invalid {severity!r} count: {count!r}"
            )
        counts[severity] = count
    if counts["total"] != sum(counts[name] for name in severities[:-1]):
        raise ReleaseCheckError(
            f"{label} npm audit vulnerability totals are inconsistent: {counts}"
        )
    if counts["total"] != 0:
        raise ReleaseCheckError(
            f"{label} npm dependencies have known vulnerabilities: {counts}"
        )
    return {"status": "no_known_vulnerabilities", "vulnerabilities": counts}


def _write_build_requirements(source_root: Path, output_path: Path) -> tuple[str, ...]:
    configuration = tomllib.loads(
        (source_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    raw_requirements = configuration["build-system"]["requires"]
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise ReleaseCheckError("build-system.requires must be a non-empty list")
    requirements: list[str] = []
    for raw_requirement in raw_requirements:
        if (
            not isinstance(raw_requirement, str)
            or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9._+-]*",
                raw_requirement,
            )
        ):
            raise ReleaseCheckError(
                "build dependency is not exactly pinned: "
                f"{raw_requirement!r}"
            )
        requirements.append(raw_requirement)
    if len(set(requirements)) != len(requirements):
        raise ReleaseCheckError("build-system.requires contains duplicates")
    output_path.write_text("\n".join(requirements) + "\n", encoding="utf-8")
    return tuple(requirements)


def _inventory_coordinates(inventory: Mapping[str, object]) -> set[str]:
    dependencies = inventory.get("dependencies")
    if inventory.get("status") != "reviewed" or not isinstance(
        dependencies, list
    ):
        raise ReleaseCheckError("Python license inventory is malformed")
    coordinates: set[str] = set()
    for dependency in dependencies:
        if not isinstance(dependency, Mapping):
            raise ReleaseCheckError("Python license inventory has malformed data")
        name = dependency.get("name")
        version = dependency.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise ReleaseCheckError("Python license inventory has missing coordinates")
        coordinate = f"{_normalized_package_name(name)}=={version}"
        if coordinate in coordinates:
            raise ReleaseCheckError(
                f"Python license inventory duplicates {coordinate}"
            )
        coordinates.add(coordinate)
    return coordinates


def _validate_audit_license_alignment(
    audit: Mapping[str, object],
    inventory: Mapping[str, object],
    *,
    label: str,
) -> None:
    raw_audit_packages = audit.get("packages")
    if not isinstance(raw_audit_packages, list):
        raise ReleaseCheckError(f"{label} audit evidence has no package list")
    audit_packages = {
        f"{_normalized_package_name(value.rsplit('==', 1)[0])}=="
        f"{value.rsplit('==', 1)[1]}"
        for value in raw_audit_packages
        if isinstance(value, str) and "==" in value
    }
    if len(audit_packages) != len(raw_audit_packages):
        raise ReleaseCheckError(f"{label} audit evidence has malformed packages")
    inventory_packages = _inventory_coordinates(inventory)
    if audit_packages != inventory_packages:
        raise ReleaseCheckError(
            f"{label} security and license inventories differ: "
            f"audit_only={sorted(audit_packages - inventory_packages)}, "
            f"license_only={sorted(inventory_packages - audit_packages)}"
        )


def _go_dependency_inventory(source_root: Path) -> dict[str, object]:
    module_paths = (
        "adapters/go-stdlib/go.mod",
        "tests/fixtures/brownfield/go_stdlib_legacy_platforms/go.mod",
        "tests/fixtures/brownfield/go_stdlib_legacy_quote/go.mod",
    )
    modules: list[dict[str, str]] = []
    for relative_path in module_paths:
        path = source_root / relative_path
        content = path.read_text(encoding="utf-8")
        if re.search(r"(?m)^\s*require(?:\s|\()", content):
            raise ReleaseCheckError(
                f"Go module has external requirements requiring review: {relative_path}"
            )
        if path.with_name("go.sum").exists():
            raise ReleaseCheckError(
                f"Go module has an unreviewed dependency sum: {relative_path}"
            )
        toolchain = re.search(r"(?m)^toolchain\s+(\S+)\s*$", content)
        modules.append(
            {
                "path": relative_path,
                "sha256": _sha256(path),
                "toolchain": toolchain.group(1) if toolchain else "inherited",
            }
        )
    notice_paths = (
        "adapters/go-stdlib/third_party/go/LICENSE",
        "adapters/go-stdlib/third_party/go/PATENTS",
    )
    notices = {}
    for relative_path in notice_paths:
        path = source_root / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            raise ReleaseCheckError(
                f"Go toolchain notice is missing or empty: {relative_path}"
            )
        notices[relative_path] = _sha256(path)
    return {
        "external_module_count": 0,
        "modules": modules,
        "status": "reviewed",
        "upstream_notices": notices,
    }


def _verify_installs(
    wheel_path: Path,
    *,
    source_root: Path,
    scratch_root: Path,
    expected_version: str,
) -> dict[str, object]:
    ordinary = scratch_root / "ordinary-environment"
    _create_environment(ordinary, cwd=scratch_root)
    _run(
        (
            "uv",
            "pip",
            "install",
            "--python",
            str(_venv_python(ordinary)),
            str(wheel_path),
        ),
        cwd=scratch_root,
    )
    _run_installed_cli(
        ordinary, cwd=scratch_root, expected_version=expected_version
    )
    ordinary_inventory_path = scratch_root / "ordinary-license-inventory.json"
    _run(
        (
            str(_venv_python(ordinary)),
            str(source_root / "tools/release_check.py"),
            "--installed-python-license-inventory",
            str(ordinary_inventory_path),
        ),
        cwd=scratch_root,
    )
    ordinary_inventory = _load_json_object(
        ordinary_inventory_path,
        label="ordinary installed Python license inventory",
    )

    floors = scratch_root / "minimum-environment"
    _create_environment(floors, cwd=scratch_root)
    _run(
        (
            "uv",
            "pip",
            "install",
            "--python",
            str(_venv_python(floors)),
            "--no-deps",
            str(wheel_path),
        ),
        cwd=scratch_root,
    )
    _run(
        (
            "uv",
            "pip",
            "install",
            "--python",
            str(_venv_python(floors)),
            *_minimum_requirements(source_root),
        ),
        cwd=scratch_root,
    )
    _run(
        ("uv", "pip", "freeze", "--python", str(_venv_python(floors))),
        cwd=scratch_root,
    )
    _run_installed_cli(
        floors, cwd=scratch_root, expected_version=expected_version
    )
    floor_inventory_path = scratch_root / "supported-floor-license-inventory.json"
    _run(
        (
            str(_venv_python(floors)),
            str(source_root / "tools/release_check.py"),
            "--installed-python-license-inventory",
            str(floor_inventory_path),
        ),
        cwd=scratch_root,
    )
    floor_inventory = _load_json_object(
        floor_inventory_path,
        label="supported-floor installed Python license inventory",
    )
    return {
        "ordinary": ordinary_inventory,
        "supported_floor": floor_inventory,
    }


def _audit_installed_environment(
    *,
    label: str,
    inventory: Mapping[str, object],
    scratch_root: Path,
    source_root: Path,
) -> dict[str, object]:
    coordinates = sorted(_inventory_coordinates(inventory))
    if not coordinates:
        raise ReleaseCheckError(f"{label} installed dependency inventory is empty")
    requirements_path = scratch_root / f"{label}-requirements.txt"
    report_path = scratch_root / f"{label}-audit.json"
    requirements_path.write_text(
        "\n".join(coordinates) + "\n", encoding="utf-8"
    )
    _run(
        (
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pip-audit",
            "--requirement",
            str(requirements_path),
            "--no-deps",
            "--disable-pip",
            "--strict",
            "--progress-spinner",
            "off",
            "--format",
            "json",
            "--output",
            str(report_path),
        ),
        cwd=source_root,
    )
    audit = validate_python_audit_report(
        _load_json_object(report_path, label=f"{label} Python audit"),
        label=label,
    )
    _validate_audit_license_alignment(audit, inventory, label=label)
    return {
        "audit": audit,
        "audit_report_sha256": _sha256(report_path),
        "licenses_and_environment": inventory,
        "requirements_sha256": _sha256(requirements_path),
    }


def check_dependency_audits(
    source_root: Path,
    *,
    installation_environments: Mapping[str, object],
) -> dict[str, object]:
    source_root = source_root.resolve()
    with tempfile.TemporaryDirectory(prefix="ucf-release-dependencies-") as raw:
        scratch = Path(raw)
        runtime_requirements = scratch / "python-all-extras.txt"
        runtime_report_path = scratch / "python-all-extras-audit.json"
        build_requirements_path = scratch / "python-build.txt"
        build_report_path = scratch / "python-build-audit.json"
        runtime_inventory_path = scratch / "python-all-extras-licenses.json"
        build_inventory_path = scratch / "python-build-licenses.json"

        build_requirements = _write_build_requirements(
            source_root, build_requirements_path
        )
        commands = dependency_audit_commands(source_root, scratch)
        for command in commands[:3]:
            _run(command, cwd=source_root)

        runtime_audit = validate_python_audit_report(
            _load_json_object(runtime_report_path, label="runtime Python audit"),
            label="runtime",
        )
        build_audit = validate_python_audit_report(
            _load_json_object(build_report_path, label="build Python audit"),
            label="build",
        )

        _run(
            (
                "uv",
                "run",
                "--locked",
                "--all-extras",
                "python",
                "tools/release_check.py",
                "--installed-python-license-inventory",
                str(runtime_inventory_path),
            ),
            cwd=source_root,
        )
        build_environment_arguments = tuple(
            argument
            for requirement in build_requirements
            for argument in ("--with", requirement)
        )
        _run(
            (
                "uv",
                "run",
                "--isolated",
                "--no-project",
                *build_environment_arguments,
                "python",
                str(source_root / "tools/release_check.py"),
                "--installed-python-license-inventory",
                str(build_inventory_path),
            ),
            cwd=source_root,
        )
        runtime_inventory = _load_json_object(
            runtime_inventory_path, label="runtime Python license inventory"
        )
        build_inventory = _load_json_object(
            build_inventory_path, label="build Python license inventory"
        )
        _validate_audit_license_alignment(
            runtime_audit, runtime_inventory, label="runtime Python"
        )
        _validate_audit_license_alignment(
            build_audit, build_inventory, label="build Python"
        )

        npm_labels = (
            "web-all",
            "web-runtime",
            "typescript-adapter",
            "typescript-fixture",
        )
        npm_audits = {
            label: validate_npm_audit_report(
                _run_json_command(command, cwd=source_root), label=label
            )
            for label, command in zip(npm_labels, commands[3:], strict=True)
        }
        npm_lock_paths = {
            "typescript-adapter": (
                source_root / "adapters/typescript-fastify/package-lock.json"
            ),
            "typescript-fixture": (
                source_root
                / "tests/fixtures/brownfield/typescript_fastify_legacy_quote"
                / "package-lock.json"
            ),
            "web": source_root / "web/package-lock.json",
        }
        npm_licenses = {}
        for label, lock_path in npm_lock_paths.items():
            lock = _load_json_object(lock_path, label=f"{label} package lock")
            inventory = validate_npm_lock_inventory(lock, label=label)
            inventory["lock_sha256"] = _sha256(lock_path)
            npm_licenses[label] = inventory

        if set(installation_environments) != {"ordinary", "supported_floor"}:
            raise ReleaseCheckError(
                "installed environment evidence must contain ordinary and "
                "supported_floor inventories"
            )
        installed_environment_audits = {}
        for label in ("ordinary", "supported_floor"):
            inventory = installation_environments[label]
            if not isinstance(inventory, Mapping):
                raise ReleaseCheckError(
                    f"{label} installed environment inventory is malformed"
                )
            installed_environment_audits[label] = _audit_installed_environment(
                label=label,
                inventory=inventory,
                scratch_root=scratch,
                source_root=source_root,
            )

        evidence = {
            "go": _go_dependency_inventory(source_root),
            "npm": {
                "audits": npm_audits,
                "licenses": npm_licenses,
            },
            "python": {
                "build": {
                    "audit": build_audit,
                    "audit_report_sha256": _sha256(build_report_path),
                    "licenses": build_inventory,
                    "requirements": list(build_requirements),
                    "requirements_sha256": _sha256(build_requirements_path),
                },
                "runtime_and_release_tools": {
                    "audit": runtime_audit,
                    "audit_report_sha256": _sha256(runtime_report_path),
                    "licenses": runtime_inventory,
                    "requirements_sha256": _sha256(runtime_requirements),
                    "uv_lock_sha256": _sha256(source_root / "uv.lock"),
                },
                "installed_environments": installed_environment_audits,
            },
            "status": "passed",
        }
        print(json.dumps(evidence, indent=2, sort_keys=True), flush=True)
        return evidence


def _read_hosted_json(url: str) -> Mapping[str, object]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "UCF-release-check/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    print(f"$ GET {url}", flush=True)
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read(MAX_HOSTED_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ReleaseCheckError(
            f"cannot verify GitHub release surface {url}: {exc}"
        ) from exc
    if len(payload) > MAX_HOSTED_RESPONSE_BYTES:
        raise ReleaseCheckError(f"GitHub release surface response is too large: {url}")
    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseCheckError(
            f"GitHub release surface returned invalid JSON: {url}: {exc}"
        ) from exc
    if not isinstance(result, Mapping):
        raise ReleaseCheckError(
            f"GitHub release surface returned a non-object: {url}"
        )
    return result


def _require_clean_git_source(source_root: Path) -> None:
    for difference in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
        command = ("git", "-C", str(source_root), *difference)
        print(f"$ {shlex.join(command)}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            raise ReleaseCheckError(
                "release evidence requires committed tracked source bytes: "
                f"{shlex.join(command)} exited {result.returncode}"
            )


def _committed_source_identity(
    source_root: Path, *, require_clean: bool
) -> tuple[str, str]:
    revision = _git_output(
        source_root, "rev-parse", "--verify", "HEAD"
    ).decode("ascii", errors="replace").strip()
    if GIT_OBJECT_ID.fullmatch(revision) is None:
        raise ReleaseCheckError(
            f"committed release source revision is malformed: {revision!r}"
        )
    tree = _git_output(
        source_root, "rev-parse", "--verify", f"{revision}^{{tree}}"
    ).decode("ascii", errors="replace").strip()
    if GIT_OBJECT_ID.fullmatch(tree) is None:
        raise ReleaseCheckError(
            f"committed release source tree is malformed: {tree!r}"
        )
    if require_clean:
        _require_clean_git_source(source_root)
    return revision, tree


def _revalidate_git_source_snapshot(
    source_root: Path, snapshot: GitSourceSnapshot
) -> None:
    if (
        snapshot.kind != "git_commit"
        or snapshot.revision is None
        or snapshot.tree is None
    ):
        raise ReleaseCheckError(
            "final release evidence requires a committed Git source snapshot"
        )
    revision, tree = _committed_source_identity(
        source_root, require_clean=True
    )
    if revision != snapshot.revision or tree != snapshot.tree:
        raise ReleaseCheckError(
            "committed release source changed during verification: "
            f"{snapshot.revision}/{snapshot.tree} != {revision}/{tree}"
        )


def _local_source_revision(
    source_root: Path, *, require_committed_source: bool
) -> str:
    revision, _ = _committed_source_identity(
        source_root, require_clean=require_committed_source
    )
    return revision


def check_github_release_surfaces(
    source_root: Path,
    *,
    require_published_source: bool,
    local_revision: str | None = None,
) -> dict[str, object]:
    if local_revision is None:
        local_revision = _local_source_revision(
            source_root,
            require_committed_source=require_published_source,
        )
    repository = _read_hosted_json(GITHUB_API_ROOT)
    private_reporting = _read_hosted_json(
        f"{GITHUB_API_ROOT}/private-vulnerability-reporting"
    )
    branch = _read_hosted_json(
        f"{GITHUB_API_ROOT}/branches/{GITHUB_DEFAULT_BRANCH}"
    )
    evidence = validate_github_release_surfaces(
        repository,
        private_reporting,
        branch,
        local_revision=local_revision,
        require_published_source=require_published_source,
    )
    evidence["status"] = "passed"
    print(json.dumps(evidence, indent=2, sort_keys=True), flush=True)
    return evidence


def check_distribution(
    source_root: Path,
    *,
    run_package_contract: bool = False,
    source_snapshot: GitSourceSnapshot | None = None,
) -> dict[str, object]:
    source_root = source_root.resolve()
    with tempfile.TemporaryDirectory(prefix="ucf-release-distribution-") as raw:
        scratch = Path(raw)
        source_only = scratch / "source-only"
        captured_snapshot = _copy_source_only(
            source_root,
            source_only,
            source_snapshot=source_snapshot,
        )
        configuration = tomllib.loads(
            (source_only / "pyproject.toml").read_text(encoding="utf-8")
        )
        version = configuration["project"]["version"]
        if not re.fullmatch(r"0\.1\.\d+", version):
            raise ReleaseCheckError(
                "release version is not in the accepted 0.1.x preview line: "
                f"{version!r}"
            )
        selected_source_manifest = _source_file_manifest(source_only)

        source_only_sdist = _build_sdist(
            source_only, scratch / "source-only-dist"
        )
        populated_sdist = _build_sdist(
            source_root, scratch / "dependency-populated-dist"
        )
        source_only_evidence, source_only_manifest = _inspect_sdist_contents(
            source_only_sdist, expected_version=version
        )
        populated_evidence, populated_manifest = _inspect_sdist_contents(
            populated_sdist, expected_version=version
        )
        validate_sdist_source_manifest(
            selected_source_manifest, source_only_manifest
        )
        validate_sdist_source_manifest(
            selected_source_manifest, populated_manifest
        )
        source_only_evidence["source_manifest_sha256"] = _manifest_sha256(
            source_only_manifest
        )
        populated_evidence["source_manifest_sha256"] = _manifest_sha256(
            populated_manifest
        )
        if source_only_evidence != populated_evidence:
            raise ReleaseCheckError(
                "source-only and dependency-populated sdist evidence differs: "
                f"{source_only_evidence!r} != {populated_evidence!r}"
            )

        extracted = _extract_sdist(source_only_sdist, scratch / "extracted")
        wheel = _build_wheel(extracted, scratch / "wheel-from-sdist")
        wheel_evidence = inspect_wheel(wheel, expected_version=version)
        installation_environments = _verify_installs(
            wheel,
            source_root=extracted,
            scratch_root=scratch,
            expected_version=version,
        )
        package_contract_evidence: dict[str, object] = {
            "source": "source_distribution",
            "performed": run_package_contract,
        }
        if run_package_contract:
            _run(
                (
                    "uv",
                    "run",
                    "--locked",
                    "python",
                    "tools/package_contract.py",
                ),
                cwd=extracted,
            )
            package_contract_evidence["status"] = "passed"

        source_evidence: dict[str, object] = {
            "kind": captured_snapshot.kind if captured_snapshot else "filesystem",
            "selected_file_count": len(selected_source_manifest),
            "selected_manifest_sha256": _manifest_sha256(
                selected_source_manifest
            ),
        }
        if captured_snapshot is not None:
            source_evidence["git_object_manifest_sha256"] = _manifest_sha256(
                {
                    entry.path.as_posix(): (
                        f"{entry.mode}:{entry.object_id}"
                    )
                    for entry in captured_snapshot.entries
                }
            )
            if captured_snapshot.revision is not None:
                source_evidence["revision"] = captured_snapshot.revision
            if captured_snapshot.tree is not None:
                source_evidence["tree"] = captured_snapshot.tree

        evidence = {
            "schema_version": 1,
            "source_snapshot": source_evidence,
            "status": "passed",
            "source_distributions": {
                "dependency_populated": populated_evidence,
                "identical": True,
                "source_only": source_only_evidence,
            },
            "wheel_from_source_distribution": wheel_evidence,
            "minimum_requirements": list(_minimum_requirements(extracted)),
            "installation_environments": installation_environments,
            "package_contract": package_contract_evidence,
        }
        print(json.dumps(evidence, indent=2, sort_keys=True), flush=True)
        return evidence


def _parse_args(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the bounded UCF source distribution, metadata, installed "
            "wheel, dependency floors, and existing package contract."
        )
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Source checkout to verify (default: repository root).",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Optional JSON path for retained distribution evidence.",
    )
    parser.add_argument(
        "--distribution-only",
        action="store_true",
        help="Do not repeat the existing wheel/package scenario contract.",
    )
    parser.add_argument(
        "--installed-python-license-inventory",
        type=Path,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(arguments)


def _invalidate_release_evidence(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory = os.open(path.parent, directory_flags)
    try:
        try:
            metadata = os.stat(
                path.name,
                dir_fd=directory,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        if stat.S_ISDIR(metadata.st_mode):
            raise ReleaseCheckError(
                f"release evidence path is a directory: {path}"
            )
        os.unlink(path.name, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)


def _read_existing_release_evidence(
    *, directory: int, name: str, expected: bytes
) -> None:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags | no_follow, dir_fd=directory)
    except OSError as exc:
        raise ReleaseCheckError(
            f"cannot safely open concurrently published evidence: {name}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size != len(expected)
        ):
            raise ReleaseCheckError(
                f"release evidence path was concurrently changed: {name}"
            )

        def read_candidate() -> bytes:
            os.lseek(descriptor, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            bytes_read = 0
            while bytes_read <= len(expected):
                chunk = os.read(
                    descriptor,
                    min(1024 * 1024, len(expected) + 1 - bytes_read),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                bytes_read += len(chunk)
            return b"".join(chunks)

        actual = read_candidate()
        try:
            entry_metadata = os.stat(
                name,
                dir_fd=directory,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise ReleaseCheckError(
                f"release evidence path was concurrently changed: {name}"
            ) from exc
        repeated = read_candidate()
        final_metadata = os.fstat(descriptor)
        stable_fields = (
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_gid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        descriptor_stable = all(
            getattr(metadata, field) == getattr(final_metadata, field)
            for field in stable_fields
        )
        same_entry = (
            entry_metadata.st_dev == metadata.st_dev
            and entry_metadata.st_ino == metadata.st_ino
            and final_metadata.st_dev == metadata.st_dev
            and final_metadata.st_ino == metadata.st_ino
            and stat.S_ISREG(entry_metadata.st_mode)
            and all(
                getattr(entry_metadata, field)
                == getattr(final_metadata, field)
                for field in stable_fields
            )
        )
        if (
            not descriptor_stable
            or not same_entry
            or actual != expected
            or repeated != expected
        ):
            raise ReleaseCheckError(
                f"release evidence path was concurrently changed: {name}"
            )
    finally:
        os.close(descriptor)


def _open_anonymous_evidence_file(directory: int) -> int:
    temporary_file_flag = getattr(os, "O_TMPFILE", 0)
    if temporary_file_flag == 0:
        raise ReleaseCheckError(
            "atomic release evidence publication requires Linux O_TMPFILE support"
        )
    flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | temporary_file_flag
    try:
        return os.open(".", flags, 0o644, dir_fd=directory)
    except OSError as exc:
        raise ReleaseCheckError(
            "atomic release evidence publication requires O_TMPFILE support "
            "from the evidence filesystem"
        ) from exc


def _link_anonymous_evidence_file(
    *, descriptor: int, directory: int, name: str
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    link_at = getattr(library, "linkat", None)
    if link_at is None:
        raise ReleaseCheckError(
            "atomic release evidence publication requires Linux linkat support"
        )
    link_at.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    )
    link_at.restype = ctypes.c_int
    result = link_at(
        descriptor,
        b"",
        directory,
        os.fsencode(name),
        0x1000,  # AT_EMPTY_PATH
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), name)
    if error_number in {
        errno.EINVAL,
        errno.ENOSYS,
        errno.EOPNOTSUPP,
        getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
        errno.EPERM,
    }:
        raise ReleaseCheckError(
            "atomic release evidence publication requires O_TMPFILE/linkat "
            "support from the evidence filesystem"
        )
    raise OSError(error_number, os.strerror(error_number), name)


def _publish_release_evidence(path: Path, evidence: Mapping[str, object]) -> None:
    serialized = (
        json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory = os.open(path.parent, directory_flags)
    descriptor: int | None = None
    try:
        descriptor = _open_anonymous_evidence_file(directory)
        remaining = memoryview(serialized)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("release evidence staging write made no progress")
            remaining = remaining[written:]
        os.fchmod(descriptor, 0o644)
        os.fsync(descriptor)
        try:
            _link_anonymous_evidence_file(
                descriptor=descriptor,
                directory=directory,
                name=path.name,
            )
        except FileExistsError as exc:
            try:
                _read_existing_release_evidence(
                    directory=directory,
                    name=path.name,
                    expected=serialized,
                )
            except ReleaseCheckError as collision:
                raise collision from exc
        try:
            os.fsync(directory)
        except OSError as exc:
            raise ReleaseCheckError(
                "release evidence committed_durability_unknown: complete "
                "evidence is visible but directory durability was not confirmed"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def _check_local_release(
    source_root: Path,
    *,
    distribution_only: bool,
    source_snapshot: GitSourceSnapshot | None,
) -> dict[str, object]:
    def run(dependency_source_root: Path) -> dict[str, object]:
        evidence = check_distribution(
            source_root,
            run_package_contract=not distribution_only,
            source_snapshot=source_snapshot,
        )
        if distribution_only:
            return evidence
        installation_environments = evidence.get("installation_environments")
        if not isinstance(installation_environments, Mapping):
            raise ReleaseCheckError(
                "distribution evidence has no installed environment inventories"
            )
        evidence["dependency_review"] = check_dependency_audits(
            dependency_source_root,
            installation_environments=installation_environments,
        )
        return evidence

    if source_snapshot is None:
        return run(source_root.resolve())

    with tempfile.TemporaryDirectory(
        prefix="ucf-release-committed-source-"
    ) as raw_snapshot_directory:
        dependency_source_root = (
            Path(raw_snapshot_directory) / "committed-source"
        )
        materialized_snapshot = _copy_source_only(
            source_root,
            dependency_source_root,
            source_snapshot=source_snapshot,
        )
        if materialized_snapshot != source_snapshot:
            raise ReleaseCheckError(
                "dependency audit source differs from captured Git snapshot"
            )
        return run(dependency_source_root)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(arguments or sys.argv[1:])
    try:
        if args.evidence is not None:
            _invalidate_release_evidence(args.evidence)
        if args.installed_python_license_inventory is not None:
            if args.evidence is not None:
                raise ReleaseCheckError(
                    "installed inventory mode cannot publish final release evidence"
                )
            _write_installed_python_license_inventory(
                args.installed_python_license_inventory
            )
            return 0
        if args.distribution_only and args.evidence is not None:
            raise ReleaseCheckError(
                "distribution-only checks cannot publish final release evidence"
            )
        source_snapshot = (
            _capture_git_source_snapshot(
                args.source_root,
                require_committed_source=True,
            )
            if args.evidence is not None
            else None
        )
        evidence = _check_local_release(
            args.source_root,
            distribution_only=args.distribution_only,
            source_snapshot=source_snapshot,
        )
        if not args.distribution_only:
            evidence["hosted_release_surfaces"] = (
                check_github_release_surfaces(
                    args.source_root,
                    require_published_source=args.evidence is not None,
                    local_revision=(
                        source_snapshot.revision
                        if source_snapshot is not None
                        else None
                    ),
                )
            )
        if args.evidence is not None:
            if source_snapshot is None:
                raise ReleaseCheckError(
                    "final release evidence has no committed source snapshot"
                )
            _revalidate_git_source_snapshot(args.source_root, source_snapshot)
            _publish_release_evidence(args.evidence, evidence)
    except (OSError, ReleaseCheckError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"release distribution check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
