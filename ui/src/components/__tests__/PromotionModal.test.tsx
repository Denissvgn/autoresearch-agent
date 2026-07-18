// Contract tests for PromotionModal (ARC-011 P3-026).
//
// Pins the target_kind branching: the modal shows a target-specific label for
// registry_api / git_branch / artifact_store, and the default "Target" label
// otherwise (which covers file_path, the incumbent ML promotion target).
//
// The modal consumes react-query mutation hooks (usePreviewPromotion /
// useConfirmPromotion); these are mocked so the preview onSuccess path fires
// synchronously with a canned preview, exercising the render branch without a
// QueryClient or network.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { PromotionPreview } from '../../api/client';

// Mock the mutation hooks BEFORE importing the component.
const _previewStore: { current: PromotionPreview | null } = { current: null };
vi.mock('../../hooks/useResearch', () => ({
  usePreviewPromotion: () => ({
    mutate: (_args: unknown, opts: { onSuccess?: (d: PromotionPreview) => void }) => {
      if (_previewStore.current) opts.onSuccess?.(_previewStore.current);
    },
    reset: () => {},
    isPending: false,
    isError: false,
    error: null,
  }),
  useConfirmPromotion: () => ({
    mutate: (_args: unknown, opts: { onSuccess?: () => void }) => opts.onSuccess?.(),
    reset: () => {},
    isPending: false,
    isError: false,
    error: null,
  }),
}));

// The modal also pulls helper utilities from productionOps; they are pure and
// need no mocking. ConfigDiff renders a diff — also pure.

import PromotionModal from '../PromotionModal';
import type { ProductionOperations } from '../../api/client';

function minimalOperations(): ProductionOperations {
  return {
    schema_version: 'production_operations.v1',
    research_id: 'r1',
    model_type: 'direction',
    candidate: null,
    promotion: {
      blocked: false,
      blockers: [],
      blocker_details: [],
      scopes: [
        { scope: 'development', status: 'not_run', blockers: [], blocker_details: [] },
      ] as unknown as ProductionOperations['promotion']['scopes'],
    },
    warnings: [],
    rl_profit: {} as ProductionOperations['rl_profit'],
    feature_readiness: {} as ProductionOperations['feature_readiness'],
    oos_provenance: {} as ProductionOperations['oos_provenance'],
    inference_parity: {} as ProductionOperations['inference_parity'],
    rollback: {} as ProductionOperations['rollback'],
    audit_events: [],
  } as ProductionOperations;
}

function cannedPreview(overrides: Partial<PromotionPreview> = {}): PromotionPreview {
  return {
    research_id: 'r1',
    iteration: 2,
    target_path: '/tmp/cfg.yaml',
    target_kind: 'file_path',
    scope: 'development',
    promotion_scope: 'development',
    promotion_allowed: true,
    new_config: 'a: 1',
    current_config: 'a: 0',
    ...overrides,
  } as PromotionPreview;
}

describe('PromotionModal target_kind branching (P3-026)', () => {
  beforeEach(() => {
    _previewStore.current = null;
  });

  it('shows the registry API target label when target_kind = registry_api', async () => {
    const user = userEvent.setup();
    _previewStore.current = cannedPreview({ target_kind: 'registry_api' });
    render(<PromotionModal researchId="r1" operations={minimalOperations()} onClose={() => {}} />);
    await user.click(screen.getByText('Preview'));
    expect(screen.getByText('Target (registry API)')).toBeInTheDocument();
  });

  it('shows the git branch target label when target_kind = git_branch', async () => {
    const user = userEvent.setup();
    _previewStore.current = cannedPreview({ target_kind: 'git_branch' });
    render(<PromotionModal researchId="r1" operations={minimalOperations()} onClose={() => {}} />);
    await user.click(screen.getByText('Preview'));
    expect(screen.getByText('Target (git branch)')).toBeInTheDocument();
  });

  it('shows the artifact store target label when target_kind = artifact_store', async () => {
    const user = userEvent.setup();
    _previewStore.current = cannedPreview({ target_kind: 'artifact_store' });
    render(<PromotionModal researchId="r1" operations={minimalOperations()} onClose={() => {}} />);
    await user.click(screen.getByText('Preview'));
    expect(screen.getByText('Target (artifact store)')).toBeInTheDocument();
  });

  it('falls back to the default "Target" label for file_path', async () => {
    const user = userEvent.setup();
    _previewStore.current = cannedPreview({ target_kind: 'file_path' });
    render(<PromotionModal researchId="r1" operations={minimalOperations()} onClose={() => {}} />);
    await user.click(screen.getByText('Preview'));
    expect(screen.getByText('Target')).toBeInTheDocument();
    // The kind-specific labels must NOT appear for the default branch.
    expect(screen.queryByText('Target (registry API)')).not.toBeInTheDocument();
  });

  it('falls back to the default "Target" label when target_kind is absent (legacy)', async () => {
    const user = userEvent.setup();
    _previewStore.current = cannedPreview({ target_kind: undefined });
    render(<PromotionModal researchId="r1" operations={minimalOperations()} onClose={() => {}} />);
    await user.click(screen.getByText('Preview'));
    expect(screen.getByText('Target')).toBeInTheDocument();
  });
});
