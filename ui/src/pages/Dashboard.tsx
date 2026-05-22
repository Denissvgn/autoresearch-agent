// Dashboard — 5-stat strip, active sessions card grid, recent sessions table.
// Wired to existing hooks/api; design ported from hifi/screen-dashboard.jsx.
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSessions, useSessionsPage, useStatus } from '../hooks/useResearch';
import { Icon, Sparkline, Stat, StatusBadge } from '../components/hifi/primitives';
import { ResearchSession } from '../api/client';

function fmtMoney(v: number | undefined | null) {
  if (v == null) return '—';
  return `$${v.toFixed(2)}`;
}

function fmtElapsed(startedAt: string, completedAt?: string | null) {
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const sec = Math.max(0, Math.round((end - start) / 1000));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

function fmtRelative(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function isActiveStatus(s: string) {
  return s === 'running' || s === 'paused';
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: sessions, isLoading, refetch } = useSessions();
  const { data: recentPage } = useSessionsPage(50, 0);
  const { data: status } = useStatus();
  const [searchTerm, setSearchTerm] = useState('');

  const active = useMemo(
    () => (sessions ?? []).filter((s) => isActiveStatus(s.status)),
    [sessions],
  );
  const allRecent = recentPage?.items ?? sessions ?? [];

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayMs = today.getTime();
  const todaySpend = (sessions ?? [])
    .filter((s) => new Date(s.started_at).getTime() >= todayMs)
    .reduce((acc, s) => acc + (s.total_api_cost_usd ?? 0), 0);
  const promotedToday = (sessions ?? []).filter(
    (s) => s.status === 'completed' && s.completed_at && new Date(s.completed_at).getTime() >= todayMs,
  ).length;
  const queueDepth = (status?.active_sessions ?? active.length) - active.length;

  const filteredRecent = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return allRecent;
    return allRecent.filter(
      (s) =>
        s.instrument.toLowerCase().includes(q) ||
        s.model_type.toLowerCase().includes(q) ||
        (s.tag || '').toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q),
    );
  }, [allRecent, searchTerm]);

  return (
    <div className="col gap-5" style={{ padding: 24 }}>
      {/* Page header */}
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <div className="col gap-1 grow">
          <span className="label">overview</span>
          <h1 className="h1">Dashboard</h1>
        </div>
        <div className="row gap-2">
          <button className="btn btn--ghost" onClick={() => refetch()} title="Refresh">
            <Icon name="refresh" />
            Refresh
          </button>
          <button className="btn btn--solid" onClick={() => navigate('/research/new')}>
            <Icon name="plus" />
            New research
          </button>
        </div>
      </div>

      {/* 5-stat status strip + right column */}
      <div className="row gap-4" style={{ alignItems: 'stretch' }}>
        <div
          className="card grow"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', padding: 20, gap: 0 }}
        >
          <Stat
            label="Active runs"
            valueSize="lg"
            value={active.length}
            sub={`of ${status?.max_concurrent ?? '—'} max concurrent`}
          />
          <div className="divider-v" style={{ margin: '0 16px' }} />
          <Stat
            label="Today's spend"
            valueSize="lg"
            value={fmtMoney(todaySpend)}
            sub="across today's sessions"
          />
          <div className="divider-v" style={{ margin: '0 16px' }} />
          <Stat
            label="Queue"
            valueSize="lg"
            value={queueDepth > 0 ? queueDepth : 0}
            sub="pending starts"
          />
          <div className="divider-v" style={{ margin: '0 16px' }} />
          <Stat
            label="Promoted today"
            valueSize="lg"
            value={promotedToday}
            sub="ready for review"
          />
          <div className="divider-v" style={{ margin: '0 16px' }} />
          <Stat
            label="Total sessions"
            valueSize="lg"
            value={(sessions ?? []).length}
            sub="all-time"
          />
        </div>
        <div className="card" style={{ width: 240, padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span className="label">system</span>
          <div className="row gap-2">
            <span className="pill pill--green">
              <span className="dot" />
              api ok
            </span>
            <span className="pill pill--ghost mono">v0.4.1</span>
          </div>
          <div className="row gap-2">
            <span className="pill pill--info">
              <span className="dot" />
              mlflow ok
            </span>
          </div>
          <div className="subtle" style={{ fontSize: 11, lineHeight: 1.5 }}>
            {status
              ? `${status.active_sessions} active · ${status.max_concurrent} max concurrent`
              : 'connecting…'}
          </div>
        </div>
      </div>

      {/* Active sessions */}
      <section className="col gap-3">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div className="col gap-1">
            <span className="label">live</span>
            <h2 className="h2">Active sessions</h2>
          </div>
          <span className="subtle">{active.length} running</span>
        </div>
        {isLoading ? (
          <div className="card placeholder" style={{ height: 140 }}>
            loading…
          </div>
        ) : active.length === 0 ? (
          <div className="card placeholder" style={{ height: 140 }}>
            no active sessions
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
              gap: 16,
            }}
          >
            {active.map((s) => (
              <ActiveSessionCard key={s.id} session={s} />
            ))}
          </div>
        )}
      </section>

      {/* Recent sessions */}
      <section className="col gap-3">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div className="col gap-1">
            <span className="label">archive</span>
            <h2 className="h2">Recent sessions</h2>
          </div>
          <div className="row gap-2">
            <div
              className="row gap-2"
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--line)',
                borderRadius: 'var(--r-2)',
                padding: '0 10px',
                height: 32,
                width: 260,
              }}
            >
              <Icon name="search" size={14} color="var(--muted)" />
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="search instrument, tag, id…"
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--fg)',
                  fontSize: 12,
                  fontFamily: "'IBM Plex Mono', monospace",
                }}
              />
            </div>
            <button className="btn btn--ghost" onClick={() => navigate('/history')}>
              <Icon name="arrR" />
              View all
            </button>
          </div>
        </div>
        <div className="card">
          <div className="scroll" style={{ maxHeight: 480 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Instrument</th>
                  <th>Model</th>
                  <th className="num">Iters</th>
                  <th className="num">Best metric</th>
                  <th className="num">Cost</th>
                  <th>Status</th>
                  <th>When</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredRecent.slice(0, 25).map((s) => (
                  <tr key={s.id} onClick={() => navigate(`/research/${s.id}`)}>
                    <td className="mono" style={{ color: 'var(--muted)' }}>
                      #{s.id.slice(0, 8)}
                    </td>
                    <td>
                      <span className="mono">{s.instrument}</span>{' '}
                      <span className="faint mono">· {s.timeframe}</span>
                    </td>
                    <td>
                      <span className="pill pill--ghost">{s.model_type}</span>
                    </td>
                    <td className="num">
                      {s.best_iteration ?? 0}/{s.max_iterations}
                    </td>
                    <td className="num">
                      {s.best_metric != null ? s.best_metric.toFixed(4) : '—'}
                    </td>
                    <td className="num">{fmtMoney(s.total_api_cost_usd)}</td>
                    <td>
                      <StatusBadge s={s.status} />
                    </td>
                    <td className="subtle">{fmtRelative(s.started_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <Icon name="chevR" size={14} color="var(--faint)" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}

function ActiveSessionCard({ session }: { session: ResearchSession }) {
  const navigate = useNavigate();
  const progress = Math.min(
    100,
    Math.round(((session.best_iteration ?? 0) / Math.max(1, session.max_iterations)) * 100),
  );
  // Trend placeholder — full series unavailable on this list endpoint; show a
  // gentle climb to the current best so the card has a visual cue.
  const series = session.best_metric != null
    ? [session.best_metric * 0.92, session.best_metric * 0.97, session.best_metric]
    : [0, 0, 0];

  return (
    <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="col gap-1">
          <Link to={`/research/${session.id}`} className="lnk mono" style={{ fontSize: 14 }}>
            {session.instrument} · {session.timeframe}
          </Link>
          <div className="row gap-2" style={{ fontSize: 11 }}>
            <span className="pill pill--ghost">{session.model_type}</span>
            <StatusBadge s={session.status} />
          </div>
        </div>
        <div className="avatar" title={session.id.slice(0, 8)}>
          {session.instrument.slice(0, 2).toUpperCase()}
        </div>
      </div>
      <div style={{ height: 32 }}>
        <Sparkline data={series} color="var(--fg-2)" fill />
      </div>
      <div className="row gap-4">
        <Stat
          label="iter"
          valueSize="sm"
          value={`${session.best_iteration ?? 0}/${session.max_iterations}`}
        />
        <Stat
          label="best"
          valueSize="sm"
          value={session.best_metric != null ? session.best_metric.toFixed(3) : '—'}
        />
        <Stat label="cost" valueSize="sm" value={fmtMoney(session.total_api_cost_usd)} />
      </div>
      <div className="progress progress--info">
        <div style={{ width: `${progress}%` }} />
      </div>
      <div className="row" style={{ justifyContent: 'space-between', fontSize: 11 }}>
        <span className="subtle">
          {session.current_phase || 'pending'} · {fmtElapsed(session.started_at)}
        </span>
        <div className="row gap-2">
          <button className="btn btn--ghost btn--sm" onClick={() => navigate(`/research/${session.id}`)}>
            <Icon name="arrR" size={12} />
            Open
          </button>
        </div>
      </div>
    </div>
  );
}
