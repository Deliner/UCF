import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type SpecSummary, type SpecCatalog } from '../api/client';

const KINDS = ['all', 'action', 'usecase', 'component', 'event', 'invariant', 'protocol'];

export function CatalogPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<SpecCatalog | null>(null);
  const [kind, setKind] = useState('all');
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const k = kind === 'all' ? undefined : kind;
    api.listSpecs(k, search || undefined)
      .then(setData)
      .catch(e => setError(e.message));
  }, [kind, search]);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="loading">Loading specs...</div>;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Spec Catalog</h1>
        <p className="page-subtitle">{data.total_count} specs across {Object.keys(data.kind_counts).length} kinds</p>
      </div>

      <div className="stats-row">
        {Object.entries(data.kind_counts).map(([k, v]) => (
          <div key={k} className="stat-card">
            <div className="stat-value">{v}</div>
            <div className="stat-label">{k}s</div>
          </div>
        ))}
      </div>

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Search specs..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="kind-tabs">
          {KINDS.map(k => (
            <button
              key={k}
              className={`kind-tab ${kind === k ? 'active' : ''}`}
              onClick={() => setKind(k)}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      {data.specs.length === 0 ? (
        <div className="empty">No specs match the current filter.</div>
      ) : (
        <table className="spec-table">
          <thead>
            <tr>
              <th>Kind</th>
              <th>Name</th>
              <th>Version</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {data.specs.map((s: SpecSummary) => (
              <tr key={`${s.kind}/${s.name}`} onClick={() => navigate(`/specs/${s.kind}/${s.name}`)}>
                <td><span className="kind-badge" data-kind={s.kind}>{s.kind}</span></td>
                <td className="spec-name">{s.name}</td>
                <td className="spec-version">{s.version || '—'}</td>
                <td>
                  <div className="spec-tags">
                    {s.tags.map(t => <span key={t} className="spec-tag">{t}</span>)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
