import { useState } from 'react';
import { usePreviewPromotion, useConfirmPromotion } from '../hooks/useResearch';
import type { PromotionPreview } from '../api/client';
import ConfigDiff from './ConfigDiff';

interface Props {
  researchId: string;
  onClose: () => void;
}

export default function PromotionModal({ researchId, onClose }: Props) {
  const [preview, setPreview] = useState<PromotionPreview | null>(null);
  const previewMut = usePreviewPromotion();
  const confirmMut = useConfirmPromotion();

  const handlePreview = () => {
    previewMut.mutate(researchId, { onSuccess: (data: PromotionPreview) => setPreview(data) });
  };

  const handleConfirm = () => {
    confirmMut.mutate(researchId, { onSuccess: () => onClose() });
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-gray-800 border border-gray-700 rounded-lg p-6 max-w-3xl w-full mx-4 max-h-[80vh] overflow-auto"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">Promote Config</h2>

        {!preview ? (
          <div className="space-y-4">
            <p className="text-gray-400 text-sm">
              Preview the config that will be promoted from the best iteration of this research session.
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
            <div className="text-sm text-gray-400">
              Target: <span className="text-gray-200 font-mono">{preview.target_path}</span>
            </div>
            <div className="text-sm text-gray-400">
              Iteration: <span className="text-gray-200">{preview.iteration}</span>
            </div>

            <ConfigDiff current={preview.current_config} proposed={preview.new_config} />

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleConfirm}
                disabled={confirmMut.isPending}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded text-sm disabled:opacity-50"
              >
                {confirmMut.isPending ? 'Promoting...' : 'Confirm Promotion'}
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
