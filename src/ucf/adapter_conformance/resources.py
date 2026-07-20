from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from ucf.adapter_conformance.models import (
    CONFORMANCE_KIT_VERSION,
    ConformanceAsset,
    ConformanceFixture,
    ConformanceKitIndex,
    ConformanceManifest,
    parse_conformance_fixture_json,
    parse_conformance_manifest_json,
    validate_resource_path,
)
from ucf.adapter_protocol import ADAPTER_PROTOCOL_VERSION

_ASSET_PACKAGE = "ucf.adapter_conformance"
_ASSET_ROOT = ("assets", "v1")


def conformance_assets() -> Traversable:
    root = files(_ASSET_PACKAGE)
    for segment in _ASSET_ROOT:
        root = root.joinpath(segment)
    return root


def conformance_asset_names() -> tuple[str, ...]:
    names: list[str] = []

    def collect(node: Traversable, prefix: str) -> None:
        for child in node.iterdir():
            logical_name = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                collect(child, logical_name)
            elif child.is_file():
                names.append(logical_name)

    collect(conformance_assets(), "")
    return tuple(sorted(names))


def read_conformance_asset(name: str) -> bytes:
    normalized = validate_resource_path(name)
    resource = conformance_assets()
    for segment in normalized.split("/"):
        resource = resource.joinpath(segment)
    if not resource.is_file():
        raise FileNotFoundError(f"unknown conformance asset: {name}")
    return resource.read_bytes()


def load_conformance_manifest() -> ConformanceManifest:
    return parse_conformance_manifest_json(
        read_conformance_asset("manifest.json")
    )


def load_conformance_fixture(name: str) -> ConformanceFixture:
    if not name.startswith("fixtures/"):
        raise ValueError("conformance fixture must be under fixtures/")
    return parse_conformance_fixture_json(read_conformance_asset(name))


def conformance_kit_index() -> ConformanceKitIndex:
    assets = []
    for name in conformance_asset_names():
        content = read_conformance_asset(name)
        assets.append(
            ConformanceAsset(
                kind="conformance_asset",
                name=name,
                sha256=hashlib.sha256(content).hexdigest(),
                size=len(content),
            )
        )
    return ConformanceKitIndex(
        kind="adapter_conformance_kit_index",
        kit_version=CONFORMANCE_KIT_VERSION,
        protocol_version=ADAPTER_PROTOCOL_VERSION,
        assets=tuple(assets),
    )


def extract_conformance_kit(destination: Path) -> ConformanceKitIndex:
    if not isinstance(destination, Path):
        raise ValueError("conformance kit destination must be a pathlib.Path")
    if destination.is_symlink():
        raise ValueError("conformance kit destination must not be a symlink")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(
                "conformance kit destination must be an empty directory"
            )
        if any(destination.iterdir()):
            raise ValueError(
                "conformance kit destination must be an empty directory"
            )

    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if not parent.is_dir():
        raise ValueError(
            "conformance kit destination parent must be a directory"
        )

    index = conformance_kit_index()
    staging = Path(
        tempfile.mkdtemp(prefix=".ucf-conformance-", dir=parent)
    )
    try:
        for asset in index.assets:
            target = staging.joinpath(*asset.name.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read_conformance_asset(asset.name))
        if destination.exists():
            destination.rmdir()
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return index
