const BASE = '/api';

export interface SpecSummary {
  kind: string;
  name: string;
  version: string;
  owner: string;
  tags: string[];
}

export interface SpecCatalog {
  specs: SpecSummary[];
  total_count: number;
  kind_counts: Record<string, number>;
}

export interface SpecDetail {
  kind: string;
  name: string;
  version: string;
  owner: string;
  tags: string[];
  raw_yaml: string;
  impl_status: string;
}

export interface RelationshipEdge {
  ref: string;
  kind: string;
  name: string;
  edge_type: string;
}

export interface SpecRelationships {
  upstream: RelationshipEdge[];
  downstream: RelationshipEdge[];
  edge_count: number;
}

export interface GraphNode {
  id: string;
  kind: string;
  name: string;
  group: number;
}

export interface GraphLink {
  source: string;
  target: string;
  edge_type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  node_count: number;
  edge_count: number;
}

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v);
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  listSpecs: (kind?: string, search?: string) =>
    get<SpecCatalog>('/specs', { kind: kind || '', search: search || '' }),

  getSpecDetail: (kind: string, name: string) =>
    get<SpecDetail>(`/specs/${kind}/${name}`),

  getSpecRelationships: (kind: string, name: string) =>
    get<SpecRelationships>(`/specs/${kind}/${name}/rels`),

  getGraph: () => get<GraphData>('/graph'),
};
