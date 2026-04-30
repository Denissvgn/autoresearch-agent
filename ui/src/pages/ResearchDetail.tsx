import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSession, useIterations, useResearchState, useStopSession, usePauseSession, useResumeSession, useContinueSession } from '../hooks/useResearch';
import { api } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import MetricsChart from '../components/MetricsChart';
import IterationsTable from '../components/IterationsTable';
import AgentLog from '../components/AgentLog';
import PromotionModal from '../components/PromotionModal';
import ResearchStatePanel from '../components/ResearchStatePanel';
import ProductionOpsPanel from '../components/ProductionOpsPanel';

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: session, isLoading } = useSession(id!);
  const { data: iterations } = useIterations(id!);
  const { data: researchState } = useResearchState(id!);
  const stopMut = useStopSession();
  const pauseMut = usePauseSession();
  const resumeMut = useResumeSession();
  const continueMut = useContinueSession();
  const [showPromotion, setShowPromotion] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [tab, setTab] = useState<'ops' | 'state' | 'chart' | 'table' | 'log'>('ops');

  if (isLoading || !session) {
    return <div className="text-gray-500">Loading...</div>;
  }

  const isActive = session.status === 'running' || session.status === 'paused';
  const canPromote = session.best_iteration != null && session.best_iteration > 0;
  const canContinuePipeline = session.status === 'timed_out'
    || session.status === 'phase_failed'
    || session.status === 'promotion_blocked';

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">{session.instrument}</h1>
            <StatusBadge status={session.status} />
          </div>
          <div className="text-sm text-gray-500 mt-1">
          {session.model_type} · {session.timeframe}
          {session.tag && <span> · #{session.tag}</span>}
          {(session.current_phase || researchState?.current_phase) && (
            <span> · phase: {session.current_phase || researchState?.current_phase}</span>
          )}
          <span className="ml-3 font-mono text-xs">{session.id.slice(0, 8)}</span>
            {session.resumed_from && (
              <span className="ml-2 text-blue-400">
                ← continued from <a href={`/research/${session.resumed_from}`} className="underline font-mono">{session.resumed_from.slice(0, 12)}</a>
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {session.status === 'running' && (
            <>
              <button
                onClick={() => pauseMut.mutate(id!)}
                className="px-3 py-1.5 bg-yellow-600/20 text-yellow-400 rounded text-sm hover:bg-yellow-600/30"
              >
                Pause
              </button>
              <button
                onClick={() => stopMut.mutate(id!)}
                className="px-3 py-1.5 bg-red-600/20 text-red-400 rounded text-sm hover:bg-red-600/30"
              >
                Stop
              </button>
            </>
          )}
          {session.status === 'paused' && (
            <>
              <button
                onClick={() => resumeMut.mutate(id!)}
                className="px-3 py-1.5 bg-green-600/20 text-green-400 rounded text-sm hover:bg-green-600/30"
              >
                Resume
              </button>
              <button
                onClick={() => stopMut.mutate(id!)}
                className="px-3 py-1.5 bg-red-600/20 text-red-400 rounded text-sm hover:bg-red-600/30"
              >
                Stop
              </button>
            </>
          )}
          {canContinuePipeline && (
            <button
              onClick={() => continueMut.mutate(id!)}
              className="px-3 py-1.5 bg-blue-600/20 text-blue-400 rounded text-sm hover:bg-blue-600/30"
              disabled={continueMut.isPending}
            >
              {continueMut.isPending ? 'Continuing...' : 'Continue'}
            </button>
          )}
          {canPromote && !isActive && (
            <button
              onClick={() => setShowPromotion(true)}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded text-sm"
            >
              Promote Config
            </button>
          )}
          <div className="relative">
            <button
              onClick={() => setShowExport((v) => !v)}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm flex items-center gap-1"
            >
              Export
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showExport && (
              <div className="absolute right-0 mt-1 w-48 bg-gray-800 border border-gray-700 rounded shadow-lg z-10">
                <button
                  onClick={() => { api.downloadConfig(id!); setShowExport(false); }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-700 rounded-t"
                >
                  Best Config (.yaml)
                </button>
                <button
                  onClick={() => { api.downloadAgentLog(id!); setShowExport(false); }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-700"
                >
                  Agent Log (.jsonl)
                </button>
                <button
                  onClick={() => { api.downloadResults(id!); setShowExport(false); }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-700 rounded-b"
                >
                  Full Results (.json)
                </button>
              </div>
            )}
          </div>
          <button
            onClick={() => navigate(-1)}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm"
          >
            Back
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex gap-4 flex-wrap">
        {[
          { label: 'Best Metric', value: session.best_metric != null ? session.best_metric.toFixed(4) : '—' },
          { label: 'Best Iteration', value: session.best_iteration != null ? `#${session.best_iteration}` : '—' },
          { label: 'Iterations', value: `${iterations?.length ?? 0}/${session.max_iterations}` },
          { label: 'Cost', value: `$${(session.total_api_cost_usd ?? 0).toFixed(2)}` },
          { label: 'Mode', value: session.quick_mode ? 'Quick' : 'Standard' },
        ].map((s) => (
          <div key={s.label} className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
            <div className="text-xs text-gray-500">{s.label}</div>
            <div className="font-mono text-sm">{s.value}</div>
          </div>
        ))}
        {/* Best iteration MLflow link */}
        {(() => {
          const best = iterations?.find((it) => it.iteration === session.best_iteration);
          if (best?.mlflow_url) {
            return (
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-xs text-gray-500">Best MLflow Run</div>
                <a
                  href={best.mlflow_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-indigo-400 hover:text-indigo-300 underline font-mono"
                >
                  {best.mlflow_run_id?.slice(0, 8) ?? '—'}
                </a>
              </div>
            );
          }
          return null;
        })()}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-700 flex gap-4">
        {(['ops', 'state', 'chart', 'table', 'log'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-sm capitalize ${tab === t ? 'text-indigo-400 border-b-2 border-indigo-400' : 'text-gray-500 hover:text-gray-300'}`}
          >
            {t === 'ops' ? 'Operations' : t === 'state' ? 'State' : t === 'chart' ? 'Metrics Chart' : t === 'table' ? 'Iterations' : 'Agent Log'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'ops' && <ProductionOpsPanel state={researchState} />}
      {tab === 'state' && <ResearchStatePanel state={researchState} />}
      {tab === 'chart' && <MetricsChart iterations={iterations ?? []} />}
      {tab === 'table' && (
        <IterationsTable iterations={iterations ?? []} bestIteration={session.best_iteration} />
      )}
      {tab === 'log' && <AgentLog researchId={id!} isActive={isActive} />}

      {/* Error */}
      {session.error_message && (
        <div className="bg-red-900/20 border border-red-800 rounded p-3 text-sm text-red-300">
          {session.error_message}
          {session.promotion_blockers && session.promotion_blockers.length > 0 && (
            <div className="mt-2 text-xs text-red-200">
              {session.promotion_blockers.join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Promotion modal */}
      {showPromotion && (
        <PromotionModal
          researchId={id!}
          operations={researchState?.production_operations ?? null}
          onClose={() => setShowPromotion(false)}
        />
      )}
    </div>
  );
}
