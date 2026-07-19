// New research wizard — 720px centered layout per hifi/screen-new.jsx.
// Skill-aware: uses SkillPicker (P3-021) + DynamicFormFields (P3-022) when
// skills are available from GET /skills; falls back to legacy model-type
// selector + hardcoded instrument/timeframe for backward compat.
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useInstruments, useModels, useStartResearch, useSkills, useSkillFormFields } from '../hooks/useResearch';
import { Field, Icon, Segmented } from '../components/hifi/primitives';
import SkillPicker from '../components/SkillPicker';
import DynamicFormFields from '../components/DynamicFormFields';
import type { SkillSummary, FormField } from '../api/client';

const TIMEFRAMES = ['5m', '15m', '1h', '4h'];

interface ModelCard {
  id: string;
  name: string;
  desc: string;
  icon: string;
}

const FALLBACK_MODELS: ModelCard[] = [
  { id: 'direction', name: 'direction', desc: 'Up/down classifier with calibration', icon: 'arrU' },
  { id: 'volatility', name: 'volatility', desc: 'ATR breakout / regime detector', icon: 'bolt' },
  { id: 'rl', name: 'rl', desc: 'PPO agent for execution policy', icon: 'flask' },
];

const FOCUS_EXAMPLES = [
  'temporal stability',
  'lower drawdown',
  'reduce overtrading',
];

