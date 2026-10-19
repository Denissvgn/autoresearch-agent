// Leaderboard comparability: one champion table per comparable context —
// incomparable and legacy contexts never merge into a shared winner.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../hooks/useResearch', () => ({
  useSkills: () => ({ data: [{ id: 'prompt-engineering', display_name: 'PE' }] }),
  useSkillLeaderboard: () => ({
    data: {
      skill_id: 'prompt-engineering',
      metric: { field: 'score', label: 'Score', direction: 'higher_is_better', format: '.4f' },
      ranking_scope: 'global within comparable-context groups',
      groups: [
        {
          context: { objective: 'score', scorer: 'scorer-a' },
          label: 'objective=score, units=ratio, scorer=scorer-a',
          known_context: true,
          items: [
            {
              research_id: 'res_alpha0001', subject_id: 's', variant: 'v',
              tag: null, status: 'completed', best_metric: 0.7, metric_name: null,
              best_iteration: 1, iterations: 3, total_api_cost_usd: 1.5,
              started_at: '2026-10-01T00:00:00', completed_at: '2026-10-01T01:00:00',
            },
          ],
          total: 1, limit: 20, offset: 0,
        },
        {
          context: null,
          label: 'unknown / legacy context',
          known_context: false,
          items: [
            {
              research_id: 'res_legacy001', subject_id: 's', variant: 'v',
              tag: null, status: 'completed', best_metric: 0.99, metric_name: null,
              best_iteration: 1, iterations: 1, total_api_cost_usd: 0.5,
              started_at: '2026-09-01T00:00:00', completed_at: '2026-09-01T01:00:00',
            },
          ],
          total: 1, limit: 20, offset: 0,
        },
      ],
    },
    isLoading: false,
  }),
}));

import Leaderboard from '../Leaderboard';

describe('Leaderboard groups are never merged', () => {
  it('renders one champion table per comparable context', () => {
    render(
      <MemoryRouter>
        <Leaderboard />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('ranking-scope').textContent).toContain(
      'global within comparable-context groups',
    );
    const known = screen.getByTestId('leaderboard-group-known');
    const unknown = screen.getByTestId('leaderboard-group-unknown');
    // the incomparable legacy result (0.99) sits in its own group and is
    // never a shared champion over the known group's 0.7
    expect(known.textContent).toContain('res_alpha');
    expect(known.textContent).not.toContain('res_legacy');
    expect(unknown.textContent).toContain('res_legacy');
    expect(unknown.textContent).toContain('unknown / legacy context');
  });
});