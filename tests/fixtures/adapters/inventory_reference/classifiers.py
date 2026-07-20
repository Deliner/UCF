from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from dataclasses import dataclass

MAX_CLASSIFICATION_BYTES = 1_048_576

BUILD_MANIFEST_DIALECT = (
    "urn:ucf:inventory-dialect:pyproject-toml:1.0.0"
)
PYTHON_INTERFACE_DIALECT = (
    "urn:ucf:inventory-interface:python-function:1.0.0"
)
PYTHON_TEST_DIALECT = "urn:ucf:inventory-test:python-function:1.0.0"
OPENAPI_DIALECT = "urn:ucf:inventory-dialect:openapi:1.0.0"


@dataclass(frozen=True)
class ClassifiedFact:
    kind: str
    attributes: dict[str, object]


class ClassificationFailure(ValueError):
    def __init__(self, fact_kind: str) -> None:
        self.fact_kind = fact_kind
        super().__init__(fact_kind)


class ClassificationLimit(RuntimeError):
    pass


def classify_file(
    path: str,
    content: bytes,
    *,
    max_facts: int,
) -> tuple[ClassifiedFact, ...]:
    """Return deterministic facts without retaining or exposing source text."""

    if max_facts < 0:
        raise ValueError("classification fact limit must be non-negative")
    if len(content) > MAX_CLASSIFICATION_BYTES:
        return ()
    if path == "pyproject.toml":
        facts = _classify_pyproject(content)
    elif path == "api/openapi.json":
        facts = _classify_openapi(content)
    elif path.endswith(".py"):
        try:
            return _classify_python(
                path,
                content,
                max_facts=max_facts,
            )
        except (MemoryError, RecursionError) as error:
            raise ClassificationFailure(
                _python_fact_kind(path)
            ) from error
    else:
        facts = ()
    if len(facts) > max_facts:
        raise ClassificationLimit
    return facts


def _classify_pyproject(content: bytes) -> tuple[ClassifiedFact, ...]:
    try:
        document = tomllib.loads(content.decode("utf-8"))
    except (
        MemoryError,
        RecursionError,
        UnicodeDecodeError,
        tomllib.TOMLDecodeError,
    ) as error:
        raise ClassificationFailure("build_manifest") from error
    if not isinstance(document.get("project"), dict):
        return ()
    return (
        ClassifiedFact(
            kind="build_manifest",
            attributes={"dialect_uri": BUILD_MANIFEST_DIALECT},
        ),
    )


def _classify_openapi(content: bytes) -> tuple[ClassifiedFact, ...]:
    try:
        document = json.loads(content.decode("utf-8"))
    except (
        MemoryError,
        RecursionError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise ClassificationFailure("api_description") from error
    if not isinstance(document, dict):
        raise ClassificationFailure("api_description")
    version = document.get("openapi")
    if not isinstance(version, str) or not version:
        return ()
    return (
        ClassifiedFact(
            kind="api_description",
            attributes={
                "dialect_uri": OPENAPI_DIALECT,
                "declared_version": version,
            },
        ),
    )


def _classify_python(
    path: str,
    content: bytes,
    *,
    max_facts: int,
) -> tuple[ClassifiedFact, ...]:
    try:
        text = content.decode("utf-8")
        tree = ast.parse(text, filename="<inventory>")
    except (
        MemoryError,
        RecursionError,
        UnicodeDecodeError,
        SyntaxError,
        ValueError,
    ) as error:
        raise ClassificationFailure(_python_fact_kind(path)) from error

    facts: list[ClassifiedFact] = []
    is_test_module = (
        path.startswith("tests/")
        or path.rsplit("/", 1)[-1].startswith("test_")
    )
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if is_test_module and node.name.startswith("test_"):
            if len(facts) >= max_facts:
                raise ClassificationLimit
            facts.append(
                ClassifiedFact(
                    kind="test_asset",
                    attributes={
                        "test_kind_uri": PYTHON_TEST_DIALECT,
                        "name": node.name,
                    },
                )
            )
            continue
        if is_test_module or node.name.startswith("_"):
            continue
        if len(facts) >= max_facts:
            raise ClassificationLimit
        declaration = {
            "async": isinstance(node, ast.AsyncFunctionDef),
            "name": node.name,
            "parameters": ast.dump(
                node.args,
                annotate_fields=True,
                include_attributes=False,
            ),
            "returns": (
                ast.dump(
                    node.returns,
                    annotate_fields=True,
                    include_attributes=False,
                )
                if node.returns is not None
                else None
            ),
        }
        facts.append(
            ClassifiedFact(
                kind="public_interface",
                attributes={
                    "interface_kind_uri": PYTHON_INTERFACE_DIALECT,
                    "name": node.name,
                    "container": None,
                    "declaration_digest": _digest(
                        _canonical_bytes(declaration)
                    ),
                },
            )
        )
    return tuple(facts)


def _python_fact_kind(path: str) -> str:
    if (
        path.startswith("tests/")
        or path.rsplit("/", 1)[-1].startswith("test_")
    ):
        return "test_asset"
    return "public_interface"


def _digest(content: bytes) -> dict[str, str]:
    return {
        "kind": "digest",
        "algorithm": "sha-256",
        "value": hashlib.sha256(content).hexdigest(),
    }


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
