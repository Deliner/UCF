"""Pydantic response models for the web API.

@implements("actions/list-spec-catalog")
@implements("actions/get-spec-detail")
@implements("actions/get-spec-relationships")
@implements("actions/build-graph-json")
"""

from __future__ import annotations

from pydantic import BaseModel


class SpecSummary(BaseModel):
    kind: str
    name: str
    version: str = ""
    owner: str = ""
    tags: list[str] = []


class SpecCatalogResponse(BaseModel):
    specs: list[SpecSummary]
    total_count: int
    kind_counts: dict[str, int]


class SpecDetailResponse(BaseModel):
    kind: str
    name: str
    version: str = ""
    owner: str = ""
    tags: list[str] = []
    raw_yaml: str
    impl_status: str


class RelationshipEdge(BaseModel):
    ref: str
    kind: str
    name: str
    edge_type: str = "depends_on"


class SpecRelationshipsResponse(BaseModel):
    upstream: list[RelationshipEdge]
    downstream: list[RelationshipEdge]
    edge_count: int


class GraphNode(BaseModel):
    id: str
    kind: str
    name: str
    group: int = 0


class GraphLink(BaseModel):
    source: str
    target: str
    edge_type: str = "depends_on"


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]
    node_count: int
    edge_count: int
