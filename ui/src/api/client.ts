const BASE = '/api/v1';
const API_TOKEN_STORAGE_KEY = 'autoresearch.apiToken';

export interface ResearchSession {
  id: string;
  instrument: string;
  timeframe: string;
  model_type: string;
  /** P3-014: canonical skill fields (dual-shape, §10 guarantee #4). */
  skill_id?: string;
  subject_id?: string;
  variant?: string;
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
  effective_iteration_count?: number | null;
  resumed_from: string | null;
  current_phase?: string | null;
  next_action?: string | null;
  phase_state_json?: string | null;
  active_phase_session_id?: string | null;
  promotion_blocked_phase?: string | null;
  promotion_blockers?: string[];
  promotion_preview?: Record<string, unknown> | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
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
  training_gates_passed?: boolean;
  all_gates_passed: boolean;
  consistency_report_passed?: boolean;
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
  feature_readiness_metrics?: Record<string, number>;
  rl_economic_replay?: Record<string, unknown> | null;
  attempt_snapshot?: Record<string, unknown> | null;
  // ML-59: HPO search phase
  search_phase: string | null;
  /** P3-015/016: canonical skill fields (dual-shape, §10 guarantee #4). */
  skill_id?: string;
  skill_phase?: string | null;
  evidence_keys?: string[];
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
  line_number?: number;
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
  scope?: PromotionScope;
  metadata_path?: string | null;
  promotion_metadata?: Record<string, unknown> | null;
  rolled_back_at?: string | null;
  promoted_at: string;
}

export type PromotionScope = 'development' | 'paper' | 'canary' | 'production';

export interface PromotionApproval {
  approver?: string;
  reason?: string;
  method?: string;
  signature?: string;
  approved?: boolean;
  /** v2 candidate binding: the exact preview the signature covers. */
  iteration?: number;
  config_snapshot_sha256?: string;
  target_identity?: string;
}

export interface PromotionPreviewRequest {
  scope: PromotionScope;
  approval?: PromotionApproval | null;
}

export interface PromotionScopeRequest {
  scope: PromotionScope;
  approval?: PromotionApproval | null;
}

export interface PromotionPreview {
  research_id: string;
  iteration: number;
  model_type?: string;
  instrument?: string;
  timeframe?: string;
  /** P3-017: canonical skill fields + promotion target kind discriminator. */
  skill_id?: string;
  subject_id?: string;
  variant?: string;
  target_kind?: string;
  scope?: PromotionScope;
  promotion_scope?: PromotionScope;
  promotion_allowed?: boolean;
  scope_promotion_allowed?: boolean;
  target_path: string;
  new_config: string;
  current_config: string | null;
  /** v2 approval candidate: sign these exact values for production confirm. */
  config_snapshot_sha256?: string;
  target_identity?: string;
  best_metric?: number | null;
  training_gates_passed?: boolean;
  gates_passed?: boolean;
  development_gate_bundle_passed?: boolean;
  consistency_report_passed?: boolean;
  gate_bundle_evaluation?: PromotionGateEvaluation | null;
  consistency_report?: ConsistencyReport | null;
  development_promotion_metadata?: Record<string, unknown> | null;
  scoped_promotion_metadata?: ScopedPromotionMetadata | null;
  promotion_metadata?: Record<string, unknown> | null;
  scope_gate_evaluation?: PromotionGateEvaluation | null;
}

export interface PromotionGateCheck {
  name: string;
  status: string;
  reason?: string | null;
  details?: unknown;
}

export interface PromotionGateEvaluation {
  scope?: string;
  passed?: boolean;
  blockers?: string[];
  checks?: PromotionGateCheck[];
}

export interface ScopedPromotionMetadata {
  schema_version?: string;
  scope?: PromotionScope;
  promotion_allowed?: boolean;
  blockers?: string[];
  checks?: PromotionGateCheck[];
  required_prior_scopes?: PromotionScope[];
  prior_promotions?: Record<string, unknown>;
  decision_chain?: Array<Record<string, unknown>>;
  approval?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  rollback_target?: string | null;
  rollback_targets?: Record<string, unknown>;
}

