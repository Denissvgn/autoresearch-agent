// History — summary cards, filter row, past sessions table, promotions table.
// Wired to existing hooks; design ported from hifi/screen-history.jsx.
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usePromotions, useSessions, useSessionsPage } from '../hooks/useResearch';
import { Icon, Stat, StatusBadge } from '../components/hifi/primitives';

export default function History() {
  const navigate = useNavigate();
  const { data: sessions } = useSessions();
  const { data: page } = useSessionsPage(100, 0);
  const { data: promotions } = usePromotions();

  const [search, setSearch] = useState('');
  const [instrument, setInstrument] = useState('');
  const [model, setModel] = useState('');
  const [status, setStatus] = useState('');

  const all = page?.items ?? sessions ?? [];
  const finished = all.filter((s) => s.status !== 'running' && s.status !== 'paused');
  const total = finished.length;
  const promotedCount = finished.filter((s) => s.status === 'completed').length;
  const promoRate = total ? Math.round((promotedCount / total) * 100) : 0;
  const avgBest = (() => {
    const vals = finished.map((s) => s.best_metric).filter((v): v is number => typeof v === 'number');
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  })();
  const spend = finished.reduce((a, s) => a + (s.total_api_cost_usd ?? 0), 0);

  const instruments = useMemo(() => Array.from(new Set(all.map((s) => s.instrument))).sort(), [all]);
  const models = useMemo(() => Array.from(new Set(all.map((s) => s.model_type))).sort(), [all]);
  const statuses = useMemo(() => Array.from(new Set(all.map((s) => s.status))).sort(), [all]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return finished.filter((s) => {
      if (q && !`${s.instrument} ${s.model_type} ${s.tag || ''} ${s.id}`.toLowerCase().includes(q)) return false;
      if (instrument && s.instrument !== instrument) return false;
      if (model && s.model_type !== model) return false;
      if (status && s.status !== status) return false;
      return true;
    });
  }, [finished, search, instrument, model, status]);

  return (
    <div className="col gap-5" style={{ padding: 24 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <div className="col gap-1 grow">
          <span className="label">archive</span>
          <h1 className="h1">History</h1>
        </div>
        <div className="row gap-2">
          <button className="btn btn--ghost">
            <Icon name="dl" /> Export csv
          </button>
          <button className="btn btn--solid" onClick={() => navigate('/research/new')}>
            <Icon name="plus" /> New research
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <div className="card" style={{ padding: 18 }}>
          <Stat label="total sessions" valueSize="lg" value={total} />
        </div>
        <div className="card" style={{ padding: 18 }}>
          <Stat label="promotion rate" valueSize="lg" value={`${promoRate}%`} sub={`${promotedCount}/${total}`} />
          <div className={`progress ${promoRate >= 50 ? 'progress--green' : promoRate >= 25 ? 'progress--amber' : 'progress--red'}`} style={{ marginTop: 10 }}>
            <div style={{ width: `${promoRate}%` }} />
          </div>
        </div>
        <div className="card" style={{ padding: 18 }}>
          <Stat label="avg best metric" valueSize="lg" value={avgBest != null ? avgBest.toFixed(4) : '—'} />
        </div>
        <div className="card" style={{ padding: 18 }}>
          <Stat label="cumulative spend" valueSize="lg" value={`$${spend.toFixed(2)}`} />
        </div>
      </div>

      {/* Filter card */}
      <div className="card" style={{ padding: 14, display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 12 }}>
        <div
          className="row gap-2"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            borderRadius: 'var(--r-2)',
            padding: '0 10px',
            height: 32,
          }}
        >
          <Icon name="search" size={14} color="var(--muted)" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="search subject, tag, id…"
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--fg)', fontSize: 12, fontFamily: "'IBM Plex Mono', monospace" }}
          />
        </div>
        <select className="select mono" value={instrument} onChange={(e) => setInstrument(e.target.value)}>
          <option value="">all subjects</option>
          {instruments.map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
        <select className="select mono" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">all models</option>
          {models.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select className="select mono" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">all statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Past sessions */}
      <section className="col gap-3">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2 className="h2">Past sessions</h2>
          <span className="subtle">{filtered.length} matching</span>
        </div>
        <div className="card">
          <div className="scroll" style={{ maxHeight: 480 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Session</th>
                  <th>Subject</th>
                  <th>Model</th>
                  <th className="num">Iters</th>
                  <th className="num">Best</th>
                  <th className="num">Cost</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => {
                  const dur = s.completed_at
                    ? Math.round((new Date(s.completed_at).getTime() - new Date(s.started_at).getTime()) / 60000)
                    : null;
                  return (
                    <tr key={s.id} onClick={() => navigate(`/research/${s.id}`)}>
                      <td className="subtle" style={{ fontSize: 11 }}>
                        {new Date(s.started_at).toLocaleString()} {dur != null && <span className="faint">· {dur}m</span>}
                      </td>
                      <td className="mono subtle">#{s.id.slice(0, 8)}</td>
                      <td className="mono">{s.instrument} <span className="faint">· {s.timeframe}</span></td>
                      <td><span className="pill pill--ghost">{s.model_type}</span></td>
                      <td className="num">{s.best_iteration ?? 0}/{s.max_iterations}</td>
                      <td className="num">{s.best_metric != null ? s.best_metric.toFixed(4) : '—'}</td>
                      <td className="num">${(s.total_api_cost_usd ?? 0).toFixed(2)}</td>
                      <td><StatusBadge s={s.status} /></td>
                      <td style={{ textAlign: 'right' }}><Icon name="chevR" size={14} color="var(--faint)" /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Promotions */}
      <section className="col gap-3">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2 className="h2">Config promotions</h2>
          <span className="subtle">{promotions?.length ?? 0} total</span>
        </div>
        <div className="card">
          {!promotions || promotions.length === 0 ? (
            <div className="placeholder" style={{ height: 100, margin: 14 }}>no promotions yet</div>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Research</th>
                  <th className="num">Iter</th>
                  <th>Scope</th>
                  <th>Target</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {promotions.map((p) => (
                  <tr key={p.id}>
                    <td className="subtle" style={{ fontSize: 11 }}>{new Date(p.promoted_at).toLocaleString()}</td>
                    <td>
                      <Link className="lnk mono" to={`/research/${p.research_id}`}>
                        #{p.research_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="num">#{p.iteration}</td>
                    <td>
                      <span className={`pill ${p.scope === 'production' ? 'pill--red' : p.scope === 'canary' ? 'pill--amber' : p.scope === 'paper' ? 'pill--info' : 'pill--green'}`}>
                        <span className="dot" />
                        {p.scope ?? 'development'}
                      </span>
                    </td>
                    <td className="mono subtle" style={{ fontSize: 11 }}>{p.target_path}</td>
                    <td>
                      {p.rolled_back_at ? (
                        <span className="pill pill--red">
                          <span className="dot" /> rolled back
                        </span>
                      ) : (
                        <span className="pill pill--green">
                          <span className="dot" /> active
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
