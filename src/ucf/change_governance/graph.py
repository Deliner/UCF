from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterable

from ucf.change_governance.models import (
    DocumentCoordinate,
    EntityCoordinate,
    GraphSide,
    ImpactCoordinate,
    ImpactEdge,
    ImpactFinding,
    ImpactPrecision,
    ImpactRelation,
    ImpactWitness,
    PortCoordinate,
)
from ucf.change_lifecycle.models import (
    AddedBehavior,
    BehaviorDelta,
    BehaviorDeltaEntry,
    ModifiedBehavior,
)
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
    Observation,
    PortRef,
    Provenance,
    Step,
    UseCase,
    VerificationEvidence,
)

type CoordinateKey = tuple[str, ...]


def derive_impact_graph(
    delta: BehaviorDelta,
    findings: tuple[ImpactFinding, ...],
    *,
    base_behavior: BehaviorIR,
    final_behavior: BehaviorIR,
) -> tuple[tuple[ImpactEdge, ...], tuple[ImpactWitness, ...]]:
    side_documents = {
        GraphSide.BASE: base_behavior,
        GraphSide.FINAL: final_behavior,
    }
    edges = tuple(
        sorted(
            (
                edge
                for side, document in side_documents.items()
                for edge in _extract_edges(document, side=side)
            ),
            key=_edge_key,
        )
    )
    witnesses = _derive_witnesses(
        delta,
        findings,
        edges=edges,
        side_documents=side_documents,
    )
    return edges, witnesses


def _extract_edges(
    document: BehaviorIR,
    *,
    side: GraphSide,
) -> tuple[ImpactEdge, ...]:
    entities = {entity.id: entity for entity in document.entities}
    edges: list[ImpactEdge] = []
    document_coordinate = DocumentCoordinate(
        kind="document_coordinate",
        document_id=document.document_id,
    )
    for position, ref in enumerate(_sorted_refs(document.roots)):
        edges.append(
            _edge(
                side=side,
                source=document_coordinate,
                target=_entity_coordinate(ref),
                field_path=f"/roots/{position}",
                relation=ImpactRelation.ROOT_REFERENCE,
            )
        )

    step_port_definition_edges: dict[
        tuple[CoordinateKey, CoordinateKey],
        ImpactEdge,
    ] = {}
    for entity in sorted(
        document.entities,
        key=lambda item: (item.kind.value, item.id),
    ):
        source = _entity_coordinate(entity)
        if isinstance(entity, Action):
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="effects",
                refs=entity.effects,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="requires",
                refs=entity.requires,
            )
        elif isinstance(entity, UseCase):
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="steps",
                refs=entity.steps,
                ordered=True,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="invariants",
                refs=entity.invariants,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="requires",
                refs=entity.requires,
            )
        elif isinstance(entity, Step):
            _append_single_ref_edge(
                edges,
                side=side,
                source=source,
                field_path="/action",
                ref=entity.action,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="bindings",
                refs=entity.bindings,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="effects",
                refs=entity.effects,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="observations",
                refs=entity.observations,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="requires",
                refs=entity.requires,
            )
        elif isinstance(entity, Binding):
            _append_port_edge(
                edges,
                step_port_definition_edges,
                side=side,
                source=source,
                field_path="/target",
                ref=entity.target,
                entities=entities,
            )
            if isinstance(entity.source, PortRef):
                _append_port_edge(
                    edges,
                    step_port_definition_edges,
                    side=side,
                    source=source,
                    field_path="/source",
                    ref=entity.source,
                    entities=entities,
                )
        elif isinstance(entity, Effect):
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="requires",
                refs=entity.requires,
            )
        elif isinstance(entity, Observation):
            _append_single_ref_edge(
                edges,
                side=side,
                source=source,
                field_path="/subject",
                ref=entity.subject,
            )
        elif isinstance(entity, Invariant):
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="applies_to",
                refs=entity.applies_to,
            )
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="requires",
                refs=entity.requires,
            )
        elif isinstance(entity, VerificationEvidence):
            _append_ref_edges(
                edges,
                side=side,
                source=source,
                field="subjects",
                refs=entity.subjects,
            )
        elif not isinstance(entity, (CapabilityRequirement, Provenance)):
            raise AssertionError(f"unhandled IR entity type: {type(entity)!r}")

        if not isinstance(entity, Provenance):
            _append_single_ref_edge(
                edges,
                side=side,
                source=source,
                field_path="/provenance",
                ref=entity.provenance,
            )
        if isinstance(entity, CapabilityRequirement) and entity.required:
            edges.append(
                _edge(
                    side=side,
                    source=document_coordinate,
                    target=source,
                    field_path=f"/@required_capabilities/{entity.id}",
                    relation=ImpactRelation.REQUIRED_CAPABILITY,
                    precision=ImpactPrecision.DEFINITE,
                )
            )

    edges.extend(step_port_definition_edges.values())
    return tuple(edges)


