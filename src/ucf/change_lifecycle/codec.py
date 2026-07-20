from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import Enum
from types import UnionType
from typing import (
    Annotated,
    Any,
    Literal,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ucf.change_lifecycle.behavior import validate_behavior_document
from ucf.change_lifecycle.errors import (
    ChangeLifecycleErrorCode,
    ChangeLifecycleValidationError,
)
from ucf.change_lifecycle.models import (
    BEHAVIOR_DELTA_SCHEMA_URI,
    CHANGE_LIFECYCLE_VERSION,
    CHANGE_PROPOSAL_SCHEMA_URI,
    IMPLEMENTATION_RECORD_SCHEMA_URI,
    TASK_GRAPH_SCHEMA_URI,
    VERIFICATION_RECORD_SCHEMA_URI,
    ArchiveRecord,
    BehaviorDelta,
    BehaviorDeltaRef,
    ChangeProposal,
    ChangeProposalRef,
    ImplementationRecord,
    ImplementationRecordRef,
    TaskGraph,
    TaskGraphRef,
    VerificationRecord,
    VerificationRecordRef,
)
from ucf.ir import (
    IRErrorCode,
    IRValidationError,
    canonical_ir_json,
    decode_strict_json_object,
    parse_ir_json,
)
from ucf.ir.codec import MAX_JSON_NESTING
from ucf.ir.models import Digest

type ChangeLifecycleDocument = (
    ChangeProposal
    | BehaviorDelta
    | TaskGraph
    | ImplementationRecord
    | VerificationRecord
    | ArchiveRecord
)
_CHANGE_LIFECYCLE_DOCUMENT_TYPES = (
    ChangeProposal,
    BehaviorDelta,
    TaskGraph,
    ImplementationRecord,
    VerificationRecord,
    ArchiveRecord,
)


def canonical_change_lifecycle_json(
    document: ChangeLifecycleDocument,
) -> bytes:
    model = type(document)
    if model not in _CHANGE_LIFECYCLE_DOCUMENT_TYPES:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "lifecycle resource must use one exact canonical document type",
            location="$",
        )
    document = _normalize_embedded_behavior(document)
    try:
        _reject_undeclared_typed_fields(
            document,
            declared_type=model,
            location="$",
            seen=set(),
            depth=0,
        )
    except RecursionError as error:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "lifecycle resource exceeds the maximum typed nesting depth "
            f"of {MAX_JSON_NESTING}",
            location="$",
        ) from error
    try:
        encoded = (
            json.dumps(
                document.model_dump(
                    mode="json",
                    serialize_as_any=True,
                ),
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except RecursionError as error:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "lifecycle resource exceeds the maximum typed nesting depth "
            f"of {MAX_JSON_NESTING}",
            location="$",
        ) from error
    except (TypeError, ValueError) as error:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            f"lifecycle resource cannot be serialized: {error}",
            location="$",
        ) from error
    _parse_change_document(encoded, model)
    return encoded


def _normalize_embedded_behavior(
    document: ChangeLifecycleDocument,
) -> ChangeLifecycleDocument:
    if type(document) is not ArchiveRecord:
        return document
    validate_behavior_document(
        document.final_behavior,
        location="$.final_behavior",
    )
    canonical_behavior = parse_ir_json(canonical_ir_json(document.final_behavior))
    if document.final_behavior == canonical_behavior:
        return document
    return document.model_copy(update={"final_behavior": canonical_behavior})


