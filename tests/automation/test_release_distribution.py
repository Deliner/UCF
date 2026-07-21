from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import sys
import tarfile
import tomllib
from email.message import Message
from pathlib import Path

import pytest
import tools.release_check as release_check
from tools.release_check import (
    MAX_SDIST_BYTES,
    MAX_SDIST_MEMBERS,
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
        "pydantic>=2.4.0",
        "pyyaml>=6.0.1",
        "typer>=0.16.0",
        "networkx>=3.0",
        "rich>=13.0",
        "jinja2>=3.1.6",
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
        "**/id_ecdsa",
        "**/id_rsa",
        "**/.aws/",
        "**/.ssh/",
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
        "id_ecdsa",
        "id_rsa",
        ".aws/",
        ".ssh/",
        "node_modules/",
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

    oversized_member_sizes = {path: 1 for path in valid_members}
    oversized_member_sizes[valid_members[0]] = 6 * 1024 * 1024
    with pytest.raises(ReleaseCheckError, match="uncompressed member size"):
        validate_sdist_member_paths(
            valid_members,
            archive_size=1,
            member_sizes=oversized_member_sizes,
        )

    oversized_total_sizes = {path: 1 for path in valid_members}
    for path in valid_members[:6]:
        oversized_total_sizes[path] = 5 * 1024 * 1024
    with pytest.raises(ReleaseCheckError, match="total uncompressed size"):
        validate_sdist_member_paths(
            valid_members,
            archive_size=1,
            member_sizes=oversized_total_sizes,
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

    for alias in ("src//ucf/__init__.py", "src/./ucf/__init__.py"):
        with pytest.raises(ReleaseCheckError, match="unsafe archive member"):
            validate_sdist_member_paths(
                [*sorted(REQUIRED_SDIST_MEMBERS), alias],
                archive_size=1,
            )


def test_sdist_rejects_directory_member_amplification_before_file_validation(
    tmp_path,
):
    archive_path = tmp_path / "amplified.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for index in range(MAX_SDIST_MEMBERS + 1):
            member = tarfile.TarInfo(f"ucf-0.1.0/docs/empty-{index}/")
            member.type = tarfile.DIRTYPE
            member.mode = 0o755
            archive.addfile(member)

    with pytest.raises(ReleaseCheckError, match="member limit"):
        release_check.inspect_sdist(archive_path, expected_version="0.1.0")


def test_sdist_rejects_unsafe_directory_member_paths(tmp_path):
    archive_path = tmp_path / "unsafe-directory.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("ucf-0.1.0/unsafe/../outside/")
        member.type = tarfile.DIRTYPE
        member.mode = 0o755
        archive.addfile(member)

    with pytest.raises(ReleaseCheckError, match="unsafe archive member"):
        release_check.inspect_sdist(archive_path, expected_version="0.1.0")


def _write_minimal_valid_sdist(archive_path: Path) -> None:
    metadata_lines = [
        "Metadata-Version: 2.4",
        "Name: ucf",
        "Version: 0.1.0",
        "Requires-Python: >=3.12",
        "License-Expression: Apache-2.0",
        "Author: Deliner",
        "Maintainer: Deliner",
        "Description-Content-Type: text/markdown",
        "License-File: LICENSE",
        "License-File: NOTICE",
        *(
            f"Classifier: {classifier}"
            for classifier in sorted(release_check.EXPECTED_CLASSIFIERS)
        ),
        *(
            f"Project-URL: {project_url}"
            for project_url in sorted(release_check.EXPECTED_PROJECT_URLS)
        ),
        *(
            f"Requires-Dist: {requirement}"
            for requirement in sorted(
                release_check.EXPECTED_RUNTIME_REQUIREMENTS
            )
        ),
        "",
        "fixture",
    ]
    metadata = "\n".join(metadata_lines).encode("utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        for relative_path in sorted(REQUIRED_SDIST_MEMBERS):
            payload = metadata if relative_path == "PKG-INFO" else b"fixture\n"
            member = tarfile.TarInfo(f"ucf-0.1.0/{relative_path}")
            member.mode = 0o644
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))


def test_sdist_rejects_a_concatenated_gzip_member_over_stream_limit(tmp_path):
    archive_path = tmp_path / "concatenated.tar.gz"
    _write_minimal_valid_sdist(archive_path)
    with gzip.open(archive_path, "ab") as trailing_member:
        for _ in range(
            release_check.MAX_SDIST_TAR_STREAM_BYTES // (1024 * 1024) + 1
        ):
            trailing_member.write(b"x" * (1024 * 1024))

    with pytest.raises(ReleaseCheckError, match="decompressed stream limit"):
        release_check.inspect_sdist(archive_path, expected_version="0.1.0")


def test_sdist_rejects_a_corrupt_concatenated_gzip_member(tmp_path):
    archive_path = tmp_path / "corrupt-concatenated.tar.gz"
    _write_minimal_valid_sdist(archive_path)
    with gzip.open(archive_path, "ab") as trailing_member:
        trailing_member.write(b"unexpected trailing stream" * 1024)
    payload = archive_path.read_bytes()
    archive_path.write_bytes(payload[:-1] + bytes([payload[-1] ^ 0xFF]))

    with pytest.raises(ReleaseCheckError, match="invalid gzip stream"):
        release_check.inspect_sdist(archive_path, expected_version="0.1.0")


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
    (source_root / ".gitattributes").write_text(
        "src/tracked.py filter=rewrite\n", encoding="utf-8"
    )
    (source_root / "pyproject.toml").write_text(
        """
[tool.hatch.build.targets.sdist]
only-include = ["src"]
""".lstrip(),
        encoding="utf-8",
    )
    (source_root / "src" / "tracked.py").write_text(
        'TOKEN = "safe-index-bytes"\n', encoding="utf-8"
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
            ".gitattributes",
            ".gitignore",
            "pyproject.toml",
            "src/tracked.py",
        ),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(source_root),
            "config",
            "filter.rewrite.smudge",
            "sed s/safe-index-bytes/smudged-filter-output/",
        ),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(source_root),
            "config",
            "filter.rewrite.clean",
            "cat",
        ),
        check=True,
    )
    (source_root / "src" / "tracked.py").write_text(
        'TOKEN = "unstaged-working-tree-secret"\n', encoding="utf-8"
    )

    release_check._copy_source_only(source_root, target_root)

    assert (target_root / "src" / "tracked.py").read_text(encoding="utf-8") == (
        'TOKEN = "safe-index-bytes"\n'
    )
    assert not (target_root / "src" / "credentials.secret").exists()


