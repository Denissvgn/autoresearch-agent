import { useState } from 'react';
import type { Iteration, MetricColumn } from '../api/client';

interface Props {
  iterations: Iteration[];
  bestIteration?: number | null;
  /** P3-025: manifest-driven columns from metric_schema.iteration_table_columns.
   * When provided, extra columns are rendered from iteration metrics data. */
  tableColumns?: MetricColumn[];
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s}s`;
}

function formatValue(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(4);
  }
  return String(v);
}

function trainingGatesPassed(iteration: Iteration): boolean {
  return iteration.training_gates_passed ?? iteration.all_gates_passed;
}

export default function IterationsTable({ iterations, bestIteration, tableColumns }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const extraCols = tableColumns ?? [];

  if (iterations.length === 0) {
    return <div className="text-gray-500 text-sm py-4 text-center">No iterations recorded</div>;
  }

  const toggle = (n: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(n) ? next.delete(n) : next.add(n);
      return next;
    });
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400 text-left">
            <th className="py-2 px-3 w-6"></th>
            <th className="py-2 px-3">#</th>
            <th className="py-2 px-3">Metric</th>
            <th className="py-2 px-3">Value</th>
            <th className="py-2 px-3">Training Gates</th>
            <th className="py-2 px-3">Decision</th>
            <th className="py-2 px-3">Duration</th>
            <th className="py-2 px-3">Time</th>
            {extraCols.map((col) => (
              <th key={col.field} className="py-2 px-3">{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {iterations.map((it) => {
            const isExpanded = expanded.has(it.iteration);
            const hasSecondary = it.secondary_metrics && Object.keys(it.secondary_metrics).length > 0;
            const hasDetails = hasSecondary || Boolean(it.consistency_report || it.artifact_hash || it.attempt_snapshot_hash);
            return (
              <>
                <tr
                  key={it.iteration}
                  className={`border-b border-gray-800 cursor-pointer hover:bg-gray-800/50 ${it.iteration === bestIteration ? 'bg-indigo-500/10' : ''}`}
                  onClick={() => toggle(it.iteration)}
                >
                  <td className="py-2 px-3 text-gray-500 text-xs">
                    {hasDetails ? (isExpanded ? '▼' : '▶') : ''}
                  </td>
                  <td className="py-2 px-3 font-mono">
                    {it.iteration}
                    {it.iteration === bestIteration && (
                      <span className="ml-1 text-yellow-400 text-xs">★</span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-gray-400">{it.metric_name}</td>
                  <td className="py-2 px-3 font-mono">
                    {it.primary_metric != null ? it.primary_metric.toFixed(4) : '—'}
                  </td>
                  <td className="py-2 px-3">
                    {trainingGatesPassed(it) ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-red-400">✗</span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    {it.decision === 'keep' ? (
                      <span className="text-green-400">{it.decision}</span>
                    ) : it.decision === 'improve' ? (
                      <span className="text-yellow-400">{it.decision}</span>
                    ) : it.decision === 'discard' ? (
                      <span className="text-red-400">{it.decision}</span>
                    ) : it.decision === 'hpo_screening' ? (
                      <span className="text-purple-400">HPO</span>
                    ) : (
                      <span className="text-gray-300">{it.decision}</span>
                    )}
                    {it.search_phase && (
                      <span className="ml-1 text-[10px] px-1 py-0.5 rounded bg-purple-900/50 text-purple-300">
                        {it.search_phase === 'hpo_screening' ? 'HPO' : it.search_phase}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-gray-400 font-mono text-xs">
                    {formatDuration(it.training_time_s)}
                  </td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{new Date(it.created_at).toLocaleTimeString()}</td>
                  {extraCols.map((col) => (
                    <td key={col.field} className="py-2 px-3 font-mono text-xs text-gray-400">
                      {formatValue(it.metrics?.[col.field])}
                    </td>
                  ))}
                </tr>
                {isExpanded && (
                  <tr key={`${it.iteration}-detail`} className="border-b border-gray-800 bg-gray-900/50">
                    <td colSpan={8 + extraCols.length} className="py-3 px-6">
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 text-xs">
                        {hasSecondary && Object.entries(it.secondary_metrics).map(([key, m]) => (
                          <div key={key} className="bg-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500">{m.label}</div>
                            <div className="font-mono text-gray-200">{formatValue(m.value)}</div>
                          </div>
                        ))}
                        {it.training_mode && (
                          <div className="bg-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500">Training Mode</div>
                            <div className="font-mono text-gray-200">{it.training_mode}</div>
                          </div>
                        )}
                        {it.model_version && (
                          <div className="bg-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500">Model Version</div>
                            <div className="font-mono text-gray-200">{it.model_version}</div>
                          </div>
                        )}
                        {it.artifact_hash && (
                          <div className="bg-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500">Artifact Hash</div>
                            <div className="font-mono text-gray-200 break-all">{it.artifact_hash}</div>
                          </div>
                        )}
                        {it.attempt_snapshot_hash && (
                          <div className="bg-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500">Attempt Snapshot</div>
                            <div className="font-mono text-gray-200 break-all">{it.attempt_snapshot_hash}</div>
                          </div>
                        )}
                        {it.consistency_report && (
                          <div className="bg-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500">Consistency</div>
                            <div className={it.consistency_report.passed ? 'text-green-300' : 'text-red-300'}>
                              {it.consistency_report.passed ? 'passed' : it.consistency_report.blockers.join(', ')}
                            </div>
                          </div>
                        )}
                      </div>
                      {/* Links row */}
                      <div className="mt-2 flex gap-4 text-xs">
                        {it.mlflow_url && (
                          <a
                            href={it.mlflow_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-400 hover:text-indigo-300 underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            View in MLflow →
                          </a>
                        )}
                        {it.mlflow_run_id && (
                          <span className="text-gray-600 font-mono">{it.mlflow_run_id.slice(0, 8)}</span>
                        )}
                      </div>
                      {it.description && (
                        <div className="mt-2 text-xs text-gray-500 italic">{it.description}</div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
