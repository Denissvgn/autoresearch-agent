// Promote wizard — 3-step stepper:
//   1. Review winner
//   2. Review diff
//   3. Scope & confirm
// Wired to previewPromotion / confirmPromotion. Design ported from
// hifi/screen-promote.jsx.
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useConfirmPromotion, usePreviewPromotion, useSession } from '../hooks/useResearch';
import {
  PromotionGateCheck,
  PromotionPreview,
  PromotionScope,
} from '../api/client';
import { Icon, Stat, StatusBadge } from '../components/hifi/primitives';

interface ScopeOption {
  id: PromotionScope;
  label: string;
  risk: 'low' | 'med' | 'high';
  desc: string;
  icon: string;
}

const SCOPES: ScopeOption[] = [
  { id: 'development', label: 'development', risk: 'low', desc: 'Internal sandbox; no external impact.', icon: 'flask' },
  { id: 'paper', label: 'paper', risk: 'low', desc: 'Shadow runner; mirrors production observations.', icon: 'book' },
  { id: 'canary', label: 'canary', risk: 'med', desc: 'Limited live deployment with auto-rollback gates.', icon: 'bolt' },
  { id: 'production', label: 'production', risk: 'high', desc: 'Full production roll-out. Fail-closed delegated.', icon: 'server' },
];

export default function Promote() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: session } = useSession(id!);
  const previewMut = usePreviewPromotion();
  const confirmMut = useConfirmPromotion();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [scope, setScope] = useState<PromotionScope>('development');
  const [diffMode, setDiffMode] = useState<'unified' | 'split'>('unified');

  // Lazily fetch preview when session is known.
  const [preview, setPreview] = useState<PromotionPreview | null>(null);
  useEffect(() => {
    if (!id) return;
    previewMut.mutate(
      { id, request: { scope } },
      { onSuccess: (data) => setPreview(data) },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, scope]);

  const checks: PromotionGateCheck[] = preview?.gate_bundle_evaluation?.checks ?? [];
  const blockers = preview?.gate_bundle_evaluation?.blockers ?? [];
  const passed = preview?.gate_bundle_evaluation?.passed ?? preview?.training_gates_passed ?? false;

  return (
    <div className="col gap-5" style={{ padding: 24 }}>
      <div className="col gap-2">
        <div className="crumb">
          <Link to="/">Dashboard</Link>
          <Icon name="chevR" size={12} />
          <Link to={`/research/${id}`}>
            <span className="mono">#{id?.slice(0, 8)}</span>
          </Link>
          <Icon name="chevR" size={12} />
          <span>Promote config</span>
        </div>
        <h1 className="h1">Promote winning config</h1>
        {session && (
          <div className="row gap-2" style={{ fontSize: 13 }}>
            <span className="mono">{session.instrument}</span>
            <span className="faint">·</span>
            <span className="mono">{session.timeframe}</span>
            <span className="pill pill--ghost">{session.model_type}</span>
            <StatusBadge s={session.status} />
          </div>
        )}
      </div>

      <Stepper step={step} />

      {step === 1 && (
        <Step1
          preview={preview}
          loading={previewMut.isPending}
          onBack={() => navigate(`/research/${id}`)}
          onNext={() => setStep(2)}
        />
      )}
      {step === 2 && (
        <Step2
          preview={preview}
          diffMode={diffMode}
          onDiffMode={setDiffMode}
          checks={checks}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      )}
      {step === 3 && (
        <Step3
          scope={scope}
          onScope={setScope}
          targetPath={preview?.target_path}
          allowed={preview?.scope_promotion_allowed ?? preview?.promotion_allowed ?? passed}
          blockers={blockers}
          confirming={confirmMut.isPending}
          onBack={() => setStep(2)}
          onConfirm={() =>
            confirmMut.mutate(
              { id: id!, request: { scope } },
              {
                onSuccess: () => navigate(`/history`),
              },
            )
          }
        />
      )}
    </div>
  );
}