def _append_ref_edges(
    edges: list[ImpactEdge],
    *,
    side: GraphSide,
    source: EntityCoordinate,
    field: str,
    refs: Iterable[EntityRef],
    ordered: bool = False,
) -> None:
    selected = tuple(refs)
    if not ordered:
        selected = _sorted_refs(selected)
    for position, ref in enumerate(selected):
        _append_single_ref_edge(
            edges,
            side=side,
            source=source,
            field_path=f"/{field}/{position}",
            ref=ref,
        )


def _append_single_ref_edge(
    edges: list[ImpactEdge],
    *,
    side: GraphSide,
    source: EntityCoordinate,
    field_path: str,
    ref: EntityRef,
) -> None:
    edges.append(
        _edge(
            side=side,
            source=source,
            target=_entity_coordinate(ref),
            field_path=field_path,
            relation=ImpactRelation.ENTITY_REFERENCE,
        )
    )


def _append_port_edge(
    edges: list[ImpactEdge],
    step_port_definition_edges: dict[
        tuple[CoordinateKey, CoordinateKey],
        ImpactEdge,
    ],
    *,
    side: GraphSide,
    source: EntityCoordinate,
    field_path: str,
    ref: PortRef,
    entities: dict[str, Entity],
) -> None:
    coordinate = _port_coordinate(ref, entities=entities)
    edges.append(
        _edge(
            side=side,
            source=source,
            target=coordinate,
            field_path=field_path,
            relation=ImpactRelation.PORT_SELECTION,
        )
    )
    if coordinate.owner_kind is not EntityKind.STEP:
        return
    if coordinate.resolved_action_id is None:
        raise AssertionError("validated step port lacks a resolved action")
    definition = PortCoordinate(
        kind="port_coordinate",
        owner_kind=EntityKind.ACTION,
        owner_id=coordinate.resolved_action_id,
        direction=coordinate.direction,
        name=coordinate.name,
        resolved_action_id=None,
    )
    edge = _edge(
        side=side,
        source=coordinate,
        target=definition,
        field_path="/action",
        relation=ImpactRelation.STEP_PORT_DEFINITION,
    )
    step_port_definition_edges[
        (_coordinate_key(coordinate), _coordinate_key(definition))
    ] = edge


def _edge(
    *,
    side: GraphSide,
    source: ImpactCoordinate,
    target: ImpactCoordinate,
    field_path: str,
    relation: ImpactRelation,
    precision: ImpactPrecision = ImpactPrecision.MAY_AFFECT,
) -> ImpactEdge:
    return ImpactEdge(
        kind="impact_edge",
        side=side,
        source=source,
        target=target,
        field_path=field_path,
        relation=relation,
        precision=precision,
    )


def _port_coordinate(
    ref: PortRef,
    *,
    entities: dict[str, Entity],
) -> PortCoordinate:
    owner = entities[ref.owner.target_id]
    resolved_action_id = owner.action.target_id if isinstance(owner, Step) else None
    return PortCoordinate(
        kind="port_coordinate",
        owner_kind=ref.owner.target_kind,
        owner_id=ref.owner.target_id,
        direction=ref.direction,
        name=ref.name,
        resolved_action_id=resolved_action_id,
    )


def _entity_coordinate(value: Entity | EntityRef) -> EntityCoordinate:
    if isinstance(value, EntityRef):
        target_kind = value.target_kind
        target_id = value.target_id
    else:
        target_kind = value.kind
        target_id = value.id
    return EntityCoordinate(
        kind="entity_coordinate",
        target_kind=target_kind,
        target_id=target_id,
    )


