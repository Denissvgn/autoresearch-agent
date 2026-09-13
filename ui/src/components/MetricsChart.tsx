import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from 'recharts';
import type { Iteration, MetricColumn } from '../api/client';

interface Props {
  iterations: Iteration[];
  selectedIteration?: number | null;
  onSelectIteration?: (iteration: number) => void;
  /** P3-024: manifest-driven chart series from metric_schema.chart_series.
   * When provided, overrides the hardcoded per-model-type series. */
  chartSeries?: MetricColumn[];
}

// Key secondary metrics worth charting per model type.
// Manifest chart_series (metric_schema.chart_series) are the primary source;
// when absent, the first numeric secondary metrics observed in the iterations
// are used as a generic fallback (P3-024).
const DEFAULT_COLORS = ['#34D399', '#FBBF24', '#F472B6', '#60A5FA', '#F87171', '#A78BFA'];

function fallbackSeries(iterations: Iteration[]): { key: string; label: string; color: string }[] {
  const seen = new Set<string>();
  for (const it of iterations) {
    const sm = it.secondary_metrics;
    if (!sm) continue;
    for (const key of Object.keys(sm)) {
      const value = sm[key]?.value;
      if (typeof value === 'number') seen.add(key);
      if (seen.size >= 3) break;
    }
    if (seen.size >= 3) break;
  }
  return Array.from(seen).map((key, i) => ({
    key,
    label: key,
    color: DEFAULT_COLORS[i % DEFAULT_COLORS.length],
  }));
}

function trainingGatesPassed(iteration: Iteration): boolean {
  return iteration.training_gates_passed ?? iteration.all_gates_passed;
}

export default function MetricsChart({ iterations, selectedIteration = null, onSelectIteration, chartSeries }: Props) {

  // P3-024: manifest-driven chart series take priority over the hardcoded
  // per-model-type fallback. When chartSeries is provided (from
  // metric_schema.chart_series via the skill descriptor), use it; otherwise
  // fall back to the legacy detection so existing sessions still render.
  const secondaryDefs = chartSeries && chartSeries.length > 0
    ? chartSeries.map((col, i) => ({
        key: col.field,
        label: col.label,
        color: DEFAULT_COLORS[i % DEFAULT_COLORS.length],
      }))
    : fallbackSeries(iterations);
  const [enabledLines, setEnabledLines] = useState<Set<string>>(new Set(['metric']));

  const data = iterations.map((it) => {
    const point: Record<string, unknown> = {
      iteration: it.iteration,
      metric: it.primary_metric,
      name: it.metric_name,
      passed: trainingGatesPassed(it),
    };
    for (const def of secondaryDefs) {
      const sm = it.secondary_metrics?.[def.key];
      if (sm) point[def.key] = typeof sm.value === 'number' ? sm.value : null;
    }
    return point;
  });

  if (data.length === 0) {
    return <div className="text-gray-500 text-sm py-8 text-center">No iterations yet</div>;
  }

  const toggleLine = (key: string) => {
    setEnabledLines((prev) => {
      const next = new Set(prev);
      if (key === 'metric') return prev; // Primary is always on
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  return (
    <div>
      {/* Toggle buttons for secondary metrics */}
      {secondaryDefs.length > 0 && (
        <div className="flex gap-2 mb-2 flex-wrap">
          <span className="text-xs text-gray-500 py-1">Overlay:</span>
          {secondaryDefs.map((def) => (
            <button
              key={def.key}
              onClick={() => toggleLine(def.key)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                enabledLines.has(def.key)
                  ? 'border-gray-500 text-gray-200 bg-gray-700'
                  : 'border-gray-700 text-gray-500 hover:border-gray-600'
              }`}
              style={enabledLines.has(def.key) ? { borderColor: def.color, color: def.color } : undefined}
            >
              {def.label}
            </button>
          ))}
        </div>
      )}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="iteration" stroke="#9CA3AF" fontSize={12} />
            <YAxis yAxisId="primary" stroke="#9CA3AF" fontSize={12} />
            {enabledLines.size > 1 && <YAxis yAxisId="secondary" orientation="right" stroke="#6B7280" fontSize={10} />}
            <Tooltip
              contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: 8 }}
              labelStyle={{ color: '#D1D5DB' }}
            />
            {(enabledLines.size > 1) && <Legend />}
            <Line
              yAxisId="primary"
              type="monotone"
              dataKey="metric"
              name="Primary Metric"
              stroke="#818CF8"
              strokeWidth={2}
              dot={(props: Record<string, unknown>) => {
                const { cx, cy, payload } = props as {
                  cx?: number;
                  cy?: number;
                  payload?: { iteration?: number; passed?: boolean };
                };
                if (typeof cx !== 'number' || typeof cy !== 'number' || !payload) return <g />;
                const iteration = Number(payload.iteration);
                const selected = Number.isFinite(iteration) && selectedIteration === iteration;
                return (
                  <circle
                    key={`dot-${cx}-${cy}`}
                    cx={cx}
                    cy={cy}
                    r={selected ? 6 : 4}
                    fill={payload.passed ? '#34D399' : '#F87171'}
                    stroke={selected ? '#F9FAFB' : 'none'}
                    strokeWidth={selected ? 2 : 0}
                    style={onSelectIteration ? { cursor: 'pointer' } : undefined}
                    onClick={(event) => {
                      event.stopPropagation();
                      if (Number.isFinite(iteration)) onSelectIteration?.(iteration);
                    }}
                  />
                );
              }}
            />
            {secondaryDefs
              .filter((def) => enabledLines.has(def.key))
              .map((def) => (
                <Line
                  key={def.key}
                  yAxisId="secondary"
                  type="monotone"
                  dataKey={def.key}
                  name={def.label}
                  stroke={def.color}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                  connectNulls
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
