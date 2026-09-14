// Skill Studio (P2 Skill SDK): installed skills + the generation wizard.
// The wizard is the UI face of `autoresearch new-skill` — it drafts a skill
// package from a goal (POST /skills/generate, feature-flagged server-side)
// and surfaces the policy audit. Promotion stays an operator act (CLI).
import { FormEvent, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSkills } from '../hooks/useResearch';
import { api, GeneratedSkillDraft } from '../api/client';

export default function Skills() {
  const { data: skills, isLoading } = useSkills();
  const [goal, setGoal] = useState('');
  const [skillId, setSkillId] = useState('');
  const [draft, setDraft] = useState<GeneratedSkillDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const generate = useMutation({
    mutationFn: () =>
      api.generateSkill({
        goal: goal.trim(),
        ...(skillId.trim() ? { skill_id: skillId.trim() } : {}),
      }),
    onSuccess: (body) => {
      setDraft(body);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['skills'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setDraft(null);
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (goal.trim().length < 8 || generate.isPending) return;
    generate.mutate();
  }

  const flagDisabled = error?.includes('skill_generator_disabled') ?? false;

  return (
    <div className="col gap-5" style={{ padding: 24 }}>
      <div className="col gap-1">
        <span className="label">skill sdk</span>
        <h1 className="h1">Skill Studio</h1>
        <p className="subtle" style={{ maxWidth: 640 }}>
          Installed skills drive every session. Describe a new research domain
          and the generator drafts a full package — manifest, bootstrap, eval,
          primer — validated and policy-audited into a draft you review before
          it goes live.
        </p>
      </div>

      <div className="row gap-5" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {/* ── Installed skills ─────────────────────────────────────────── */}
        <section className="card grow" style={{ padding: 0, minWidth: 340 }}>
          <div className="row" style={{ justifyContent: 'space-between', padding: '14px 16px' }}>
            <span className="label">installed · {skills?.length ?? 0}</span>
            {isLoading && <span className="subtle">loading…</span>}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Skill</th>
                  <th>Version</th>
                  <th>Category</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {(skills ?? []).map((s) => (
                  <tr key={s.id}>
                    <td className="mono">{s.display_name || s.id}</td>
                    <td className="mono subtle">{s.version}</td>
                    <td className="subtle">{s.category}</td>
                    <td className="subtle">{s.description}</td>
                  </tr>
                ))}
                {skills?.length === 0 && !isLoading && (
                  <tr>
                    <td colSpan={4} className="subtle" style={{ textAlign: 'center', padding: 24 }}>
                      No skills installed — generate one on the right.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Generation wizard ────────────────────────────────────────── */}
        <section className="card" style={{ padding: 16, minWidth: 320, maxWidth: 460 }}>
          <span className="label">new-skill wizard</span>
          <form className="col gap-3" onSubmit={handleSubmit} style={{ marginTop: 10 }}>
            <div className="field">
              <div className="field__lbl">Goal</div>
              <textarea
                className="input"
                rows={4}
                placeholder="e.g. tune a Postgres config for latency under a fixed workload…"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              />
            </div>
            <div className="field">
              <div className="field__lbl">Skill id (optional)</div>
              <input
                className="input mono"
                placeholder="my-skill"
                value={skillId}
                onChange={(e) => setSkillId(e.target.value)}
              />
            </div>
            <button
              className="btn btn--primary"
              type="submit"
              disabled={goal.trim().length < 8 || generate.isPending}
            >
              {generate.isPending ? 'Generating…' : 'Generate draft'}
            </button>
          </form>

          {flagDisabled && (
            <p className="subtle" style={{ marginTop: 12, fontSize: 12 }}>
              Generation is disabled on this server. Set{' '}
              <code>AUTORESEARCH_SKILL_GENERATOR_ENABLED=true</code> to expose
              it (it spends LLM tokens and writes drafts into{' '}
              <code>skills/_drafts/</code>).
            </p>
          )}
          {error && !flagDisabled && (
            <p className="subtle" style={{ marginTop: 12, fontSize: 12, whiteSpace: 'pre-wrap' }}>
              {error}
            </p>
          )}

          {draft && (
            <div className="col gap-2" style={{ marginTop: 14 }}>
              <span className="label">
                draft · <span className="mono">{draft.skill_id}</span>
              </span>
              <div className="subtle mono" style={{ fontSize: 12 }}>
                {draft.files.join('  ·  ')}
              </div>
              {draft.policy_findings.length === 0 ? (
                <span className="pill pill--green">policy audit clean</span>
              ) : (
                <div className="col gap-1">
                  {draft.policy_findings.map((f, i) => (
                    <span
                      key={i}
                      className={`pill ${f.severity === 'critical' ? 'pill--red' : 'pill--ghost'}`}
                      style={{ alignSelf: 'flex-start' }}
                    >
                      {f.severity}: {f.reason}
                    </span>
                  ))}
                </div>
              )}
              <p className="subtle" style={{ fontSize: 12 }}>
                {draft.next}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
