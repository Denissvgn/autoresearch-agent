const BASE = '/api';

export interface ResearchSession {
  id: string;
  instrument: string;
  timeframe: string;
  model_type: string;
  tag: string;
  skill_name: string;
  status: string;
  quick_mode: boolean | number;
  max_iterations: number;
  max_budget_usd: number;
  focus_hint: string | null;
  workspace_path: string;
  best_metric: number | null;
  best_iteration: number | null;
  total_api_cost_usd: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  resumed_from: string | null;
  current_phase?: string | null;
  next_action?: string | null;
  phase_state_json?: string | null;
  active_phase_session_id?: string | null;
}

export interface SecondaryMetric {
  label: string;
  value: number | string;
}

export interface Iteration {
  id: number;
  research_id: string;
  iteration: number;
  primary_metric: number | null;
  metric_name: string;
  all_gates_passed: boolean;
  decision: string;
  config_snapshot: string | null;
  metrics_json: string | null;
  created_at: string;
  // ML-58: Enriched fields from backend
  metrics: Record<string, unknown>;
  mlflow_run_id: string;
  mlflow_url: string | null;
  model_version: string | null;
  model_registry_name: string | null;
  training_time_s: number | null;
  training_mode: string | null;
  description: string | null;
  secondary_metrics: Record<string, SecondaryMetric>;
  // ML-59: HPO search phase
  search_phase: string | null;
  attempt_snapshot_hash?: string | null;
  attempt_snapshot_path?: string | null;
  artifact_hash?: string | null;
  config_snapshot_sha256?: string | null;
  consistency_report?: ConsistencyReport | null;
}

export interface ConsistencyReport {
  schema_version: string;
  passed: boolean;
  blockers: string[];
  checks: Array<{ name: string; status: string; detail?: string | null }>;
  config_snapshot_sha256?: string | null;
  artifact_hash?: string | null;
  feature_schema_hash?: string | null;
  mlflow_run_id?: string | null;
}

export interface AgentLogEntry {
  ts: string;
  turn: number;
  type: string;
  content: string;
  meta: Record<string, unknown>;
  research_id?: string;
  pipeline_phase?: string;
}

export interface Promotion {
  id: number;
  research_id: string;
  iteration: number;
  target_path: string;
  config_yaml: string;
  previous_yaml: string | null;
  promoted_at: string;
}

export interface PromotionPreview {
  research_id: string;
  iteration: number;
  target_path: string;
  new_config: string;
  current_config: string | null;
}

export interface StartResearchRequest {
  instrument: string;
  timeframe: string;
  model_type: string;
  tag?: string;
  quick_mode?: boolean;
  max_iterations?: number;
  max_budget_usd?: number;
  timeout_minutes?: number;
  focus_hint?: string;
  // RL-specific fixed settings (not in tuning space)
  trading_mode?: 'stock' | 'margin';
  agent_strategy?: 'AGGR' | 'CONS' | 'BALA' | 'SCAL';
  initial_balance?: number;
  // ML-59: HPO settings (RL only)
  enable_hpo?: boolean;
  hpo_trials?: number;
  hpo_timesteps?: number;
  // ML-63: Pipeline settings
  phase_budgets?: { direction?: number; volatility?: number; rl?: number };
}

export interface HpoTrial {
  rank: number;
  trial_number: number;
  composite_score: number;
  params: Record<string, unknown>;
  metrics: Record<string, number>;
}

export interface HpoStudy {
  id: number;
  research_id: string;
  iteration: number;
  n_trials: number;
  completed_trials: number;
  best_composite: number | null;
  training_time_s: number | null;
  top_trials: HpoTrial[];
  study_id?: string | null;
  max_trials?: number | null;
  search_space?: Record<string, unknown>;
  budget?: Record<string, unknown>;
  timeout_s?: number | null;
  quick_mode?: boolean | number;
  status: string;
  created_at: string;
}

