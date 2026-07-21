from __future__ import annotations

import json
import subprocess
import tomllib
from email.message import Message
from pathlib import Path

import pytest
import tools.release_check as release_check
from tools.release_check import (
    MAX_SDIST_BYTES,
    REQUIRED_SDIST_MEMBERS,
    ReleaseCheckError,
    validate_sdist_member_paths,
    validate_sdist_source_manifest,
)
from typer.testing import CliRunner

from ucf import __version__
from ucf.cli import app

ROOT = Path(__file__).resolve().parents[2]
RUNNER = CliRunner()


def _configuration() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _numeric_version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def test_preview_distribution_metadata_and_supported_dependency_floors_are_explicit():
    configuration = _configuration()
    project = configuration["project"]

    assert project["version"].startswith("0.1.")
    assert project["readme"] == "README.md"
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    assert project["authors"] == [{"name": "Deliner"}]
    assert project["maintainers"] == [{"name": "Deliner"}]
    assert project["classifiers"] == [
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
    ]
    assert project["urls"] == {
        "Documentation": "https://github.com/Deliner/UCF/tree/main/docs",
        "Repository": "https://github.com/Deliner/UCF",
        "Security": "https://github.com/Deliner/UCF/security/advisories/new",
        "Support": "https://github.com/Deliner/UCF/issues",
    }
    assert project["dependencies"] == [
        "pydantic>=2.0",
        "pyyaml>=6.0.1",
        "typer>=0.16.0",
        "networkx>=3.0",
        "rich>=13.0",
        "jinja2>=3.1",
    ]
    assert "pip-audit==2.10.1" in project["optional-dependencies"]["dev"]
    assert configuration["build-system"]["requires"] == [
        "hatchling==1.31.0",
        "packaging==26.2",
        "pathspec==1.1.1",
        "pluggy==1.6.0",
        "trove-classifiers==2026.6.1.19",
    ]


def test_package_version_is_one_diagnostic_contract():
    configuration = _configuration()
    result = RUNNER.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"ucf {__version__}\n"
    assert configuration["project"]["version"] == __version__

    web_source = (ROOT / "src/ucf/web/app.py").read_text(encoding="utf-8")
    adapter_source = (
        ROOT / "src/ucf/adapter_protocol/process.py"
    ).read_text(encoding="utf-8")
    assert "from ucf import __version__" in web_source
    assert "version=__version__" in web_source
    assert 'version="0.1.0"' not in web_source
    assert "from ucf import __version__" in adapter_source
    assert "version=__version__" in adapter_source
    assert 'version="0.1.0"' not in adapter_source


def test_clean_install_rejects_cli_version_drift(tmp_path, monkeypatch):
    environment = tmp_path / "environment"
    (environment / "bin").mkdir(parents=True)

    def run(command, **_kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ucf 0.1.999\n",
            )
        return subprocess.CompletedProcess(command, 0, stdout=None)

    monkeypatch.setattr(release_check.subprocess, "run", run)

    with pytest.raises(ReleaseCheckError, match="version drift"):
        release_check._run_installed_cli(
            environment,
            cwd=tmp_path,
            expected_version="0.1.0",
        )


def test_sdist_has_an_explicit_source_boundary_and_dependency_exclusions():
    configuration = _configuration()
    sdist = configuration["tool"]["hatch"]["build"]["targets"]["sdist"]

    assert sdist["reproducible"] is True
    assert sdist["skip-excluded-dirs"] is True
    assert set(sdist["only-include"]) >= {
        "adapters",
        "docs",
        "examples",
        "specs",
        "src",
        "tests",
        "tools",
        "web",
        "LICENSE",
        "NOTICE",
        "README.md",
        "SECURITY.md",
        "uv.lock",
    }
    assert set(sdist["exclude"]) >= {
        "/.cursor/settings.json",
        "**/.artifacts/",
        "**/.DS_Store",
        "**/.env",
        "**/.env.*",
        "**/.netrc",
        "**/.npmrc",
        "**/.pypirc",
        "**/.venv/",
        "**/__pycache__/",
        "**/id_ed25519",
        "**/id_rsa",
        "**/*.key",
        "**/*.jks",
        "**/*.keystore",
        "**/*.p12",
        "**/*.pfx",
        "**/*.pem",
        "**/build/",
        "**/dist/",
        "**/htmlcov/",
        "**/node_modules/",
        "**/.coverage",
        "**/.pytest_cache/",
        "**/.ruff_cache/",
        "**/*.egg-info/",
        "**/*.py[cod]",
    }

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert {
        ".env",
        ".env.*",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "id_ed25519",
        "id_rsa",
        "*.jks",
        "*.key",
        "*.keystore",
        "*.p12",
        "*.pfx",
        "*.pem",
    } <= set(ignored)


