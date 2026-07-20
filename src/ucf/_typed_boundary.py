from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import UnionType
from typing import (
    Annotated,
    Literal,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel


class TypedBoundaryError(ValueError):
    def __init__(self, message: str, *, location: str) -> None:
        self.location = location
        super().__init__(message)


def reject_noncanonical_typed_values(
    value: object,
    *,
    declared_type: object,
    max_depth: int,
) -> None:
    _reject_value(
        value,
        declared_type=declared_type,
        location="$",
        seen=set(),
        depth=0,
        max_depth=max_depth,
    )


def _reject_value(
    value: object,
    *,
    declared_type: object,
    location: str,
    seen: set[int],
    depth: int,
    max_depth: int,
) -> None:
    declared_type = _unwrap_declared_type(declared_type)
    origin = get_origin(declared_type)
    if origin in (Union, UnionType):
        branch = _matching_declared_branch(value, get_args(declared_type))
        if branch is not None:
            _reject_value(
                value,
                declared_type=branch,
                location=location,
                seen=seen,
                depth=depth,
                max_depth=max_depth,
            )
            return
    expected_models = _declared_model_types(declared_type)
    if expected_models and type(value) not in expected_models:
        _raise_model_type_error(value, expected_models, location=location)
    if isinstance(value, BaseModel):
        if type(value) not in expected_models:
            _raise_model_type_error(value, expected_models, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_depth(
            depth,
            max_depth=max_depth,
            location=location,
        )
        seen.add(identity)
        fields = type(value).model_fields
        unknown = set(value.__dict__) - set(fields)
        extra = value.__pydantic_extra__
        if extra:
            unknown.update(extra)
        if unknown:
            field = min(unknown)
            raise TypedBoundaryError(
                f"Extra inputs are not permitted: {field!r}",
                location=f"{location}.{field}",
            )
        for field, field_info in fields.items():
            if field not in value.__dict__:
                continue
            _reject_value(
                value.__dict__[field],
                declared_type=field_info.annotation,
                location=f"{location}.{field}",
                seen=seen,
                depth=depth + 1,
                max_depth=max_depth,
            )
        return

    expected_scalars = _declared_scalar_types(declared_type)
    if expected_scalars:
        _reject_excessive_depth(
            depth,
            max_depth=max_depth,
            location=location,
        )
        if type(value) not in expected_scalars:
            _raise_scalar_type_error(
                value,
                expected_scalars,
                location=location,
            )
        return
    if origin is tuple:
        if type(value) is not tuple:
            _raise_container_type_error(value, tuple, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_depth(
            depth,
            max_depth=max_depth,
            location=location,
        )
        seen.add(identity)
        arguments = get_args(declared_type)
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            item_types = (arguments[0],) * len(value)
        elif len(arguments) == len(value):
            item_types = arguments
        else:
            return
        for index, (item, item_type) in enumerate(zip(value, item_types, strict=True)):
            _reject_value(
                item,
                declared_type=item_type,
                location=f"{location}[{index}]",
                seen=seen,
                depth=depth + 1,
                max_depth=max_depth,
            )
        return
    if origin is list:
        if type(value) is not list:
            _raise_container_type_error(value, list, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_depth(
            depth,
            max_depth=max_depth,
            location=location,
        )
        seen.add(identity)
        arguments = get_args(declared_type)
        if not arguments:
            return
        for index, item in enumerate(value):
            _reject_value(
                item,
                declared_type=arguments[0],
                location=f"{location}[{index}]",
                seen=seen,
                depth=depth + 1,
                max_depth=max_depth,
            )
        return
    if origin in (dict, Mapping):
        if type(value) is not dict:
            _raise_container_type_error(value, dict, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_depth(
            depth,
            max_depth=max_depth,
            location=location,
        )
        seen.add(identity)
        arguments = get_args(declared_type)
        if len(arguments) != 2:
            return
        _, item_type = arguments
        for key, item in value.items():
            _reject_value(
                item,
                declared_type=item_type,
                location=f"{location}[{key!r}]",
                seen=seen,
                depth=depth + 1,
                max_depth=max_depth,
            )


def _reject_excessive_depth(
    depth: int,
    *,
    max_depth: int,
    location: str,
) -> None:
    if depth > max_depth:
        raise TypedBoundaryError(
            f"resource exceeds the maximum typed nesting depth of {max_depth}",
            location=location,
        )


def _unwrap_declared_type(declared_type: object) -> object:
    while True:
        if isinstance(declared_type, TypeAliasType):
            declared_type = declared_type.__value__
            continue
        if get_origin(declared_type) is Annotated:
            declared_type = get_args(declared_type)[0]
            continue
        return declared_type


def _declared_model_types(
    declared_type: object,
) -> tuple[type[BaseModel], ...]:
    declared_type = _unwrap_declared_type(declared_type)
    if isinstance(declared_type, type) and issubclass(
        declared_type,
        BaseModel,
    ):
        return (declared_type,)
    if get_origin(declared_type) in (Union, UnionType):
        return tuple(
            model
            for branch in get_args(declared_type)
            for model in _declared_model_types(branch)
        )
    return ()


def _declared_scalar_types(
    declared_type: object,
) -> tuple[type[object], ...]:
    declared_type = _unwrap_declared_type(declared_type)
    for scalar_type in (bool, int, float, str):
        if declared_type is scalar_type:
            return (scalar_type,)
    if isinstance(declared_type, type) and issubclass(declared_type, Enum):
        return (declared_type,)
    if get_origin(declared_type) is Literal:
        return tuple(dict.fromkeys(type(value) for value in get_args(declared_type)))
    return ()


def _matching_declared_branch(
    value: object,
    branches: tuple[object, ...],
) -> object | None:
    for branch in branches:
        if type(value) in _declared_scalar_types(branch):
            return branch
    for branch in branches:
        candidate = _unwrap_declared_type(branch)
        origin = get_origin(candidate)
        if candidate is None or candidate is type(None):
            if value is None:
                return branch
        elif origin is tuple and isinstance(value, tuple):
            return branch
        elif origin is list and isinstance(value, list):
            return branch
        elif origin in (dict, Mapping) and isinstance(value, Mapping):
            return branch
        elif isinstance(candidate, type) and isinstance(value, candidate):
            return branch
    return None


def _raise_model_type_error(
    value: object,
    expected: tuple[type[BaseModel], ...],
    *,
    location: str,
) -> None:
    expected_names = ", ".join(model.__name__ for model in expected)
    expectation = expected_names or "no Pydantic model"
    raise TypedBoundaryError(
        "value must use an exact canonical model type "
        f"({expectation}); got {type(value).__name__}",
        location=location,
    )


def _raise_scalar_type_error(
    value: object,
    expected: tuple[type[object], ...],
    *,
    location: str,
) -> None:
    expected_names = ", ".join(item.__name__ for item in expected)
    raise TypedBoundaryError(
        "value must use its exact declared scalar type "
        f"({expected_names}); got {type(value).__name__}",
        location=location,
    )


def _raise_container_type_error(
    value: object,
    expected: object,
    *,
    location: str,
) -> None:
    expected_name = getattr(expected, "__name__", str(expected))
    raise TypedBoundaryError(
        "value must use its declared canonical container type "
        f"{expected_name}; got {type(value).__name__}",
        location=location,
    )
