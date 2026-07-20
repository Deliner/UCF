from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from dataclasses import dataclass

from .classifiers import (
    MAX_CLASSIFICATION_BYTES,
    ClassificationFailure,
    ClassificationLimit,
    ClassifiedFact,
    classify_file,
)
from .limits import MAX_CANONICAL_RECORDS

HASH_CHUNK_BYTES = 65_536
MAX_DEPTH = 64
MAX_FILESYSTEM_ENTRIES = 20_000
MAX_FILE_BYTES = 268_435_456
MAX_TOTAL_FILE_BYTES = 2_147_483_648
MAX_PATH_BYTES = 1_024
MAX_OUTPUT_RECORDS = MAX_CANONICAL_RECORDS

_WINDOWS_RESERVED = frozenset(
    {
        "AUX",
        "CON",
        "NUL",
        "PRN",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)


@dataclass(frozen=True)
class ScannedEntry:
    path: str
    entry_kind: str
    size_bytes: int | None
    content_digest: str | None
    symlink_target_digest: str | None


@dataclass(frozen=True)
class ScannedClassification:
    path: str
    fact: ClassifiedFact


@dataclass(frozen=True)
class ScannedIgnore:
    rule_id: str
    path: str


@dataclass(frozen=True)
class ScannedDiagnostic:
    severity: str
    code: str
    fact_kind: str | None
    path: str | None
    stage: str
    message: str


@dataclass(frozen=True)
class ScanResult:
    entries: tuple[ScannedEntry, ...]
    classifications: tuple[ScannedClassification, ...]
    ignores: tuple[ScannedIgnore, ...]
    diagnostics: tuple[ScannedDiagnostic, ...]


class ScanCancelled(RuntimeError):
    pass


class _ResourceLimit(RuntimeError):
    pass


class _Accumulator:
    def __init__(self, cancel_event) -> None:
        self.cancel_event = cancel_event
        self.entry_count = 0
        self.total_file_bytes = 0
        self.entries: list[ScannedEntry] = []
        self.classifications: list[ScannedClassification] = []
        self.ignores: list[ScannedIgnore] = []
        self.diagnostics: list[ScannedDiagnostic] = []
        self.portable_paths: set[str] = set()
        self.output_record_count = 0
        self.diagnostic_identities: set[
            tuple[str, str | None, str | None, str]
        ] = set()

    def check_cancelled(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise ScanCancelled

    def consume_path(self) -> None:
        self.entry_count += 1
        if self.entry_count > MAX_FILESYSTEM_ENTRIES:
            raise _ResourceLimit

    def add_path(self, path: str) -> None:
        key = _portable_path_key(path)
        if key in self.portable_paths:
            self.add_diagnostic(
                code="path-collision",
                fact_kind="repository_entry",
                path=path,
                stage="enumerate",
                message="Repository path identity is not unique.",
            )
            raise ValueError("path-collision")
        self.portable_paths.add(key)

    def reserve_output(self, amount: int) -> None:
        self._reserve_output(amount, keep_resource_slot=True)

    def remaining_classification_capacity(self) -> int:
        return max(
            0,
            MAX_OUTPUT_RECORDS - self.output_record_count - 1,
        )

    def add_ignore(self, *, rule_id: str, path: str) -> None:
        self.reserve_output(1)
        self.ignores.append(ScannedIgnore(rule_id=rule_id, path=path))

    def add_diagnostic(
        self,
        *,
        code: str,
        fact_kind: str | None,
        path: str | None,
        stage: str,
        message: str,
        reserve_resource_slot: bool = True,
    ) -> None:
        identity = (code, fact_kind, path, stage)
        if identity in self.diagnostic_identities:
            return
        self._reserve_output(
            1,
            keep_resource_slot=reserve_resource_slot,
        )
        self.diagnostic_identities.add(identity)
        self.diagnostics.append(
            ScannedDiagnostic(
                severity="error",
                code=f"org.ucf.inventory.{code}",
                fact_kind=fact_kind,
                path=path,
                stage=stage,
                message=message,
            )
        )

    def _reserve_output(
        self,
        amount: int,
        *,
        keep_resource_slot: bool,
    ) -> None:
        limit = MAX_OUTPUT_RECORDS - (1 if keep_resource_slot else 0)
        if self.output_record_count + amount > limit:
            raise _ResourceLimit
        self.output_record_count += amount


def scan_repository(
    *,
    root_path: str,
    ignore_rules: tuple[dict[str, object], ...],
    cancel_event=None,
) -> ScanResult:
    accumulator = _Accumulator(cancel_event)
    root_fd = _open_root(root_path)
    try:
        accumulator.consume_path()
        accumulator.add_path(".")
        accumulator.reserve_output(2)
        accumulator.entries.append(
            ScannedEntry(
                path=".",
                entry_kind="directory",
                size_bytes=None,
                content_digest=None,
                symlink_target_digest=None,
            )
        )
        try:
            _scan_directory(
                root_fd,
                ".",
                0,
                ignore_rules,
                accumulator,
            )
        except _ResourceLimit:
            accumulator.add_diagnostic(
                code="resource-limit",
                fact_kind=None,
                path=None,
                stage="enumerate",
                message="Inventory resource limit was reached.",
                reserve_resource_slot=False,
            )
    finally:
        os.close(root_fd)
    return ScanResult(
        entries=tuple(accumulator.entries),
        classifications=tuple(accumulator.classifications),
        ignores=tuple(accumulator.ignores),
        diagnostics=tuple(accumulator.diagnostics),
    )


def _open_root(root_path: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    current = os.open(".", flags)
    try:
        if root_path == ".":
            return current
        for part in root_path.split("/"):
            next_fd = os.open(
                part,
                flags | nofollow,
                dir_fd=current,
            )
            os.close(current)
            current = next_fd
        return current
    except BaseException:
        os.close(current)
        raise


def _bounded_directory_names(
    directory_fd: int,
    accumulator: _Accumulator,
) -> tuple[str, ...]:
    remaining = MAX_FILESYSTEM_ENTRIES - accumulator.entry_count
    names: list[str] = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            accumulator.check_cancelled()
            if len(names) >= remaining:
                raise _ResourceLimit
            names.append(entry.name)
    return tuple(sorted(names, key=os.fsencode))


def _scan_directory(
    directory_fd: int,
    parent_path: str,
    depth: int,
    ignore_rules: tuple[dict[str, object], ...],
    accumulator: _Accumulator,
) -> None:
    accumulator.check_cancelled()
    if depth > MAX_DEPTH:
        raise _ResourceLimit
    before = os.fstat(directory_fd)
    try:
        names = _bounded_directory_names(directory_fd, accumulator)
    except OSError:
        accumulator.add_diagnostic(
            code="entry-inaccessible",
            fact_kind="repository_entry",
            path=parent_path,
            stage="enumerate",
            message="Repository entry could not be enumerated.",
        )
        return

    for name in names:
        accumulator.check_cancelled()
        accumulator.consume_path()
        path = name if parent_path == "." else f"{parent_path}/{name}"
        if not _valid_name(name) or len(path.encode("utf-8")) > MAX_PATH_BYTES:
            accumulator.add_diagnostic(
                code="path-unsupported",
                fact_kind="repository_entry",
                path=parent_path,
                stage="enumerate",
                message="Repository entry name is not portable.",
            )
            continue
        matching = _matching_rules(ignore_rules, path)
        if matching:
            accumulator.add_ignore(
                rule_id=min(matching),
                path=path,
            )
            continue
        try:
            accumulator.add_path(path)
        except ValueError:
            continue
        try:
            before_entry = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except OSError:
            accumulator.add_diagnostic(
                code="entry-inaccessible",
                fact_kind="repository_entry",
                path=path,
                stage="stat",
                message="Repository entry could not be inspected.",
            )
            continue
        mode = before_entry.st_mode
        if stat.S_ISLNK(mode):
            _scan_symlink(
                directory_fd,
                name,
                path,
                before_entry,
                accumulator,
            )
        elif stat.S_ISDIR(mode):
            _scan_child_directory(
                directory_fd,
                name,
                path,
                before_entry,
                depth,
                ignore_rules,
                accumulator,
            )
        elif stat.S_ISREG(mode):
            _scan_file(
                directory_fd,
                name,
                path,
                before_entry,
                accumulator,
            )
        else:
            accumulator.add_diagnostic(
                code="non-regular-entry",
                fact_kind="repository_entry",
                path=path,
                stage="stat",
                message="Repository entry is not a regular supported type.",
            )

    after = os.fstat(directory_fd)
    if not _same_identity(before, after, directory=True):
        accumulator.add_diagnostic(
            code="source-changed",
            fact_kind=None,
            path=parent_path,
            stage="scan",
            message="Repository source changed during inventory.",
        )


def _scan_child_directory(
    parent_fd: int,
    name: str,
    path: str,
    before_entry: os.stat_result,
    depth: int,
    ignore_rules: tuple[dict[str, object], ...],
    accumulator: _Accumulator,
) -> None:
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        child_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        accumulator.add_diagnostic(
            code="entry-inaccessible",
            fact_kind="repository_entry",
            path=path,
            stage="open",
            message="Repository entry could not be opened.",
        )
        return
    try:
        opened = os.fstat(child_fd)
        if not _same_identity(before_entry, opened, directory=True):
            accumulator.add_diagnostic(
                code="source-changed",
                fact_kind=None,
                path=path,
                stage="scan",
                message="Repository source changed during inventory.",
            )
            return
        accumulator.reserve_output(2)
        accumulator.entries.append(
            ScannedEntry(
                path=path,
                entry_kind="directory",
                size_bytes=None,
                content_digest=None,
                symlink_target_digest=None,
            )
        )
        _scan_directory(
            child_fd,
            path,
            depth + 1,
            ignore_rules,
            accumulator,
        )
    finally:
        os.close(child_fd)


def _scan_symlink(
    parent_fd: int,
    name: str,
    path: str,
    before_entry: os.stat_result,
    accumulator: _Accumulator,
) -> None:
    try:
        target = os.readlink(name, dir_fd=parent_fd)
        after = os.stat(
            name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except OSError:
        accumulator.add_diagnostic(
            code="entry-inaccessible",
            fact_kind="repository_entry",
            path=path,
            stage="read",
            message="Repository entry could not be read.",
        )
        return
    if not _same_identity(before_entry, after, directory=False):
        accumulator.add_diagnostic(
            code="source-changed",
            fact_kind=None,
            path=path,
            stage="scan",
            message="Repository source changed during inventory.",
        )
        return
    target_bytes = os.fsencode(target)
    accumulator.reserve_output(2)
    accumulator.entries.append(
        ScannedEntry(
            path=path,
            entry_kind="symlink",
            size_bytes=None,
            content_digest=None,
            symlink_target_digest=hashlib.sha256(target_bytes).hexdigest(),
        )
    )


def _scan_file(
    parent_fd: int,
    name: str,
    path: str,
    before_entry: os.stat_result,
    accumulator: _Accumulator,
) -> None:
    flags = (
        os.O_RDONLY
        | os.O_CLOEXEC
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        file_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        accumulator.add_diagnostic(
            code="entry-inaccessible",
            fact_kind="repository_entry",
            path=path,
            stage="open",
            message="Repository entry could not be opened.",
        )
        return
    try:
        opened = os.fstat(file_fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not _same_identity(before_entry, opened, directory=False)
        ):
            accumulator.add_diagnostic(
                code="source-changed",
                fact_kind=None,
                path=path,
                stage="scan",
                message="Repository source changed during inventory.",
            )
            return
        if opened.st_size > MAX_FILE_BYTES:
            raise _ResourceLimit
        accumulator.total_file_bytes += opened.st_size
        if accumulator.total_file_bytes > MAX_TOTAL_FILE_BYTES:
            raise _ResourceLimit
        digest = hashlib.sha256()
        prefix = bytearray()
        byte_count = 0
        while True:
            accumulator.check_cancelled()
            chunk = os.read(file_fd, HASH_CHUNK_BYTES)
            if not chunk:
                break
            byte_count += len(chunk)
            if byte_count > MAX_FILE_BYTES:
                raise _ResourceLimit
            digest.update(chunk)
            remaining = MAX_CLASSIFICATION_BYTES - len(prefix)
            if remaining > 0:
                prefix.extend(chunk[:remaining])
        after_open = os.fstat(file_fd)
    except OSError:
        accumulator.add_diagnostic(
            code="entry-inaccessible",
            fact_kind="repository_entry",
            path=path,
            stage="read",
            message="Repository entry could not be read.",
        )
        return
    finally:
        os.close(file_fd)
    try:
        after_path = os.stat(
            name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except OSError:
        accumulator.add_diagnostic(
            code="source-changed",
            fact_kind=None,
            path=path,
            stage="scan",
            message="Repository source changed during inventory.",
        )
        return
    if (
        byte_count != opened.st_size
        or not _same_identity(opened, after_open, directory=False)
        or not _same_identity(opened, after_path, directory=False)
    ):
        accumulator.add_diagnostic(
            code="source-changed",
            fact_kind=None,
            path=path,
            stage="scan",
            message="Repository source changed during inventory.",
        )
        return
    content_digest = digest.hexdigest()
    accumulator.reserve_output(2)
    accumulator.entries.append(
        ScannedEntry(
            path=path,
            entry_kind="file",
            size_bytes=byte_count,
            content_digest=content_digest,
            symlink_target_digest=None,
        )
    )
    try:
        facts = classify_file(
            path,
            bytes(prefix),
            max_facts=accumulator.remaining_classification_capacity(),
        )
    except ClassificationLimit as error:
        raise _ResourceLimit from error
    except ClassificationFailure as error:
        accumulator.add_diagnostic(
            code="classification-failed",
            fact_kind=error.fact_kind,
            path=path,
            stage="classify",
            message="Repository entry classification failed.",
        )
        return
    accumulator.reserve_output(len(facts))
    accumulator.classifications.extend(
        ScannedClassification(path=path, fact=fact) for fact in facts
    )


def _matching_rules(
    rules: tuple[dict[str, object], ...],
    path: str,
) -> tuple[str, ...]:
    parts = path.split("/")
    matching: list[str] = []
    for rule in rules:
        matcher = rule["matcher"]
        assert isinstance(matcher, dict)
        if matcher["kind"] == "path_segment":
            if matcher["segment"] in parts:
                matching.append(str(rule["id"]))
        else:
            prefix = str(matcher["path"])
            if prefix == "." or path == prefix or path.startswith(f"{prefix}/"):
                matching.append(str(rule["id"]))
    return tuple(matching)


def _valid_name(name: str) -> bool:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or ":" in name
        or any(character in '<>"|?*' for character in name)
        or name.endswith((" ", "."))
        or unicodedata.normalize("NFC", name) != name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        return False
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if len(encoded) > 255:
        return False
    return name.partition(".")[0].upper() not in _WINDOWS_RESERVED


def _portable_path_key(path: str) -> str:
    return "".join(
        character.lower() if "A" <= character <= "Z" else character
        for character in path
    )


def _same_identity(
    left: os.stat_result,
    right: os.stat_result,
    *,
    directory: bool,
) -> bool:
    common = (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and left.st_mode == right.st_mode
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )
    return common and (directory or left.st_size == right.st_size)
