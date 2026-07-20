import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as d3 from 'd3';
import { api, type GraphData, type GraphNode } from '../api/client';

const KIND_COLORS: Record<string, string> = {
  action: '#ff8a65',
  usecase: '#6c8aff',
  component: '#81c784',
  event: '#ffb74d',
  invariant: '#ce93d8',
  protocol: '#4fc3f7',
};

interface SimNode extends GraphNode, d3.SimulationNodeDatum {}
interface SimLink extends d3.SimulationLinkDatum<SimNode> { edge_type: string }

export function GraphPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getGraph().then(setData).catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!data || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const nodes: SimNode[] = data.nodes.map(n => ({ ...n }));
    const links: SimLink[] = data.links.map(l => ({
      source: l.source,
      target: l.target,
      edge_type: l.edge_type,
    }));

    const g = svg.append('g');

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(25));

    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#2a2e42')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6);

    const node = g.append('g')
      .selectAll<SVGCircleElement, SimNode>('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => d.kind === 'usecase' ? 8 : 6)
      .attr('fill', d => KIND_COLORS[d.kind] || '#888')
      .attr('stroke', 'var(--bg-primary)')
      .attr('stroke-width', 2)
      .attr('cursor', 'pointer')
      .call(d3.drag<SVGCircleElement, SimNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    const label = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text(d => d.name)
      .attr('dx', 12)
      .attr('dy', 4)
      .attr('font-size', 10)
      .attr('fill', '#8b90a8');

    const tooltip = tooltipRef.current;

    node.on('mouseover', (event, d) => {
      if (!tooltip) return;
      tooltip.style.display = 'block';
      tooltip.style.left = `${event.clientX + 12}px`;
      tooltip.style.top = `${event.clientY - 10}px`;
      tooltip.innerHTML = `<div class="tt-kind">${d.kind}</div><div class="tt-name">${d.name}</div>`;

      link
        .attr('stroke', l => {
          const s = typeof l.source === 'object' ? (l.source as SimNode).id : l.source;
          const t = typeof l.target === 'object' ? (l.target as SimNode).id : l.target;
          return s === d.id || t === d.id ? KIND_COLORS[d.kind] || '#6c8aff' : '#2a2e42';
        })
        .attr('stroke-width', l => {
          const s = typeof l.source === 'object' ? (l.source as SimNode).id : l.source;
          const t = typeof l.target === 'object' ? (l.target as SimNode).id : l.target;
          return s === d.id || t === d.id ? 2.5 : 1.5;
        });
    });

    node.on('mouseout', () => {
      if (tooltip) tooltip.style.display = 'none';
      link.attr('stroke', '#2a2e42').attr('stroke-width', 1.5);
    });

    node.on('click', (_event, d) => {
      navigate(`/specs/${d.kind}/${d.name}`);
    });

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x!)
        .attr('y1', d => (d.source as SimNode).y!)
        .attr('x2', d => (d.target as SimNode).x!)
        .attr('y2', d => (d.target as SimNode).y!);
      node.attr('cx', d => d.x!).attr('cy', d => d.y!);
      label.attr('x', d => d.x!).attr('y', d => d.y!);
    });

    return () => { simulation.stop(); };
  }, [data, navigate]);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="loading">Loading graph...</div>;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Dependency Graph</h1>
        <p className="page-subtitle">{data.node_count} nodes, {data.edge_count} edges</p>
      </div>
      <div className="stats-row">
        {Object.entries(KIND_COLORS).map(([k, c]) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: c, display: 'inline-block' }} />
            <span style={{ fontSize: 11, color: '#8b90a8', textTransform: 'uppercase', letterSpacing: 1 }}>{k}</span>
          </div>
        ))}
      </div>
      <div className="graph-container">
        <svg ref={svgRef} />
        <div ref={tooltipRef} className="graph-tooltip" style={{ display: 'none' }} />
      </div>
    </div>
  );
}