def test_lock_keeps_the_known_python_runtime_advisories_closed():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {package["name"]: package["version"] for package in lock["package"]}
    fixed_floors = {
        "click": "8.3.3",
        "idna": "3.15",
        "pygments": "2.20.0",
        "python-dotenv": "1.2.2",
        "starlette": "1.3.1",
    }

    for package, fixed_floor in fixed_floors.items():
        assert _numeric_version(versions[package]) >= _numeric_version(fixed_floor)


def test_release_check_rejects_dependency_populated_and_unbounded_sdists():
    valid_members = sorted(REQUIRED_SDIST_MEMBERS)

    with pytest.raises(ReleaseCheckError, match="forbidden directory"):
        validate_sdist_member_paths(
            [*valid_members, "web/node_modules/react/index.js"],
            archive_size=MAX_SDIST_BYTES,
        )

    with pytest.raises(ReleaseCheckError, match="size limit"):
        validate_sdist_member_paths(
            valid_members,
            archive_size=MAX_SDIST_BYTES + 1,
        )


def test_release_check_rejects_incomplete_or_unsafe_source_manifests():
    missing_tests = sorted(REQUIRED_SDIST_MEMBERS - {"tests/__init__.py"})

    with pytest.raises(ReleaseCheckError, match="required source members"):
        validate_sdist_member_paths(missing_tests, archive_size=1)

    with pytest.raises(ReleaseCheckError, match="unsafe archive member"):
        validate_sdist_member_paths(
            [*sorted(REQUIRED_SDIST_MEMBERS), "../outside"],
            archive_size=1,
        )


def test_release_check_rejects_any_omitted_or_changed_selected_source():
    selected_source = {
        "src/ucf/__init__.py": "source-digest",
        "tests/test_contract.py": "test-digest",
    }

    with pytest.raises(ReleaseCheckError, match="omits selected source"):
        validate_sdist_source_manifest(
            selected_source,
            {"src/ucf/__init__.py": "source-digest"},
        )

    with pytest.raises(ReleaseCheckError, match="changes selected source"):
        validate_sdist_source_manifest(
            selected_source,
            {
                "src/ucf/__init__.py": "different-digest",
                "tests/test_contract.py": "test-digest",
            },
        )


def test_source_only_manifest_uses_git_index_not_untracked_checkout_files(
    tmp_path,
):
    source_root = tmp_path / "checkout"
    target_root = tmp_path / "source-only"
    (source_root / "src").mkdir(parents=True)
    (source_root / ".gitignore").write_text("*.secret\n", encoding="utf-8")
    (source_root / "pyproject.toml").write_text(
        """
[tool.hatch.build.targets.sdist]
only-include = ["src"]
""".lstrip(),
        encoding="utf-8",
    )
    (source_root / "src" / "tracked.py").write_text(
        "TRACKED = True\n", encoding="utf-8"
    )
    (source_root / "src" / "credentials.secret").write_text(
        "must-not-ship\n", encoding="utf-8"
    )
    subprocess.run(
        ("git", "init", "--quiet", str(source_root)),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(source_root),
            "add",
            ".gitignore",
            "pyproject.toml",
            "src/tracked.py",
        ),
        check=True,
    )

    release_check._copy_source_only(source_root, target_root)

    assert (target_root / "src" / "tracked.py").is_file()
    assert not (target_root / "src" / "credentials.secret").exists()