def _sorted_refs(refs: Iterable[EntityRef]) -> tuple[EntityRef, ...]:
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.target_kind.value, ref.target_id),
        )
    )


def _derive_witnesses(
    delta: BehaviorDelta,
    findings: tuple[ImpactFinding, ...],
    *,
    edges: tuple[ImpactEdge, ...],
    side_documents: dict[GraphSide, BehaviorIR],
) -> tuple[ImpactWitness, ...]:
    reverse: dict[
        tuple[GraphSide, CoordinateKey],
        list[int],
    ] = defaultdict(list)
    coordinates: dict[CoordinateKey, ImpactCoordinate] = {}
    for index, edge in enumerate(edges):
        reverse[(edge.side, _coordinate_key(edge.target))].append(index)
        coordinates[_coordinate_key(edge.source)] = edge.source
        coordinates[_coordinate_key(edge.target)] = edge.target

    witnesses = []
    for entry, finding in zip(delta.entries, findings, strict=True):
        for side in _entry_sides(entry):
            seeds = _entry_seeds(
                entry,
                side=side,
                side_documents=side_documents,
                edges=edges,
            )
            seed_keys = {_coordinate_key(seed) for seed in seeds}
            queue = [(0, (), key) for key in sorted(seed_keys)]
            heapq.heapify(queue)
            visited: set[CoordinateKey] = set()
            while queue:
                _length, path, current_key = heapq.heappop(queue)
                if current_key in visited:
                    continue
                visited.add(current_key)
                if path:
                    witnesses.append(
                        ImpactWitness(
                            kind="impact_witness",
                            direct_subject=finding.subject,
                            side=side,
                            affected=coordinates[current_key],
                            precision=_path_precision(path, edges=edges),
                            edge_indexes=path,
                        )
                    )
                for edge_index in reverse.get((side, current_key), ()):
                    source_key = _coordinate_key(edges[edge_index].source)
                    if source_key not in visited:
                        heapq.heappush(
                            queue,
                            (
                                len(path) + 1,
                                (*path, edge_index),
                                source_key,
                            ),
                        )
    return tuple(sorted(witnesses, key=_witness_key))


def _entry_sides(entry: BehaviorDeltaEntry) -> tuple[GraphSide, ...]:
    if isinstance(entry, AddedBehavior):
        return (GraphSide.FINAL,)
    if isinstance(entry, ModifiedBehavior):
        return (GraphSide.BASE, GraphSide.FINAL)
    return (GraphSide.BASE,)


def _entry_seeds(
    entry: BehaviorDeltaEntry,
    *,
    side: GraphSide,
    side_documents: dict[GraphSide, BehaviorIR],
    edges: tuple[ImpactEdge, ...],
) -> tuple[ImpactCoordinate, ...]:
    document = side_documents[side]
    subject = (
        entry.final_subject if isinstance(entry, AddedBehavior) else entry.base_subject
    )
    entity = next(
        candidate
        for candidate in document.entities
        if candidate.kind is subject.target_kind and candidate.id == subject.target_id
    )
    seeds: list[ImpactCoordinate] = [_entity_coordinate(entity)]
    if isinstance(entry, ModifiedBehavior):
        seeds.extend(
            _modified_port_seeds(
                entry,
                side=side,
                side_documents=side_documents,
                edges=edges,
            )
        )
    else:
        seeds.extend(_all_port_seeds(entity, side=side, edges=edges))
    unique = {_coordinate_key(seed): seed for seed in seeds}
    return tuple(unique[key] for key in sorted(unique))


def _modified_port_seeds(
    entry: ModifiedBehavior,
    *,
    side: GraphSide,
    side_documents: dict[GraphSide, BehaviorIR],
    edges: tuple[ImpactEdge, ...],
) -> tuple[ImpactCoordinate, ...]:
    document = side_documents[side]
    opposite = side_documents[
        GraphSide.FINAL if side is GraphSide.BASE else GraphSide.BASE
    ]
    identity = (
        entry.base_subject.target_kind,
        entry.base_subject.target_id,
    )
    current = next(
        entity for entity in document.entities if (entity.kind, entity.id) == identity
    )
    previous_or_next = next(
        entity for entity in opposite.entities if (entity.kind, entity.id) == identity
    )
    if isinstance(current, (Action, UseCase)):
        if not isinstance(previous_or_next, type(current)):
            raise AssertionError("delta retained identity with a different type")
        return _changed_declared_ports(
            current=current,
            opposite=previous_or_next,
        )
    if (
        isinstance(current, Step)
        and isinstance(previous_or_next, Step)
        and current.action != previous_or_next.action
    ):
        return _selected_step_ports(
            current.id,
            side=side,
            edges=edges,
        )
    return ()


