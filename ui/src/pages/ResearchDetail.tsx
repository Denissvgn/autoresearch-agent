// Session detail — header, stat strip, tab navigation, panels for state /
// metrics / iterations / agent log. Wired to existing hooks; design ported
// from hifi/screen-session.jsx.
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  useAgentLog,
  useIterations,
  usePauseSession,
  useResearchState,
  useResumeSession,
  useSession,
  useStopSession,
} from '../hooks/useResearch';
import { api, AgentLogEntry, Iteration, ResearchState } from '../api/client';
import {
  Icon,
  MetricChart,
  MetricPoint,
  PhaseBar,
  Stat,
  StatusBadge,
} from '../components/hifi/primitives';

type Tab = 'state' | 'metrics' | 'iterations' | 'log';

function fmtElapsed(startIso?: string | null, endIso?: string | null) {
  if (!startIso) return '—';
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const sec = Math.max(0, Math.round((end - start) / 1000));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: session, isLoading } = useSession(id!);
  const { data: iterations } = useIterations(id!);
  const { data: state } = useResearchState(id!);
  const isActive = session?.status === 'running' || session?.status === 'paused';
  const { data: agentLog } = useAgentLog(id!, isActive);
  const pauseMut = usePauseSession();
  const resumeMut = useResumeSession();
  const stopMut = useStopSession();

  // Default tab is metrics for active sessions, state otherwise.
  const initialTab: Tab = isActive ? 'metrics' : 'state';
  const [tab, setTab] = useState<Tab>(initialTab);

  if (isLoading || !session) {
    return (
      <div className="placeholder" style={{ margin: 24, height: 200 }}>
        loading…
      </div>
    );
  }

  const phaseLabel = session.current_phase || state?.current_phase || 'pending';
  const canPromote = !!session.best_iteration && !isActive;
  const iterationCount = iterations?.length ?? 0;

  return (
    <div className="col gap-5" style={{ padding: 24 }}>
      {/* Header */}
      <div className="col gap-2">
        <div className="crumb">
          <Link to="/">Dashboard</Link>
          <Icon name="chevR" size={12} />
          <span>Session</span>
          <Icon name="chevR" size={12} />
          <span className="mono">#{session.id.slice(0, 8)}</span>
        </div>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div className="col gap-2">
            <div className="row gap-3" style={{ alignItems: 'center' }}>
              <h1 className="mono" style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em' }}>
                {session.instrument}
              </h1>
              <span className="pill pill--ghost mono">{session.timeframe}</span>
              <span className="pill pill--ghost">{session.model_type}</span>
              <StatusBadge s={session.status} />
              {phaseLabel !== 'pending' && (
                <span className="pill pill--info">
                  <span className="dot" />
                  {phaseLabel}
                </span>
              )}
            </div>
            {session.tag && (
              <span className="faint mono" style={{ fontSize: 12 }}>
                #{session.tag}
              </span>
            )}
            {session.resumed_from && (
              <span className="subtle" style={{ fontSize: 11 }}>
                ← resumed from{' '}
                <Link className="lnk mono" to={`/research/${session.resumed_from}`}>
                  {session.resumed_from.slice(0, 12)}
                </Link>
              </span>
            )}
          </div>
          <div className="row gap-2">
            {session.status === 'running' && (
              <>
                <button className="btn" onClick={() => pauseMut.mutate(id!)}>
                  <Icon name="pause" />
                  Pause
                </button>
                <button className="btn btn--danger" onClick={() => stopMut.mutate(id!)}>
                  <Icon name="stop" />
                  Stop
                </button>
              </>
            )}
            {session.status === 'paused' && (
              <>
                <button className="btn" onClick={() => resumeMut.mutate(id!)}>
                  <Icon name="play" />
                  Resume
                </button>
                <button className="btn btn--danger" onClick={() => stopMut.mutate(id!)}>
                  <Icon name="stop" />
                  Stop
                </button>
              </>
            )}
            <button className="btn btn--ghost" onClick={() => api.downloadResults(id!)}>
              <Icon name="dl" />
              Export
            </button>
            {canPromote && (
              <button className="btn btn--solid" onClick={() => navigate(`/research/${id}/promote`)}>
                <Icon name="arrU" />
                Promote config
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Stat strip */}
      <div
        className="card"
        style={{ padding: 18, display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 0 }}
      >
        <Stat
          label="iteration"
          valueSize="lg"
          value={`${iterationCount}/${session.max_iterations}`}
        />
        <div className="divider-v" style={{ margin: '0 16px' }} />
        <Stat
          label="best metric"
          valueSize="lg"
          value={session.best_metric != null ? session.best_metric.toFixed(4) : '—'}
        />
        <div className="divider-v" style={{ margin: '0 16px' }} />
        <Stat
          label="best iter"
          valueSize="lg"
          value={session.best_iteration != null ? `#${session.best_iteration}` : '—'}
        />
        <div className="divider-v" style={{ margin: '0 16px' }} />
        <Stat
          label="cost"
          valueSize="lg"
          value={`$${(session.total_api_cost_usd ?? 0).toFixed(2)}`}
          sub={`/ $${session.max_budget_usd.toFixed(2)} cap`}
        />
        <div className="divider-v" style={{ margin: '0 16px' }} />
        <Stat
          label="elapsed"
          valueSize="lg"
          value={fmtElapsed(session.started_at, session.completed_at)}
        />
        <div className="divider-v" style={{ margin: '0 16px' }} />
        <Stat label="mode" valueSize="lg" value={session.quick_mode ? 'quick' : 'standard'} />
      </div>

      {session.error_message && (
        <div className="banner banner--red">
          <Icon name="info" />
          <div className="col gap-1">
            <span style={{ fontWeight: 600 }}>{session.error_message}</span>
            {session.promotion_blockers && session.promotion_blockers.length > 0 && (
              <span className="mono" style={{ fontSize: 11, opacity: 0.85 }}>
                {session.promotion_blockers.join(' · ')}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        <div className={`tab ${tab === 'state' ? 'on' : ''}`} onClick={() => setTab('state')}>
          <Icon name="flask" /> State
        </div>
        <div className={`tab ${tab === 'metrics' ? 'on' : ''}`} onClick={() => setTab('metrics')}>
          <Icon name="spark" /> Metrics
        </div>
        <div className={`tab ${tab === 'iterations' ? 'on' : ''}`} onClick={() => setTab('iterations')}>
          <Icon name="grid" /> Iterations
          <span className="count">· {iterationCount}</span>
        </div>
        <div className={`tab ${tab === 'log' ? 'on' : ''}`} onClick={() => setTab('log')}>
          <Icon name="bolt" /> Agent log
        </div>
      </div>

      {tab === 'state' && <StateTab state={state ?? null} session={session.model_type} />}
      {tab === 'metrics' && <MetricsTab iterations={iterations ?? []} />}
      {tab === 'iterations' && <IterationsTab iterations={iterations ?? []} bestIteration={session.best_iteration} researchId={id!} />}
      {tab === 'log' && <AgentLogTab entries={agentLog?.entries ?? []} researchId={id!} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
function StateTab({ state, session: modelType }: { state: ResearchState | null; session: string }) {
  if (!state) {
    return <div className="placeholder" style={{ height: 240 }}>research state pending…</div>;
  }
  const phases = state.phase_state.phases.map((p) => p.label);
  const activeIdx = state.phase_state.phases.findIndex((p) => p.status === 'active');
  const safeActive = activeIdx < 0 ? state.phase_state.phases.filter((p) => p.status === 'done').length : activeIdx;

  const budget = state.budget_usage;
  const budgetPct = Math.min(100, Math.round((budget.api_cost_usd / Math.max(budget.max_budget_usd, 0.0001)) * 100));

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
      <div className="col gap-4">
        <div className="card" style={{ padding: 18 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 className="h2">{state.current_phase || 'idle'}</h2>
            <span className="pill pill--info mono">{state.status}</span>
          </div>
          {state.next_action && (
            <div className="code" style={{ marginTop: 12 }}>
              <span className="key">next_action</span> = <span className="str">{state.next_action}</span>
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <PhaseBar phases={phases} active={safeActive} />
          </div>
        </div>

        <div className="card">
          <div className="card__head">
            <div className="card__title">Top candidates</div>
            <span className="card__sub">{state.top_candidates.length}</span>
          </div>
          {state.top_candidates.length === 0 ? (
            <div className="placeholder" style={{ margin: 14, height: 96 }}>no candidates yet</div>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Iter</th>
                  <th className="num">Metric</th>
                  <th>Gates</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {state.top_candidates.slice(0, 6).map((c, i) => {
                  const it = c as Record<string, unknown>;
                  const iter = it.iteration ?? it.i ?? i;
                  const metric = (it.primary_metric ?? it.metric) as number | undefined;
                  const passed = Boolean(it.all_gates_passed);
                  const decision = String(it.decision ?? '—');
                  return (
                    <tr key={i}>
                      <td className="mono">#{String(iter)}</td>
                      <td className="num">{metric != null ? metric.toFixed(4) : '—'}</td>
                      <td>
                        <span className={`pill ${passed ? 'pill--green' : 'pill--red'}`}>
                          <span className="dot" /> {passed ? 'pass' : 'fail'}
                        </span>
                      </td>
                      <td className="mono subtle">{decision}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {state.failed_pruned_configs.length > 0 && (
          <div className="card" style={{ padding: 14 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="label">pruned</span>
              <span className="subtle">{state.failed_pruned_configs.length} configs</span>
            </div>
            <div className="code" style={{ marginTop: 8, maxHeight: 160 }}>
              {state.failed_pruned_configs.slice(0, 12).map((c, i) => (
                <div key={i}>
                  <span className="dim">#{String((c as any).iteration ?? i)}</span>{' '}
                  <span className="warn">
                    {String((c as any).reason ?? (c as any).decision ?? 'pruned')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="col gap-4">
        <div className="card" style={{ padding: 16 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="label">budget</span>
            <span className="mono subtle">{budgetPct}%</span>
          </div>
          <div className="stat__value stat__value--sm" style={{ marginTop: 6 }}>
            ${budget.api_cost_usd.toFixed(2)}{' '}
            <span className="subtle" style={{ fontSize: 11 }}>
              / ${budget.max_budget_usd.toFixed(2)}
            </span>
          </div>
          <div className={`progress ${budgetPct > 80 ? 'progress--red' : budgetPct > 60 ? 'progress--amber' : 'progress--info'}`} style={{ marginTop: 10 }}>
            <div style={{ width: `${budgetPct}%` }} />
          </div>
          <div className="subtle" style={{ fontSize: 11, marginTop: 8 }}>
            {budget.iterations_used}/{budget.max_iterations} iterations
          </div>
        </div>

        <div className="card" style={{ padding: 16 }}>
          <span className="label">rollback target</span>
          <div className="mono" style={{ marginTop: 6, wordBreak: 'break-all' }}>
            {state.rollback_target ?? '—'}
          </div>
          {state.smoke_status && (
            <div className="row gap-2" style={{ marginTop: 10 }}>
              <span className="pill pill--info">smoke</span>
              <span className="mono subtle">
                {(state.smoke_status as any).status ?? 'pending'}
              </span>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card__head">
            <div className="card__title">HPO studies</div>
            <span className="card__sub">{state.hpo_studies.length}</span>
          </div>
          {state.hpo_studies.length === 0 ? (
            <div className="placeholder" style={{ margin: 14, height: 60 }}>no studies yet</div>
          ) : (
            <div className="col gap-1" style={{ padding: 12 }}>
              {state.hpo_studies.slice(0, 6).map((s) => (
                <div key={s.id} className="row" style={{ justifyContent: 'space-between', fontSize: 12 }}>
                  <span className="mono subtle">{s.study_id || `#${s.id}`}</span>
                  <span className="mono">{s.completed_trials}/{s.n_trials}</span>
                  <span className="mono">{s.best_composite != null ? s.best_composite.toFixed(3) : '—'}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ padding: 16 }}>
          <span className="label">model</span>
          <div className="col gap-1" style={{ marginTop: 6, fontSize: 12 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="subtle">type</span>
              <span className="mono">{modelType}</span>
            </div>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="subtle">schema</span>
              <span className="mono">{state.schema_version}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
function MetricsTab({ iterations }: { iterations: Iteration[] }) {
  const points: MetricPoint[] = useMemo(
    () =>
      iterations
        .filter((it) => it.primary_metric != null)
        .map((it) => ({ i: it.iteration, v: it.primary_metric as number, gates: !!it.all_gates_passed })),
    [iterations],
  );
  const passCount = iterations.filter((it) => it.all_gates_passed).length;
  const passRate = iterations.length ? Math.round((passCount / iterations.length) * 100) : 0;
  const best = points.reduce((a, b) => (a.v > b.v ? a : b), { i: 0, v: -Infinity, gates: false } as MetricPoint);
  const delta = points.length > 1 ? (points[points.length - 1].v - points[0].v) : 0;
  const avgTrain = (() => {
    const vals = iterations.map((it) => it.training_time_s).filter((v): v is number => typeof v === 'number');
    if (!vals.length) return '—';
    return `${(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)}s`;
  })();

  return (
    <div className="col gap-4">
      <div className="card" style={{ padding: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
          <span className="label">primary metric</span>
          {best.v > -Infinity && (
            <span className="mono subtle" style={{ fontSize: 11 }}>
              best #{best.i} · {best.v.toFixed(4)}
            </span>
          )}
        </div>
        <MetricChart points={points} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <div className="card" style={{ padding: 16 }}>
          <Stat
            label="delta vs first"
            value={`${delta >= 0 ? '+' : ''}${delta.toFixed(4)}`}
            deltaDir={delta > 0 ? 'up' : delta < 0 ? 'dn' : 'flat'}
          />
        </div>
        <div className="card" style={{ padding: 16 }}>
          <Stat label="gate pass rate" value={`${passRate}%`} />
          <div className={`progress ${passRate >= 70 ? 'progress--green' : passRate >= 40 ? 'progress--amber' : 'progress--red'}`} style={{ marginTop: 10 }}>
            <div style={{ width: `${passRate}%` }} />
          </div>
        </div>
        <div className="card" style={{ padding: 16 }}>
          <Stat label="avg train time" value={avgTrain} />
        </div>
        <div className="card" style={{ padding: 16 }}>
          <Stat label="iterations" value={iterations.length} sub={`${passCount} passing gates`} />
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
function IterationsTab({
  iterations,
  bestIteration,
  researchId,
}: {
  iterations: Iteration[];
  bestIteration: number | null;
  researchId: string;
}) {
  const [filter, setFilter] = useState('');
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return iterations;
    return iterations.filter(
      (it) =>
        String(it.iteration).includes(q) ||
        (it.decision || '').toLowerCase().includes(q) ||
        (it.mlflow_run_id || '').toLowerCase().includes(q),
    );
  }, [iterations, filter]);

  return (
    <div className="col gap-3">
      <div className="row gap-2">
        <div
          className="row gap-2"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            borderRadius: 'var(--r-2)',
            padding: '0 10px',
            height: 32,
            width: 280,
          }}
        >
          <Icon name="filter" size={14} color="var(--muted)" />
          <input
            className="mono"
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--fg)', fontSize: 12 }}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="filter iterations…"
          />
        </div>
        <div className="grow" />
        <button className="btn btn--ghost" onClick={() => api.downloadResults(researchId)}>
          <Icon name="dl" />
          Export .json
        </button>
      </div>
      <div className="card">
        <div className="scroll" style={{ maxHeight: 560 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Iter</th>
                <th className="num">Metric</th>
                <th>Gates</th>
                <th>Decision</th>
                <th>Phase</th>
                <th className="num">Train</th>
                <th>MLflow</th>
                <th>Snap</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((it) => {
                const isBest = bestIteration != null && it.iteration === bestIteration;
                return (
                  <tr key={it.id} className={isBest ? 'is-selected' : ''}>
                    <td className="mono">
                      #{it.iteration}{isBest && <span className="success-text"> ★</span>}
                    </td>
                    <td className="num">{it.primary_metric != null ? it.primary_metric.toFixed(4) : '—'}</td>
                    <td>
                      <span className={`pill ${it.all_gates_passed ? 'pill--green' : 'pill--red'}`}>
                        <Icon name={it.all_gates_passed ? 'check' : 'x'} size={10} />
                        {it.all_gates_passed ? 'pass' : 'fail'}
                      </span>
                    </td>
                    <td>
                      <span className={`pill ${it.decision === 'keep' ? 'pill--green' : it.decision === 'discard' ? 'pill--red' : 'pill--ghost'}`}>
                        {it.decision || '—'}
                      </span>
                    </td>
                    <td className="mono subtle">{it.search_phase || '—'}</td>
                    <td className="num">{it.training_time_s != null ? `${it.training_time_s.toFixed(1)}s` : '—'}</td>
                    <td>
                      {it.mlflow_url ? (
                        <a href={it.mlflow_url} target="_blank" rel="noreferrer" className="lnk mono">
                          {(it.mlflow_run_id || '').slice(0, 8) || 'open'}
                        </a>
                      ) : (
                        <span className="faint">—</span>
                      )}
                    </td>
                    <td className="mono subtle">{(it.attempt_snapshot_hash || it.artifact_hash || '').slice(0, 8) || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
type LogFilter = 'all' | 'plan' | 'tool' | 'res' | 'warn' | 'err';

const LOG_FILTERS: { id: LogFilter; label: string }[] = [
  { id: 'all', label: 'all' },
  { id: 'plan', label: 'plan' },
  { id: 'tool', label: 'tool' },
  { id: 'res', label: 'result' },
  { id: 'warn', label: 'warn' },
  { id: 'err', label: 'error' },
];

function logClass(type: string): string {
  if (type === 'plan') return 'plan';
  if (type === 'tool' || type === 'tool_call') return 'tool';
  if (type === 'result' || type === 'res' || type === 'observation') return 'res';
  if (type === 'warning' || type === 'warn') return 'warn';
  if (type === 'error' || type === 'err') return 'err';
  return 'sys';
}

function AgentLogTab({ entries, researchId }: { entries: AgentLogEntry[]; researchId: string }) {
  const [filter, setFilter] = useState<LogFilter>('all');
  const filtered = useMemo(() => {
    if (filter === 'all') return entries;
    return entries.filter((e) => logClass(e.type) === filter);
  }, [entries, filter]);
  return (
    <div className="col gap-3">
      <div className="row gap-2">
        <div className="btn-group">
          {LOG_FILTERS.map((f) => (
            <div key={f.id} className={`seg ${filter === f.id ? 'on' : ''}`} onClick={() => setFilter(f.id)}>
              {f.label}
            </div>
          ))}
        </div>
        <span className="grow subtle" style={{ fontSize: 11 }}>
          {filtered.length} of {entries.length} entries
        </span>
        <button
          className="btn btn--ghost"
          onClick={() => navigator.clipboard?.writeText(filtered.map((e) => `[${e.ts}] ${e.type}: ${e.content}`).join('\n'))}
        >
          <Icon name="copy" /> Copy
        </button>
        <button className="btn btn--ghost" onClick={() => api.downloadAgentLog(researchId)}>
          <Icon name="dl" /> .jsonl
        </button>
      </div>
      <div className="card" style={{ padding: 14 }}>
        <pre className="log scroll" style={{ maxHeight: 520, margin: 0 }}>
          {filtered.length === 0 ? (
            <span className="dim">no log entries…</span>
          ) : (
            filtered.map((e, i) => (
              <div key={`${e.ts}-${i}`}>
                <span className="ts">[{(e.ts || '').slice(11, 19)}]</span>{' '}
                <span className={logClass(e.type)}>
                  {e.type}: {e.content}
                </span>
              </div>
            ))
          )}
        </pre>
      </div>
    </div>
  );
}
