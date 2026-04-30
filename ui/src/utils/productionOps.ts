export type OpsTone = 'success' | 'warning' | 'danger' | 'info' | 'muted';
export type PromotionScopeName = 'development' | 'paper' | 'canary' | 'production';

interface BlockerDetailShape {
  code: string;
  label: string;
}

interface ProductionWarningShape {
  code: string;
  severity: string;
  message: string;
}

interface PromotionScopeStatusShape {
  scope: PromotionScopeName;
  status: string;
  ready: boolean;
  requires_approval: boolean;
  required_prior_scopes: PromotionScopeName[];
  blockers: string[];
  blocker_details: BlockerDetailShape[];
}

interface ProductionOperationsShape {
  promotion: {
    scopes: Array<{ scope: PromotionScopeName; status: string }>;
  };
}

const BLOCKER_MESSAGES: Record<string, string> = {
  candidate_gates_not_passed: 'Candidate gates have not passed.',
  development_promotion_not_allowed: 'Development promotion gates have not passed.',
  inference_reload_failed: 'Inference reload or parity validation failed.',
  missing_canary_duration: 'Canary validation duration is missing or too short.',
  missing_canary_promotion: 'A canary promotion record is required first.',
  missing_development_promotion: 'A development promotion record is required first.',
  missing_direction_feature_provenance: 'Direction feature provenance is missing.',
  missing_economic_replay: 'Economic replay evidence is missing.',
  missing_feature_readiness: 'Direction and volatility feature readiness evidence is missing.',
  missing_inference_parity: 'Inference parity evidence is missing.',
  missing_live_risk_limits: 'Production risk limits are not configured.',
  missing_model_card: 'A reviewed model card is required.',
  missing_monitoring_alerts: 'Production monitoring and alerts are not configured.',
  missing_multi_seed_rl_validation: 'Multi-seed RL validation is missing.',
  missing_nested_validation: 'Nested or blocked-time RL validation is missing.',
  missing_paper_promotion: 'A paper promotion record is required first.',
  missing_paper_validation: 'Paper trading validation evidence is missing.',
  missing_production_approval: 'Production approval is required.',
  missing_production_promotion: 'A production promotion record is required.',
  missing_rl_economic_replay: 'RL economic replay evidence is missing.',
  missing_rl_feature_bundle_hash: 'The RL feature bundle hash is missing.',
  missing_rl_oos_metrics: 'RL out-of-sample metrics are missing.',
  missing_rl_oos_provenance: 'RL OOS and feature provenance evidence is missing.',
  missing_rollback_target: 'Rollback target is missing.',
  missing_scope_approval: 'Promotion approval is required for this scope.',
  missing_volatility_feature_provenance: 'Volatility feature provenance is missing.',
  stale_or_leaked_feature_provenance: 'Feature provenance is stale or leaked.',
};

const SCOPE_LABELS: Record<PromotionScopeName, string> = {
  development: 'Development',
  paper: 'Paper',
  canary: 'Canary',
  production: 'Production',
};

export function humanizeBlocker(code: string): string {
  if (BLOCKER_MESSAGES[code]) return BLOCKER_MESSAGES[code];
  const text = code.replace(/_/g, ' ').trim();
  if (!text) return 'Unknown blocker.';
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

export function blockerLabels(blockers: string[], details?: BlockerDetailShape[]): string[] {
  const labels = new Map((details ?? []).map((detail) => [detail.code, detail.label]));
  return blockers.map((code) => labels.get(code) || humanizeBlocker(code));
}

export function scopeLabel(scope: PromotionScopeName): string {
  return SCOPE_LABELS[scope];
}

export function toneForStatus(status?: string | null): OpsTone {
  switch (status) {
    case 'passed':
    case 'promoted':
    case 'ready':
    case 'success':
    case 'production_ready':
      return 'success';
    case 'partial':
    case 'needs_approval':
    case 'warning':
    case 'development_scope':
      return 'warning';
    case 'blocked':
    case 'failed':
    case 'missing':
    case 'rolled_back':
    case 'failure':
      return 'danger';
    case 'not_applicable':
    case 'pending':
      return 'muted';
    default:
      return 'info';
  }
}

export function toneClasses(tone: OpsTone): string {
  switch (tone) {
    case 'success':
      return 'border-emerald-700/60 bg-emerald-950/30 text-emerald-200';
    case 'warning':
      return 'border-amber-700/60 bg-amber-950/30 text-amber-200';
    case 'danger':
      return 'border-red-800/70 bg-red-950/30 text-red-200';
    case 'info':
      return 'border-sky-800/60 bg-sky-950/30 text-sky-200';
    case 'muted':
    default:
      return 'border-gray-700 bg-gray-900/60 text-gray-300';
  }
}

export function scopeSummary(scope: PromotionScopeStatusShape): {
  label: string;
  tone: OpsTone;
  message: string;
  canConfirm: boolean;
} {
  const label = scopeLabel(scope.scope);
  if (scope.status === 'promoted') {
    return { label, tone: 'success', message: 'Promotion recorded.', canConfirm: false };
  }
  if (scope.status === 'ready') {
    return { label, tone: 'success', message: 'Ready to promote.', canConfirm: true };
  }
  if (scope.status === 'needs_approval') {
    return { label, tone: 'warning', message: 'Approval required before promotion.', canConfirm: true };
  }
  if (scope.status === 'blocked') {
    return { label, tone: 'danger', message: blockerLabels(scope.blockers, scope.blocker_details)[0] || 'Blocked.', canConfirm: false };
  }
  if (scope.status === 'rolled_back') {
    return { label, tone: 'danger', message: 'Latest promotion was rolled back.', canConfirm: false };
  }
  return { label, tone: 'muted', message: 'Waiting for candidate evidence.', canConfirm: false };
}

export function warningTone(warning: ProductionWarningShape): OpsTone {
  if (warning.severity === 'critical') return 'danger';
  if (warning.severity === 'warning') return 'warning';
  return 'info';
}

export function formatMetric(value: unknown): string {
  if (value == null) return '-';
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return String(value);
    return Math.abs(value) >= 10 ? value.toFixed(2) : value.toFixed(4);
  }
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  return String(value);
}

export function productionReady(ops?: ProductionOperationsShape | null): boolean {
  const production = ops?.promotion.scopes.find((scope) => scope.scope === 'production');
  return production?.status === 'promoted' || production?.status === 'ready';
}
