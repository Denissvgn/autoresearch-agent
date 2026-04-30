import type { FeatureReadinessChannel, ProductionOperations, ResearchState } from '../api/client';
import {
  blockerLabels,
  formatMetric,
  productionReady,
  scopeSummary,
  toneClasses,
  toneForStatus,
  warningTone,
} from '../utils/productionOps';

interface Props {
  state?: ResearchState;
}

function StatusPill({ status }: { status?: string | null }) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded border px-2 py-0.5 text-[11px] font-medium ${toneClasses(toneForStatus(status))}`}>
      {status ? status.replace(/_/g, ' ') : 'unknown'}
    </span>
  );
}

function metricGrid(metrics?: Record<string, unknown>) {
  const entries = Object.entries(metrics ?? {});
  if (entries.length === 0) return <div className="text-xs text-gray-500">No metrics recorded</div>;
  return (
    <div className="grid grid-cols-2 gap-2 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="border border-gray-800 bg-gray-950 px-2 py-1.5">
          <div className="text-gray-500">{key.replace(/_/g, ' ')}</div>
          <div className="font-mono text-gray-200">{formatMetric(value)}</div>
        </div>
      ))}
    </div>
  );
}

function FeatureChannel({ label, channel }: { label: string; channel?: FeatureReadinessChannel }) {
  return (
    <div className="border border-gray-800 bg-gray-900/60 px-3 py-2">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="text-xs font-medium text-gray-300">{label}</div>
        <StatusPill status={channel?.status ?? 'missing'} />
      </div>
      {metricGrid(channel?.metrics)}
    </div>
  );
}

function OperationsEmpty() {
  return (
    <div className="border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-gray-500">
      Production operations state is not available yet.
    </div>
  );
}

export default function ProductionOpsPanel({ state }: Props) {
  const ops = state?.production_operations;
  if (!ops) return <OperationsEmpty />;

  const blockerText = blockerLabels(ops.promotion.blockers, ops.promotion.blocker_details);
  const warnings = ops.warnings ?? [];

  return (
    <div className="space-y-4 text-sm">
      <div className={`border px-4 py-3 ${productionReady(ops) ? 'border-emerald-800 bg-emerald-950/20' : ops.promotion.blocked ? 'border-red-900 bg-red-950/20' : 'border-gray-800 bg-gray-900/70'}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Production Operations</h2>
            <div className="mt-1 text-xs text-gray-500">
              Candidate #{ops.candidate?.iteration ?? '-'} · {ops.model_type} · {ops.candidate?.metric_name ?? 'metric'} {formatMetric(ops.candidate?.primary_metric)}
            </div>
          </div>
          <StatusPill status={productionReady(ops) ? 'production_ready' : ops.promotion.blocked ? 'blocked' : 'development_scope'} />
        </div>
        {blockerText.length > 0 && (
          <div className="mt-3 border border-red-900/70 bg-red-950/30 px-3 py-2 text-xs text-red-100">
            <div className="font-medium text-red-200">Promotion blockers</div>
            <ul className="mt-1 space-y-1">
              {blockerText.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase text-gray-500">Promotion Scope Status</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          {ops.promotion.scopes.map((scope) => {
            const summary = scopeSummary(scope);
            return (
              <div key={scope.scope} className={`border px-3 py-2 ${toneClasses(summary.tone)}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">{summary.label}</div>
                  <span className="text-[11px]">{scope.status.replace(/_/g, ' ')}</span>
                </div>
                <div className="mt-2 text-xs opacity-90">{summary.message}</div>
                {scope.promotion?.promoted_at && (
                  <div className="mt-2 text-[11px] opacity-75">
                    {new Date(scope.promotion.promoted_at).toLocaleString()}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <section className="border border-gray-800 bg-gray-900 px-4 py-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">RL Economic Replay</h3>
            <StatusPill status={ops.rl_profit.status} />
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="border border-gray-800 bg-gray-950 px-2 py-1.5">
              <div className="text-gray-500">profit score</div>
              <div className="font-mono text-gray-200">{formatMetric(ops.rl_profit.score)}</div>
            </div>
            {Object.entries(ops.rl_profit.metrics ?? {}).map(([key, value]) => (
              <div key={key} className="border border-gray-800 bg-gray-950 px-2 py-1.5">
                <div className="text-gray-500">{key.replace(/_/g, ' ')}</div>
                <div className="font-mono text-gray-200">{formatMetric(value)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 space-y-1 text-xs">
            <div>
              <span className="text-gray-500">Artifact: </span>
              <span className="font-mono text-gray-300 break-all">{ops.rl_profit.artifact_path ?? '-'}</span>
            </div>
            <div>
              <span className="text-gray-500">Hash: </span>
              <span className="font-mono text-gray-300 break-all">{ops.rl_profit.artifact_hash ?? '-'}</span>
            </div>
          </div>
        </section>

        <section className="border border-gray-800 bg-gray-900 px-4 py-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Supervised Feature Readiness</h3>
            <StatusPill status={ops.feature_readiness.status} />
          </div>
          <div className="space-y-3">
            <FeatureChannel label="Direction" channel={ops.feature_readiness.direction} />
            <FeatureChannel label="Volatility" channel={ops.feature_readiness.volatility} />
          </div>
        </section>

        <section className="border border-gray-800 bg-gray-900 px-4 py-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">OOS And Provenance</h3>
            <StatusPill status={ops.oos_provenance.status} />
          </div>
          {ops.oos_provenance.required ? (
            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div className="border border-gray-800 bg-gray-950 px-2 py-1.5">
                  <div className="text-gray-500">nested validation</div>
                  <div className="font-mono text-gray-200">{formatMetric(ops.oos_provenance.nested_validation)}</div>
                </div>
                <div className="border border-gray-800 bg-gray-950 px-2 py-1.5">
                  <div className="text-gray-500">multi seed</div>
                  <div className="font-mono text-gray-200">{formatMetric(ops.oos_provenance.multi_seed)}</div>
                </div>
              </div>
              <div>
                <span className="text-gray-500">Feature bundle: </span>
                <span className="font-mono text-gray-300 break-all">{ops.oos_provenance.feature_bundle_hash ?? '-'}</span>
              </div>
              {ops.oos_provenance.blockers.length > 0 && (
                <ul className="space-y-1 text-red-200">
                  {blockerLabels(ops.oos_provenance.blockers, ops.oos_provenance.blocker_details).map((blocker) => (
                    <li key={blocker}>{blocker}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <div className="text-xs text-gray-500">Not required for this model type.</div>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="border border-gray-800 bg-gray-900 px-4 py-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Inference Parity</h3>
            <StatusPill status={ops.inference_parity.status} />
          </div>
          {ops.inference_parity.failed_checks.length > 0 ? (
            <ul className="space-y-1 text-xs text-red-200">
              {ops.inference_parity.failed_checks.map((check) => (
                <li key={check}>{check.replace(/_/g, ' ')}</li>
              ))}
            </ul>
          ) : (
            <div className="text-xs text-gray-500">No failed checks recorded.</div>
          )}
        </section>

        <section className="border border-gray-800 bg-gray-900 px-4 py-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Rollback Target</h3>
            <StatusPill status={ops.rollback.status} />
          </div>
          <div className="font-mono text-xs text-gray-300 break-all">{ops.rollback.target ?? '-'}</div>
        </section>

        <section className="border border-gray-800 bg-gray-900 px-4 py-3">
          <h3 className="mb-3 text-sm font-semibold">Warnings</h3>
          {warnings.length === 0 ? (
            <div className="text-xs text-gray-500">No active warnings.</div>
          ) : (
            <div className="space-y-2">
              {warnings.slice(0, 4).map((warning) => (
                <div key={warning.code} className={`border px-2 py-1.5 text-xs ${toneClasses(warningTone(warning))}`}>
                  {warning.message}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="border border-gray-800 bg-gray-900 px-4 py-3">
        <h3 className="mb-3 text-sm font-semibold">Audit Events</h3>
        {ops.audit_events.length === 0 ? (
          <div className="text-xs text-gray-500">No audit events recorded for this session.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-500">
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Action</th>
                  <th className="py-2 pr-3">Scope</th>
                  <th className="py-2 pr-3">Outcome</th>
                  <th className="py-2 pr-3">Actor</th>
                </tr>
              </thead>
              <tbody>
                {ops.audit_events.map((event) => (
                  <tr key={event.event_id ?? `${event.timestamp}-${event.action}`} className="border-b border-gray-800">
                    <td className="py-2 pr-3 text-gray-500">{event.timestamp ? new Date(event.timestamp).toLocaleString() : '-'}</td>
                    <td className="py-2 pr-3 text-gray-300">{event.action ?? '-'}</td>
                    <td className="py-2 pr-3 font-mono text-gray-400">{event.scope ?? '-'}</td>
                    <td className="py-2 pr-3"><StatusPill status={event.outcome ?? 'unknown'} /></td>
                    <td className="py-2 pr-3 font-mono text-gray-500">{event.actor_id ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
