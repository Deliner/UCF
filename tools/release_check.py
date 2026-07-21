from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from collections import Counter
from collections.abc import Mapping, Sequence
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from importlib.metadata import distributions
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MAX_SDIST_BYTES = 5 * 1024 * 1024
MAX_SDIST_MEMBERS = 2_000

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
        "jinja2>=3.1",
        "networkx>=3.0",
        "pydantic>=2.0",
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


class ReleaseCheckError(RuntimeError):
    """Raised when a releasable distribution invariant is false."""


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
    return {
        "dependencies": inventory,
        "dependency_count": len(inventory),
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
    if private_reporting.get("enabled") is not True:
        raise ReleaseCheckError(
            "GitHub Private Vulnerability Reporting is not enabled"
        )
    return {
        "default_branch": GITHUB_DEFAULT_BRANCH,
        "issues": "enabled",
        "private_vulnerability_reporting": "enabled",
        "repository": GITHUB_REPOSITORY,
        "visibility": "public",
    }


def _safe_member_path(raw_path: str) -> PurePosixPath:
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or "\\" in raw_path
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ReleaseCheckError(f"unsafe archive member: {raw_path!r}")
    return path


def validate_sdist_member_paths(
    relative_paths: Sequence[str], *, archive_size: int
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

    normalized_paths: set[str] = set()
    for raw_path in relative_paths:
        path = _safe_member_path(raw_path)
        normalized_paths.add(path.as_posix())
        if path.parts[0] not in ALLOWED_SDIST_ROOTS:
            raise ReleaseCheckError(
                f"sdist has an unapproved root member: {raw_path}"
            )
        forbidden_directory = next(
            (
                part
                for part in path.parts[:-1]
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
        if path.name == ".coverage" or path.suffix in {".pyc", ".pyo"}:
            raise ReleaseCheckError(
                f"sdist contains generated local state: {raw_path}"
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


def _sdist_source_manifest(
    archive_path: Path, *, expected_version: str
) -> dict[str, str]:
    manifest: dict[str, str] = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        files = [member for member in archive.getmembers() if member.isfile()]
        _, relative_paths = _strip_sdist_root(
            [member.name for member in files],
            expected_version=expected_version,
        )
        for member, relative_path in zip(files, relative_paths, strict=True):
            if relative_path == "PKG-INFO":
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ReleaseCheckError(
                    f"cannot read sdist source member: {member.name}"
                )
            manifest[relative_path] = _sha256_bytes(stream.read())
    return manifest


def _strip_sdist_root(
    member_names: Sequence[str], *, expected_version: str
) -> tuple[str, tuple[str, ...]]:
    safe_names = tuple(_safe_member_path(name) for name in member_names)
    roots = {path.parts[0] for path in safe_names}
    if len(roots) != 1:
        raise ReleaseCheckError(
            f"sdist must have one archive root, found: {sorted(roots)}"
        )
    [root] = roots
    expected_root = f"ucf-{expected_version}"
    if root != expected_root:
        raise ReleaseCheckError(f"unexpected sdist archive root: {root!r}")
    return root, tuple(
        PurePosixPath(*path.parts[1:]).as_posix() for path in safe_names
    )


def inspect_sdist(
    archive_path: Path, *, expected_version: str
) -> dict[str, object]:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        unsupported = [
            member.name
            for member in members
            if not (member.isfile() or member.isdir())
        ]
        if unsupported:
            raise ReleaseCheckError(
                f"sdist contains links or special files: {unsupported}"
            )
        files = [member for member in members if member.isfile()]
        _, relative_paths = _strip_sdist_root(
            [member.name for member in files],
            expected_version=expected_version,
        )
        validate_sdist_member_paths(
            relative_paths, archive_size=archive_path.stat().st_size
        )
        [metadata_member] = [
            member for member in files if member.name.endswith("/PKG-INFO")
        ]
        metadata_stream = archive.extractfile(metadata_member)
        if metadata_stream is None:
            raise ReleaseCheckError("cannot read sdist PKG-INFO")
        metadata = BytesParser(policy=default).parsebytes(metadata_stream.read())
        validate_core_metadata(metadata, expected_version=expected_version)

    return {
        "bytes": archive_path.stat().st_size,
        "file_members": len(relative_paths),
        "sha256": _sha256(archive_path),
    }


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


def _configured_sdist_inputs(source_root: Path) -> tuple[str, ...]:
    configuration = tomllib.loads(
        (source_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    sdist = configuration["tool"]["hatch"]["build"]["targets"]["sdist"]
    return tuple(
        dict.fromkeys([".gitignore", "pyproject.toml", *sdist["only-include"]])
    )


def _git_index_source_files(
    source_root: Path, *, selected_inputs: Sequence[str]
) -> tuple[PurePosixPath, ...]:
    command = ("git", "-C", str(source_root), "ls-files", "--cached", "-z")
    print(f"$ {shlex.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseCheckError(
            "cannot read the Git index used as the release source boundary: "
            f"{detail or f'exit {completed.returncode}'}"
        )

    selected_paths = tuple(PurePosixPath(value) for value in selected_inputs)
    included: list[PurePosixPath] = []
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = _safe_member_path(os.fsdecode(raw_path))
        if any(
            path == selected or selected in path.parents
            for selected in selected_paths
        ):
            included.append(path)
    if not included:
        raise ReleaseCheckError(
            "Git index contains no selected source-distribution files"
        )
    return tuple(sorted(included, key=PurePosixPath.as_posix))


def _copy_source_only(source_root: Path, target_root: Path) -> None:
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

    if (source_root / ".git").exists():
        for relative_path in _git_index_source_files(
            source_root, selected_inputs=selected
        ):
            source = source_root.joinpath(*relative_path.parts)
            target = target_root.joinpath(*relative_path.parts)
            if not source.is_file():
                raise ReleaseCheckError(
                    "Git-indexed source-distribution input is missing or not a file: "
                    f"{relative_path.as_posix()}"
                )
            if source.is_symlink():
                raise ReleaseCheckError(
                    "Git-indexed source-distribution input is a symlink: "
                    f"{relative_path.as_posix()}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return

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
) -> None:
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


def check_dependency_audits(source_root: Path) -> dict[str, object]:
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


def check_github_release_surfaces() -> dict[str, object]:
    repository = _read_hosted_json(GITHUB_API_ROOT)
    private_reporting = _read_hosted_json(
        f"{GITHUB_API_ROOT}/private-vulnerability-reporting"
    )
    evidence = validate_github_release_surfaces(repository, private_reporting)
    evidence["status"] = "passed"
    print(json.dumps(evidence, indent=2, sort_keys=True), flush=True)
    return evidence


def check_distribution(
    source_root: Path, *, run_package_contract: bool = False
) -> dict[str, object]:
    source_root = source_root.resolve()
    configuration = tomllib.loads(
        (source_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    version = configuration["project"]["version"]
    if not re.fullmatch(r"0\.1\.\d+", version):
        raise ReleaseCheckError(
            f"release version is not in the accepted 0.1.x preview line: {version!r}"
        )
    with tempfile.TemporaryDirectory(prefix="ucf-release-distribution-") as raw:
        scratch = Path(raw)
        source_only = scratch / "source-only"
        _copy_source_only(source_root, source_only)
        selected_source_manifest = _source_file_manifest(source_only)

        source_only_sdist = _build_sdist(
            source_only, scratch / "source-only-dist"
        )
        populated_sdist = _build_sdist(
            source_root, scratch / "dependency-populated-dist"
        )
        source_only_evidence = inspect_sdist(
            source_only_sdist, expected_version=version
        )
        populated_evidence = inspect_sdist(
            populated_sdist, expected_version=version
        )
        source_only_manifest = _sdist_source_manifest(
            source_only_sdist, expected_version=version
        )
        populated_manifest = _sdist_source_manifest(
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

        extracted = _extract_sdist(populated_sdist, scratch / "extracted")
        wheel = _build_wheel(extracted, scratch / "wheel-from-sdist")
        wheel_evidence = inspect_wheel(wheel, expected_version=version)
        _verify_installs(
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

        evidence = {
            "schema_version": 1,
            "status": "passed",
            "source_distributions": {
                "dependency_populated": populated_evidence,
                "identical": True,
                "source_only": source_only_evidence,
            },
            "wheel_from_source_distribution": wheel_evidence,
            "minimum_requirements": list(_minimum_requirements(extracted)),
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


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(arguments or sys.argv[1:])
    try:
        if args.installed_python_license_inventory is not None:
            _write_installed_python_license_inventory(
                args.installed_python_license_inventory
            )
            return 0
        evidence = check_distribution(
            args.source_root,
            run_package_contract=not args.distribution_only,
        )
        if not args.distribution_only:
            evidence["dependency_review"] = check_dependency_audits(
                args.source_root
            )
            evidence["hosted_release_surfaces"] = (
                check_github_release_surfaces()
            )
        if args.evidence is not None:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (OSError, ReleaseCheckError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"release distribution check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