def _reject_undeclared_typed_fields(
    value: object,
    *,
    declared_type: object,
    location: str,
    seen: set[int],
    depth: int,
) -> None:
    declared_type = _unwrap_declared_type(declared_type)
    expected_models = _declared_model_types(declared_type)
    if expected_models and type(value) not in expected_models:
        _raise_model_type_error(value, expected_models, location=location)
    if isinstance(value, BaseModel):
        if type(value) not in expected_models:
            _raise_model_type_error(value, expected_models, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_typed_depth(depth, location=location)
        seen.add(identity)
        fields = type(value).model_fields
        unknown = set(value.__dict__) - set(fields)
        extra = value.__pydantic_extra__
        if extra:
            unknown.update(extra)
        if unknown:
            field = min(unknown)
            raise ChangeLifecycleValidationError(
                ChangeLifecycleErrorCode.INVALID_STRUCTURE,
                f"Extra inputs are not permitted: {field!r}",
                location=f"{location}.{field}",
            )
        for field in fields:
            if field in value.__dict__:
                _reject_undeclared_typed_fields(
                    value.__dict__[field],
                    declared_type=fields[field].annotation,
                    location=f"{location}.{field}",
                    seen=seen,
                    depth=depth + 1,
                )
        return

    origin = get_origin(declared_type)
    if origin in (Union, UnionType):
        branch = _matching_declared_branch(value, get_args(declared_type))
        if branch is not None:
            _reject_undeclared_typed_fields(
                value,
                declared_type=branch,
                location=location,
                seen=seen,
                depth=depth,
            )
        return
    expected_scalar_types = _declared_scalar_types(declared_type)
    if expected_scalar_types:
        _reject_excessive_typed_depth(depth, location=location)
        if type(value) not in expected_scalar_types:
            _raise_scalar_type_error(
                value,
                expected_scalar_types,
                location=location,
            )
        return
    if origin is tuple:
        if type(value) is not tuple:
            _raise_container_type_error(value, tuple, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_typed_depth(depth, location=location)
        seen.add(identity)
        arguments = get_args(declared_type)
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            item_types = (arguments[0],) * len(value)
        elif len(arguments) == len(value):
            item_types = arguments
        else:
            return
        for index, (item, item_type) in enumerate(zip(value, item_types, strict=True)):
            _reject_undeclared_typed_fields(
                item,
                declared_type=item_type,
                location=f"{location}[{index}]",
                seen=seen,
                depth=depth + 1,
            )
        return
    if origin is list:
        if type(value) is not list:
            _raise_container_type_error(value, list, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_typed_depth(depth, location=location)
        seen.add(identity)
        arguments = get_args(declared_type)
        if not arguments:
            return
        for index, item in enumerate(value):
            _reject_undeclared_typed_fields(
                item,
                declared_type=arguments[0],
                location=f"{location}[{index}]",
                seen=seen,
                depth=depth + 1,
            )
        return
    if origin in (dict, Mapping):
        if type(value) is not dict:
            _raise_container_type_error(value, dict, location=location)
        identity = id(value)
        if identity in seen:
            return
        _reject_excessive_typed_depth(depth, location=location)
        seen.add(identity)
        arguments = get_args(declared_type)
        if len(arguments) != 2:
            return
        _, item_type = arguments
        for key, item in value.items():
            _reject_undeclared_typed_fields(
                item,
                declared_type=item_type,
                location=f"{location}[{key!r}]",
                seen=seen,
                depth=depth + 1,
            )
        return


def _reject_excessive_typed_depth(depth: int, *, location: str) -> None:
    if depth > MAX_JSON_NESTING:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "lifecycle resource exceeds the maximum typed nesting depth "
            f"of {MAX_JSON_NESTING}",
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


def _declared_model_types(declared_type: object) -> tuple[type[BaseModel], ...]:
    declared_type = _unwrap_declared_type(declared_type)
    if isinstance(declared_type, type) and issubclass(declared_type, BaseModel):
        return (declared_type,)
    if get_origin(declared_type) in (Union, UnionType):
        return tuple(
            model
            for branch in get_args(declared_type)
            for model in _declared_model_types(branch)
        )
    return ()


def _declared_scalar_types(declared_type: object) -> tuple[type[object], ...]:
    declared_type = _unwrap_declared_type(declared_type)
    for scalar_type in (bool, int, float, str):
        if declared_type is scalar_type:
            return (scalar_type,)
    if isinstance(declared_type, type) and issubclass(declared_type, Enum):
        return (declared_type,)
    if get_origin(declared_type) is Literal:
        return tuple(dict.fromkeys(type(value) for value in get_args(declared_type)))
    return ()


def _raise_model_type_error(
    value: object,
    expected: tuple[type[BaseModel], ...],
    *,
    location: str,
) -> None:
    expected_names = ", ".join(model.__name__ for model in expected)
    expectation = expected_names or "no Pydantic model"
    raise ChangeLifecycleValidationError(
        ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        "lifecycle value must use an exact canonical model type "
        f"({expectation}); got {type(value).__name__}",
        location=location,
    )


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


def _raise_scalar_type_error(
    value: object,
    expected: tuple[type[object], ...],
    *,
    location: str,
) -> None:
    expected_names = ", ".join(item.__name__ for item in expected)
    raise ChangeLifecycleValidationError(
        ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        "lifecycle value must use its exact declared scalar type "
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
    raise ChangeLifecycleValidationError(
        ChangeLifecycleErrorCode.INVALID_STRUCTURE,
        "lifecycle value must use its declared canonical container type "
        f"{expected_name}; got {type(value).__name__}",
        location=location,
    )


def canonical_change_lifecycle_digest(
    document: ChangeLifecycleDocument,
) -> Digest:
    return Digest(
        kind="digest",
        algorithm="sha-256",
        value=hashlib.sha256(canonical_change_lifecycle_json(document)).hexdigest(),
    )


def _require_exact_lifecycle_resource(
    value: object,
    expected_type: type[BaseModel],
    *,
    location: str,
) -> None:
    if type(value) is not expected_type:
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            "lifecycle reference source must use its exact declared "
            f"{expected_type.__name__} type; got {type(value).__name__}",
            location=location,
        )


def change_proposal_ref(proposal: ChangeProposal) -> ChangeProposalRef:
    _require_exact_lifecycle_resource(
        proposal,
        ChangeProposal,
        location="$.proposal",
    )
    return ChangeProposalRef(
        kind="change_proposal_ref",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=CHANGE_PROPOSAL_SCHEMA_URI,
        change_id=proposal.change_id,
        canonical_digest=canonical_change_lifecycle_digest(proposal),
    )


def behavior_delta_ref(delta: BehaviorDelta) -> BehaviorDeltaRef:
    _require_exact_lifecycle_resource(
        delta,
        BehaviorDelta,
        location="$.delta",
    )
    return BehaviorDeltaRef(
        kind="behavior_delta_ref",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=BEHAVIOR_DELTA_SCHEMA_URI,
        change_id=delta.change_id,
        canonical_digest=canonical_change_lifecycle_digest(delta),
    )


def task_graph_ref(graph: TaskGraph) -> TaskGraphRef:
    _require_exact_lifecycle_resource(
        graph,
        TaskGraph,
        location="$.tasks",
    )
    return TaskGraphRef(
        kind="task_graph_ref",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=TASK_GRAPH_SCHEMA_URI,
        change_id=graph.change_id,
        canonical_digest=canonical_change_lifecycle_digest(graph),
    )


def implementation_record_ref(
    record: ImplementationRecord,
) -> ImplementationRecordRef:
    _require_exact_lifecycle_resource(
        record,
        ImplementationRecord,
        location="$.implementation",
    )
    return ImplementationRecordRef(
        kind="implementation_record_ref",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=IMPLEMENTATION_RECORD_SCHEMA_URI,
        change_id=record.change_id,
        canonical_digest=canonical_change_lifecycle_digest(record),
    )


def verification_record_ref(
    record: VerificationRecord,
) -> VerificationRecordRef:
    _require_exact_lifecycle_resource(
        record,
        VerificationRecord,
        location="$.verification",
    )
    return VerificationRecordRef(
        kind="verification_record_ref",
        change_lifecycle_version=CHANGE_LIFECYCLE_VERSION,
        schema_uri=VERIFICATION_RECORD_SCHEMA_URI,
        change_id=record.change_id,
        canonical_digest=canonical_change_lifecycle_digest(record),
    )


def parse_change_proposal_json(payload: str | bytes) -> ChangeProposal:
    return _parse_change_document(payload, ChangeProposal)


def parse_behavior_delta_json(payload: str | bytes) -> BehaviorDelta:
    return _parse_change_document(payload, BehaviorDelta)


def parse_task_graph_json(payload: str | bytes) -> TaskGraph:
    return _parse_change_document(payload, TaskGraph)


def parse_implementation_record_json(
    payload: str | bytes,
) -> ImplementationRecord:
    return _parse_change_document(payload, ImplementationRecord)


def parse_verification_record_json(
    payload: str | bytes,
) -> VerificationRecord:
    return _parse_change_document(payload, VerificationRecord)


def parse_archive_record_json(payload: str | bytes) -> ArchiveRecord:
    return _parse_change_document(payload, ArchiveRecord)


def _parse_change_document(payload: str | bytes, model: Any):
    if not isinstance(payload, (str, bytes)):
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_JSON,
            "lifecycle JSON payload must be str or bytes; "
            f"got {type(payload).__name__}",
            location="$",
        )
    try:
        decoded = decode_strict_json_object(payload)
    except IRValidationError as error:
        code = (
            ChangeLifecycleErrorCode.DUPLICATE_JSON_MEMBER
            if error.code is IRErrorCode.DUPLICATE_JSON_MEMBER
            else ChangeLifecycleErrorCode.INVALID_JSON
        )
        raise ChangeLifecycleValidationError(
            code,
            str(error),
            location="$",
        ) from error
    normalized = json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    try:
        document = model.model_validate_json(normalized)
    except PydanticValidationError as error:
        detail = error.errors(
            include_context=False,
            include_input=False,
            include_url=False,
        )[0]
        raise ChangeLifecycleValidationError(
            ChangeLifecycleErrorCode.INVALID_STRUCTURE,
            detail["msg"],
            location=_pydantic_location(detail["loc"]),
        ) from error
    if isinstance(document, ArchiveRecord):
        return _normalize_embedded_behavior(document)
    return document


def _pydantic_location(components: tuple[Any, ...]) -> str:
    location = "$"
    for component in components:
        if isinstance(component, int):
            location += f"[{component}]"
        else:
            location += f".{component}"
    return location


__all__ = [
    "BEHAVIOR_DELTA_SCHEMA_URI",
    "CHANGE_PROPOSAL_SCHEMA_URI",
    "behavior_delta_ref",
    "canonical_change_lifecycle_digest",
    "canonical_change_lifecycle_json",
    "change_proposal_ref",
    "implementation_record_ref",
    "parse_archive_record_json",
    "parse_behavior_delta_json",
    "parse_change_proposal_json",
    "parse_implementation_record_json",
    "parse_task_graph_json",
    "parse_verification_record_json",
    "task_graph_ref",
    "verification_record_ref",
]
