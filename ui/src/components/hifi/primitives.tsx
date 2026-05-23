// Hi-fi primitive components (ported from design-handoff/hifi/primitives.jsx)
import { CSSProperties, ReactNode } from 'react';

// ─────────────────────────────────────────────────────────────
// Icons — tiny SVG glyph set (1.5px stroke, 16px viewBox)
// ─────────────────────────────────────────────────────────────
const ICON_PATHS: Record<string, string> = {
  grid: 'M3 3h4v4H3zM9 3h4v4H9zM3 9h4v4H3zM9 9h4v4H9z',
  plus: 'M8 3v10M3 8h10',
  play: 'M5 3l8 5-8 5z',
  pause: 'M5 3h2v10H5zM9 3h2v10H9z',
  stop: 'M4 4h8v8H4z',
  check: 'M3 8.5l3 3 7-7',
  x: 'M4 4l8 8M12 4l-8 8',
  arrR: 'M3 8h10M10 5l3 3-3 3',
  arrU: 'M8 13V3M5 6l3-3 3 3',
  arrD: 'M8 3v10M5 10l3 3 3-3',
  chev: 'M5 6l3 3 3-3',
  chevR: 'M6 4l3 4-3 4',
  flask: 'M6 2v3.5L2.5 12a1.5 1.5 0 001.3 2h8.4a1.5 1.5 0 001.3-2L10 5.5V2M5 2h6',
  bolt: 'M9 1L3 9h4l-1 6 6-8H8z',
  history: 'M2 8a6 6 0 1 0 2-4.5M2 3v3h3M8 5v3l2 2',
  book: 'M3 3h7a2 2 0 0 1 2 2v8H5a2 2 0 0 1-2-2zM12 13H5',
  gear: 'M8 5.5A2.5 2.5 0 1 0 8 10.5 2.5 2.5 0 0 0 8 5.5zM8 1v2M8 13v2M14 8h-2M2 8h2M12.2 3.8l-1.4 1.4M5.2 10.8l-1.4 1.4M12.2 12.2l-1.4-1.4M5.2 5.2L3.8 3.8',
  bell: 'M3 11h10l-1.5-2V6a3.5 3.5 0 0 0-7 0v3zM6 13a2 2 0 0 0 4 0',
  search: 'M7 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM13 13l-2.5-2.5',
  copy: 'M5 5h7v8H5zM3 3h7v2M3 3v8h2',
  dl: 'M8 2v8M5 8l3 3 3-3M3 14h10',
  eye: 'M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5zM8 10.5A2.5 2.5 0 1 0 8 5.5a2.5 2.5 0 0 0 0 5z',
  eyeOff: 'M3 3l10 10M11.3 11.3A7 7 0 0 1 1 8s1-2 3-3.5M5.5 5.5A2.5 2.5 0 0 1 10.5 10.5M9 4a7 7 0 0 1 6 4 12 12 0 0 1-1.5 2',
  refresh: 'M2 8a6 6 0 0 1 11-3.5M14 8a6 6 0 0 1-11 3.5M11 4.5h2v-2M5 11.5H3v2',
  filter: 'M2 3h12l-4.5 5v5L7 12V8z',
  spark: 'M2 11l3-4 3 3 5-7',
  info: 'M8 5v3M8 11v.01M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12z',
  sun: 'M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8 1v2M8 13v2M14 8h-2M2 8h2M12.2 3.8l-1.4 1.4M5.2 10.8l-1.4 1.4M12.2 12.2l-1.4-1.4M5.2 5.2L3.8 3.8',
  moon: 'M13 9a5 5 0 0 1-7-7 6 6 0 1 0 7 7z',
  diff: 'M5 3v10M3 5l2-2 2 2M11 13V3M9 11l2 2 2-2',
  server: 'M2 3h12v4H2zM2 9h12v4H2zM4 5h.01M4 11h.01',
  lock: 'M4 7V5a4 4 0 0 1 8 0v2M3 7h10v7H3z',
  spinner: 'M8 2v3M8 11v3M14 8h-3M5 8H2M12.2 3.8l-2 2M5.8 10.2l-2 2M12.2 12.2l-2-2M5.8 5.8l-2-2',
  star: 'M8 1l2.2 4.6L15 6.3l-3.5 3.4L12.4 15 8 12.5 3.6 15l1-5.3L1 6.3l4.8-.7z',
};

export type IconName = keyof typeof ICON_PATHS | string;

export interface IconProps {
  name: IconName;
  size?: number;
  color?: string;
  stroke?: number;
  style?: CSSProperties;
  className?: string;
}

export function Icon({ name, size = 16, color = 'currentColor', stroke = 1.5, style, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke={color}
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0, display: 'inline-block', verticalAlign: 'middle', ...(style || {}) }}
      className={className}
    >
      <path d={ICON_PATHS[name] || ''} />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// Status badge
