// New research wizard — 720px centered layout per hifi/screen-new.jsx.
// Skill-aware: uses SkillPicker + DynamicFormFields from the selected skill's
// manifest (GET /skills); falls back to a subject/variant free-form pair.
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useModels, useStartResearch, useSkills, useSkillFormFields, useCostEstimate, useHarnesses } from '../hooks/useResearch';
import { Field, Icon } from '../components/hifi/primitives';
import SkillPicker from '../components/SkillPicker';
import DynamicFormFields from '../components/DynamicFormFields';
import HarnessPicker from '../components/HarnessPicker';

const FOCUS_EXAMPLES = [
  'improve robustness',
  'reduce overfitting',
  'explore a new dimension',
];

export default function NewResearch() {
  const navigate = useNavigate();
  const startMut = useStartResearch();
  const { data: models } = useModels();

  const [subject, setSubject] = useState('');
  const [variant, setVariant] = useState('default');
  const [tag, setTag] = useState('');
  const [focusHint, setFocusHint] = useState('');
  const [maxIterations, setMaxIterations] = useState(30);
  const [maxBudget, setMaxBudget] = useState(10);
  const [timeoutMinutes, setTimeoutMinutes] = useState(120);
  const [quickMode, setQuickMode] = useState(false);

  // P3-021 / P3-022: skill-aware form state.
  const { data: skills } = useSkills();
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const { data: skillFormFieldsData } = useSkillFormFields(selectedSkillId);
  const [skillParams, setSkillParams] = useState<Record<string, unknown>>({});
  const skillFormFields = skillFormFieldsData?.form_fields ?? [];

  // Harness selection: capability descriptors, no name branches.
  const { data: harnessesData } = useHarnesses();
  const harnessList = harnessesData?.harnesses ?? [];
  const [selectedHarness, setSelectedHarness] = useState<string | null>(null);
  const effectiveHarness = selectedHarness ?? harnessList[0]?.name ?? null;

  // Default the subject/variant to the selected skill's first enumeration.
  useEffect(() => {
    if (!selectedSkillId) return;
    setSubject((prev) => prev || 'default');
  }, [selectedSkillId]);

  // When form fields include subject/variant, sync them into the state.
  useEffect(() => {
    if (skillFormFields.length === 0) return;
    const subjectField = skillFormFields.find((f) => f.name === 'subject_id');
    const variantField = skillFormFields.find((f) => f.name === 'variant');
    if (subjectField) {
      const val = skillParams[subjectField.name];
      if (typeof val === 'string' && val) setSubject(val);
    }
    if (variantField) {
      const val = skillParams[variantField.name];
      if (typeof val === 'string' && val) setVariant(val);
    }
  }, [skillFormFields, skillParams]);

  const modelCount = useMemo(() => (models?.length ?? 0), [models]);

  // Cheap estimates surfaced in the preview row.
  const estRuntime = useMemo(() => {
    const perIter = quickMode ? 2 : 6; // minutes
    const total = maxIterations * perIter;
    const h = Math.floor(total / 60);
    const m = total % 60;
    return h ? `~${h}h ${m}m` : `~${m}m`;
  }, [maxIterations, quickMode]);
  // P2 ops: server-side estimator (same pricing as the post-call ledger),
  // replacing the old $0.24×iters client heuristic.
  const { data: costEstimate, isLoading: costLoading } = useCostEstimate(
    maxIterations, quickMode, maxBudget,
  );
  const estCostLabel = costLoading
    ? '…'
    : costEstimate
      ? `~$${costEstimate.total_usd.toFixed(2)}${costEstimate.capped_by_budget ? ' (budget-capped)' : ''}`
      : '—';

  const skillSelected = Boolean(selectedSkillId);

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    if (!skillSelected || !subject) return;
    startMut.mutate(
      {
        skill_id: selectedSkillId ?? undefined,
        subject_id: subject,
        variant,
        skill_params: Object.keys(skillParams).length > 0 ? skillParams : undefined,
        tag: tag || undefined,
        harness: effectiveHarness ?? undefined,
        quick_mode: quickMode,
        max_iterations: maxIterations,
        max_budget_usd: maxBudget,
        timeout_minutes: timeoutMinutes,
        focus_hint: focusHint || undefined,
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
            Pick a skill and set its parameters. The agent will explore configurations,
            evaluate gates, and surface promotable candidates.
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

            {/* P3-021: skill picker selects the installed skill. */}
            <Field label="Skill" required>
              <SkillPicker
                skills={skills ?? []}
                selected={selectedSkillId}
                onSelect={(id) => {
                  setSelectedSkillId(id);
                  setSkillParams({});
                }}
              />
              {modelCount === 0 && (
                <span className="subtle" style={{ fontSize: 11 }}>
                  No skills installed — add a package under skills/ and reload.
                </span>
              )}
            </Field>

            {/* Harness selection and capability/preflight diagnostics —
                rendered from API descriptors, preserving the skill-driven
                parameter forms below. */}
            {harnessList.length > 0 && (
              <HarnessPicker
                harnesses={harnessList}
                selected={effectiveHarness}
                onSelect={setSelectedHarness}
              />
            )}

            {skillFormFields.length > 0 ? (
              /* P3-022: dynamic form fields from the selected skill's manifest */
              <DynamicFormFields
                fields={skillFormFields}
                values={skillParams}
                onChange={(name, value) => setSkillParams((prev) => ({ ...prev, [name]: value }))}
                skillId={selectedSkillId ?? undefined}
              />
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
                <Field label="Subject" required help="The entity this research operates on.">
                  <input
                    className="input mono"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="e.g. default"
                    required
                  />
                </Field>
                <Field label="Variant" required>
                  <input
                    className="input mono"
                    value={variant}
                    onChange={(e) => setVariant(e.target.value)}
                    placeholder="e.g. production"
                    required
                  />
                </Field>
              </div>
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
                placeholder="e.g. Improve robustness without inflating cost."
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
            <PreviewItem label="estimated cost" value={estCostLabel} />
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
                disabled={startMut.isPending || !skillSelected || !subject}
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
