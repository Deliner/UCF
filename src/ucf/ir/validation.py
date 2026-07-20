from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from ucf.ir.errors import IRErrorCode, IRValidationError
from ucf.ir.models import (
    Action,
    BehaviorIR,
    Binding,
    CapabilityRequirement,
    Effect,
    Entity,
    EntityKind,
    EntityRef,
    Invariant,
    IRValue,
    ListValue,
    Observation,
    Port,
    PortRef,
    Provenance,
    RecordValue,
    Step,
    UseCase,
    ValueKind,
    VerificationEvidence,
)

SEMANTIC_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
type EntityIndex = dict[str, Entity]


def _fail(
    code: IRErrorCode,
    message: str,
    *,
    location: str,
) -> None:
    raise IRValidationError(code, message, location=location)


def _build_index(document: BehaviorIR) -> EntityIndex:
    index: EntityIndex = {}
    capability_names: dict[str, str] = {}
    for position, entity in enumerate(document.entities):
        previous = index.get(entity.id)
        if previous is not None:
            _fail(
                IRErrorCode.DUPLICATE_IDENTITY,
                (
                    f"entity id {entity.id!r} is used by both "
                    f"{previous.kind.value!r} and {entity.kind.value!r}"
                ),
                location=f"$.entities[{position}].id",
            )
        if isinstance(entity, CapabilityRequirement):
            previous_id = capability_names.get(entity.name)
            if previous_id is not None:
                _fail(
                    IRErrorCode.DUPLICATE_CAPABILITY,
                    (
                        f"capability name {entity.name!r} is declared by both "
                        f"{previous_id!r} and {entity.id!r}"
                    ),
                    location=f"$.entities[{position}].name",
                )
            capability_names[entity.name] = entity.id
        index[entity.id] = entity
    return index


def _resolve_ref(
    ref: EntityRef,
    index: EntityIndex,
    *,
    location: str,
    expected: set[EntityKind] | None = None,
) -> Entity:
    target = index.get(ref.target_id)
    if target is None:
        _fail(
            IRErrorCode.BROKEN_REFERENCE,
            f"reference target {ref.target_id!r} does not exist",
            location=location,
        )
    if target.kind is not ref.target_kind:
        _fail(
            IRErrorCode.WRONG_TARGET_KIND,
            (
                f"reference declares {ref.target_kind.value!r}, but "
                f"{ref.target_id!r} is {target.kind.value!r}"
            ),
            location=f"{location}.target_kind",
        )
    if expected is not None and target.kind not in expected:
        allowed = ", ".join(sorted(kind.value for kind in expected))
        _fail(
            IRErrorCode.WRONG_TARGET_KIND,
            (
                f"{ref.target_id!r} has kind {target.kind.value!r}; "
                f"expected one of: {allowed}"
            ),
            location=f"{location}.target_kind",
        )
    return target


def _validate_ref_sequence(
    refs: Sequence[EntityRef],
    index: EntityIndex,
    *,
    location: str,
    expected: set[EntityKind] | None = None,
    unique: bool = True,
) -> None:
    seen: set[tuple[EntityKind, str]] = set()
    for position, ref in enumerate(refs):
        identity = (ref.target_kind, ref.target_id)
        if unique and identity in seen:
            _fail(
                IRErrorCode.DUPLICATE_REFERENCE,
                (
                    f"reference to {ref.target_kind.value!r} "
                    f"{ref.target_id!r} is duplicated"
                ),
                location=f"{location}[{position}]",
            )
        seen.add(identity)
        _resolve_ref(
            ref,
            index,
            location=f"{location}[{position}]",
            expected=expected,
        )


def _require_semantic_capability(
    refs: Sequence[EntityRef],
    index: EntityIndex,
    *,
    location: str,
) -> None:
    if any(
        isinstance(index[ref.target_id], CapabilityRequirement)
        and index[ref.target_id].required
        for ref in refs
    ):
        return
    _fail(
        IRErrorCode.MISSING_CAPABILITY_REQUIREMENT,
        "opaque semantics require at least one required capability",
        location=location,
    )


def _validate_ports(
    ports: Sequence[Port],
    *,
    location: str,
) -> None:
    seen: set[str] = set()
    for position, port in enumerate(ports):
        if port.name in seen:
            _fail(
                IRErrorCode.DUPLICATE_PORT,
                f"port name {port.name!r} is duplicated",
                location=f"{location}[{position}].name",
            )
        seen.add(port.name)