// ─────────────────────────────────────────────────────────────
const STATUS_MAP: Record<string, { cls: string; label: string }> = {
  running: { cls: 'pill--info', label: 'running' },
  paused: { cls: 'pill--amber', label: 'paused' },
  done: { cls: 'pill--green', label: 'completed' },
  completed: { cls: 'pill--green', label: 'completed' },
  promoted: { cls: 'pill--green', label: 'promoted' },
  stopped: { cls: 'pill--ghost', label: 'stopped' },
  failed: { cls: 'pill--red', label: 'failed' },
  pending: { cls: 'pill--amber', label: 'pending' },
  queued: { cls: 'pill--ghost', label: 'queued' },
  timed_out: { cls: 'pill--amber', label: 'timed out' },
  phase_failed: { cls: 'pill--red', label: 'phase failed' },
  promotion_blocked: { cls: 'pill--amber', label: 'promotion blocked' },
};

export function StatusBadge({ s }: { s: string }) {
  const m = STATUS_MAP[s] || STATUS_MAP.done;
  return (
    <span className={`pill ${m.cls}`}>
      <span className="dot" />
      {m.label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────
// Stat — label + big number
// ─────────────────────────────────────────────────────────────
export interface StatProps {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  delta?: string;
  deltaDir?: 'up' | 'dn' | 'flat';
  valueSize?: 'sm' | 'lg';
}

export function Stat({ label, value, sub, delta, deltaDir, valueSize }: StatProps) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div
        className={`stat__value ${valueSize === 'sm' ? 'stat__value--sm' : valueSize === 'lg' ? 'stat__value--lg' : ''}`}
      >
        {value}
        {delta && (
          <span className={`delta delta--${deltaDir || 'flat'}`} style={{ marginLeft: 8, fontSize: '0.55em' }}>
            {deltaDir === 'up' ? '▲' : deltaDir === 'dn' ? '▼' : '·'} {delta}
          </span>
        )}
      </div>
      {sub && <div className="stat__sub">{sub}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Sparkline
// ─────────────────────────────────────────────────────────────
export interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  fill?: boolean;
}

export function Sparkline({ data, color, height = 32, fill = false }: SparklineProps) {
  if (!data || data.length < 2) {
    return <svg style={{ width: '100%', height, display: 'block' }} />;
  }
  const w = 120;
  const h = height;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const norm = (v: number) => h - 2 - ((v - min) / (max - min || 1)) * (h - 6);
  const step = w / (data.length - 1);
  const d = data
    .map((v, i) => `${i === 0 ? 'M' : 'L'} ${(i * step).toFixed(2)} ${norm(v).toFixed(2)}`)
    .join(' ');
  const f = fill ? `${d} L ${w} ${h} L 0 ${h} Z` : null;
  const c = color || 'var(--fg-2)';
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height, display: 'block' }}>
      {fill && f && <path d={f} fill={c} opacity={0.12} />}
      <path d={d} stroke={c} strokeWidth={1.25} fill="none" />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// Metric chart (axes, grid, dots colored by gate pass)
// ─────────────────────────────────────────────────────────────
export interface MetricPoint {
  i: number;
  v: number;
  gates: boolean;
}

export interface MetricChartProps {
  points: MetricPoint[];
  height?: number;
  showAxis?: boolean;
  showBest?: boolean;
}

export function MetricChart({ points, height = 280, showAxis = true, showBest = true }: MetricChartProps) {
  if (!points.length) {
    return (
      <div className="placeholder" style={{ height }}>
        no iteration metrics yet
      </div>
    );
  }
  const w = 1000;
  const h = height;
  const padL = showAxis ? 44 : 8;
  const padR = 12;
  const padT = 14;
  const padB = showAxis ? 26 : 8;
  const xs = points.map((p) => p.i);
  const ys = points.map((p) => p.v);
  const yMinRaw = Math.min(...ys);
  const yMaxRaw = Math.max(...ys);
  const yMin = yMinRaw === yMaxRaw ? yMinRaw - 0.01 : yMinRaw * 0.985;
  const yMax = yMinRaw === yMaxRaw ? yMaxRaw + 0.01 : yMaxRaw * 1.015;
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const X = (x: number) => padL + ((x - xMin) / (xMax - xMin || 1)) * (w - padL - padR);
  const Y = (y: number) => padT + (1 - (y - yMin) / (yMax - yMin || 1)) * (h - padT - padB);
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${X(p.i).toFixed(1)} ${Y(p.v).toFixed(1)}`)
    .join(' ');
  const area = `${path} L ${X(xMax).toFixed(1)} ${h - padB} L ${X(xMin).toFixed(1)} ${h - padB} Z`;
  const gridY = 5;
  const best = Math.max(...ys);
  const bestIdx = ys.indexOf(best);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height, display: 'block' }}>
      <g className="chart-grid">
        {Array.from({ length: gridY + 1 }).map((_, i) => {
          const y = padT + (i * (h - padT - padB)) / gridY;
          return <line key={i} x1={padL} x2={w - padR} y1={y} y2={y} strokeWidth={1} />;
        })}
      </g>
      {showAxis && (
        <g className="chart-axis">
          {Array.from({ length: gridY + 1 }).map((_, i) => {
            const y = padT + (i * (h - padT - padB)) / gridY;
            const v = (yMax - ((yMax - yMin) * i) / gridY).toFixed(3);
            return (
              <text key={i} x={padL - 8} y={y + 3} textAnchor="end">
                {v}
              </text>
            );
          })}
          {points
            .filter((_, i) => i % Math.max(1, Math.ceil(points.length / 8)) === 0)
            .map((p) => (
              <text key={`xl-${p.i}`} x={X(p.i)} y={h - 8} textAnchor="middle">
                {p.i}
              </text>
            ))}
        </g>
      )}
      <path d={area} fill="var(--fg-2)" opacity={0.05} />
      {showBest && (
        <g>
          <line
            x1={padL}
            x2={w - padR}
            y1={Y(best)}
            y2={Y(best)}
            stroke="var(--green)"
            strokeWidth={1}
            strokeDasharray="3 3"
            opacity={0.6}
          />
          <text
            x={w - padR - 4}
            y={Y(best) - 5}
            textAnchor="end"
            fill="var(--green)"
            fontFamily="IBM Plex Mono, monospace"
            fontSize={10}
          >
            best {best.toFixed(3)}
          </text>
        </g>
      )}
      <path d={path} stroke="var(--fg)" strokeWidth={1.5} fill="none" />
      {points.map((p, i) => (
        <g key={p.i}>
          <circle
            cx={X(p.i)}
            cy={Y(p.v)}
            r={i === bestIdx ? 5 : 3.5}
            fill={p.gates ? 'var(--green)' : 'var(--red)'}
            stroke="var(--bg)"
            strokeWidth={1.5}
          />
          {i === bestIdx && (
            <circle cx={X(p.i)} cy={Y(p.v)} r={9} fill="none" stroke="var(--green)" strokeWidth={1} opacity={0.5} />
          )}
        </g>
      ))}
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// Phase bar
// ─────────────────────────────────────────────────────────────
export interface PhaseBarItem {
  id?: string;
  label: string;
  status?: string;
}

export interface PhaseBarProps {
  phases: Array<string | PhaseBarItem>;
  active?: number;
}

function phaseClass(status: string | undefined, index: number, active?: number): string {
  const normalized = status || (active == null ? '' : index < active ? 'completed' : index === active ? 'in_progress' : 'pending');
  if (normalized === 'completed' || normalized === 'done') return 'is-done';
  if (normalized === 'blocked') return 'is-blocked';
  if (normalized === 'in_progress' || normalized === 'active') return 'is-active';
  return '';
}

export function PhaseBar({ phases, active }: PhaseBarProps) {
  return (
    <div className="row gap-2">
      {phases.map((phase, i) => {
        const label = typeof phase === 'string' ? phase : phase.label;
        const id = typeof phase === 'string' ? phase : phase.id || phase.label;
        const state = phaseClass(typeof phase === 'string' ? undefined : phase.status, i, active);
        return (
          <div key={id} className={`phase ${state}`}>
            <div className="phase__lbl">step {String(i + 1).padStart(2, '0')}</div>
            <div className="phase__name truncate">{label}</div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Field helpers
// ─────────────────────────────────────────────────────────────
export interface FieldProps {
  label: ReactNode;
  required?: boolean;
  help?: ReactNode;
  children: ReactNode;
}

export function Field({ label, required, help, children }: FieldProps) {
  return (
    <div className="field">
      <div className="field__lbl">
        {label}
        {required && <span className="req">required</span>}
      </div>
      {children}
      {help && <div className="field__help">{help}</div>}
    </div>
  );
}

export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedProps {
  options: Array<string | SegmentedOption>;
  value: string;
  onChange?: (value: string) => void;
}

export function Segmented({ options, value, onChange }: SegmentedProps) {
  return (
    <div className="btn-group">
      {options.map((o) => {
        const k = typeof o === 'string' ? o : o.value;
        const l = typeof o === 'string' ? o : o.label;
        return (
          <div key={k} className={`seg ${value === k ? 'on' : ''}`} onClick={() => onChange?.(k)}>
            {l}
          </div>
        );
      })}
    </div>
  );
}
