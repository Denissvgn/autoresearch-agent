import { useState } from 'react';
import { usePreviewPromotion, useConfirmPromotion } from '../hooks/useResearch';
import type {
  ProductionOperations,
  PromotionApproval,
  PromotionPreview,
  PromotionScope,
  PromotionScopeRequest,
} from '../api/client';
import {
  blockerLabels,
  scopeLabel,
  scopeSummary,
  toneClasses,
  toneForStatus,
} from '../utils/productionOps';
import ConfigDiff from './ConfigDiff';

interface Props {
  researchId: string;
  operations?: ProductionOperations | null;
  onClose: () => void;
}

const SCOPES: PromotionScope[] = ['development', 'paper', 'canary', 'production'];

function requestFor(scope: PromotionScope, approval: PromotionApproval): PromotionScopeRequest {
  const cleanedApproval: PromotionApproval | null = scope === 'development'
    ? null
    : {
        approver: approval.approver?.trim() || undefined,
        reason: approval.reason?.trim() || undefined,
        method: approval.method?.trim() || 'manual',
        signature: approval.signature?.trim() || undefined,
        approved: true,
      };
  return { scope, approval: cleanedApproval };
}

function blockerText(preview: PromotionPreview): string[] {
  const gateBlockers = preview.scope_gate_evaluation?.blockers
    ?? preview.gate_bundle_evaluation?.blockers
    ?? preview.scoped_promotion_metadata?.blockers
    ?? [];
  return blockerLabels(gateBlockers);
}