def test_committed_source_snapshot_binds_exported_bytes_to_captured_head(
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
    tracked = source_root / "src" / "tracked.py"
    tracked.write_text('TOKEN = "committed"\n', encoding="utf-8")
    subprocess.run(("git", "init", "--quiet", str(source_root)), check=True)
    subprocess.run(
        ("git", "-C", str(source_root), "config", "user.name", "Test"),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(source_root),
            "config",
            "user.email",
            "test@example.invalid",
        ),
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
    subprocess.run(
        ("git", "-C", str(source_root), "commit", "--quiet", "-m", "source"),
        check=True,
    )

    snapshot = release_check._capture_git_source_snapshot(
        source_root, require_committed_source=True
    )
    tracked.write_text('TOKEN = "forged"\n', encoding="utf-8")
    subprocess.run(
        ("git", "-C", str(source_root), "add", "src/tracked.py"), check=True
    )

    release_check._copy_source_only(
        source_root, target_root, source_snapshot=snapshot
    )

    assert (target_root / "src" / "tracked.py").read_text(encoding="utf-8") == (
        'TOKEN = "committed"\n'
    )
    assert snapshot.revision is not None
    assert snapshot.tree is not None


def test_failed_sdist_package_contract_publishes_no_release_evidence(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    evidence_path.write_text(
        '{"source":"stale","status":"passed"}\n', encoding="utf-8"
    )
    calls = []

    snapshot = release_check.GitSourceSnapshot(
        entries=(),
        kind="git_commit",
        revision="a" * 40,
        tree="b" * 40,
    )

    def fail_distribution(_root, *, run_package_contract, source_snapshot):
        calls.append(run_package_contract)
        assert source_snapshot == snapshot
        raise ReleaseCheckError("package contract failed in extracted sdist")

    monkeypatch.setattr(
        release_check,
        "_capture_git_source_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(release_check, "check_distribution", fail_distribution)

    assert release_check.main(["--evidence", str(evidence_path)]) == 1
    assert calls == [True]
    assert not evidence_path.exists()


def test_release_evidence_publication_is_atomic_and_create_only(tmp_path):
    evidence_path = tmp_path / "release-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    serialized = json.dumps(expected, indent=2, sort_keys=True) + "\n"

    evidence_path.write_text(serialized, encoding="utf-8")
    release_check._publish_release_evidence(evidence_path, expected)
    assert evidence_path.read_text(encoding="utf-8") == serialized

    evidence_path.write_text('{"status":"different"}\n', encoding="utf-8")
    with pytest.raises(ReleaseCheckError, match="concurrently changed"):
        release_check._publish_release_evidence(evidence_path, expected)
    assert evidence_path.read_text(encoding="utf-8") == (
        '{"status":"different"}\n'
    )


def test_release_evidence_publication_reports_a_post_commit_failure(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    real_fsync = os.fsync
    fsync_calls = 0

    def fail_first_directory_fsync(descriptor):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            raise OSError("injected directory fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr(release_check.os, "fsync", fail_first_directory_fsync)

    with pytest.raises(
        ReleaseCheckError, match="committed_durability_unknown"
    ):
        release_check._publish_release_evidence(evidence_path, expected)
    assert evidence_path.read_text(encoding="utf-8") == (
        json.dumps(expected, indent=2, sort_keys=True) + "\n"
    )


def test_release_evidence_post_commit_failure_preserves_an_identical_file(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    serialized = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    evidence_path.write_text(serialized, encoding="utf-8")
    real_fsync = os.fsync
    fsync_calls = 0

    def fail_first_directory_fsync(descriptor):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            raise OSError("injected directory fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr(release_check.os, "fsync", fail_first_directory_fsync)

    with pytest.raises(
        ReleaseCheckError, match="committed_durability_unknown"
    ):
        release_check._publish_release_evidence(evidence_path, expected)
    assert evidence_path.read_text(encoding="utf-8") == serialized


def test_release_evidence_post_commit_failure_preserves_replaced_destination(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    replacement = tmp_path / "concurrent-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    serialized = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    replacement.write_text(serialized, encoding="utf-8")
    real_fsync = os.fsync
    fsync_calls = 0

    def replace_destination_before_failure(descriptor):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            evidence_path.unlink()
            os.link(replacement, evidence_path)
            raise OSError("injected directory fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr(
        release_check.os, "fsync", replace_destination_before_failure
    )

    with pytest.raises(
        ReleaseCheckError, match="committed_durability_unknown"
    ):
        release_check._publish_release_evidence(evidence_path, expected)
    assert evidence_path.read_text(encoding="utf-8") == serialized
    assert evidence_path.stat().st_ino == replacement.stat().st_ino
    assert replacement.stat().st_nlink == 2


def test_release_evidence_post_commit_failure_never_starts_name_rollback(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    replacement = tmp_path / "concurrent-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    serialized = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    replacement.write_text(serialized, encoding="utf-8")
    real_fsync = os.fsync
    real_stat = os.stat
    fsync_calls = 0
    rollback_identity_checked = False

    def fail_post_commit_directory_fsync(descriptor):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            raise OSError("injected post-commit directory fsync failure")
        return real_fsync(descriptor)

    def swap_after_rollback_identity_check(path, *args, **kwargs):
        nonlocal rollback_identity_checked
        metadata = real_stat(path, *args, **kwargs)
        if (
            not rollback_identity_checked
            and path == evidence_path.name
            and kwargs.get("dir_fd") is not None
            and kwargs.get("follow_symlinks") is False
        ):
            evidence_path.unlink()
            os.link(replacement, evidence_path)
            rollback_identity_checked = True
        return metadata

    monkeypatch.setattr(
        release_check.os, "fsync", fail_post_commit_directory_fsync
    )
    monkeypatch.setattr(
        release_check.os, "stat", swap_after_rollback_identity_check
    )

    with pytest.raises(
        ReleaseCheckError, match="committed_durability_unknown"
    ):
        release_check._publish_release_evidence(evidence_path, expected)
    assert rollback_identity_checked is False
    assert evidence_path.read_text(encoding="utf-8") == serialized
    assert evidence_path.stat().st_ino != replacement.stat().st_ino
    assert replacement.stat().st_nlink == 1


def test_release_evidence_collision_rejects_fifo_without_blocking(tmp_path):
    evidence_path = tmp_path / "release-evidence.json"
    os.mkfifo(evidence_path)
    program = "\n".join(
        (
            "from pathlib import Path",
            (
                "from tools.release_check import "
                "ReleaseCheckError, _publish_release_evidence"
            ),
            f"path = Path({str(evidence_path)!r})",
            "try:",
            "    _publish_release_evidence(path, {'status': 'passed'})",
            "except ReleaseCheckError:",
            "    print('rejected')",
            "else:",
            "    raise SystemExit('FIFO collision was accepted')",
        )
    )

    result = subprocess.run(
        (sys.executable, "-c", program),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "rejected\n"


def test_release_evidence_collision_rejects_append_during_identity_check(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    serialized = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    evidence_path.write_text(serialized, encoding="utf-8")
    real_stat = os.stat
    appended = False

    def append_before_entry_metadata(path, *args, **kwargs):
        nonlocal appended
        if (
            not appended
            and path == evidence_path.name
            and kwargs.get("dir_fd") is not None
            and kwargs.get("follow_symlinks") is False
        ):
            with evidence_path.open("ab") as stream:
                stream.write(b'{"concurrent":true}\n')
                stream.flush()
            appended = True
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(release_check.os, "stat", append_before_entry_metadata)

    with pytest.raises(ReleaseCheckError, match="concurrently changed"):
        release_check._publish_release_evidence(evidence_path, expected)
    assert appended is True
    assert evidence_path.read_bytes() != serialized.encode("utf-8")


def test_release_evidence_invalidation_unlinks_symlink_without_touching_target(
    tmp_path,
):
    target = tmp_path / "old-evidence.json"
    target.write_text('{"status":"passed"}\n', encoding="utf-8")
    evidence_path = tmp_path / "release-evidence.json"
    evidence_path.symlink_to(target)

    release_check._invalidate_release_evidence(evidence_path)

    assert not evidence_path.exists()
    assert not evidence_path.is_symlink()
    assert target.read_text(encoding="utf-8") == '{"status":"passed"}\n'


def test_release_evidence_collision_rejects_directory_entry_swap(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    expected = {"schema_version": 1, "status": "passed"}
    serialized = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    evidence_path.write_text(serialized, encoding="utf-8")
    replacement = tmp_path / "replacement.json"
    replacement.write_text(serialized, encoding="utf-8")
    original_stat = os.stat
    swapped = False

    def swap_before_identity_check(path, *args, **kwargs):
        nonlocal swapped
        if (
            not swapped
            and path == evidence_path.name
            and kwargs.get("dir_fd") is not None
            and kwargs.get("follow_symlinks") is False
        ):
            evidence_path.unlink()
            evidence_path.symlink_to(replacement)
            swapped = True
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(release_check.os, "stat", swap_before_identity_check)

    with pytest.raises(ReleaseCheckError, match="concurrently changed"):
        release_check._publish_release_evidence(evidence_path, expected)
    assert swapped is True
    assert replacement.read_text(encoding="utf-8") == serialized


def test_distribution_only_run_cannot_publish_release_evidence(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    evidence_path.write_text('{"status":"stale"}\n', encoding="utf-8")

    def unexpected_distribution(*_args, **_kwargs):
        raise AssertionError("scoped evidence must fail before distribution")

    monkeypatch.setattr(
        release_check, "check_distribution", unexpected_distribution
    )

    assert (
        release_check.main(
            ["--distribution-only", "--evidence", str(evidence_path)]
        )
        == 1
    )
    assert not evidence_path.exists()


def test_inventory_mode_cannot_preserve_or_publish_release_evidence(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    evidence_path.write_text('{"status":"stale"}\n', encoding="utf-8")
    inventory_path = tmp_path / "inventory.json"

    monkeypatch.setattr(
        release_check,
        "_write_installed_python_license_inventory",
        lambda *_args, **_kwargs: pytest.fail(
            "conflicting inventory mode must fail before writing inventory"
        ),
    )

    assert (
        release_check.main(
            [
                "--installed-python-license-inventory",
                str(inventory_path),
                "--evidence",
                str(evidence_path),
            ]
        )
        == 1
    )
    assert not evidence_path.exists()
    assert not inventory_path.exists()


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

    skipped = {
        "dependencies": [
            {
                "name": "unresolved",
                "version": "1.0.0",
                "vulns": [],
                "skip_reason": "dependency was not found",
            }
        ],
        "fixes": [],
    }
    with pytest.raises(ReleaseCheckError, match="skipped dependencies"):
        release_check.validate_python_audit_report(skipped, label="runtime")


def test_hosted_release_surface_requires_enabled_private_reporting():
    revision = "a" * 40
    repository = {
        "default_branch": "main",
        "full_name": "Deliner/UCF",
        "has_issues": True,
        "private": False,
        "size": 1,
    }
    branch = {"name": "main", "commit": {"sha": revision}}

    with pytest.raises(ReleaseCheckError, match="not enabled"):
        release_check.validate_github_release_surfaces(
            repository,
            {"enabled": False},
            branch,
            local_revision=revision,
            require_published_source=True,
        )


def test_hosted_release_uses_exact_main_when_repository_size_cache_is_zero():
    local_revision = "a" * 40
    repository = {
        "default_branch": "main",
        "full_name": "Deliner/UCF",
        "has_issues": True,
        "private": False,
        "size": 0,
    }
    branch = {}

    with pytest.raises(ReleaseCheckError, match="main branch is malformed"):
        release_check.validate_github_release_surfaces(
            repository,
            {"enabled": True},
            branch,
            local_revision=local_revision,
            require_published_source=True,
        )

    branch = {"name": "main", "commit": {"sha": "b" * 40}}
    with pytest.raises(ReleaseCheckError, match="not published"):
        release_check.validate_github_release_surfaces(
            repository,
            {"enabled": True},
            branch,
            local_revision=local_revision,
            require_published_source=True,
        )

    branch["commit"]["sha"] = local_revision
    evidence = release_check.validate_github_release_surfaces(
        repository,
        {"enabled": True},
        branch,
        local_revision=local_revision,
        require_published_source=True,
    )
    assert evidence["remote_main_revision"] == local_revision
    assert evidence["reported_repository_size_kib"] == 0
    assert evidence["source_revision"] == local_revision
    assert evidence["source_published_to_main"] is True


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
    installation_environments = {
        "ordinary": {"dependencies": [], "status": "reviewed"},
        "supported_floor": {"dependencies": [], "status": "reviewed"},
    }
    snapshot = release_check.GitSourceSnapshot(
        entries=(),
        kind="git_commit",
        revision="a" * 40,
        tree="b" * 40,
    )
    monkeypatch.setattr(
        release_check,
        "_capture_git_source_snapshot",
        lambda *_args, **_kwargs: calls.append("capture") or snapshot,
    )

    def materialize_snapshot(_root, target, *, source_snapshot):
        assert _root == ROOT
        assert source_snapshot == snapshot
        target.mkdir(parents=True)
        (target / "uv.lock").write_text("committed lock\n", encoding="utf-8")
        calls.append(("materialize", source_snapshot))
        return source_snapshot

    monkeypatch.setattr(
        release_check,
        "_copy_source_only",
        materialize_snapshot,
    )
    monkeypatch.setattr(
        release_check,
        "check_distribution",
        lambda _root, *, run_package_contract, source_snapshot: (
            calls.append(("distribution", run_package_contract, source_snapshot))
            or {
                "installation_environments": installation_environments,
                "schema_version": 1,
                "status": "passed",
            }
        ),
    )
    def dependency_audits(audit_root, *, installation_environments):
        assert audit_root != ROOT
        assert (audit_root / "uv.lock").read_text(encoding="utf-8") == (
            "committed lock\n"
        )
        calls.append(("dependencies", installation_environments))
        return {"status": "passed"}

    monkeypatch.setattr(
        release_check,
        "check_dependency_audits",
        dependency_audits,
        raising=False,
    )
    monkeypatch.setattr(
        release_check,
        "check_github_release_surfaces",
        lambda _root, *, require_published_source, local_revision: (
            calls.append(("hosted", require_published_source, local_revision))
            or {"status": "passed"}
        ),
        raising=False,
    )
    monkeypatch.setattr(
        release_check,
        "_revalidate_git_source_snapshot",
        lambda _root, value: calls.append(("revalidate", value)),
    )

    assert release_check.main(["--evidence", str(evidence_path)]) == 0
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert calls == [
        "capture",
        ("materialize", snapshot),
        ("distribution", True, snapshot),
        ("dependencies", installation_environments),
        ("hosted", True, snapshot.revision),
        ("revalidate", snapshot),
    ]
    assert evidence["dependency_review"] == {"status": "passed"}
    assert evidence["hosted_release_surfaces"] == {"status": "passed"}


def test_snapshot_cleanup_failure_cannot_leave_final_release_evidence(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "release-evidence.json"
    evidence_path.write_text('{"status":"stale"}\n', encoding="utf-8")
    snapshot = release_check.GitSourceSnapshot(
        entries=(),
        kind="git_commit",
        revision="a" * 40,
        tree="b" * 40,
    )

    class FailingTemporaryDirectory:
        def __init__(self, *_args, **_kwargs):
            self.name = str(tmp_path / "committed-snapshot")

        def __enter__(self):
            Path(self.name).mkdir()
            return self.name

        def __exit__(self, *_args):
            raise OSError("injected snapshot cleanup failure")

        def cleanup(self):
            raise OSError("injected snapshot cleanup failure")

    monkeypatch.setattr(
        release_check,
        "_capture_git_source_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        release_check,
        "_copy_source_only",
        lambda _root, target, *, source_snapshot: (
            target.mkdir(parents=True) or source_snapshot
        ),
    )
    monkeypatch.setattr(
        release_check,
        "check_distribution",
        lambda *_args, **_kwargs: {
            "installation_environments": {
                "ordinary": {"dependencies": [], "status": "reviewed"},
                "supported_floor": {
                    "dependencies": [],
                    "status": "reviewed",
                },
            },
            "schema_version": 1,
            "status": "passed",
        },
    )
    monkeypatch.setattr(
        release_check,
        "check_dependency_audits",
        lambda *_args, **_kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        release_check,
        "check_github_release_surfaces",
        lambda *_args, **_kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        release_check, "_revalidate_git_source_snapshot", lambda *_args: None
    )
    monkeypatch.setattr(
        release_check.tempfile,
        "TemporaryDirectory",
        FailingTemporaryDirectory,
    )

    assert release_check.main(["--evidence", str(evidence_path)]) == 1
    assert not evidence_path.exists()