def _validate_value(value: IRValue, *, location: str) -> None:
    if isinstance(value, ListValue):
        for position, item in enumerate(value.items):
            _validate_value(item, location=f"{location}.items[{position}]")
    elif isinstance(value, RecordValue):
        seen: set[str] = set()
        for position, entry in enumerate(value.entries):
            if entry.name in seen:
                _fail(
                    IRErrorCode.DUPLICATE_IDENTITY,
                    f"record entry name {entry.name!r} is duplicated",
                    location=f"{location}.entries[{position}].name",
                )
            seen.add(entry.name)
            _validate_value(
                entry.value,
                location=f"{location}.entries[{position}].value",
            )


def validate_ir_value(value: IRValue) -> None:
    """Validate the semantic invariants of one standalone tagged IR value."""

    _validate_value(value, location="$")


def _step_action(
    step: Step,
    index: EntityIndex,
    *,
    location: str,
) -> Action:
    action = _resolve_ref(
        step.action,
        index,
        location=location,
        expected={EntityKind.ACTION},
    )
    if not isinstance(action, Action):
        raise AssertionError("kind-discriminated entity index is inconsistent")
    return action


def _resolve_port(
    ref: PortRef,
    index: EntityIndex,
    *,
    location: str,
) -> Port:
    owner = _resolve_ref(
        ref.owner,
        index,
        location=f"{location}.owner",
        expected={EntityKind.USE_CASE, EntityKind.STEP},
    )
    if isinstance(owner, Step):
        port_owner: Action | UseCase = _step_action(
            owner,
            index,
            location=f"{location}.owner.action",
        )
    elif isinstance(owner, UseCase):
        port_owner = owner
    else:
        raise AssertionError("validated port owner kind is inconsistent")

    ports = (
        port_owner.input_ports
        if ref.direction == "input"
        else port_owner.output_ports
    )
    port = next((candidate for candidate in ports if candidate.name == ref.name), None)
    if port is None:
        _fail(
            IRErrorCode.UNKNOWN_PORT,
            (
                f"{ref.direction} port {ref.name!r} does not exist on "
                f"{ref.owner.target_id!r}"
            ),
            location=f"{location}.name",
        )
    return port


def _validate_binding(
    binding: Binding,
    index: EntityIndex,
    *,
    location: str,
) -> None:
    target_owner = _resolve_ref(
        binding.target.owner,
        index,
        location=f"{location}.target.owner",
        expected={EntityKind.STEP},
    )
    if not isinstance(target_owner, Step):
        raise AssertionError("validated binding target owner is inconsistent")
    if binding.target.direction != "input":
        _fail(
            IRErrorCode.INVALID_BINDING,
            "binding target must be an input port",
            location=f"{location}.target.direction",
        )
    target = _resolve_port(binding.target, index, location=f"{location}.target")

    if isinstance(binding.source, PortRef):
        source_owner = _resolve_ref(
            binding.source.owner,
            index,
            location=f"{location}.source.owner",
            expected={EntityKind.USE_CASE, EntityKind.STEP},
        )
        valid_direction = (
            isinstance(source_owner, UseCase)
            and binding.source.direction == "input"
        ) or (
            isinstance(source_owner, Step)
            and binding.source.direction == "output"
        )
        if not valid_direction:
            _fail(
                IRErrorCode.INVALID_BINDING,
                (
                    "binding source must be a use-case input "
                    "or a step output"
                ),
                location=f"{location}.source.direction",
            )
        source_kind = _resolve_port(
            binding.source,
            index,
            location=f"{location}.source",
        ).value_kind
    else:
        _validate_value(binding.source, location=f"{location}.source")
        source_kind = ValueKind(binding.source.kind)
        if source_kind is ValueKind.NULL and target.required:
            _fail(
                IRErrorCode.INVALID_BINDING,
                "null cannot bind to a required input port",
                location=f"{location}.source",
            )

    if source_kind is not ValueKind.NULL and source_kind is not target.value_kind:
        _fail(
            IRErrorCode.INVALID_BINDING,
            (
                f"source value kind {source_kind.value!r} does not match "
                f"target value kind {target.value_kind.value!r}"
            ),
            location=f"{location}.source",
        )