def test_failed_sdist_package_contract_publishes_no_release_evidence(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    calls = []

    def fail_distribution(_root, *, run_package_contract):
        calls.append(run_package_contract)
        raise ReleaseCheckError("package contract failed in extracted sdist")

    monkeypatch.setattr(release_check, "check_distribution", fail_distribution)

    assert release_check.main(["--evidence", str(evidence_path)]) == 1
    assert calls == [True]
    assert not evidence_path.exists()


def test_dependency_audits_cover_every_lock_without_waivers(tmp_path):
    commands = release_check.dependency_audit_commands(ROOT, tmp_path)
    flattened = [argument for command in commands for argument in command]

    assert "pip-audit" in flattened
    assert "--require-hashes" in flattened
    assert "--strict" in flattened
    assert sum(command[:2] == ("npm", "audit") for command in commands) == 4
    assert not {
        "--audit-level",
        "--fix",
        "--force",
        "--ignore-vuln",
        "--legacy-peer-deps",
    }.intersection(flattened)


def test_dependency_inventory_rejects_missing_or_unreviewed_npm_licenses():
    missing = {
        "packages": {
            "": {"name": "private-root", "private": True},
            "node_modules/missing": {"name": "missing", "version": "1.0.0"},
        }
    }
    unreviewed = {
        "packages": {
            "": {"name": "private-root", "private": True},
            "node_modules/unreviewed": {
                "name": "unreviewed",
                "version": "1.0.0",
                "license": "UNKNOWN-CUSTOM",
            },
        }
    }

    with pytest.raises(ReleaseCheckError, match="missing license"):
        release_check.validate_npm_lock_inventory(missing, label="fixture")
    with pytest.raises(ReleaseCheckError, match="unreviewed licenses"):
        release_check.validate_npm_lock_inventory(unreviewed, label="fixture")


def test_python_audit_report_rejects_any_advisory():
    report = {
        "dependencies": [
            {
                "name": "unsafe",
                "version": "1.0.0",
                "vulns": [{"id": "PYSEC-TEST", "fix_versions": ["1.0.1"]}],
            }
        ],
        "fixes": [],
    }

    with pytest.raises(ReleaseCheckError, match="known vulnerabilities"):
        release_check.validate_python_audit_report(report, label="runtime")


def test_hosted_release_surface_requires_enabled_private_reporting():
    repository = {
        "default_branch": "main",
        "full_name": "Deliner/UCF",
        "has_issues": True,
        "private": False,
    }

    with pytest.raises(ReleaseCheckError, match="not enabled"):
        release_check.validate_github_release_surfaces(
            repository,
            {"enabled": False},
        )


def test_python_license_inventory_rejects_an_unreviewed_identity():
    metadata = Message()
    metadata["Name"] = "unknown-license-package"
    metadata["License-Expression"] = "LicenseRef-Proprietary-Unknown"

    with pytest.raises(ReleaseCheckError, match="unreviewed Python license"):
        release_check.python_license_identity(metadata)


def test_full_release_evidence_includes_dependency_and_hosted_checks(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    calls = []
    monkeypatch.setattr(
        release_check,
        "check_distribution",
        lambda _root, *, run_package_contract: {
            "schema_version": 1,
            "status": "passed",
        },
    )
    monkeypatch.setattr(
        release_check,
        "check_dependency_audits",
        lambda _root: calls.append("dependencies") or {"status": "passed"},
        raising=False,
    )
    monkeypatch.setattr(
        release_check,
        "check_github_release_surfaces",
        lambda: calls.append("hosted") or {"status": "passed"},
        raising=False,
    )

    assert release_check.main(["--evidence", str(evidence_path)]) == 0
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert calls == ["dependencies", "hosted"]
    assert evidence["dependency_review"] == {"status": "passed"}
    assert evidence["hosted_release_surfaces"] == {"status": "passed"}
