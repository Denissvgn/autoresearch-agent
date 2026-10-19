// Session detail — header, stat strip, tab navigation, panels for state /
// metrics / iterations / agent log. Wired to existing hooks; design ported
// from hifi/screen-session.jsx.
import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  useIterations,
  useAgentLog,
  useHarnessContext,
  usePauseSession,
  useResearchState,
  useResumeSession,
  useSession,
  useSkillMetricSchema,
  useStopSession,
} from '../hooks/useResearch';
import { api, Iteration, MetricColumn, ResearchState } from '../api/client';
import HarnessContextPanel from '../components/HarnessContextPanel';
import {
  Icon,
  PhaseBar,
  Stat,
  StatusBadge,
} from '../components/hifi/primitives';
import AgentLog from '../components/AgentLog';
import IterationsTable from '../components/IterationsTable';
import MetricsTrendChart from '../components/MetricsChart';
import { useWebSocket } from '../hooks/useWebSocket';

type Tab = 'state' | 'metrics' | 'iterations' | 'log' | 'harness';

function fmtElapsed(startIso?: string | null, endIso?: string | null, nowMs = Date.now()) {
  if (!startIso) return '—';
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : nowMs;
  const sec = Math.max(0, Math.round((end - start) / 1000));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

function fmtAgo(iso?: string | null, nowMs = Date.now()) {
  if (!iso) return '—';
  const diff = Math.max(0, Math.round((nowMs - new Date(iso).getTime()) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

function timestampMs(iso?: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime();
  return Number.isFinite(ms) ? ms : null;
}

function latestActivity(candidates: Array<{ at?: string | null; source: string }>): { at: string | null; source: string } {
  let latest: { at: string | null; source: string; ms: number } = { at: null, source: 'none', ms: -1 };
  candidates.forEach((candidate) => {
    const ms = timestampMs(candidate.at);
    if (ms !== null && ms > latest.ms) {
      latest = { at: candidate.at ?? null, source: candidate.source, ms };
    }
  });
  return { at: latest.at, source: latest.source };
}

function eventTimestamp(event: Record<string, unknown>): string | null {
  if (typeof event.timestamp === 'string') return event.timestamp;
  const entry = event.entry as Record<string, unknown> | undefined;
  return typeof entry?.ts === 'string' ? entry.ts : null;
}

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: session, isLoading } = useSession(id!);
  const { data: iterations } = useIterations(id!);
  const { data: state } = useResearchState(id!);
  // P3-024: fetch the session's skill metric schema for manifest-driven chart series.
  const skillId = session?.skill_id || null;
  const { data: skillMetricSchema } = useSkillMetricSchema(skillId);
  const isRunning = session?.status === 'running';
  const isActive = session?.status === 'running' || session?.status === 'paused';
  const { data: agentLog } = useAgentLog(id!, isActive);
  const { lastEvent } = useWebSocket();
  const [lastLiveAt, setLastLiveAt] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());
  const pauseMut = usePauseSession();
  const resumeMut = useResumeSession();
  const stopMut = useStopSession();

  useEffect(() => {
    if (!isActive) return;
    const timer = setInterval(() => setNowMs(Date.now()), 15_000);
    return () => clearInterval(timer);
  }, [isActive]);

  useEffect(() => {
    if (!lastEvent || !id) return;
    const activePhaseId = session?.active_phase_session_id;
    const entry = lastEvent.entry as Record<string, unknown> | undefined;
    const entryMeta = entry?.meta as Record<string, unknown> | undefined;
    const matches =
      lastEvent.research_id === id ||
      lastEvent.pipeline_id === id ||
      lastEvent.session_id === id ||
      entry?.research_id === id ||
      entryMeta?.research_id === id ||
      (activePhaseId &&
        (lastEvent.research_id === activePhaseId ||
          lastEvent.session_id === activePhaseId ||
          entry?.research_id === activePhaseId ||
          entryMeta?.research_id === activePhaseId));
    if (matches) {
      const at = eventTimestamp(lastEvent) ?? new Date().toISOString();
      setLastLiveAt((current) =>
        latestActivity([
          { at: current, source: 'websocket/log' },
          { at, source: 'websocket/log' },
        ]).at,
      );
      setNowMs(Date.now());
    }
  }, [lastEvent, id, session?.active_phase_session_id]);

  const [tab, setTab] = useState<Tab>('state');

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
  const sessionEffectiveIterations =
    typeof session.effective_iteration_count === 'number'
      ? session.effective_iteration_count
      : 0;
  const stateIterations = state?.budget_usage.iterations_used ?? 0;
  const effectiveIterations = Math.max(
    sessionEffectiveIterations,
    stateIterations,
    iterationCount,
  );
  const latestIterationAt = latestActivity(
    (iterations ?? []).map((iteration) => ({ at: iteration.created_at, source: 'iteration' })),
  );
  const latestAgentLogAt = latestActivity(
    (agentLog?.entries ?? []).map((entry) => ({ at: entry.ts, source: 'agent log' })),
  );
  const backendActivity = latestActivity([
    { at: state?.phase_state.generated_at, source: 'phase state' },
    latestAgentLogAt,
    latestIterationAt,
    { at: session.completed_at, source: 'session complete' },
    { at: session.started_at, source: 'session start' },
  ]);
  const liveActivity = latestActivity([
    { at: lastLiveAt, source: 'websocket/log' },
    backendActivity,
  ]);

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
          value={`${effectiveIterations}/${session.max_iterations}`}
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
          value={fmtElapsed(session.started_at, session.completed_at, nowMs)}
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
        <div className={`tab ${tab === 'harness' ? 'on' : ''}`} onClick={() => setTab('harness')}>
          <Icon name="bolt" /> Harness
        </div>
      </div>

      {tab === 'state' && (
        <StateTab
          state={state ?? null}
          session={session.model_type}
          lastActivityAt={liveActivity.at}
          lastActivitySource={liveActivity.source}
          nowMs={nowMs}
          isRunning={isRunning}
          isPaused={session.status === 'paused'}
        />
      )}
      {tab === 'metrics' && <MetricsTab iterations={iterations ?? []} modelType={session.model_type} chartSeries={skillMetricSchema?.chart_series} primaryDirection={skillMetricSchema?.primary?.direction} />}
      {tab === 'iterations' && <IterationsTab iterations={iterations ?? []} bestIteration={session.best_iteration} researchId={id!} tableColumns={skillMetricSchema?.iteration_table_columns} />}
      {tab === 'log' && <AgentLog researchId={id!} isActive={isActive} />}
      {tab === 'harness' && <HarnessTab researchId={id!} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
function HarnessTab({ researchId }: { researchId: string }) {
  const { data: context, isLoading, error } = useHarnessContext(researchId);
  const pauseMut = usePauseSession();
  const resumeMut = useResumeSession();
  const stopMut = useStopSession();

  if (isLoading) return <p className="subtle">loading harness context…</p>;
  if (error || !context) {
    return (
      <p className="subtle" data-testid="harness-context-unavailable">
        harness context unavailable — controls stay consistent with server
        authorization
      </p>
    );
  }
  return (
    <HarnessContextPanel
      context={context}
      onAction={(action) => {
        // only enabled actions reach the server; the panel disables the rest
        if (action === 'pause') pauseMut.mutate(researchId);
        else if (action === 'resume') resumeMut.mutate(researchId);
        else if (action === 'stop') stopMut.mutate(researchId);
      }}
    />
  );
}

function StateTab({
  state,
  session: modelType,
  lastActivityAt,
  lastActivitySource,
  nowMs,
  isRunning,
  isPaused,
}: {
  state: ResearchState | null;
  session: string;
  lastActivityAt: string | null;
  lastActivitySource: string;
  nowMs: number;
  isRunning: boolean;
  isPaused: boolean;
}) {
  if (!state) {
    return <div className="placeholder" style={{ height: 240 }}>research state pending…</div>;
  }
  const activePhaseIndex = state.phase_state.phases.findIndex(
    (p) =>
      p.id === state.phase_state.current_phase ||
      p.status === 'in_progress' ||
      p.status === 'blocked',
  );
  const phaseItems = state.phase_state.phases.map((p, index) => ({
    id: p.id,
    label: p.label,
    status: activePhaseIndex >= 0 && index > activePhaseIndex ? 'pending' : p.status,
  }));
  const activePhase =
    state.phase_state.phases.find((p) => p.id === state.phase_state.current_phase) ??
    state.phase_state.phases.find((p) => p.status === 'in_progress' || p.status === 'blocked') ??
    null;
  const inPhase = state.phase_state.iterations_in_current_phase ?? 0;
  const stalled = state.phase_state.stalled_iterations ?? 0;
  const phaseCap = activePhase?.max_iterations;
  const phaseFloor = activePhase?.min_iterations;
  const phasePct = phaseCap ? Math.min(100, Math.round((inPhase / Math.max(1, phaseCap)) * 100)) : null;

  const budget = state.budget_usage;
  const budgetPct = Math.min(100, Math.round((budget.api_cost_usd / Math.max(budget.max_budget_usd, 0.0001)) * 100));
  const iterPct = Math.min(100, Math.round((budget.iterations_used / Math.max(1, budget.max_iterations)) * 100));
  const inactivityWarn = isRunning && lastActivityAt ? nowMs - new Date(lastActivityAt).getTime() > 120_000 : false;
  const activitySub = !lastActivityAt
    ? 'waiting for activity'
    : isPaused
      ? `paused · ${lastActivitySource}`
      : !isRunning
        ? lastActivitySource
        : inactivityWarn
          ? `no ${lastActivitySource} > 2m`
          : lastActivitySource;
  const activityBannerText = !lastActivityAt
    ? 'Waiting for live activity'
    : isPaused
      ? 'Session paused'
      : !isRunning
        ? 'Latest activity captured'
        : inactivityWarn
          ? 'No recent live update'
          : 'Live progress active';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
      <div className="col gap-4">
        <div className="card" style={{ padding: 18 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 className="h2">{state.current_phase || 'idle'}</h2>
            <div className="row gap-2">
              {state.phase_state.all_phases_complete && <span className="pill pill--green">complete</span>}
              <span className="pill pill--info mono">{state.status}</span>
            </div>
          </div>
          {state.next_action && (
            <div className="code" style={{ marginTop: 12 }}>
              <span className="key">next_action</span> = <span className="str">{state.next_action}</span>
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <PhaseBar phases={phaseItems} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 16 }}>
            <div className="card card--raised" style={{ padding: 12 }}>
              <Stat
                label="phase attempts"
                value={`${inPhase}${phaseCap ? `/${phaseCap}` : ''}`}
                sub={phaseFloor ? `${phaseFloor} min` : 'no floor'}
              />
              {phasePct != null && (
                <div className={`progress ${phasePct >= 90 ? 'progress--amber' : 'progress--info'}`} style={{ marginTop: 10 }}>
                  <div style={{ width: `${phasePct}%` }} />
                </div>
              )}
            </div>
            <div className="card card--raised" style={{ padding: 12 }}>
              <Stat
                label="stall count"
                value={stalled}
                deltaDir={stalled > 0 ? 'dn' : 'flat'}
                sub="trailing no-advance attempts"
              />
            </div>
            <div className="card card--raised" style={{ padding: 12 }}>
              <Stat label="iteration budget" value={`${iterPct}%`} sub={`${budget.iterations_used}/${budget.max_iterations}`} />
              <div className={`progress ${iterPct > 80 ? 'progress--red' : iterPct > 60 ? 'progress--amber' : 'progress--info'}`} style={{ marginTop: 10 }}>
                <div style={{ width: `${iterPct}%` }} />
              </div>
            </div>
            <div className="card card--raised" style={{ padding: 12 }}>
              <Stat
                label="last live event"
                value={fmtAgo(lastActivityAt, nowMs)}
                deltaDir={inactivityWarn ? 'dn' : 'flat'}
                sub={activitySub}
              />
            </div>
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

        <div className={`banner ${inactivityWarn ? 'banner--amber' : 'banner--info'}`}>
          <Icon name="bolt" />
          <div className="col gap-1">
            <span style={{ fontWeight: 600 }}>{activityBannerText}</span>
            <span className="mono" style={{ fontSize: 11 }}>{fmtAgo(lastActivityAt, nowMs)}</span>
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
type MetricDef = { key: string; label: string; better?: 'high' | 'low' };
type MetricDiagnostic = MetricDef & {
  latest: { iteration: number; value: unknown };
  best: { iteration: number; value: number } | null;
};
type DetailEntry = { key?: string; label: string; value: ReactNode };

// Metric columns come from the skill's metric_schema when available; the
// fallback auto-derives columns from the metrics the iterations carry.
function fallbackMetrics(iterations: Iteration[]): MetricDef[] {
  const seen = new Set<string>();
  for (const it of iterations) {
    for (const key of Object.keys(it.secondary_metrics ?? {})) {
      if (typeof it.secondary_metrics?.[key]?.value === 'number') seen.add(key);
      if (seen.size >= 8) break;
    }
    if (seen.size >= 8) break;
  }
  return Array.from(seen).map((key) => ({ key, label: key, better: undefined }));
}

function metricValue(iteration: Iteration, key: string): unknown {
  const secondary = iteration.secondary_metrics?.[key]?.value;
  if (secondary != null) return secondary;
  const readiness = iteration.feature_readiness_metrics?.[key];
  if (readiness != null) return readiness;
  const replay = iteration.rl_economic_replay as Record<string, unknown> | null | undefined;
  if (replay && replay[key] != null) return replay[key];
  return iteration.metrics?.[key];
}

function numberValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function hasDisplayValue(value: unknown): boolean {
  return value != null && value !== '';
}

function fmtMetric(value: unknown): string {
  const numeric = numberValue(value);
  if (numeric != null) {
    if (Math.abs(numeric) >= 100) return numeric.toFixed(0);
    if (Math.abs(numeric) >= 10) return numeric.toFixed(2);
    return numeric.toFixed(4);
  }
  if (!hasDisplayValue(value)) return '—';
  return String(value);
}

function metricLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderDetailValue(value: unknown): ReactNode {
  if (!hasDisplayValue(value)) return '—';
  if (typeof value === 'number') return fmtMetric(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === 'object') {
    const json = JSON.stringify(value);
    const summary = json.length > 96 ? `${json.slice(0, 93)}...` : json;
    return <span title={json}>{summary}</span>;
  }
  return String(value);
}

function recordDetailEntries(
  record: Record<string, unknown> | null | undefined,
  omitKeys = new Set<string>(),
): DetailEntry[] {
  if (!record) return [];
  return Object.entries(record)
    .filter(([key, value]) => !omitKeys.has(key) && hasDisplayValue(value))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => ({ key, label: metricLabel(key), value: renderDetailValue(value) }));
}

function diagnosticsFor(iterations: Iteration[]): MetricDiagnostic[] {
  const defs = fallbackMetrics(iterations);
  const discovered = new Set<string>();
  for (const it of iterations) {
    Object.keys(it.secondary_metrics || {}).forEach((key) => discovered.add(key));
  }
  const allDefs: MetricDef[] = [
    ...defs,
    ...Array.from(discovered)
      .filter((key) => !defs.some((def) => def.key === key))
      .map((key): MetricDef => ({ key, label: metricLabel(key) })),
  ];

  return allDefs.map((def) => {
    const points = iterations
      .map((it) => ({ iteration: it.iteration, value: metricValue(it, def.key) }))
      .filter((point) => hasDisplayValue(point.value));
    const numeric = points
      .map((point) => ({ iteration: point.iteration, value: numberValue(point.value) }))
      .filter((point): point is { iteration: number; value: number } => point.value != null);
    if (!points.length) return null;
    const latest = points[points.length - 1];
    const best = numeric.length
      ? numeric.reduce((winner, point) => {
          if (def.better === 'low') return point.value < winner.value ? point : winner;
          return point.value > winner.value ? point : winner;
        }, numeric[0])
      : null;
    return { ...def, latest, best };
  }).filter(Boolean) as MetricDiagnostic[];
}

function iterationOptionLabel(iteration: Iteration): string {
  const metric = iteration.primary_metric != null ? fmtMetric(iteration.primary_metric) : '—';
  const gates = iteration.all_gates_passed ? 'pass' : 'fail';
  const phase = iteration.search_phase || 'no phase';
  return `#${iteration.iteration} · ${metric} · ${gates} · ${phase}`;
}

function DetailGrid({ title, entries }: { title: string; entries: DetailEntry[] }) {
  if (!entries.length) return null;
  const visible = entries.slice(0, 12);
  const hidden = entries.slice(12);
  const renderEntry = (entry: DetailEntry, index: number) => (
    <div
      key={`${entry.key || entry.label}-${index}`}
      style={{
        minWidth: 0,
        background: 'var(--surface-2)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2)',
        padding: 10,
      }}
    >
      <div className="label truncate">{entry.label}</div>
      <div className="mono truncate" style={{ marginTop: 6, fontSize: 12 }}>
        {entry.value}
      </div>
    </div>
  );

  return (
    <section className="col gap-2">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="label">{title}</span>
        <span className="mono subtle" style={{ fontSize: 11 }}>{entries.length}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 10 }}>
        {visible.map(renderEntry)}
      </div>
      {hidden.length > 0 && (
        <details className="code" style={{ padding: 10 }}>
          <summary className="mono" style={{ cursor: 'pointer' }}>{hidden.length} more fields</summary>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 10, marginTop: 10 }}>
            {hidden.map(renderEntry)}
          </div>
        </details>
      )}
    </section>
  );
}

function IterationDetails({
  iteration,
  diagnostics,
}: {
  iteration: Iteration | null;
  diagnostics: MetricDiagnostic[];
}) {
  if (!iteration) {
    return <div className="placeholder" style={{ height: 120 }}>no iteration selected</div>;
  }

  const knownMetricKeys = new Set(diagnostics.map((metric) => metric.key));
  const objectiveEntries: DetailEntry[] = [
    { label: 'Iteration', value: `#${iteration.iteration}` },
    { label: iteration.metric_name || 'Primary Metric', value: fmtMetric(iteration.primary_metric) },
    { label: 'Gates', value: iteration.all_gates_passed ? 'pass' : 'fail' },
    { label: 'Training Gates', value: (iteration.training_gates_passed ?? iteration.all_gates_passed) ? 'pass' : 'fail' },
    { label: 'Decision', value: iteration.decision || '—' },
    { label: 'Phase', value: iteration.search_phase || '—' },
    { label: 'Train Time', value: iteration.training_time_s != null ? `${iteration.training_time_s.toFixed(1)}s` : '—' },
    { label: 'Created', value: iteration.created_at ? fmtAgo(iteration.created_at) : '—' },
  ];
  const selectedDiagnostics = diagnostics
    .map((metric) => ({
      key: metric.key,
      label: metric.label,
      value: metricValue(iteration, metric.key),
    }))
    .filter((entry) => hasDisplayValue(entry.value))
    .map((entry) => ({ ...entry, value: fmtMetric(entry.value) }));
  const artifactEntries: DetailEntry[] = [
    iteration.mlflow_url
      ? {
          label: 'MLflow Run',
          value: (
            <a href={iteration.mlflow_url} target="_blank" rel="noreferrer" className="lnk mono">
              {(iteration.mlflow_run_id || '').slice(0, 12) || 'open'}
            </a>
          ),
        }
      : { label: 'MLflow Run', value: iteration.mlflow_run_id || '—' },
    { label: 'Model Version', value: iteration.model_version || '—' },
    { label: 'Registry', value: iteration.model_registry_name || '—' },
    { label: 'Mode', value: iteration.training_mode || '—' },
    { label: 'Snapshot Hash', value: iteration.attempt_snapshot_hash || '—' },
    { label: 'Artifact Hash', value: iteration.artifact_hash || '—' },
    { label: 'Config Hash', value: iteration.config_snapshot_sha256 || '—' },
    { label: 'Snapshot Path', value: iteration.attempt_snapshot_path || '—' },
  ].filter((entry) => entry.value !== '—');
  const tsfmEvidenceKeys = new Set([
    'tsfm_adapter',
    'tsfm_fallback_validation',
    'tsfm_adapter_metadata',
  ]);
  const additionalMetricOmitKeys = new Set([...knownMetricKeys, ...tsfmEvidenceKeys]);
  const tsfmEvidenceEntries = recordDetailEntries({
    tsfm_adapter: iteration.metrics?.tsfm_adapter,
    tsfm_fallback_validation: iteration.metrics?.tsfm_fallback_validation,
    tsfm_adapter_metadata: iteration.metrics?.tsfm_adapter_metadata,
  });
  const additionalMetricEntries = recordDetailEntries(iteration.metrics, additionalMetricOmitKeys);
  const readinessEntries = recordDetailEntries(iteration.feature_readiness_metrics);
  const replayEntries = recordDetailEntries(iteration.rl_economic_replay as Record<string, unknown> | null | undefined);
  const attemptEntries = recordDetailEntries(iteration.attempt_snapshot);

  return (
    <div className="card">
      <div className="card__head">
        <div className="card__title">Iteration details</div>
        <span className="card__sub mono">#{iteration.iteration}</span>
        <span className={`pill ${iteration.all_gates_passed ? 'pill--green' : 'pill--red'}`}>
          <span className="dot" /> {iteration.all_gates_passed ? 'pass' : 'fail'}
        </span>
      </div>
      <div className="col gap-4" style={{ padding: 14 }}>
        <DetailGrid title="Objective" entries={objectiveEntries} />
        <DetailGrid title="Model diagnostics" entries={selectedDiagnostics} />
        <DetailGrid title="TS-FM evidence" entries={tsfmEvidenceEntries} />
        <DetailGrid title="Run artifacts" entries={artifactEntries} />
        <DetailGrid title="Feature readiness" entries={readinessEntries} />
        <DetailGrid title="Economic replay" entries={replayEntries} />
        <DetailGrid title="Additional metrics" entries={additionalMetricEntries} />
        <DetailGrid title="Attempt snapshot" entries={attemptEntries} />
      </div>
    </div>
  );
}

function MetricsTab({ iterations, modelType, chartSeries, primaryDirection }: { iterations: Iteration[]; modelType: string; chartSeries?: MetricColumn[]; primaryDirection?: string }) {
  const orderedIterations = useMemo(
    () => [...iterations].sort((a, b) => a.iteration - b.iteration),
    [iterations],
  );
  const latestIteration = orderedIterations.length
    ? orderedIterations[orderedIterations.length - 1].iteration
    : null;
  const [selectedIteration, setSelectedIteration] = useState<number | null>(null);
  const [manualSelection, setManualSelection] = useState(false);

  useEffect(() => {
    if (latestIteration == null) {
      setSelectedIteration(null);
      setManualSelection(false);
      return;
    }
    const selectedExists =
      selectedIteration != null && orderedIterations.some((it) => it.iteration === selectedIteration);
    if (manualSelection && selectedExists) return;
    if (manualSelection && !selectedExists) setManualSelection(false);
    setSelectedIteration(latestIteration);
  }, [latestIteration, manualSelection, orderedIterations, selectedIteration]);

  const selected = useMemo(
    () => orderedIterations.find((it) => it.iteration === selectedIteration) ?? orderedIterations[orderedIterations.length - 1] ?? null,
    [orderedIterations, selectedIteration],
  );
  const selectedIterationNumber = selected?.iteration ?? null;
  const passCount = orderedIterations.filter((it) => it.all_gates_passed).length;
  const passRate = orderedIterations.length ? Math.round((passCount / orderedIterations.length) * 100) : 0;
  const primaryPoints = orderedIterations.filter((it) => it.primary_metric != null);
  // Winner selection follows the objective direction the skill declares — the
  // same comparator semantics as the backend: minimize objectives pick
  // the lowest metric; ties keep the earlier iteration.
  const lowerIsBetter = primaryDirection === 'lower_is_better';
  const best = primaryPoints.reduce<Iteration | null>((winner, it) => {
    if (!winner) return it;
    const candidate = it.primary_metric ?? null;
    const incumbent = winner.primary_metric ?? null;
    if (candidate == null) return winner;
    if (incumbent == null) return it;
    return lowerIsBetter ? (candidate < incumbent ? it : winner) : (candidate > incumbent ? it : winner);
  }, null);
  const delta = primaryPoints.length > 1
    ? (primaryPoints[primaryPoints.length - 1].primary_metric ?? 0) - (primaryPoints[0].primary_metric ?? 0)
    : 0;
  const avgTrain = (() => {
    const vals = orderedIterations.map((it) => it.training_time_s).filter((v): v is number => typeof v === 'number');
    if (!vals.length) return '—';
    return `${(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)}s`;
  })();
  const diagnostics = useMemo(() => diagnosticsFor(orderedIterations), [orderedIterations]);

  const selectIteration = (iteration: number) => {
    setSelectedIteration(iteration);
    setManualSelection(latestIteration != null && iteration !== latestIteration);
  };

  const followLatest = () => {
    setManualSelection(false);
    setSelectedIteration(latestIteration);
  };

  return (
    <div className="col gap-4">
      <div className="card" style={{ padding: 16 }}>
        <div className="row gap-3" style={{ justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div className="col gap-1">
            <span className="label">objective + model metrics</span>
            {best && best.primary_metric != null && (
              <span className="mono subtle" style={{ fontSize: 11 }}>
                best #{best.iteration} · {best.primary_metric.toFixed(4)}
              </span>
            )}
          </div>
          <div className="row gap-2" style={{ flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <select
              className="select mono"
              style={{ width: 280 }}
              value={selectedIterationNumber ?? ''}
              onChange={(event) => selectIteration(Number(event.target.value))}
              disabled={!orderedIterations.length}
              aria-label="Select iteration metrics"
            >
              {orderedIterations.slice().reverse().map((iteration) => (
                <option key={iteration.id} value={iteration.iteration}>
                  {iterationOptionLabel(iteration)}
                </option>
              ))}
            </select>
            {manualSelection && latestIteration != null ? (
              <button className="btn btn--sm btn--ghost" onClick={followLatest}>
                latest
              </button>
            ) : selectedIterationNumber != null ? (
              <span className="pill pill--info"><span className="dot" /> latest</span>
            ) : null}
          </div>
        </div>
        <MetricsTrendChart
          iterations={orderedIterations}
          selectedIteration={selectedIterationNumber}
          onSelectIteration={selectIteration}
          chartSeries={chartSeries}
        />
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
          <Stat label="iterations" value={orderedIterations.length} sub={`${passCount} passing gates`} />
        </div>
      </div>
      <div className="card">
        <div className="card__head">
          <div className="card__title">Model diagnostics</div>
          <span className="card__sub">{diagnostics.length}</span>
          {selectedIterationNumber != null && <span className="card__sub mono">selected #{selectedIterationNumber}</span>}
        </div>
        {diagnostics.length === 0 ? (
          <div className="placeholder" style={{ margin: 14, height: 96 }}>no model metrics yet</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, padding: 14 }}>
            {diagnostics.map((metric) => {
              const selectedValue = selected ? metricValue(selected, metric.key) : null;
              return (
                <div key={metric.key} className="card card--raised" style={{ padding: 12 }}>
                  <div className="label">{metric.label}</div>
                  <div className="stat__value stat__value--sm" style={{ marginTop: 6 }}>
                    {hasDisplayValue(selectedValue) ? fmtMetric(selectedValue) : '—'}
                  </div>
                  <div className="subtle mono" style={{ fontSize: 11, marginTop: 4 }}>
                    {selectedIterationNumber != null ? `selected #${selectedIterationNumber}` : 'no selection'}
                    {metric.latest ? ` · latest #${metric.latest.iteration} ${fmtMetric(metric.latest.value)}` : ''}
                    {metric.best ? ` · best #${metric.best.iteration} ${fmtMetric(metric.best.value)}` : ''}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <IterationDetails iteration={selected} diagnostics={diagnostics} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
function IterationsTab({
  iterations,
  bestIteration,
  researchId,
  tableColumns,
}: {
  iterations: Iteration[];
  bestIteration: number | null;
  researchId: string;
  /** P3-025: manifest-driven columns from metric_schema.iteration_table_columns. */
  tableColumns?: MetricColumn[];
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
          <IterationsTable iterations={filtered} bestIteration={bestIteration} tableColumns={tableColumns} />
        </div>
      </div>
    </div>
  );
}