def validate_ir_semantics(document: BehaviorIR) -> None:
    index = _build_index(document)
    _validate_ref_sequence(
        document.roots,
        index,
        location="$.roots",
        expected={EntityKind.USE_CASE},
    )

    for position, entity in enumerate(document.entities):
        location = f"$.entities[{position}]"
        if isinstance(entity, Action):
            _validate_ports(
                entity.input_ports,
                location=f"{location}.input_ports",
            )
            _validate_ports(
                entity.output_ports,
                location=f"{location}.output_ports",
            )
            _validate_ref_sequence(
                entity.effects,
                index,
                location=f"{location}.effects",
                expected={EntityKind.EFFECT},
            )
            _validate_ref_sequence(
                entity.requires,
                index,
                location=f"{location}.requires",
                expected={EntityKind.CAPABILITY_REQUIREMENT},
            )
        elif isinstance(entity, UseCase):
            _validate_ports(
                entity.input_ports,
                location=f"{location}.input_ports",
            )
            _validate_ports(
                entity.output_ports,
                location=f"{location}.output_ports",
            )
            _validate_ref_sequence(
                entity.steps,
                index,
                location=f"{location}.steps",
                expected={EntityKind.STEP},
                unique=False,
            )
            _validate_ref_sequence(
                entity.invariants,
                index,
                location=f"{location}.invariants",
                expected={EntityKind.INVARIANT},
            )
            _validate_ref_sequence(
                entity.requires,
                index,
                location=f"{location}.requires",
                expected={EntityKind.CAPABILITY_REQUIREMENT},
            )
        elif isinstance(entity, Step):
            _step_action(entity, index, location=f"{location}.action")
            _validate_ref_sequence(
                entity.bindings,
                index,
                location=f"{location}.bindings",
                expected={EntityKind.BINDING},
            )
            _validate_ref_sequence(
                entity.effects,
                index,
                location=f"{location}.effects",
                expected={EntityKind.EFFECT},
            )
            _validate_ref_sequence(
                entity.observations,
                index,
                location=f"{location}.observations",
                expected={EntityKind.OBSERVATION},
            )
            _validate_ref_sequence(
                entity.requires,
                index,
                location=f"{location}.requires",
                expected={EntityKind.CAPABILITY_REQUIREMENT},
            )
        elif isinstance(entity, Binding):
            _validate_binding(entity, index, location=location)
        elif isinstance(entity, Effect):
            _validate_value(entity.value, location=f"{location}.value")
            _validate_ref_sequence(
                entity.requires,
                index,
                location=f"{location}.requires",
                expected={EntityKind.CAPABILITY_REQUIREMENT},
            )
            _require_semantic_capability(
                entity.requires,
                index,
                location=f"{location}.requires",
            )
        elif isinstance(entity, Observation):
            _resolve_ref(
                entity.subject,
                index,
                location=f"{location}.subject",
                expected={
                    EntityKind.ACTION,
                    EntityKind.STEP,
                    EntityKind.USE_CASE,
                },
            )
            _validate_value(entity.value, location=f"{location}.value")
        elif isinstance(entity, Invariant):
            _validate_ref_sequence(
                entity.applies_to,
                index,
                location=f"{location}.applies_to",
                expected={
                    EntityKind.ACTION,
                    EntityKind.STEP,
                    EntityKind.USE_CASE,
                },
            )
            _validate_ref_sequence(
                entity.requires,
                index,
                location=f"{location}.requires",
                expected={EntityKind.CAPABILITY_REQUIREMENT},
            )
            _require_semantic_capability(
                entity.requires,
                index,
                location=f"{location}.requires",
            )
        elif isinstance(entity, VerificationEvidence):
            _validate_ref_sequence(
                entity.subjects,
                index,
                location=f"{location}.subjects",
            )
        elif isinstance(entity, Provenance):
            continue
        elif not isinstance(entity, CapabilityRequirement):
            raise AssertionError("unhandled IR entity kind")

        if not isinstance(entity, Provenance):
            _resolve_ref(
                entity.provenance,
                index,
                location=f"{location}.provenance",
                expected={EntityKind.PROVENANCE},
            )


def _version_tuple(version: str, *, location: str) -> tuple[int, int, int]:
    if SEMANTIC_VERSION.fullmatch(version) is None:
        _fail(
            IRErrorCode.INVALID_VALUE,
            f"capability version {version!r} is not normalized major.minor.patch",
            location=location,
        )
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def validate_required_capabilities(
    document: BehaviorIR,
    available: Mapping[str, str],
) -> None:
    for position, entity in enumerate(document.entities):
        if not isinstance(entity, CapabilityRequirement) or not entity.required:
            continue
        actual = available.get(entity.name)
        location = f"$.entities[{position}].minimum_version"
        if actual is None:
            _fail(
                IRErrorCode.UNSUPPORTED_CAPABILITY,
                f"required capability {entity.name!r} is unavailable",
                location=location,
            )
        actual_version = _version_tuple(
            actual,
            location=f"$.capabilities.{entity.name}",
        )
        minimum_version = _version_tuple(
            entity.minimum_version,
            location=location,
        )
        if actual_version < minimum_version:
            _fail(
                IRErrorCode.UNSUPPORTED_CAPABILITY,
                (
                    f"capability {entity.name!r} has version {actual!r}; "
                    f"requires at least {entity.minimum_version!r}"
                ),
                location=location,
            )
