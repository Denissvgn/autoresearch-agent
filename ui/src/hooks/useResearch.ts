import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { api, PromotionScopeRequest, StartResearchRequest } from '../api/client';
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
    || status === 'phase_failed'
    || status === 'promotion_blocked';
}

export function useSessions() {
  useWSInvalidation();
  return useQuery({ queryKey: ['sessions'], queryFn: api.listSessions, refetchInterval: 30_000 });
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
    refetchInterval: 30_000,
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

export function useInstruments() {
  return useQuery({ queryKey: ['instruments'], queryFn: api.getInstruments, staleTime: 60_000 });
}

export function useModels() {
  return useQuery({ queryKey: ['models'], queryFn: api.getModels, staleTime: 60_000 });
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
