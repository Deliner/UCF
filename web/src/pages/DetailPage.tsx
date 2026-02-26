import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api, type SpecDetail, type SpecRelationships } from '../api/client';

type Tab = 'overview' | 'yaml' | 'relationships';

export function DetailPage() {
  const { kind, name } = useParams<{ kind: string; name: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<SpecDetail | null>(null);
  const [rels, setRels] = useState<SpecRelationships | null>(null);
  const [tab, setTab] = useState<Tab>('overview');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!kind || !name) return;
    Promise.all([
      api.getSpecDetail(kind, name),
      api.getSpecRelationships(kind, name),
    ])
      .then(([d, r]) => { setDetail(d); setRels(r); })
      .catch(e => setError(e.message));
  }, [kind, name]);

  if (error) return <div className="error">{error}</div>;
  if (!detail) return <div className="loading">Loading spec...</div>;

  return (
    <div>
      <div className="detail-header">
        <Link to="/" className="back-link">← Catalog</Link>
        <span className="kind-badge" data-kind={detail.kind}>{detail.kind}</span>
        <h1 className="page-title" style={{ marginBottom: 0 }}>{detail.name}</h1>
        <span className={`impl-badge ${detail.impl_status}`}>{detail.impl_status}</span>
      </div>

      <div className="detail-tabs">
        {(['overview', 'yaml', 'relationships'] as Tab[]).map(t => (
          <button
            key={t}
            className={`detail-tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="detail-section">
          <h3>Metadata</h3>
          <table className="spec-table" style={{ maxWidth: 500 }}>
            <tbody>
              <tr><td style={{ color: 'var(--text-muted)', width: 120 }}>Kind</td><td>{detail.kind}</td></tr>
              <tr><td style={{ color: 'var(--text-muted)' }}>Version</td><td>{detail.version || '—'}</td></tr>
              <tr><td style={{ color: 'var(--text-muted)' }}>Owner</td><td>{detail.owner || '—'}</td></tr>
              <tr><td style={{ color: 'var(--text-muted)' }}>Status</td><td><span className={`impl-badge ${detail.impl_status}`}>{detail.impl_status}</span></td></tr>
              {detail.tags.length > 0 && (
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Tags</td>
                  <td><div className="spec-tags">{detail.tags.map(t => <span key={t} className="spec-tag">{t}</span>)}</div></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'yaml' && (
        <div className="detail-section">
          <h3>YAML Source</h3>
          <pre className="yaml-block">{detail.raw_yaml}</pre>
        </div>
      )}

      {tab === 'relationships' && rels && (
        <div className="detail-section">
          <h3>Upstream ({rels.upstream.length})</h3>
          {rels.upstream.length === 0 ? (
            <p className="empty" style={{ padding: '12px 0' }}>No upstream dependencies</p>
          ) : (
            <div className="rels-list">
              {rels.upstream.map(r => (
                <a key={r.ref} className="rel-item" onClick={() => navigate(`/specs/${r.kind}/${r.name}`)} style={{ cursor: 'pointer' }}>
                  <span className="rel-direction">→</span>
                  <span className="kind-badge" data-kind={r.kind}>{r.kind}</span>
                  <span className="spec-name">{r.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 'auto' }}>{r.edge_type}</span>
                </a>
              ))}
            </div>
          )}

          <h3 style={{ marginTop: 24 }}>Downstream ({rels.downstream.length})</h3>
          {rels.downstream.length === 0 ? (
            <p className="empty" style={{ padding: '12px 0' }}>No downstream dependents</p>
          ) : (
            <div className="rels-list">
              {rels.downstream.map(r => (
                <a key={r.ref} className="rel-item" onClick={() => navigate(`/specs/${r.kind}/${r.name}`)} style={{ cursor: 'pointer' }}>
                  <span className="rel-direction">←</span>
                  <span className="kind-badge" data-kind={r.kind}>{r.kind}</span>
                  <span className="spec-name">{r.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 'auto' }}>{r.edge_type}</span>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
