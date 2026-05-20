import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useSessions, useSessionsPage, useStatus } from '../hooks/useResearch';
import StatusBadge from '../components/StatusBadge';

const PAGE = 50;

export default function Dashboard() {
  const [offset, setOffset] = useState(0);
  const { data: allSessions } = useSessions();
  const { data: page, isLoading } = useSessionsPage(PAGE, offset);
  const { data: status } = useStatus();

  // Filter States
  const [filterInstrument, setFilterInstrument] = useState('');
  const [filterModel, setFilterModel] = useState('');
  const [filterTag, setFilterTag] = useState('');

  const active = allSessions?.filter((s) => s.status === 'running' || s.status === 'paused') ?? [];
  const rawRecent = page?.items ?? [];
  
  const recent = rawRecent.filter((s) => {
    const matchInst = !filterInstrument || s.instrument.toLowerCase().includes(filterInstrument.toLowerCase());
    const matchModel = !filterModel || s.model_type === filterModel;
    const matchTag = !filterTag || (s.tag && s.tag.toLowerCase().includes(filterTag.toLowerCase()));
    return matchInst && matchModel && matchTag;
  });

  const total = page?.total ?? 0;
  const hasMore = total > offset + PAGE;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Status bar */}
      <div className="flex items-center gap-6">
        <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
          <div className="text-xs text-gray-500">Active Sessions</div>
          <div className="text-2xl font-mono">
            {status?.active_sessions ?? 0}
            <span className="text-gray-600 text-sm">/{status?.max_concurrent ?? '—'}</span>
          </div>
        </div>
        <Link
          to="/research/new"
          className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition"
        >
          + New Research
        </Link>
      </div>

      {/* Active sessions */}
      {active.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">Active Sessions</h2>
          <div className="grid gap-3">
            {active.map((s) => (
              <Link
                key={s.id}
                to={`/research/${s.id}`}
                className="bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-indigo-500/50 transition block"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{s.instrument}</span>
                    <span className="text-gray-500 ml-2">{s.model_type}</span>
                    <span className="text-gray-600 ml-2 text-sm">{s.timeframe}</span>
                    {s.tag && <span className="text-gray-600 ml-2 text-xs">#{s.tag}</span>}
                  </div>
                  <StatusBadge status={s.status} />
                </div>
                <div className="mt-2 flex gap-4 text-xs text-gray-500">
                  {s.best_iteration != null && <span>Iteration #{s.best_iteration}</span>}
                  {s.best_metric != null && (
                    <span>Best: {s.best_metric.toFixed(4)} @ #{s.best_iteration}</span>
                  )}
                  <span>${(s.total_api_cost_usd ?? 0).toFixed(2)}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Recent */}
      <section>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <h2 className="text-sm font-medium text-gray-400">
            Recent Sessions
            {total > 0 && <span className="text-gray-600 ml-2 font-normal">({total})</span>}
          </h2>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              placeholder="Search instrument..."
              value={filterInstrument}
              onChange={(e) => setFilterInstrument(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-indigo-500 w-36"
            />
            <select
              value={filterModel}
              onChange={(e) => setFilterModel(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-indigo-500"
            >
              <option value="">All models</option>
              <option value="direction">Direction</option>
              <option value="volatility">Volatility</option>
              <option value="rl">RL</option>
              <option value="pipeline">Pipeline</option>
            </select>
            <input
              type="text"
              placeholder="Filter tag..."
              value={filterTag}
              onChange={(e) => setFilterTag(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 outline-none focus:border-indigo-500 w-28"
            />
            {(filterInstrument || filterModel || filterTag) && (
              <button
                onClick={() => { setFilterInstrument(''); setFilterModel(''); setFilterTag(''); }}
                className="text-xs text-gray-500 hover:text-gray-300 transition"
              >
                Clear
              </button>
            )}
          </div>
        </div>
        {isLoading ? (
          <div className="text-gray-500 text-sm">Loading...</div>
        ) : recent.length === 0 ? (
          <div className="border border-dashed border-gray-700 rounded-lg px-6 py-10 text-center">
            <p className="text-gray-500 text-sm">No research sessions yet.</p>
            <Link
              to="/research/new"
              className="mt-3 inline-block px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-medium transition"
            >
              Start your first session
            </Link>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-400 text-left">
                    <th className="py-2 px-3">Instrument</th>
                    <th className="py-2 px-3">Model</th>
                    <th className="py-2 px-3">Tag</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3">Iterations</th>
                    <th className="py-2 px-3">Best</th>
                    <th className="py-2 px-3">Cost</th>
                    <th className="py-2 px-3">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((s) => (
                    <tr key={s.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                      <td className="py-2 px-3">
                        <Link to={`/research/${s.id}`} className="text-indigo-400 hover:underline">
                          {s.instrument}
                        </Link>
                      </td>
                      <td className="py-2 px-3 text-gray-400">{s.model_type}</td>
                      <td className="py-2 px-3 text-gray-500 text-xs">{s.tag || '—'}</td>
                      <td className="py-2 px-3"><StatusBadge status={s.status} /></td>
                      <td className="py-2 px-3 font-mono">{s.best_iteration ?? '—'}</td>
                      <td className="py-2 px-3 font-mono">
                        {s.best_metric != null ? s.best_metric.toFixed(4) : '—'}
                      </td>
                      <td className="py-2 px-3 font-mono">${(s.total_api_cost_usd ?? 0).toFixed(2)}</td>
                      <td className="py-2 px-3 text-gray-500 text-xs">
                        {new Date(s.started_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {hasMore && (
              <div className="mt-3 text-center">
                <button
                  onClick={() => setOffset((o) => o + PAGE)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded text-sm text-gray-300 transition"
                >
                  Load more ({total - offset - PAGE} remaining)
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
