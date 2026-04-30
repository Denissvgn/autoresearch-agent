const colors: Record<string, string> = {
  running: 'bg-green-500/20 text-green-400 border-green-500/30',
  paused: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  timed_out: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  phase_failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  promotion_blocked: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  stopped: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  pending: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = colors[status] ?? colors.pending;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border ${cls}`}>
      {status}
    </span>
  );
}
