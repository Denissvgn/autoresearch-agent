# Autoresearch Agent Workspace

You are running inside the autoresearch-agent Docker container.
Your job is to autonomously run research iterations for the session's skill. Act immediately — do NOT explore the filesystem. The workspace is already set up for you.

## CRITICAL: Fully Autonomous — Never Ask Questions

You are running **unattended**. There is NO human monitoring this session. You MUST:
- **NEVER ask questions** — there is nobody to answer them.
- **NEVER say "should I…?" or "would you like…?"** — make the decision yourself.
- **NEVER wait for confirmation** — act on your best judgment immediately.
- When facing ambiguity, **always choose the approach most likely to improve the primary metric**.
- When a parameter change fails, **immediately revert and try a different dimension** — do not dwell or re-run the same thing.
- When you encounter an error, diagnose it yourself using the skill's SKILL.md context and retry with an alternative approach.

## CRITICAL: Act, Don't Explore

You have a LIMITED number of tool calls. **Do not waste them** on `ls`, `find`, `cat`, or process listings. Dependency readiness is handled by the server before your session starts. Jump straight to running experiments.

## Quick Reference

- **Python**: `/app/workspace/.venv/bin/python` (never system python)
- **Working dir**: `/app/workspace/`
- **Skill instructions**: the session prompt carries the skill's SKILL.md and its experiment command template. Follow it exactly.
- **Promotion handoff**: Do not promote directly. Finish with a best validated result and let the server preview/confirm.
- Dependency readiness is recorded in the server-owned research manifest.

## Exact Experiment Loop

**Step 1** — If the session prompt supplies a setup command, run it (1 tool call). Fresh sessions arrive with a **server-bootstrapped** workspace (the skill's `bootstrap.py` ran before your session started); continuation sessions reuse the existing workspace and do not reset it.

**Step 2** — Read the skill's reference docs (SKILL.md, knowledge/) and the current config/candidate file (1 tool call). If the workspace already contains tuned state from prior sessions, treat it as part of the baseline. Do not overwrite it with generic defaults before you have reproduced the baseline once.

**Step 3** — Baseline run (1 tool call): execute the skill's experiment command exactly as supplied. Do NOT append `2>&1`, `| tail`, `| head`, or any other shell redirection or pipe — command policy rejects them. After the run completes, copy the current candidate file to its `best_*` counterpart if the skill instructions call for it.

**Step 4** — For each subsequent iteration:
1. Edit the candidate file (change ONE meaningful variable per the skill's guidance)
2. Run the experiment command again
3. Check the emitted metrics: if the primary metric improved AND all gates passed, keep the change (update the best files); otherwise revert from best.
4. **Robustness check**: if the output includes stability or holdout metrics (folds, seeds, variance), weigh them alongside the primary metric. An improvement that degrades stability is fragile — consider discarding it.
5. Output the iteration marker in the format your skill declares (e.g. `ITERATION_RESULT: {"iteration": N, "primary_metric": X.XXXX, "metric_name": "...", "all_gates_passed": true|false, "decision": "keep|discard", "description": "brief description"}`).

   **IMPORTANT:** Emit the iteration marker ONLY immediately after an experiment command run in the same turn. Do NOT emit a marker on turns where you only ran `cp`, `read_file`, or `write_file` — the server will discard those markers. Revert/restore turns are bookkeeping, not iterations.

## Rules

- NEVER write outside `/app/workspace/`
- Do NOT run `docker`, `git`, `make`, or `apt` — they are not installed
- Spend at most 2-3 tool calls on setup/reading, then START EXPERIMENTING
- **NEVER pipe experiment output** through `| tail`, `| head`, `| grep`, or `timeout`. The full stdout is critical for iteration detection. Run the experiment command directly and rely on the bash tool's default timeout.
- If the experiment crashes with transient connection errors (external services), wait 15 seconds and retry once. Do NOT spend iterations debugging infrastructure.

## Anti-Waste Rules (MANDATORY)

These rules prevent common failure patterns observed in research sessions:

1. **Never re-run the exact same configuration** — deterministic experiments return the same result. Always change at least one meaningful parameter.
2. **Never change ONLY a random seed** — if a configuration only works with one specific seed, it is not robust and will never pass multi-seed validation. Changing the seed is not a valid optimization strategy.
3. **Make meaningful changes** — do not nudge parameters by tiny amounts. Change by at least 2× or 0.5× for multiplicative params, or jump to a qualitatively different value.
4. **Never "restore best and re-run unchanged"** — if you already ran that configuration, re-running it gives the same result. Always vary at least one parameter when restoring from best.
5. **Diversify search dimensions** — if 3+ consecutive iterations tuned the same parameter, switch to a completely different dimension.
6. **Screening trap**: if the skill offers a quick/screening mode, use it for triage only. Validate promising candidates in full mode EARLY (don't wait until the last iteration). Quick-mode winners often fail in full mode — expect this and plan for it.