export interface ResearchState {
  schema_version: string;
  research_id: string;
  model_type: string;
  status: string;
  current_phase: string | null;
  next_action: string | null;
  phase_state: {
    current_phase: string | null;
    next_action: string | null;
    blocked: boolean;
    block_reason: string | null;
    phases: Array<{ id: string; label: string; status: string; next_action: string }>;
  };
  top_candidates: Array<Record<string, unknown>>;
  failed_pruned_configs: Array<Record<string, unknown>>;
  gate_failure_reasons: Array<{ iteration: number; blockers: string[] }>;
  budget_usage: {
    api_cost_usd: number;
    max_budget_usd: number;
    iterations_used: number;
    max_iterations: number;
  };
  hpo_studies: HpoStudy[];
  hpo_study_ids: Array<string | number | null>;
  artifact_hashes: Array<{ iteration: number; artifact_hash: string }>;
  mlflow_links: Array<{ iteration: number; mlflow_run_id: string }>;
  promoted_version: Promotion | null;
  rollback_target: string | null;
  smoke_status: Record<string, unknown> | null;
  paper_status: unknown;
}

export interface SystemStatus {
  active_sessions: number;
  max_concurrent: number;
  sessions: Array<{ id: string; instrument: string; model_type: string; status: string }>;
}

export interface InstrumentInfo {
  name: string;
  instrument: string;
  timeframe: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  skill: string;
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

/** Trigger a browser file download from an API endpoint. */
async function triggerDownload(url: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition');
  let filename = 'download';
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match) filename = match[1];
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

export const api = {
  // Research sessions
  startResearch: (req: StartResearchRequest) =>
    request<ResearchSession>('/research/start', { method: 'POST', body: JSON.stringify(req) }),

  listSessions: () => request<ResearchSession[]>('/research'),

  getSession: (id: string) => request<ResearchSession>(`/research/${id}`),

  stopSession: (id: string) => request<void>(`/research/${id}/stop`, { method: 'POST' }),

  pauseSession: (id: string) => request<void>(`/research/${id}/pause`, { method: 'POST' }),

  resumeSession: (id: string) => request<void>(`/research/${id}/resume`, { method: 'POST' }),

  continueSession: (id: string, body?: { max_iterations?: number; focus_hint?: string; timeout_minutes?: number }) =>
    request<ResearchSession>(`/research/${id}/continue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }),

  deleteSession: (id: string) => request<void>(`/research/${id}`, { method: 'DELETE' }),

  // Results
  getResults: (id: string) => request<{ session: ResearchSession; iterations: Iteration[] }>(`/research/${id}/results`),

  getIterations: (id: string) => request<Iteration[]>(`/research/${id}/iterations`),

  getBestIteration: (id: string) => request<Iteration>(`/research/${id}/best`),

  getHpoStudies: (id: string) => request<{ hpo_studies: HpoStudy[] }>(`/research/${id}/hpo-studies`),

  getResearchState: (id: string) => request<ResearchState>(`/research/${id}/state`),

  getAgentLog: (id: string) =>
    request<{ entries: AgentLogEntry[]; total_lines: number; resolved_research_id?: string | null }>(
      `/research/${id}/agent-log?format=json`
    ),

  // Promotions
  previewPromotion: (id: string) => request<PromotionPreview>(`/research/${id}/promote/preview`, { method: 'POST' }),

  confirmPromotion: (id: string) => request<Promotion>(`/research/${id}/promote/confirm`, { method: 'POST' }),

  listPromotions: () => request<Promotion[]>('/promotions'),

  // Downloads (trigger browser file save)
  downloadConfig: (id: string) =>
    triggerDownload(`${BASE}/research/${id}/download/config`),

  downloadAgentLog: (id: string) =>
    triggerDownload(`${BASE}/research/${id}/download/agent-log`),

  downloadResults: (id: string) =>
    triggerDownload(`${BASE}/research/${id}/download/results`),

  // Meta
  getInstruments: () => request<InstrumentInfo[]>('/instruments'),

  getModels: () => request<ModelInfo[]>('/models'),

  getStatus: () => request<SystemStatus>('/status'),
};
