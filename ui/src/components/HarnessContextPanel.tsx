// Run-bound harness context: evidence authority, candidate/evaluator
// context, usage quality, resume mode, and capability- and
// permission-aware lifecycle actions. Unknown cost is visibly unknown;
// unsupported controls carry their server-provided explanations.
import type { HarnessContext } from '../api/client';

interface HarnessContextPanelProps {
  context: HarnessContext;
  onAction?: (action: string) => void;
}

function costLabel(quality: HarnessContext['usage_quality']) {
  if (quality.cost_status === 'unknown') return 'cost unknown';
  const known = `$${quality.cost_known_usd.toFixed(4)} known`;
  return quality.cost_status === 'partial'
    ? `${known} + ${quality.cost_unknown_events} unknown-cost event(s)`
    : known;
}

export default function HarnessContextPanel({ context, onAction }: HarnessContextPanelProps) {
  const { harness, evidence, usage_quality: quality, lifecycle, viewer } = context;
  return (
    <section aria-label="harness context">
      <h3>Harness &amp; evidence</h3>
      <dl>
        <dt>harness</dt>
        <dd data-testid="ctx-harness">
          {harness.name} ({harness.version}, {harness.contract_version})
        </dd>
        <dt>resume mode</dt>
        <dd data-testid="ctx-resume-mode">{context.resume_mode}</dd>
        <dt>verified evidence</dt>
        <dd data-testid="ctx-evidence">
          {evidence.verified
            ? `verified (${evidence.authority_counts.receipt_verified ?? 0})`
            : 'no verified evidence yet'}
          {evidence.imported > 0 ? ` · imported: ${evidence.imported}` : ''}
          {evidence.authority_counts.model_proposed
            ? ` · model-proposed: ${evidence.authority_counts.model_proposed}`
            : ''}
        </dd>
        <dt>candidate / evaluator</dt>
        <dd data-testid="ctx-candidate">
          {(() => {
            const evaluator = context.candidate_evaluator_context.evaluator;
            const digest = context.candidate_evaluator_context.candidate_digest;
            if (!evaluator && !digest) return 'no evaluator context recorded';
            return [evaluator && `evaluator: ${evaluator}`, digest && `candidate: ${digest}`]
              .filter(Boolean)
              .join(' · ');
          })()}
        </dd>
        <dt>usage quality</dt>
        <dd data-testid="ctx-usage">{costLabel(quality)}</dd>
      </dl>
      <h4>Lifecycle</h4>
      <div role="group" aria-label="lifecycle actions">
        {lifecycle.actions.map((action) => (
          <button
            key={action.action}
            type="button"
            data-testid={`lifecycle-${action.action}`}
            disabled={!action.enabled}
            title={action.reason || undefined}
            onClick={() => onAction?.(action.action)}
          >
            {action.action}
            {!action.enabled && (
              <span data-testid={`lifecycle-${action.action}-reason`}> — {action.reason}</span>
            )}
          </button>
        ))}
      </div>
      <p data-testid="ctx-viewer">
        viewer: {viewer.kind} ({viewer.permissions.join(', ')})
      </p>
    </section>
  );
}