// Contract tests for MetricsChart (ARC-011 P3-024).
//
// Recharts renders SVG paths; rather than assert on chart internals, these
// tests pin the manifest-vs-fallback series selection through the overlay
// toggle buttons (one per secondary metric), which expose the resolved series
// by label. The manifest `chartSeries` must win when present; the hardcoded
// per-model-type fallback must be used otherwise.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MetricsChart from '../MetricsChart';
import type { Iteration, MetricColumn } from '../../api/client';

function makeIteration(overrides: Partial<Iteration> = {}): Iteration {
  return {
    id: 1,
    research_id: 'r1',
    iteration: 1,
    primary_metric: 0.7,
    metric_name: 'auc',
    all_gates_passed: true,
    decision: 'keep',
    description: '',
    config_snapshot: '',
    search_phase: '',
    training_time_s: 10,
    created_at: '2026-01-01T00:00:00Z',
    secondary_metrics: {
      walkforward_auc: { label: 'WF AUC', value: 0.65 },
    },
    ...overrides,
  } as Iteration;
}

describe('MetricsChart series selection (P3-024)', () => {
  it('uses the manifest chartSeries when provided (manifest wins)', () => {
    const chartSeries: MetricColumn[] = [
      { field: 'custom_a', label: 'Custom A' },
      { field: 'custom_b', label: 'Custom B' },
    ];
    render(
      <MetricsChart
        iterations={[makeIteration()]}
        chartSeries={chartSeries}
      />,
    );
    expect(screen.getByRole('button', { name: 'Custom A' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Custom B' })).toBeInTheDocument();
  });

  it('falls back to the observed numeric metrics when no manifest is given', () => {
    render(<MetricsChart iterations={[makeIteration()]} />);
    // The generic fallback derives series from the iteration's own numeric
    // secondary metrics (up to three).
    expect(screen.getByRole('button', { name: 'walkforward_auc' })).toBeInTheDocument();
  });

  it('falls back to skill-specific metrics when present', () => {
    render(
      <MetricsChart
        iterations={[makeIteration({
          secondary_metrics: {
            score: { label: 'Score', value: 0.8 },
            precision: { label: 'Precision', value: 0.6 },
          },
        })]}
      />,
    );
    expect(screen.getByRole('button', { name: 'score' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'precision' })).toBeInTheDocument();
  });

  it('renders the empty state when there are no iterations', () => {
    render(<MetricsChart iterations={[]} />);
    expect(screen.getByText('No iterations yet')).toBeInTheDocument();
  });

  it('renders the empty state even when a manifest chartSeries is provided but iterations are empty', () => {
    render(<MetricsChart iterations={[]} chartSeries={[{ field: 'x', label: 'X' }]} />);
    expect(screen.getByText('No iterations yet')).toBeInTheDocument();
  });
});
