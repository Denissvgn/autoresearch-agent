// Contract tests for IterationsTable (ARC-011 P3-025).
//
// Pins the manifest-driven extra columns: when tableColumns is provided, the
// extra columns render headers + per-row values sourced from iteration
// metrics; otherwise the default columns render. Also guards the best-row
// highlight and the empty state.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import IterationsTable from '../IterationsTable';
import type { Iteration, MetricColumn } from '../../api/client';

function makeIteration(overrides: Partial<Iteration> = {}): Iteration {
  return {
    id: 1,
    research_id: 'r1',
    iteration: 1,
    primary_metric: 0.7231,
    metric_name: 'auc',
    all_gates_passed: true,
    training_gates_passed: true,
    decision: 'keep',
    description: '',
    config_snapshot: '',
    search_phase: 'validation',
    training_time_s: 120,
    created_at: '2026-01-01T00:00:00Z',
    metrics: { custom_metric: 0.91 },
    ...overrides,
  } as Iteration;
}

describe('IterationsTable (P3-025)', () => {
  it('renders the default columns when no tableColumns are provided', () => {
    render(<IterationsTable iterations={[makeIteration()]} />);
    // Default built-in headers (sample).
    expect(screen.getByText('Metric')).toBeInTheDocument();
    expect(screen.getByText('Decision')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
  });

  it('renders manifest-driven extra column headers', () => {
    const cols: MetricColumn[] = [
      { field: 'custom_metric', label: 'Custom Metric' },
      { field: 'other', label: 'Other' },
    ];
    render(<IterationsTable iterations={[makeIteration()]} tableColumns={cols} />);
    expect(screen.getByText('Custom Metric')).toBeInTheDocument();
    expect(screen.getByText('Other')).toBeInTheDocument();
  });

  it('sources extra column cell values from iteration.metrics by field name', () => {
    const cols: MetricColumn[] = [{ field: 'custom_metric', label: 'Custom Metric' }];
    const { container } = render(
      <IterationsTable iterations={[makeIteration()]} tableColumns={cols} />,
    );
    // 0.91 from metrics.custom_metric → formatted to 4 decimals.
    expect(container.textContent).toContain('0.9100');
  });

  it('renders an em-dash for an extra column whose metric is absent', () => {
    const cols: MetricColumn[] = [{ field: 'missing_metric', label: 'Missing' }];
    const { container } = render(
      <IterationsTable iterations={[makeIteration()]} tableColumns={cols} />,
    );
    // formatValue(null) → '—' present somewhere in the row.
    expect(container.textContent).toContain('—');
  });

  it('renders the empty state when there are no iterations', () => {
    render(<IterationsTable iterations={[]} />);
    expect(screen.getByText('No iterations recorded')).toBeInTheDocument();
  });

  it('marks the best iteration row with the highlight class', () => {
    const { container } = render(
      <IterationsTable iterations={[makeIteration()]} bestIteration={1} />,
    );
    // The best row carries the indigo highlight class (P3-025 visual cue).
    expect(container.querySelector('.bg-indigo-500\\/10')).not.toBeNull();
  });

  it('does not mark a row as best when bestIteration does not match', () => {
    const { container } = render(
      <IterationsTable iterations={[makeIteration()]} bestIteration={99} />,
    );
    expect(container.querySelector('.bg-indigo-500\\/10')).toBeNull();
  });
});
