import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { api, PromotionScopeRequest, StartResearchRequest, PaginatedResponse, ResearchSession } from '../api/client';
import { useWebSocket } from './useWebSocket';

/**
 * Invalidate queries on WS events instead of aggressive polling.
 * Polling is kept as a slow fallback (30s) for resilience.
 */
function useWSInvalidation() {
  const { on } = useWebSocket();
  const qc = useQueryClient();

  useEffect(() => {
    const unsubs = [
      on('iteration_complete', () => {
        qc.invalidateQueries({ queryKey: ['sessions'] });
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['iterations'] });
        qc.invalidateQueries({ queryKey: ['results'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('research_completed', () => {
        qc.invalidateQueries({ queryKey: ['sessions'] });
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['results'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('research_failed', () => {
        qc.invalidateQueries({ queryKey: ['sessions'] });
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('pipeline_phase_started', () => {
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['iterations'] });
        qc.invalidateQueries({ queryKey: ['results'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('phase_state_updated', () => {
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('pipeline_phase_completed', () => {
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['iterations'] });
        qc.invalidateQueries({ queryKey: ['results'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('pipeline_completed', () => {
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['iterations'] });
        qc.invalidateQueries({ queryKey: ['results'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
      on('pipeline_promotion_blocked', () => {
        qc.invalidateQueries({ queryKey: ['session'] });
        qc.invalidateQueries({ queryKey: ['iterations'] });
        qc.invalidateQueries({ queryKey: ['results'] });
        qc.invalidateQueries({ queryKey: ['research-state'] });
        qc.invalidateQueries({ queryKey: ['status'] });
      }),
    ];
    return () => unsubs.forEach((u) => u());
  }, [on, qc]);
}

function isTerminalStatus(status?: string) {
  return status === 'completed'
    || status === 'failed'
    || status === 'stopped'
    || status === 'timed_out'
    || status === 'phase_failed'
    || status === 'promotion_blocked';
}

export function ResearchRealtimeBridge() {
  useWSInvalidation();
  return null;
}

export function useSessions() {
  return useQuery({ queryKey: ['sessions'], queryFn: api.listSessions, refetchInterval: 30_000 });
}

export function useSessionsPage(limit: number, offset: number) {
  return useQuery<PaginatedResponse<ResearchSession>>({
    queryKey: ['sessions-page', limit, offset],
    queryFn: () => api.listSessionsPage(limit, offset),
    refetchInterval: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useSession(id: string) {
  return useQuery({
    queryKey: ['session', id],
    queryFn: () => api.getSession(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (isTerminalStatus(status)) return false;
      return 30_000;
    },
  });
}

export function useResults(id: string) {
  return useQuery({
    queryKey: ['results', id],
    queryFn: () => api.getResults(id),
    refetchInterval: (query) => {
      const status = query.state.data?.session?.status;
      if (isTerminalStatus(status)) return false;
      return 30_000;
    },
  });
}

export function useIterations(id: string) {
  return useQuery({ queryKey: ['iterations', id], queryFn: () => api.getIterations(id), refetchInterval: 30_000 });
}

export function useResearchState(id: string) {
  return useQuery({
    queryKey: ['research-state', id],
    queryFn: () => api.getResearchState(id),
    refetchInterval: (query) => {
      const status = (query.state.data as any)?.status;
      if (isTerminalStatus(status)) return false;
      return 30_000;
    },
  });
}

export function useBestIteration(id: string) {
  return useQuery({ queryKey: ['best', id], queryFn: () => api.getBestIteration(id) });
}

export function useAgentLog(id: string, isActive = false) {
  // Active sessions are updated via WS agent_log events — no polling needed.
  // Completed/failed sessions: single fetch with no refetch.
  return useQuery({
    queryKey: ['agent-log', id],
    queryFn: () => api.getAgentLog(id),
    refetchInterval: false,
    // Fetch once on mount so the log container initialises with historical lines.
    staleTime: isActive ? 0 : Infinity,
  });
}


export function useModels() {
  return useQuery({ queryKey: ['models'], queryFn: api.getModels, staleTime: 60_000 });
}

// ── Skill hooks (ARC-011 P3-021..025) ──────────────────────────────────

export function useSkills() {
  return useQuery({ queryKey: ['skills'], queryFn: () => api.getSkills(), staleTime: 60_000 });
}

export function useSkillFormFields(skillId: string | null) {
  return useQuery({
    queryKey: ['skill-form-fields', skillId],
    queryFn: () => api.getSkillFormFields(skillId!),
    enabled: Boolean(skillId),
    staleTime: 60_000,
  });
}

export function useSkillMetricSchema(skillId: string | null) {
  return useQuery({
    queryKey: ['skill-metric-schema', skillId],
    queryFn: () => api.getSkillMetricSchema(skillId!),
    enabled: Boolean(skillId),
    staleTime: 60_000,
  });
}

// P0-4: cross-session leaderboard for one skill.
export function useSkillLeaderboard(skillId: string | null, limit = 20) {
  return useQuery({
    queryKey: ['skill-leaderboard', skillId, limit],
    queryFn: () => api.getSkillLeaderboard(skillId!, limit),
    enabled: Boolean(skillId),
    refetchInterval: 30_000,
  });
}

export function useStatus() {
  return useQuery({ queryKey: ['status'], queryFn: api.getStatus, refetchInterval: 30_000 });
}

export function usePromotions() {
  return useQuery({ queryKey: ['promotions'], queryFn: api.listPromotions });
}

export function useStartResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: StartResearchRequest) => api.startResearch(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions'] });
      qc.invalidateQueries({ queryKey: ['status'] });
    },
  });
}

// P2 ops: server-side expected-cost preview for the New Research wizard.
// Keyed on the form values that drive the estimate; falls back to nothing
// while loading (the caller renders a placeholder).
export function useCostEstimate(
  maxIterations: number,
  quickMode: boolean,
  maxBudgetUsd?: number,
) {
  return useQuery({
    queryKey: ['cost-estimate', maxIterations, quickMode, maxBudgetUsd ?? null],
    queryFn: () =>
      api.estimateCost({
        max_iterations: maxIterations,
        quick_mode: quickMode,
        ...(maxBudgetUsd != null ? { max_budget_usd: maxBudgetUsd } : {}),
      }),
    staleTime: 300_000,
    retry: 1,
  });
}

export function useStopSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.stopSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function usePauseSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.pauseSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function useResumeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.resumeSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function useContinueSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.continueSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function usePreviewPromotion() {
  return useMutation({
    mutationFn: ({ id, request }: { id: string; request?: PromotionScopeRequest }) =>
      api.previewPromotion(id, request),
  });
}

export function useConfirmPromotion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, request }: { id: string; request?: PromotionScopeRequest }) =>
      api.confirmPromotion(id, request),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['promotions'] });
      qc.invalidateQueries({ queryKey: ['research-state'] });
    },
  });
}