function Stepper({ step }: { step: 1 | 2 | 3 }) {
  const items = ['Review winner', 'Review diff', 'Scope & confirm'];
  return (
    <div className="row gap-3">
      {items.map((label, i) => {
        const n = (i + 1) as 1 | 2 | 3;
        const state = step === n ? 'is-active' : step > n ? 'is-done' : '';
        return (
          <div
            key={label}
            className="row gap-3"
            style={{ flex: 1, opacity: state === '' ? 0.6 : 1 }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                background:
                  state === 'is-active' ? 'var(--fg)' : state === 'is-done' ? 'var(--green)' : 'var(--surface-2)',
                color:
                  state === 'is-active' ? 'var(--bg)' : state === 'is-done' ? 'var(--bg)' : 'var(--muted)',
                display: 'grid',
                placeItems: 'center',
                fontFamily: 'IBM Plex Mono, monospace',
                fontSize: 12,
                fontWeight: 600,
                border: '1px solid var(--line)',
              }}
            >
              {state === 'is-done' ? <Icon name="check" size={12} /> : n}
            </div>
            <div className="col gap-1">
              <span className="label">step {n}</span>
              <span style={{ fontSize: 13, fontWeight: state === 'is-active' ? 600 : 500 }}>{label}</span>
            </div>
            {i < items.length - 1 && <div className="grow divider" style={{ alignSelf: 'center', margin: 0 }} />}
          </div>
        );
      })}
    </div>
  );
}

function Step1({
  preview,
  loading,
  onBack,
  onNext,
}: {
  preview: PromotionPreview | null;
  loading: boolean;
  onBack: () => void;
  onNext: () => void;
}) {
  if (loading || !preview) {
    return <div className="placeholder" style={{ height: 200 }}>computing preview…</div>;
  }
  const metric = preview.best_metric;
  const passedCount = preview.gate_bundle_evaluation?.checks?.filter((c) => c.status === 'passed').length ?? 0;
  const totalChecks = preview.gate_bundle_evaluation?.checks?.length ?? 0;
  return (
    <div className="col gap-4">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <div className="card" style={{ padding: 16 }}>
          <Stat label="winning iter" value={`#${preview.iteration}`} />
        </div>
        <div className="card" style={{ padding: 16 }}>
          <Stat label="best metric" value={metric != null ? metric.toFixed(4) : '—'} />
        </div>
        <div className="card" style={{ padding: 16 }}>
          <Stat
            label="gates"
            value={`${passedCount}/${totalChecks || '—'}`}
            sub={preview.gate_bundle_evaluation?.passed ? 'all passing' : 'see step 2'}
          />
        </div>
        <div className="card" style={{ padding: 16 }}>
          <Stat label="target path" valueSize="sm" value={<span className="mono">{preview.target_path.split('/').slice(-1)[0]}</span>} />
        </div>
      </div>
      <div className="card" style={{ padding: 16 }}>
        <span className="label">candidate summary</span>
        <div className="code" style={{ marginTop: 10 }}>
          <span className="key">research_id</span> = <span className="str">{preview.research_id}</span>{'\n'}
          <span className="key">iteration</span> = <span className="num">{preview.iteration}</span>{'\n'}
          <span className="key">target</span> = <span className="str">{preview.target_path}</span>{'\n'}
          <span className="key">scope</span> = <span className="str">{preview.scope ?? preview.promotion_scope ?? 'development'}</span>
        </div>
      </div>
      <Footer back={{ label: 'Cancel', onClick: onBack }} next={{ label: 'Review diff', onClick: onNext }} />
    </div>
  );
}

