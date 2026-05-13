import type { ResearchState } from '../api/client';

interface Props {
  state?: ResearchState;
}

function valueText(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  return String(value);
}

export default function ResearchStatePanel({ state }: Props) {
  if (!state) {
    return <div className="text-gray-500 text-sm py-4 text-center">State not available</div>;
  }

  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-xs text-gray-500">Current Phase</div>
          <div className="font-mono text-gray-100">{state.current_phase ?? '—'}</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-xs text-gray-500">Outcome</div>
          <div className="font-mono text-gray-100">{state.research_outcome ?? state.status ?? '—'}</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-xs text-gray-500">Terminal Reason</div>
          <div className="font-mono text-gray-100">{state.terminal_reason ?? '—'}</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-xs text-gray-500">Budget</div>
          <div className="font-mono text-gray-100">
            ${valueText(state.budget_usage.api_cost_usd)} / ${valueText(state.budget_usage.max_budget_usd)}
          </div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2 md:col-span-4">
          <div className="text-xs text-gray-500">Next Action</div>
          <div className="text-gray-100">{state.next_action ?? '—'}</div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-700 text-left text-gray-400">
              <th className="py-2 px-3">Phase</th>
              <th className="py-2 px-3">Status</th>
              <th className="py-2 px-3">Next Action</th>
            </tr>
          </thead>
          <tbody>
            {state.phase_state.phases.map((phase) => (
              <tr key={phase.id} className="border-b border-gray-800">
                <td className="py-2 px-3 text-gray-200">{phase.label}</td>
                <td className="py-2 px-3 font-mono">{phase.status}</td>
                <td className="py-2 px-3 text-gray-400">{phase.next_action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section>
          <h2 className="text-sm font-semibold mb-2">Top Candidates</h2>
          <div className="space-y-2">
            {state.top_candidates.length === 0 && (
              <div className="text-gray-500 text-xs">No candidates yet</div>
            )}
            {state.top_candidates.map((candidate) => (
              <div key={String(candidate.iteration)} className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="flex justify-between gap-2">
                  <span className="font-mono">#{valueText(candidate.iteration)}</span>
                  <span className="text-gray-400">{valueText(candidate.metric_name)} {valueText(candidate.primary_metric)}</span>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  decision={valueText(candidate.decision)} · consistency={valueText(candidate.consistency_passed)}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-sm font-semibold mb-2">Failed / Pruned</h2>
          <div className="space-y-2">
            {state.failed_pruned_configs.length === 0 && (
              <div className="text-gray-500 text-xs">No failed or pruned attempts</div>
            )}
            {state.failed_pruned_configs.slice(0, 5).map((candidate) => (
              <div key={String(candidate.iteration)} className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="flex justify-between gap-2">
                  <span className="font-mono">#{valueText(candidate.iteration)}</span>
                  <span className="text-red-300">{valueText(candidate.status ?? candidate.decision)}</span>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  {Array.isArray(candidate.gate_failure_reasons)
                    ? candidate.gate_failure_reasons.join(', ')
                    : '—'}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-gray-500">HPO Studies</div>
          <div className="font-mono text-gray-100">{state.hpo_study_ids.filter(Boolean).join(', ') || '—'}</div>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-gray-500">Rollback Target</div>
          {state.rollback_target != null ? (
            <div className="font-mono text-gray-100 truncate text-xs" title={state.rollback_target}>{state.rollback_target}</div>
          ) : state.latest_known_artifacts?.rollback_target != null ? (
            <>
              <div className="font-mono text-gray-100 truncate text-xs" title={state.latest_known_artifacts.rollback_target.value}>{state.latest_known_artifacts.rollback_target.value}</div>
              <div className="text-gray-500 mt-0.5">iter {state.latest_known_artifacts.rollback_target.iteration}</div>
            </>
          ) : (
            <div className="font-mono text-gray-100">—</div>
          )}
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
          <div className="text-gray-500">Smoke Status</div>
          {state.smoke_status != null ? (
            <div className="font-mono text-gray-100">{valueText('recorded')}</div>
          ) : state.latest_known_artifacts?.smoke_status != null ? (
            <>
              <div className="font-mono text-gray-100">{valueText('recorded')}</div>
              <div className="text-gray-500 mt-0.5">last known from iter {state.latest_known_artifacts.smoke_status.iteration}</div>
            </>
          ) : (
            <div className="font-mono text-gray-100">—</div>
          )}
        </div>
      </div>
    </div>
  );
}
