import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStartResearch, useInstruments, useModels } from '../hooks/useResearch';

export default function NewResearch() {
  const navigate = useNavigate();
  const startMut = useStartResearch();
  const { data: instruments } = useInstruments();
  const { data: models } = useModels();

  const [instrument, setInstrument] = useState('');
  const [timeframe, setTimeframe] = useState('15m');
  const [modelType, setModelType] = useState('direction');
  const [tag, setTag] = useState('');
  const [quickMode, setQuickMode] = useState(false);
  const [maxIterations, setMaxIterations] = useState(30);
  const [maxBudget, setMaxBudget] = useState(10);
  const [timeoutMinutes, setTimeoutMinutes] = useState(120);
  const [focusHint, setFocusHint] = useState('');
  // RL-specific fixed settings
  const [tradingMode, setTradingMode] = useState<'stock' | 'margin'>('stock');
  const [agentStrategy, setAgentStrategy] = useState<'AGGR' | 'CONS' | 'BALA' | 'SCAL'>('BALA');
  const [initialBalance, setInitialBalance] = useState(10000);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startMut.mutate(
      {
        instrument,
        timeframe,
        model_type: modelType,
        tag: tag || undefined,
        quick_mode: quickMode,
        max_iterations: maxIterations,
        max_budget_usd: maxBudget,
        timeout_minutes: timeoutMinutes,
        focus_hint: focusHint || undefined,
        ...(modelType === 'rl' || modelType === 'pipeline' ? {
          trading_mode: tradingMode,
          agent_strategy: agentStrategy,
          initial_balance: initialBalance,
        } : {}),
      },
      {
        onSuccess: (session) => navigate(`/research/${session.id}`),
      }
    );
  };

  const inputCls = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';
  const labelCls = 'block text-sm text-gray-400 mb-1';

  return (
    <div className="max-w-lg">
      <h1 className="text-xl font-semibold mb-6">New Research Session</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={labelCls}>Instrument</label>
          {instruments && instruments.length > 0 ? (
            <select value={instrument} onChange={(e) => setInstrument(e.target.value)} className={inputCls} required>
              <option value="">Select...</option>
              {instruments.map((inst) => (
                <option key={inst.name} value={inst.instrument}>{inst.instrument} ({inst.timeframe})</option>
              ))}
            </select>
          ) : (
            <input
              value={instrument}
              onChange={(e) => setInstrument(e.target.value)}
              placeholder="e.g. DOGE-USDT"
              className={inputCls}
              required
            />
          )}
        </div>

        <div>
          <label className={labelCls}>Timeframe</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={inputCls}>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
          </select>
        </div>

        <div>
          <label className={labelCls}>Model Type</label>
          {models && models.length > 0 ? (
            <select value={modelType} onChange={(e) => setModelType(e.target.value)} className={inputCls}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          ) : (
            <select value={modelType} onChange={(e) => setModelType(e.target.value)} className={inputCls}>
              <option value="direction">direction</option>
              <option value="volatility">volatility</option>
              <option value="rl">rl</option>
              <option value="pipeline">pipeline (dir→vol→rl)</option>
            </select>
          )}
        </div>

        <div>
          <label className={labelCls}>Tag (optional)</label>
          <input
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder="e.g. sweep-lr"
            className={inputCls}
          />
        </div>

        <div>
          <label className={labelCls}>Focus Hint (optional)</label>
          <textarea
            value={focusHint}
            onChange={(e) => setFocusHint(e.target.value)}
            placeholder="e.g. Focus on improving temporal stability"
            rows={2}
            className={inputCls}
          />
        </div>

        {(modelType === 'rl' || modelType === 'pipeline') && (
          <div className="border border-gray-700 rounded p-4 space-y-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">RL Environment Settings</p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className={labelCls}>Market Type</label>
                <select value={tradingMode} onChange={(e) => setTradingMode(e.target.value as 'stock' | 'margin')} className={inputCls}>
                  <option value="stock">Stock (no leverage)</option>
                  <option value="margin">Margin (3x leverage)</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Strategy</label>
                <select value={agentStrategy} onChange={(e) => setAgentStrategy(e.target.value as 'AGGR' | 'CONS' | 'BALA' | 'SCAL')} className={inputCls}>
                  <option value="BALA">Balanced (BALA)</option>
                  <option value="AGGR">Aggressive (AGGR)</option>
                  <option value="CONS">Conservative (CONS)</option>
                  <option value="SCAL">Scalping (SCAL)</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Initial Balance ($)</label>
                <input
                  type="number"
                  value={initialBalance}
                  onChange={(e) => setInitialBalance(Number(e.target.value))}
                  min={100}
                  max={1000000}
                  step={1000}
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={labelCls}>Max Iterations</label>
            <input
              type="number"
              value={maxIterations}
              onChange={(e) => setMaxIterations(Number(e.target.value))}
              min={1}
              max={500}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Max Budget ($)</label>
            <input
              type="number"
              value={maxBudget}
              onChange={(e) => setMaxBudget(Number(e.target.value))}
              min={1}
              max={500}
              step={0.5}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Timeout (min)</label>
            <input
              type="number"
              value={timeoutMinutes}
              onChange={(e) => setTimeoutMinutes(Number(e.target.value))}
              min={30}
              max={1440}
              step={30}
              className={inputCls}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="quick-mode"
            checked={quickMode}
            onChange={(e) => setQuickMode(e.target.checked)}
            className="rounded border-gray-600"
          />
          <label htmlFor="quick-mode" className="text-sm text-gray-400">
            Quick mode (fewer iterations, reduced sample size)
          </label>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={startMut.isPending || !instrument}
            className="w-full px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-medium disabled:opacity-50 transition"
          >
            {startMut.isPending ? 'Starting...' : 'Start Research'}
          </button>
          {startMut.isError && (
            <p className="text-red-400 text-sm mt-2">{(startMut.error as Error).message}</p>
          )}
        </div>
      </form>
    </div>
  );
}
