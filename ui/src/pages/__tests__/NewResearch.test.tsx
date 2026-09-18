// Contract test for the NewResearch page (ARC-012 P7-015).
//
// Pins the start payload's canonical shape: a selected skill sends
// `skill_id` (+ subject_id/variant) — never the legacy
// model_type/instrument/timeframe trio, which after P7-010 is translated
// server-side and skill-checked (a legacy-trio payload for an uninstalled
// skill would 404 instead of starting a session).
//
// The hooks module is mocked (same pattern as PromotionModal.test.tsx) so
// the wiring is exercised without a QueryClient or network; the mutation
// captures the payload the form actually submits.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const _startSeen: unknown[] = [];

vi.mock('../../hooks/useResearch', () => ({
  useModels: () => ({
    data: [{ id: 'prompt-engineering', name: 'prompt-engineering', skill: 'prompt-engineering' }],
  }),
  useSkills: () => ({
    data: [
      {
        id: 'prompt-engineering',
        version: '0.3.0',
        category: 'generative',
        display_name: 'Prompt Engineering Research',
        description: 'Iterate prompt variants against an eval set.',
        schema_version: 'research_skill.v1',
        model_type: '',
        has_subjects: true,
        has_variants: true,
      },
    ],
  }),
  useSkillFormFields: () => ({ data: { form_fields: [] } }),
  useCostEstimate: () => ({ data: null, isLoading: false }),
  useStartResearch: () => ({
    mutate: (
      req: unknown,
      opts?: { onSuccess?: (session: { id: string }) => void },
    ) => {
      _startSeen.push(req);
      opts?.onSuccess?.({ id: 'res_ui0001' });
    },
    reset: () => {},
    isPending: false,
    isError: false,
    error: null,
  }),
}));

import NewResearch from '../NewResearch';

function renderPage() {
  return render(
    <MemoryRouter>
      <NewResearch />
    </MemoryRouter>,
  );
}

describe('NewResearch start payload (P7-015)', () => {
  beforeEach(() => {
    _startSeen.length = 0;
  });

  it('sends skill_id for a selected skill — never the legacy trio', () => {
    renderPage();

    // Select the skill from the picker card.
    fireEvent.click(screen.getByText('Prompt Engineering Research'));
    // Subject auto-defaults to 'default' once a skill is selected.
    fireEvent.click(screen.getByRole('button', { name: /start research/i }));

    expect(_startSeen).toHaveLength(1);
    const payload = _startSeen[0] as Record<string, unknown>;
    expect(payload.skill_id).toBe('prompt-engineering');
    expect(payload.subject_id).toBe('default');
    expect(typeof payload.variant).toBe('string');
    // The legacy trio must not ride along (P7-010/D3: the server translates
    // and skill-checks legacy requests — the UI sends canonical only).
    expect('model_type' in payload).toBe(false);
    expect('instrument' in payload).toBe(false);
    expect('timeframe' in payload).toBe(false);
  });

  it('cannot submit without a selected skill', () => {
    renderPage();
    const start = screen.getByRole('button', { name: /start research/i });
    expect((start as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByText('Prompt Engineering Research'));
    expect((screen.getByRole('button', { name: /start research/i }) as HTMLButtonElement).disabled)
      .toBe(false);
  });
});
