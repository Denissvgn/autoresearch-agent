// Leaderboard (P0-4): cross-session comparison for one skill.
// Ranked by the skill's declared primary-metric direction (server-side sort).
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSkills, useSkillLeaderboard } from '../hooks/useResearch';
import { Icon, StatusBadge } from '../components/hifi/primitives';
import { LeaderboardEntry } from '../api/client';

function fmtMetric(v: number | null, format = '.4f') {
  if (v == null) return '—';
  const digits = Number(format.split('.')[1]?.replace(/[^0-9]/g, '') ?? 4);
  return v.toFixed(Math.min(8, digits));
}

function fmtCost(v: number) {
  return `$${v.toFixed(2)}`;
}

function fmtRelative(iso: string | null) {
  if (!iso) return '—';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

export default function Leaderboard() {
  const { data: skills } = useSkills();
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const { data: board, isLoading } = useSkillLeaderboard(selectedSkillId, 50);

  useEffect(() => {
    if (!selectedSkillId && skills && skills.length > 0) {
      setSelectedSkillId(skills[0].id);
    }
  }, [skills, selectedSkillId]);

  const items: LeaderboardEntry[] = useMemo(() => board?.items ?? [], [board]);
  const metricLabel = board?.metric.label ?? 'Best metric';

  return (
    <div className="col gap-5" style={{ padding: 24 }}>
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <div className="col gap-1 grow">
          <span className="label">comparison</span>
          <h1 className="h1">Leaderboard</h1>
        </div>
        <div className="field" style={{ minWidth: 260 }}>
          <div className="field__lbl">Skill</div>
          <select
            className="input mono"
            value={selectedSkillId ?? ''}
            onChange={(e) => setSelectedSkillId(e.target.value || null)}
          >
            {(skills ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.display_name || s.id}
              </option>
            ))}
          </select>
        </div>
      </div>

      <section className="card" style={{ padding: 0 }}>
        <div className="row" style={{ justifyContent: 'space-between', padding: '14px 16px' }}>
          <span className="label">
            {metricLabel} · {board?.total ?? 0} scored sessions
          </span>
          {isLoading && <span className="subtle">loading…</span>}
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>#</th>
                <th>Session</th>
                <th>Subject · Variant</th>
                <th className="num">Best</th>
                <th className="num">Iters</th>
                <th className="num">Cost</th>
                <th>Status</th>
                <th>When</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row, i) => (
                <tr key={row.research_id}>
                  <td className="mono">{i + 1}</td>
                  <td className="mono">
                    <Link to={`/research/${row.research_id}`} className="lnk">
                      {row.research_id.slice(0, 12)}
                    </Link>
                    {row.tag ? <span className="pill pill--ghost" style={{ marginLeft: 8 }}>{row.tag}</span> : null}
                  </td>
                  <td className="subtle">
                    {row.subject_id ?? '—'} · {row.variant ?? '—'}
                  </td>
                  <td className="num mono">{fmtMetric(row.best_metric, board?.metric.format)}</td>
                  <td className="num mono">{row.iterations}</td>
                  <td className="num mono">{fmtCost(row.total_api_cost_usd)}</td>
                  <td><StatusBadge s={row.status} /></td>
                  <td className="subtle">{fmtRelative(row.completed_at ?? row.started_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Icon name="chevR" size={14} color="var(--faint)" />
                  </td>
                </tr>
              ))}
              {items.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={9} className="subtle" style={{ textAlign: 'center', padding: 24 }}>
                    No scored sessions for this skill yet — start one from New Research.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