def _changed_declared_ports(
    *,
    current: Action | UseCase,
    opposite: Action | UseCase,
) -> tuple[PortCoordinate, ...]:
    seeds = []
    for direction, current_ports, opposite_ports in (
        ("input", current.input_ports, opposite.input_ports),
        ("output", current.output_ports, opposite.output_ports),
    ):
        opposite_by_name = {port.name: port for port in opposite_ports}
        for port in current_ports:
            if opposite_by_name.get(port.name) == port:
                continue
            seeds.append(
                PortCoordinate(
                    kind="port_coordinate",
                    owner_kind=current.kind,
                    owner_id=current.id,
                    direction=direction,
                    name=port.name,
                    resolved_action_id=None,
                )
            )
    return tuple(seeds)


def _all_port_seeds(
    entity: Entity,
    *,
    side: GraphSide,
    edges: tuple[ImpactEdge, ...],
) -> tuple[PortCoordinate, ...]:
    if isinstance(entity, (Action, UseCase)):
        return tuple(
            PortCoordinate(
                kind="port_coordinate",
                owner_kind=entity.kind,
                owner_id=entity.id,
                direction=direction,
                name=port.name,
                resolved_action_id=None,
            )
            for direction, ports in (
                ("input", entity.input_ports),
                ("output", entity.output_ports),
            )
            for port in ports
        )
    if isinstance(entity, Step):
        return _selected_step_ports(entity.id, side=side, edges=edges)
    return ()


def _selected_step_ports(
    step_id: str,
    *,
    side: GraphSide,
    edges: tuple[ImpactEdge, ...],
) -> tuple[PortCoordinate, ...]:
    selected = {}
    for edge in edges:
        for coordinate in (edge.source, edge.target):
            if (
                edge.side is side
                and isinstance(coordinate, PortCoordinate)
                and coordinate.owner_kind is EntityKind.STEP
                and coordinate.owner_id == step_id
            ):
                selected[_coordinate_key(coordinate)] = coordinate
    return tuple(selected[key] for key in sorted(selected))


def _path_precision(
    path: tuple[int, ...],
    *,
    edges: tuple[ImpactEdge, ...],
) -> ImpactPrecision:
    precisions = {edges[index].precision for index in path}
    if ImpactPrecision.UNRESOLVED in precisions:
        return ImpactPrecision.UNRESOLVED
    if ImpactPrecision.MAY_AFFECT in precisions:
        return ImpactPrecision.MAY_AFFECT
    return ImpactPrecision.DEFINITE


def _coordinate_key(coordinate: ImpactCoordinate) -> CoordinateKey:
    if isinstance(coordinate, EntityCoordinate):
        return (
            coordinate.kind,
            coordinate.target_kind.value,
            coordinate.target_id,
        )
    if isinstance(coordinate, PortCoordinate):
        return (
            coordinate.kind,
            coordinate.owner_kind.value,
            coordinate.owner_id,
            coordinate.direction,
            coordinate.name,
            coordinate.resolved_action_id or "",
        )
    return (coordinate.kind, coordinate.document_id)


def _edge_key(edge: ImpactEdge) -> tuple[object, ...]:
    return (
        edge.side.value,
        _coordinate_key(edge.source),
        _coordinate_key(edge.target),
        edge.field_path,
        edge.relation.value,
        edge.precision.value,
    )


def _witness_key(witness: ImpactWitness) -> tuple[object, ...]:
    return (
        witness.side.value,
        witness.direct_subject.operation,
        witness.direct_subject.target_kind.value,
        witness.direct_subject.target_id,
        _coordinate_key(witness.affected),
        witness.edge_indexes,
    )