function Step2({
  preview,
  diffMode,
  onDiffMode,
  checks,
  onBack,
  onNext,
}: {
  preview: PromotionPreview | null;
  diffMode: 'unified' | 'split';
  onDiffMode: (m: 'unified' | 'split') => void;
  checks: PromotionGateCheck[];
  onBack: () => void;
  onNext: () => void;
}) {
  const lines = useMemo(() => buildDiff(preview?.current_config ?? '', preview?.new_config ?? ''), [preview]);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 16 }}>
      <div className="card">
        <div className="card__head">
          <div className="card__title mono">{preview?.target_path || '—'}</div>
          <span className="grow" />
          <span className="subtle" style={{ fontSize: 11 }}>
            {lines.filter((l) => l.kind === 'add').length} added · {lines.filter((l) => l.kind === 'del').length} removed
          </span>
          <div className="btn-group" style={{ marginLeft: 12 }}>
            <div className={`seg ${diffMode === 'unified' ? 'on' : ''}`} onClick={() => onDiffMode('unified')}>
              unified
            </div>
            <div className={`seg ${diffMode === 'split' ? 'on' : ''}`} onClick={() => onDiffMode('split')}>
              split
            </div>
          </div>
        </div>
        <div className="code scroll" style={{ maxHeight: 520, fontSize: 12 }}>
          {lines.length === 0 ? (
            <span className="dim">no diff</span>
          ) : (
            lines.map((line, i) => (
              <div key={i} className={`diff-row ${line.kind === 'add' ? 'diff-add' : line.kind === 'del' ? 'diff-del' : 'diff-ctx'}`}>
                <span className="ln">{line.ln}</span>
                <span className="sg">{line.kind === 'add' ? '+' : line.kind === 'del' ? '-' : ' '}</span>
                <span className="ct">{line.text}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="col gap-3">
        <div className="card" style={{ padding: 14 }}>
          <span className="label">risk checks</span>
          <div className="col gap-2" style={{ marginTop: 10 }}>
            {checks.length === 0 ? (
              <span className="subtle">No gate checks reported.</span>
            ) : (
              checks.map((c) => (
                <div key={c.name} className="row gap-2" style={{ justifyContent: 'space-between' }}>
                  <span className="mono" style={{ fontSize: 12 }}>{c.name}</span>
                  <span
                    className={`pill ${c.status === 'passed' || c.status === 'ok' ? 'pill--green' : c.status === 'warn' || c.status === 'warning' ? 'pill--amber' : 'pill--red'}`}
                  >
                    <span className="dot" />
                    {c.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
        {preview?.consistency_report && (
          <div className="card" style={{ padding: 14 }}>
            <span className="label">consistency</span>
            <div className="row gap-2" style={{ marginTop: 10 }}>
              <span className={`pill ${preview.consistency_report.passed ? 'pill--green' : 'pill--red'}`}>
                <span className="dot" />
                {preview.consistency_report.passed ? 'passed' : 'blocked'}
              </span>
              <span className="subtle mono" style={{ fontSize: 11 }}>
                {preview.consistency_report.schema_version}
              </span>
            </div>
            {preview.consistency_report.blockers.length > 0 && (
              <div className="code" style={{ marginTop: 10 }}>
                {preview.consistency_report.blockers.map((b) => (
                  <div key={b}><span className="err">! {b}</span></div>
                ))}
              </div>
            )}
          </div>
        )}
        <div style={{ gridColumn: '1 / -1' }} />
        <Footer back={{ label: 'Back', onClick: onBack }} next={{ label: 'Choose scope', onClick: onNext }} />
      </div>
    </div>
  );
}

function Step3({
  scope,
  onScope,
  targetPath,
  allowed,
  blockers,
  confirming,
  onBack,
  onConfirm,
}: {
  scope: PromotionScope;
  onScope: (s: PromotionScope) => void;
  targetPath?: string;
  allowed: boolean;
  blockers: string[];
  confirming: boolean;
  onBack: () => void;
  onConfirm: () => void;
}) {
  return (
    <div style={{ maxWidth: 920, width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
        {SCOPES.map((s) => {
          const on = scope === s.id;
          return (
            <button
              type="button"
              key={s.id}
              onClick={() => onScope(s.id)}
              className="card"
              style={{
                padding: 16,
                textAlign: 'left',
                background: on ? 'var(--surface-2)' : 'var(--surface)',
                borderColor: on ? 'var(--fg)' : 'var(--line-soft)',
                cursor: 'pointer',
                display: 'flex',
                gap: 12,
                alignItems: 'flex-start',
              }}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  border: '2px solid var(--line)',
                  marginTop: 2,
                  background: on ? 'var(--fg)' : 'transparent',
                  flexShrink: 0,
                }}
              />
              <div className="col gap-1 grow">
                <div className="row gap-2">
                  <Icon name={s.icon} />
                  <span className="mono" style={{ fontWeight: 600 }}>{s.label}</span>
                  <span className={`pill ${s.risk === 'low' ? 'pill--green' : s.risk === 'med' ? 'pill--amber' : 'pill--red'}`}>
                    <span className="dot" />
                    {s.risk}
                  </span>
                </div>
                <span className="subtle" style={{ fontSize: 12 }}>{s.desc}</span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="card" style={{ padding: 14 }}>
        <span className="label">target path</span>
        <div className="mono" style={{ marginTop: 6, wordBreak: 'break-all' }}>
          {targetPath || '—'}
        </div>
      </div>

      {scope === 'production' && (
        <div className="banner banner--amber">
          <Icon name="info" />
          Production scope is fail-closed and delegated. Confirmation triggers a downstream audit
          gate; rollback target is captured automatically.
        </div>
      )}

      {!allowed && (
        <div className="banner banner--red">
          <Icon name="info" />
          <div className="col gap-1">
            <span style={{ fontWeight: 600 }}>This scope is currently blocked.</span>
            {blockers.length > 0 && (
              <span className="mono" style={{ fontSize: 11 }}>{blockers.join(' · ')}</span>
            )}
          </div>
        </div>
      )}

      <div className="row" style={{ justifyContent: 'space-between' }}>
        <button className="btn btn--ghost" onClick={onBack}>
          <Icon name="chev" /> Back
        </button>
        <button
          className="btn btn--solid"
          disabled={!allowed || confirming}
          onClick={onConfirm}
        >
          {confirming ? 'Confirming…' : 'Confirm promotion'}
          <Icon name="check" size={12} />
        </button>
      </div>
    </div>
  );
}

function Footer({
  back,
  next,
}: {
  back: { label: string; onClick: () => void };
  next: { label: string; onClick: () => void };
}) {
  return (
    <div className="row" style={{ justifyContent: 'space-between' }}>
      <button className="btn btn--ghost" onClick={back.onClick}>
        {back.label}
      </button>
      <button className="btn btn--solid" onClick={next.onClick}>
        {next.label}
        <Icon name="arrR" size={12} />
      </button>
    </div>
  );
}

// Naive line-by-line diff. Sufficient for surfacing config changes; the
// actual schema rules live server-side.
interface DiffLine {
  ln: number;
  kind: 'add' | 'del' | 'ctx';
  text: string;
}

function buildDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText ? oldText.split('\n') : [];
  const newLines = newText ? newText.split('\n') : [];
  const max = Math.max(oldLines.length, newLines.length);
  const out: DiffLine[] = [];
  let lnOld = 0;
  let lnNew = 0;
  for (let i = 0; i < max; i += 1) {
    const o = oldLines[i];
    const n = newLines[i];
    if (o === undefined && n !== undefined) {
      lnNew += 1;
      out.push({ ln: lnNew, kind: 'add', text: n });
    } else if (n === undefined && o !== undefined) {
      lnOld += 1;
      out.push({ ln: lnOld, kind: 'del', text: o });
    } else if (o !== n) {
      lnOld += 1;
      lnNew += 1;
      out.push({ ln: lnOld, kind: 'del', text: o ?? '' });
      out.push({ ln: lnNew, kind: 'add', text: n ?? '' });
    } else {
      lnOld += 1;
      lnNew += 1;
      out.push({ ln: lnNew, kind: 'ctx', text: o ?? '' });
    }
  }
  return out;
}