export default function PromotionModal({ researchId, operations, onClose }: Props) {
  const [preview, setPreview] = useState<PromotionPreview | null>(null);
  const [scope, setScope] = useState<PromotionScope>('development');
  const [approval, setApproval] = useState<PromotionApproval>({ method: 'manual' });
  const previewMut = usePreviewPromotion();
  const confirmMut = useConfirmPromotion();
  const selectedScopeStatus = operations?.promotion.scopes.find((item) => item.scope === scope);
  const selectedSummary = selectedScopeStatus ? scopeSummary(selectedScopeStatus) : null;
  const approvalRequired = scope !== 'development';
  const approvalReady = !approvalRequired || Boolean(approval.approver?.trim() && (approval.reason?.trim() || approval.signature?.trim()));
  const canConfirmPreview = Boolean(preview?.promotion_allowed) && approvalReady;

  const handlePreview = () => {
    previewMut.mutate(
      { id: researchId, request: requestFor(scope, approval) },
      { onSuccess: (data: PromotionPreview) => setPreview(data) }
    );
  };

  const handleConfirm = () => {
    confirmMut.mutate(
      { id: researchId, request: requestFor(scope, approval) },
      { onSuccess: () => onClose() }
    );
  };

  const updateScope = (nextScope: PromotionScope) => {
    setScope(nextScope);
    setPreview(null);
    previewMut.reset();
    confirmMut.reset();
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[85vh] overflow-auto"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Promote Config</h2>
            <p className="mt-1 text-sm text-gray-400">
              Server-owned promotion scope: {scopeLabel(scope)}
            </p>
          </div>
          <span className={`rounded border px-2 py-1 text-xs ${toneClasses(toneForStatus(selectedScopeStatus?.status))}`}>
            {selectedScopeStatus?.status?.replace(/_/g, ' ') ?? 'not previewed'}
          </span>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-2 md:grid-cols-4">
          {SCOPES.map((item) => {
            const status = operations?.promotion.scopes.find((entry) => entry.scope === item);
            const summary = status ? scopeSummary(status) : null;
            const active = item === scope;
            return (
              <button
                key={item}
                type="button"
                onClick={() => updateScope(item)}
                className={`border px-3 py-2 text-left text-sm ${active ? 'border-indigo-500 bg-indigo-950/30' : 'border-gray-700 bg-gray-950 hover:border-gray-500'}`}
              >
                <div className="font-medium text-gray-100">{scopeLabel(item)}</div>
                <div className="mt-1 text-xs text-gray-400">{summary?.message ?? 'Preview required.'}</div>
              </button>
            );
          })}
        </div>

        {selectedSummary && selectedScopeStatus?.blockers?.length ? (
          <div className="mb-4 border border-red-900/70 bg-red-950/30 px-3 py-2 text-xs text-red-100">
            {blockerLabels(selectedScopeStatus.blockers, selectedScopeStatus.blocker_details).map((blocker) => (
              <div key={blocker}>{blocker}</div>
            ))}
          </div>
        ) : null}

        {approvalRequired && (
          <div className="mb-5 grid grid-cols-1 gap-3 border border-gray-800 bg-gray-950 p-3 md:grid-cols-2">
            <label className="text-xs text-gray-400">
              Approver
              <input
                value={approval.approver ?? ''}
                onChange={(event) => setApproval((prev) => ({ ...prev, approver: event.target.value }))}
                className="mt-1 w-full border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-gray-100 outline-none focus:border-indigo-500"
              />
            </label>
            <label className="text-xs text-gray-400">
              Reason
              <input
                value={approval.reason ?? ''}
                onChange={(event) => setApproval((prev) => ({ ...prev, reason: event.target.value }))}
                className="mt-1 w-full border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-gray-100 outline-none focus:border-indigo-500"
              />
            </label>
          </div>
        )}

        {!preview ? (
          <div className="space-y-4">
            <p className="text-gray-400 text-sm">
              Preview the best iteration against {scopeLabel(scope).toLowerCase()} readiness before confirming.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handlePreview}
                disabled={previewMut.isPending}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm disabled:opacity-50"
              >
                {previewMut.isPending ? 'Loading...' : 'Preview'}
              </button>
              <button onClick={onClose} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">
                Cancel
              </button>
            </div>
            {previewMut.isError && (
              <p className="text-red-400 text-sm">{(previewMut.error as Error).message}</p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-3">
              <div className="border border-gray-800 bg-gray-950 px-3 py-2">
                <div className="text-xs text-gray-500">Target</div>
                <div className="font-mono text-gray-200 break-all">{preview.target_path}</div>
              </div>
              <div className="border border-gray-800 bg-gray-950 px-3 py-2">
                <div className="text-xs text-gray-500">Iteration</div>
                <div className="font-mono text-gray-200">{preview.iteration}</div>
              </div>
              <div className={`border px-3 py-2 ${toneClasses(preview.promotion_allowed ? 'success' : 'danger')}`}>
                <div className="text-xs opacity-80">Preview</div>
                <div className="font-medium">{preview.promotion_allowed ? 'Ready' : 'Blocked'}</div>
              </div>
            </div>

            {blockerText(preview).length > 0 && (
              <div className="border border-red-900/70 bg-red-950/30 px-3 py-2 text-xs text-red-100">
                <div className="font-medium text-red-200">Blocked reasons</div>
                <ul className="mt-1 space-y-1">
                  {blockerText(preview).map((blocker) => (
                    <li key={blocker}>{blocker}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
              {(preview.scope_gate_evaluation?.checks ?? preview.gate_bundle_evaluation?.checks ?? []).slice(0, 8).map((check) => (
                <div key={check.name} className={`border px-2 py-1.5 ${toneClasses(toneForStatus(check.status))}`}>
                  <div className="font-medium">{check.name.replace(/_/g, ' ')}</div>
                  {check.reason && <div className="mt-1 opacity-80">{check.reason.replace(/_/g, ' ')}</div>}
                </div>
              ))}
            </div>

            <ConfigDiff current={preview.current_config} proposed={preview.new_config} />

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleConfirm}
                disabled={confirmMut.isPending || !canConfirmPreview}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded text-sm disabled:opacity-50"
              >
                {confirmMut.isPending ? 'Promoting...' : `Confirm ${scopeLabel(scope)} Promotion`}
              </button>
              <button onClick={onClose} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">
                Cancel
              </button>
            </div>
            {confirmMut.isError && (
              <p className="text-red-400 text-sm">{(confirmMut.error as Error).message}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
