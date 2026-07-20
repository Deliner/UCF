from __future__ import annotations

import base64
import binascii
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class InvalidOpenSpecProfileError(ValueError):
    """The declared OpenSpec profile metadata cannot be parsed safely."""


class UnsupportedOpenSpecProfileError(ValueError):
    """The manifest does not conform to the supported OpenSpec profile."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def validate_spec_driven_profile(
    artifacts: Iterable[tuple[str, str]],
    *,
    change_path: str,
) -> None:
    """Validate the one exact OpenSpec profile supported by this boundary."""
    artifact_content = dict(artifacts)
    change = PurePosixPath(change_path)
    delta_capabilities: set[str] = set()
    base_capabilities: set[str] = set()

    for path in artifact_content:
        artifact_path = PurePosixPath(path)
        try:
            change_relative = artifact_path.relative_to(change)
        except ValueError:
            change_relative = None
        if (
            change_relative is not None
            and change_relative.parts[:1] == ("specs",)
            and artifact_path.suffix == ".md"
        ):
            if (
                len(change_relative.parts) != 3
                or change_relative.parts[-1] != "spec.md"
            ):
                raise UnsupportedOpenSpecProfileError(
                    "nested or noncanonical delta-spec layout is unsupported"
                )
            delta_capabilities.add(change_relative.parts[1])
        if (
            len(artifact_path.parts) == 3
            and artifact_path.parts[0] == "specs"
            and artifact_path.parts[-1] == "spec.md"
        ):
            base_capabilities.add(artifact_path.parts[1])

    orphaned = sorted(base_capabilities - delta_capabilities)
    if orphaned:
        raise UnsupportedOpenSpecProfileError(
            "base specs require matching delta specs: " + ", ".join(orphaned)
        )

    metadata_path = (change / ".openspec.yaml").as_posix()
    selected = artifact_content.get(metadata_path)
    if selected is None:
        selected = artifact_content.get("config.yaml")
    if selected is None:
        raise UnsupportedOpenSpecProfileError(
            "supported import requires change metadata or config.yaml"
        )

    try:
        content = base64.b64decode(selected.encode("ascii"), validate=True)
        parsed: Any = yaml.load(
            content.decode("utf-8"),
            Loader=_UniqueKeyLoader,
        )
    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        binascii.Error,
        yaml.YAMLError,
        RecursionError,
    ) as error:
        raise InvalidOpenSpecProfileError(
            f"OpenSpec profile metadata is invalid: {error}"
        ) from error
    if not isinstance(parsed, dict) or parsed.get("schema") != "spec-driven":
        raise UnsupportedOpenSpecProfileError(
            "only the built-in spec-driven schema is supported"
        )


__all__ = [
    "InvalidOpenSpecProfileError",
    "UnsupportedOpenSpecProfileError",
    "validate_spec_driven_profile",
]
