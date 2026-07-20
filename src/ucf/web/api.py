"""FastAPI routes for the UCF web dashboard.

@implements("actions/list-spec-catalog")
@implements("actions/get-spec-detail")
@implements("actions/get-spec-relationships")
@implements("actions/build-graph-json")
@implements("use-cases/browse-spec-catalog")
@implements("use-cases/inspect-spec-detail")
@implements("use-cases/explore-dependency-graph")
@implements("use-cases/browse-spec-catalog-web")
@implements("use-cases/inspect-spec-detail-web")
@implements("use-cases/explore-dependency-graph-web")
@implements("actions/ui-filter-spec-catalog")
@implements("actions/ui-navigate-to-spec")
@implements("actions/ui-toggle-detail-tab")
@implements("actions/ui-navigate-to-related-spec")
@implements("actions/ui-interact-with-graph")
@implements("actions/ui-toggle-graph-view")
@implements("components/built-graph")
"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from ucf.graph.dependency import DependencyGraph
from ucf.parser.registry import SpecRegistry
from ucf.web.serializers import (
    GraphLink,
    GraphNode,
    GraphResponse,
    RelationshipEdge,
    SpecCatalogResponse,
    SpecDetailResponse,
    SpecRelationshipsResponse,
    SpecSummary,
)

router = APIRouter(prefix="/api")

_registry: SpecRegistry | None = None
_graph: DependencyGraph | None = None
_spec_paths: dict[str, Path] = {}

_KIND_GROUP = {
    "action": 0,
    "usecase": 1,
    "component": 2,
    "event": 3,
    "protocol": 4,
    "invariant": 5,
}

_SINGULAR_TO_PLURAL = {
    "action": "actions",
    "event": "events",
    "component": "components",
    "protocol": "protocols",
    "usecase": "use-cases",
    "invariant": "invariants",
}


def init_registry(registry: SpecRegistry, graph: DependencyGraph) -> None:
    global _registry, _graph
    _registry = registry
    _graph = graph


@router.get("/specs", response_model=SpecCatalogResponse)
def list_specs(
    kind: str | None = None, search: str | None = None
) -> SpecCatalogResponse:
    assert _registry is not None
    specs = _registry.all_specs()

    if kind:
        specs = [s for s in specs if s.kind == kind]

    if search:
        q = search.lower()
        specs = [s for s in specs if q in s.metadata.name.lower()]

    summaries = [
        SpecSummary(
            kind=s.kind,
            name=s.metadata.name,
            version=s.metadata.version or "",
            owner=s.metadata.owner or "",
            tags=s.metadata.tags or [],
        )
        for s in specs
    ]

    kind_counts: dict[str, int] = {}
    for s in _registry.all_specs():
        kind_counts[s.kind] = kind_counts.get(s.kind, 0) + 1

    return SpecCatalogResponse(
        specs=summaries,
        total_count=len(summaries),
        kind_counts=kind_counts,
    )


@router.get("/specs/{kind}/{name}", response_model=SpecDetailResponse)
def get_spec_detail(kind: str, name: str) -> SpecDetailResponse:
    assert _registry is not None
    spec = _registry.get(kind, name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Spec '{kind}/{name}' not found")

    plural = _SINGULAR_TO_PLURAL.get(kind, f"{kind}s")
    ref_key = f"{plural}/{name}"
    path = _registry.get_path(ref_key)

    raw = ""
    if path and path.exists():
        raw = path.read_text(encoding="utf-8")
    else:
        raw = yaml.dump(spec.model_dump(exclude_none=True), default_flow_style=False)

    impl_status = "unknown"
    try:
        from ucf.drift.mapper import SpecCodeMapper
        from ucf.drift.scanner import SourceScanner

        src_dir = Path("src")
        if src_dir.exists():
            scanner = SourceScanner(src_dir)
            scan_result = scanner.scan()
            mapper = SpecCodeMapper(_registry, scan_result.implementations)
            spec_map = mapper.build()
            mapped = ref_key in spec_map.spec_to_code
            impl_status = "mapped" if mapped else "unimplemented"
    except Exception:
        impl_status = "unknown"

    return SpecDetailResponse(
        kind=kind,
        name=name,
        version=spec.metadata.version or "",
        owner=spec.metadata.owner or "",
        tags=spec.metadata.tags or [],
        raw_yaml=raw,
        impl_status=impl_status,
    )


@router.get("/specs/{kind}/{name}/rels", response_model=SpecRelationshipsResponse)
def get_spec_relationships(kind: str, name: str) -> SpecRelationshipsResponse:
    assert _registry is not None and _graph is not None
    spec = _registry.get(kind, name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Spec '{kind}/{name}' not found")

    node_id = f"{kind}/{name}"
    g = _graph.g

    upstream: list[RelationshipEdge] = []
    downstream: list[RelationshipEdge] = []

    if g.has_node(node_id):
        for succ in g.successors(node_id):
            parts = succ.split("/", 1)
            data = g.edges[node_id, succ]
            if len(parts) == 2:
                upstream.append(
                    RelationshipEdge(
                        ref=succ,
                        kind=parts[0],
                        name=parts[1],
                        edge_type=data.get("type", "depends_on"),
                    )
                )

        for pred in g.predecessors(node_id):
            parts = pred.split("/", 1)
            data = g.edges[pred, node_id]
            if len(parts) == 2:
                downstream.append(
                    RelationshipEdge(
                        ref=pred,
                        kind=parts[0],
                        name=parts[1],
                        edge_type=data.get("type", "depends_on"),
                    )
                )

    return SpecRelationshipsResponse(
        upstream=upstream,
        downstream=downstream,
        edge_count=len(upstream) + len(downstream),
    )


@router.get("/graph", response_model=GraphResponse)
def get_graph() -> GraphResponse:
    assert _graph is not None
    g = _graph.g

    nodes = []
    for node_id, data in g.nodes(data=True):
        kind = data.get("kind", "unknown")
        name = data.get("name", node_id)
        nodes.append(
            GraphNode(
                id=node_id,
                kind=kind,
                name=name,
                group=_KIND_GROUP.get(kind, 6),
            )
        )

    links = []
    for src, tgt, data in g.edges(data=True):
        links.append(
            GraphLink(
                source=src,
                target=tgt,
                edge_type=data.get("type", "depends_on"),
            )
        )

    return GraphResponse(
        nodes=nodes,
        links=links,
        node_count=len(nodes),
        edge_count=len(links),
    )