export interface StartResearchRequest {
  /** Canonical skill shape; legacy instrument/timeframe/model_type aliases
   *  are still accepted by the server for old clients. */
  skill_id?: string;
  subject_id?: string;
  variant?: string;
  skill_params?: Record<string, unknown>;
  tag?: string;
  quick_mode?: boolean;
  max_iterations?: number;
  max_budget_usd?: number;
  timeout_minutes?: number;
  focus_hint?: string;
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
  research_outcome?: string | null;
  terminal_reason?: string | null;
  current_phase: string | null;
  next_action: string | null;
  phase_state: {
    schema_version?: string;
    research_id?: string;
    model_type?: string;
    generated_at?: string;
    current_phase: string | null;
    next_action: string | null;
    blocked: boolean;
    block_reason: string | null;
    all_phases_complete?: boolean;
    iterations_in_current_phase?: number;
    stalled_iterations?: number;
    phases: Array<{
      id: string;
      label: string;
      status: string;
      next_action: string;
      min_iterations?: number;
      max_iterations?: number;
    }>;
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
  production_operations?: ProductionOperations | null;
  /** AR-8: last-known artifact values from iteration metrics_json.
   *  Used as fallback panel content when the primary source (a confirmed
   *  promotions record) is null. Each entry is {value, iteration}. */
  latest_known_artifacts?: {
    rollback_target?: { value: string; iteration: number };
    smoke_status?: { value: Record<string, unknown>; iteration: number };
  } | null;
}

export interface ProductionOperations {
  schema_version: string;
  research_id: string;
  model_type: string;
  candidate: ProductionCandidate | null;
  promotion: {
    blocked: boolean;
    blockers: string[];
    blocker_details: BlockerDetail[];
    latest_scope?: PromotionScope | null;
    latest_record?: CompactPromotion | null;
    scopes: PromotionScopeStatus[];
  };
  warnings: ProductionWarning[];
  rl_profit: RlProfitSummary;
  feature_readiness: FeatureReadinessSummary;
  oos_provenance: OosProvenanceSummary;
  inference_parity: InferenceParitySummary;
  rollback: RollbackStatusSummary;
  audit_events: ProductionAuditEvent[];
}

export interface ProductionCandidate {
  iteration: number;
  primary_metric: number | null;
  metric_name: string | null;
  training_gates_passed?: boolean;
  all_gates_passed: boolean;
  decision?: string | null;
  search_phase?: string | null;
  config_snapshot_sha256?: string | null;
  attempt_snapshot_hash?: string | null;
  artifact_hash?: string | null;
  mlflow_run_id?: string | null;
}

export interface BlockerDetail {
  code: string;
  label: string;
}

export interface CompactPromotion {
  id?: number;
  scope?: PromotionScope;
  research_id?: string;
  iteration?: number;
  target_path?: string;
  metadata_path?: string | null;
  promoted_at?: string;
  rolled_back_at?: string | null;
  promotion_allowed?: boolean | null;
  rollback_target?: string | null;
}

export interface PromotionScopeStatus {
  scope: PromotionScope;
  status: string;
  ready: boolean;
  requires_approval: boolean;
  required_prior_scopes: PromotionScope[];
  blockers: string[];
  blocker_details: BlockerDetail[];
  promotion?: CompactPromotion | null;
}

export interface ProductionWarning {
  code: string;
  severity: string;
  message: string;
  details?: unknown;
}

export interface RlProfitSummary {
  status: string;
  score?: number | null;
  missing?: string[];
  metrics?: Record<string, number>;
  artifact_path?: string | null;
  artifact_hash?: string | null;
  schema_version?: string | null;
}

export interface FeatureReadinessChannel {
  status: string;
  passed: boolean;
  metrics: Record<string, number>;
  details?: Record<string, unknown>;
}

export interface FeatureReadinessSummary {
  status: string;
  direction?: FeatureReadinessChannel;
  volatility?: FeatureReadinessChannel;
}

export interface OosProvenanceSummary {
  status: string;
  required: boolean;
  blockers: string[];
  blocker_details?: BlockerDetail[];
  feature_bundle_hash?: string | null;
  nested_validation?: boolean;
  multi_seed?: boolean;
  direction?: Record<string, unknown>;
  volatility?: Record<string, unknown>;
  details?: Record<string, unknown>;
}

export interface InferenceParitySummary {
  status: string;
  passed: boolean;
  failed_checks: string[];
  details?: Record<string, unknown>;
}

export interface RollbackStatusSummary {
  status: string;
  target?: string | null;
  readiness?: Record<string, unknown>;
  rolled_back_at?: string | null;
}

export interface ProductionAuditEvent {
  event_id?: string;
  timestamp?: string;
  actor_id?: string;
  action?: string;
  outcome?: string;
  research_id?: string | null;
  pipeline_id?: string | null;
  scope?: string | null;
  error_message?: string | null;
}

export interface SystemStatus {
  active_sessions: number;
  max_concurrent: number;
  sessions: Array<{ id: string; instrument: string; model_type: string; status: string }>;
}

export interface ModelInfo {
  id: string;
  name: string;
  skill: string;
}

// ── Skill API types (ARC-011 P3-001..011) ──────────────────────────────

export interface SkillSummary {
  id: string;
  version: string;
  category: string;
  display_name: string;
  description: string;
  schema_version: string;
  /** Legacy alias — empty string for non-ML skills (§10 guarantee #5). */
  model_type: string;
  has_subjects: boolean;
  has_variants: boolean;
}

// ── Skill generation (P2 Skill SDK — `autoresearch new-skill` parity) ──

export interface PolicyFinding {
  severity: 'critical' | 'warning' | string;
  reason: string;
  location: string;
}

export interface GeneratedSkillDraft {
  skill_id: string;
  draft_dir: string;
  files: string[];
  lifecycle_state: 'draft';
  policy_findings: PolicyFinding[];
  next: string;
}

// ── Cost estimate (P2 ops — POST /research/estimate-cost) ──────────────

export interface CostEstimate {
  per_iteration_usd: number;
  total_usd: number;
  uncapped_total_usd: number;
  capped_by_budget: boolean;
  max_budget_usd: number | null;
  assumptions: Record<string, number>;
}

export interface FormField {
  name: string;
  type: string;
  description?: string;
  default?: unknown;
  min?: number;
  max?: number;
  enum?: string[];
  options_url?: string;
  visible_when?: { field: string; equals: string };
  required?: boolean;
}

export interface MetricColumn {
  field: string;
  label: string;
  kind?: string;
  axis?: 'left' | 'right';
  format?: string;
}

export interface MetricSchema {
  primary: { field: string; label: string; direction: string; format?: string };
  gates: MetricColumn[];
  chart_series: MetricColumn[];
  iteration_table_columns: MetricColumn[];
  goal: string;
}

export interface SubjectInfo {
  id: string;
  label: string;
}

// ── Leaderboard types (P0-4) ──────────────────────────────────────────

export interface LeaderboardEntry {
  research_id: string;
  subject_id: string | null;
  variant: string | null;
  tag: string | null;
  status: string;
  best_metric: number | null;
  metric_name: string | null;
  best_iteration: number | null;
  iterations: number;
  total_api_cost_usd: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface SkillLeaderboard {
  skill_id: string;
  metric: { field: string; label: string; direction: string; format: string };
  items: LeaderboardEntry[];
  total: number;
}

export function getAutoresearchApiToken(): string | null {
  const envToken = import.meta.env.VITE_AUTORESEARCH_API_TOKEN as string | undefined;
  if (envToken?.trim()) return envToken.trim();
  try {
    const storedToken = localStorage.getItem(API_TOKEN_STORAGE_KEY);
    return storedToken?.trim() || null;
  } catch {
    return null;
  }
}

export function hasBuildTimeAutoresearchApiToken(): boolean {
  const envToken = import.meta.env.VITE_AUTORESEARCH_API_TOKEN as string | undefined;
  return Boolean(envToken?.trim());
}

export function setAutoresearchApiToken(token: string): void {
  localStorage.setItem(API_TOKEN_STORAGE_KEY, token.trim());
}

export function clearAutoresearchApiToken(): void {
  localStorage.removeItem(API_TOKEN_STORAGE_KEY);
}

function base64UrlEncode(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function getAutoresearchWebSocketProtocols(): string[] | undefined {
  const token = getAutoresearchApiToken();
  if (!token) return undefined;
  return [`autoresearch.token.${base64UrlEncode(token)}`];
}

function withAuthHeaders(headers?: HeadersInit, includeJson = false): Headers {
  const merged = new Headers(headers);
  if (includeJson && !merged.has('Content-Type')) {
    merged.set('Content-Type', 'application/json');
  }
  const token = getAutoresearchApiToken();
  if (token) {
    merged.set('Authorization', `Bearer ${token}`);
  }
  return merged;
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: withAuthHeaders(opts?.headers, true),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export function normalizeListResponse<T>(
  payload: T[] | PaginatedResponse<T>,
): T[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

/** Trigger a browser file download from an API endpoint. */
async function triggerDownload(url: string): Promise<void> {
  const res = await fetch(url, { headers: withAuthHeaders() });
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

function makeIdempotencyKey(scope: string, id: string): string {
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${scope}:${id}:${random}`;
}

export const api = {
  // Research sessions
  startResearch: (req: StartResearchRequest) =>
    request<ResearchSession>('/research/start', { method: 'POST', body: JSON.stringify(req) }),

  // P2 ops: expected-cost preview (server-side estimator — same pricing as
  // the post-call ledger; replaces the old $0.24×iters UI heuristic).
  estimateCost: (req: { max_iterations: number; quick_mode: boolean; max_budget_usd?: number }) =>
    request<CostEstimate>('/research/estimate-cost', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  listSessions: async () =>
    normalizeListResponse(
      await request<ResearchSession[] | PaginatedResponse<ResearchSession>>(
        '/research',
      ),
    ),

  listSessionsPage: (limit: number, offset: number) =>
    request<PaginatedResponse<ResearchSession>>(`/research?limit=${limit}&offset=${offset}`),

  getSession: (id: string) => request<ResearchSession>(`/research/${id}`),

  stopSession: (id: string) => request<void>(`/research/${id}/stop`, { method: 'POST' }),

  pauseSession: (id: string) => request<void>(`/research/${id}/pause`, { method: 'POST' }),

  resumeSession: (id: string) => request<void>(`/research/${id}/resume`, { method: 'POST' }),

  continueSession: (id: string, body?: { max_iterations?: number; focus_hint?: string; timeout_minutes?: number }) =>
    request<ResearchSession>(`/research/${id}/continue`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': makeIdempotencyKey('continue', id),
      },
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
  previewPromotion: (id: string, body?: PromotionPreviewRequest) =>
    request<PromotionPreview>(`/research/${id}/promote/preview`, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),

  confirmPromotion: (id: string, body?: PromotionScopeRequest) =>
    request<Promotion>(`/research/${id}/promote/confirm`, {
      method: 'POST',
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        // P1-3: idempotent confirm — a retried promotion must not double-deliver.
        'Idempotency-Key': makeIdempotencyKey('promote-confirm', id),
      },
      body: body ? JSON.stringify(body) : undefined,
    }),

  listPromotions: () => request<Promotion[]>('/promotions'),

  // Downloads (trigger browser file save)
  downloadConfig: (id: string) =>
    triggerDownload(`${BASE}/research/${id}/download/config`),

  downloadAgentLog: (id: string) =>
    triggerDownload(`${BASE}/research/${id}/download/agent-log`),

  downloadResults: (id: string) =>
    triggerDownload(`${BASE}/research/${id}/download/results`),

  // Meta
  getModels: () => request<ModelInfo[]>('/models'),

  getStatus: () => request<SystemStatus>('/status'),

  // Skills (ARC-011 P3-001..008)
  getSkills: (category?: string) =>
    request<SkillSummary[]>(`/skills${category ? `?category=${category}` : ''}`),

  getSkill: (id: string) => request<Record<string, unknown>>(`/skills/${id}`),

  getSkillFormFields: (id: string) =>
    request<{ skill_id: string; form_fields: FormField[] }>(`/skills/${id}/form-fields`),

  getSkillMetricSchema: (id: string) =>
    request<MetricSchema>(`/skills/${id}/metric-schema`),

  getSkillVersions: (id: string) =>
    request<{
      skill_id: string;
      versions: Array<{
        version: string;
        schema_version: string;
        current: boolean;
        tagged?: boolean;
      }>;
      tags?: string[];
    }>(`/skills/${id}/versions`),

  // Skill generation (P2 Skill SDK) — drafts only; promotion is an operator
  // act via the CLI (`autoresearch promote-skill`).
  generateSkill: (body: { goal: string; skill_id?: string }) =>
    request<GeneratedSkillDraft>('/skills/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  // Leaderboard (P0-4)
  getSkillLeaderboard: (id: string, limit = 20) =>
    request<SkillLeaderboard>(`/skills/${encodeURIComponent(id)}/leaderboard?limit=${limit}`),

  reloadSkills: () =>
    request<{ status: string; reloaded: number; available: string[] }>('/skills/reload', { method: 'POST' }),

  // Subjects (ARC-011 P3-009, P3-010)
  getSubjects: (skillId: string) =>
    request<SubjectInfo[]>(`/subjects?skill_id=${encodeURIComponent(skillId)}`),

  getSubjectVariants: (subjectId: string, skillId: string) =>
    request<{ skill_id: string; subject_id: string; variants: string[] }>(
      `/subjects/${encodeURIComponent(subjectId)}/variants?skill_id=${encodeURIComponent(skillId)}`,
    ),
};