export default function NewResearch() {
  const navigate = useNavigate();
  const startMut = useStartResearch();
  const { data: instruments } = useInstruments();
  const { data: models } = useModels();

  const [instrument, setInstrument] = useState('');
  const [timeframe, setTimeframe] = useState('15m');
  const [modelType, setModelType] = useState('direction');
  const [tag, setTag] = useState('');
  const [focusHint, setFocusHint] = useState('');
  const [maxIterations, setMaxIterations] = useState(30);
  const [maxBudget, setMaxBudget] = useState(10);
  const [timeoutMinutes, setTimeoutMinutes] = useState(120);
  const [quickMode, setQuickMode] = useState(false);
  // RL knobs
  const [tradingMode, setTradingMode] = useState<'stock' | 'margin'>('stock');
  const [agentStrategy, setAgentStrategy] = useState<'AGGR' | 'CONS' | 'BALA' | 'SCAL'>('BALA');
  const [initialBalance, setInitialBalance] = useState(10000);

  // P3-021 / P3-022: skill-aware form state.
  const { data: skills } = useSkills();
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const { data: skillFormFieldsData } = useSkillFormFields(selectedSkillId);
  const [skillParams, setSkillParams] = useState<Record<string, unknown>>({});
  const skillFormFields: FormField[] = skillFormFieldsData?.form_fields ?? [];

  // Sync modelType from the selected skill's legacy alias.
  useEffect(() => {
    if (!selectedSkillId || !skills) return;
    const skill = skills.find((s) => s.id === selectedSkillId);
    if (skill?.model_type) {
      setModelType(skill.model_type);
    }
  }, [selectedSkillId, skills]);

  // When form fields include instrument/timeframe, sync them into the legacy state.
  useEffect(() => {
    if (skillFormFields.length === 0) return;
    const instrumentField = skillFormFields.find((f) => f.name === 'instrument' || f.name === 'subject_id');
    const timeframeField = skillFormFields.find((f) => f.name === 'timeframe' || f.name === 'variant');
    if (instrumentField) {
      const val = skillParams[instrumentField.name];
      if (typeof val === 'string' && val) setInstrument(val);
    }
    if (timeframeField) {
      const val = skillParams[timeframeField.name];
      if (typeof val === 'string' && val) setTimeframe(val);
    }
  }, [skillFormFields, skillParams]);

  const instrumentOptions = useMemo(() => {
    const seen = new Set<string>();
    return (instruments ?? [])
      .map((inst) => inst.instrument.trim())
      .filter((name) => {
        if (!name || seen.has(name)) return false;
        seen.add(name);
        return true;
      });
  }, [instruments]);

  const modelCards: ModelCard[] = useMemo(() => {
    if (models && models.length > 0) {
      return models.map((m) => ({
        id: m.id,
        name: m.name,
        desc: m.skill || m.id,
        icon: m.id === 'rl' || m.id.startsWith('pipeline') ? 'flask' : m.id === 'volatility' ? 'bolt' : 'arrU',
      }));
    }
    return FALLBACK_MODELS;
  }, [models]);

  // Cheap estimates surfaced in the preview row.
  const estRuntime = useMemo(() => {
    const perIter = quickMode ? 2 : 6; // minutes
    const total = maxIterations * perIter;
    const h = Math.floor(total / 60);
    const m = total % 60;
    return h ? `~${h}h ${m}m` : `~${m}m`;
  }, [maxIterations, quickMode]);
  const estCost = useMemo(() => Math.min(maxBudget, maxIterations * (quickMode ? 0.04 : 0.24)), [maxIterations, maxBudget, quickMode]);

  const isRlLike = modelType === 'rl' || modelType.startsWith('pipeline');

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    if (!instrument) return;
    startMut.mutate(
      {
        instrument,
        timeframe,
        model_type: modelType,
        // P3-013: canonical skill fields (dual-shape — both shapes sent).
        skill_id: selectedSkillId ?? undefined,
        subject_id: instrument || undefined,
        variant: timeframe || undefined,
        skill_params: Object.keys(skillParams).length > 0 ? skillParams : undefined,
        tag: tag || undefined,
        quick_mode: quickMode,
        max_iterations: maxIterations,
        max_budget_usd: maxBudget,
        timeout_minutes: timeoutMinutes,
        focus_hint: focusHint || undefined,
        ...(isRlLike
          ? {
              trading_mode: tradingMode,
              agent_strategy: agentStrategy,
              initial_balance: initialBalance,
            }
          : {}),
      },
      { onSuccess: (session) => navigate(`/research/${session.id}`) },
    );
  };

  return (
    <div style={{ display: 'grid', placeItems: 'start center', padding: '32px 24px' }}>
      <div style={{ width: 720, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div className="col gap-1">
          <div className="crumb">
            <Link to="/">Dashboard</Link>
            <Icon name="chevR" size={12} />
            <span>New research</span>
          </div>
          <h1 className="h1">Start a new research session</h1>
          <p className="subtle" style={{ maxWidth: 540, lineHeight: 1.5 }}>
            Configure the instrument and target model. The agent will explore configs, evaluate
            gates, and surface promotable candidates.
          </p>
        </div>

        <form onSubmit={handleStart} className="col gap-4">
          {/* Required card */}
          <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div className="col gap-1">
                <span className="label">required</span>
                <h2 className="h2">Target</h2>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
              {skillFormFields.length > 0 ? (
                /* P3-022: dynamic form fields from the selected skill's manifest */
                <div style={{ gridColumn: '1 / -1' }}>
                  <DynamicFormFields
                    fields={skillFormFields}
                    values={skillParams}
                    onChange={(name, value) => setSkillParams((prev) => ({ ...prev, [name]: value }))}
                    skillId={selectedSkillId ?? undefined}
                  />
                </div>
              ) : (
                <>
                  <Field label="Instrument" required>
                    {instrumentOptions.length > 0 ? (
                      <select className="select mono" value={instrument} onChange={(e) => setInstrument(e.target.value)} required>
                        <option value="">Select…</option>
                        {instrumentOptions.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="input mono"
                        value={instrument}
                        onChange={(e) => setInstrument(e.target.value)}
                        placeholder="e.g. DOGE_USDT"
                        required
                      />
                    )}
                  </Field>
                  <Field label="Timeframe" required>
                    <Segmented options={TIMEFRAMES} value={timeframe} onChange={setTimeframe} />
                  </Field>
                </>
              )}
            </div>

            {/* P3-021: skill picker replaces the hardcoded model-type selector. */}
            {skills && skills.length > 0 ? (
              <Field label="Skill" required>
                <SkillPicker
                  skills={skills}
                  selected={selectedSkillId}
                  onSelect={(id) => {
                    setSelectedSkillId(id);
                    setSkillParams({});
                  }}
                />
              </Field>
            ) : (
              <Field label="Model type" required>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${modelCards.length}, 1fr)`, gap: 12 }}>
                  {modelCards.map((m) => {
                    const on = modelType === m.id;
                    return (
                      <button
                        type="button"
                        key={m.id}
                        onClick={() => setModelType(m.id)}
                        className="card"
                        style={{
                          padding: 14,
                          textAlign: 'left',
                          background: on ? 'var(--surface-2)' : 'var(--surface)',
                          borderColor: on ? 'var(--fg)' : 'var(--line-soft)',
                          cursor: 'pointer',
                        }}
                      >
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
                          <Icon name={m.icon} color={on ? 'var(--fg)' : 'var(--muted)'} />
                          {on && <Icon name="check" color="var(--green)" />}
                        </div>
                        <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                          {m.name}
                        </div>
                        <div className="subtle" style={{ fontSize: 11, marginTop: 4 }}>
                          {m.desc}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </Field>
            )}
          </div>

          {/* Optional card */}
          <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div className="col gap-1">
              <span className="label">optional</span>
              <h2 className="h2">Shape the search</h2>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="Tag">
                <input className="input mono" value={tag} onChange={(e) => setTag(e.target.value)} placeholder="e.g. sweep-lr" />
              </Field>
              <Field label="Max iterations" help={`hard cap at ${maxIterations}`}>
                <input
                  className="input mono"
                  type="number"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(Number(e.target.value))}
                  min={1}
                  max={500}
                />
              </Field>
            </div>

            <Field label="Focus hint" help="Direction for the agent's exploration.">
              <textarea
                className="textarea"
                rows={2}
                value={focusHint}
                onChange={(e) => setFocusHint(e.target.value)}
                placeholder="e.g. Improve temporal stability without inflating turnover."
              />
              <div className="row gap-2" style={{ marginTop: 6 }}>
                {FOCUS_EXAMPLES.map((ex) => (
                  <button
                    type="button"
                    key={ex}
                    className="btn btn--ghost btn--sm"
                    onClick={() => setFocusHint(ex)}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </Field>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="Max budget (USD)">
                <input
                  className="input mono"
                  type="number"
                  value={maxBudget}
                  onChange={(e) => setMaxBudget(Number(e.target.value))}
                  min={1}
                  max={500}
                  step={0.5}
                />
              </Field>
              <Field label="Timeout (min)">
                <input
                  className="input mono"
                  type="number"
                  value={timeoutMinutes}
                  onChange={(e) => setTimeoutMinutes(Number(e.target.value))}
                  min={30}
                  max={1440}
                  step={30}
                />
              </Field>
            </div>

            <label className={`check ${quickMode ? 'on' : ''}`}>
              <span className="check__box" onClick={() => setQuickMode(!quickMode)} />
              <span>Quick mode (fewer iterations, reduced sample size)</span>
            </label>

            {isRlLike && (
              <div
                className="card card--raised"
                style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}
              >
                <span className="label">rl environment</span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                  <Field label="Market">
                    <select
                      className="select mono"
                      value={tradingMode}
                      onChange={(e) => setTradingMode(e.target.value as 'stock' | 'margin')}
                    >
                      <option value="stock">stock (no leverage)</option>
                      <option value="margin">margin (3x)</option>
                    </select>
                  </Field>
                  <Field label="Strategy">
                    <select
                      className="select mono"
                      value={agentStrategy}
                      onChange={(e) => setAgentStrategy(e.target.value as 'AGGR' | 'CONS' | 'BALA' | 'SCAL')}
                    >
                      <option value="BALA">balanced</option>
                      <option value="AGGR">aggressive</option>
                      <option value="CONS">conservative</option>
                      <option value="SCAL">scalping</option>
                    </select>
                  </Field>
                  <Field label="Initial balance ($)">
                    <input
                      className="input mono"
                      type="number"
                      value={initialBalance}
                      onChange={(e) => setInitialBalance(Number(e.target.value))}
                      min={100}
                      max={1000000}
                      step={1000}
                    />
                  </Field>
                </div>
              </div>
            )}
          </div>

          {/* Preview row */}
          <div
            className="card card--raised"
            style={{
              padding: 16,
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
            }}
          >
            <PreviewItem label="estimated runtime" value={estRuntime} />
            <PreviewItem label="estimated cost" value={`~$${estCost.toFixed(2)}`} />
            <PreviewItem label="iteration cap" value={`${maxIterations}`} />
            <PreviewItem label="mode" value={quickMode ? 'quick' : 'standard'} />
          </div>

          {/* Actions */}
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => navigate('/')}
            >
              Cancel
            </button>
            <div className="row gap-2">
              <button type="button" className="btn btn--ghost" disabled>
                Save as draft
              </button>
              <button
                type="submit"
                className="btn btn--solid"
                disabled={startMut.isPending || !instrument}
              >
                {startMut.isPending ? 'Starting…' : 'Start research'}
                <Icon name="arrR" size={12} />
              </button>
            </div>
          </div>
          {startMut.isError && (
            <div className="banner banner--red">{(startMut.error as Error).message}</div>
          )}
        </form>
      </div>
    </div>
  );
}

function PreviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="col gap-1">
      <span className="label">{label}</span>
      <span className="mono" style={{ fontSize: 14, color: 'var(--fg)' }}>
        {value}
      </span>
    </div>
  );
}
