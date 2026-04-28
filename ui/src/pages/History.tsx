import { Link } from 'react-router-dom';
import { useSessions, usePromotions } from '../hooks/useResearch';
import StatusBadge from '../components/StatusBadge';

export default function History() {
  const { data: sessions, isLoading } = useSessions();
  const { data: promotions } = usePromotions();

  const completed = sessions?.filter((s) => s.status !== 'running' && s.status !== 'paused') ?? [];

  return (
    <div className="max-w-5xl space-y-8">
      <h1 className="text-xl font-semibold">History</h1>

      {/* Past sessions */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">Past Sessions</h2>
        {isLoading ? (
          <div className="text-gray-500 text-sm">Loading...</div>
        ) : completed.length === 0 ? (
          <div className="text-gray-500 text-sm">No completed sessions.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-left">
                  <th className="py-2 px-3">Instrument</th>
                  <th className="py-2 px-3">Model</th>
                  <th className="py-2 px-3">TF</th>
                  <th className="py-2 px-3">Tag</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3">Iters</th>
                  <th className="py-2 px-3">Best</th>
                  <th className="py-2 px-3">Cost</th>
                  <th className="py-2 px-3">Duration</th>
                </tr>
              </thead>
              <tbody>
                {completed.map((s) => {
                  const dur = s.completed_at
                    ? Math.round((new Date(s.completed_at).getTime() - new Date(s.started_at).getTime()) / 60000)
                    : null;
                  return (
                    <tr key={s.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                      <td className="py-2 px-3">
                        <Link to={`/research/${s.id}`} className="text-indigo-400 hover:underline">
                          {s.instrument}
                        </Link>
                      </td>
                      <td className="py-2 px-3 text-gray-400">{s.model_type}</td>
                      <td className="py-2 px-3 text-gray-500">{s.timeframe}</td>
                      <td className="py-2 px-3 text-gray-500 text-xs">{s.tag || '—'}</td>
                      <td className="py-2 px-3"><StatusBadge status={s.status} /></td>
                      <td className="py-2 px-3 font-mono">{s.best_iteration ?? '—'}</td>
                      <td className="py-2 px-3 font-mono">
                        {s.best_metric != null ? s.best_metric.toFixed(4) : '—'}
                      </td>
                      <td className="py-2 px-3 font-mono">${(s.total_api_cost_usd ?? 0).toFixed(2)}</td>
                      <td className="py-2 px-3 text-gray-500 text-xs">
                        {dur != null ? `${dur}m` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Promotions */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">Config Promotions</h2>
        {!promotions || promotions.length === 0 ? (
          <div className="text-gray-500 text-sm">No promotions yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-left">
                  <th className="py-2 px-3">Research</th>
                  <th className="py-2 px-3">Iteration</th>
                  <th className="py-2 px-3">Target</th>
                  <th className="py-2 px-3">Promoted At</th>
                </tr>
              </thead>
              <tbody>
                {promotions.map((p) => (
                  <tr key={p.id} className="border-b border-gray-800">
                    <td className="py-2 px-3">
                      <Link to={`/research/${p.research_id}`} className="text-indigo-400 hover:underline font-mono text-xs">
                        {p.research_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="py-2 px-3 font-mono">{p.iteration}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-400">{p.target_path}</td>
                    <td className="py-2 px-3 text-gray-500 text-xs">
                      {new Date(p.promoted_at).toLocaleString()}
                    </td>
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
